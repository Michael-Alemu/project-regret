# ============================
# 🎬 Imports & Config
# ============================
from config import TEMP_CHUNK_DIR, TEMP_UPLOAD_DIR, MANIFEST_DIR, CHUNK_SIZE_BYTES
from pathlib import Path
import json

from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List
import time
import threading

import os
import uuid
import random
import requests
import shutil
import base64
from chunk_utils import split_file, reassemble_file
from crypto_utils import decrypt_bytes, generate_key, encrypt_bytes
from manifest_utils import ManifestChunkManager

# ============================
# 🏁 Global Constants
# ============================
CHUNK_REDUNDANCY = 3
HEARTBEAT_TIMEOUT = 30
healing_queue = []

# ============================
# 📜 Manifest Manager Setup
# ============================
manifest_encryption_key = generate_key()

manifest_manager = ManifestChunkManager(
    manifest_dir=MANIFEST_DIR,
    chunk_size=4096,
    encryption_key=manifest_encryption_key
)

# ============================
# ⚙️ RAM-Based Node Registry
# ============================
nodes: Dict[str, Dict[str, float]] = {}
chunk_map: Dict[str, List[str]] = {}

# ============================
# 📦 API Models
# ============================
class NodeRegistration(BaseModel):
    """
    📦 Node registration payload schema.

    Attributes:
        node_id (str): Unique identifier for the node.
        storage_available (int): Storage space available on the node.
    """
    node_id: str  # who dis
    storage_available: int  # how much space u got

class Heartbeat(BaseModel):
    """
    ❤️ Heartbeat payload schema.

    Attributes:
        node_id (str): ID of the node sending the heartbeat.
    """
    node_id: str  # just sayin hi

class ChunkAssignment(BaseModel):
    """
    📦 Chunk assignment payload schema.

    Attributes:
        chunk_id (str): ID of the chunk.
        node_id (str): Node assigned to store the chunk.
    """
    chunk_id: str  # unique chunk name
    node_id: str   # node that stores this chunk

# ============================
# 🚪 Node Registration Endpoint
# ============================
app = FastAPI()

@app.post("/register")
def register_node(node: dict):
    """
    🚪 Doorway to the network. Enter your info, traveler.

    Args:
        node (dict): Node metadata including ID, IP, port, and storage.

    Returns:
        dict: Registration status.
    """
    node_id = node["node_id"]
    nodes[node_id] = {
        "storage_available": node["storage_available"],
        "ip": node["ip"],
        "port": node["port"],
        "last_seen": time.time()
    }
    print(f"🆕 Registered node {node_id} at {node['ip']}:{node['port']}")
    return {"status": "registered"}

# ============================
# ❤️ Heartbeat Monitor
# ============================
@app.post("/heartbeat")
def heartbeat(hb: Heartbeat):
    """
    ❤️ Nodes yell out: "I'm alive!" Otherwise we hold a funeral.
     Args:
        hb (Heartbeat): Heartbeat payload.

    Returns:
        dict: Heartbeat acknowledgment.
    """
    now = time.time()

    # --- THIS PART MOVES TO THE TOP ---
    # 1. Let the living node check in and update its 'last_seen' timestamp.
    if hb.node_id in nodes:
        nodes[hb.node_id]["last_seen"] = now
    else:
        # If a node sends a heartbeat but isn't registered, it's a ghost.
        raise HTTPException(status_code=404, detail=f"Ghost node {hb.node_id} tried to heartbeat. Not registered.")
    # --- END OF MOVED PART ---

    # 2. NOW, after everyone's had a chance to check in, find the ones who didn't.
    for node_id in list(nodes.keys()):
        # Use a slightly longer timeout here to be safe
        if now - nodes[node_id].get("last_seen", 0) > HEARTBEAT_TIMEOUT:
            mark_node_dead(node_id)
            del nodes[node_id]

    return {"status": "alive"}  # We can return alive even if others died.

# ============================
# 📡 View Active Nodes
# ============================
@app.get("/nodes")
def get_nodes():
    """
     📡 Peek behind the curtain — see who's online.

    Returns:
        dict: Node metadata including IP, port, and last seen.
    """
    return nodes

# ============================
# 🔍 Find Chunk Holders
# ============================
@app.get("/chunk/{chunk_id}")
def get_chunk_locations(chunk_id: str):
    """
    🔍 Get all nodes that store a specific chunk.

    Args:
        chunk_id (str): The ID of the chunk.

    Returns:
        dict: List of node IDs storing the chunk.
    """
    if chunk_id in chunk_map:
        return {"nodes": chunk_map[chunk_id]}
    raise HTTPException(status_code=404, detail="Chunk not found")

# ============================
# 📦 Manual Chunk Assignment
# ============================
@app.post("/chunk")
def assign_chunk(assignment: ChunkAssignment):
    """
    📦 Sling a chunk over to a chosen node.

    Args:
        assignment (ChunkAssignment): Chunk assignment request.

    Returns:
        dict: Assignment confirmation.
    """
    if assignment.chunk_id not in chunk_map:
        chunk_map[assignment.chunk_id] = []
    if assignment.node_id not in chunk_map[assignment.chunk_id]:
        chunk_map[assignment.chunk_id].append(assignment.node_id)
    return {"status": "chunk assigned"}

# ============================
# 🔑 Encryption Keys Info
# ============================
@app.get("/keys")
def get_keys_info():
    """
    🔑 How many secrets do we know?
    """
    return {"stored_keys": len(manifest_manager.list_manifests())}

# ============================
# 📜 Retrieve Manifest
# ============================
@app.get("/manifest/{file_id}")
def get_manifest(file_id: str):
    """
    📜 Retrieve the manifest for a given file.

    Args:
        file_id (str): The ID of the file.

    Returns:
        dict: File manifest or 404 error.
    """
    manifest = manifest_manager.load_manifest(file_id)
    if not manifest:
        return {"error": "file_id not found"}, 404

    # 🧽 Patch it for JSON friendliness
    if isinstance(manifest.get("encryption_key"), bytes):
        manifest["encryption_key"] = base64.urlsafe_b64encode(
        manifest["encryption_key"]
    ).decode("utf-8")
    return manifest

# ============================
# 📤 Upload + Chunkify + Encrypt
# ============================
@app.post("/upload_file")
def upload_file(file: UploadFile = File(...)):
    """
    📤 Split it, scramble it, send it. It's magic.

    Args:
        file (UploadFile): File uploaded via POST.

    Returns:
        dict: Upload confirmation, file_id, and chunk count.
    """
    # 👶 Give this file a unique ID, because we're fancy
    file_id = f"file-{uuid.uuid4().hex[:6]}"
    filename = file.filename
    temp_file_path = TEMP_UPLOAD_DIR / f"temp_{file_id}_{filename}"

    # 💾 Save uploaded file locally
    with open(temp_file_path, "wb") as f:
        f.write(file.file.read())

    # 🛡️ Generate an encryption key for this file
    file_key = generate_key()
    chunk_paths = split_file(temp_file_path, chunk_size_bytes=CHUNK_SIZE_BYTES)

    if not nodes:
        return {"error": "No nodes online"}, 503

    chunk_records = []

    for chunk_path in chunk_paths:
        chunk_id = os.path.basename(chunk_path)

        # 🧹 Read the raw chunk
        with open(chunk_path, "rb") as chunk_file:
            chunk_data = chunk_file.read()

        # 🔒 Encrypt the chunk BEFORE upload
        encrypted_chunk = encrypt_bytes(chunk_data, file_key)

        # 🎯 Pick a random node to send the chunk to
        available_nodes = list(nodes.keys())
        selected_nodes = random.sample(available_nodes, min(CHUNK_REDUNDANCY, len(available_nodes)))

        chunk_success_nodes = []

        for node_id in selected_nodes:
            node_info = nodes[node_id]
            node_url = f"http://{node_info['ip']}:{node_info['port']}/store_chunk"

            try:
                res = requests.post(node_url, files={"chunk": (chunk_id, encrypted_chunk)}, data={"chunk_id": chunk_id})
                if res.status_code == 200:
                    print(f"📦 Sent {chunk_id} to {node_id}")
                    chunk_success_nodes.append(node_id)
                else:
                    print(f"⚠️ Failed to store chunk {chunk_id} on {node_id}")
            except Exception as e:
                print(f"🔥 Error sending chunk {chunk_id} to {node_id}: {e}")

        if chunk_success_nodes:
            chunk_records.append({
                "chunk_id": chunk_id,
                "node_ids": chunk_success_nodes
            })
        else:
            print(f"❌ No nodes accepted chunk {chunk_id}, skipping.")

    # 🛡️ Generate a JSON-safe encryption key string for THIS file
    file_key_string = file_key if isinstance(file_key, str) else file_key.decode("utf-8") # This now returns a string

    manifest_manager.save_manifest(file_id, {
        "original_filename": filename,
        "chunks": chunk_records,
        "encryption_key": file_key_string
    })

    # 🧹 Clean up temporary file + chunks
    os.remove(temp_file_path)
    for chunk_path in chunk_paths:
        os.remove(chunk_path)

    return {"file_id": file_id, "chunks_stored": len(chunk_records)}

# ============================
# 📦 Download + Reassemble
# ============================
@app.get("/download_file/{file_id}")
def download_file(file_id: str, background_tasks: BackgroundTasks):
    """
    📦 Download, decrypt, and reassemble a file using its manifest.

    Args:
        file_id (str): The ID of the file to download.

    Returns:
        FileResponse: The fully reassembled and decrypted file.
    """
    manifest = manifest_manager.load_manifest(file_id)
    if not manifest:
        return {"error": "File not found"}, 404

    # 🔑 Get the encryption key
    file_key = manifest.get("encryption_key")
    if not file_key:
        return {"error": "Encryption key not found"}, 500

    # 🗃️ Make a folder to store the returning chunk babies
    temp_dir = TEMP_CHUNK_DIR / f"{file_id}"
    os.makedirs(temp_dir, exist_ok=True)

    # 🔄 Loop through each chunk in the manifest
    for chunk in manifest["chunks"]:
        chunk_id = chunk["chunk_id"]
        node_ids = chunk["node_ids"]

        # 🛰️ Try fetching from any available node
        success = False
        for node_id in node_ids:
            node = nodes.get(node_id)
            if not node:
                continue

            url = f"http://{node['ip']}:{node['port']}/chunk/{chunk_id}"
            try:
                res = requests.get(url)
                if res.status_code == 200:
                    # 🔓 Decrypt the chunk before saving
                    decrypted_chunk = decrypt_bytes(res.content, file_key)

                    with open(os.path.join(temp_dir, chunk_id), "wb") as f:
                        f.write(decrypted_chunk)

                    success = True
                    break  # ✅ Done, stop trying nodes
            except Exception:
                continue

        if not success:
            return {"error": f"Failed to fetch chunk {chunk_id} from any node"}, 502

    # 🧩 All chunks retrieved and decrypted, time to stitch the beast
    output_file = f"reassembled_{manifest['original_filename']}"
    reassemble_file(output_file, temp_dir)

    background_tasks.add_task(cleanup_temp_folder, temp_dir)

    # 🎁 Send the reassembled file back like a gift
    return FileResponse(output_file, filename=manifest["original_filename"])

# ============================
# 🧹 Cleanup Temporary Graveyards
# ============================
def cleanup_temp_folder(folder_path: str):
    """
    🧼 Clean up temporary folder used during file recovery.

    Args:
        folder_path (str): Path to the folder to remove.
    """
    try:
        shutil.rmtree(folder_path)
        print(f"🧼 Cleaned up: {folder_path}")
    except Exception as e:
        print(f"⚠️ Failed to clean {folder_path}: {e}")

# ============================
# 📊 System Status Dashboard
# ============================
@app.get("/status")
def get_system_status():
    """
    Check the heartbeats of the universe.
    📊 Return current system status including nodes, files, and chunks.

    Returns:
        dict: Overview of registered nodes, stored files, and chunk distribution.
    """
    all_manifest_ids = manifest_manager.list_manifests()

    file_details = {}
    errors = []
    total_chunks = 0

    # NOW, we try to load each one, and we prepare for failure.
    for file_id in all_manifest_ids:
        try:
            # Try to perform the dangerous act of loading a manifest
            manifest = manifest_manager.load_manifest(file_id)
            chunk_count = len(manifest.get("chunks", []))
            file_details[file_id] = {
                "original_filename": manifest.get("original_filename", "N/A"),
                "chunk_count": chunk_count
            }
            total_chunks += chunk_count
        except Exception as e:
            # If a manifest is broken, DON'T CRASH. Report it.
            errors.append({"file_id": file_id, "error": str(e)})

    return {
        "node_count": len(nodes),
        "registered_nodes": list(nodes.keys()),
        "file_count": len(all_manifest_ids),
        "files": file_details,
        "total_chunks": total_chunks,
        "manifest_errors": errors  # <<<<<<<<<<<< THIS IS THE KEY
    }
# ============================
# 🩹 Healing Process
# ============================
@app.post("/heal_now")
def heal_now():
    """
    🩹 Manually slap on band-aids to busted chunks.
    """
    threading.Thread(target=heal_chunks, daemon=True).start()
    return {"status": "Healing started in background"}


# The fixed, glorious way
def mark_node_dead(dead_node_id: str):
    """⚰️ Lays a node to rest and queues its chunks for reincarnation."""
    print(f"⚰️ Node {dead_node_id} has been marked for death.")

    # Get the simple list of all known file IDs.
    all_file_ids = manifest_manager.list_manifests()

    # Loop through the IDs one by one.
    for file_id in all_file_ids:
        try:
            # For each ID, load the full manifest from disk.
            manifest = manifest_manager.load_manifest(file_id)

            # --- Your original logic now works perfectly ---
            needs_update = False
            for chunk in manifest.get("chunks", []):
                if dead_node_id in chunk.get("node_ids", []):
                    chunk["node_ids"].remove(dead_node_id)
                    needs_update = True
                    print(f"  -> Found chunk {chunk['chunk_id']} belonging to dead node.")

                    if len(chunk["node_ids"]) < CHUNK_REDUNDANCY:
                        if chunk["chunk_id"] not in healing_queue:
                            healing_queue.append(chunk["chunk_id"])
                            print(f"    🚑 Queued {chunk['chunk_id']} for emergency healing.")

            # If we made any changes, save the manifest back to disk.
            if needs_update:
                manifest_manager.update_manifest(file_id, manifest)
                print(f"  -> Updated manifest for {file_id}.")

        except FileNotFoundError:
            # This is fine. Just means the manifest was a ghost.
            print(f"  -> Skipped ghost manifest for {file_id}.")
            continue


# ============================
# ❤️‍🩹 The Healing Daemon (V2)
# ============================
def heal_chunks():
    """
    🩹 Patches wounded soldiers (chunks) from the healing queue.

       b
        This is the heart of our network's resilience. It never sleeps.
    """
    while True:
        if not healing_queue:
            time.sleep(5)  # Rest if there are no wounded.
            continue

        print(f"🧪 Healing Queue has {len(healing_queue)} chunks. Engaging...")
        chunk_id_to_heal = healing_queue.pop(0)  # FIFO healing

        found_and_healed = False
        all_file_ids = manifest_manager.list_manifests()

        # 🧙 Scan all manifests to find the parent of this wounded chunk.
        for file_id in all_file_ids:
            if found_and_healed: break
            try:
                manifest = manifest_manager.load_manifest(file_id)
                for chunk in manifest.get("chunks", []):
                    if chunk.get("chunk_id") == chunk_id_to_heal:
                        # --- We found the patient. Now, operate. ---

                        alive_nodes = chunk.get("node_ids", [])
                        needed = CHUNK_REDUNDANCY - len(alive_nodes)

                        if needed <= 0:
                            print(f"✅ Chunk {chunk_id_to_heal} is already healthy. False alarm.")
                            found_and_healed = True
                            break

                        available_nodes = [nid for nid in nodes if nid not in alive_nodes]
                        random.shuffle(available_nodes)

                        if not alive_nodes:
                            print(f"💀 CRITICAL: All replicas for {chunk_id_to_heal} are lost. Unhealable.")
                            found_and_healed = True  # We handled it, even if it failed.
                            break

                        # Find new homes for the replicas.
                        for new_node_id in available_nodes:
                            if needed <= 0: break

                            donor_node_id = random.choice(alive_nodes)
                            donor_node = nodes.get(donor_node_id)
                            new_node = nodes.get(new_node_id)

                            if not donor_node or not new_node: continue

                            chunk_url = f"http://{donor_node['ip']}:{donor_node['port']}/chunk/{chunk_id_to_heal}"
                            store_url = f"http://{new_node['ip']}:{new_node['port']}/store_chunk"

                            try:
                                print(
                                    f"  -> Attempting to copy {chunk_id_to_heal} from {donor_node_id} to {new_node_id}...")
                                res = requests.get(chunk_url, timeout=5)
                                if res.status_code == 200:
                                    push = requests.post(store_url, files={"chunk": res.content},
                                                         data={"chunk_id": chunk_id_to_heal})
                                    if push.status_code == 200:
                                        chunk["node_ids"].append(new_node_id)
                                        alive_nodes.append(new_node_id)
                                        needed -= 1
                                        print(f"    🧩 SUCCESS: Healed {chunk_id_to_heal} -> {new_node_id}")
                                    else:
                                        print(f"    ⚠️ FAILED to store chunk on {new_node_id}.")
                                else:
                                    print(f"    ⚠️ FAILED to fetch chunk from donor {donor_node_id}.")
                            except Exception as e:
                                print(f"    🔥 HEALING ERROR during replication: {e}")

                        # After attempting to heal, save the updated manifest.
                        manifest_manager.update_manifest(file_id, manifest)
                        found_and_healed = True
                        break  # Move to the next chunk in the queue

            except FileNotFoundError:
                continue

threading.Thread(target=heal_chunks, daemon=True).start()
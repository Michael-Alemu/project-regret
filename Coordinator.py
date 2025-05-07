from config import TEMP_CHUNK_DIR, TEMP_UPLOAD_DIR, MANIFEST_DIR, CHUNK_SIZE_BYTES
from pathlib import Path
import json

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
from chunk_utils import split_file, reassemble_file
from crypto_utils import decrypt_bytes,  generate_key, encrypt_bytes

CHUNK_REDUNDANCY = 3
HEARTBEAT_TIMEOUT = 30
healing_queue = []  # 🚑 Chunks that need help

# ============================
# 🔐 Encryption Keys Persistence
# ============================

KEYS_FILE = "encryption_keys.json"

def save_keys_to_disk():
    """ Save encryption keys to disk (plaintext) """
    with open(KEYS_FILE, "w") as f:
        json.dump(encryption_keys, f)
    print(f"💾 Saved encryption keys to {KEYS_FILE}")

def load_keys_from_disk():
    """ Load encryption keys from disk if available """
    global encryption_keys
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r") as f:
            encryption_keys = json.load(f)
        print(f"🔑 Loaded {len(encryption_keys)} encryption keys from {KEYS_FILE}")
    else:
        print(f"🕳️ No encryption keys file found. Starting fresh.")


app = FastAPI()
load_keys_from_disk()

# ============================
# 📓 Manifest store (in-memory)
# ============================

# file_id: {
#     "original_filename": str,
#     "chunks": [
#         {"chunk_id": str, "node_id": str}
#     ]
# }
file_manifests = {}

# 🗃️ Load saved manifests from disk
for manifest_file in MANIFEST_DIR.glob("*.json"):
    with open(manifest_file, "r") as f:
        manifest = json.load(f)
        file_id = manifest_file.stem
        file_manifests[file_id] = manifest
print(f"📁 Loaded {len(file_manifests)} manifest(s) from disk")

def save_manifest(file_id: str, original_filename: str, chunk_info: list):
    """
    📓 Save a manifest mapping a file to its chunks and storage nodes.

    Args:
        file_id (str): Unique file identifier.
        original_filename (str): Name of the original file.
        chunk_info (list): List of chunk metadata (chunk_id and node_id).
    """
    file_manifests[file_id] = {
        "original_filename": original_filename,
        "chunks": chunk_info
    }

    manifest_path = MANIFEST_DIR / f"{file_id}.json"
    with open(manifest_path, "w") as f:
        json.dump(file_manifests[file_id], f)

    print(f"📓 Manifest saved for {file_id} with {len(chunk_info)} chunks")


# ================================
# 🤝 Node & Chunk Storage (RAM-Only)
# ================================

nodes: Dict[str, Dict[str, float]] = {}  # node_id -> { storage: int, last_seen: float }
chunk_map: Dict[str, List[str]] = {}    # chunk_id -> list of node_ids

# ================================
# 📦 Models for incoming JSON data
# ================================

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

# ================================
# 🚪 Register a new node
# ================================
@app.post("/register")
def register_node(node: dict):
    """
    🚪 Register a node with the coordinator.

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

# ================================
# ❤️ Heartbeat endpoint
# ================================
@app.post("/heartbeat")
def heartbeat(hb: Heartbeat):
    """
    ❤️ Node heartbeat. Updates 'last_seen', or mourns the dead.
     Args:
        hb (Heartbeat): Heartbeat payload.

    Returns:
        dict: Heartbeat acknowledgment.
    """
    now = time.time()

    # ⏳ Check if any nodes are dead
    for node_id in list(nodes.keys()):
        if now - nodes[node_id]["last_seen"] > HEARTBEAT_TIMEOUT:
            mark_node_dead(node_id)
            del nodes[node_id]

    if hb.node_id in nodes:
        nodes[hb.node_id]["last_seen"] = now
        return {"status": "alive"}

    raise HTTPException(status_code=404, detail=f"Node id {hb.node_id} not found")

# ================================
# 📡 List all known nodes
# ================================
@app.get("/nodes")
def get_nodes():
    """
    📡 Retrieve all currently known nodes.

    Returns:
        dict: Node metadata including IP, port, and last seen.
    """
    return nodes

# ================================
# 🔍 Where is this chunk?
# ================================
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

# ================================
# 📦 Assign a chunk to a node
# ================================
@app.post("/chunk")
def assign_chunk(assignment: ChunkAssignment):
    """
    📦 Assign a chunk to a specified node.

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

@app.get("/keys")
def get_keys_info():
    return {"stored_keys": len(encryption_keys)}

@app.get("/manifest/{file_id}")
def get_manifest(file_id: str):
    """
    📜 Retrieve the manifest for a given file.

    Args:
        file_id (str): The ID of the file.

    Returns:
        dict: File manifest or 404 error.
    """
    manifest = file_manifests.get(file_id)
    if not manifest:
        return {"error": "file_id not found"}, 404
    return manifest

@app.post("/upload_file")
def upload_file(file: UploadFile = File(...)):
    """
    📤 Upload and distribute an encrypted file across registered nodes.

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
    encryption_keys[file_id] = file_key
    save_keys_to_disk()

    # 🔪 Slice the file into little byte-squares
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
                res = requests.post(node_url, files={
                    "chunk": (chunk_id, encrypted_chunk)
                }, data={
                    "chunk_id": chunk_id
                })

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

    if len(chunk_records) != len(chunk_paths):
        print("⚠️ Warning: Some chunks failed to store and were excluded from manifest.")

    # 📓 Save the manifest
    save_manifest(file_id, filename, chunk_records)

    # 🧹 Clean up temporary file + chunks
    os.remove(temp_file_path)
    for chunk_path in chunk_paths:
        os.remove(chunk_path)

    return {"file_id": file_id, "chunks_stored": len(chunk_records)}

# ============================
# 📦 Chunk Recovery Endpoint
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
    # 🧠 Get the manifest (it's the treasure map)
    manifest = file_manifests.get(file_id)
    if not manifest:
        return {"error": "File not found"}, 404

    # 🔑 Get the encryption key
    file_key = encryption_keys.get(file_id)
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


@app.get("/status")
def get_system_status():
    """
    📊 Return current system status including nodes, files, and chunks.

    Returns:
        dict: Overview of registered nodes, stored files, and chunk distribution.
    """
    return {
        "node_count": len(nodes),
        "registered_nodes": list(nodes.keys()),
        "file_count": len(file_manifests),
        "files": {
            file_id: {
                "original_filename": manifest["original_filename"],
                "chunk_count": len(manifest["chunks"])
            }
            for file_id, manifest in file_manifests.items()
        },
        "total_chunks": sum(len(m["chunks"]) for m in file_manifests.values())
    }

@app.post("/heal_now")
def heal_now():
    """
    🧪 Manual Healing Trigger
    Fire this to kick off one round of healing manually.
    """
    threading.Thread(target=heal_chunks, daemon=True).start()
    return {"status": "Healing started in background"}

def mark_node_dead(dead_node_id: str):
    """
    💀 Removes dead node from manifests and adds affected chunks to the healing queue.
    """
    print(f"⚰️ Node {dead_node_id} marked dead")
    for file_id, manifest in file_manifests.items():
        for chunk in manifest["chunks"]:
            if dead_node_id in chunk["node_ids"]:
                chunk["node_ids"].remove(dead_node_id)
                if len(chunk["node_ids"]) < CHUNK_REDUNDANCY:
                    if chunk["chunk_id"] not in healing_queue:
                        healing_queue.append(chunk["chunk_id"])
                        print(f"🚑 Queued {chunk['chunk_id']} for healing")


def heal_chunks():
    """
    🩹 New & Improved Healing Loop: only works on the queue of known injured chunks.
    """
    while True:
        if healing_queue:
            print(f"🧪 Healing Queue: {len(healing_queue)} chunks")
        else:
            time.sleep(5)
            continue

        chunk_id = healing_queue.pop(0)  # FIFO healing

        # 🧙 Scan all manifests for this chunk
        for file_id, manifest in file_manifests.items():
            for chunk in manifest["chunks"]:
                if chunk["chunk_id"] != chunk_id:
                    continue

                alive_nodes = chunk["node_ids"]
                needed = CHUNK_REDUNDANCY - len(alive_nodes)

                if needed <= 0:
                    break  # nothing to do

                available_nodes = [nid for nid in nodes if nid not in alive_nodes]
                random.shuffle(available_nodes)

                for new_node in available_nodes:
                    if needed == 0:
                        break
                    if not alive_nodes:
                        print(f"⚠️ No healthy replicas for {chunk_id}")
                        break

                    donor_node = random.choice(alive_nodes)
                    chunk_url = f"http://{nodes[donor_node]['ip']}:{nodes[donor_node]['port']}/chunk/{chunk_id}"
                    store_url = f"http://{nodes[new_node]['ip']}:{nodes[new_node]['port']}/store_chunk"

                    try:
                        res = requests.get(chunk_url)
                        if res.status_code == 200:
                            push = requests.post(store_url, files={"chunk": res.content}, data={"chunk_id": chunk_id})
                            if push.status_code == 200:
                                chunk["node_ids"].append(new_node)
                                alive_nodes.append(new_node)
                                needed -= 1
                                print(f"🧩 Healed {chunk_id} → {new_node}")
                        else:
                            print(f"⚠️ Chunk {chunk_id} fetch from {donor_node} failed")
                    except Exception as e:
                        print(f"🔥 Healing error: {e}")
                break


# 🧵 Launch background healing thread on startup
threading.Thread(target=heal_chunks, daemon=True).start()
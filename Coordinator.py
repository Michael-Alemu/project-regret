from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List
import time

import os
import uuid
import random
import requests
import shutil
from chunk_utils import split_file, reassemble_file  # Your lovely util

app = FastAPI()

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
    ❤️ Update the last seen timestamp of a node.

    Args:
        hb (Heartbeat): Heartbeat payload.

    Returns:
        dict: Heartbeat acknowledgment.
    """
    if hb.node_id in nodes:
        nodes[hb.node_id]["last_seen"] = time.time()
        return {"status": "alive"}
    raise HTTPException(status_code=404, detail="Node not found")

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
    print(f"📓 Manifest saved for {file_id} with {len(chunk_info)} chunks")

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
    📤 Upload and distribute a file across registered nodes.

    Args:
        file (UploadFile): File uploaded via POST.

    Returns:
        dict: Upload confirmation, file_id, and chunk count.
    """
    # 👶 Give this file a unique ID, because we're fancy
    file_id = f"file-{uuid.uuid4().hex[:6]}"
    filename = file.filename
    temp_file_path = f"temp_{file_id}_{filename}"

    # 💾 Save uploaded file locally
    with open(temp_file_path, "wb") as f:
        f.write(file.file.read())

    # 🔪 Slice the file into little byte-squares
    chunk_paths = split_file(temp_file_path, chunk_size_bytes=100 * 1024)  # 100KB chunks

    if not nodes:
        return {"error": "No nodes online"}, 503

    chunk_records = []

    for i, chunk_path in enumerate(chunk_paths):
        chunk_id = os.path.basename(chunk_path)

        # 🎯 Pick a random node to send the chunk to
        node_id = random.choice(list(nodes.keys()))
        node_info = nodes[node_id]
        node_url = f"http://{node_info['ip']}:{node_info['port']}/store_chunk"

        try:
            with open(chunk_path, "rb") as chunk_file:
                res = requests.post(node_url, files={
                    "chunk": chunk_file
                }, data={
                    "chunk_id": chunk_id
                })
            if res.status_code == 200:
                print(f"📦 Sent {chunk_id} to {node_id}")
                chunk_records.append({
                    "chunk_id": chunk_id,
                    "node_id": node_id
                })
            else:
                print(f"⚠️ Failed to store chunk {chunk_id} on {node_id}")
        except Exception as e:
            print(f"🔥 Error sending chunk {chunk_id} to {node_id}: {e}")

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
    📦 Download and reassemble a file using its manifest.

    Args:
        file_id (str): The ID of the file to download.

    Returns:
        FileResponse: The fully reassembled file.
    """
    # 🧠 Get the manifest (it's the treasure map)
    manifest = file_manifests.get(file_id)
    if not manifest:
        return {"error": "File not found"}, 404

    # 🗃️ Make a folder to store the returning chunk babies
    temp_dir = f"temp_chunks_{file_id}"
    os.makedirs(temp_dir, exist_ok=True)

    # 🔄 Loop through each chunk in the manifest
    for chunk in manifest["chunks"]:
        chunk_id = chunk["chunk_id"]
        node_id = chunk["node_id"]

        # 🛰️ Find the node where the chunk lives
        node = nodes.get(node_id)
        if not node:
            return {"error": f"Node {node_id} not available"}, 503

        # 🌐 Build the URL to fetch the chunk from the node
        url = f"http://{node['ip']}:{node['port']}/chunk/{chunk_id}"
        try:
            # 📡 GET the chunk like we're Netflix buffering
            res = requests.get(url)
            if res.status_code == 200:
                # 💾 Save it to our local chunk graveyard
                with open(os.path.join(temp_dir, chunk_id), "wb") as f:
                    f.write(res.content)
            else:
                return {"error": f"Failed to fetch chunk {chunk_id} from {node_id}"}, 502
        except Exception as e:
            return {"error": str(e)}, 500

    # 🧩 All chunks retrieved, time to stitch the beast
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

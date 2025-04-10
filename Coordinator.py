from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List
import time

import os
import uuid
import random
import requests
from fastapi import UploadFile, File
from chunk_utils import split_file  # Your lovely util

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
    node_id: str  # who dis
    storage_available: int  # how much space u got

class Heartbeat(BaseModel):
    node_id: str  # just sayin hi

class ChunkAssignment(BaseModel):
    chunk_id: str  # unique chunk name
    node_id: str   # node that stores this chunk

# ================================
# 🚪 Register a new node
# ================================
@app.post("/register")
def register_node(node: dict):
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
    if hb.node_id in nodes:
        nodes[hb.node_id]["last_seen"] = time.time()
        return {"status": "alive"}
    raise HTTPException(status_code=404, detail="Node not found")

# ================================
# 📡 List all known nodes
# ================================
@app.get("/nodes")
def get_nodes():
    return nodes

# ================================
# 🔍 Where is this chunk?
# ================================
@app.get("/chunk/{chunk_id}")
def get_chunk_locations(chunk_id: str):
    if chunk_id in chunk_map:
        return {"nodes": chunk_map[chunk_id]}
    raise HTTPException(status_code=404, detail="Chunk not found")

# ================================
# 📦 Assign a chunk to a node
# ================================
@app.post("/chunk")
def assign_chunk(assignment: ChunkAssignment):
    if assignment.chunk_id not in chunk_map:
        chunk_map[assignment.chunk_id] = []
    if assignment.node_id not in chunk_map[assignment.chunk_id]:
        chunk_map[assignment.chunk_id].append(assignment.node_id)
    return {"status": "chunk assigned"}

def save_manifest(file_id: str, original_filename: str, chunk_info: list):
    file_manifests[file_id] = {
        "original_filename": original_filename,
        "chunks": chunk_info
    }
    print(f"📓 Manifest saved for {file_id} with {len(chunk_info)} chunks")

@app.get("/manifest/{file_id}")
def get_manifest(file_id: str):
    manifest = file_manifests.get(file_id)
    if not manifest:
        return {"error": "file_id not found"}, 404
    return manifest


@app.post("/upload_file")
def upload_file(file: UploadFile = File(...)):
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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
import time

app = FastAPI()

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
def register_node(reg: NodeRegistration):
    nodes[reg.node_id] = {
        "storage": reg.storage_available,
        "last_seen": time.time()
    }
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

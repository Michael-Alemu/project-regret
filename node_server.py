# ============================
# 📦 Chunk Storage Server
# ============================
from flask import Flask, request, jsonify
import os
from node_config import NODE_ID, PORT, CHUNK_FOLDER

app = Flask(__name__)

os.makedirs(CHUNK_FOLDER, exist_ok=True)

@app.route("/store_chunk", methods=["POST"])
def store_chunk():
    if "chunk" not in request.files or "chunk_id" not in request.form:
        return jsonify({"error": "Missing chunk or chunk_id"}), 400

    chunk = request.files["chunk"]
    chunk_id = request.form["chunk_id"]

    chunk_path = os.path.join(CHUNK_FOLDER, chunk_id)
    chunk.save(chunk_path)

    print(f"[{NODE_ID}] 📦 Stored chunk: {chunk_id}")
    return jsonify({"status": "chunk stored", "node": NODE_ID, "chunk_id": chunk_id})

if __name__ == "__main__":
    app.run(port=PORT)
from flask import Flask, request, jsonify, send_file  # 👈 added send_file
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

# 👇 NEW endpoint for retrieving stored chunk
@app.route("/chunk/<chunk_id>", methods=["GET"])
def get_chunk(chunk_id):
    chunk_path = os.path.join(CHUNK_FOLDER, chunk_id)

    if not os.path.exists(chunk_path):
        return jsonify({"error": "Chunk not found"}), 404

    print(f"[{NODE_ID}] 📤 Served chunk: {chunk_id}")
    return send_file(chunk_path, as_attachment=True)



if __name__ == "__main__":
    app.run(port=PORT)
# =============================
# 🧪 Multi-Node Network Test
# =============================
import requests
import time
import random

COORDINATOR_URL = "http://localhost:8000"
NODE_PORTS = [5001, 5002, 5003]  # Simulate 3 nodes
NODE_IDS = [f"node-{port}" for port in NODE_PORTS]
TEST_FILE_PATH = "/Users/kingkong/DEV/p2p/TEST_Payment_Confirmation.pdf"  # Use a real file here

def register_all_nodes():
    for node_id, port in zip(NODE_IDS, NODE_PORTS):
        print(f"🚪 Registering {node_id}")
        res = requests.post(f"{COORDINATOR_URL}/register", json={
            "node_id": node_id,
            "storage_available": 1024 * 2,
            "ip": "localhost",
            "port": port
        })
        print(res.status_code, res.json())

def heartbeat_all():
    for node_id in NODE_IDS:
        print(f"❤️ Heartbeat from {node_id}")
        res = requests.post(f"{COORDINATOR_URL}/heartbeat", json={
            "node_id": node_id
        })
        print(res.status_code, res.json())

def upload_file():
    print("📤 Uploading file...")
    with open(TEST_FILE_PATH, "rb") as f:
        res = requests.post(f"{COORDINATOR_URL}/upload_file", files={
            "file": f
        })
    print(res.status_code, res.json())
    return res.json()["file_id"]


def download_file(file_id):
    print("📥 Downloading file...")
    res = requests.get(f"{COORDINATOR_URL}/download_file/{file_id}")
    output_file = f"downloaded_{file_id}.pdf"
    with open(output_file, "wb") as f:
        f.write(res.content)
    print(f"✅ File saved as: {output_file}")

def verify_manifest(file_id):
    print("📓 Manifest Check...")
    res = requests.get(f"{COORDINATOR_URL}/manifest/{file_id}")
    manifest = res.json()
    for chunk in manifest["chunks"]:
        print(f"🧩 {chunk['chunk_id']} stored on {chunk['node_ids']}")
    return manifest

def verify_status():
    print("📊 Network Status:")
    res = requests.get(f"{COORDINATOR_URL}/status")
    print(res.status_code, res.json())

if __name__ == "__main__":
    register_all_nodes()
    time.sleep(1)
    heartbeat_all()
    file_id = upload_file()
    time.sleep(1)
    verify_manifest(file_id)
    verify_status()
    download_file(file_id)

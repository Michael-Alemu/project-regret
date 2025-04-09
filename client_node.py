# ============================
# 🫀 Node Heartbeat Client
# ============================
import requests
import time
from node_config import NODE_ID, COORDINATOR_URL

STORAGE_AVAILABLE = 1024  # totally real amount of space

def register():
    print(f"[{NODE_ID}] Registering with coordinator...")
    try:
        res = requests.post(f"{COORDINATOR_URL}/register", json={
            "node_id": NODE_ID,
            "storage_available": STORAGE_AVAILABLE
        })
        print(f"[{NODE_ID}] ✅ Registration: {res.status_code} - {res.json()}")
    except Exception as e:
        print(f"[{NODE_ID}] ❌ Registration failed: {e}")

def heartbeat():
    while True:
        try:
            res = requests.post(f"{COORDINATOR_URL}/heartbeat", json={
                "node_id": NODE_ID
            })
            print(f"[{NODE_ID}] ❤️ Beat: {res.status_code}")
        except Exception as e:
            print(f"[{NODE_ID}] 💔 Heartbeat failed: {e}")
        time.sleep(5)

if __name__ == "__main__":
    register()
    heartbeat()
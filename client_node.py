# ============================
# 🫀 Node Heartbeat Client
# ============================
import requests
import time
from node_config import NODE_ID, COORDINATOR_URL, PORT, ADVERTISE_PORT

STORAGE_AVAILABLE = 1024  # totally real amount of space

def register():
    print(f"[{NODE_ID}] Registering with coordinator...")
    try:
        res = requests.post(f"{COORDINATOR_URL}/register", json={
            "node_id": NODE_ID,
            "storage_available": STORAGE_AVAILABLE,
            "ip": "127.0.0.1",  # make this dynamic later.
            "port": ADVERTISE_PORT  # 📣 advertise the doorway, not the room
        })
        print(f"[{NODE_ID}] ✅ Registration: {res.status_code} - {res.json()} PORT 🔌 {PORT} (advertised {ADVERTISE_PORT})")
    except Exception as e:
        print(f"[{NODE_ID}] ❌ Registration failed: {e}")

def heartbeat():
    while True:
        try:
            res = requests.post(f"{COORDINATOR_URL}/heartbeat", json={
                "node_id": NODE_ID
            })

            if res.status_code == 200:
                print(f"[{NODE_ID}] ❤️ Coordinator {res.status_code}.")
            elif res.status_code == 404:
                # 👻 Coordinator rebooted and forgot we exist. Rude. We used to just
                # scream heartbeats into the void forever — now we re-introduce ourselves.
                print(f"[{NODE_ID}] 👻 Coordinator called us a ghost. Re-registering...")
                register()
            else:
                print(f"[{NODE_ID}] 💔 Unexpected heartbeat response: {res.status_code} - {res.text}")

        except requests.exceptions.ConnectionError:
            print(f"[{NODE_ID}] ❌ Coordinator unreachable. Is it running at {COORDINATOR_URL}?")
        except Exception as e:
            print(f"[{NODE_ID}] 💥 Unknown heartbeat error: {type(e).__name__} - {e}")

        time.sleep(5)

if __name__ == "__main__":
    register()
    heartbeat()
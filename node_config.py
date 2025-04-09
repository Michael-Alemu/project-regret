# =====================
# 🧠 Node Configuration
# =====================
import uuid

# Your node's unique identity (stay weird)
NODE_ID = f"node-{uuid.uuid4().hex[:6]}"

# Port for the Flask server
PORT = 5001

# Folder to store chunk data (your local junk drawer)
CHUNK_FOLDER = "chunks"

# Coordinator address (where the boss lives)
COORDINATOR_URL = "http://localhost:8000"
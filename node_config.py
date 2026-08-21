# =====================
# 🧠 Node Configuration
# =====================
import os
import uuid

# Your node's unique identity (stay weird) — settable via env so you can
# actually run more than one of these without playing musical chairs with the code
NODE_ID = os.environ.get("NODE_ID", f"node-{uuid.uuid4().hex[:6]}")

# Port for the Flask server (NODE_PORT env var, or the classic 5001)
PORT = int(os.environ.get("NODE_PORT", "5001"))

# Folder to store chunk data (your local junk drawer).
# ⚠️ ABSOLUTE path on purpose: store_chunk writes relative to cwd, but Flask's
# send_file resolves relative paths against the app's root dir. With a relative
# folder, a node launched from anywhere else stores chunks it can never serve.
# Two hands, one brain. Absolute path makes them agree.
CHUNK_FOLDER = os.path.abspath(os.environ.get("CHUNK_FOLDER", "chunks"))

# Coordinator address (where the boss lives)
COORDINATOR_URL = os.environ.get("COORDINATOR_URL", "http://localhost:8000")

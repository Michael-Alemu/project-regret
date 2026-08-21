# ============================
# ⚙️ Global Configs
# ============================

from pathlib import Path

WORK_DIR = Path("work_dir")
WORK_DIR.mkdir(exist_ok=True)

# Subdirectories
MANIFEST_DIR = WORK_DIR / "manifests"
TEMP_CHUNK_DIR = WORK_DIR / "temp_chunks"
TEMP_UPLOAD_DIR = WORK_DIR / "temp_uploads"

# 🔑 Where the manifest master key sleeps between coordinator lifetimes.
# Lose this file, lose every manifest. Guard it like the last cheeseburger on Earth.
MASTER_KEY_PATH = WORK_DIR / "manifest_master.key"

# 🧩 Chunk size in bytes
CHUNK_SIZE_BYTES = 100 * 1024  # 100KB

# Ensure all dirs exist
for path in [MANIFEST_DIR, TEMP_CHUNK_DIR, TEMP_UPLOAD_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# 📜 Future: default policy, encryption flag, manifest path, dynamic CHUNK_SIZE_BYTES etc.

# ==========================================================
# 📜 manifest_utils.py (The TikTok Brain Director's Cut)
# The sacred scroll keeper for the Republic of Chunks.
# This isn't just a class, it's the network's memory. Handle with care.
# ==========================================================
import os
import json
import threading
import base64
from pathlib import Path
from typing import List, Dict

# Yoink the magic spells from our friendly neighborhood wizard.
from crypto_utils import encrypt_bytes, decrypt_bytes, _normalize_key


class ManifestChunkManager:
    """
    📚 The Manifest Librarian.

    Takes big, scary manifest files, whispers sweet nothings to them,
    encrypts them, and chops them into tiny, bite-sized chunklets.
    It's basically a data therapist with a butcher's knife.
    """

    def __init__(self, manifest_dir: Path, chunk_size: int, encryption_key: str | bytes):
        """
        🏗️ Wakes up the librarian and gives them coffee.

        Args:
            manifest_dir (Path): Where the librarian hides the secret scrolls.
            chunk_size (int): How big each page of the scroll is (in bytes).
            encryption_key (bytes): The master key to the whole library. Lose this, lose everything.
        """
        self.manifest_dir = manifest_dir
        self.chunk_size = chunk_size
        # The key to the kingdom, kept as bytes 'cause Fernet is picky.
        self.encryption_key = _normalize_key(encryption_key)
        # One lock to rule them all, so we don't trip over our own feet.
        self._lock = threading.Lock()

        # If the library doesn't exist, we build it. From dust.
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def _get_chunk_path(self, file_id: str, chunk_index: int) -> Path:
        """ 🗺️ Figures out where a specific page of a scroll should live. It's just path math, fam. """
        return self.manifest_dir / f"{file_id}_manifest_chunk_{chunk_index:04d}.bin"

    def save_manifest(self, file_id: str, manifest_data: dict):
        """
        💾 Inscribes a new story into the archives. Takes a manifest, encrypts it,
        and shatters it into a thousand tiny, secure pieces. A true work of art.
        """
        # First, we turn the manifest into a long, rambling string of JSON.
        serialized = json.dumps(manifest_data).encode("utf-8")
        # Then, ✨ chunk magic ✨.
        chunks = [serialized[i:i + self.chunk_size] for i in range(0, len(serialized), self.chunk_size)]

        with self._lock:  # Don't let anyone interrupt this sacred ritual.
            for idx, chunk_data in enumerate(chunks):
                # Encrypt every single piece. No witnesses.
                encrypted_chunk = encrypt_bytes(chunk_data, self.encryption_key)
                with open(self._get_chunk_path(file_id, idx), "wb") as f:
                    f.write(encrypted_chunk)  # Bury the evidence.

        print(f"📦 Saved manifest {file_id} in {len(chunks)} encrypted chunklets. The lore is safe.")

    def load_manifest(self, file_id: str) -> Dict:
        """
        📖 Summons an ancient scroll from the depths. Finds all the encrypted pieces,
        decrypts them with a magic word, and stitches them back together.
        """
        manifest_data_bytes = b""
        idx = 0
        while True:  # We go hunting for pieces until we can't find any more.
            chunk_path = self._get_chunk_path(file_id, idx)
            if not chunk_path.exists():
                break  # End of the scroll.

            with open(chunk_path, "rb") as f:
                encrypted_chunk = f.read()
                # Whisper the secret key to decrypt the page.
                decrypted_chunk = decrypt_bytes(encrypted_chunk, self.encryption_key)
                manifest_data_bytes += decrypted_chunk
            idx += 1

        if not manifest_data_bytes:
            # We found nothing. The scroll is a lie. Panic.
            raise FileNotFoundError(f"Manifest {file_id} not found! It's a ghost!")

        # We reassembled the scroll. Now, we read it.
        manifest = json.loads(manifest_data_bytes.decode("utf-8"))
        return manifest

    def update_manifest(self, file_id: str, updated_manifest: dict):
        """
        🛠️ Rewrites history. Burns the old scroll and writes a new one.
        There is no 'edit', only 'replace'. Brutal.
        """
        self.save_manifest(file_id, updated_manifest)
        print(f"🔄 The history of {file_id} has been... revised.")

    def delete_manifest(self, file_id: str):
        """
        🧹 Erases a story from existence. Turns a manifest into digital dust.
        Use with caution. Or don't. I'm a comment, not a cop.
        """
        with self._lock:
            idx = 0
            deleted_count = 0
            while True:
                chunk_path = self._get_chunk_path(file_id, idx)
                if not chunk_path.exists():
                    break

                os.remove(chunk_path)  # Begone.
                deleted_count += 1
                idx += 1

            if deleted_count > 0:
                print(f"🗑️ The manifest for {file_id} is no more. It has ceased to be.")

    def list_manifests(self) -> List[str]:
        """
        📜 Asks the librarian for a list of all the books in the library.
        Doesn't tell you what's in them, just their names. For privacy. Obviously.
        """
        manifests = set()
        # Look for any file that looks like a manifest chunk.
        for file in self.manifest_dir.glob("*_manifest_chunk_*.bin"):
            # Do some ungodly string splitting to get the original file_id. It's ugly but it works.
            file_id = "_".join(file.stem.split("_")[:-3])
            manifests.add(file_id)

        return sorted(list(manifests))
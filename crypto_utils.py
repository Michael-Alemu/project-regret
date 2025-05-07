# ============================
# 🛡️ crypto_utils.py
# ============================
import json
import os
from cryptography.fernet import Fernet

# In-memory key store (file_id -> encryption key)
encryption_keys = {}

def generate_key() -> bytes:
    """
    🎲 Generate a new random encryption key.

    Returns:
        bytes: A new Fernet key.
    """
    return Fernet.generate_key()

def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """
    🔒 Encrypt raw bytes using a given key.

    Args:
        data (bytes): The data to encrypt.
        key (bytes): Encryption key.

    Returns:
        bytes: Encrypted data.
    """
    f = Fernet(key)
    return f.encrypt(data)

def decrypt_bytes(data: bytes, key: bytes) -> bytes:
    """
    🔓 Decrypt raw bytes using a given key.

    Args:
        data (bytes): Encrypted data.
        key (bytes): Encryption key.

    Returns:
        bytes: Decrypted original data.
    """
    f = Fernet(key)
    return f.decrypt(data)

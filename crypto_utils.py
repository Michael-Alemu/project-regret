# ============================================
# 🔐 Crypto Utilities (Crypteia Mode - FINAL)
# ============================================
# 🕰️ Time-travel insurance: lets the fancy `str | bytes` type hints run on
# Python 3.9, which is what some of our machines are still rocking.
from __future__ import annotations
from cryptography.fernet import Fernet
import base64

def generate_key() -> str:
    """
    🎲 Generates a new, Fernet-compliant, 32-byte, base64-encoded
    encryption key AND returns it as a string safe for JSON storage.
    """
    return Fernet.generate_key().decode("utf-8")

def _normalize_key(key: str | bytes) -> bytes:

    """
    🔑 Normalize Fernet keys: accept raw bytes or base64 strings.
    """
    if isinstance(key, str):
        try:
            key_bytes = key.encode("utf-8")
            # Validate it's already a proper base64-encoded key
            Fernet(key_bytes)
            return key_bytes
        except Exception:
            # If that fails, maybe it's *not* base64 yet—try decoding
            try:
                decoded = base64.urlsafe_b64decode(key_bytes)
                Fernet(decoded)  # Validate
                return decoded
            except Exception as e:
                raise ValueError(f"Invalid Fernet key (base64 decode failed): {e}")
    elif isinstance(key, bytes):
        try:
            Fernet(key)
            return key
        except Exception as e:
            raise ValueError(f"Invalid Fernet key (bytes): {e}")
    else:
        raise TypeError(f"Key must be str or bytes, got {type(key).__name__}")

def encrypt_bytes(data: bytes, key: str | bytes) -> bytes:
    """
    🔒 Encrypts raw bytes using a given key.
    Normalizes the key before use.
    """
    normalized_key = _normalize_key(key)
    f = Fernet(normalized_key)
    return f.encrypt(data)

def decrypt_bytes(data: bytes, key: str | bytes) -> bytes:
    """
    🔓 Decrypts raw bytes using a given key.
    Normalizes the key before use.
    """
    normalized_key = _normalize_key(key)
    f = Fernet(normalized_key)
    return f.decrypt(data)
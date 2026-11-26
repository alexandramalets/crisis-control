"""AES-256-GCM для исходных файлов наборов данных (ЛЗ п. 3.4.1, S-07)."""

import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_SIZE = 12
KEY_SIZE = 32


def file_encryption_key(secret: str) -> bytes:
    """32 байта ключа: если секрет уже 32 байта — как есть, иначе SHA-256."""
    raw = secret.encode("utf-8")
    return raw if len(raw) == KEY_SIZE else hashlib.sha256(raw).digest()


def encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(NONCE_SIZE)
    return AESGCM(key).encrypt(nonce, plaintext, None), nonce


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return AESGCM(key).decrypt(nonce, ciphertext, None)

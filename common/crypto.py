"""
Envelope encryption helpers (protocol sec. 9, Layer 1: AES-256 encryption).

Each book file gets its own random Fernet key (the "DEK" - data encryption
key). The DEK is itself encrypted ("wrapped") with a single master key
before being stored on BookAsset.wrapped_key, so a database leak alone
never exposes usable decryption keys.

MASTER_KEY belongs in a secrets manager in production (AWS KMS / Secrets
Manager, Vault, etc.) - here it's derived from Django's SECRET_KEY only
because there's no secrets manager wired up yet in this scaffold.
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _master_fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def generate_dek() -> bytes:
    """A fresh, random per-book encryption key."""
    return Fernet.generate_key()


def wrap_key(dek: bytes) -> str:
    """Encrypt a DEK with the master key, for storage in wrapped_key."""
    return _master_fernet().encrypt(dek).decode()


def unwrap_key(wrapped_key: str) -> bytes:
    return _master_fernet().decrypt(wrapped_key.encode())


def encrypt_bytes(data: bytes, dek: bytes) -> bytes:
    return Fernet(dek).encrypt(data)


def decrypt_bytes(token: bytes, dek: bytes) -> bytes:
    return Fernet(dek).decrypt(token)

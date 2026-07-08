from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    from app.config import SECRET_KEY

    secret = SECRET_KEY or "opsdev-secret-key-change-in-production"
    key = _derive_key(secret)
    _fernet = Fernet(key)
    return _fernet


def encrypt_value(value: str) -> str:
    if value is None:
        return ""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_value(token: str) -> str:
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""

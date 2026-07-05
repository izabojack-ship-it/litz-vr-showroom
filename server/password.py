"""管理後台密碼雜湊（PBKDF2，僅 stdlib）。"""
from __future__ import annotations

import base64
import hashlib
import secrets

PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return base64.b64encode(salt + digest).decode("ascii")


def verify_password(password: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False
    if len(raw) < 17:
        return False
    salt, digest = raw[:16], raw[16:]
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return secrets.compare_digest(digest, check)

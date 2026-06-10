"""Admin authentication module."""
import os
import hashlib
import secrets
from datetime import datetime

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

_admin_sessions = {}  # token -> username


def make_token(username: str) -> str:
    raw = f"{username}:{datetime.utcnow().timestamp()}:{secrets.token_hex(8)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def authenticate(username: str, password: str) -> str | None:
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = make_token(username)
        _admin_sessions[token] = username
        return token
    return None


def validate_token(token: str) -> bool:
    return token in _admin_sessions

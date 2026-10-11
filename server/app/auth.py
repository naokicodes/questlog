"""Per-device login tokens. Only the SHA-256 hash is stored."""

import hashlib
import secrets
import sqlite3

from .days import iso, now

COOKIE = "questlog_token"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_device(conn: sqlite3.Connection, name: str, kind: str) -> str:
    if kind not in ("laptop", "phone"):
        raise ValueError("kind must be 'laptop' or 'phone'")
    token = new_token()
    conn.execute(
        "INSERT INTO devices (name, kind, token_hash, created_at) VALUES (?, ?, ?, ?)",
        (name, kind, hash_token(token), iso(now())),
    )
    conn.commit()
    return token


def device_for_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM devices WHERE token_hash = ?", (hash_token(token),)
    ).fetchone()

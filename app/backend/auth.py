#!/usr/bin/env python3
"""
PPT Master SaaS - Authentication

PBKDF2-HMAC-SHA256 password hashing (stdlib hashlib) with per-user salt,
bearer-token sessions in the sessions table. FastAPI dependencies for
current-user / admin-only routes.

See docs/saas/ARCHITECTURE.md §4.

Dependencies:
    fastapi
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request

from .db import Database, utcnow

_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str, salt: str) -> str:
    """Derive a hex password hash via PBKDF2-HMAC-SHA256."""
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return digest.hex()


def new_salt() -> str:
    return secrets.token_hex(16)


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), expected_hash)


def create_session(db: Database, user_id: int, ttl_hours: int) -> str:
    """Create a session row and return its bearer token."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ttl_hours)
    db.execute(
        "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now.strftime("%Y-%m-%dT%H:%M:%SZ"),
         expires.strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    return token


def delete_session(db: Database, token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_db(request: Request) -> Database:
    return request.app.state.db


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return ""


def current_user(request: Request, db: Database = Depends(get_db)) -> dict:
    """FastAPI dependency: resolve the bearer token to a user row."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    session = db.query_one("SELECT * FROM sessions WHERE token = ?", (token,))
    if not session:
        raise HTTPException(status_code=401, detail="invalid session")
    if session["expires_at"] < utcnow():
        delete_session(db, token)
        raise HTTPException(status_code=401, detail="session expired")
    user = db.query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    if not user or user["disabled"]:
        raise HTTPException(status_code=401, detail="user disabled or missing")
    user["_token"] = token
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    """FastAPI dependency: require the admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user


def public_user(user: dict) -> dict:
    """Strip private fields before serializing a user row."""
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "token_quota": user["token_quota"],
        "token_used": user["token_used"],
        "disabled": user["disabled"],
        "created_at": user["created_at"],
    }


def find_user_by_name(db: Database, username: str) -> Optional[dict]:
    return db.query_one("SELECT * FROM users WHERE username = ?", (username,))

#!/usr/bin/env python3
"""
PPT Master SaaS - SQLite thin wrapper

Stdlib sqlite3 only (no ORM). Schema follows docs/saas/ARCHITECTURE.md §4.

Dependencies:
    None (only uses standard library)
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    salt TEXT,
    role TEXT DEFAULT 'user',
    token_quota INTEGER DEFAULT 2000000,
    token_used INTEGER DEFAULT 0,
    disabled INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions(
    token TEXT PRIMARY KEY,
    user_id INTEGER,
    created_at TEXT,
    expires_at TEXT
);
CREATE TABLE IF NOT EXISTS projects(
    id TEXT PRIMARY KEY,
    user_id INTEGER,
    title TEXT,
    status TEXT,
    theme_id INTEGER,
    slide_count INTEGER,
    style_brief TEXT,
    outline_json TEXT,
    error TEXT,
    pptx_path TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS pages(
    project_id TEXT,
    page_number INTEGER,
    status TEXT,
    error TEXT,
    PRIMARY KEY(project_id, page_number)
);
CREATE TABLE IF NOT EXISTS token_usage(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    project_id TEXT,
    stage TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS themes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    builtin INTEGER DEFAULT 0,
    owner_id INTEGER,
    style_md TEXT,
    description TEXT,
    palette TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS settings(
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


# Columns added after the v1 schema; applied idempotently to existing DBs.
_MIGRATIONS = (
    ("themes", "description", "TEXT"),
    ("themes", "palette", "TEXT"),
)


def utcnow() -> str:
    """Current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    """Single-connection sqlite3 wrapper guarded by a lock.

    The backend is asyncio-based with low write volume; a serialized
    connection keeps the code simple and correct under check_same_thread.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            for table, column, col_type in _MIGRATIONS:
                cols = {r[1] for r in self._conn.execute(
                    f"PRAGMA table_info({table})")}
                if column not in cols:
                    self._conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

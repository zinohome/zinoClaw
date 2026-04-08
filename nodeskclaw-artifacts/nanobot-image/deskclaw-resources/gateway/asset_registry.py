"""Unified asset registry — SQLite index for materials and outputs."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from loguru import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    source      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    filename    TEXT NOT NULL,
    path        TEXT,
    url         TEXT,
    hash        TEXT,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_source ON assets(session_id, source);
CREATE INDEX IF NOT EXISTS idx_hash ON assets(hash);
"""

_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"})
_VIDEO_EXTS = frozenset({".mp4", ".webm", ".mov", ".avi", ".mkv"})


def guess_kind(name_or_url: str) -> str:
    suffix = Path(name_or_url.split("?")[0]).suffix.lower()
    if suffix in _IMAGE_EXTS:
        return "image"
    if suffix in _VIDEO_EXTS:
        return "video"
    return "file"


def extract_filename(name_or_url: str) -> str:
    clean = name_or_url.split("?")[0].split("#")[0]
    name = Path(clean).name
    return name if name else name_or_url[:80]


class AssetRegistry:
    """Thread-safe SQLite registry. All public methods are synchronous;
    call via ``run_in_executor`` from async code."""

    def __init__(self, workspace: str | Path) -> None:
        db_dir = Path(workspace).resolve() / "media"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / ".assets.db"
        self._conn = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
            isolation_level="DEFERRED",
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=3000")
        self._conn.executescript(_SCHEMA)
        self._conn.row_factory = sqlite3.Row
        logger.info("AssetRegistry opened: {}", db_path)

    def register(
        self,
        session_id: str,
        source: str,
        kind: str,
        filename: str,
        *,
        path: str | None = None,
        url: str | None = None,
        content_hash: str | None = None,
    ) -> str:
        if content_hash:
            existing = self.exists_hash(session_id, content_hash)
            if existing:
                return existing["id"]

        if url and not content_hash:
            row = self._conn.execute(
                "SELECT id FROM assets WHERE session_id=? AND url=?",
                (session_id, url),
            ).fetchone()
            if row:
                return row["id"]

        asset_id = uuid4().hex[:16]
        self._conn.execute(
            "INSERT INTO assets (id, session_id, source, kind, filename, path, url, hash, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (asset_id, session_id, source, kind, filename, path, url, content_hash, time.time()),
        )
        self._conn.commit()
        return asset_id

    def query(
        self,
        session_id: str | None = None,
        source: str | None = None,
        kind: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[str | int] = []
        if session_id is not None:
            clauses.append("session_id=?")
            params.append(session_id)
        if source is not None:
            clauses.append("source=?")
            params.append(source)
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM assets{where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def exists_hash(self, session_id: str, hash: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM assets WHERE session_id=? AND hash=?",
            (session_id, hash),
        ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self._conn.close()

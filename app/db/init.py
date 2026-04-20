"""SQLite access helpers. init_db() creates schema; get_conn() returns a row-dict conn."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from app.config import settings


SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _db_path() -> Path:
    p = Path(settings.db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_conn() -> sqlite3.Connection:
    """Returns a sqlite3 Connection with row_factory=Row and FK/WAL enabled."""
    conn = sqlite3.connect(_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Context manager: commit on success, rollback on exception."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Apply schema.sql. Idempotent."""
    sql = SCHEMA_PATH.read_text()
    with tx() as conn:
        conn.executescript(sql)


def log_fetch(target: str, status: str, message: str = "", items: int = 0) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with tx() as conn:
        conn.execute(
            "INSERT INTO fetch_log(target, status, message, items, ts) VALUES (?,?,?,?,?)",
            (target, status, message, items, ts),
        )


def prune_old(hours: int | None = None) -> int:
    """Delete articles older than `hours` and old fetch_log rows (>14d)."""
    hours = hours or settings.article_retention_hours
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    log_cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    with tx() as conn:
        cur = conn.execute("DELETE FROM articles WHERE fetched_at < ?", (cutoff,))
        deleted = cur.rowcount
        conn.execute("DELETE FROM fetch_log WHERE ts < ?", (log_cutoff,))
    return deleted


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {_db_path()}")

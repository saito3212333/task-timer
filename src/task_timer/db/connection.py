from __future__ import annotations

import sqlite3
from pathlib import Path

from task_timer.db.schema import DDL_STATEMENTS, SCHEMA_VERSION


def project_root() -> Path:
    """Walk up from this file to the task_timer project root."""
    return Path(__file__).resolve().parents[3]


def default_db_path() -> Path:
    return project_root() / "data" / "task_timer.db"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults and ensure schema exists."""
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    _apply_schema(conn)
    return conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    with conn:
        for stmt in DDL_STATEMENTS:
            conn.execute(stmt)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
            ("version", str(SCHEMA_VERSION)),
        )

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
        _migrate_existing(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
            ("version", str(SCHEMA_VERSION)),
        )


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_existing(conn: sqlite3.Connection) -> None:
    """既存DBに新カラムがなければ ALTER で追加する（v1→v2）。"""
    if "is_routine" not in _column_names(conn, "phases"):
        conn.execute(
            "ALTER TABLE phases ADD COLUMN is_routine INTEGER NOT NULL DEFAULT 0"
        )
    if "recurrence" not in _column_names(conn, "tasks"):
        # CHECK制約はALTERでは付けられないが、INSERT/UPDATEは値を絞っているのでOK。
        conn.execute("ALTER TABLE tasks ADD COLUMN recurrence TEXT")

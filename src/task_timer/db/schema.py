"""SQLite DDL for task-timer.

All timestamps stored as ISO-8601 strings (TEXT). Dates as YYYY-MM-DD.
"""

SCHEMA_VERSION = 3

DDL_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS projects (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT    NOT NULL,
        status          TEXT    NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active','done','archived')),
        deadline        TEXT,
        planned_hours   REAL,
        planned_money   INTEGER,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS phases (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        name            TEXT    NOT NULL,
        status          TEXT    NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active','done','archived')),
        order_index     INTEGER NOT NULL DEFAULT 0,
        deadline        TEXT    NOT NULL,
        planned_hours   REAL,
        is_routine      INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        phase_id        INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
        name            TEXT    NOT NULL,
        description     TEXT,
        status          TEXT    NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active','done','archived')),
        order_index     INTEGER NOT NULL DEFAULT 0,
        priority        TEXT    NOT NULL DEFAULT 'normal'
                                CHECK (priority IN ('high','normal','low')),
        deadline        TEXT,
        planned_hours   REAL,
        recurrence      TEXT
                                CHECK (recurrence IS NULL OR recurrence IN ('daily','weekly')),
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS time_logs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id         INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        started_at      TEXT    NOT NULL,
        ended_at        TEXT    NOT NULL,
        duration_sec    INTEGER NOT NULL,
        note            TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_phases_project ON phases(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_phase ON tasks(phase_id)",
    "CREATE INDEX IF NOT EXISTS idx_time_logs_task ON time_logs(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_time_logs_started ON time_logs(started_at)",
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key     TEXT PRIMARY KEY,
        value   TEXT NOT NULL
    )
    """,
]

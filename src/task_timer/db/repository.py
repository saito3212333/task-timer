from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

from task_timer.models import (
    Phase,
    PhaseWithTasks,
    Project,
    ProjectTree,
    Task,
    TimeLog,
)


def _to_date(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


def _to_dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def _date_str(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _dt_str(d: datetime | None) -> str | None:
    return d.isoformat(timespec="seconds") if d else None


def _row_project(r: sqlite3.Row) -> Project:
    return Project(
        id=r["id"],
        name=r["name"],
        status=r["status"],
        deadline=_to_date(r["deadline"]),
        planned_hours=r["planned_hours"],
        planned_money=r["planned_money"],
        created_at=_to_dt(r["created_at"]),
        updated_at=_to_dt(r["updated_at"]),
    )


def _row_phase(r: sqlite3.Row) -> Phase:
    return Phase(
        id=r["id"],
        project_id=r["project_id"],
        name=r["name"],
        status=r["status"],
        order_index=r["order_index"],
        deadline=_to_date(r["deadline"]),  # phase deadline is required
        planned_hours=r["planned_hours"],
        created_at=_to_dt(r["created_at"]),
        updated_at=_to_dt(r["updated_at"]),
    )


def _row_task(r: sqlite3.Row) -> Task:
    return Task(
        id=r["id"],
        phase_id=r["phase_id"],
        name=r["name"],
        status=r["status"],
        order_index=r["order_index"],
        priority=r["priority"],
        deadline=_to_date(r["deadline"]),
        planned_hours=r["planned_hours"],
        created_at=_to_dt(r["created_at"]),
        updated_at=_to_dt(r["updated_at"]),
    )


def _row_time_log(r: sqlite3.Row) -> TimeLog:
    return TimeLog(
        id=r["id"],
        task_id=r["task_id"],
        started_at=_to_dt(r["started_at"]),  # required
        ended_at=_to_dt(r["ended_at"]),
        duration_sec=r["duration_sec"],
        note=r["note"],
        created_at=_to_dt(r["created_at"]),
    )


class Database:
    """Thin CRUD layer over the SQLite connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    # transaction helper
    # ------------------------------------------------------------------
    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.conn:
            yield self.conn

    # ------------------------------------------------------------------
    # projects
    # ------------------------------------------------------------------
    def create_project(self, project: Project) -> Project:
        with self.tx() as c:
            cur = c.execute(
                """
                INSERT INTO projects(name, status, deadline, planned_hours, planned_money)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project.name,
                    project.status,
                    _date_str(project.deadline),
                    project.planned_hours,
                    project.planned_money,
                ),
            )
        return self.get_project(cur.lastrowid)  # type: ignore[arg-type]

    def get_project(self, project_id: int) -> Project:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"project {project_id} not found")
        return _row_project(row)

    def list_projects(self, include_archived: bool = False) -> list[Project]:
        if include_archived:
            rows = self.conn.execute(
                "SELECT * FROM projects ORDER BY id"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM projects WHERE status != 'archived' ORDER BY id"
            ).fetchall()
        return [_row_project(r) for r in rows]

    def update_project(self, project_id: int, **fields: Any) -> Project:
        return self._patch("projects", project_id, fields, _row_project)

    def delete_project(self, project_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # ------------------------------------------------------------------
    # phases
    # ------------------------------------------------------------------
    def create_phase(self, phase: Phase) -> Phase:
        with self.tx() as c:
            cur = c.execute(
                """
                INSERT INTO phases(project_id, name, status, order_index, deadline, planned_hours)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    phase.project_id,
                    phase.name,
                    phase.status,
                    phase.order_index,
                    _date_str(phase.deadline),
                    phase.planned_hours,
                ),
            )
        return self.get_phase(cur.lastrowid)  # type: ignore[arg-type]

    def get_phase(self, phase_id: int) -> Phase:
        row = self.conn.execute(
            "SELECT * FROM phases WHERE id = ?", (phase_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"phase {phase_id} not found")
        return _row_phase(row)

    def list_phases(self, project_id: int) -> list[Phase]:
        rows = self.conn.execute(
            "SELECT * FROM phases WHERE project_id = ? ORDER BY order_index, id",
            (project_id,),
        ).fetchall()
        return [_row_phase(r) for r in rows]

    def update_phase(self, phase_id: int, **fields: Any) -> Phase:
        return self._patch("phases", phase_id, fields, _row_phase)

    def delete_phase(self, phase_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM phases WHERE id = ?", (phase_id,))

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------
    def create_task(self, task: Task) -> Task:
        with self.tx() as c:
            cur = c.execute(
                """
                INSERT INTO tasks(phase_id, name, status, order_index, priority, deadline, planned_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.phase_id,
                    task.name,
                    task.status,
                    task.order_index,
                    task.priority,
                    _date_str(task.deadline),
                    task.planned_hours,
                ),
            )
        return self.get_task(cur.lastrowid)  # type: ignore[arg-type]

    def get_task(self, task_id: int) -> Task:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"task {task_id} not found")
        return _row_task(row)

    def list_tasks(self, phase_id: int) -> list[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE phase_id = ? ORDER BY order_index, id",
            (phase_id,),
        ).fetchall()
        return [_row_task(r) for r in rows]

    def update_task(self, task_id: int, **fields: Any) -> Task:
        return self._patch("tasks", task_id, fields, _row_task)

    def delete_task(self, task_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    # ------------------------------------------------------------------
    # time logs
    # ------------------------------------------------------------------
    def create_time_log(self, log: TimeLog) -> TimeLog:
        with self.tx() as c:
            cur = c.execute(
                """
                INSERT INTO time_logs(task_id, started_at, ended_at, duration_sec, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    log.task_id,
                    _dt_str(log.started_at),
                    _dt_str(log.ended_at),
                    log.duration_sec,
                    log.note,
                ),
            )
        row = self.conn.execute(
            "SELECT * FROM time_logs WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return _row_time_log(row)

    def list_time_logs_for_task(self, task_id: int) -> list[TimeLog]:
        rows = self.conn.execute(
            "SELECT * FROM time_logs WHERE task_id = ? ORDER BY started_at",
            (task_id,),
        ).fetchall()
        return [_row_time_log(r) for r in rows]

    def total_seconds_for_phase(self, phase_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(tl.duration_sec), 0) AS s
            FROM time_logs tl
            JOIN tasks t ON tl.task_id = t.id
            WHERE t.phase_id = ?
            """,
            (phase_id,),
        ).fetchone()
        return int(row["s"] or 0)

    def total_seconds_for_project(self, project_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(tl.duration_sec), 0) AS s
            FROM time_logs tl
            JOIN tasks t  ON tl.task_id = t.id
            JOIN phases p ON t.phase_id = p.id
            WHERE p.project_id = ?
            """,
            (project_id,),
        ).fetchone()
        return int(row["s"] or 0)

    # ------------------------------------------------------------------
    # tree view (for management UI)
    # ------------------------------------------------------------------
    def load_project_tree(self, project_id: int) -> ProjectTree:
        proj = self.get_project(project_id)
        phases = self.list_phases(project_id)
        return ProjectTree(
            project=proj,
            phases=[
                PhaseWithTasks(phase=p, tasks=self.list_tasks(p.id))  # type: ignore[arg-type]
                for p in phases
            ],
        )

    def load_all_trees(self, include_archived: bool = False) -> list[ProjectTree]:
        return [
            self.load_project_tree(p.id)  # type: ignore[arg-type]
            for p in self.list_projects(include_archived=include_archived)
        ]

    # ------------------------------------------------------------------
    # generic patch helper
    # ------------------------------------------------------------------
    def _patch(self, table: str, row_id: int, fields: dict[str, Any], row_fn):
        if not fields:
            raise ValueError("update called with no fields")

        normalized: dict[str, Any] = {}
        for k, v in fields.items():
            if isinstance(v, date) and not isinstance(v, datetime):
                normalized[k] = _date_str(v)
            elif isinstance(v, datetime):
                normalized[k] = _dt_str(v)
            else:
                normalized[k] = v

        cols = ", ".join(f"{k} = ?" for k in normalized.keys())
        params = (*normalized.values(), row_id)
        sql = f"UPDATE {table} SET {cols}, updated_at = datetime('now') WHERE id = ?"
        with self.tx() as c:
            cur = c.execute(sql, params)
            if cur.rowcount == 0:
                raise KeyError(f"{table} {row_id} not found")
        row = self.conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)
        ).fetchone()
        return row_fn(row)

"""DB行 → モデル変換と日付/datetime のシリアライズヘルパー。"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from task_timer.models import Phase, Project, Task, TimeLog


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
        is_routine=bool(r["is_routine"]),
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
        recurrence=r["recurrence"],
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

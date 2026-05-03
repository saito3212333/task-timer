from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

Status = Literal["active", "done", "archived"]
Priority = Literal["high", "normal", "low"]


@dataclass(slots=True)
class Project:
    name: str
    id: int | None = None
    status: Status = "active"
    deadline: date | None = None
    planned_hours: float | None = None
    planned_money: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Phase:
    project_id: int
    name: str
    deadline: date
    id: int | None = None
    status: Status = "active"
    order_index: int = 0
    planned_hours: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Task:
    phase_id: int
    name: str
    id: int | None = None
    status: Status = "active"
    order_index: int = 0
    priority: Priority = "normal"
    deadline: date | None = None
    planned_hours: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class TimeLog:
    task_id: int
    started_at: datetime
    ended_at: datetime
    duration_sec: int
    id: int | None = None
    note: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class ProjectTree:
    """Project + nested phases + tasks. Used for the management view."""

    project: Project
    phases: list[PhaseWithTasks] = field(default_factory=list)


@dataclass(slots=True)
class PhaseWithTasks:
    phase: Phase
    tasks: list[Task] = field(default_factory=list)

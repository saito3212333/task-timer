"""SQLite を介した CRUD ファサード。実装は repositories/ 配下の mixin に分割。"""
from __future__ import annotations

import sqlite3

from task_timer.db.repositories import (
    AggregatesMixin,
    BaseMixin,
    PhasesMixin,
    ProjectsMixin,
    SystemEntitiesMixin,
    TasksMixin,
    TimeLogsMixin,
    TreeMixin,
)


class Database(
    SystemEntitiesMixin,
    TreeMixin,
    AggregatesMixin,
    TimeLogsMixin,
    TasksMixin,
    PhasesMixin,
    ProjectsMixin,
    BaseMixin,
):
    """Thin CRUD layer over the SQLite connection.

    機能ごとの mixin で実装を分割している（base / projects / phases / tasks /
    time_logs / aggregates / tree / system）。公開APIは旧 Database と同一。
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        # システム必須エンティティのIDキャッシュ（init_default_setup で埋まる）
        self.system_ids: dict[str, int] = {}

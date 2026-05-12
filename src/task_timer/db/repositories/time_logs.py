"""time_logs テーブルの CRUD とメモ件数取得。"""
from __future__ import annotations

from typing import Any

from task_timer.db._converters import _dt_str, _row_time_log
from task_timer.models import TimeLog


class TimeLogsMixin:
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

    def update_time_log(self, log_id: int, **fields: Any) -> TimeLog:
        if not fields:
            raise ValueError("update_time_log called with no fields")
        cols = ", ".join(f"{k} = ?" for k in fields)
        params = (*fields.values(), log_id)
        with self.tx() as c:
            cur = c.execute(
                f"UPDATE time_logs SET {cols} WHERE id = ?", params
            )
            if cur.rowcount == 0:
                raise KeyError(f"time_log {log_id} not found")
        row = self.conn.execute(
            "SELECT * FROM time_logs WHERE id = ?", (log_id,)
        ).fetchone()
        return _row_time_log(row)

    def list_notes_for_task(self, task_id: int) -> list[TimeLog]:
        """note が入っているログだけを新しい順で返す。"""
        rows = self.conn.execute(
            """
            SELECT * FROM time_logs
            WHERE task_id = ? AND note IS NOT NULL AND TRIM(note) != ''
            ORDER BY started_at DESC
            """,
            (task_id,),
        ).fetchall()
        return [_row_time_log(r) for r in rows]

    def count_notes_for_task(self, task_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS n FROM time_logs
            WHERE task_id = ? AND note IS NOT NULL AND TRIM(note) != ''
            """,
            (task_id,),
        ).fetchone()
        return int(row["n"] or 0)

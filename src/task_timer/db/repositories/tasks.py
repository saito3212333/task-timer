"""tasks テーブルの CRUD と完了時の再発（recurrence）処理。"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from task_timer.db._converters import _date_str, _row_task
from task_timer.models import Task


class TasksMixin:
    def create_task(self, task: Task) -> Task:
        with self.tx() as c:
            cur = c.execute(
                """
                INSERT INTO tasks(phase_id, name, status, order_index, priority, deadline, planned_hours, recurrence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.phase_id,
                    task.name,
                    task.status,
                    task.order_index,
                    task.priority,
                    _date_str(task.deadline),
                    task.planned_hours,
                    task.recurrence,
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

    def complete_task(self, task_id: int) -> Task | None:
        """status='done'にしてフェーズ末尾に下げる。
        recurrence設定済みなら同位置に active クローンを作って返す。"""
        task = self.get_task(task_id)
        new_clone: Task | None = None
        if task.recurrence in ("daily", "weekly"):
            new_deadline = task.deadline
            if new_deadline is not None:
                delta = 1 if task.recurrence == "daily" else 7
                new_deadline = new_deadline + timedelta(days=delta)
            new_clone = self.create_task(Task(
                phase_id=task.phase_id,
                name=task.name,
                status="active",
                order_index=task.order_index,
                priority=task.priority,
                deadline=new_deadline,
                planned_hours=task.planned_hours,
                recurrence=task.recurrence,
            ))
        siblings = self.list_tasks(task.phase_id)
        max_order = max(
            (t.order_index for t in siblings if t.id != task_id), default=-1
        )
        self.update_task(task_id, status="done", order_index=max_order + 1)
        return new_clone

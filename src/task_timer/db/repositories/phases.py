"""phases テーブルの CRUD。"""
from __future__ import annotations

from typing import Any

from task_timer.db._converters import _date_str, _row_phase
from task_timer.models import Phase


class PhasesMixin:
    def create_phase(self, phase: Phase) -> Phase:
        with self.tx() as c:
            cur = c.execute(
                """
                INSERT INTO phases(project_id, name, status, order_index, deadline, planned_hours, is_routine)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    phase.project_id,
                    phase.name,
                    phase.status,
                    phase.order_index,
                    _date_str(phase.deadline),
                    phase.planned_hours,
                    1 if phase.is_routine else 0,
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

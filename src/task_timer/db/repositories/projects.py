"""projects テーブルの CRUD。"""
from __future__ import annotations

from typing import Any

from task_timer.db._converters import _date_str, _row_project
from task_timer.models import Project


class ProjectsMixin:
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

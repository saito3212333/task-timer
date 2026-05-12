"""管理UI向けのツリー読み込み（Project × Phase × Task）。"""
from __future__ import annotations

from task_timer.models import PhaseWithTasks, ProjectTree


class TreeMixin:
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

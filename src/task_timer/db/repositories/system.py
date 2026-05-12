"""システム必須エンティティ（汎用PJ・ルーティン/スポット phase・スケジューリング task）。"""
from __future__ import annotations

from datetime import date

from task_timer.models import Phase, Project, Task


class SystemEntitiesMixin:
    system_ids: dict[str, int]

    def init_default_setup(self) -> None:
        """起動時に呼び出し：「汎用」プロジェクト・標準フェーズ・スケジューリングタスクが
        無ければ自動生成する。生成されたIDを self.system_ids に保持する。"""
        proj = next((p for p in self.list_projects() if p.name == "汎用"), None)
        if proj is None:
            proj = self.create_project(Project(name="汎用"))

        phases = self.list_phases(proj.id)
        routine = next((ph for ph in phases if ph.name == "ルーティン"), None)
        if routine is None:
            routine = self.create_phase(Phase(
                project_id=proj.id,
                name="ルーティン",
                deadline=date.today(),
                order_index=0,
                is_routine=True,
            ))
        spot = next((ph for ph in phases if ph.name == "スポット"), None)
        if spot is None:
            spot = self.create_phase(Phase(
                project_id=proj.id,
                name="スポット",
                deadline=date.today(),
                order_index=1,
                is_routine=False,
            ))

        sched_task = next(
            (t for t in self.list_tasks(routine.id) if t.name == "スケジューリング"),
            None,
        )
        if sched_task is None:
            sched_task = self.create_task(Task(
                phase_id=routine.id,
                name="スケジューリング",
                order_index=0,
                recurrence=None,
            ))

        self.system_ids = {
            "general_project_id": proj.id,
            "routine_phase_id": routine.id,
            "spot_phase_id": spot.id,
            "scheduling_task_id": sched_task.id,
        }

    def is_system_project(self, project_id: int) -> bool:
        return self.system_ids.get("general_project_id") == project_id

    def is_system_phase(self, phase_id: int) -> bool:
        return phase_id in (
            self.system_ids.get("routine_phase_id"),
            self.system_ids.get("spot_phase_id"),
        )

    def is_system_task(self, task_id: int) -> bool:
        return self.system_ids.get("scheduling_task_id") == task_id

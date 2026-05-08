"""累計時間ダイアログ：タスク・フェーズ・プロジェクトの累計を時間と人工で並べる。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QWidget,
)

from task_timer.db import Database


def _fmt_hm(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h{m:02d}m"


def _fmt_days(sec: int) -> str:
    return f"{sec / 3600 / 8:.2f}人工"


class TotalsDialog(QDialog):
    """1タスク・そのフェーズ・そのプロジェクトの累計を縦に並べる。
    各行に「時間」と「人工」を併記。"""

    def __init__(self, db: Database, task_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("累計時間")
        self.setMinimumWidth(280)

        task = db.get_task(task_id)
        phase = db.get_phase(task.phase_id)
        project = db.get_project(phase.project_id)

        task_sec = db.total_seconds_for_task(task_id)
        phase_sec = db.total_seconds_for_phase(task.phase_id)
        proj_sec = db.total_seconds_for_project(phase.project_id)

        grid = QGridLayout(self)
        grid.setContentsMargins(20, 18, 20, 18)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)

        # ヘッダー行（時間 / 人工）
        h_time = QLabel("時間")
        h_days = QLabel("人工")
        for h in (h_time, h_days):
            h.setStyleSheet("font-size: 11px;")
            h.setAlignment(Qt.AlignRight)
        grid.addWidget(h_time, 0, 1)
        grid.addWidget(h_days, 0, 2)

        rows = [
            (f"タスク（{task.name}）", task_sec),
            (f"フェーズ（{phase.name}）", phase_sec),
            (f"プロジェクト（{project.name}）", proj_sec),
        ]
        for i, (label_text, sec) in enumerate(rows, start=1):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 12px;")
            grid.addWidget(lbl, i, 0)

            time_lbl = QLabel(_fmt_hm(sec))
            time_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
            time_lbl.setAlignment(Qt.AlignRight)
            grid.addWidget(time_lbl, i, 1)

            days_lbl = QLabel(_fmt_days(sec))
            days_lbl.setStyleSheet("font-size: 13px;")
            days_lbl.setAlignment(Qt.AlignRight)
            grid.addWidget(days_lbl, i, 2)

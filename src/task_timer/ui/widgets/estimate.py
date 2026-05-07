"""見積もり／実績バッジ。"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from task_timer.ui.format_helpers import estimate_color, fmt_actual, fmt_planned
from task_timer.ui.theme import MUTED


class EstimateBadge(QLabel):
    """見積もり／実績バッジ。

    - 未完了：`~1h`（薄字）
    - 完了：`1h → 1h32m`（早い=GREEN／近い=MUTED／遅い=ORANGE）
    """

    def __init__(
        self,
        planned_hours: float | None,
        actual_sec: int = 0,
        is_done: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._render(planned_hours, actual_sec, is_done)

    def _render(self, planned_hours: float | None, actual_sec: int, is_done: bool) -> None:
        # 表示すべきものがなければ非表示
        if planned_hours is None and not (is_done and actual_sec > 0):
            self.setText("")
            self.setStyleSheet("background: transparent; padding: 0; font-size: 11px;")
            return

        if is_done and actual_sec > 0:
            actual_str = fmt_actual(actual_sec)
            if planned_hours is not None:
                color = estimate_color(planned_hours, actual_sec)
                text = f"{fmt_planned(planned_hours)} → {actual_str}"
            else:
                color = MUTED
                text = actual_str
        else:
            color = MUTED
            text = f"~{fmt_planned(planned_hours)}"

        self.setText(text)
        self.setStyleSheet(
            f"color: {color}; background: transparent; font-size: 11px; padding: 1px 4px;"
        )

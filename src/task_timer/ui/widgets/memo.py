"""メモ件数バッジ＋履歴ポップアップ。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.ui.format_helpers import fmt_actual
from task_timer.ui.theme import ACCENT, CARD_BG, MUTED, TEXT


class MemoBadge(QPushButton):
    """`📝N` のバッジ。件数0なら非表示。クリックで履歴ダイアログを開く。"""

    def __init__(self, db: Database, task_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.task_id = task_id
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QPushButton {{ color: {MUTED}; background: transparent;"
            f" border: none; font-size: 11px; padding: 1px 4px; }}"
            f"QPushButton:hover {{ color: {ACCENT}; }}"
        )
        self.clicked.connect(self._open_history)
        self.refresh()

    def refresh(self) -> None:
        count = self.db.count_notes_for_task(self.task_id)
        if count <= 0:
            self.setVisible(False)
            self.setText("")
            return
        self.setVisible(True)
        self.setText(f"📝{count}")

    def _open_history(self) -> None:
        dlg = MemoHistoryDialog(self.db, self.task_id, self)
        dlg.exec()


class MemoHistoryDialog(QDialog):
    """1タスクのメモ履歴を縦に並べる。"""

    def __init__(self, db: Database, task_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.task_id = task_id

        task = db.get_task(task_id)
        self.setWindowTitle(f"メモ — {task.name}")
        self.resize(420, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        body = QWidget()
        body.setStyleSheet(f"background: {CARD_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(10)

        logs = db.list_notes_for_task(task_id)
        if not logs:
            empty = QLabel("メモはまだありません")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {MUTED}; font-size: 12px; padding: 20px;")
            bl.addWidget(empty)
        else:
            for log in logs:
                bl.addWidget(self._row(log))

        bl.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll)

    def _row(self, log) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border-bottom: 1px solid #e2e8f0;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 8)
        v.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(8)
        when = log.started_at.strftime("%Y-%m-%d %H:%M") if log.started_at else "—"
        lbl_when = QLabel(when)
        lbl_when.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        head.addWidget(lbl_when)
        lbl_dur = QLabel(fmt_actual(log.duration_sec))
        lbl_dur.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        head.addWidget(lbl_dur)
        head.addStretch()
        v.addLayout(head)

        body = QLabel(log.note or "")
        body.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        body.setWordWrap(True)
        v.addWidget(body)
        return w

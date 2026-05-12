"""1タスクの time_logs を一覧・編集するダイアログ。"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QTime, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import TimeLog
from task_timer.ui.format_helpers import fmt_actual
from task_timer.ui.theme import ACCENT, BTN_STYLE, CARD_BG, MUTED, TEXT


class TimeLogsDialog(QDialog):
    """started_at / ended_at を編集して保存。duration_sec は再計算する。"""

    def __init__(self, db: Database, task_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.task_id = task_id

        task = db.get_task(task_id)
        self.setWindowTitle(f"履歴・ログ編集 — {task.name}")
        self.resize(560, 460)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._body = QWidget()
        self._body.setStyleSheet(f"background: {CARD_BG};")
        self._bl = QVBoxLayout(self._body)
        self._bl.setContentsMargins(16, 12, 16, 12)
        self._bl.setSpacing(8)

        self._reload()

        scroll.setWidget(self._body)
        root.addWidget(scroll)

    def _clear_body(self) -> None:
        while self._bl.count():
            item = self._bl.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _reload(self) -> None:
        self._clear_body()
        hint = QLabel("HH または mm をクリック → 数字入力 / ↑↓キーで変更")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 11px; padding-bottom: 4px;")
        self._bl.addWidget(hint)

        logs = self.db.list_time_logs_for_task(self.task_id)
        if not logs:
            empty = QLabel("ログはまだありません")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {MUTED}; font-size: 12px; padding: 20px;")
            self._bl.addWidget(empty)
        else:
            for log in logs:
                self._bl.addWidget(self._row(log))
        self._bl.addStretch()

    def _row(self, log: TimeLog) -> QWidget:
        w = QWidget()
        w.setStyleSheet("border-bottom: 1px solid #e2e8f0;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 4, 0, 8)
        v.setSpacing(4)

        edits = QHBoxLayout()
        edits.setSpacing(6)

        time_style = (
            "QTimeEdit { background: white; color: #0f172a;"
            " border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px;"
            " min-width: 70px; }"
            "QTimeEdit::up-button, QTimeEdit::down-button { width: 16px; }"
        )

        date_str = log.started_at.strftime("%m/%d") if log.started_at else "—"
        lbl_date = QLabel(date_str)
        lbl_date.setStyleSheet(f"color: {TEXT}; font-size: 12px;")

        lbl_s = QLabel("開始")
        lbl_s.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        time_s = QTimeEdit()
        time_s.setDisplayFormat("HH:mm")
        time_s.setStyleSheet(time_style)
        if log.started_at:
            time_s.setTime(QTime(log.started_at.hour, log.started_at.minute))

        lbl_e = QLabel("終了")
        lbl_e.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        time_e = QTimeEdit()
        time_e.setDisplayFormat("HH:mm")
        time_e.setStyleSheet(time_style)
        if log.ended_at:
            time_e.setTime(QTime(log.ended_at.hour, log.ended_at.minute))

        lbl_dur = QLabel(fmt_actual(log.duration_sec))
        lbl_dur.setStyleSheet(f"color: {TEXT}; font-size: 11px;")

        btn_save = QPushButton("保存")
        btn_save.setStyleSheet(BTN_STYLE)
        btn_save.clicked.connect(lambda: self._save(log, time_s, time_e, lbl_dur))

        edits.addWidget(lbl_date)
        edits.addSpacing(6)
        edits.addWidget(lbl_s)
        edits.addWidget(time_s)
        edits.addWidget(lbl_e)
        edits.addWidget(time_e)
        edits.addStretch()
        edits.addWidget(lbl_dur)
        edits.addWidget(btn_save)
        v.addLayout(edits)

        if log.note:
            note = QLabel(log.note)
            note.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
            note.setWordWrap(True)
            v.addWidget(note)

        return w

    def _save(
        self,
        log: TimeLog,
        time_s: QTimeEdit,
        time_e: QTimeEdit,
        lbl_dur: QLabel,
    ) -> None:
        # 元の started_at の日付を基準にする（夜またぎは ended を翌日扱い）
        base_date = log.started_at.date() if log.started_at else datetime.now().date()
        qts = time_s.time()
        qte = time_e.time()
        s = datetime(base_date.year, base_date.month, base_date.day, qts.hour(), qts.minute())
        e = datetime(base_date.year, base_date.month, base_date.day, qte.hour(), qte.minute())
        if e < s:
            e += timedelta(days=1)
        duration = int((e - s).total_seconds())
        if duration <= 0:
            QMessageBox.warning(self, "保存できません", "開始と終了が同じです。")
            return
        self.db.update_time_log(
            log.id,
            started_at=s.isoformat(timespec="seconds"),
            ended_at=e.isoformat(timespec="seconds"),
            duration_sec=duration,
        )
        log.started_at = s
        log.ended_at = e
        log.duration_sec = duration
        lbl_dur.setText(fmt_actual(duration))
        lbl_dur.setStyleSheet(f"color: {ACCENT}; font-size: 11px;")

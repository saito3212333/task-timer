"""タスクカード：チェック・名前編集・見積／締切バッジ・削除を1行に。"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QFont, QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import Task
from task_timer.ui.theme import ACCENT, CARD_BG, MUTED, TEXT
from task_timer.ui.widgets.deadline import DeadlineBadge, DeadlinePicker
from task_timer.ui.widgets.memo import MemoBadge


class TaskCard(QWidget):
    deleted          = Signal(int)        # task_id
    status_changed   = Signal(int, bool)  # task_id, is_done
    split_requested  = Signal(int)        # task_id

    MIME_TYPE = "application/x-task-timer-task-id"

    def __init__(
        self,
        task: Task,
        db: Database,
        is_in_routine_phase: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.task = task
        self.db = db
        self.is_in_routine_phase = is_in_routine_phase
        self._committing = False
        self._drag_start: QPoint | None = None

        self.setObjectName("TaskCard")
        self.setStyleSheet(
            f"#TaskCard {{ background: {CARD_BG}; border: 1px solid #cbd5e1; border-radius: 6px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        self.check = QCheckBox()
        self.check.setChecked(task.status == "done")
        self.check.toggled.connect(self._on_toggle)

        # 繰り返し設定済みなら 🔁
        self.recurrence_icon = QLabel("🔁")
        self.recurrence_icon.setStyleSheet(
            f"color: {MUTED}; background: transparent; font-size: 11px;"
        )
        self.recurrence_icon.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._update_recurrence_icon()

        # 読み取り専用 QLineEdit をラベル代わりに使う
        self.name_edit = QLineEdit(task.name)
        self.name_edit.setReadOnly(True)
        self.name_edit.setFrame(False)
        self.name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.name_edit.setCursor(Qt.OpenHandCursor)
        self.name_edit.installEventFilter(self)
        self.name_edit.returnPressed.connect(self._commit_edit)
        self._apply_name_style()
        self._adjust_name_font()

        self.deadline_badge = DeadlineBadge(task.deadline)
        self.deadline_badge.clicked.connect(self._open_deadline_picker)

        self.memo_badge = MemoBadge(db, task.id) if task.id else None

        self.btn_del = QPushButton("×")
        self.btn_del.setFixedSize(20, 20)
        self.btn_del.setFlat(True)
        self.btn_del.setStyleSheet(
            f"color: {MUTED}; font-size: 14px; background: transparent;"
        )
        self.btn_del.clicked.connect(lambda: self.deleted.emit(task.id))
        # システムタスク（スケジューリング）は削除させない
        if task.id is not None and db.is_system_task(task.id):
            self.btn_del.setVisible(False)

        layout.addWidget(self.check)
        layout.addSpacing(8)
        layout.addWidget(self.recurrence_icon)
        layout.addWidget(self.name_edit, 1)
        if self.memo_badge is not None:
            layout.addWidget(self.memo_badge)
        layout.addWidget(self.deadline_badge)
        layout.addWidget(self.btn_del)

    # ── event filter（ダブルクリック編集 / フォーカスアウト保存 / ドラッグ開始）

    def eventFilter(self, obj, event):
        if obj is self.name_edit:
            et = event.type()
            if et == QEvent.Type.MouseButtonDblClick and self.name_edit.isReadOnly():
                self._start_edit()
                return True
            if et == QEvent.Type.FocusOut and not self.name_edit.isReadOnly():
                self._commit_edit()
            # ドラッグ起点：読み取り専用かつ未完了のときだけ
            if self.name_edit.isReadOnly() and not self.check.isChecked():
                if et == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                    self._drag_start = event.position().toPoint()
                elif et == QEvent.Type.MouseMove and self._drag_start is not None:
                    if (event.position().toPoint() - self._drag_start).manhattanLength() >= QApplication.startDragDistance():
                        self._begin_drag()
                        self._drag_start = None
                        return True
                elif et == QEvent.Type.MouseButtonRelease:
                    self._drag_start = None
        return super().eventFilter(obj, event)

    def _begin_drag(self) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, str(self.task.id).encode())
        drag.setMimeData(mime)
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(20, self.height() // 2))
        drag.exec(Qt.MoveAction)

    # ── 右クリック → 分解／削除 ────────────────────────────────────────

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu, QMenu QMenu {{
                background: white;
                color: {TEXT};
                border: 1px solid #cbd5e1;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 18px;
                color: {TEXT};
            }}
            QMenu::item:selected {{
                background: {ACCENT};
                color: white;
            }}
            """
        )

        is_system = self.task.id is not None and self.db.is_system_task(self.task.id)

        # ルーティンフェーズのみ「繰り返し」サブメニューを出す
        act_rec_off = act_rec_daily = act_rec_weekly = None
        if self.is_in_routine_phase and not is_system:
            sub = menu.addMenu("繰り返し")
            act_rec_off    = sub.addAction(("● " if self.task.recurrence is None     else "  ") + "なし")
            act_rec_daily  = sub.addAction(("● " if self.task.recurrence == "daily"  else "  ") + "毎日")
            act_rec_weekly = sub.addAction(("● " if self.task.recurrence == "weekly" else "  ") + "毎週")
            menu.addSeparator()

        act_split = act_del = None
        if not is_system:
            act_split = menu.addAction("分解…")
            act_del   = menu.addAction("削除")
        if menu.isEmpty():
            return
        chosen = menu.exec(event.globalPos())

        if chosen is None:
            return
        if chosen is act_split:
            self.split_requested.emit(self.task.id)
        elif chosen is act_del:
            self.deleted.emit(self.task.id)
        elif chosen is act_rec_off:
            self._set_recurrence(None)
        elif chosen is act_rec_daily:
            self._set_recurrence("daily")
        elif chosen is act_rec_weekly:
            self._set_recurrence("weekly")

    def _set_recurrence(self, value: str | None) -> None:
        if self.task.recurrence == value:
            return
        self.db.update_task(self.task.id, recurrence=value)
        self.task.recurrence = value
        self._update_recurrence_icon()

    def _update_recurrence_icon(self) -> None:
        self.recurrence_icon.setVisible(self.task.recurrence is not None)
        if self.task.recurrence == "weekly":
            self.recurrence_icon.setToolTip("毎週")
        elif self.task.recurrence == "daily":
            self.recurrence_icon.setToolTip("毎日")
        else:
            self.recurrence_icon.setToolTip("")

    def _start_edit(self) -> None:
        self.name_edit.setReadOnly(False)
        self.name_edit.setStyleSheet(
            f"color: {TEXT}; background: white;"
            f" border: 1px solid {ACCENT}; border-radius: 3px; padding: 1px 3px;"
        )
        self.name_edit.selectAll()
        self.name_edit.setFocus()

    def _commit_edit(self) -> None:
        if self._committing:
            return
        self._committing = True
        name = self.name_edit.text().strip()
        if name:
            self.db.update_task(self.task.id, name=name)
            self.task.name = name
        else:
            self.name_edit.setText(self.task.name)
        self.name_edit.setReadOnly(True)
        self._apply_name_style()
        self._adjust_name_font()
        self._committing = False

    # ── toggle ────────────────────────────────────────────────────────────

    def _on_toggle(self, checked: bool) -> None:
        new_status = "done" if checked else "active"
        self.db.update_task(self.task.id, status=new_status)
        self.task.status = new_status
        self._apply_name_style()
        self.status_changed.emit(self.task.id, checked)

    # ── deadline ──────────────────────────────────────────────────────────

    def _open_deadline_picker(self) -> None:
        dlg = DeadlinePicker(self.task.deadline, allow_clear=True, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        cleared, new_date = dlg.result_value()
        if cleared:
            self.db.update_task(self.task.id, deadline=None)
            self.task.deadline = None
        elif new_date is not None and new_date != self.task.deadline:
            self.db.update_task(self.task.id, deadline=new_date)
            self.task.deadline = new_date
        self.deadline_badge.set_deadline(self.task.deadline)

    def _apply_name_style(self) -> None:
        if self.check.isChecked():
            self.name_edit.setStyleSheet(
                f"color: {MUTED}; text-decoration: line-through;"
                " background: transparent; border: none;"
            )
        else:
            self.name_edit.setStyleSheet(
                f"color: {TEXT}; background: transparent; border: none;"
            )

    def _adjust_name_font(self) -> None:
        """利用可能幅に応じてフォントサイズを 13 → 9pt の範囲で縮める。"""
        text = self.name_edit.text()
        f = QFont(self.name_edit.font())
        f.setPointSize(13)
        available = self.name_edit.width() - 6
        if text and available > 0:
            while f.pointSize() > 9:
                if QFontMetrics(f).horizontalAdvance(text) <= available:
                    break
                f.setPointSize(f.pointSize() - 1)
        self.name_edit.setFont(f)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._adjust_name_font()

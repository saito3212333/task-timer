"""フェーズ列：ヘッダー（編集可・進捗バッジ・締切）＋カードリスト＋追加入力。"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import Phase, Task
from task_timer.ui.theme import ACCENT, CARD_BG, MUTED, PHASE_COL_BGS, TEXT
from task_timer.ui.widgets.deadline import DeadlineBadge, DeadlinePicker
from task_timer.ui.widgets.task_card import TaskCard


class PhaseColumn(QWidget):
    task_added           = Signal(int, str)        # phase_id, name
    task_deleted         = Signal(int)             # task_id
    task_status_changed  = Signal(int, bool)       # task_id, is_done
    task_dropped         = Signal(int, int, int)   # task_id, target_phase_id, insert_index
    task_split_requested = Signal(int)             # task_id
    task_start_timer     = Signal(int)             # task_id
    task_logs_edit       = Signal(int)             # task_id
    phase_deleted        = Signal(int)             # phase_id

    def __init__(
        self,
        db: Database,
        phase: Phase,
        tasks: list[Task],
        total_count: int = 0,
        done_count: int = 0,
        index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.phase = phase
        self._title_committing = False

        self.setFixedWidth(240)
        self.setObjectName("PhaseColumn")
        self.setAttribute(Qt.WA_StyledBackground, True)
        bg = PHASE_COL_BGS[index % len(PHASE_COL_BGS)]
        self.setStyleSheet(
            f"#PhaseColumn {{ background: {bg}; border-radius: 10px; }}"
        )
        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        # Header（タイトルはダブルクリックで編集可）
        header = QHBoxLayout()
        self.title_edit = QLineEdit(phase.name)
        self.title_edit.setReadOnly(True)
        self.title_edit.setFrame(False)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        self.title_edit.setFont(title_font)
        self.title_edit.setCursor(Qt.OpenHandCursor)
        self.title_edit.setStyleSheet(
            f"color: {TEXT}; background: transparent; border: none; padding: 0;"
        )
        self.title_edit.installEventFilter(self)
        self.title_edit.returnPressed.connect(self._commit_title)

        self.progress_label = QLabel(f"{done_count}/{total_count}")
        self.progress_label.setStyleSheet(
            f"color: {MUTED}; background: transparent; font-size: 11px;"
        )
        self.progress_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        self.routine_badge = QLabel("🔁")
        self.routine_badge.setStyleSheet(
            f"color: {MUTED}; background: transparent; font-size: 11px;"
        )
        self.routine_badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.routine_badge.setVisible(bool(phase.is_routine))
        self.routine_badge.setToolTip("ルーティンフェーズ")

        self.deadline_badge = DeadlineBadge(phase.deadline)
        self.deadline_badge.clicked.connect(self._open_deadline_picker)

        btn_del = QPushButton("×")
        btn_del.setFixedSize(22, 22)
        btn_del.setFlat(True)
        btn_del.setStyleSheet(f"color: {MUTED}; font-size: 14px; background: transparent;")
        btn_del.clicked.connect(lambda: self.phase_deleted.emit(phase.id))
        # システムフェーズ（汎用→ルーティン/スポット）は削除させない
        if phase.id is not None and db.is_system_phase(phase.id):
            btn_del.setVisible(False)

        header.addWidget(self.title_edit, 1)
        header.addWidget(self.progress_label)
        header.addWidget(self.routine_badge)
        header.addWidget(self.deadline_badge)
        header.addWidget(btn_del)
        outer.addLayout(header)

        # Cards
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(4)
        for t in tasks:
            card = TaskCard(t, db, is_in_routine_phase=phase.is_routine)
            card.deleted.connect(self.task_deleted.emit)
            card.status_changed.connect(self.task_status_changed.emit)
            card.split_requested.connect(self.task_split_requested.emit)
            card.start_timer_requested.connect(self.task_start_timer.emit)
            card.logs_edit_requested.connect(self.task_logs_edit.emit)
            self.cards_layout.addWidget(card)
        outer.addLayout(self.cards_layout)

        outer.addStretch()

        # Drop indicator (overlay; not in layout)
        self._drop_indicator = QFrame(self)
        self._drop_indicator.setFixedHeight(3)
        self._drop_indicator.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
        self._drop_indicator.hide()

        # Add task input
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("＋ タスクを追加…")
        self.add_input.setStyleSheet(f"""
            QLineEdit {{
                background: {CARD_BG};
                color: {TEXT};
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 5px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
        """)
        self.add_input.returnPressed.connect(self._on_add)
        outer.addWidget(self.add_input)

    def _on_add(self) -> None:
        name = self.add_input.text().strip()
        if name:
            self.add_input.clear()
            self.task_added.emit(self.phase.id, name)

    # ── title edit (double-click) ────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.title_edit:
            et = event.type()
            if et == QEvent.Type.MouseButtonDblClick and self.title_edit.isReadOnly():
                self._start_title_edit()
                return True
            if et == QEvent.Type.FocusOut and not self.title_edit.isReadOnly():
                self._commit_title()
        return super().eventFilter(obj, event)

    def _start_title_edit(self) -> None:
        self.title_edit.setReadOnly(False)
        self.title_edit.setStyleSheet(
            f"color: {TEXT}; background: white;"
            f" border: 1px solid {ACCENT}; border-radius: 3px; padding: 1px 3px;"
        )
        self.title_edit.selectAll()
        self.title_edit.setFocus()

    def _commit_title(self) -> None:
        if self._title_committing:
            return
        self._title_committing = True
        name = self.title_edit.text().strip()
        if name and name != self.phase.name:
            self.db.update_phase(self.phase.id, name=name)
            self.phase.name = name
        else:
            self.title_edit.setText(self.phase.name)
        self.title_edit.setReadOnly(True)
        self.title_edit.setStyleSheet(
            f"color: {TEXT}; background: transparent; border: none; padding: 0;"
        )
        self._title_committing = False

    def _open_deadline_picker(self) -> None:
        dlg = DeadlinePicker(self.phase.deadline, allow_clear=False, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        _, new_date = dlg.result_value()
        if new_date is not None and new_date != self.phase.deadline:
            self.db.update_phase(self.phase.id, deadline=new_date)
            self.phase.deadline = new_date
            self.deadline_badge.set_deadline(new_date)

    # ── drag & drop ──────────────────────────────────────────────────────

    def _cards(self) -> list[QWidget]:
        items = [self.cards_layout.itemAt(i) for i in range(self.cards_layout.count())]
        return [it.widget() for it in items if it and it.widget() is not None]

    def _calc_insert_index(self, y: int) -> tuple[int, int]:
        """y座標に対応する挿入インデックスと、そのY位置を返す。"""
        cards = self._cards()
        for i, c in enumerate(cards):
            top = c.mapTo(self, c.rect().topLeft()).y()
            mid = top + c.height() / 2
            if y < mid:
                return i, top - 2
        if cards:
            last = cards[-1]
            bot = last.mapTo(self, last.rect().topLeft()).y() + last.height()
            return len(cards), bot
        # 空フェーズ：カード領域の先頭を見つける
        layout_top = self.cards_layout.geometry().y()
        return 0, max(layout_top, 50)

    def _show_drop_indicator(self, y: int) -> None:
        _, ind_y = self._calc_insert_index(y)
        self._drop_indicator.setGeometry(8, int(ind_y), self.width() - 16, 3)
        self._drop_indicator.show()
        self._drop_indicator.raise_()

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasFormat(TaskCard.MIME_TYPE):
            e.acceptProposedAction()

    def dragMoveEvent(self, e) -> None:
        if e.mimeData().hasFormat(TaskCard.MIME_TYPE):
            self._show_drop_indicator(int(e.position().y()))
            e.acceptProposedAction()

    def dragLeaveEvent(self, e) -> None:
        self._drop_indicator.hide()

    def dropEvent(self, e) -> None:
        if not e.mimeData().hasFormat(TaskCard.MIME_TYPE):
            return
        try:
            task_id = int(bytes(e.mimeData().data(TaskCard.MIME_TYPE)).decode())
        except (ValueError, UnicodeDecodeError):
            return
        index, _ = self._calc_insert_index(int(e.position().y()))
        self._drop_indicator.hide()
        e.acceptProposedAction()
        self.task_dropped.emit(task_id, self.phase.id, index)

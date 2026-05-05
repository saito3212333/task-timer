from __future__ import annotations

from datetime import date

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import Phase, Project, Task

BG        = "#e2e8f0"
COL_BG    = "#f1f5f9"
CARD_BG   = "#ffffff"
TOPBAR_BG = "#1e293b"
TEXT      = "#1e293b"
MUTED     = "#64748b"
ACCENT    = "#3b82f6"

_BTN_STYLE = f"""
    QPushButton {{
        background: {ACCENT};
        color: white;
        border: none;
        border-radius: 5px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{ background: #2563eb; }}
"""
_BTN_DANGER = """
    QPushButton {
        background: #ef4444;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 5px 12px;
    }
    QPushButton:hover { background: #dc2626; }
"""


# ---------------------------------------------------------------------------
# Task card  （①インライン編集）
# ---------------------------------------------------------------------------

class TaskCard(QWidget):
    deleted = Signal(int)  # task_id

    def __init__(self, task: Task, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task = task
        self.db = db
        self._committing = False

        self.setStyleSheet(
            f"background: {CARD_BG}; border: 1px solid #cbd5e1; border-radius: 6px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.check = QCheckBox()
        self.check.setChecked(task.status == "done")
        self.check.toggled.connect(self._on_toggle)

        # 読み取り専用 QLineEdit をラベル代わりに使う
        self.name_edit = QLineEdit(task.name)
        self.name_edit.setReadOnly(True)
        self.name_edit.setFrame(False)
        self.name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.name_edit.installEventFilter(self)
        self.name_edit.returnPressed.connect(self._commit_edit)
        self._apply_name_style()

        self.btn_del = QPushButton("×")
        self.btn_del.setFixedSize(20, 20)
        self.btn_del.setFlat(True)
        self.btn_del.setStyleSheet(
            f"color: {MUTED}; font-size: 14px; background: transparent;"
        )
        self.btn_del.clicked.connect(lambda: self.deleted.emit(task.id))

        layout.addWidget(self.check)
        layout.addWidget(self.name_edit, 1)
        layout.addWidget(self.btn_del)

    # ── event filter（ダブルクリック＆フォーカスアウト）─────────────────

    def eventFilter(self, obj, event):
        if obj is self.name_edit:
            if (
                event.type() == QEvent.Type.MouseButtonDblClick
                and self.name_edit.isReadOnly()
            ):
                self._start_edit()
                return True
            if (
                event.type() == QEvent.Type.FocusOut
                and not self.name_edit.isReadOnly()
            ):
                self._commit_edit()
        return super().eventFilter(obj, event)

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
        else:
            self.name_edit.setText(self.task.name)
        self.name_edit.setReadOnly(True)
        self._apply_name_style()
        self._committing = False

    # ── toggle ────────────────────────────────────────────────────────────

    def _on_toggle(self, checked: bool) -> None:
        self.db.update_task(self.task.id, status="done" if checked else "active")
        self._apply_name_style()

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


# ---------------------------------------------------------------------------
# Phase column
# ---------------------------------------------------------------------------

class PhaseColumn(QWidget):
    task_added   = Signal(int, str)  # phase_id, name
    task_deleted = Signal(int)       # task_id
    phase_deleted = Signal(int)      # phase_id

    def __init__(
        self,
        db: Database,
        phase: Phase,
        tasks: list[Task],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.phase = phase

        self.setFixedWidth(240)
        self.setStyleSheet(f"background: {COL_BG}; border-radius: 10px;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title = QLabel(phase.name)
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {TEXT}; background: transparent;")

        btn_del = QPushButton("×")
        btn_del.setFixedSize(22, 22)
        btn_del.setFlat(True)
        btn_del.setStyleSheet(f"color: {MUTED}; font-size: 14px; background: transparent;")
        btn_del.clicked.connect(lambda: self.phase_deleted.emit(phase.id))

        header.addWidget(title, 1)
        header.addWidget(btn_del)
        outer.addLayout(header)

        # Cards
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(4)
        for t in tasks:
            card = TaskCard(t, db)
            card.deleted.connect(self.task_deleted.emit)
            self.cards_layout.addWidget(card)
        outer.addLayout(self.cards_layout)

        outer.addStretch()

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
            self.task_added.emit(self.phase.id, name)
            self.add_input.clear()


# ---------------------------------------------------------------------------
# Kanban window  （②プロジェクト削除）
# ---------------------------------------------------------------------------

class KanbanWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._project_id: int | None = None

        self.setWindowTitle("Task Timer — ボード")
        self.resize(960, 620)

        # ── Top bar ──────────────────────────────────────────────────────
        top = QWidget()
        top.setStyleSheet(f"background: {TOPBAR_BG};")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(16, 10, 16, 10)
        tl.setSpacing(10)

        lbl = QLabel("プロジェクト")
        lbl.setStyleSheet("color: #94a3b8; background: transparent;")
        tl.addWidget(lbl)

        self.project_cmb = QComboBox()
        self.project_cmb.setMinimumWidth(200)
        self.project_cmb.setStyleSheet(f"""
            QComboBox {{
                background: #334155; color: #f1f5f9;
                border: 1px solid #475569; border-radius: 5px; padding: 4px 8px;
            }}
            QComboBox QAbstractItemView {{
                background: #334155; color: #f1f5f9;
                selection-background-color: {ACCENT};
            }}
        """)
        self.project_cmb.currentIndexChanged.connect(self._on_project_changed)
        tl.addWidget(self.project_cmb)

        btn_add_proj = QPushButton("＋ プロジェクト")
        btn_add_proj.setStyleSheet(_BTN_STYLE)
        btn_add_proj.clicked.connect(self._add_project)
        tl.addWidget(btn_add_proj)

        # ② プロジェクト削除ボタン
        btn_del_proj = QPushButton("削除")
        btn_del_proj.setStyleSheet(_BTN_DANGER)
        btn_del_proj.clicked.connect(self._delete_project)
        tl.addWidget(btn_del_proj)

        tl.addStretch()

        # ── Board scroll area ─────────────────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(self.scroll.Shape.NoFrame)
        self.scroll.setStyleSheet(f"background: {BG};")

        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(top)
        cl.addWidget(self.scroll, 1)
        self.setCentralWidget(central)

        self._load_projects()

    # ── project selector ─────────────────────────────────────────────────

    def _load_projects(self) -> None:
        self.project_cmb.blockSignals(True)
        self.project_cmb.clear()
        for p in self.db.list_projects():
            self.project_cmb.addItem(p.name, userData=p.id)
        self.project_cmb.blockSignals(False)
        self._project_id = self.project_cmb.currentData()
        self._reload_board()

    def _on_project_changed(self) -> None:
        self._project_id = self.project_cmb.currentData()
        self._reload_board()

    # ── board ─────────────────────────────────────────────────────────────

    def _reload_board(self) -> None:
        board = QWidget()
        board.setStyleSheet(f"background: {BG};")
        layout = QHBoxLayout(board)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        if self._project_id is not None:
            trees = self.db.load_all_trees()
            proj_tree = next(
                (t for t in trees if t.project.id == self._project_id), None
            )
            if proj_tree:
                for pwt in proj_tree.phases:
                    col = PhaseColumn(self.db, pwt.phase, pwt.tasks)
                    col.task_added.connect(self._on_task_added)
                    col.task_deleted.connect(self._on_task_deleted)
                    col.phase_deleted.connect(self._on_phase_deleted)
                    layout.addWidget(col)

        btn_add_phase = QPushButton("＋\nフェーズ")
        btn_add_phase.setFixedSize(70, 80)
        btn_add_phase.setStyleSheet(f"""
            QPushButton {{
                background: #cbd5e1; border-radius: 10px;
                color: {TEXT}; font-size: 13px;
            }}
            QPushButton:hover {{ background: #94a3b8; }}
        """)
        btn_add_phase.clicked.connect(self._add_phase)
        layout.addWidget(btn_add_phase)

        layout.addStretch()
        self.scroll.setWidget(board)

    # ── slots ─────────────────────────────────────────────────────────────

    def _on_task_added(self, phase_id: int, name: str) -> None:
        existing = self.db.list_tasks(phase_id)
        order = (max((t.order_index for t in existing), default=-1)) + 1
        self.db.create_task(Task(phase_id=phase_id, name=name, order_index=order))
        self._reload_board()

    def _on_task_deleted(self, task_id: int) -> None:
        reply = QMessageBox.question(self, "削除確認", "このタスクを削除しますか？")
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_task(task_id)
            self._reload_board()

    def _on_phase_deleted(self, phase_id: int) -> None:
        reply = QMessageBox.question(
            self, "削除確認", "このフェーズを削除しますか？\n（タスクもすべて削除されます）"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_phase(phase_id)
            self._reload_board()

    def _add_project(self) -> None:
        name, ok = QInputDialog.getText(self, "プロジェクト追加", "名前:")
        if not ok or not name.strip():
            return
        p = self.db.create_project(Project(name=name.strip()))
        self._load_projects()
        idx = self.project_cmb.findData(p.id)
        if idx >= 0:
            self.project_cmb.setCurrentIndex(idx)

    def _delete_project(self) -> None:
        if self._project_id is None:
            return
        name = self.project_cmb.currentText()
        reply = QMessageBox.question(
            self,
            "プロジェクト削除",
            f"「{name}」を削除しますか？\n（フェーズ・タスクもすべて削除されます）",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_project(self._project_id)
            self._project_id = None
            self._load_projects()

    def _add_phase(self) -> None:
        if self._project_id is None:
            return
        name, ok = QInputDialog.getText(self, "フェーズ追加", "名前:")
        if not ok or not name.strip():
            return
        existing = self.db.list_phases(self._project_id)
        order = (max((ph.order_index for ph in existing), default=-1)) + 1
        self.db.create_phase(Phase(
            project_id=self._project_id,
            name=name.strip(),
            deadline=date.today(),
            order_index=order,
        ))
        self._reload_board()

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import Phase, Project, Task

Kind = Literal["project", "phase", "task"]

PLANNED_HOURS_OPTIONS: list[tuple[str, float | None]] = [
    ("未設定", None),
    ("XS (15分)", 0.25),
    ("S (30分)", 0.5),
    ("M (1時間)", 1.0),
    ("L (2時間)", 2.0),
    ("XL (4時間)", 4.0),
    ("XXL (1日 / 8時間)", 8.0),
]

STATUS_OPTIONS: list[str] = ["active", "done", "archived"]
PRIORITY_OPTIONS: list[str] = ["high", "normal", "low"]


# ---------------------------------------------------------------------------
# Tree item helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeRef:
    kind: Kind
    id: int


def _set_node_ref(item: QTreeWidgetItem, ref: NodeRef) -> None:
    item.setData(0, Qt.ItemDataRole.UserRole, ref)


def _node_ref(item: QTreeWidgetItem) -> NodeRef | None:
    return item.data(0, Qt.ItemDataRole.UserRole)


def _format_planned(hours: float | None) -> str:
    if hours is None:
        return ""
    for label, value in PLANNED_HOURS_OPTIONS:
        if value == hours:
            return label
    return f"{hours}h"


def _format_date(d: date | None) -> str:
    return d.isoformat() if d else ""


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------

class DetailPanel(QWidget):
    """Editor for the currently selected tree node."""

    saved = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._current: NodeRef | None = None

        self.title = QLabel("選択なし")
        font = self.title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.title.setFont(font)

        self.name_edit = QLineEdit()
        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUS_OPTIONS)

        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDisplayFormat("yyyy-MM-dd")
        self.deadline_clear_btn = QPushButton("クリア")
        self.deadline_clear_btn.clicked.connect(self._clear_deadline)
        deadline_row = QHBoxLayout()
        deadline_row.setContentsMargins(0, 0, 0, 0)
        deadline_row.addWidget(self.deadline_edit, 1)
        deadline_row.addWidget(self.deadline_clear_btn)
        deadline_wrap = QWidget()
        deadline_wrap.setLayout(deadline_row)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(PRIORITY_OPTIONS)

        self.planned_combo = QComboBox()
        for label, _ in PLANNED_HOURS_OPTIONS:
            self.planned_combo.addItem(label)

        form = QFormLayout()
        form.addRow("名前", self.name_edit)
        form.addRow("状態", self.status_combo)
        self._deadline_row_label = QLabel("締切")
        form.addRow(self._deadline_row_label, deadline_wrap)
        self._priority_row_label = QLabel("優先度")
        form.addRow(self._priority_row_label, self.priority_combo)
        self._planned_row_label = QLabel("見積")
        form.addRow(self._planned_row_label, self.planned_combo)

        self.save_btn = QPushButton("保存")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        group = QGroupBox()
        group.setLayout(form)
        layout.addWidget(group)
        layout.addWidget(self.save_btn)
        layout.addStretch(1)

        self._priority_widgets = (self._priority_row_label, self.priority_combo)
        self._set_enabled(False)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def show_node(self, ref: NodeRef | None) -> None:
        self._current = ref
        if ref is None:
            self.title.setText("選択なし")
            self.name_edit.clear()
            self._set_enabled(False)
            return

        self._set_enabled(True)
        if ref.kind == "project":
            p = self.db.get_project(ref.id)
            self.title.setText(f"プロジェクト: {p.name}")
            self.name_edit.setText(p.name)
            self.status_combo.setCurrentText(p.status)
            self._set_deadline(p.deadline)
            self._set_planned(p.planned_hours)
            self._show_priority(False)
            self._deadline_required(False)
        elif ref.kind == "phase":
            ph = self.db.get_phase(ref.id)
            self.title.setText(f"フェーズ: {ph.name}")
            self.name_edit.setText(ph.name)
            self.status_combo.setCurrentText(ph.status)
            self._set_deadline(ph.deadline)
            self._set_planned(ph.planned_hours)
            self._show_priority(False)
            self._deadline_required(True)
        else:  # task
            t = self.db.get_task(ref.id)
            self.title.setText(f"タスク: {t.name}")
            self.name_edit.setText(t.name)
            self.status_combo.setCurrentText(t.status)
            self._set_deadline(t.deadline)
            self._set_planned(t.planned_hours)
            self.priority_combo.setCurrentText(t.priority)
            self._show_priority(True)
            self._deadline_required(False)

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------
    def _set_enabled(self, enabled: bool) -> None:
        self.name_edit.setEnabled(enabled)
        self.status_combo.setEnabled(enabled)
        self.deadline_edit.setEnabled(enabled)
        self.deadline_clear_btn.setEnabled(enabled)
        self.priority_combo.setEnabled(enabled)
        self.planned_combo.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)

    def _show_priority(self, show: bool) -> None:
        for w in self._priority_widgets:
            w.setVisible(show)

    def _deadline_required(self, required: bool) -> None:
        suffix = " *" if required else ""
        self._deadline_row_label.setText("締切" + suffix)
        self.deadline_clear_btn.setVisible(not required)

    def _set_deadline(self, d: date | None) -> None:
        if d is None:
            today = date.today()
            self.deadline_edit.setDate(QDate(today.year, today.month, today.day))
            self.deadline_edit.setSpecialValueText(" ")
            self.deadline_edit.setProperty("hasDate", False)
            self.deadline_edit.setDate(self.deadline_edit.minimumDate())
        else:
            self.deadline_edit.setDate(QDate(d.year, d.month, d.day))
            self.deadline_edit.setProperty("hasDate", True)

    def _clear_deadline(self) -> None:
        self.deadline_edit.setDate(self.deadline_edit.minimumDate())
        self.deadline_edit.setProperty("hasDate", False)

    def _read_deadline(self) -> date | None:
        if self.deadline_edit.date() == self.deadline_edit.minimumDate():
            return None
        qd = self.deadline_edit.date()
        return date(qd.year(), qd.month(), qd.day())

    def _set_planned(self, hours: float | None) -> None:
        for i, (_, v) in enumerate(PLANNED_HOURS_OPTIONS):
            if v == hours:
                self.planned_combo.setCurrentIndex(i)
                return
        self.planned_combo.setCurrentIndex(0)

    def _read_planned(self) -> float | None:
        idx = self.planned_combo.currentIndex()
        return PLANNED_HOURS_OPTIONS[idx][1]

    def _on_save(self) -> None:
        ref = self._current
        if ref is None:
            return

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "保存できません", "名前を入力してください")
            return

        status = self.status_combo.currentText()
        deadline = self._read_deadline()
        planned = self._read_planned()

        try:
            if ref.kind == "project":
                self.db.update_project(
                    ref.id,
                    name=name,
                    status=status,
                    deadline=deadline,
                    planned_hours=planned,
                )
            elif ref.kind == "phase":
                if deadline is None:
                    QMessageBox.warning(
                        self, "保存できません", "フェーズには締切が必須です"
                    )
                    return
                self.db.update_phase(
                    ref.id,
                    name=name,
                    status=status,
                    deadline=deadline,
                    planned_hours=planned,
                )
            else:
                self.db.update_task(
                    ref.id,
                    name=name,
                    status=status,
                    deadline=deadline,
                    priority=self.priority_combo.currentText(),
                    planned_hours=planned,
                )
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存に失敗", str(e))
            return

        self.saved.emit()


# ---------------------------------------------------------------------------
# Manager window
# ---------------------------------------------------------------------------

class ManagerWindow(QMainWindow):
    HEADERS = ["名前", "状態", "締切", "優先度", "見積"]

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("Task Timer — 管理")
        self.resize(900, 600)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(self.HEADERS)
        self.tree.setColumnWidth(0, 320)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        self.detail = DetailPanel(self.db)
        self.detail.saved.connect(self._on_detail_saved)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self.statusBar().showMessage("Ready")
        self.reload()

    # ------------------------------------------------------------------
    # toolbar / actions
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        tb = QToolBar("Actions")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.act_add_project = QAction("＋ プロジェクト", self)
        self.act_add_project.triggered.connect(self._add_project)
        tb.addAction(self.act_add_project)

        self.act_add_phase = QAction("＋ フェーズ", self)
        self.act_add_phase.triggered.connect(self._add_phase)
        tb.addAction(self.act_add_phase)

        self.act_add_task = QAction("＋ タスク", self)
        self.act_add_task.triggered.connect(self._add_task)
        tb.addAction(self.act_add_task)

        tb.addSeparator()

        self.act_delete = QAction("削除", self)
        self.act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self.act_delete.triggered.connect(self._delete_selected)
        tb.addAction(self.act_delete)

        self.act_up = QAction("↑", self)
        self.act_up.triggered.connect(lambda: self._move_selected(-1))
        tb.addAction(self.act_up)

        self.act_down = QAction("↓", self)
        self.act_down.triggered.connect(lambda: self._move_selected(1))
        tb.addAction(self.act_down)

        tb.addSeparator()

        self.act_reload = QAction("再読込", self)
        self.act_reload.setShortcut(QKeySequence.StandardKey.Refresh)
        self.act_reload.triggered.connect(self.reload)
        tb.addAction(self.act_reload)

    # ------------------------------------------------------------------
    # tree population
    # ------------------------------------------------------------------
    def reload(self, select: NodeRef | None = None) -> None:
        select = select or self._current_ref()
        self.tree.blockSignals(True)
        self.tree.clear()
        trees = self.db.load_all_trees(include_archived=True)
        for tree in trees:
            self._add_project_item(tree)
        self.tree.expandAll()
        self.tree.blockSignals(False)

        if select is not None:
            self._select_ref(select)
        else:
            self.detail.show_node(None)

    def _add_project_item(self, tree) -> None:
        p = tree.project
        item = QTreeWidgetItem(
            [
                f"📁 {p.name}",
                p.status,
                _format_date(p.deadline),
                "",
                _format_planned(p.planned_hours),
            ]
        )
        _set_node_ref(item, NodeRef("project", p.id))
        self.tree.addTopLevelItem(item)
        for pwt in tree.phases:
            self._add_phase_item(item, pwt)

    def _add_phase_item(self, parent: QTreeWidgetItem, pwt) -> None:
        ph = pwt.phase
        item = QTreeWidgetItem(
            [
                f"📂 {ph.name}",
                ph.status,
                _format_date(ph.deadline),
                "",
                _format_planned(ph.planned_hours),
            ]
        )
        _set_node_ref(item, NodeRef("phase", ph.id))
        parent.addChild(item)
        for t in pwt.tasks:
            self._add_task_item(item, t)

    def _add_task_item(self, parent: QTreeWidgetItem, t: Task) -> None:
        priority_icon = {"high": "🔴", "normal": "🟡", "low": "⚪"}.get(t.priority, "")
        item = QTreeWidgetItem(
            [
                f"  • {t.name}",
                t.status,
                _format_date(t.deadline),
                priority_icon,
                _format_planned(t.planned_hours),
            ]
        )
        _set_node_ref(item, NodeRef("task", t.id))
        parent.addChild(item)

    # ------------------------------------------------------------------
    # selection helpers
    # ------------------------------------------------------------------
    def _current_item(self) -> QTreeWidgetItem | None:
        items = self.tree.selectedItems()
        return items[0] if items else None

    def _current_ref(self) -> NodeRef | None:
        item = self._current_item()
        return _node_ref(item) if item else None

    def _select_ref(self, ref: NodeRef) -> None:
        def visit(item: QTreeWidgetItem) -> bool:
            if _node_ref(item) == ref:
                self.tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if visit(item.child(i)):
                    return True
            return False

        for i in range(self.tree.topLevelItemCount()):
            if visit(self.tree.topLevelItem(i)):
                return

    def _on_selection_changed(self) -> None:
        self.detail.show_node(self._current_ref())

    def _on_detail_saved(self) -> None:
        ref = self._current_ref()
        self.reload(select=ref)
        self.statusBar().showMessage("保存しました", 2000)

    # ------------------------------------------------------------------
    # add / delete / move
    # ------------------------------------------------------------------
    def _add_project(self) -> None:
        name, ok = QInputDialog.getText(self, "プロジェクト追加", "名前:")
        if not ok or not name.strip():
            return
        p = self.db.create_project(Project(name=name.strip()))
        self.reload(select=NodeRef("project", p.id))

    def _add_phase(self) -> None:
        ref = self._current_ref()
        project_id = self._project_id_for(ref)
        if project_id is None:
            QMessageBox.information(self, "選択してください", "プロジェクトを選択してください")
            return
        name, ok = QInputDialog.getText(self, "フェーズ追加", "名前:")
        if not ok or not name.strip():
            return
        existing = self.db.list_phases(project_id)
        order = (max((p.order_index for p in existing), default=-1)) + 1
        ph = self.db.create_phase(
            Phase(
                project_id=project_id,
                name=name.strip(),
                deadline=date.today(),
                order_index=order,
            )
        )
        self.reload(select=NodeRef("phase", ph.id))

    def _add_task(self) -> None:
        ref = self._current_ref()
        phase_id = self._phase_id_for(ref)
        if phase_id is None:
            QMessageBox.information(self, "選択してください", "フェーズかその配下のタスクを選択してください")
            return
        name, ok = QInputDialog.getText(self, "タスク追加", "名前:")
        if not ok or not name.strip():
            return
        existing = self.db.list_tasks(phase_id)
        order = (max((t.order_index for t in existing), default=-1)) + 1
        t = self.db.create_task(
            Task(phase_id=phase_id, name=name.strip(), order_index=order)
        )
        self.reload(select=NodeRef("task", t.id))

    def _delete_selected(self) -> None:
        ref = self._current_ref()
        if ref is None:
            return
        msg = {
            "project": "このプロジェクトを削除します(配下のフェーズ・タスクも消えます)。よろしいですか？",
            "phase": "このフェーズを削除します(配下のタスクも消えます)。よろしいですか？",
            "task": "このタスクを削除します。よろしいですか？",
        }[ref.kind]
        reply = QMessageBox.question(self, "削除確認", msg)
        if reply != QMessageBox.StandardButton.Yes:
            return
        if ref.kind == "project":
            self.db.delete_project(ref.id)
        elif ref.kind == "phase":
            self.db.delete_phase(ref.id)
        else:
            self.db.delete_task(ref.id)
        self.reload()

    def _move_selected(self, delta: int) -> None:
        ref = self._current_ref()
        if ref is None or ref.kind == "project":
            return  # project ordering not supported in v0.1
        if ref.kind == "phase":
            ph = self.db.get_phase(ref.id)
            siblings = self.db.list_phases(ph.project_id)
            self._swap_order(siblings, ph.id, delta, self.db.update_phase)
        else:
            t = self.db.get_task(ref.id)
            siblings = self.db.list_tasks(t.phase_id)
            self._swap_order(siblings, t.id, delta, self.db.update_task)
        self.reload(select=ref)

    @staticmethod
    def _swap_order(siblings, target_id: int, delta: int, update_fn) -> None:
        idx = next((i for i, s in enumerate(siblings) if s.id == target_id), -1)
        new_idx = idx + delta
        if idx < 0 or new_idx < 0 or new_idx >= len(siblings):
            return
        a, b = siblings[idx], siblings[new_idx]
        update_fn(a.id, order_index=b.order_index)
        update_fn(b.id, order_index=a.order_index)

    # ------------------------------------------------------------------
    # parent resolution
    # ------------------------------------------------------------------
    def _project_id_for(self, ref: NodeRef | None) -> int | None:
        if ref is None:
            return None
        if ref.kind == "project":
            return ref.id
        if ref.kind == "phase":
            return self.db.get_phase(ref.id).project_id
        if ref.kind == "task":
            phase = self.db.get_phase(self.db.get_task(ref.id).phase_id)
            return phase.project_id
        return None

    def _phase_id_for(self, ref: NodeRef | None) -> int | None:
        if ref is None:
            return None
        if ref.kind == "phase":
            return ref.id
        if ref.kind == "task":
            return self.db.get_task(ref.id).phase_id
        return None

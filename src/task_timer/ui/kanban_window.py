"""カンバンボード：プロジェクト×フェーズ×タスクの一覧画面。"""
from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import Phase, Project, Task, TimeLog
from task_timer.ui.format_helpers import round_to_tshirt
from task_timer.ui.theme import (
    ACCENT,
    BG,
    BTN_DANGER,
    BTN_STYLE,
    TEXT,
    TOPBAR_BG,
)
from task_timer.ui.widgets.phase_column import PhaseColumn


class KanbanWindow(QMainWindow):
    def __init__(self, db: Database, initial_project_id: int | None = None) -> None:
        super().__init__()
        self.db = db
        self._project_id: int | None = None
        self._initial_project_id: int | None = initial_project_id
        self._hide_done: bool = False
        # スケジューリング時間：カンバンを開いている間を計測する
        self._opened_at: datetime = datetime.now()

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
        btn_add_proj.setStyleSheet(BTN_STYLE)
        btn_add_proj.clicked.connect(self._add_project)
        tl.addWidget(btn_add_proj)

        self._btn_del_proj = QPushButton("削除")
        self._btn_del_proj.setStyleSheet(BTN_DANGER)
        self._btn_del_proj.clicked.connect(self._delete_project)
        tl.addWidget(self._btn_del_proj)

        tl.addStretch()

        self.cb_hide_done = QCheckBox("完了を隠す")
        self.cb_hide_done.setStyleSheet(
            "QCheckBox { color: #94a3b8; background: transparent; }"
            "QCheckBox:hover { color: #f1f5f9; }"
        )
        self.cb_hide_done.toggled.connect(self._on_hide_done_toggled)
        tl.addWidget(self.cb_hide_done)

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
        # 起動時に呼び出し元から渡された project_id があればそれを選ぶ
        if self._initial_project_id is not None:
            idx = self.project_cmb.findData(self._initial_project_id)
            if idx >= 0:
                self.project_cmb.setCurrentIndex(idx)
            self._initial_project_id = None  # 次回 _load_projects で再適用しない
        self.project_cmb.blockSignals(False)
        self._on_project_changed()

    def _on_project_changed(self) -> None:
        self._project_id = self.project_cmb.currentData()
        # システムプロジェクトは削除させない
        is_system = self._project_id is not None and self.db.is_system_project(self._project_id)
        self._btn_del_proj.setEnabled(not is_system)
        self._reload_board()

    def _on_hide_done_toggled(self, checked: bool) -> None:
        self._hide_done = checked
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
                for idx, pwt in enumerate(proj_tree.phases):
                    all_tasks = pwt.tasks
                    total = len(all_tasks)
                    done  = sum(1 for t in all_tasks if t.status == "done")
                    visible = (
                        [t for t in all_tasks if t.status != "done"]
                        if self._hide_done else all_tasks
                    )
                    sorted_tasks = sorted(
                        visible,
                        key=lambda t: (t.status == "done", t.order_index, t.id),
                    )
                    col = PhaseColumn(
                        self.db,
                        pwt.phase,
                        sorted_tasks,
                        total_count=total,
                        done_count=done,
                        index=idx,
                    )
                    col.task_added.connect(self._on_task_added)
                    col.task_deleted.connect(self._on_task_deleted)
                    col.task_status_changed.connect(self._on_task_status_changed)
                    col.task_dropped.connect(self._on_task_dropped)
                    col.task_split_requested.connect(self._on_task_split)
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

    def _schedule_reload(self) -> None:
        """シグナルから直接 _reload_board を呼ぶと、emit中のウィジェットが
        破棄されてクラッシュする。次のイベントループに遅延させる。"""
        QTimer.singleShot(0, self._reload_board)

    def _auto_estimate_hours(self) -> float | None:
        """同プロジェクトの完了タスク中央値を Tシャツ丸めで返す。データなしならNone。"""
        if self._project_id is None:
            return None
        median_sec = self.db.median_actual_seconds_for_project(self._project_id)
        if median_sec is None:
            return None
        return round_to_tshirt(median_sec / 3600)

    def _on_task_added(self, phase_id: int, name: str) -> None:
        existing = self.db.list_tasks(phase_id)
        order = (max((t.order_index for t in existing), default=-1)) + 1
        phase = self.db.get_phase(phase_id)
        recurrence = "daily" if phase.is_routine else None
        self.db.create_task(Task(
            phase_id=phase_id,
            name=name,
            order_index=order,
            planned_hours=self._auto_estimate_hours(),
            recurrence=recurrence,
        ))
        self._schedule_reload()

    def _on_task_deleted(self, task_id: int) -> None:
        reply = QMessageBox.question(self, "削除確認", "このタスクを削除しますか？")
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_task(task_id)
            self._schedule_reload()

    def _on_task_status_changed(self, task_id: int, is_done: bool) -> None:
        # 完了にしたら：末尾移動＋繰り返しならクローン作成（共通ロジック）
        if is_done:
            self.db.complete_task(task_id)
        self._schedule_reload()

    def _on_task_dropped(self, task_id: int, target_phase_id: int, insert_index: int) -> None:
        # 表示順（未完了→完了）に揃えてから order_index を振り直す
        target_tasks = [t for t in self.db.list_tasks(target_phase_id) if t.id != task_id]
        target_tasks.sort(key=lambda t: (t.status == "done", t.order_index, t.id))
        insert_index = max(0, min(insert_index, len(target_tasks)))
        for i, t in enumerate(target_tasks):
            new_order = i if i < insert_index else i + 1
            if t.order_index != new_order:
                self.db.update_task(t.id, order_index=new_order)
        self.db.update_task(task_id, phase_id=target_phase_id, order_index=insert_index)
        self._schedule_reload()

    def _on_task_split(self, task_id: int) -> None:
        parent = self.db.get_task(task_id)
        text, ok = QInputDialog.getMultiLineText(
            self,
            "タスクを分解",
            f"「{parent.name}」を細かいタスクに分解\n（1行 = 1タスク）",
            "",
        )
        if not ok:
            return
        names = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not names:
            return

        # 親の位置に新タスクをN個入れて、親は消す
        siblings = self.db.list_tasks(parent.phase_id)
        n = len(names)
        planned = self._auto_estimate_hours()
        for s in siblings:
            if s.id != parent.id and s.order_index > parent.order_index:
                self.db.update_task(s.id, order_index=s.order_index + n - 1)
        for i, name in enumerate(names):
            self.db.create_task(Task(
                phase_id=parent.phase_id,
                name=name,
                order_index=parent.order_index + i,
                planned_hours=planned,
            ))
        self.db.delete_task(parent.id)
        self._schedule_reload()

    def _on_phase_deleted(self, phase_id: int) -> None:
        reply = QMessageBox.question(
            self, "削除確認", "このフェーズを削除しますか？\n（タスクもすべて削除されます）"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_phase(phase_id)
            self._schedule_reload()

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

    # ── close hook：開いていた時間をスケジューリングに記録 ───────────────────

    def closeEvent(self, event) -> None:
        sched_id = self.db.system_ids.get("scheduling_task_id")
        ended_at = datetime.now()
        duration = int((ended_at - self._opened_at).total_seconds())
        # 一瞬だけ開いて閉じた事故を弾く（5秒未満は記録しない）
        if sched_id is not None and duration >= 5:
            self.db.create_time_log(TimeLog(
                task_id=sched_id,
                started_at=self._opened_at,
                ended_at=ended_at,
                duration_sec=duration,
            ))
        super().closeEvent(event)

    def _add_phase(self) -> None:
        if self._project_id is None:
            return
        dlg = _PhaseAddDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.name()
        if not name:
            return
        existing = self.db.list_phases(self._project_id)
        order = (max((ph.order_index for ph in existing), default=-1)) + 1
        self.db.create_phase(Phase(
            project_id=self._project_id,
            name=name,
            deadline=date.today(),
            order_index=order,
            is_routine=dlg.is_routine(),
        ))
        self._reload_board()


class _PhaseAddDialog(QDialog):
    """名前入力＋ルーティンチェックの小ダイアログ。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("フェーズを追加")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(QLabel("名前"))
        self._name = QLineEdit()
        layout.addWidget(self._name)
        self._cb = QCheckBox("ルーティンフェーズにする（タスクを繰り返し設定可能）")
        layout.addWidget(self._cb)

        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        self._name.setFocus()

    def name(self) -> str:
        return self._name.text().strip()

    def is_routine(self) -> bool:
        return self._cb.isChecked()

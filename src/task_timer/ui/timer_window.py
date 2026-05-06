from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import TimeLog


PHASE_COLORS = [
    "#3498db",  # blue
    "#e67e22",  # orange
    "#9b59b6",  # purple
    "#1abc9c",  # teal
    "#e74c3c",  # red
    "#f39c12",  # amber
]


class TimerWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._manager_window = None

        self._started_at: datetime | None = None
        self._elapsed_sec: int = 0
        self._running: bool = False

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        # 累計表示の状態
        self._show_totals: bool = False
        self._total_unit_hours: bool = True  # True=時間, False=人工(8h/日)

        self.setWindowTitle("task-timer")
        self.setFixedSize(380, 560)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._build_ui()
        self._load_projects()

    # ──────────────────────────────── UI構築

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # プロジェクト・タスク（2段）
        self._cmb_project = QComboBox()
        self._cmb_task = QComboBox()
        for cmb in [self._cmb_project, self._cmb_task]:
            cmb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(cmb)

        self._cmb_project.currentIndexChanged.connect(self._on_project_changed)
        self._cmb_task.currentIndexChanged.connect(self._update_start_button)

        # 時計表示
        self._lbl_time = QLabel("00:00:00")
        font = QFont()
        font.setPointSize(48)
        font.setFamily("Courier New")
        self._lbl_time.setFont(font)
        self._lbl_time.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_time, stretch=1)

        # 状態ラベル
        self._lbl_status = QLabel("停止中")
        self._lbl_status.setAlignment(Qt.AlignCenter)
        self._lbl_status.setStyleSheet("color: gray; font-size: 13px;")
        layout.addWidget(self._lbl_status)

        # コントロールボタン
        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("▶  スタート")
        self._btn_stop  = QPushButton("⏹  ストップ")
        self._btn_start.setFixedHeight(44)
        self._btn_stop.setFixedHeight(44)
        self._btn_stop.setEnabled(False)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_stop)
        layout.addLayout(btn_row)

        # 累計表示トグル + 単位切替
        totals_btn_row = QHBoxLayout()
        self._btn_toggle_totals = QPushButton("📊 累計を表示")
        self._btn_toggle_totals.setCheckable(True)
        self._btn_toggle_totals.setFixedHeight(28)
        self._btn_toggle_totals.toggled.connect(self._on_toggle_totals)
        self._btn_toggle_unit = QPushButton("人工で表示")
        self._btn_toggle_unit.setCheckable(True)
        self._btn_toggle_unit.setFixedHeight(28)
        self._btn_toggle_unit.toggled.connect(self._on_toggle_unit)
        totals_btn_row.addWidget(self._btn_toggle_totals)
        totals_btn_row.addWidget(self._btn_toggle_unit)
        layout.addLayout(totals_btn_row)

        # 累計パネル（折りたたみ可）
        self._totals_panel = QWidget()
        tp = QVBoxLayout(self._totals_panel)
        tp.setContentsMargins(0, 0, 0, 0)
        tp.setSpacing(2)
        self._lbl_total_proj  = QLabel("プロジェクト: -")
        self._lbl_total_phase = QLabel("フェーズ: -")
        for lbl in (self._lbl_total_proj, self._lbl_total_phase):
            lbl.setStyleSheet("color: gray; font-size: 12px;")
            lbl.setAlignment(Qt.AlignCenter)
            tp.addWidget(lbl)
        self._totals_panel.setVisible(False)
        layout.addWidget(self._totals_panel)

        # タスク完了ボタン
        self._btn_done = QPushButton("✓  このタスクを完了")
        self._btn_done.setFixedHeight(36)
        self._btn_done.clicked.connect(self._on_complete_task)
        layout.addWidget(self._btn_done)

        # 管理画面ボタン
        self._btn_manager = QPushButton("管理画面を開く")
        self._btn_manager.setFixedHeight(36)
        self._btn_manager.clicked.connect(self._open_manager)
        layout.addWidget(self._btn_manager)

    # ──────────────────────────────── データ読み込み

    def _load_projects(self) -> None:
        self._cmb_project.blockSignals(True)
        self._cmb_project.clear()
        for p in self.db.list_projects():
            self._cmb_project.addItem(p.name, userData=p.id)
        self._cmb_project.blockSignals(False)
        self._on_project_changed()

    def _on_project_changed(self) -> None:
        project_id = self._cmb_project.currentData()
        self._reload_tasks(project_id)

    def _reload_tasks(self, project_id: int | None) -> None:
        """タスクドロップダウンをフェーズごとにグループ化して構築する。"""
        self._cmb_task.blockSignals(True)
        model = QStandardItemModel(self._cmb_task)
        first_task_row: int | None = None

        if project_id is not None:
            phases = self.db.list_phases(project_id)
            for p_idx, phase in enumerate(phases):
                tasks = [t for t in self.db.list_tasks(phase.id) if t.status != "done"]
                if not tasks:
                    continue

                color = QColor(PHASE_COLORS[p_idx % len(PHASE_COLORS)])

                # フェーズヘッダー（選択不可）
                header = QStandardItem(f"── {phase.name} ──")
                header.setSelectable(False)
                header.setEnabled(False)
                hf = header.font()
                hf.setBold(True)
                header.setFont(hf)
                header.setForeground(QBrush(color))
                model.appendRow(header)

                # タスク（フェーズの色を前景色に）
                for t in tasks:
                    item = QStandardItem(f"   {t.name}")
                    item.setData(t.id, Qt.UserRole)
                    item.setForeground(QBrush(color))
                    model.appendRow(item)
                    if first_task_row is None:
                        first_task_row = model.rowCount() - 1

        self._cmb_task.setModel(model)
        if first_task_row is not None:
            self._cmb_task.setCurrentIndex(first_task_row)
        else:
            self._cmb_task.setCurrentIndex(-1)
        self._cmb_task.blockSignals(False)
        self._update_start_button()

    def _current_task_id(self) -> int | None:
        idx = self._cmb_task.currentIndex()
        if idx < 0:
            return None
        data = self._cmb_task.itemData(idx, Qt.UserRole)
        return data if isinstance(data, int) else None

    def _update_start_button(self) -> None:
        has_task = self._current_task_id() is not None
        self._btn_start.setEnabled(has_task and not self._running)
        self._btn_done.setEnabled(has_task and not self._running)
        self._refresh_totals()

    # ──────────────────────────────── タイマー操作

    def _on_start(self) -> None:
        task_id = self._current_task_id()
        if task_id is None:
            return
        self._started_at = datetime.now()
        self._elapsed_sec = 0
        self._running = True
        self._tick_timer.start()
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_done.setEnabled(False)
        self._cmb_project.setEnabled(False)
        self._cmb_task.setEnabled(False)
        self._lbl_status.setText("計測中…")
        self._lbl_status.setStyleSheet("color: #2ecc71; font-size: 13px;")

    def _on_stop(self) -> None:
        if not self._running or self._started_at is None:
            return
        self._tick_timer.stop()
        self._running = False
        ended_at = datetime.now()
        duration = int((ended_at - self._started_at).total_seconds())

        task_id = self._current_task_id()
        log = TimeLog(
            task_id=task_id,
            started_at=self._started_at,
            ended_at=ended_at,
            duration_sec=duration,
        )
        self.db.create_time_log(log)

        # ③ カンバンが開いていれば自動更新
        if self._manager_window is not None and self._manager_window.isVisible():
            self._manager_window._reload_board()

        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_done.setEnabled(self._current_task_id() is not None)
        self._cmb_project.setEnabled(True)
        self._cmb_task.setEnabled(True)
        self._lbl_status.setText(f"保存しました（{self._fmt(duration)}）")
        self._lbl_status.setStyleSheet("color: gray; font-size: 13px;")
        self._elapsed_sec = 0
        self._lbl_time.setText("00:00:00")
        self._refresh_totals()

    def _on_tick(self) -> None:
        self._elapsed_sec += 1
        self._lbl_time.setText(self._fmt(self._elapsed_sec))

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ──────────────────────────────── 累計表示

    def _on_toggle_totals(self, checked: bool) -> None:
        self._show_totals = checked
        self._totals_panel.setVisible(checked)
        self._btn_toggle_totals.setText("📊 累計を隠す" if checked else "📊 累計を表示")
        if checked:
            self._refresh_totals()

    def _on_toggle_unit(self, checked: bool) -> None:
        # checked=人工モード、未チェック=時間モード
        self._total_unit_hours = not checked
        self._btn_toggle_unit.setText("時間で表示" if checked else "人工で表示")
        self._refresh_totals()

    def _refresh_totals(self) -> None:
        if not self._show_totals:
            return
        task_id = self._current_task_id()
        if task_id is None:
            self._lbl_total_proj.setText("プロジェクト: -")
            self._lbl_total_phase.setText("フェーズ: -")
            return
        task = self.db.get_task(task_id)
        phase = self.db.get_phase(task.phase_id)
        proj_sec  = self.db.total_seconds_for_project(phase.project_id)
        phase_sec = self.db.total_seconds_for_phase(task.phase_id)
        self._lbl_total_proj.setText(f"プロジェクト: {self._fmt_total(proj_sec)}")
        self._lbl_total_phase.setText(f"フェーズ: {self._fmt_total(phase_sec)}")

    def _fmt_total(self, sec: int) -> str:
        if self._total_unit_hours:
            h, rem = divmod(sec, 3600)
            m, _ = divmod(rem, 60)
            return f"{h}h {m:02d}m"
        # 1人工 = 8時間
        days = sec / 3600 / 8
        return f"{days:.2f}人工"

    # ──────────────────────────────── タスク完了

    def _on_complete_task(self) -> None:
        if self._running:
            return
        task_id = self._current_task_id()
        if task_id is None:
            return
        task = self.db.get_task(task_id)
        reply = QMessageBox.question(
            self,
            "タスクを完了",
            f"「{task.name}」を完了にしますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        self.db.update_task(task_id, status="done")
        self._lbl_status.setText(f"完了：{task.name}")
        self._lbl_status.setStyleSheet("color: gray; font-size: 13px;")

        # ドロップダウンから除外（再構築）
        self._reload_tasks(self._cmb_project.currentData())
        self._refresh_totals()

        # カンバンが開いていれば自動更新
        if self._manager_window is not None and self._manager_window.isVisible():
            self._manager_window._reload_board()

    # ──────────────────────────────── 管理画面

    def _open_manager(self) -> None:
        from task_timer.ui.kanban_window import KanbanWindow
        if self._manager_window is None or not self._manager_window.isVisible():
            self._manager_window = KanbanWindow(self.db)
            self._manager_window.show()
        else:
            self._manager_window.raise_()
            self._manager_window.activateWindow()

    # ──────────────────────────────── 終了ガード

    def closeEvent(self, event) -> None:
        if self._running:
            reply = QMessageBox.question(
                self,
                "計測中",
                "計測中です。終了しますか？\n（ログは保存されません）",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        event.accept()

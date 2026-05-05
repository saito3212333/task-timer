from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
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

        self.setWindowTitle("task-timer")
        self.setFixedSize(380, 480)
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

        # ドロップダウン
        self._cmb_project = QComboBox()
        self._cmb_phase = QComboBox()
        self._cmb_task = QComboBox()
        for cmb in [self._cmb_project, self._cmb_phase, self._cmb_task]:
            cmb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(cmb)

        self._cmb_project.currentIndexChanged.connect(self._on_project_changed)
        self._cmb_phase.currentIndexChanged.connect(self._on_phase_changed)
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
        self._cmb_phase.blockSignals(True)
        self._cmb_phase.clear()
        if project_id is not None:
            for ph in self.db.list_phases(project_id):
                self._cmb_phase.addItem(ph.name, userData=ph.id)
        self._cmb_phase.blockSignals(False)
        self._on_phase_changed()

    def _on_phase_changed(self) -> None:
        phase_id = self._cmb_phase.currentData()
        self._cmb_task.clear()
        if phase_id is not None:
            for t in self.db.list_tasks(phase_id):
                if t.status != "done":
                    self._cmb_task.addItem(t.name, userData=t.id)
        self._update_start_button()

    def _update_start_button(self) -> None:
        has_task = self._cmb_task.currentData() is not None
        self._btn_start.setEnabled(has_task and not self._running)

    # ──────────────────────────────── タイマー操作

    def _on_start(self) -> None:
        task_id = self._cmb_task.currentData()
        if task_id is None:
            return
        self._started_at = datetime.now()
        self._elapsed_sec = 0
        self._running = True
        self._tick_timer.start()
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._cmb_project.setEnabled(False)
        self._cmb_phase.setEnabled(False)
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

        task_id = self._cmb_task.currentData()
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
        self._cmb_project.setEnabled(True)
        self._cmb_phase.setEnabled(True)
        self._cmb_task.setEnabled(True)
        self._lbl_status.setText(f"保存しました（{self._fmt(duration)}）")
        self._lbl_status.setStyleSheet("color: gray; font-size: 13px;")
        self._elapsed_sec = 0
        self._lbl_time.setText("00:00:00")

    def _on_tick(self) -> None:
        self._elapsed_sec += 1
        self._lbl_time.setText(self._fmt(self._elapsed_sec))

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

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

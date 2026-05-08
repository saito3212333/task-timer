from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from task_timer.db import Database
from task_timer.models import TimeLog
from task_timer.ui.format_helpers import fmt_planned
from task_timer.ui.theme import (
    ACCENT,
    BTN_START_STYLE,
    BTN_STOP_STYLE,
    GREEN,
    LINK_STYLE,
    MUTED,
    TEXT,
)


# タイマー画面のタスクDDで使うフェーズ色（既存パレットとは別系統で読みやすい色）
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
        self._last_log_id: int | None = None

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        self.setWindowTitle("task-timer")
        self.setMinimumWidth(280)
        self.setMinimumHeight(360)
        self.resize(self.minimumWidth(), self.minimumHeight())

        self._build_ui()
        self._load_projects()

    # ──────────────────────────────── UI構築

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 上部セレクタ：通常はDDs2段／集中モードはタスク名（QStackedWidgetで同位置に切替）
        self._cmb_project = QComboBox()
        self._cmb_task = QComboBox()
        for cmb in [self._cmb_project, self._cmb_task]:
            cmb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        page_dd = QWidget()
        pl = QVBoxLayout(page_dd)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(2)
        pl.addWidget(self._cmb_project)
        pl.addWidget(self._cmb_task)

        page_name = QWidget()
        pn = QVBoxLayout(page_name)
        pn.setContentsMargins(0, 0, 0, 0)
        self._lbl_task_name = QLabel("")
        self._lbl_task_name.setAlignment(Qt.AlignCenter)
        self._lbl_task_name.setStyleSheet(
            "font-size: 16px; font-weight: 600; padding: 4px;"
        )
        pn.addStretch()
        pn.addWidget(self._lbl_task_name)
        pn.addStretch()

        self._top_stack = QStackedWidget()
        self._top_stack.addWidget(page_dd)    # index 0
        self._top_stack.addWidget(page_name)  # index 1
        self._top_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self._top_stack)

        self._cmb_project.currentIndexChanged.connect(self._on_project_changed)
        self._cmb_task.currentIndexChanged.connect(self._update_controls)

        # タイマー表示（停止＝グレー、計測中＝緑）
        self._lbl_time = QLabel("00:00:00")
        font = QFont()
        font.setPointSize(40)
        font.setFamily("Courier New")
        self._lbl_time.setFont(font)
        self._lbl_time.setAlignment(Qt.AlignCenter)
        self._lbl_time.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(self._lbl_time, stretch=1)

        # 見積もり（タスク選択時のみ表示・薄字）
        self._lbl_estimate = QLabel("")
        self._lbl_estimate.setAlignment(Qt.AlignCenter)
        self._lbl_estimate.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        layout.addWidget(self._lbl_estimate)

        # メモ入力（ストップ時に表示・空でEnterするとスキップ）
        self._memo_edit = QLineEdit()
        self._memo_edit.setPlaceholderText("メモを残す（Enterで保存・Escでスキップ）")
        self._memo_edit.setStyleSheet(
            f"QLineEdit {{ color: {TEXT}; background: white;"
            f" border: 1px solid {ACCENT}; border-radius: 4px;"
            f" padding: 4px 8px; font-size: 12px; }}"
        )
        self._memo_edit.returnPressed.connect(self._commit_memo)
        self._memo_edit.installEventFilter(self)
        self._memo_edit.setVisible(False)
        layout.addWidget(self._memo_edit)

        # スタート⇄ストップ統合ボタン（中央寄せの小さめボタン）
        self._btn_play = QPushButton("▶  スタート")
        self._btn_play.setFixedSize(180, 34)
        self._btn_play.setStyleSheet(BTN_START_STYLE)
        self._btn_play.clicked.connect(self._on_play_toggle)
        play_row = QHBoxLayout()
        play_row.addStretch()
        play_row.addWidget(self._btn_play)
        play_row.addStretch()
        layout.addLayout(play_row)

        # 完了リンク（中央寄せ・薄字）
        self._done_widget = QWidget()
        done_row = QHBoxLayout(self._done_widget)
        done_row.setContentsMargins(0, 0, 0, 0)
        done_row.addStretch()
        self._btn_done = QPushButton("✓ このタスクを完了")
        self._btn_done.setFlat(True)
        self._btn_done.setStyleSheet(LINK_STYLE)
        self._btn_done.clicked.connect(self._on_complete_task)
        done_row.addWidget(self._btn_done)
        done_row.addStretch()
        layout.addWidget(self._done_widget)

        # 下段：管理画面 · 累計（中央寄せのテキストリンク）
        self._bottom_widget = QWidget()
        bottom_row = QHBoxLayout(self._bottom_widget)
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(0)
        bottom_row.addStretch()
        self._btn_manager = QPushButton("管理画面")
        self._btn_manager.setFlat(True)
        self._btn_manager.setStyleSheet(LINK_STYLE)
        self._btn_manager.clicked.connect(self._open_manager)
        bottom_row.addWidget(self._btn_manager)

        dot = QLabel("·")
        dot.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        bottom_row.addWidget(dot)

        self._btn_totals = QPushButton("累計")
        self._btn_totals.setFlat(True)
        self._btn_totals.setStyleSheet(LINK_STYLE)
        self._btn_totals.clicked.connect(self._open_totals_dialog)
        bottom_row.addWidget(self._btn_totals)
        bottom_row.addStretch()
        layout.addWidget(self._bottom_widget)

    # ──────────────────────────────── データ読み込み

    def _load_projects(self) -> None:
        self._cmb_project.blockSignals(True)
        self._cmb_project.clear()
        for p in self.db.list_projects():
            self._cmb_project.addItem(p.name, userData=p.id)
        self._cmb_project.blockSignals(False)
        self._on_project_changed()

    def _refresh_from_db(self) -> None:
        """管理画面から戻ってきたとき、選択を保ったままDBを読み直す。"""
        if self._running:
            return
        cur_proj_id = self._cmb_project.currentData()
        cur_task_id = self._current_task_id()

        self._cmb_project.blockSignals(True)
        self._cmb_project.clear()
        for p in self.db.list_projects():
            self._cmb_project.addItem(p.name, userData=p.id)
        idx = self._cmb_project.findData(cur_proj_id) if cur_proj_id is not None else -1
        if idx >= 0:
            self._cmb_project.setCurrentIndex(idx)
        self._cmb_project.blockSignals(False)

        self._reload_tasks(self._cmb_project.currentData(), preferred_task_id=cur_task_id)

    def event(self, ev) -> bool:
        if ev.type() == QEvent.WindowActivate:
            self._refresh_from_db()
        return super().event(ev)

    def eventFilter(self, obj, ev) -> bool:
        if obj is self._memo_edit and ev.type() == QEvent.Type.KeyPress:
            assert isinstance(ev, QKeyEvent)
            if ev.key() == Qt.Key_Escape:
                self._dismiss_memo()
                return True
        return super().eventFilter(obj, ev)

    def _on_project_changed(self) -> None:
        project_id = self._cmb_project.currentData()
        self._reload_tasks(project_id)

    def _reload_tasks(self, project_id: int | None, preferred_task_id: int | None = None) -> None:
        """タスクドロップダウンをフェーズごとにグループ化して構築する。"""
        self._cmb_task.blockSignals(True)
        model = QStandardItemModel(self._cmb_task)
        first_task_row: int | None = None
        preferred_row: int | None = None

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
                    row = model.rowCount() - 1
                    if first_task_row is None:
                        first_task_row = row
                    if preferred_task_id is not None and t.id == preferred_task_id:
                        preferred_row = row

        self._cmb_task.setModel(model)
        target = preferred_row if preferred_row is not None else first_task_row
        self._cmb_task.setCurrentIndex(target if target is not None else -1)
        self._cmb_task.blockSignals(False)
        self._update_controls()

    def _find_next_task_id(self) -> int | None:
        """現在の選択より下にある最初のタスクID（次へ進む先）。なければNone。"""
        model = self._cmb_task.model()
        if not isinstance(model, QStandardItemModel):
            return None
        cur = self._cmb_task.currentIndex()
        for row in range(cur + 1, model.rowCount()):
            item = model.item(row)
            if item is None:
                continue
            data = item.data(Qt.UserRole)
            if isinstance(data, int):
                return data
        return None

    def _current_task_id(self) -> int | None:
        idx = self._cmb_task.currentIndex()
        if idx < 0:
            return None
        data = self._cmb_task.itemData(idx, Qt.UserRole)
        return data if isinstance(data, int) else None

    def _update_controls(self) -> None:
        has_task = self._current_task_id() is not None
        if self._running:
            self._btn_play.setText("⏹  ストップ")
            self._btn_play.setStyleSheet(BTN_STOP_STYLE)
            self._btn_play.setEnabled(True)
            self._btn_done.setEnabled(False)
        else:
            self._btn_play.setText("▶  スタート")
            self._btn_play.setStyleSheet(BTN_START_STYLE)
            self._btn_play.setEnabled(has_task)
            self._btn_done.setEnabled(has_task)
        self._refresh_estimate()

    def _refresh_estimate(self) -> None:
        task_id = self._current_task_id()
        if task_id is None:
            self._lbl_estimate.setText("")
            return
        task = self.db.get_task(task_id)
        if task.planned_hours:
            self._lbl_estimate.setText(f"見積 ~{fmt_planned(task.planned_hours)}")
        else:
            self._lbl_estimate.setText("")

    # ──────────────────────────────── タイマー操作

    def _on_play_toggle(self) -> None:
        if self._running:
            self._on_stop()
        else:
            self._on_start()

    def _on_start(self) -> None:
        task_id = self._current_task_id()
        if task_id is None:
            return
        # 前回ストップ時に出ていたメモ入力欄が残っていれば閉じる
        if self._memo_edit.isVisible():
            self._dismiss_memo()
        self._started_at = datetime.now()
        self._elapsed_sec = 0
        self._running = True
        self._tick_timer.start()
        self._lbl_time.setText("00:00:00")
        self._lbl_time.setStyleSheet(f"color: {GREEN};")
        self._enter_focus_mode()
        self._update_controls()

    def _enter_focus_mode(self) -> None:
        """計測中：タスク名・タイマー・ストップボタンだけ残し、他は不可視
        （opacity 0 で場所は確保したまま）。"""
        task = self.db.get_task(self._current_task_id())
        self._lbl_task_name.setText(task.name)
        self._top_stack.setCurrentIndex(1)

        for w in self._focus_hidden_widgets():
            self._set_opacity(w, 0.0)
            w.setEnabled(False)

    def _exit_focus_mode(self) -> None:
        """通常表示に戻す。"""
        self._top_stack.setCurrentIndex(0)
        for w in self._focus_hidden_widgets():
            self._set_opacity(w, 1.0)
            w.setEnabled(True)

    def _focus_hidden_widgets(self) -> list[QWidget]:
        # _lbl_estimate と _done_widget と _bottom_widget は集中モード中も layout 上は残す
        return [self._lbl_estimate, self._done_widget, self._bottom_widget]

    @staticmethod
    def _set_opacity(widget: QWidget, value: float) -> None:
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(value)
        widget.setGraphicsEffect(eff)

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
        saved = self.db.create_time_log(log)
        self._last_log_id = saved.id

        # カンバンが開いていれば自動更新
        if self._manager_window is not None and self._manager_window.isVisible():
            self._manager_window._reload_board()

        self._exit_focus_mode()
        self._update_controls()

        # 保存フィードバック：タイマー位置に「✓ 1h23m」を一瞬表示
        self._lbl_time.setText(f"✓ {self._fmt(duration)}")
        self._lbl_time.setStyleSheet(f"color: {GREEN};")
        QTimer.singleShot(1800, self._reset_timer_display)

        # メモ入力を表示（見積ラベルは一時的に隠す）
        self._lbl_estimate.setVisible(False)
        self._memo_edit.clear()
        self._memo_edit.setVisible(True)
        self._memo_edit.setFocus()

    def _commit_memo(self) -> None:
        text = self._memo_edit.text().strip()
        if text and self._last_log_id is not None:
            self.db.update_time_log(self._last_log_id, note=text)
            # 保存フィードバック
            self._lbl_time.setText("✓ メモ保存")
            self._lbl_time.setStyleSheet(f"color: {GREEN};")
            QTimer.singleShot(1200, self._reset_timer_display)
            # カンバンのバッジ件数を更新
            if self._manager_window is not None and self._manager_window.isVisible():
                self._manager_window._reload_board()
        self._dismiss_memo()

    def _dismiss_memo(self) -> None:
        self._memo_edit.clear()
        self._memo_edit.setVisible(False)
        self._lbl_estimate.setVisible(True)
        self._last_log_id = None

    def _reset_timer_display(self) -> None:
        if self._running:
            return
        self._elapsed_sec = 0
        self._lbl_time.setText("00:00:00")
        self._lbl_time.setStyleSheet(f"color: {MUTED};")

    def _on_tick(self) -> None:
        self._elapsed_sec += 1
        self._lbl_time.setText(self._fmt(self._elapsed_sec))

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ──────────────────────────────── 累計ダイアログ

    def _open_totals_dialog(self) -> None:
        task_id = self._current_task_id()
        if task_id is None:
            return
        from task_timer.ui.widgets.totals_dialog import TotalsDialog
        TotalsDialog(self.db, task_id, self).exec()

    # ──────────────────────────────── タスク完了

    def _on_complete_task(self) -> None:
        if self._running:
            return
        task_id = self._current_task_id()
        if task_id is None:
            return

        # 次に選択するタスク（リロード前に決める）
        next_id = self._find_next_task_id()

        self.db.complete_task(task_id)

        # 完了フィードバック：タイマー位置に「✓ 完了」を一瞬表示
        self._lbl_time.setText("✓ 完了")
        self._lbl_time.setStyleSheet(f"color: {GREEN};")
        QTimer.singleShot(1200, self._reset_timer_display)

        # ドロップダウンから除外 → 次のタスクを自動選択
        self._reload_tasks(self._cmb_project.currentData(), preferred_task_id=next_id)
        self._refresh_totals()

        # カンバンが開いていれば自動更新
        if self._manager_window is not None and self._manager_window.isVisible():
            self._manager_window._reload_board()

    # ──────────────────────────────── 管理画面

    def _open_manager(self) -> None:
        from task_timer.ui.kanban_window import KanbanWindow
        if self._manager_window is None or not self._manager_window.isVisible():
            current_project_id = self._cmb_project.currentData()
            self._manager_window = KanbanWindow(
                self.db, initial_project_id=current_project_id
            )
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

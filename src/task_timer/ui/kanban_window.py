from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, QEvent, QMimeData, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
    QPixmap,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
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

# 各フェーズ列の薄い背景色（順に循環）
PHASE_COL_BGS = [
    "#eff6ff",  # sky
    "#fff7ed",  # orange
    "#faf5ff",  # purple
    "#ecfdf5",  # mint
    "#fef2f2",  # rose
    "#fefce8",  # cream
]

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
# Deadline helpers / dialog
# ---------------------------------------------------------------------------

def _preset_today() -> date:
    return date.today()

def _preset_tomorrow() -> date:
    return date.today() + timedelta(days=1)

def _preset_this_weekend() -> date:
    """今週土曜（土曜なら今日、日曜なら6日後）"""
    today = date.today()
    return today + timedelta(days=(5 - today.weekday()) % 7)

def _preset_next_monday() -> date:
    today = date.today()
    return today + timedelta(days=7 - today.weekday())


class WeekendCalendar(QCalendarWidget):
    """土曜=青・日曜=赤を、現在月外の日付にも適用するカレンダー。"""

    _COLOR_SAT = QColor("#2563eb")
    _COLOR_SUN = QColor("#dc2626")
    _COLOR_TEXT = QColor(TEXT)
    _COLOR_SEL_BG = QColor(ACCENT)
    _COLOR_SEL_FG = QColor("white")

    def paintCell(self, painter: QPainter, rect, qdate: QDate) -> None:  # type: ignore[override]
        is_selected = qdate == self.selectedDate()
        in_month    = qdate.month() == self.monthShown() and qdate.year() == self.yearShown()
        wd = qdate.dayOfWeek()  # Mon=1 ... Sun=7

        if is_selected:
            painter.fillRect(rect, self._COLOR_SEL_BG)
            color = QColor(self._COLOR_SEL_FG)
        else:
            if wd == 6:
                color = QColor(self._COLOR_SAT)
            elif wd == 7:
                color = QColor(self._COLOR_SUN)
            else:
                color = QColor(self._COLOR_TEXT)
            if not in_month:
                color.setAlpha(110)

        painter.save()
        painter.setPen(QPen(color))
        painter.drawText(rect, Qt.AlignCenter, str(qdate.day()))
        painter.restore()


class DeadlinePicker(QDialog):
    """プリセット4種＋カレンダーで締切を選ぶダイアログ。"""

    def __init__(self, current: date | None, allow_clear: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("締切を設定")
        self._result: date | None = current
        self._cleared: bool = False

        # 親のCSS継承を避け、明示的なライトテーマを当てる
        self.setStyleSheet(f"""
            QDialog {{ background: white; }}
            QLabel  {{ color: {TEXT}; background: transparent; }}
            QCalendarWidget QWidget {{ color: {TEXT}; }}
            QCalendarWidget QToolButton {{
                color: {TEXT}; background: white;
                font-size: 13px; padding: 4px;
            }}
            QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
            QCalendarWidget QSpinBox {{ color: {TEXT}; background: white; }}
            QCalendarWidget QAbstractItemView:enabled {{
                color: {TEXT}; background: white;
                selection-background-color: {ACCENT};
                selection-color: white;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        presets = QHBoxLayout()
        for label, fn in [
            ("今日", _preset_today),
            ("明日", _preset_tomorrow),
            ("今週末", _preset_this_weekend),
            ("来週月曜", _preset_next_monday),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(_BTN_STYLE)
            btn.clicked.connect(lambda _=False, f=fn: self._select(f()))
            presets.addWidget(btn)
        layout.addLayout(presets)

        self.cal = WeekendCalendar()
        self.cal.setGridVisible(True)
        # 左の週番号列を消す
        self.cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        # 曜日ヘッダーの土日色（セル中身は paintCell で着色）
        sat_fmt = QTextCharFormat()
        sat_fmt.setForeground(QColor("#2563eb"))
        self.cal.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, sat_fmt)
        sun_fmt = QTextCharFormat()
        sun_fmt.setForeground(QColor("#dc2626"))
        self.cal.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, sun_fmt)
        # 月/年ボタンの幅を絞ってナビゲーションの空白をなくす
        for name, w in [
            ("qt_calendar_monthbutton", 60),
            ("qt_calendar_yearbutton",  70),
        ]:
            btn = self.cal.findChild(QToolButton, name)
            if btn:
                btn.setMaximumWidth(w)
        if current:
            self.cal.setSelectedDate(QDate(current.year, current.month, current.day))
        self.cal.clicked.connect(lambda qd: self._select(qd.toPython()))
        layout.addWidget(self.cal)

        _NEUTRAL_BTN = f"""
            QPushButton {{
                background: #e2e8f0; color: {TEXT};
                border: 1px solid #cbd5e1; border-radius: 5px; padding: 5px 12px;
            }}
            QPushButton:hover {{ background: #cbd5e1; }}
        """
        bottom = QHBoxLayout()
        if allow_clear:
            btn_clear = QPushButton("クリア")
            btn_clear.setStyleSheet(_NEUTRAL_BTN)
            btn_clear.clicked.connect(self._on_clear)
            bottom.addWidget(btn_clear)
        bottom.addStretch()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.setStyleSheet(_NEUTRAL_BTN)
        btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(btn_cancel)
        btn_ok = QPushButton("OK")
        btn_ok.setStyleSheet(_BTN_STYLE)
        btn_ok.clicked.connect(self.accept)
        bottom.addWidget(btn_ok)
        layout.addLayout(bottom)

    def _select(self, d: date) -> None:
        self._result = d
        self._cleared = False
        self.cal.setSelectedDate(QDate(d.year, d.month, d.day))

    def _on_clear(self) -> None:
        self._cleared = True
        self.accept()

    def result_value(self) -> tuple[bool, date | None]:
        """(cleared, new_date) を返す。clearedがTrueならNoneを設定。"""
        if self._cleared:
            return True, None
        return False, self._result


class DeadlineBadge(QPushButton):
    """締切日を色付きで表示するクリック可能バッジ。"""

    def __init__(self, deadline: date | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.set_deadline(deadline)

    def set_deadline(self, deadline: date | None) -> None:
        if deadline is None:
            self.setText("+ 締切")
            self.setStyleSheet(
                f"color: {MUTED}; background: transparent; border: none;"
                " padding: 1px 4px; font-size: 11px;"
            )
            return
        delta = (deadline - date.today()).days
        if delta == 0:
            text = "今日"
        elif delta == 1:
            text = "明日"
        elif delta == -1:
            text = "昨日"
        elif -7 < delta < 0:
            text = f"{-delta}日前"
        else:
            text = f"{deadline.month}/{deadline.day}"

        if delta <= 0:
            color = "#ef4444"  # 期限切れ・今日 → 赤
        elif delta <= 3:
            color = "#f59e0b"  # 3日以内 → オレンジ
        else:
            color = MUTED
        self.setText(text)
        self.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
            " padding: 1px 4px; font-size: 11px;"
        )


# ---------------------------------------------------------------------------
# Task card  （①インライン編集）
# ---------------------------------------------------------------------------

class TaskCard(QWidget):
    deleted          = Signal(int)        # task_id
    status_changed   = Signal(int, bool)  # task_id, is_done
    split_requested  = Signal(int)        # task_id

    MIME_TYPE = "application/x-task-timer-task-id"

    def __init__(self, task: Task, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task = task
        self.db = db
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

        self.btn_del = QPushButton("×")
        self.btn_del.setFixedSize(20, 20)
        self.btn_del.setFlat(True)
        self.btn_del.setStyleSheet(
            f"color: {MUTED}; font-size: 14px; background: transparent;"
        )
        self.btn_del.clicked.connect(lambda: self.deleted.emit(task.id))

        layout.addWidget(self.check)
        layout.addWidget(self.name_edit, 1)
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
            QMenu {{
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
        act_split = menu.addAction("分解…")
        act_del   = menu.addAction("削除")
        chosen = menu.exec(event.globalPos())
        if chosen is act_split:
            self.split_requested.emit(self.task.id)
        elif chosen is act_del:
            self.deleted.emit(self.task.id)

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


# ---------------------------------------------------------------------------
# Phase column
# ---------------------------------------------------------------------------

class PhaseColumn(QWidget):
    task_added           = Signal(int, str)        # phase_id, name
    task_deleted         = Signal(int)             # task_id
    task_status_changed  = Signal(int, bool)       # task_id, is_done
    task_dropped         = Signal(int, int, int)   # task_id, target_phase_id, insert_index
    task_split_requested = Signal(int)             # task_id
    phase_deleted        = Signal(int)             # phase_id

    def __init__(
        self,
        db: Database,
        phase: Phase,
        tasks: list[Task],
        index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.phase = phase

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

        # Header
        header = QHBoxLayout()
        title = QLabel(phase.name)
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        title.setWordWrap(True)
        title.setStyleSheet(f"color: {TEXT}; background: transparent;")

        self.deadline_badge = DeadlineBadge(phase.deadline)
        self.deadline_badge.clicked.connect(self._open_deadline_picker)

        btn_del = QPushButton("×")
        btn_del.setFixedSize(22, 22)
        btn_del.setFlat(True)
        btn_del.setStyleSheet(f"color: {MUTED}; font-size: 14px; background: transparent;")
        btn_del.clicked.connect(lambda: self.phase_deleted.emit(phase.id))

        header.addWidget(title, 1)
        header.addWidget(self.deadline_badge)
        header.addWidget(btn_del)
        outer.addLayout(header)

        # Cards
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(4)
        for t in tasks:
            card = TaskCard(t, db)
            card.deleted.connect(self.task_deleted.emit)
            card.status_changed.connect(self.task_status_changed.emit)
            card.split_requested.connect(self.task_split_requested.emit)
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
                for idx, pwt in enumerate(proj_tree.phases):
                    sorted_tasks = sorted(
                        pwt.tasks,
                        key=lambda t: (t.status == "done", t.order_index, t.id),
                    )
                    col = PhaseColumn(self.db, pwt.phase, sorted_tasks, index=idx)
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

    def _on_task_added(self, phase_id: int, name: str) -> None:
        existing = self.db.list_tasks(phase_id)
        order = (max((t.order_index for t in existing), default=-1)) + 1
        self.db.create_task(Task(phase_id=phase_id, name=name, order_index=order))
        self._schedule_reload()

    def _on_task_deleted(self, task_id: int) -> None:
        reply = QMessageBox.question(self, "削除確認", "このタスクを削除しますか？")
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_task(task_id)
            self._schedule_reload()

    def _on_task_status_changed(self, task_id: int, is_done: bool) -> None:
        # E: 完了にしたらフェーズの末尾に移動
        if is_done:
            task = self.db.get_task(task_id)
            siblings = self.db.list_tasks(task.phase_id)
            max_order = max(
                (t.order_index for t in siblings if t.id != task_id), default=-1
            )
            self.db.update_task(task_id, order_index=max_order + 1)
        self._schedule_reload()

    def _on_task_dropped(self, task_id: int, target_phase_id: int, insert_index: int) -> None:
        # 表示順（未完了→完了）に揃えてから order_index を振り直す
        target_tasks = [t for t in self.db.list_tasks(target_phase_id) if t.id != task_id]
        target_tasks.sort(key=lambda t: (t.status == "done", t.order_index, t.id))
        insert_index = max(0, min(insert_index, len(target_tasks)))
        # 移動先の order_index を 0..N で振り直す
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
        # 親より後ろのタスクを (N-1) ずらす（親1個ぶんは新タスクが埋める）
        for s in siblings:
            if s.id != parent.id and s.order_index > parent.order_index:
                self.db.update_task(s.id, order_index=s.order_index + n - 1)
        for i, name in enumerate(names):
            self.db.create_task(Task(
                phase_id=parent.phase_id,
                name=name,
                order_index=parent.order_index + i,
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

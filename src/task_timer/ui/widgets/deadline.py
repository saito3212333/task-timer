"""締切：プリセット関数・カレンダー・ピッカー・バッジ。"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from task_timer.ui.theme import ACCENT, BTN_STYLE, DANGER, MUTED, ORANGE, TEXT


# ---------------------------------------------------------------------------
# Presets
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


# ---------------------------------------------------------------------------
# Calendar widget
# ---------------------------------------------------------------------------

class WeekendCalendar(QCalendarWidget):
    """土曜=青・日曜=赤を、現在月外の日付にも適用するカレンダー。"""

    _COLOR_SAT    = QColor("#2563eb")
    _COLOR_SUN    = QColor("#dc2626")
    _COLOR_TEXT   = QColor(TEXT)
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


# ---------------------------------------------------------------------------
# Picker dialog
# ---------------------------------------------------------------------------

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
            btn.setStyleSheet(BTN_STYLE)
            btn.clicked.connect(lambda _=False, f=fn: self._select(f()))
            presets.addWidget(btn)
        layout.addLayout(presets)

        self.cal = WeekendCalendar()
        self.cal.setGridVisible(True)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        sat_fmt = QTextCharFormat()
        sat_fmt.setForeground(QColor("#2563eb"))
        self.cal.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, sat_fmt)
        sun_fmt = QTextCharFormat()
        sun_fmt.setForeground(QColor("#dc2626"))
        self.cal.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, sun_fmt)
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
        btn_ok.setStyleSheet(BTN_STYLE)
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


# ---------------------------------------------------------------------------
# Badge button
# ---------------------------------------------------------------------------

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
            self.setText("〆 +")
            self.setStyleSheet(
                f"color: {MUTED}; background: transparent; border: none;"
                " padding: 1px 4px; font-size: 10px;"
            )
            return
        delta = (deadline - date.today()).days
        if delta == 0:
            text = "〆 今日"
        elif delta == 1:
            text = "〆 明日"
        elif delta == -1:
            text = "〆 昨日"
        elif -7 < delta < 0:
            text = f"〆 {-delta}日前"
        else:
            text = f"〆 {deadline.month}/{deadline.day}"

        if delta <= 0:
            color = DANGER
        elif delta <= 3:
            color = ORANGE
        else:
            color = MUTED
        self.setText(text)
        self.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
            " padding: 1px 4px; font-size: 10px;"
        )

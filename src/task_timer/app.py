from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from task_timer.db import Database, connect
from task_timer.ui.theme import TOOLTIP_STYLE
from task_timer.ui.timer_window import TimerWindow


def main() -> None:
    conn = connect()
    db = Database(conn)
    db.init_default_setup()

    app = QApplication(sys.argv)
    # QToolTip は macOS の Qt がパレットを優先するため、Palette と StyleSheet 両方を設定
    pal = app.palette()
    pal.setColor(QPalette.ToolTipBase, QColor("#1e293b"))
    pal.setColor(QPalette.ToolTipText, QColor("#f1f5f9"))
    app.setPalette(pal)
    app.setStyleSheet(TOOLTIP_STYLE)

    window = TimerWindow(db)
    window.show()
    sys.exit(app.exec())

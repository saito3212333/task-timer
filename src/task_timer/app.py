from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from task_timer.db import Database, connect
from task_timer.ui.timer_window import TimerWindow


def main() -> None:
    conn = connect()
    db = Database(conn)
    db.init_default_setup()

    app = QApplication(sys.argv)
    window = TimerWindow(db)
    window.show()
    sys.exit(app.exec())

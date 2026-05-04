from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from task_timer.db import Database, connect
from task_timer.ui.manager_window import ManagerWindow


def main() -> None:
    conn = connect()
    db = Database(conn)

    app = QApplication(sys.argv)
    window = ManagerWindow(db)
    window.show()
    sys.exit(app.exec())

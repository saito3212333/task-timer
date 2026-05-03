from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from task_timer.db import Database, connect, default_db_path


class TimerWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("Task Timer")
        self.resize(380, 480)

        n_projects = len(self.db.list_projects(include_archived=True))
        placeholder = QLabel(
            f"⏱  task-timer v0.1\n(skeleton)\n\n"
            f"DB: {default_db_path()}\n"
            f"projects: {n_projects}"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)


def main() -> None:
    conn = connect()
    db = Database(conn)

    app = QApplication(sys.argv)
    window = TimerWindow(db)
    window.show()
    sys.exit(app.exec())

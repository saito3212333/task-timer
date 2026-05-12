"""トランザクションヘルパーと汎用 UPDATE。"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Callable, Iterator

from task_timer.db._converters import _date_str, _dt_str


class BaseMixin:
    """Database クラス本体で self.conn を提供する前提。"""

    conn: sqlite3.Connection

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self.conn:
            yield self.conn

    def _patch(
        self,
        table: str,
        row_id: int,
        fields: dict[str, Any],
        row_fn: Callable[[sqlite3.Row], Any],
    ):
        if not fields:
            raise ValueError("update called with no fields")

        normalized: dict[str, Any] = {}
        for k, v in fields.items():
            if isinstance(v, bool):
                normalized[k] = 1 if v else 0
            elif isinstance(v, date) and not isinstance(v, datetime):
                normalized[k] = _date_str(v)
            elif isinstance(v, datetime):
                normalized[k] = _dt_str(v)
            else:
                normalized[k] = v

        cols = ", ".join(f"{k} = ?" for k in normalized.keys())
        params = (*normalized.values(), row_id)
        sql = f"UPDATE {table} SET {cols}, updated_at = datetime('now') WHERE id = ?"
        with self.tx() as c:
            cur = c.execute(sql, params)
            if cur.rowcount == 0:
                raise KeyError(f"{table} {row_id} not found")
        row = self.conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)
        ).fetchone()
        return row_fn(row)

"""集計クエリ（実績時間の合計・中央値）。"""
from __future__ import annotations


class AggregatesMixin:
    def total_seconds_for_task(self, task_id: int) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(duration_sec), 0) AS s FROM time_logs WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        return int(row["s"] or 0)

    def total_seconds_for_phase(self, phase_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(tl.duration_sec), 0) AS s
            FROM time_logs tl
            JOIN tasks t ON tl.task_id = t.id
            WHERE t.phase_id = ?
            """,
            (phase_id,),
        ).fetchone()
        return int(row["s"] or 0)

    def median_actual_seconds_for_project(self, project_id: int) -> float | None:
        """同プロジェクト内の完了タスクの実績時間（time_logs合計）の中央値。
        サンプルが0件のときはNone。Tシャツ丸めは呼び出し側で行う。"""
        rows = self.conn.execute(
            """
            SELECT SUM(tl.duration_sec) AS total_sec
            FROM tasks t
            JOIN phases p   ON t.phase_id = p.id
            JOIN time_logs tl ON tl.task_id = t.id
            WHERE p.project_id = ? AND t.status = 'done'
            GROUP BY t.id
            HAVING total_sec > 0
            ORDER BY total_sec
            """,
            (project_id,),
        ).fetchall()
        if not rows:
            return None
        vals = [r["total_sec"] for r in rows]
        n = len(vals)
        if n % 2 == 0:
            return (vals[n // 2 - 1] + vals[n // 2]) / 2
        return float(vals[n // 2])

    def total_seconds_for_project(self, project_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(tl.duration_sec), 0) AS s
            FROM time_logs tl
            JOIN tasks t  ON tl.task_id = t.id
            JOIN phases p ON t.phase_id = p.id
            WHERE p.project_id = ?
            """,
            (project_id,),
        ).fetchone()
        return int(row["s"] or 0)

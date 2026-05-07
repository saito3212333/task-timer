"""見積もり／時間フォーマット用ヘルパー。"""
from __future__ import annotations

from task_timer.ui.theme import GREEN, MUTED, ORANGE


TSHIRT_HOURS = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]


def round_to_tshirt(hours: float) -> float:
    """任意の時間を最も近いTシャツサイズに丸める。"""
    return min(TSHIRT_HOURS, key=lambda x: abs(x - hours))


def fmt_planned(hours: float) -> str:
    if hours < 1:
        return f"{int(round(hours * 60))}m"
    if hours == int(hours):
        return f"{int(hours)}h"
    return f"{hours}h"


def fmt_actual(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m = rem // 60
    if h == 0:
        return f"{m}m"
    if m == 0:
        return f"{h}h"
    return f"{h}h{m:02d}m"


def estimate_color(planned_hours: float, actual_sec: int) -> str:
    """完了タスクの実績色：早い=GREEN／近い=MUTED／遅い=ORANGE。"""
    planned_sec = planned_hours * 3600
    if planned_sec <= 0:
        return MUTED
    ratio = actual_sec / planned_sec
    if ratio < 0.8:
        return GREEN
    if ratio > 1.2:
        return ORANGE
    return MUTED

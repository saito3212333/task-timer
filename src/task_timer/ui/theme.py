"""色パレット＋共通スタイル文字列。

タイマー画面・カンバン画面・各ウィジェットから参照される唯一の色定義。
"""

# Backgrounds
BG        = "#e2e8f0"
COL_BG    = "#f1f5f9"
CARD_BG   = "#ffffff"
TOPBAR_BG = "#1e293b"

# Foreground
TEXT  = "#1e293b"
MUTED = "#64748b"

# Accents
ACCENT = "#3b82f6"  # blue
DANGER = "#ef4444"  # red
GREEN  = "#10b981"  # success / under-estimate
ORANGE = "#f59e0b"  # warn / over-estimate

# Phase column backgrounds (cycling)
PHASE_COL_BGS = [
    "#eff6ff",  # sky
    "#fff7ed",  # orange
    "#faf5ff",  # purple
    "#ecfdf5",  # mint
    "#fef2f2",  # rose
    "#fefce8",  # cream
]

# ---------------------------------------------------------------------------
# Reusable button styles
# ---------------------------------------------------------------------------

BTN_STYLE = f"""
    QPushButton {{
        background: {ACCENT};
        color: white;
        border: none;
        border-radius: 5px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{ background: #2563eb; }}
"""

BTN_DANGER = f"""
    QPushButton {{
        background: {DANGER};
        color: white;
        border: none;
        border-radius: 5px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{ background: #dc2626; }}
"""

# 文字のみのスタート／ストップ（他のテキストと同じMUTED色、ホバーで計測中と同じ緑）
BTN_START_STYLE = f"""
    QPushButton {{
        background: transparent;
        color: {MUTED};
        border: none;
        font-size: 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ color: {GREEN}; }}
    QPushButton:disabled {{ color: #cbd5e1; }}
"""

BTN_STOP_STYLE = BTN_START_STYLE

LINK_STYLE = f"""
    QPushButton {{
        background: transparent;
        color: {MUTED};
        border: none;
        font-size: 12px;
        padding: 2px 8px;
    }}
    QPushButton:hover {{ color: {GREEN}; }}
    QPushButton:disabled {{ color: #cbd5e1; }}
    QPushButton:checked {{ color: {GREEN}; }}
"""

# QToolTip: 濃いネイビー背景 + 白文字で可読性確保
TOOLTIP_STYLE = f"""
QToolTip {{
    background-color: {TOPBAR_BG};
    color: #f1f5f9;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 6px 8px;
}}
"""

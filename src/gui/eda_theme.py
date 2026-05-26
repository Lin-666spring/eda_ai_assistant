"""
EDA AI 智能助手 — 4套多颜色主题系统

主题列表:
  1. 深海科技 (deep_sea)       — 深蓝专业风，默认主题
  2. 极简冷白 (minimal_white)  — 浅色清爽，明亮环境
  3. 石墨灰调 (graphite)       — 中性深灰，减少视觉疲劳
  4. 青森护眼 (forest_green)   — 低饱和绿，长时间护眼

用法:
  from .eda_theme import switch_theme, current_theme, THEME_NAMES
  switch_theme("minimal_white")
  t = current_theme()  # 始终返回当前激活主题
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Callable

# ══════════════════════════════════════════
#  Fonts (shared across all themes)
# ══════════════════════════════════════════

FONT_FAMILY = (
    '"Segoe UI Variable", "Segoe UI", '
    '"HarmonyOS Sans SC", "Noto Sans SC", "Microsoft YaHei", sans-serif'
)
FONT_MONO = (
    '"Cascadia Code", "JetBrains Mono", "Fira Code", '
    '"Consolas", "Microsoft YaHei Mono", monospace'
)
FONT_SIZE = "13px"
FONT_SIZE_SM = "12px"
FONT_SIZE_XS = "11px"

# ══════════════════════════════════════════
#  Persistence
# ══════════════════════════════════════════

_SETTINGS_DIR = Path.home() / ".eda_ai_assistant"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"


def _load_theme_preference() -> str:
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            name = data.get("selected_theme", "")
            if name in THEMES:
                return name
    except (json.JSONDecodeError, OSError):
        pass
    return "deep_sea"


def _save_theme_preference(name: str):
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        data = {}
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        data["selected_theme"] = name
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ══════════════════════════════════════════
#  Theme: 深海科技 (Deep Sea — default)
# ══════════════════════════════════════════

DEEP_SEA: Dict[str, str] = {
    "theme_name": "深海科技",
    "theme_id": "deep_sea",
    "is_dark": "1",
    # Core
    "primary": "#165DFF",
    "primary_hover": "#3478FF",
    "primary_pressed": "#1248CC",
    "primary_glow": "#165DFF40",
    # Background
    "bg_main": "#0A1629",
    "bg_card": "#132442",
    "bg_card_hover": "#1A3055",
    "bg_input": "#0D1C35",
    "bg_header": "#0F1E38",
    # Text
    "text_primary": "#E6EDF7",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "text_white": "#FFFFFF",
    # Accent
    "highlight": "#3B8CFF",
    "success": "#22C55E",
    "warning": "#FF7D00",
    "warning_bg": "rgba(255,125,0,0.12)",
    "error": "#EF4444",
    "error_bg": "rgba(239,68,68,0.10)",
    # Borders
    "border": "#1E3555",
    "border_light": "#2A4470",
    "border_focus": "#165DFF",
    # Selection
    "selection_bg": "#165DFF40",
    "selection_text": "#FFFFFF",
    # Scrollbar
    "scrollbar_handle": "#1E3555",
    "scrollbar_handle_hover": "#2A4470",
    # Status bar
    "status_bar_bg": "#060E1C",
    "status_bar_text": "#7B8BA8",
    # Chat
    "chat_bg": "#0A1629",
    "chat_bubble_user": "#165DFF",
    "chat_bubble_ai": "#132442",
    "chat_text_user": "#FFFFFF",
    "chat_text_ai": "#E6EDF7",
    "chat_text_sys": "#94A3B8",
    "chat_time_user": "#FFFFFF99",
    "chat_time_ai": "#64748B",
    # Navbar
    "navbar_bg": "#0E1C30",
    # Card
    "card_bg": "#132442",
    "card_radius": "10px",
    "card_border": "#1A3050",
    # Misc
    "shadow": "#060D1A",
    "divider": "#1A3050",
    # Table alt row
    "table_alt_bg": "#0E1D33",
    # Welcome section blocks (per-theme adaptive)
    "section_header_bg": "rgba(22,93,255,0.07)",
    "config_tip_bg": "#1E3A6A",
    "config_tip_border": "#254B85",
}

# ══════════════════════════════════════════
#  Theme: 极简冷白 (Minimal White)
# ══════════════════════════════════════════

MINIMAL_WHITE: Dict[str, str] = {
    "theme_name": "极简冷白",
    "theme_id": "minimal_white",
    "is_dark": "0",
    # Core
    "primary": "#2563EB",
    "primary_hover": "#3B82F6",
    "primary_pressed": "#1D4ED8",
    "primary_glow": "#2563EB30",
    # Background
    "bg_main": "#F8FAFC",
    "bg_card": "#FFFFFF",
    "bg_card_hover": "#F1F5F9",
    "bg_input": "#FFFFFF",
    "bg_header": "#F8FAFC",
    # Text
    "text_primary": "#1E293B",
    "text_secondary": "#64748B",
    "text_muted": "#94A3B8",
    "text_white": "#FFFFFF",
    # Accent
    "highlight": "#2563EB",
    "success": "#16A34A",
    "warning": "#EA580C",
    "warning_bg": "rgba(234,88,12,0.08)",
    "error": "#DC2626",
    "error_bg": "rgba(220,38,38,0.06)",
    # Borders
    "border": "#E2E8F0",
    "border_light": "#CBD5E1",
    "border_focus": "#2563EB",
    # Selection
    "selection_bg": "#2563EB30",
    "selection_text": "#FFFFFF",
    # Scrollbar
    "scrollbar_handle": "#CBD5E1",
    "scrollbar_handle_hover": "#94A3B8",
    # Status bar
    "status_bar_bg": "#F1F5F9",
    "status_bar_text": "#64748B",
    # Chat
    "chat_bg": "#F8FAFC",
    "chat_bubble_user": "#2563EB",
    "chat_bubble_ai": "#F1F5F9",
    "chat_text_user": "#FFFFFF",
    "chat_text_ai": "#1E293B",
    "chat_text_sys": "#64748B",
    "chat_time_user": "#FFFFFFB3",
    "chat_time_ai": "#94A3B8",
    # Navbar
    "navbar_bg": "#FFFFFF",
    # Card
    "card_bg": "#FFFFFF",
    "card_radius": "10px",
    "card_border": "#E2E8F0",
    # Misc
    "shadow": "#00000010",
    "divider": "#E2E8F0",
    # Table alt row
    "table_alt_bg": "#F1F5F9",
    # Welcome section blocks (per-theme adaptive)
    "section_header_bg": "rgba(37,99,235,0.04)",
    "config_tip_bg": "#EFF6FF",
    "config_tip_border": "#BFDBFE",
}

# ══════════════════════════════════════════
#  Theme: 石墨灰调 (Graphite)
# ══════════════════════════════════════════

GRAPHITE: Dict[str, str] = {
    "theme_name": "石墨灰调",
    "theme_id": "graphite",
    "is_dark": "1",
    # Core
    "primary": "#475569",
    "primary_hover": "#64748B",
    "primary_pressed": "#334155",
    "primary_glow": "#47556940",
    # Background
    "bg_main": "#1A1A1A",
    "bg_card": "#292929",
    "bg_card_hover": "#363636",
    "bg_input": "#242424",
    "bg_header": "#222222",
    # Text
    "text_primary": "#D1D5DB",
    "text_secondary": "#9CA3AF",
    "text_muted": "#6B7280",
    "text_white": "#FFFFFF",
    # Accent
    "highlight": "#94A3B8",
    "success": "#4ADE80",
    "warning": "#F59E0B",
    "warning_bg": "rgba(245,158,11,0.12)",
    "error": "#F87171",
    "error_bg": "rgba(248,113,113,0.10)",
    # Borders
    "border": "#404040",
    "border_light": "#525252",
    "border_focus": "#64748B",
    # Selection
    "selection_bg": "#47556940",
    "selection_text": "#FFFFFF",
    # Scrollbar
    "scrollbar_handle": "#404040",
    "scrollbar_handle_hover": "#525252",
    # Status bar
    "status_bar_bg": "#111111",
    "status_bar_text": "#9CA3AF",
    # Chat
    "chat_bg": "#1A1A1A",
    "chat_bubble_user": "#475569",
    "chat_bubble_ai": "#292929",
    "chat_text_user": "#FFFFFF",
    "chat_text_ai": "#D1D5DB",
    "chat_text_sys": "#9CA3AF",
    "chat_time_user": "#FFFFFF99",
    "chat_time_ai": "#6B7280",
    # Navbar
    "navbar_bg": "#222222",
    # Card
    "card_bg": "#292929",
    "card_radius": "10px",
    "card_border": "#404040",
    # Misc
    "shadow": "#00000040",
    "divider": "#404040",
    # Table alt row
    "table_alt_bg": "#222222",
    # Welcome section blocks (per-theme adaptive)
    "section_header_bg": "rgba(71,85,105,0.08)",
    "config_tip_bg": "#334155",
    "config_tip_border": "#475569",
}

# ══════════════════════════════════════════
#  Theme: 青森护眼 (Forest Green)
# ══════════════════════════════════════════

FOREST_GREEN: Dict[str, str] = {
    "theme_name": "青森护眼",
    "theme_id": "forest_green",
    "is_dark": "1",
    # Core — fresh teal-green, calm & clear
    "primary": "#0D9488",
    "primary_hover": "#14B8A6",
    "primary_pressed": "#0B7A70",
    "primary_glow": "#0D948850",
    # Background — lighter teal-tinted dark, not deep black-green
    "bg_main": "#1A3A35",
    "bg_card": "#234D47",
    "bg_card_hover": "#2C5E57",
    "bg_input": "#1D423C",
    "bg_header": "#1F453F",
    # Text — crisp, good contrast on lighter bg
    "text_primary": "#D1FAE5",
    "text_secondary": "#8CC4B5",
    "text_muted": "#6DA096",
    "text_white": "#ECFDF5",
    # Accent
    "highlight": "#5AB8A2",
    "success": "#3CB38A",
    "warning": "#F09060",
    "warning_bg": "rgba(240,144,96,0.12)",
    "error": "#FB7185",
    "error_bg": "rgba(251,113,133,0.10)",
    # Borders — lighter, more open feel
    "border": "#2C5E57",
    "border_light": "#3A7A6E",
    "border_focus": "#0D9488",
    # Selection
    "selection_bg": "#0D948850",
    "selection_text": "#ECFDF5",
    # Scrollbar
    "scrollbar_handle": "#2C5E57",
    "scrollbar_handle_hover": "#3A7A6E",
    # Status bar
    "status_bar_bg": "#122E2A",
    "status_bar_text": "#6DA096",
    # Chat — teal-toned, noticeably lighter
    "chat_bg": "#1A3A35",
    "chat_bubble_user": "#0D9488",
    "chat_bubble_ai": "#234D47",
    "chat_text_user": "#ECFDF5",
    "chat_text_ai": "#D1FAE5",
    "chat_text_sys": "#8CC4B5",
    "chat_time_user": "#FFFFFF99",
    "chat_time_ai": "#6DA096",
    # Navbar
    "navbar_bg": "#1C3F3A",
    # Card
    "card_bg": "#234D47",
    "card_radius": "10px",
    "card_border": "#2C5E57",
    # Misc
    "shadow": "#0A1A17",
    "divider": "#2C5E57",
    # Table alt row
    "table_alt_bg": "#1C3F3A",
    # Welcome section blocks
    "section_header_bg": "rgba(13,148,136,0.08)",
    "config_tip_bg": "#1E5F58",
    "config_tip_border": "#297A70",
}

# ══════════════════════════════════════════
#  Theme registry
# ══════════════════════════════════════════

THEMES: Dict[str, Dict[str, str]] = {
    "deep_sea": DEEP_SEA,
    "minimal_white": MINIMAL_WHITE,
    "graphite": GRAPHITE,
    "forest_green": FOREST_GREEN,
}

THEME_DISPLAY_ORDER = ["deep_sea", "minimal_white", "graphite", "forest_green"]

# ══════════════════════════════════════════
#  Semantic status colours — dark-mode low-saturation glow
#  Shared across all themes; translucent rgba works on any bg
# ══════════════════════════════════════════

SEMANTIC: Dict[str, Dict[str, str]] = {
    "info": {
        "label": "信息",
        "bg": "rgba(99, 102, 241, 0.15)",
        "border": "rgba(99, 102, 241, 0.30)",
        "text": "#818CF8",
    },
    "success": {
        "label": "成功",
        "bg": "rgba(16, 185, 129, 0.15)",
        "border": "rgba(16, 185, 129, 0.30)",
        "text": "#34D399",
    },
    "warning": {
        "label": "警告",
        "bg": "rgba(245, 158, 11, 0.15)",
        "border": "rgba(245, 158, 11, 0.30)",
        "text": "#FBBF24",
    },
    "error": {
        "label": "错误",
        "bg": "rgba(244, 63, 94, 0.15)",
        "border": "rgba(244, 63, 94, 0.30)",
        "text": "#FB7185",
    },
}


def _detect_semantic_type(text: str) -> str:
    """Auto-detect semantic type from message content keywords."""
    tl = text.lower()
    # Error — unconfigured, invalid, disabled, failed
    if any(kw in tl for kw in ["未配置", "无效", "禁用", "失败", "错误",
                                 "unconfigured", "invalid", "disabled", "failed"]):
        return "error"
    # Success — passed, complete, generated, successful
    if any(kw in tl for kw in ["通过", "完成", "已生成", "成功", "就绪",
                                 "passed", "complete", "generated", "ready", " done"]):
        return "success"
    # Warning — attention needed, missing data, pending
    if any(kw in tl for kw in ["请先", "缺少", "待处理", "部分", "注意",
                                 "missing", "pending", "attention", "please"]):
        return "warning"
    # Info — default for everything else
    return "info"


def get_semantic_style(semantic_type: str) -> Dict[str, str]:
    """Return {bg, border, text} for a semantic type."""
    return SEMANTIC.get(semantic_type, SEMANTIC["info"])
# ══════════════════════════════════════════

_active_theme_name: str = _load_theme_preference()
_listeners: List[Callable[[str], None]] = []


def current_theme() -> Dict[str, str]:
    """Return the currently active theme palette."""
    return THEMES[_active_theme_name]


def get_active_theme_name() -> str:
    return _active_theme_name


def get_theme_display_name(name: str = None) -> str:
    if name is None:
        name = _active_theme_name
    return THEMES[name].get("theme_name", name)


def switch_theme(name: str):
    """Switch to a named theme, persist, and notify all listeners."""
    global _active_theme_name
    if name not in THEMES:
        raise ValueError(f"Unknown theme: {name}. Available: {list(THEMES.keys())}")
    _active_theme_name = name
    _save_theme_preference(name)
    for cb in _listeners:
        try:
            cb(name)
        except Exception:
            pass


def on_theme_changed(callback: Callable[[str], None]):
    """Register a callback invoked after theme switch. Callback receives theme name."""
    if callback not in _listeners:
        _listeners.append(callback)


def remove_theme_listener(callback: Callable[[str], None]):
    if callback in _listeners:
        _listeners.remove(callback)


# ══════════════════════════════════════════
#  Stylesheet compiler
# ══════════════════════════════════════════

def compile_stylesheet() -> str:
    """Generate a complete QSS stylesheet from the active theme."""
    t = current_theme()
    return f"""
    /* ═══════════════════════════════════════
       EDA AI 智能助手 — Global Stylesheet
       Theme: {t['theme_name']}
       ═══════════════════════════════════════ */

    QWidget {{
        background-color: {t['bg_main']};
        color: {t['text_primary']};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE};
        border: none;
        outline: none;
    }}

    QMainWindow {{
        background-color: {t['bg_main']};
    }}

    QMainWindow::separator {{
        width: 1px;
        height: 1px;
        background-color: {t['border']};
    }}

    /* ── Menu Bar ── */

    QMenuBar {{
        background-color: {t['navbar_bg']};
        padding: 4px 12px;
        border-bottom: 1px solid {t['border']};
    }}

    QMenuBar::item {{
        padding: 6px 14px;
        margin: 2px 2px;
        background-color: transparent;
        color: {t['text_secondary']};
        border-radius: 6px;
        font-size: {FONT_SIZE_SM};
    }}

    QMenuBar::item:selected {{
        background-color: {t['primary']};
        color: {t['text_white']};
    }}

    QMenu {{
        background-color: {t['bg_card']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        padding: 6px 0;
    }}

    QMenu::item {{
        padding: 8px 36px 8px 16px;
        color: {t['text_primary']};
    }}

    QMenu::item:selected {{
        background-color: {t['primary']};
        color: {t['text_white']};
        border-radius: 4px;
        margin: 1px 4px;
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {t['border']};
        margin: 6px 12px;
    }}

    /* ── Splitter ── */

    QSplitter::handle {{
        background-color: {t['border']};
    }}

    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    /* ── Tabs ── */

    QTabWidget::pane {{
        border: none;
        background-color: transparent;
    }}

    QTabBar::tab {{
        background-color: transparent;
        color: {t['text_secondary']};
        padding: 10px 20px;
        margin-right: 2px;
        border-bottom: 2px solid transparent;
        font-size: {FONT_SIZE};
        font-weight: 500;
    }}

    QTabBar::tab:selected {{
        color: {t['text_primary']};
        border-bottom: 2px solid {t['primary']};
        font-weight: 600;
    }}

    QTabBar::tab:hover:!selected {{
        color: {t['text_primary']};
        background-color: {t['bg_card_hover']};
        border-radius: 6px 6px 0 0;
    }}

    /* ── Table ── */

    QTableWidget {{
        background-color: transparent;
        alternate-background-color: {t['table_alt_bg']};
        gridline-color: transparent;
        font-size: {FONT_SIZE_SM};
        border: none;
        border-radius: 0;
        font-family: {FONT_FAMILY};
    }}

    QTableWidget::item {{
        padding: 8px 14px;
        color: {t['text_primary']};
        border-bottom: 1px solid {t['border']};
    }}

    QTableWidget::item:selected {{
        background-color: {t['primary']};
        color: {t['text_white']};
    }}

    QTableWidget::item:hover:!selected {{
        background-color: {t['bg_card_hover']};
    }}

    QHeaderView::section {{
        background-color: {t['bg_card']};
        color: {t['text_secondary']};
        padding: 10px 14px;
        font-weight: 600;
        font-size: {FONT_SIZE_XS};
        border: none;
        border-right: 1px solid {t['border']};
        border-bottom: 1px solid {t['border']};
    }}

    QHeaderView::section:hover {{
        background-color: {t['bg_card_hover']};
        color: {t['text_primary']};
    }}

    QTableCornerButton::section {{
        background-color: {t['bg_card']};
        border-bottom: 1px solid {t['border']};
    }}

    /* ── Text Edit ── */

    QTextEdit {{
        background-color: {t['bg_main']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        font-size: {FONT_SIZE};
        selection-background-color: {t['primary']};
        selection-color: {t['text_white']};
    }}

    QTextEdit:focus {{
        border-color: {t['border_focus']};
    }}

    /* ── Line Edit ── */

    QLineEdit {{
        background-color: {t['bg_input']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: {FONT_SIZE};
        selection-background-color: {t['primary']};
    }}

    QLineEdit:focus {{
        border: 2px solid {t['border_focus']};
        padding: 9px 13px;
    }}

    /* ── Push Button ── */

    QPushButton {{
        background-color: {t['primary']};
        color: {t['text_white']};
        border: none;
        border-radius: 8px;
        padding: 9px 18px;
        font-size: {FONT_SIZE};
        font-weight: 600;
    }}

    QPushButton:hover {{
        background-color: {t['primary_hover']};
    }}

    QPushButton:pressed {{
        background-color: {t['primary_pressed']};
    }}

    QPushButton:disabled {{
        background-color: {t['border']};
        color: {t['text_muted']};
    }}

    /* ── Combo Box ── */

    QComboBox {{
        background-color: {t['bg_input']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: {FONT_SIZE};
    }}

    QComboBox:hover {{ border-color: {t['border_light']}; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox QAbstractItemView {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        border-radius: 8px;
        selection-background-color: {t['primary']};
        selection-color: {t['text_white']};
        padding: 4px;
    }}

    /* ── Scroll Bars ── */

    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px; margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {t['scrollbar_handle']};
        border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {t['scrollbar_handle_hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background-color: transparent; }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px; margin: 2px 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {t['scrollbar_handle']};
        border-radius: 4px; min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {t['scrollbar_handle_hover']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background-color: transparent; }}

    /* ── Status Bar ── */

    QStatusBar {{
        background-color: {t['status_bar_bg']};
        color: {t['status_bar_text']};
        font-size: {FONT_SIZE_XS};
        padding: 3px 12px;
        border-top: 1px solid {t['border']};
    }}
    QStatusBar::item {{ border: none; }}
    QStatusBar QLabel {{
        color: {t['status_bar_text']};
        font-size: {FONT_SIZE_XS};
        padding: 0 10px;
        background-color: transparent;
    }}

    /* ── Tool Tip ── */

    QToolTip {{
        background-color: {t['bg_card']};
        color: {t['text_primary']};
        border: 1px solid {t['border_light']};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: {FONT_SIZE_XS};
    }}

    /* ── Dialogs ── */

    QMessageBox {{ background-color: {t['bg_card']}; }}
    QMessageBox QLabel {{ color: {t['text_primary']}; }}
    QDialog {{ background-color: {t['bg_card']}; }}

    /* ── Form Labels ── */

    QFormLayout QLabel {{
        color: {t['text_secondary']};
        font-size: {FONT_SIZE_SM};
        font-weight: 500;
    }}

    /* ── Progress Bar ── */

    QProgressBar {{
        background-color: {t['bg_input']};
        border: none; border-radius: 4px;
        height: 4px; text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {t['primary']};
        border-radius: 4px;
    }}
    """

"""
VS Code Dark+ and Light+ themes for the EDA AI Assistant GUI.

Usage:
    from .vscode_theme import compile_stylesheet, toggle_theme, current_theme

    app.setStyleSheet(compile_stylesheet())       # dark
    toggle_theme()                                 # switch
    app.setStyleSheet(compile_stylesheet())        # now light
"""

from typing import Dict

# ══════════════════════════════════════════
#  Fonts (shared)
# ══════════════════════════════════════════

# UI sans-serif — Inter (modern UI standard), Segoe UI (Windows), CJK fallbacks
FONT_FAMILY = (
    '"Inter", "Segoe UI Variable", "Segoe UI", '
    '"HarmonyOS Sans SC", "Noto Sans SC", "Microsoft YaHei", sans-serif'
)
# Monospace — JetBrains Mono (best readability), Maple Mono (2:1 CJK alignment),
# Fira Code (rich ligatures), Cascadia Code (Windows default), Consolas (classic)
FONT_MONO = (
    '"JetBrains Mono", "Fira Code", "Maple Mono", "Cascadia Code", '
    '"Consolas", "Microsoft YaHei Mono", monospace'
)
FONT_SIZE = "13px"
FONT_SIZE_SM = "12px"
FONT_SIZE_XS = "11px"

# ══════════════════════════════════════════
#  Chat syntax colours (shared)
# ══════════════════════════════════════════

SYNTAX_KEYWORD = "#569cd6"
SYNTAX_TYPE = "#4ec9b0"
SYNTAX_ERROR = "#f44747"

# ══════════════════════════════════════════
#  Dark theme
# ══════════════════════════════════════════

DARK = {
    "bg_editor": "#1e1e1e",
    "bg_sidebar": "#252526",
    "bg_activity": "#333333",
    "bg_tab_inactive": "#2d2d2d",
    "bg_input": "#3c3c3c",
    "bg_hover": "#2a2d2e",
    "accent": "#007acc",
    "accent_hover": "#1a8ad4",
    "btn_bg": "#0e639c",
    "btn_bg_hover": "#1177bb",
    "btn_bg_pressed": "#0d5689",
    "border": "#3c3c3c",
    "border_strong": "#474747",
    "text_primary": "#cccccc",
    "text_secondary": "#969696",
    "text_white": "#ffffff",
    "selection_bg": "#264f78",
    "status_bar_bg": "#333333",
    "status_bar_text": "#cccccc",
    "scrollbar_handle": "#424242",
    "scrollbar_handle_hover": "#4f4f4f",
    "activity_text": "#858585",
    "activity_text_active": "#ffffff",
    "title_bar_bg": "#2d2d2d",
    "title_bar_text": "#cccccc",
    "chat_bg": "#1e1e1e",
    "chat_border": "#3c3c3c",
    "chat_header_user": "#569cd6",
    "chat_header_ai": "#4ec9b0",
    "chat_header_sys": "#969696",
    "chat_header_err": "#f44747",
    "chat_text": "#cccccc",
    "chat_stream_token": "#cccccc",
    "chat_separator": "#3c3c3c",
    "msgbox_bg": "#2d2d2d",
}

# ══════════════════════════════════════════
#  Light theme (VS Code Light+)
# ══════════════════════════════════════════

LIGHT = {
    "bg_editor": "#ffffff",
    "bg_sidebar": "#f3f3f3",
    "bg_activity": "#2c2c2c",
    "bg_tab_inactive": "#ececec",
    "bg_input": "#ffffff",
    "bg_hover": "#e8e8e8",
    "accent": "#005fb8",
    "accent_hover": "#0071d4",
    "btn_bg": "#d4d4d4",
    "btn_bg_hover": "#c4c4c4",
    "btn_bg_pressed": "#b4b4b4",
    "border": "#e7e7e7",
    "border_strong": "#cccccc",
    "text_primary": "#3b3b3b",
    "text_secondary": "#616161",
    "text_white": "#ffffff",
    "selection_bg": "#0060c0",
    "status_bar_bg": "#e0e0e0",
    "status_bar_text": "#3b3b3b",
    "scrollbar_handle": "#c1c1c1",
    "scrollbar_handle_hover": "#a8a8a8",
    "activity_text": "#cccccc",
    "activity_text_active": "#ffffff",
    "title_bar_bg": "#ececec",
    "title_bar_text": "#3b3b3b",
    "chat_bg": "#ffffff",
    "chat_border": "#e7e7e7",
    "chat_header_user": "#0451a5",
    "chat_header_ai": "#1a7f37",
    "chat_header_sys": "#616161",
    "chat_header_err": "#cf222e",
    "chat_text": "#3b3b3b",
    "chat_stream_token": "#616161",
    "chat_separator": "#e7e7e7",
    "msgbox_bg": "#f3f3f3",
}

# ══════════════════════════════════════════
#  Theme management
# ══════════════════════════════════════════

_current_is_dark = True


def current_theme() -> Dict[str, str]:
    """Return the active theme palette."""
    return DARK if _current_is_dark else LIGHT


def is_dark() -> bool:
    return _current_is_dark


def toggle_theme() -> bool:
    """Switch theme. Returns True if now dark."""
    global _current_is_dark
    _current_is_dark = not _current_is_dark
    return _current_is_dark


def set_theme(dark: bool):
    global _current_is_dark
    _current_is_dark = dark


def compile_stylesheet() -> str:
    """Return a QSS string for the current theme."""
    t = current_theme()
    return f"""
    /* ═══════════════════════════════════════
       Global
       ═══════════════════════════════════════ */

    QWidget {{
        background-color: {t['bg_editor']};
        color: {t['text_primary']};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE};
        border: none;
        outline: none;
    }}

    QMainWindow {{
        background-color: {t['bg_editor']};
    }}

    QMainWindow::separator {{
        width: 1px; height: 1px;
        background-color: {t['border']};
    }}

    /* ═══════════════════════════════════════
       Menu bar
       ═══════════════════════════════════════ */

    QMenuBar {{
        background-color: {t['bg_tab_inactive']};
        padding: 2px 8px;
        border-bottom: 1px solid {t['border']};
    }}

    QMenuBar::item {{
        padding: 4px 10px;
        background-color: transparent;
        color: {t['text_primary']};
    }}

    QMenuBar::item:selected {{
        background-color: {t['bg_hover']};
    }}

    QMenu {{
        background-color: {t['bg_tab_inactive']};
        border: 1px solid {t['border']};
        padding: 4px 0;
    }}

    QMenu::item {{
        padding: 6px 32px 6px 16px;
    }}

    QMenu::item:selected {{
        background-color: {t['selection_bg']};
        color: #ffffff;
    }}

    QMenu::separator {{
        height: 1px;
        background-color: {t['border']};
        margin: 4px 8px;
    }}

    /* ═══════════════════════════════════════
       Splitter
       ═══════════════════════════════════════ */

    QSplitter::handle {{
        background-color: {t['border']};
    }}

    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}

    /* ═══════════════════════════════════════
       Tabs
       ═══════════════════════════════════════ */

    QTabWidget::pane {{
        border: none;
        background-color: {t['bg_editor']};
    }}

    QTabBar::tab {{
        background-color: {t['bg_tab_inactive']};
        color: {t['text_secondary']};
        padding: 6px 16px;
        border-right: 1px solid {t['border']};
        font-size: {FONT_SIZE};
    }}

    QTabBar::tab:selected {{
        background-color: {t['bg_editor']};
        color: {t['text_primary']};
        border-top: 2px solid {t['accent']};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: {t['bg_hover']};
        color: {t['text_primary']};
    }}

    /* ═══════════════════════════════════════
       Table
       ═══════════════════════════════════════ */

    QTableWidget {{
        background-color: {t['bg_editor']};
        alternate-background-color: {t['bg_sidebar']};
        gridline-color: {t['border']};
        font-size: {FONT_SIZE_SM};
        border: none;
    }}

    QTableWidget::item {{
        padding: 4px 8px;
        color: {t['text_primary']};
    }}

    QTableWidget::item:selected {{
        background-color: {t['selection_bg']};
        color: #ffffff;
    }}

    QHeaderView::section {{
        background-color: {t['bg_tab_inactive']};
        color: {t['text_primary']};
        padding: 6px 8px;
        font-weight: bold;
        font-size: {FONT_SIZE_SM};
        border: none;
        border-right: 1px solid {t['border']};
        border-bottom: 1px solid {t['border']};
    }}

    QHeaderView::section:hover {{
        background-color: {t['bg_hover']};
    }}

    QTableCornerButton::section {{
        background-color: {t['bg_tab_inactive']};
        border-bottom: 1px solid {t['border']};
    }}

    /* ═══════════════════════════════════════
       Text edit
       ═══════════════════════════════════════ */

    QTextEdit {{
        background-color: {t['bg_editor']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        font-size: {FONT_SIZE};
        selection-background-color: {t['selection_bg']};
    }}

    QTextEdit:focus {{
        border-color: {t['accent']};
    }}

    /* ═══════════════════════════════════════
       Line edit
       ═══════════════════════════════════════ */

    QLineEdit {{
        background-color: {t['bg_input']};
        color: {t['text_primary']};
        border: 1px solid {t['border']};
        padding: 8px 10px;
        font-size: {FONT_SIZE};
        selection-background-color: {t['selection_bg']};
    }}

    QLineEdit:focus {{
        border-color: {t['accent']};
    }}

    /* ═══════════════════════════════════════
       Push button
       ═══════════════════════════════════════ */

    QPushButton {{
        background-color: {t['btn_bg']};
        color: {t['text_primary']};
        border: none;
        padding: 8px 14px;
        font-size: {FONT_SIZE};
    }}

    QPushButton:hover {{
        background-color: {t['btn_bg_hover']};
    }}

    QPushButton:pressed {{
        background-color: {t['btn_bg_pressed']};
    }}

    QPushButton:disabled {{
        background-color: {t['border']};
        color: {t['text_secondary']};
    }}

    /* ═══════════════════════════════════════
       Scroll bars
       ═══════════════════════════════════════ */

    QScrollBar:vertical {{
        background-color: transparent;
        width: 10px; margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background-color: {t['scrollbar_handle']};
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {t['scrollbar_handle_hover']};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{ height: 0px; }}

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background-color: transparent;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 10px; margin: 0;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {t['scrollbar_handle']};
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {t['scrollbar_handle_hover']};
    }}

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{ width: 0px; }}

    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background-color: transparent;
    }}

    /* ═══════════════════════════════════════
       Status bar
       ═══════════════════════════════════════ */

    QStatusBar {{
        background-color: {t['status_bar_bg']};
        color: {t['status_bar_text']};
        font-size: {FONT_SIZE_XS};
        padding: 0 8px;
        border: none;
    }}

    QStatusBar::item {{
        border: none;
    }}

    QStatusBar QLabel {{
        color: {t['status_bar_text']};
        font-size: {FONT_SIZE_XS};
        padding: 0 8px;
        background-color: transparent;
    }}

    /* ═══════════════════════════════════════
       Tool tip
       ═══════════════════════════════════════ */

    QToolTip {{
        background-color: {t['bg_tab_inactive']};
        color: {t['text_primary']};
        border: 1px solid {t['border_strong']};
        padding: 4px 8px;
        font-size: {FONT_SIZE_XS};
    }}

    /* ═══════════════════════════════════════
       Dialogs
       ═══════════════════════════════════════ */

    QMessageBox {{
        background-color: {t['msgbox_bg']};
    }}

    QMessageBox QLabel {{
        color: {t['text_primary']};
    }}

    QDialog {{
        background-color: {t['msgbox_bg']};
    }}
    """

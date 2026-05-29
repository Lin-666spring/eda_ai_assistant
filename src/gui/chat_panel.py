"""
聊天面板组件 — 支持4主题动态切换，现代对话气泡 UI + 流式响应。
"""

from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from .eda_theme import (
    current_theme, FONT_FAMILY,
    _detect_semantic_type, get_semantic_style,
)


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
        .replace("\n", "<br>")
    )


def _ts() -> str:
    return datetime.now().strftime("%H:%M")


class ChatPanel(QWidget):
    message_sent = pyqtSignal(str)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._streaming = False
        self._stream_marker = 0
        self._stream_tokens: list[str] = []
        self._showing_welcome = False
        self._setup_ui()
        self._show_welcome()

    # ── UI ──

    def _setup_ui(self):
        t = current_theme()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setFixedHeight(44)
        self._header.setObjectName("chatHeader")
        self._header.setStyleSheet(
            f"QWidget#chatHeader {{ background-color: transparent; "
            f"border-bottom: 1px solid {t['border']}; }}"
        )
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(16, 0, 10, 0)
        hl.setSpacing(8)

        self._header_title = QLabel("AI 助手")
        self._header_title.setStyleSheet(
            f"color: {t['text_primary']}; font-size: 14px; font-weight: 600; background: transparent;"
        )
        hl.addWidget(self._header_title)
        hl.addStretch()

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setMinimumWidth(64)
        self.clear_btn.setFixedHeight(30)
        self.clear_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.clear_btn.setObjectName("chatClearBtn")
        self._style_clear_btn()
        self.clear_btn.clicked.connect(self._clear_chat)
        hl.addWidget(self.clear_btn)
        layout.addWidget(self._header)

        # Display
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setObjectName("chatDisplay")
        self._style_display()
        layout.addWidget(self.display)

        # Input area
        self._input_container = QWidget()
        self._input_container.setObjectName("chatInputContainer")
        self._input_container.setStyleSheet(
            f"QWidget#chatInputContainer {{ background-color: transparent; "
            f"border-top: 1px solid {t['border']}; }}"
        )
        il = QHBoxLayout(self._input_container)
        il.setContentsMargins(14, 12, 14, 12)
        il.setSpacing(10)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入指令，如「合并 BOM」...")
        self.input_box.setMinimumHeight(40)
        self._style_input_box()
        self.input_box.returnPressed.connect(self._on_send)
        il.addWidget(self.input_box)

        self.send_btn = QPushButton("发送")
        self.send_btn.setMinimumWidth(72)
        self.send_btn.setFixedHeight(40)
        self.send_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._style_send_btn()
        self.send_btn.clicked.connect(self._on_send)
        il.addWidget(self.send_btn)

        layout.addWidget(self._input_container)

    # ── Inline style helpers ──

    def _style_clear_btn(self):
        t = current_theme()
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['border']}; color: {t['text_secondary']};
                border: none; border-radius: 7px;
                padding: 5px 16px; font-size: 12px; font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t['primary']}; color: {t['text_white']};
            }}
        """)

    def _style_display(self):
        t = current_theme()
        self.display.setStyleSheet(f"""
            QTextEdit#chatDisplay {{
                background-color: transparent; border: none;
                padding: 16px 14px; font-size: 13px;
                font-family: {FONT_FAMILY};
            }}
            QScrollBar:vertical {{ background: transparent; width: 6px; margin: 2px; }}
            QScrollBar::handle:vertical {{
                background: {t['scrollbar_handle']}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {t['scrollbar_handle_hover']}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)

    def _style_input_box(self):
        t = current_theme()
        self.input_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t['bg_input']}; color: {t['text_primary']};
                border: 1px solid {t['border']}; border-radius: 8px;
                padding: 10px 14px; font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {t['border_focus']}; padding: 9px 13px;
            }}
        """)

    def _style_send_btn(self):
        t = current_theme()
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['primary']}; color: {t['text_white']};
                border: none; border-radius: 8px;
                padding: 10px 20px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t['primary_hover']}; }}
            QPushButton:pressed {{ background-color: {t['primary_pressed']}; }}
        """)

    # ── Send ──

    def _on_send(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.add_user_message(text)
        self.input_box.clear()
        self.message_sent.emit(text)

    # ── Public message API ──

    def add_user_message(self, text: str):
        self._showing_welcome = False
        self._append_bubble("user", _esc(text))

    def add_ai_message(self, text: str):
        self._showing_welcome = False
        self._append_bubble("ai", _esc(text))

    def add_system_message(self, text: str):
        self._append_system(_esc(text))

    def add_error_message(self, text: str):
        self._append_error(_esc(text))

    def add_config_tip(self, text: str, semantic_type: str = None):
        self._append_config_tip(_esc(text), semantic_type)

    # ── Streaming ──

    def show_thinking(self):
        t = current_theme()
        self._streaming = True
        self._stream_tokens = []
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._stream_marker = cursor.position()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(t["highlight"]))
        cursor.insertText("思考中...", fmt)
        self._end_cursor(cursor)

    def append_stream_token(self, token: str):
        if not self._streaming:
            return
        self._stream_tokens.append(token)
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(current_theme()["chat_text_ai"]))
        cursor.insertText(token, fmt)
        self._end_cursor(cursor)

    def finish_streaming(self, final_text: str):
        if not self._streaming:
            self.add_ai_message(final_text)
            return
        self._streaming = False
        text = "".join(self._stream_tokens) if self._stream_tokens else final_text
        cursor = self.display.textCursor()
        cursor.setPosition(self._stream_marker)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self._append_bubble("ai", _esc(text))

    def cancel_streaming(self):
        """Cancel in-progress streaming and remove placeholder."""
        if not self._streaming:
            return
        self._streaming = False
        cursor = self.display.textCursor()
        cursor.setPosition(self._stream_marker)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()

    # ── Message builders ──

    def _append_bubble(self, side: str, html_text: str):
        t = current_theme()
        if side == "user":
            bg, fg, time_c = t["chat_bubble_user"], t["chat_text_user"], t["chat_time_user"]
            align, radius, label = "right", "12px 12px 0 12px", ""
        else:
            bg, fg, time_c = t["chat_bubble_ai"], t["chat_text_ai"], t["chat_time_ai"]
            align, radius = "left", "0 12px 12px 12px"
            label = (
                f'<span style="color:{t["text_muted"]};font-size:11px;font-weight:600;">AI</span>'
                f'<span style="color:{t["text_muted"]};font-size:10px;margin-left:8px;">{_ts()}</span><br>'
            )

        html = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td align="{align}">'
            f'<table cellpadding="0" cellspacing="0" border="0" style="max-width:85%;display:inline-table;">'
            f'<tr><td style="background-color:{bg};border-radius:{radius};padding:10px 14px;">'
            f'{label}'
            f'<span style="color:{fg};font-size:13px;line-height:1.6;">{html_text}</span><br>'
            f'<span style="color:{time_c};font-size:10px;float:right;margin-top:2px;">{_ts()}</span>'
            f'</td></tr></table></td></tr></table>'
            f'<div style="height:6px;"></div>'
        )
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self._end_cursor(cursor)

    def _append_system(self, html_text: str):
        t = current_theme()
        html = (
            f'<span style="color:{t["chat_text_sys"]};font-size:11px;">{html_text}</span>'
        )
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertBlock()
        cursor.insertHtml(html)
        self._end_cursor(cursor)

    def _append_error(self, html_text: str):
        s = get_semantic_style("error")
        html = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td align="center">'
            f'<table cellpadding="0" cellspacing="0" border="0" style="max-width:90%;display:inline-table;">'
            f'<tr><td style="background-color:{s["bg"]};border-left:3px solid {s["border"]};'
            f'border-radius:0 6px 6px 0;padding:8px 14px;">'
            f'<span style="color:{s["text"]};font-size:12px;">{html_text}</span>'
            f'</td></tr></table></td></tr></table>'
            f'<div style="height:6px;"></div>'
        )
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self._end_cursor(cursor)

    def _append_config_tip(self, html_text: str, semantic_type: str = None):
        """Semantic status tip — auto-detects type from content keywords."""
        if semantic_type is None:
            semantic_type = _detect_semantic_type(html_text)
        s = get_semantic_style(semantic_type)
        html = (
            f'<div style="height:8px;"></div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr><td align="left">'
            f'<table cellpadding="0" cellspacing="0" border="0" style="max-width:95%;display:inline-table;">'
            f'<tr><td style="background-color:{s["bg"]};'
            f'border:1px solid {s["border"]};'
            f'border-radius:6px;padding:10px 14px;">'
            f'<span style="color:{s["text"]};font-size:11px;line-height:1.5;">{html_text}</span>'
            f'</td></tr></table></td></tr></table>'
            f'<div style="height:4px;"></div>'
        )
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self._end_cursor(cursor)

    # ── Helpers ──

    def _end_cursor(self, cursor: QTextCursor):
        self.display.setTextCursor(cursor)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        sb = self.display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_chat(self):
        self._streaming = False
        self._stream_tokens = []
        self.display.clear()
        self._show_welcome()
        self.clear_requested.emit()

    def _show_welcome(self):
        """Structured welcome: Title → Features → Guide — left-aligned, clean dividers."""
        t = current_theme()
        features = [
            ("合并 BOM", "合并同类元件"),
            ("封装校验", "校验封装与型号匹配"),
            ("位号查重", "检查重复位号"),
            ("HTML BOM", "生成交互式 HTML BOM"),
            ("设计规则检查", "PCB 设计规则检查"),
        ]
        feature_rows = "".join(
            f'<tr>'
            f'<td style="padding:2px 0;color:{t["highlight"]};font-size:12px;font-weight:500;white-space:nowrap;">'
            f'{name}</td>'
            f'<td style="padding:2px 6px;color:{t["text_muted"]};font-size:12px;">—</td>'
            f'<td style="padding:2px 0;color:{t["text_muted"]};font-size:12px;">{desc}</td>'
            f'</tr>'
            for name, desc in features
        )

        card_bg = t["bg_card_hover"]
        card_border = t["border"]
        card_style = (
            f'background-color:{card_bg};border:1px solid {card_border};'
            f'border-radius:10px;padding:12px 16px;'
        )
        # Helper: wrap content in the same card pattern as _append_config_tip
        def _card(body: str, gap: int = 10) -> str:
            return (
                f'<div style="height:{gap}px;"></div>'
                f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
                f'<tr><td align="left">'
                f'<table cellpadding="0" cellspacing="0" border="0"'
                f' style="max-width:95%;display:inline-table;">'
                f'<tr><td style="{card_style}">{body}</td></tr>'
                f'</table></td></tr></table>'
            )

        feature_body = (
            f'<div style="color:{t["text_secondary"]};font-size:11px;font-weight:600;padding:0 0 6px 0;">'
            f'可用功能</div>'
            f'<table cellpadding="0" cellspacing="0" border="0">{feature_rows}</table>'
        )
        guide_body = (
            f'<div style="color:{t["text_muted"]};font-size:11px;line-height:1.6;">'
            f'请先导入 BOM 文件，然后在下方输入指令开始使用。</div>'
        )

        html = (
            f'<div style="padding:10px 0 4px 0;">'
            f'<span style="color:{t["primary"]};font-size:24px;font-weight:700;">EDA</span>'
            f'<span style="color:{t["text_primary"]};font-size:24px;font-weight:300;"> AI 智能助手</span>'
            f'</div>'
            f'<div style="color:{t["text_secondary"]};font-size:11px;padding:0 0 10px 0;">'
            f'面向立创 EDA 的 BOM 管理与 PCB 设计助手</div>'
            + _card(feature_body, gap=10)
            + _card(guide_body, gap=10)
            + f'<div style="height:2px;"></div>'
        )
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self._end_cursor(cursor)
        self._showing_welcome = True

    # ── Theme refresh ──

    def refresh_theme(self):
        """Re-apply all inline styles after theme switch."""
        t = current_theme()
        # Header
        self._header.setStyleSheet(
            f"QWidget#chatHeader {{ background-color: transparent; "
            f"border-bottom: 1px solid {t['border']}; }}"
        )
        self._header_title.setStyleSheet(
            f"color: {t['text_primary']}; font-size: 14px; font-weight: 600; background: transparent;"
        )
        # Buttons
        self._style_clear_btn()
        self._style_send_btn()
        # Display + input
        self._style_display()
        self._style_input_box()
        # Container
        self._input_container.setStyleSheet(
            f"QWidget#chatInputContainer {{ background-color: transparent; "
            f"border-top: 1px solid {t['border']}; }}"
        )
        re_rendered = False
        if self._showing_welcome:
            self.display.clear()
            self._showing_welcome = False
            self._show_welcome()
            re_rendered = True
        return re_rendered

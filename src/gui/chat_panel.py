"""
聊天面板组件 — 提供与 AI Agent 对话的交互界面。

Supports both static message display and incremental streaming.
"""

from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .vscode_theme import current_theme


class ChatPanel(QWidget):
    """AI 对话面板 — 支持流式和非流式两种响应模式."""

    message_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._streaming = False
        self._stream_content_start = 0
        self._setup_ui()

    # ── UI construction ──

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Title bar (VS Code panel style)
        self._title_bar = QWidget()
        self._title_bar.setStyleSheet("padding: 8px;")
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(12, 6, 12, 6)

        self._title_label = QLabel("AI 助手对话")
        self._title_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        title_layout.addWidget(self._title_label)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.clicked.connect(self._clear_chat)
        title_layout.addWidget(self.clear_btn)
        layout.addWidget(self._title_bar)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)

        # Input area
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入你的指令，如「帮我合并BOM中所有10k电阻」...")
        self.input_box.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_box)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedWidth(70)
        self.send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_widget)

        # Apply initial theme styles
        self.refresh_theme()

        # Welcome message
        self.add_system_message(
            "欢迎使用 EDA AI 智能助手！\n\n"
            "我可以帮你：\n"
            "  BOM 合并     — 合并同类元件\n"
            "  封装校验     — 校验封装与型号匹配\n"
            "  位号查重     — 检查重复位号\n"
            "  HTML BOM    — 生成交互式 HTML BOM\n"
            "  设计规则检查  — 检查设计规则\n\n"
            "请先导入 BOM 文件，然后在下方输入指令。"
        )

    # ── Send ──

    def _on_send(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.add_user_message(text)
        self.input_box.clear()
        self.message_sent.emit(text)

    # ── Static messages ──

    def add_user_message(self, text: str):
        self._append_message("[用户]", text, QColor(current_theme()["chat_header_user"]))

    def add_ai_message(self, text: str):
        self._append_message("[AI]", text, QColor(current_theme()["chat_header_ai"]))

    def add_system_message(self, text: str):
        self._append_message("[系统]", text, QColor(current_theme()["chat_header_sys"]))

    def add_error_message(self, text: str):
        self._append_message("[错误]", text, QColor(current_theme()["chat_header_err"]))

    # ── Internal helpers (cursor/builder) ──

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def _insert_header(cursor, sender: str, color: QColor):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold)
        fmt.setForeground(color)
        cursor.insertText(f"\n[{ChatPanel._timestamp()}] {sender}\n", fmt)

    @staticmethod
    def _insert_separator(cursor, color: QColor = None):
        fmt = QTextCharFormat()
        if color is None:
            color = QColor(current_theme()["chat_separator"])
        fmt.setForeground(color)
        cursor.insertText("─" * 40 + "\n", fmt)

    @staticmethod
    def _insert_text(cursor, text: str, color: QColor):
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.insertText(text, fmt)

    def _end_cursor(self, cursor):
        self.chat_display.setTextCursor(cursor)
        self._scroll_to_bottom()

    # ── Streaming support ──

    def show_thinking(self):
        self._streaming = True
        t = current_theme()
        self._stream_theme = t

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        self._insert_header(cursor, "[AI]", QColor(t["chat_header_ai"]))
        self._stream_content_start = cursor.position()
        self._insert_text(cursor, "思考中...\n", QColor(t["text_secondary"]))

        self._end_cursor(cursor)

    def append_stream_token(self, token: str):
        if not self._streaming:
            return

        t = self._stream_theme
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._insert_text(cursor, token, QColor(t["chat_text"]))
        self._end_cursor(cursor)

    def finish_streaming(self, final_text: str):
        if not self._streaming:
            self.add_ai_message(final_text)
            return

        self._streaming = False
        t = self._stream_theme

        cursor = self.chat_display.textCursor()
        cursor.setPosition(self._stream_content_start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        self._insert_text(cursor, final_text + "\n", QColor(t["chat_text"]))
        self._insert_separator(cursor)
        self._end_cursor(cursor)

    # ── Internal helpers ──

    def _append_message(self, sender: str, text: str, sender_color: QColor):
        """Append a message using current theme colours."""
        t = current_theme()
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._insert_header(cursor, sender, sender_color)
        self._insert_text(cursor, text + "\n", QColor(t["chat_text"]))
        self._insert_separator(cursor, QColor(t["chat_separator"]))
        self._end_cursor(cursor)

    def _clear_chat(self):
        self.chat_display.clear()
        self.add_system_message("对话已清空。")

    def _scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def refresh_theme(self):
        """Re-apply inline styles from the current theme."""
        t = current_theme()
        self.setStyleSheet(f"background-color: {t['bg_sidebar']};")

        # Title bar
        self._title_bar.setStyleSheet(
            f"background-color: {t['title_bar_bg']}; padding: 8px;"
        )
        self._title_label.setStyleSheet(
            f"color: {t['title_bar_text']}; font-size: 13px; font-weight: bold;"
        )

        # Chat display
        self.chat_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t['chat_bg']};
                border: 1px solid {t['chat_border']};
                padding: 8px;
                font-size: 13px;
                color: {t['text_primary']};
            }}
        """)
        self.input_box.setStyleSheet(f"""
            QLineEdit {{
                padding: 10px;
                border: 1px solid {t['border']};
                font-size: 13px;
                background-color: {t['bg_input']};
                color: {t['text_primary']};
            }}
            QLineEdit:focus {{ border-color: {t['accent']}; }}
        """)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['btn_bg']}; color: {t['text_primary']};
                border: none; padding: 10px; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t['btn_bg_hover']}; }}
            QPushButton:pressed {{ background-color: {t['btn_bg_pressed']}; }}
        """)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['border']}; color: {t['text_primary']};
                border: none; padding: 4px 8px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {t['bg_hover']}; }}
        """)
        # Re-colour existing messages
        cursor = self.chat_display.textCursor()
        cursor.select(QTextCursor.Document)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(t['text_primary']))
        cursor.mergeCharFormat(fmt)

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

        # Title bar
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #2c3e50; padding: 8px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 6, 12, 6)

        title_label = QLabel("🤖 AI 助手对话")
        title_label.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        title_layout.addWidget(title_label)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.clicked.connect(self._clear_chat)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e; color: white;
                border: none; border-radius: 4px; padding: 4px 8px;
            }
            QPushButton:hover { background-color: #4a6785; }
        """)
        title_layout.addWidget(self.clear_btn)
        layout.addWidget(title_bar)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.chat_display)

        # Input area
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入你的指令，如「帮我合并BOM中所有10k电阻」...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #3498db; }
        """)
        self.input_box.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_box)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedWidth(70)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                border: none; border-radius: 6px;
                padding: 10px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #2471a3; }
        """)
        self.send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(input_widget)

        # Welcome message
        self.add_system_message(
            "👋 欢迎使用 EDA AI 智能助手！\n\n"
            "我可以帮你：\n"
            "• 📦 合并 BOM 同类元件\n"
            "• ✅ 校验封装与型号匹配\n"
            "• 🔍 检查重复位号\n"
            "• 🌐 生成交互式 HTML BOM\n"
            "• 📏 设计规则检查\n\n"
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
        self._append_message("👤 你", text, QColor("#2c3e50"), QColor("#ecf0f1"))

    def add_ai_message(self, text: str):
        self._append_message("🤖 AI", text, QColor("#1a5276"), QColor("#d6eaf8"))

    def add_system_message(self, text: str):
        self._append_message("ℹ️ 系统", text, QColor("#7d7d7d"), QColor("#f8f9fa"))

    def add_error_message(self, text: str):
        self._append_message("❌ 错误", text, QColor("#922b21"), QColor("#fadbd8"))

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
    def _insert_separator(cursor):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e0e0e0"))
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

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        self._insert_header(cursor, "🤖 AI", QColor("#1a5276"))
        self._stream_content_start = cursor.position()
        self._insert_text(cursor, "思考中... ⏳\n", QColor("#7f8c8d"))

        self._end_cursor(cursor)

    def append_stream_token(self, token: str):
        if not self._streaming:
            return

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._insert_text(cursor, token, QColor("#7f8c8d"))
        self._end_cursor(cursor)

    def finish_streaming(self, final_text: str):
        if not self._streaming:
            self.add_ai_message(final_text)
            return

        self._streaming = False

        cursor = self.chat_display.textCursor()
        cursor.setPosition(self._stream_content_start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        self._insert_text(cursor, final_text + "\n", QColor("#2c3e50"))
        self._insert_separator(cursor)
        self._end_cursor(cursor)

    # ── Internal helpers ──

    def _append_message(self, sender: str, text: str, sender_color: QColor, _bg_color: QColor):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        self._insert_header(cursor, sender, sender_color)
        self._insert_text(cursor, text + "\n", QColor("#2c3e50"))
        self._insert_separator(cursor)
        self._end_cursor(cursor)

    def _clear_chat(self):
        self.chat_display.clear()
        self.add_system_message("对话已清空。")

    def _scroll_to_bottom(self):
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

"""
PyQt5 主窗口 — EDA AI 助手桌面应用入口。

架构：MainWindow (UI) → AppController (业务逻辑)
MainWindow 只负责「展示」和「接线」，所有业务逻辑在 AppController 中。
"""

import logging
import webbrowser
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .chat_panel import ChatPanel
from .bom_table import BOMTableView
from ..core.controller import AppController

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  Worker thread — keeps AI calls off the UI thread
# ══════════════════════════════════════════════════════


class AIWorker(QThread):
    """Runs ``controller.process_input`` in a background thread."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    token = pyqtSignal(str)

    def __init__(self, controller: AppController, user_input: str):
        super().__init__()
        self._controller = controller
        self._user_input = user_input

    def run(self):
        try:
            result = self._controller.process_input_stream(
                self._user_input, on_token=self.token.emit
            )
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("AIWorker failed")
            self.error.emit(str(exc))


# ══════════════════════════════════════════════════════
#  Main window
# ══════════════════════════════════════════════════════


class MainWindow(QMainWindow):
    """EDA AI 智能助手主窗口。

    Owns an :class:`AppController` and wires every UI action to it.
    """

    APP_TITLE = "EDA AI 智能助手 — 面向立创EDA的BOM管理与PCB设计"
    APP_VERSION = "0.1.0"
    REPORT_TAB_INDEX = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{self.APP_TITLE} v{self.APP_VERSION}")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        # ── Controller (single source of truth for business logic) ──
        self.controller = AppController()

        # ── Build UI ──
        self._setup_menu_bar()
        self._setup_tool_bar()
        self._setup_central_widget()
        self._setup_status_bar()
        self._connect_signals()
        self._apply_style()

    # ══════════════════════════════════════════════════
    #  Menu bar
    # ══════════════════════════════════════════════════

    def _setup_menu_bar(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction("导入 BOM 文件(&B)", self._on_import_bom, "Ctrl+O")
        file_menu.addAction("导入坐标文件(&P)", self._on_import_positions, "Ctrl+Shift+O")
        file_menu.addSeparator()
        file_menu.addAction("导出合并 BOM(&E)", self._on_export_bom, "Ctrl+S")
        file_menu.addAction("生成 HTML BOM(&H)", self._on_generate_html_bom, "Ctrl+G")
        file_menu.addSeparator()
        file_menu.addAction("退出(&Q)", self.close, "Alt+F4")

        tool_menu = mb.addMenu("工具(&T)")
        tool_menu.addAction("BOM 合并", self._on_bom_merge)
        tool_menu.addAction("封装校验", self._on_validate_package)
        tool_menu.addAction("位号查重", self._on_check_duplicates)
        tool_menu.addSeparator()
        tool_menu.addAction("设计规则检查", self._on_design_rule_check)

        help_menu = mb.addMenu("帮助(&H)")
        help_menu.addAction("使用手册", self._on_show_help)
        help_menu.addAction("关于", self._on_show_about)

    # ══════════════════════════════════════════════════
    #  Tool bar
    # ══════════════════════════════════════════════════

    def _setup_tool_bar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction("📂 导入BOM", self._on_import_bom)
        tb.addAction("🔄 合并BOM", self._on_bom_merge)
        tb.addAction("✅ 封装校验", self._on_validate_package)
        tb.addAction("🔍 位号查重", self._on_check_duplicates)
        tb.addSeparator()
        tb.addAction("🌐 生成HTML BOM", self._on_generate_html_bom)

    # ══════════════════════════════════════════════════
    #  Central widget
    # ══════════════════════════════════════════════════

    def _setup_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Horizontal)

        # ── Left: Chat panel ──
        self.chat_panel = ChatPanel()
        splitter.addWidget(self.chat_panel)

        # ── Right: Tab widget ──
        self.right_tabs = QTabWidget()

        self.bom_table = BOMTableView()
        self.right_tabs.addTab(self.bom_table, "📊 BOM 表格")

        # HTML BOM preview (read-only rich-text)
        self.html_preview = QTextEdit()
        self.html_preview.setReadOnly(True)
        self.html_preview.setPlaceholderText("HTML BOM 预览将在生成后显示于此")
        self.right_tabs.addTab(self.html_preview, "🌐 HTML BOM")

        # Report view (monospace, scrollable)
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        font = QFont("Consolas, Microsoft YaHei", 10)
        self.report_view.setFont(font)
        self.report_view.setPlaceholderText("校验 / 合并报告将显示于此")
        self.right_tabs.addTab(self.report_view, "📋 报告")

        splitter.addWidget(self.right_tabs)
        splitter.setSizes([500, 700])
        layout.addWidget(splitter)

    # ══════════════════════════════════════════════════
    #  Status bar
    # ══════════════════════════════════════════════════

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_label = QLabel("就绪")
        self.status_bar.addWidget(self._status_label)
        self.status_bar.showMessage("欢迎使用 EDA AI 智能助手 | 请导入 BOM 文件开始")
        self._update_agent_status()

    def _update_agent_status(self):
        if self.controller.is_agent_available():
            self.chat_panel.add_system_message("✅ DeepSeek AI Agent 已就绪")
        else:
            self.chat_panel.add_system_message(
                "⚠️ 未配置 DeepSeek API Key。将使用本地关键词匹配模式。\n"
                "请在项目根目录的 .env 文件中设置 DEEPSEEK_API_KEY。"
            )

    # ══════════════════════════════════════════════════
    #  Signal wiring — the critical integration
    # ══════════════════════════════════════════════════

    def _connect_signals(self):
        """Wire UI events → controller → UI feedback."""
        self.chat_panel.message_sent.connect(self._on_user_message)

    # ══════════════════════════════════════════════════
    #  User message handler (AI + local fallback)
    # ══════════════════════════════════════════════════

    def _on_user_message(self, text: str):
        """Handle a natural-language command from the chat panel."""
        if not self.controller.context.has_data:
            self.chat_panel.add_system_message("⚠️ 请先导入 BOM 文件再输入指令。")
            return

        self.chat_panel.show_thinking()
        self._set_buttons_enabled(False)

        self._worker = AIWorker(self.controller, text)
        self._worker.finished.connect(self._on_ai_finished)
        self._worker.error.connect(self._on_ai_error)
        self._worker.token.connect(self._on_ai_token)
        self._worker.start()

    def _on_ai_token(self, token: str):
        self.chat_panel.append_stream_token(token)

    def _on_ai_finished(self, result: str):
        self.chat_panel.finish_streaming(result)
        self._show_report(result)
        self._set_buttons_enabled(True)

    def _on_ai_error(self, error_msg: str):
        self.chat_panel.add_error_message(f"AI 处理失败: {error_msg}")
        self.chat_panel.add_system_message("已回退到本地关键词匹配模式。")
        # Retry with local-only fallback
        fallback = self.controller._local_fallback(
            self.chat_panel.input_box.text()
        )
        if fallback:
            self.chat_panel.add_ai_message(fallback)
            self._show_report(fallback)
        self._set_buttons_enabled(True)

    # ══════════════════════════════════════════════════
    #  File operations
    # ══════════════════════════════════════════════════

    def _on_import_bom(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 BOM 文件", "",
            "BOM 文件 (*.csv *.xlsx *.xls);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            count, msg = self.controller.load_bom(path)
            self.bom_table.load_items(self.controller.context.bom_items)
            self.status_bar.showMessage(f"已加载: {Path(path).name} ({count} 条)")
            self.chat_panel.add_system_message(msg)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))
            logger.exception("BOM import failed")

    def _on_import_positions(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择坐标文件 (Pick & Place CSV)", "",
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            count, msg = self.controller.load_positions(path)
            self.chat_panel.add_system_message(msg)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", str(exc))
            logger.exception("Position import failed")

    def _on_export_bom(self):
        if not self.controller.context.has_data:
            QMessageBox.information(self, "提示", "请先导入 BOM 文件")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出合并 BOM", "merged_bom.xlsx",
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)",
        )
        if not path:
            return
        try:
            self._save_dataframe(self._merged_to_dataframe(), path)
            self.status_bar.showMessage(f"已导出到: {path}")
            self.chat_panel.add_system_message(f"✅ BOM 已导出: {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def _merged_to_dataframe(self):
        from ..bom.merger import BOMMerger
        from ..bom.parser import BOMParser

        merger = BOMMerger()
        merged = merger.merge(self.controller.context.bom_items)
        # Convert MergedBOMItem → BOMItem for DataFrame serialisation
        items = [
            type(self.controller.context.bom_items[0])(
                reference=m.reference_str,
                value=m.value,
                package=m.package,
                part_number=m.part_number,
                description=m.description,
                quantity=m.total_quantity,
                manufacturer=m.manufacturer,
            )
            for m in merged
        ]
        return BOMParser().to_dataframe(items)

    @staticmethod
    def _save_dataframe(df, file_path: str):
        if file_path.endswith(".csv"):
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
        else:
            df.to_excel(file_path, index=False)

    # ══════════════════════════════════════════════════
    #  Tool actions — each delegates to controller
    # ══════════════════════════════════════════════════

    def _on_bom_merge(self):
        self._run_operation("🔄 正在执行 BOM 合并...", self.controller.merge_bom)

    def _on_validate_package(self):
        self._run_operation("🔍 正在校验封装...", self.controller.validate_packages)

    def _on_check_duplicates(self):
        self._run_operation("🔍 正在检查位号重复...", self.controller.check_duplicates)

    def _on_generate_html_bom(self):
        if not self.controller.context.has_data:
            QMessageBox.information(self, "提示", "请先导入 BOM 文件")
            return

        def _run():
            return self.controller.generate_html_bom()

        self._run_operation("🌐 正在生成 HTML BOM...", _run)
        # Also try to load the result into the preview tab
        output_path = str(
            Path(__file__).parent.parent.parent / "output" / "ibom.html"
        )
        try:
            from pathlib import Path
            if Path(output_path).exists():
                with open(output_path, "r", encoding="utf-8") as f:
                    self.html_preview.setHtml(f.read())
                self.right_tabs.setCurrentIndex(1)  # switch to HTML tab
        except Exception:
            pass

    def _on_design_rule_check(self):
        self._run_operation("📏 正在执行设计规则检查...", self.controller.check_design_rules)

    # ══════════════════════════════════════════════════
    #  Generic operation runner
    # ══════════════════════════════════════════════════

    def _run_operation(self, progress_msg: str, handler: Callable[[], str]):
        """Execute a BOM operation and route its report to the report tab."""
        self.chat_panel.add_system_message(progress_msg)
        try:
            report = handler()
            self._show_report(report)
            self.chat_panel.add_system_message("✅ 操作完成")
        except Exception as exc:
            self.chat_panel.add_error_message(f"操作失败: {exc}")
            logger.exception("Operation failed")

    def _show_report(self, text: str):
        """Display a report in the report tab."""
        self.report_view.setPlainText(text)
        self.right_tabs.setCurrentIndex(self.REPORT_TAB_INDEX)

    # ══════════════════════════════════════════════════
    #  Help / About
    # ══════════════════════════════════════════════════

    def _on_show_help(self):
        QMessageBox.information(
            self, "使用手册",
            "详细使用手册请参阅 docs/ 目录下的文档。\n\n"
            "快速开始：\n"
            "1. 文件 → 导入 BOM 文件\n"
            "2. 在聊天框输入指令或使用工具栏按钮\n"
            "3. 查看右侧报告标签页获取结果",
        )

    def _on_show_about(self):
        QMessageBox.about(
            self, "关于 EDA AI 智能助手",
            f"<h3>EDA AI 智能助手 v{self.APP_VERSION}</h3>"
            "<p>面向立创EDA的AI智能辅助设计软件<br>"
            "内置 Agent 的 BOM 管理与 PCB 设计助手</p>"
            "<p>吉林大学 · 测控技术与仪器专业<br>"
            "创新训练项目 © 2026</p>",
        )

    # ══════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════

    def _set_buttons_enabled(self, enabled: bool):
        """Toggle toolbar buttons during AI processing."""
        for tb in self.findChildren(QToolBar):
            for action in tb.actions():
                action.setEnabled(enabled)
        self.chat_panel.send_btn.setEnabled(enabled)
        self.chat_panel.input_box.setEnabled(enabled)

    # ══════════════════════════════════════════════════
    #  Style
    # ══════════════════════════════════════════════════

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QToolBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e0e0e0;
                padding: 4px;
                spacing: 6px;
            }
            QToolBar QToolButton {
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 13px;
            }
            QToolBar QToolButton:hover {
                background-color: #e8f0fe;
            }
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                background-color: #ffffff;
            }
            QTabBar::tab {
                padding: 8px 16px;
                font-size: 13px;
            }
            QStatusBar {
                background-color: #ffffff;
                border-top: 1px solid #e0e0e0;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                font-size: 13px;
            }
        """)

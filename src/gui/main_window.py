"""
PyQt5 主窗口 — EDA AI 助手桌面应用入口。

架构：MainWindow (UI) → AppController (业务逻辑)
MainWindow 只负责「展示」和「接线」，所有业务逻辑在 AppController 中。

VS Code 风格布局：
  活动栏(48px) | 侧边栏(300px) | 主内容区(标签页 + 底部面板)
  状态栏
"""

import logging
import webbrowser
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .chat_panel import ChatPanel
from .bom_table import BOMTableView
from .settings_panel import SettingsPanel
from .vscode_theme import compile_stylesheet, toggle_theme, is_dark, current_theme, FONT_MONO
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
#  Activity-bar button style constant
# ══════════════════════════════════════════════════════

_ACTIVITY_BTN_STYLE = """
    QPushButton {{
        background-color: transparent;
        color: {text};
        border: none;
        border-left: 2px solid transparent;
        font-size: 18px;
        padding: 12px 0;
    }}
    QPushButton:hover {{
        background-color: {hover};
    }}
    QPushButton[active="true"] {{
        border-left: 2px solid {accent};
    }}
"""


# ══════════════════════════════════════════════════════
#  Main window
# ══════════════════════════════════════════════════════


class MainWindow(QMainWindow):
    """EDA AI 智能助手主窗口 — VS Code 风格布局."""

    APP_TITLE = "EDA AI 智能助手 — 面向立创EDA的BOM管理与PCB设计"
    APP_VERSION = "0.2.0"
    REPORT_TAB_INDEX = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{self.APP_TITLE} v{self.APP_VERSION}")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        # ── Controller ──
        self.controller = AppController()

        # ── Build UI ──
        self._setup_menu_bar()
        self._setup_central_area()
        self._setup_status_bar()
        self._connect_signals()
        self._apply_style()
        self._refresh_inline_styles()

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
    #  Central area — activity bar | sidebar | main
    # ══════════════════════════════════════════════════

    def _setup_central_area(self):
        """Build the VS Code three-column layout."""
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Activity bar (48px fixed) ──
        root.addWidget(self._build_activity_bar())

        # ── Sidebar (300px) + Main area splitter ──
        self._build_sidebar()
        self.main_area = self._build_main_area()

        self.body_splitter = QSplitter(Qt.Horizontal)
        self.body_splitter.setHandleWidth(1)
        self.body_splitter.addWidget(self.sidebar_stack)
        self.body_splitter.addWidget(self.main_area)
        self.body_splitter.setSizes([300, 980])
        root.addWidget(self.body_splitter)

    def _build_activity_bar(self) -> QWidget:
        """Leftmost 48px icon column."""
        self._activity_bar = QWidget()
        self._activity_bar.setFixedWidth(48)

        layout = QVBoxLayout(self._activity_bar)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(2)

        self._activity_btns = []

        def _add_btn(icon: str, tooltip: str, sidebar_index: int):
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedSize(48, 48)
            btn.clicked.connect(lambda idx=sidebar_index: self._switch_sidebar(idx))
            layout.addWidget(btn)
            self._activity_btns.append(btn)
            return btn

        self._act_chat = _add_btn("💬", "AI 对话 (Ctrl+1)", 0)
        self._act_bom = _add_btn("📊", "BOM 操作 (Ctrl+2)", 1)
        self._act_report = _add_btn("📋", "报告 (Ctrl+3)", 2)
        self._act_settings = _add_btn("⚙", "设置 (Ctrl+4)", 3)

        layout.addStretch()

        # Theme toggle at bottom
        self._theme_btn = QPushButton("🌓")
        self._theme_btn.setToolTip("切换浅色/深色主题")
        self._theme_btn.setFixedSize(48, 48)
        self._theme_btn.clicked.connect(self._on_toggle_theme)
        layout.addWidget(self._theme_btn)

        # Default selection
        self._act_chat.setChecked(True)
        self._act_chat.setProperty("active", True)

        # Apply initial theme styles
        self._refresh_activity_bar_styles()

        return self._activity_bar

    def _switch_sidebar(self, index: int):
        """Switch sidebar panel and update button states."""
        self.sidebar_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._activity_btns):
            btn.setChecked(i == index)
            btn.setProperty("active", i == index)
        self._refresh_activity_bar_styles()

    def _build_sidebar(self) -> QStackedWidget:
        """Sidebar with stacked panels."""
        self.sidebar_stack = QStackedWidget()

        # Panel 0 — Chat
        self.chat_panel = ChatPanel()
        self.sidebar_stack.addWidget(self.chat_panel)

        # Panel 1 — BOM quick-actions
        self.sidebar_stack.addWidget(self._build_bom_actions_panel())

        # Panel 2 — Report quick view
        self.sidebar_stack.addWidget(self._build_report_panel())

        # Panel 3 — Settings
        self.sidebar_stack.addWidget(self._build_settings_panel())

        return self.sidebar_stack

    def _build_bom_actions_panel(self) -> QWidget:
        """BOM quick actions sidebar panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._bom_actions_title = QLabel("BOM 操作")
        self._bom_actions_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._bom_actions_title)

        def _btn(label: str, handler):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            layout.addWidget(btn)
            return btn

        _btn("📂 导入 BOM 文件", self._on_import_bom)
        _btn("📍 导入坐标文件", self._on_import_positions)
        _btn("🔄 合并 BOM", self._on_bom_merge)
        _btn("✅ 封装校验", self._on_validate_package)
        _btn("🔍 位号查重", self._on_check_duplicates)
        _btn("📏 设计规则检查", self._on_design_rule_check)
        _btn("🌐 生成 HTML BOM", self._on_generate_html_bom)
        _btn("💾 导出合并 BOM", self._on_export_bom)

        layout.addStretch()
        return panel

    def _build_report_panel(self) -> QWidget:
        """Report quick-view sidebar panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._report_panel_title = QLabel("报告")
        self._report_panel_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._report_panel_title)

        self.sidebar_report = QTextEdit()
        self.sidebar_report.setReadOnly(True)
        self.sidebar_report.setPlaceholderText("执行操作后，报告将显示在此")
        self.sidebar_report.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.sidebar_report)
        return panel

    def _build_settings_panel(self) -> QWidget:
        """Settings panel with LLM configuration form."""
        self.settings_panel = SettingsPanel()
        self.settings_panel.settings_applied.connect(self._on_settings_applied)
        return self.settings_panel

    def _build_main_area(self) -> QWidget:
        """Main content: tab widget on top, collapsible output panel below."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Tab widget ──
        self.right_tabs = QTabWidget()

        self.bom_table = BOMTableView()
        self.right_tabs.addTab(self.bom_table, "BOM 表格")

        self.html_preview = QTextEdit()
        self.html_preview.setReadOnly(True)
        self.html_preview.setPlaceholderText("HTML BOM 预览将在生成后显示于此")
        self.right_tabs.addTab(self.html_preview, "HTML BOM")

        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        font = QFont(FONT_MONO, 10)
        self.report_view.setFont(font)
        self.report_view.setPlaceholderText("校验 / 合并报告将显示于此")
        self.right_tabs.addTab(self.report_view, "报告")

        # ── Bottom output panel (collapsible) ──
        self.panel_splitter = QSplitter(Qt.Vertical)
        self.panel_splitter.setHandleWidth(1)
        self.panel_splitter.addWidget(self.right_tabs)

        self.output_panel = self._build_output_panel()
        self.output_panel.setVisible(False)
        self.panel_splitter.addWidget(self.output_panel)
        self.panel_splitter.setSizes([600, 0])

        layout.addWidget(self.panel_splitter)
        return container

    def _build_output_panel(self) -> QWidget:
        """Bottom log panel (VS Code terminal style)."""
        self._output_panel_container = QWidget()
        layout = QVBoxLayout(self._output_panel_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        self._output_title_bar = QWidget()
        self._output_title_bar.setFixedHeight(28)
        tb_layout = QHBoxLayout(self._output_title_bar)
        tb_layout.setContentsMargins(12, 0, 8, 0)
        tb_layout.setSpacing(8)

        self._output_title_label = QLabel("输出")
        self._output_title_label.setStyleSheet("font-size: 11px; font-weight: bold;")
        tb_layout.addWidget(self._output_title_label)
        tb_layout.addStretch()

        self._output_close_btn = QPushButton("✕")
        self._output_close_btn.setFixedSize(20, 20)
        self._output_close_btn.clicked.connect(lambda: self.output_panel.setVisible(False))
        tb_layout.addWidget(self._output_close_btn)

        layout.addWidget(self._output_title_bar)

        self.output_log = QTextEdit()
        self.output_log.setReadOnly(True)
        font = QFont(FONT_MONO, 10)
        self.output_log.setFont(font)
        self.output_log.setStyleSheet("border: none; font-size: 12px;")
        layout.addWidget(self.output_log)

        return self._output_panel_container

    # ══════════════════════════════════════════════════
    #  Status bar
    # ══════════════════════════════════════════════════

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self._status_message = QLabel("欢迎使用 EDA AI 智能助手")
        self.status_bar.addWidget(self._status_message)

        # Right-side info: LLM provider / model
        provider = self.controller.agent.provider_label if self.controller.agent else "LLM"
        self._status_provider = QLabel(provider)
        self.status_bar.addPermanentWidget(self._status_provider)

        self._update_agent_status()

    def _update_agent_status(self):
        if self.controller.is_agent_available():
            agent = self.controller.agent
            self._status_provider.setText(f"{agent.provider_label}  {agent.model}")
            self.chat_panel.add_system_message(f"[系统] {agent.provider_label} AI Agent 已就绪")
        else:
            self._status_provider.setText("无 API Key")
            self.chat_panel.add_system_message(
                "[系统] 未配置 LLM API Key。将使用本地关键词匹配模式。\n"
                "请在项目根目录的 .env 文件中设置 LLM_API_KEY（或使用 LLM_PROVIDER 选择厂商）。"
            )

    # ══════════════════════════════════════════════════
    #  Signal wiring
    # ══════════════════════════════════════════════════

    def _connect_signals(self):
        self.chat_panel.message_sent.connect(self._on_user_message)

    # ══════════════════════════════════════════════════
    #  User message handler
    # ══════════════════════════════════════════════════

    def _on_user_message(self, text: str):
        if not self.controller.context.has_data:
            self.chat_panel.add_system_message("[系统] 请先导入 BOM 文件再输入指令。")
            return

        self.chat_panel.show_thinking()
        self._set_buttons_enabled(False)
        self._last_user_input = text

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
        fallback = self.controller._local_fallback(
            getattr(self, "_last_user_input", "")
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
            self.chat_panel.add_system_message(f"[系统] {msg}")
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
            self.chat_panel.add_system_message(f"[系统] {msg}")
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
            self.chat_panel.add_system_message(f"[系统] BOM 已导出: {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def _merged_to_dataframe(self):
        from ..bom.merger import BOMMerger
        from ..bom.parser import BOMParser

        merger = BOMMerger()
        merged = merger.merge(self.controller.context.bom_items)
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
    #  Tool actions
    # ══════════════════════════════════════════════════

    def _on_bom_merge(self):
        self._run_operation("正在执行 BOM 合并...", self.controller.merge_bom)

    def _on_validate_package(self):
        self._run_operation("正在校验封装...", self.controller.validate_packages)

    def _on_check_duplicates(self):
        self._run_operation("正在检查位号重复...", self.controller.check_duplicates)

    def _on_generate_html_bom(self):
        if not self.controller.context.has_data:
            QMessageBox.information(self, "提示", "请先导入 BOM 文件")
            return
        if not self.controller.context.positions:
            response = QMessageBox.question(
                self, "缺少坐标数据",
                "尚未导入坐标文件(Pick & Place)，点阵位号图和封装轮廓图将无法显示。\n\n"
                "是否继续生成仅含表格的 HTML BOM？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if response == QMessageBox.No:
                return

        output_path = Path(__file__).parent.parent.parent / "output" / "ibom.html"
        report = self.controller.generate_html_bom(str(output_path))
        self._show_report(report)
        self.chat_panel.add_system_message("[系统] HTML BOM 已生成")

        if output_path.exists():
            webbrowser.open(str(output_path))

    def _on_design_rule_check(self):
        self._run_operation("正在执行设计规则检查...", self.controller.check_design_rules)

    # ══════════════════════════════════════════════════
    #  Generic operation runner
    # ══════════════════════════════════════════════════

    def _run_operation(self, progress_msg: str, handler: Callable[[], str]):
        self.chat_panel.add_system_message(f"[系统] {progress_msg}")
        self._log_output(progress_msg)
        try:
            report = handler()
            self._show_report(report)
            self._log_output(report)
            self.chat_panel.add_system_message("[系统] 操作完成")
            self._status_message.setText("就绪")
        except Exception as exc:
            self.chat_panel.add_error_message(f"操作失败: {exc}")
            self._log_output(f"错误: {exc}")
            logger.exception("Operation failed")

    def _show_report(self, text: str):
        """Display a report in both the report tab and sidebar."""
        self.report_view.setPlainText(text)
        self.sidebar_report.setPlainText(text)
        self.right_tabs.setCurrentIndex(self.REPORT_TAB_INDEX)

    def _log_output(self, text: str):
        """Append to the bottom output panel."""
        self.output_log.append(text)
        self.output_panel.setVisible(True)

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
        """Toggle UI interactivity during AI processing."""
        for btn in self._activity_btns:
            btn.setEnabled(enabled)
        for i in range(self.sidebar_stack.count()):
            self.sidebar_stack.widget(i).setEnabled(enabled)
        self.chat_panel.send_btn.setEnabled(enabled)
        self.chat_panel.input_box.setEnabled(enabled)

    # ══════════════════════════════════════════════════
    #  Theme
    # ══════════════════════════════════════════════════

    def _apply_style(self):
        self.setStyleSheet(compile_stylesheet())

    def _on_toggle_theme(self):
        dark = toggle_theme()
        self._apply_style()
        self._refresh_inline_styles()
        self.chat_panel.refresh_theme()
        self.bom_table.refresh_theme()
        self.settings_panel.refresh_theme()
        self._theme_btn.setText("🌙" if dark else "☀")
        self._status_message.setText(
            "已切换到深色主题" if dark else "已切换到浅色主题"
        )

    def _refresh_activity_bar_styles(self):
        """Re-apply activity bar button styles from current theme."""
        t = current_theme()
        self._activity_bar.setStyleSheet(
            f"background-color: {t['bg_activity']};"
        )
        # Inactive button style
        inactive_css = _ACTIVITY_BTN_STYLE.format(
            text=t["activity_text"], hover=t["bg_hover"], accent=t["accent"]
        )
        # Active button style
        active_css = _ACTIVITY_BTN_STYLE.format(
            text=t["activity_text_active"], hover=t["bg_hover"], accent=t["accent"]
        )
        # Theme toggle button
        self._theme_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {t['activity_text']}; border: none; font-size: 18px; }}"
            f"QPushButton:hover {{ background: {t['bg_hover']}; }}"
        )
        # Apply to each activity button based on active state
        for btn in self._activity_btns:
            btn.setStyleSheet(active_css if btn.property("active") else inactive_css)

    def _refresh_inline_styles(self):
        """Re-apply all inline styles that override global QSS."""
        t = current_theme()

        # Activity bar
        self._refresh_activity_bar_styles()

        # Sidebar background
        self.sidebar_stack.setStyleSheet(
            f"background-color: {t['bg_sidebar']};"
        )

        # BOM actions panel title
        self._bom_actions_title.setStyleSheet(
            f"color: {t['text_primary']}; font-size: 14px; font-weight: bold;"
        )

        # Report panel
        self._report_panel_title.setStyleSheet(
            f"color: {t['text_primary']}; font-size: 14px; font-weight: bold;"
        )
        self.sidebar_report.setStyleSheet(
            f"background-color: {t['bg_editor']}; border: 1px solid {t['border']}; font-size: 12px; color: {t['text_primary']};"
        )

        # Output panel
        self._output_panel_container.setStyleSheet(
            f"background-color: {t['bg_editor']}; border-top: 1px solid {t['border']};"
        )
        self._output_title_bar.setStyleSheet(
            f"background-color: {t['title_bar_bg']};"
        )
        self._output_title_label.setStyleSheet(
            f"color: {t['text_primary']}; font-size: 11px; font-weight: bold;"
        )
        self._output_close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {t['text_primary']}; font-size: 12px; border: none; }}"
            f"QPushButton:hover {{ background: {t['bg_hover']}; }}"
        )
        self.output_log.setStyleSheet(
            f"background-color: {t['bg_editor']}; border: none; color: {t['text_primary']}; font-size: 12px;"
        )

        # HTML preview
        self.html_preview.setStyleSheet(
            f"background-color: {t['bg_editor']}; border: 1px solid {t['border']}; color: {t['text_primary']};"
        )

        # Report view
        self.report_view.setStyleSheet(
            f"background-color: {t['bg_editor']}; border: 1px solid {t['border']}; color: {t['text_primary']};"
        )

    def _on_settings_applied(self, data: dict):
        """Handle settings saved from SettingsPanel — data passed in-memory, no disk re-read."""
        provider = data.get("llm_provider", "deepseek")
        api_key = data.get("llm_api_key", "")
        model = data.get("llm_model", "")
        base_url = data.get("llm_base_url", "")

        self.controller.reconfigure_llm(provider, api_key, base_url, model)

        if self.controller.is_agent_available():
            agent = self.controller.agent
            self._status_provider.setText(f"{agent.provider_label}  {agent.model}")
            self.chat_panel.add_system_message(
                f"[系统] 已切换至 {agent.provider_label}，模型: {agent.model}"
            )
        else:
            self._status_provider.setText("无 API Key")
            self.chat_panel.add_error_message("API Key 无效，LLM 功能已禁用。")

        self._status_message.setText("设置已保存")

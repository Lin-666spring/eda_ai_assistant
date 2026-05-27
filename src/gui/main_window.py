"""
PyQt5 主窗口 — EDA AI 智能助手

布局 (card-style 面板 + 4主题切换):
  ┌───────────────────────────────────────────────┐
  │  File  Tools(含主题切换) Help   EDA AI 助手   │ ← 导航栏
  │  ┌─────────────────┐ ┬ ┌────────────────────┐ │
  │  │   AI 助手面板   │ │ │ [BOM表][HTML][报告]│ │
  │  │   (独立卡片)    │ │ │   主内容区         │ │
  │  └─────────────────┘ ┴ └────────────────────┘ │
  │  状态: 就绪                   LLM: DeepSeek   │ ← 状态栏
  └───────────────────────────────────────────────┘
"""

import logging
import webbrowser
from pathlib import Path
from typing import Callable

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .chat_panel import ChatPanel
from .bom_table import BOMTableView
from .settings_panel import SettingsPanel
from .eda_theme import (
    compile_stylesheet, current_theme, switch_theme,
    get_active_theme_name, get_theme_display_name,
    THEME_DISPLAY_ORDER, on_theme_changed, remove_theme_listener,
    FONT_MONO, FONT_FAMILY,
)
from ..core.controller import AppController

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  Worker thread
# ══════════════════════════════════════════════════════

class AIWorker(QThread):
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
#  Card wrapper helper
# ══════════════════════════════════════════════════════

def _make_card(widget: QWidget, padding: int = 0) -> QWidget:
    """Wrap a widget in a themed card container."""
    t = current_theme()
    card = QWidget()
    card.setObjectName("themeCard")
    card.setStyleSheet(f"""
        QWidget#themeCard {{
            background-color: {t['card_bg']};
            border: 1px solid {t['card_border']};
            border-radius: {t['card_radius']};
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(padding, padding, padding, padding)
    layout.setSpacing(0)
    layout.addWidget(widget)
    return card


def _refresh_card_style(card: QWidget):
    """Re-apply card styling after theme change."""
    t = current_theme()
    card.setStyleSheet(f"""
        QWidget#themeCard {{
            background-color: {t['card_bg']};
            border: 1px solid {t['card_border']};
            border-radius: {t['card_radius']};
        }}
    """)


# ══════════════════════════════════════════════════════
#  Main window
# ══════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    APP_TITLE = "EDA AI 智能助手 — 面向立创EDA的BOM管理与PCB设计"
    APP_VERSION = "0.3.0"
    REPORT_TAB_INDEX = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{self.APP_TITLE} v{self.APP_VERSION}")
        self.resize(1300, 840)
        self.setMinimumSize(980, 620)

        self.controller = AppController()
        self._theme_actions: dict[str, QAction] = {}

        self._setup_ui()
        self._connect_signals()
        self._apply_style()
        self._update_agent_status()

        # Listen for external theme changes
        on_theme_changed(self._on_external_theme_change)

    # ══════════════════════════════════════════════════
    #  UI construction
    # ══════════════════════════════════════════════════

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_navbar())
        root.addWidget(self._build_body(), 1)
        root.addWidget(self._build_status_bar_widget())

    # ── Navbar ──

    def _build_navbar(self) -> QWidget:
        t = current_theme()
        container = QWidget()
        container.setFixedHeight(44)
        container.setObjectName("navbarContainer")
        container.setStyleSheet(
            f"QWidget#navbarContainer {{ background-color: {t['navbar_bg']}; "
            f"border-bottom: 1px solid {t['border']}; }}"
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        mb = self.menuBar()
        mb.setObjectName("mainMenuBar")
        mb.setStyleSheet(f"""
            QMenuBar#mainMenuBar {{
                background-color: {t['navbar_bg']};
                padding: 0 8px; border: none;
            }}
            QMenuBar::item {{
                padding: 10px 14px; margin: 0 1px;
                background-color: transparent;
                color: {t['text_secondary']};
                border-radius: 6px; font-size: 12px;
            }}
            QMenuBar::item:selected {{
                background-color: {t['primary']};
                color: {t['text_white']};
            }}
            QMenu {{
                background-color: {t['bg_card']};
                border: 1px solid {t['border']};
                border-radius: 8px; padding: 6px 0;
            }}
            QMenu::item {{
                padding: 8px 36px 8px 16px;
                color: {t['text_primary']};
            }}
            QMenu::item:selected {{
                background-color: {t['primary']};
                color: {t['text_white']};
                border-radius: 4px; margin: 1px 4px;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {t['border']};
                margin: 6px 12px;
            }}
        """)

        self._setup_menus()
        layout.addWidget(mb)

        layout.addStretch()
        title_label = QLabel(f"EDA AI 智能助手  v{self.APP_VERSION}")
        title_label.setObjectName("navbarTitle")
        title_label.setStyleSheet(
            f"color: {t['text_muted']}; font-size: 11px; "
            f"padding: 0 16px; background: transparent; font-weight: 500;"
        )
        layout.addWidget(title_label)

        return container

    def _setup_menus(self):
        mb = self.menuBar()

        # ── 文件 ──
        file_menu = mb.addMenu("文件")
        file_menu.addAction("导入 BOM 文件", self._on_import_bom, "Ctrl+O")
        file_menu.addAction("导入坐标文件", self._on_import_positions, "Ctrl+Shift+O")
        file_menu.addSeparator()
        file_menu.addAction("导出合并 BOM", self._on_export_bom, "Ctrl+S")
        file_menu.addAction("生成 HTML BOM", self._on_generate_html_bom, "Ctrl+G")
        file_menu.addSeparator()
        file_menu.addAction("设置", self._on_open_settings, "Ctrl+,")
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close, "Alt+F4")

        # ── 工具 ──
        tool_menu = mb.addMenu("工具")
        tool_menu.addAction("BOM 合并", self._on_bom_merge)
        tool_menu.addAction("封装校验", self._on_validate_package)
        tool_menu.addAction("位号查重", self._on_check_duplicates)
        tool_menu.addSeparator()
        tool_menu.addAction("设计规则检查", self._on_design_rule_check)
        tool_menu.addSeparator()
        tool_menu.addAction("清空对话", self._on_clear_conversation)
        tool_menu.addSeparator()

        # ── 主题切换子菜单 ──
        theme_menu = tool_menu.addMenu("主题切换")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        active = get_active_theme_name()
        for tid in THEME_DISPLAY_ORDER:
            display = get_theme_display_name(tid)
            action = theme_menu.addAction(display)
            action.setCheckable(True)
            action.setChecked(tid == active)
            action.setData(tid)
            action.triggered.connect(lambda checked, t=tid: self._on_switch_theme(t))
            theme_group.addAction(action)
            self._theme_actions[tid] = action

        # ── 帮助 ──
        help_menu = mb.addMenu("帮助")
        help_menu.addAction("使用手册", self._on_show_help)
        help_menu.addAction("关于", self._on_show_about)

    # ── Body — card panels + divider ──

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setObjectName("bodyContainer")
        body.setStyleSheet(f"QWidget#bodyContainer {{ background-color: {current_theme()['bg_main']}; }}")
        layout = QHBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # Left card: AI chat panel
        self.chat_panel = ChatPanel()
        self.chat_panel.setMinimumWidth(320)
        self._left_card = _make_card(self.chat_panel, padding=0)

        # Gap + divider
        gap = QWidget()
        gap.setFixedWidth(10)
        gap.setStyleSheet("background: transparent;")
        gap_l = QHBoxLayout(gap)
        gap_l.setContentsMargins(4, 0, 5, 0)
        gap_l.setSpacing(0)

        divider = QWidget()
        divider.setFixedWidth(1)
        divider.setObjectName("panelDivider")
        divider.setStyleSheet(
            f"QWidget#panelDivider {{ background-color: {current_theme()['divider']}; }}"
        )
        gap_l.addWidget(divider)

        # Right card: tab area
        self.right_tabs = QTabWidget()
        self.right_tabs.setObjectName("rightTabs")
        self._setup_tab_styles()

        self.bom_table = BOMTableView()
        self.right_tabs.addTab(self.bom_table, "BOM 表格")

        self.html_preview = QTextEdit()
        self.html_preview.setReadOnly(True)
        self.html_preview.setPlaceholderText("HTML BOM 预览将在生成后显示于此")
        self.right_tabs.addTab(self.html_preview, "HTML BOM")

        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setFont(QFont(FONT_MONO, 10))
        self.report_view.setPlaceholderText("校验 / 合并报告将显示于此")
        self.right_tabs.addTab(self.report_view, "报告")

        self._right_card = _make_card(self.right_tabs, padding=8)

        # Assemble
        layout.addWidget(self._left_card, 3)
        layout.addWidget(gap)
        layout.addWidget(self._right_card, 7)

        return body

    def _setup_tab_styles(self):
        t = current_theme()
        self.right_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background-color: transparent; }}
            QTabBar::tab {{
                background-color: transparent;
                color: {t['text_secondary']};
                padding: 10px 22px; margin-right: 0;
                border-bottom: 2px solid transparent;
                font-size: 13px; font-weight: 500;
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
                border-bottom: 2px solid transparent;
            }}
        """)

    # ── Status bar ──

    def _build_status_bar_widget(self) -> QWidget:
        t = current_theme()
        container = QWidget()
        container.setFixedHeight(28)
        container.setObjectName("statusBarContainer")
        container.setStyleSheet(
            f"QWidget#statusBarContainer {{ background-color: {t['status_bar_bg']}; "
            f"border-top: 1px solid {t['border']}; }}"
        )
        layout = QHBoxLayout(container)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self._status_message = QLabel("就绪")
        self._status_message.setStyleSheet(
            f"color: {t['status_bar_text']}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._status_message)
        layout.addStretch()

        self._status_provider = QLabel("未配置")
        self._status_provider.setStyleSheet(
            f"color: {t['status_bar_text']}; font-size: 11px; background: transparent; padding: 0 4px;"
        )
        layout.addWidget(self._status_provider)

        return container

    # ══════════════════════════════════════════════════
    #  Theme switching
    # ══════════════════════════════════════════════════

    def _on_switch_theme(self, name: str):
        switch_theme(name)
        self._refresh_all_styles()
        # Update action check states
        for tid, action in self._theme_actions.items():
            action.setChecked(tid == name)

    def _on_external_theme_change(self, name: str):
        """Handle theme change triggered outside (e.g. from settings)."""
        self._refresh_all_styles()
        for tid, action in self._theme_actions.items():
            action.setChecked(tid == name)

    def _refresh_all_styles(self):
        """Re-apply all stylesheets and inline styles after theme change."""
        t = current_theme()

        # Global QSS
        self._apply_style()

        # Cards
        _refresh_card_style(self._left_card)
        _refresh_card_style(self._right_card)

        # Navbar
        navbar = self.findChild(QWidget, "navbarContainer")
        if navbar:
            navbar.setStyleSheet(
                f"QWidget#navbarContainer {{ background-color: {t['navbar_bg']}; "
                f"border-bottom: 1px solid {t['border']}; }}"
            )

        # Menu bar
        mb = self.findChild(QWidget, "mainMenuBar")
        if mb:
            mb.setStyleSheet(f"""
                QMenuBar#mainMenuBar {{
                    background-color: {t['navbar_bg']};
                    padding: 0 8px; border: none;
                }}
                QMenuBar::item {{
                    padding: 10px 14px; margin: 0 1px;
                    background-color: transparent;
                    color: {t['text_secondary']};
                    border-radius: 6px; font-size: 12px;
                }}
                QMenuBar::item:selected {{
                    background-color: {t['primary']};
                    color: {t['text_white']};
                }}
                QMenu {{
                    background-color: {t['bg_card']};
                    border: 1px solid {t['border']};
                    border-radius: 8px; padding: 6px 0;
                }}
                QMenu::item {{
                    padding: 8px 36px 8px 16px;
                    color: {t['text_primary']};
                }}
                QMenu::item:selected {{
                    background-color: {t['primary']};
                    color: {t['text_white']};
                    border-radius: 4px; margin: 1px 4px;
                }}
                QMenu::separator {{
                    height: 1px;
                    background-color: {t['border']};
                    margin: 6px 12px;
                }}
            """)

        # Navbar title
        title_label = self.findChild(QLabel, "navbarTitle")
        if title_label:
            title_label.setStyleSheet(
                f"color: {t['text_muted']}; font-size: 11px; "
                f"padding: 0 16px; background: transparent; font-weight: 500;"
            )

        # Body background
        body = self.findChild(QWidget, "bodyContainer")
        if body:
            body.setStyleSheet(f"QWidget#bodyContainer {{ background-color: {t['bg_main']}; }}")

        # Divider
        divider = self.findChild(QWidget, "panelDivider")
        if divider:
            divider.setStyleSheet(f"QWidget#panelDivider {{ background-color: {t['divider']}; }}")

        # Status bar
        sb = self.findChild(QWidget, "statusBarContainer")
        if sb:
            sb.setStyleSheet(
                f"QWidget#statusBarContainer {{ background-color: {t['status_bar_bg']}; "
                f"border-top: 1px solid {t['border']}; }}"
            )
        self._status_message.setStyleSheet(
            f"color: {t['status_bar_text']}; font-size: 11px; background: transparent;"
        )
        self._status_provider.setStyleSheet(
            f"color: {t['status_bar_text']}; font-size: 11px; background: transparent; padding: 0 4px;"
        )

        # Tabs
        self._setup_tab_styles()

        # HTML preview + report view
        self.html_preview.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t['bg_main']};
                color: {t['text_primary']};
                border: 1px solid {t['border']};
                border-radius: 8px; font-size: 13px; padding: 12px; margin: 8px;
            }}
        """)
        self.report_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t['bg_main']};
                color: {t['text_primary']};
                border: 1px solid {t['border']};
                border-radius: 8px; font-size: 13px; padding: 12px; margin: 8px;
            }}
        """)

        # Child components
        self.chat_panel.refresh_theme()
        self.bom_table.refresh_theme()
        # Settings panel is in a dialog, not always loaded

    # ══════════════════════════════════════════════════
    #  Style
    # ══════════════════════════════════════════════════

    def _apply_style(self):
        self.setStyleSheet(compile_stylesheet())

    def closeEvent(self, event):
        remove_theme_listener(self._on_external_theme_change)
        super().closeEvent(event)

    # ══════════════════════════════════════════════════
    #  Signal wiring
    # ══════════════════════════════════════════════════

    def _connect_signals(self):
        self.chat_panel.message_sent.connect(self._on_user_message)
        self.chat_panel.clear_requested.connect(self._on_clear_conversation)

    # ══════════════════════════════════════════════════
    #  User message handler
    # ══════════════════════════════════════════════════

    def _on_user_message(self, text: str):
        if not self.controller.context.has_data:
            self.chat_panel.add_system_message("请先导入 BOM 文件再输入指令。")
            return

        self.chat_panel.show_thinking()
        self._set_input_enabled(False)
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
        self._set_input_enabled(True)
        self._status_message.setText("就绪")

    def _on_ai_error(self, error_msg: str):
        self.chat_panel.cancel_streaming()
        self.chat_panel.add_error_message(f"AI 处理失败: {error_msg}")
        self.chat_panel.add_system_message("已回退到本地关键词匹配模式。")
        try:
            fallback = self.controller._local_fallback(
                getattr(self, "_last_user_input", "")
            )
        except Exception:
            logger.exception("Local fallback failed")
            fallback = ""
        if fallback:
            self.chat_panel.add_ai_message(fallback)
            self._show_report(fallback)
        self._set_input_enabled(True)
        self._status_message.setText("就绪")

    def _on_clear_conversation(self):
        self.controller.clear_conversation()
        self._status_message.setText("对话已清空")

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
            self._status_message.setText(f"已加载: {Path(path).name} ({count} 条)")
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
            self._status_message.setText(f"已加载坐标: {Path(path).name}")
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
            self._status_message.setText(f"已导出到: {path}")
            self.chat_panel.add_system_message(f"BOM 已导出: {Path(path).name}")
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
        self.chat_panel.add_config_tip("HTML BOM 已生成", "success")

        if output_path.exists():
            webbrowser.open(str(output_path))

    def _on_design_rule_check(self):
        self._run_operation("正在执行设计规则检查...", self.controller.check_design_rules)

    # ══════════════════════════════════════════════════
    #  Settings dialog
    # ══════════════════════════════════════════════════

    def _on_open_settings(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("LLM 设置")
        dialog.setMinimumWidth(480)
        dialog.setStyleSheet(f"QDialog {{ background-color: {current_theme()['bg_card']}; }}")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        settings = SettingsPanel()
        settings.settings_applied.connect(self._on_settings_applied)
        settings.settings_saved.connect(dialog.accept)
        layout.addWidget(settings)

        dialog.exec_()

    # ══════════════════════════════════════════════════
    #  Generic operation runner
    # ══════════════════════════════════════════════════

    def _run_operation(self, progress_msg: str, handler: Callable[[], str]):
        self.chat_panel.add_system_message(progress_msg)
        self._status_message.setText(progress_msg)
        try:
            report = handler()
            self._show_report(report)
            self.chat_panel.add_config_tip("操作完成", "success")
            self._status_message.setText("就绪")
        except Exception as exc:
            self.chat_panel.add_config_tip(f"操作失败: {exc}", "error")
            self._status_message.setText("操作失败")
            logger.exception("Operation failed")

    def _show_report(self, text: str):
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

    def _set_input_enabled(self, enabled: bool):
        self.chat_panel.send_btn.setEnabled(enabled)
        self.chat_panel.input_box.setEnabled(enabled)
        self.chat_panel.clear_btn.setEnabled(enabled)
        self.menuBar().setEnabled(enabled)

    def _update_agent_status(self):
        if self.controller.is_agent_available():
            agent = self.controller.agent
            self._status_provider.setText(f"LLM: {agent.provider_label}  {agent.model}")
            self.chat_panel.add_config_tip(
                f"{agent.provider_label} AI Agent 已就绪  |  模型: {agent.model}"
            )
        else:
            self._status_provider.setText("无 API Key")
            self.chat_panel.add_config_tip(
                "未配置 LLM API Key，使用本地关键词匹配模式。"
                "前往 文件 → 设置 配置，或在项目 .env 文件中设置 LLM_API_KEY。"
            )

    def _on_settings_applied(self, data: dict):
        provider = data.get("llm_provider", "deepseek")
        api_key = data.get("llm_api_key", "")
        model = data.get("llm_model", "")
        base_url = data.get("llm_base_url", "")

        self.controller.reconfigure_llm(provider, api_key, base_url, model)

        if self.controller.is_agent_available():
            agent = self.controller.agent
            self._status_provider.setText(f"LLM: {agent.provider_label}  {agent.model}")
            self.chat_panel.add_config_tip(
                f"已切换至 {agent.provider_label}，模型: {agent.model}"
            )
        else:
            self._status_provider.setText("无 API Key")
            self.chat_panel.add_error_message("API Key 无效，LLM 功能已禁用。")

        self._status_message.setText("设置已保存")

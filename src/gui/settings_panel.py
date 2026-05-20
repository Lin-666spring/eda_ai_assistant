"""
GUI 设置面板 — 允许用户在界面内配置 LLM，无需手动编辑 .env。
配置持久化到 ~/.eda_ai_assistant/settings.json，不会被 git 跟踪。
"""

import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import load_settings, save_settings
from ..constants import LLM_PROVIDER_PRESETS
from .vscode_theme import current_theme

logger = logging.getLogger(__name__)


class SettingsPanel(QWidget):
    """LLM 配置表单，嵌入侧边栏使用。"""

    settings_applied = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load()

    # ── UI construction ──

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._title_label = QLabel("LLM 设置")
        self._title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._title_label)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        # Provider dropdown
        self.provider_combo = QComboBox()
        for key, preset in LLM_PROVIDER_PRESETS.items():
            self.provider_combo.addItem(f"{preset.description}", key)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("厂商:", self.provider_combo)

        # API Key (password mode)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入 API Key...")
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(self.api_key_input)
        self._show_key_btn = QPushButton("👁")
        self._show_key_btn.setFixedWidth(32)
        self._show_key_btn.setToolTip("显示/隐藏 API Key")
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        api_key_layout.addWidget(self._show_key_btn)
        self._api_key_container = QWidget()
        self._api_key_container.setLayout(api_key_layout)
        form.addRow("API Key:", self._api_key_container)

        # Model
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("选填，留空使用默认模型")
        form.addRow("模型:", self.model_input)

        # Base URL
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("选填，留空使用默认地址")
        form.addRow("Base URL:", self.base_url_input)

        layout.addLayout(form)

        # Current defaults hint
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("font-size: 11px; padding: 4px 0;")
        layout.addWidget(self.hint_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.save_btn = QPushButton("保存并应用")
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("清除")
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        # Apply initial theme styles
        self._apply_theme_styles()

    # ── Load / Save ──

    def _load(self):
        """从 settings.json 加载已保存的配置并填充表单。"""
        data = load_settings()
        provider = data.get("llm_provider", "")
        if provider and provider in LLM_PROVIDER_PRESETS:
            idx = self.provider_combo.findData(provider)
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
        self.api_key_input.setText(data.get("llm_api_key", ""))
        self.model_input.setText(data.get("llm_model", ""))
        self.base_url_input.setText(data.get("llm_base_url", ""))
        self._update_hint()

    def _on_save(self):
        """保存设置并触发热重载。"""
        provider = self.provider_combo.currentData()
        api_key = self.api_key_input.text().strip()
        model = self.model_input.text().strip()
        base_url = self.base_url_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "提示", "请输入 API Key。")
            return

        data = {
            "llm_provider": provider,
            "llm_api_key": api_key,
            "llm_model": model,
            "llm_base_url": base_url,
        }
        if save_settings(data):
            self.settings_applied.emit(data)
            self._update_hint()
            logger.info("Settings saved: provider=%s, model=%s", provider, model or "(default)")
        else:
            QMessageBox.critical(self, "保存失败", "无法写入设置文件。")

    def _on_clear(self):
        """清除表单内容（不删除已保存文件，需保存后才覆盖）。"""
        self.api_key_input.clear()
        self.model_input.clear()
        self.base_url_input.clear()
        self.provider_combo.setCurrentIndex(0)

    def _on_provider_changed(self):
        """厂商切换时更新提示。"""
        self._update_hint()

    def _toggle_key_visibility(self):
        """切换 API Key 的明文/密码显示。"""
        current = self.api_key_input.echoMode()
        if current == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self._show_key_btn.setText("🙈")
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self._show_key_btn.setText("👁")

    def _update_hint(self):
        """更新厂商默认信息提示。"""
        provider = self.provider_combo.currentData()
        preset = LLM_PROVIDER_PRESETS.get(provider)
        if preset:
            model = self.model_input.text().strip() or preset.default_model
            self.hint_label.setText(
                f"默认接口: {preset.base_url}\n默认模型: {model}"
            )

    def refresh_theme(self):
        """Re-apply theme-aware inline styles (public entry point)."""
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        """Apply all inline styles based on current theme."""
        t = current_theme()

        # Panel background
        self.setStyleSheet(f"background-color: {t['bg_sidebar']};")

        # Title
        self._title_label.setStyleSheet(
            f"color: {t['text_primary']}; font-size: 14px; font-weight: bold;"
        )

        # Hint
        self.hint_label.setStyleSheet(
            f"color: {t['text_secondary']}; font-size: 11px; padding: 4px 0;"
        )

        # Clear button (secondary action)
        self.clear_btn.setStyleSheet(
            f"QPushButton {{ background-color: {t['border']}; color: {t['text_primary']}; "
            f"padding: 8px 14px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {t['bg_hover']}; }}"
        )

        # Show/hide key button
        self._show_key_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {t['text_secondary']}; "
            f"border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {t['text_primary']}; }}"
        )

        # API key container
        self._api_key_container.setStyleSheet("background-color: transparent;")

"""
GUI 设置面板 — 配置 LLM 厂商 / API Key / 模型，4主题动态适配。

配置持久化到 ~/.eda_ai_assistant/settings.json
"""

import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ..config import load_settings, save_settings
from ..constants import LLM_PROVIDER_PRESETS
from .eda_theme import current_theme

logger = logging.getLogger(__name__)


class SettingsPanel(QWidget):
    settings_applied = pyqtSignal(dict)
    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        t = current_theme()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Title
        self._title = QLabel("LLM 设置")
        self._title.setObjectName("settingsTitle")
        layout.addWidget(self._title)

        # Subtitle
        self._subtitle = QLabel("配置 AI 大语言模型连接参数")
        self._subtitle.setObjectName("settingsSubtitle")
        layout.addWidget(self._subtitle)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)

        self._provider_label = QLabel("厂商")
        self._provider_label.setObjectName("settingsFormLabel")
        self.provider_combo = QComboBox()
        self.provider_combo.setObjectName("settingsProviderCombo")
        for key, preset in LLM_PROVIDER_PRESETS.items():
            self.provider_combo.addItem(f"{preset.description}", key)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow(self._provider_label, self.provider_combo)

        self._key_label = QLabel("API Key")
        self._key_label.setObjectName("settingsFormLabel")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入 API Key...")
        self.api_key_input.setObjectName("settingsApiKeyInput")

        api_layout = QHBoxLayout()
        api_layout.setContentsMargins(0, 0, 0, 0)
        api_layout.setSpacing(8)
        api_layout.addWidget(self.api_key_input)

        self._show_key_btn = QPushButton("显示")
        self._show_key_btn.setMinimumWidth(64)
        self._show_key_btn.setFixedHeight(36)
        self._show_key_btn.setObjectName("settingsShowKeyBtn")
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        api_layout.addWidget(self._show_key_btn)
        api_container = QWidget()
        api_container.setLayout(api_layout)
        form.addRow(self._key_label, api_container)

        self._model_label = QLabel("模型")
        self._model_label.setObjectName("settingsFormLabel")
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("选填，留空使用默认模型")
        self.model_input.setObjectName("settingsModelInput")
        form.addRow(self._model_label, self.model_input)

        self._url_label = QLabel("Base URL")
        self._url_label.setObjectName("settingsFormLabel")
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("选填，留空使用默认地址")
        self.base_url_input.setObjectName("settingsBaseUrlInput")
        form.addRow(self._url_label, self.base_url_input)

        layout.addLayout(form)

        # Hint
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setObjectName("settingsHintLabel")
        layout.addWidget(self.hint_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.save_btn = QPushButton("保存并应用")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setMinimumWidth(120)
        self.save_btn.setObjectName("settingsSaveBtn")
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("清除")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setMinimumWidth(80)
        self.clear_btn.setObjectName("settingsClearBtn")
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self._apply_theme_styles()

    def _apply_theme_styles(self):
        t = current_theme()
        self.setStyleSheet(f"background-color: {t['bg_card']};")

        self._title.setStyleSheet(
            f"color: {t['text_primary']}; font-size: 16px; font-weight: 700; "
            f"background: transparent; padding: 0 0 4px 0;"
        )
        self._subtitle.setStyleSheet(
            f"color: {t['text_secondary']}; font-size: 12px; background: transparent; padding: 0 0 8px 0;"
        )

        label_ss = f"color: {t['text_secondary']}; font-size: 12px; font-weight: 500; background: transparent;"
        for lbl in [self._provider_label, self._key_label, self._model_label, self._url_label]:
            lbl.setStyleSheet(label_ss)

        input_ss = f"""
            QLineEdit {{
                background-color: {t['bg_input']}; color: {t['text_primary']};
                border: 1px solid {t['border']}; border-radius: 8px;
                padding: 10px 14px; font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {t['border_focus']}; padding: 9px 13px;
            }}
        """
        self.api_key_input.setStyleSheet(input_ss)
        self.model_input.setStyleSheet(input_ss)
        self.base_url_input.setStyleSheet(input_ss)

        self.provider_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t['bg_input']}; color: {t['text_primary']};
                border: 1px solid {t['border']}; border-radius: 8px;
                padding: 10px 14px; font-size: 13px;
            }}
            QComboBox:hover {{ border-color: {t['border_light']}; }}
            QComboBox::drop-down {{ border: none; width: 28px; }}
            QComboBox QAbstractItemView {{
                background-color: {t['bg_card']}; color: {t['text_primary']};
                border: 1px solid {t['border']}; border-radius: 8px;
                selection-background-color: {t['primary']};
                selection-color: {t['text_white']}; padding: 4px;
            }}
        """)

        self._show_key_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['border']}; color: {t['text_secondary']};
                border: none; border-radius: 7px;
                font-size: 12px; padding: 6px 14px; font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t['border_light']}; color: {t['text_primary']};
            }}
        """)

        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['primary']}; color: {t['text_white']};
                border: none; border-radius: 8px;
                padding: 10px 22px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t['primary_hover']}; }}
            QPushButton:pressed {{ background-color: {t['primary_pressed']}; }}
        """)

        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['border']}; color: {t['text_secondary']};
                border: none; border-radius: 8px;
                padding: 10px 22px; font-size: 13px; font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t['border_light']}; color: {t['text_primary']};
            }}
        """)

        self.hint_label.setStyleSheet(
            f"color: {t['text_muted']}; font-size: 11px; background: transparent; "
            f"padding: 4px 0; line-height: 1.5;"
        )

    # ── Load / Save ──

    def _load(self):
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
            self.settings_saved.emit()
            self._update_hint()
            logger.info("Settings saved: provider=%s, model=%s", provider, model or "(default)")
        else:
            QMessageBox.critical(self, "保存失败", "无法写入设置文件。")

    def _on_clear(self):
        self.api_key_input.clear()
        self.model_input.clear()
        self.base_url_input.clear()
        self.provider_combo.setCurrentIndex(0)

    def _on_provider_changed(self):
        self._update_hint()

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self._show_key_btn.setText("隐藏")
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self._show_key_btn.setText("显示")

    def _update_hint(self):
        provider = self.provider_combo.currentData()
        preset = LLM_PROVIDER_PRESETS.get(provider)
        if preset:
            model = self.model_input.text().strip() or preset.default_model
            self.hint_label.setText(f"默认接口: {preset.base_url}\n默认模型: {model}")

    def refresh_theme(self):
        """Re-apply all inline styles after theme change."""
        self._apply_theme_styles()

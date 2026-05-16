"""
应用配置管理 — 集中化版本
支持从环境变量和 .env 文件加载，带验证和默认值

LLM 配置支持厂商预设 (LLM_PROVIDER) 和手动指定 (LLM_*)
同时向后兼容旧的 DEEPSEEK_* 环境变量
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .constants import (
    AGENT, GUI, LLM_PROVIDER_PRESETS, DEFAULT_PROVIDER,
)

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
except ImportError:
    pass


def _env(key: str, default: str = "") -> str:
    """读取环境变量"""
    return os.getenv(key, default)


def _resolve_llm_config() -> tuple[str, str, str, str]:
    """
    解析 LLM 配置，优先级：
    1. LLM_* 环境变量直接覆盖
    2. LLM_PROVIDER 厂商预设
    3. 旧的 DEEPSEEK_* 环境变量（向后兼容）
    4. 默认值 (deepseek)
    """
    # 向后兼容：旧的 DEEPSEEK_* 变量
    legacy_key = _env("DEEPSEEK_API_KEY", "")
    legacy_url = _env("DEEPSEEK_BASE_URL", "")
    legacy_model = _env("DEEPSEEK_MODEL", "")

    # 新变量优先，旧变量兜底
    api_key = _env("LLM_API_KEY", legacy_key)
    provider = _env("LLM_PROVIDER", DEFAULT_PROVIDER)
    base_url = _env("LLM_BASE_URL", "")
    model = _env("LLM_MODEL", "")

    # 如果没有显式指定 base_url / model，用 legacy 值
    if not base_url and legacy_url:
        base_url = legacy_url
    if not model and legacy_model:
        model = legacy_model

    return api_key, provider, base_url, model


@dataclass
class LLMConfig:
    """LLM API 配置 — 兼容 OpenAI/DeepSeek/通义千问/智谱/Kimi 等"""

    api_key: str = field(default_factory=lambda: _resolve_llm_config()[0])
    provider: str = field(default_factory=lambda: _resolve_llm_config()[1])
    base_url: str = field(default_factory=lambda: _resolve_llm_config()[2])
    model: str = field(default_factory=lambda: _resolve_llm_config()[3])

    def __post_init__(self):
        # 如果 base_url / model 为空，从 provider 预设解析
        if self.provider and self.provider in LLM_PROVIDER_PRESETS:
            preset = LLM_PROVIDER_PRESETS[self.provider]
            if not self.base_url:
                object.__setattr__(self, "base_url", preset.base_url)
            if not self.model:
                object.__setattr__(self, "model", preset.default_model)
        # 最终兜底
        if not self.base_url:
            object.__setattr__(self, "base_url", AGENT.DEFAULT_BASE_URL)
        if not self.model:
            object.__setattr__(self, "model", AGENT.DEFAULT_MODEL)

    @property
    def is_configured(self) -> bool:
        """API 密钥是否已正确配置"""
        return bool(self.api_key and self.api_key not in ("", "your_api_key_here", "sk-"))

    @property
    def provider_label(self) -> str:
        """当前厂商的可读名称"""
        preset = LLM_PROVIDER_PRESETS.get(self.provider)
        return preset.description if preset else self.provider


@dataclass
class PathConfig:
    """路径配置子集"""
    project_root: Path = field(
        default_factory=lambda: Path(__file__).parent.parent
    )
    log_dir: Optional[Path] = field(default=None)
    export_dir: Optional[Path] = field(default=None)

    def __post_init__(self):
        if self.log_dir is None:
            self.log_dir = self.project_root / "logs"
        if self.export_dir is None:
            self.export_dir = self.project_root / "output"

    def ensure_dirs(self):
        self.log_dir.mkdir(exist_ok=True)
        self.export_dir.mkdir(exist_ok=True)


@dataclass
class GUIConfig:
    """GUI 配置子集"""
    width: int = field(
        default_factory=lambda: int(_env("GUI_WIDTH", str(GUI.DEFAULT_WIDTH)))
    )
    height: int = field(
        default_factory=lambda: int(_env("GUI_HEIGHT", str(GUI.DEFAULT_HEIGHT)))
    )
    dark_mode: bool = field(
        default_factory=lambda: _env("GUI_DARK_MODE", "0") == "1"
    )


@dataclass
class AppConfig:
    """应用全局配置 — 组合式结构，按域分组的配置子集"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)

    @property
    def is_api_configured(self) -> bool:
        """快捷访问：API 是否就绪"""
        return self.llm.is_configured

    # 向后兼容别名
    @property
    def deepseek(self) -> LLMConfig:
        return self.llm

# 全局单例 — 模块级懒加载
_config_instance: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置单例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = AppConfig()
    return _config_instance


# 向后兼容的快捷引用
config = get_config()

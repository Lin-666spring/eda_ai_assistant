"""
应用配置管理 — 集中化版本
支持从环境变量和 .env 文件加载，带验证和默认值
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .constants import AGENT, GUI

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


@dataclass
class DeepSeekConfig:
    """DeepSeek API 配置子集"""
    api_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: _env("DEEPSEEK_BASE_URL", AGENT.DEFAULT_BASE_URL)
    )
    model: str = field(
        default_factory=lambda: _env("DEEPSEEK_MODEL", AGENT.DEFAULT_MODEL)
    )

    @property
    def is_configured(self) -> bool:
        """API 密钥是否已正确配置"""
        return bool(self.api_key and self.api_key not in ("", "your_api_key_here", "sk-"))


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

    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)

    @property
    def is_api_configured(self) -> bool:
        """快捷访问：API 是否就绪"""
        return self.deepseek.is_configured

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

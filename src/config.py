"""
应用配置管理 — 集中化版本
支持从环境变量和 .env 文件加载，带验证和默认值

LLM 配置支持厂商预设 (LLM_PROVIDER) 和手动指定 (LLM_*)
同时向后兼容旧的 DEEPSEEK_* 环境变量

GUI 设置面板保存到 ~/.eda_ai_assistant/settings.json，优先级高于 .env。
"""

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .constants import (
    AGENT, GUI, LLM_PROVIDER_PRESETS, DEFAULT_PROVIDER, app_home,
)

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).parent.parent / ".env"
    load_dotenv(_ENV_FILE)
except ImportError:
    pass

# 本地持久化设置文件 (项目外，避免被 git 跟踪)
# 目录可用 EDA_AI_HOME 覆盖（测试/受限环境改到临时目录）。
SETTINGS_DIR = app_home()
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


def load_settings() -> dict:
    """从本地 settings.json 读取设置。不存在返回空字典。"""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(data: dict) -> bool:
    """将设置写入本地 settings.json。目录不存在则创建。"""
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        return False
    # 0o600 = 仅 owner 读写（含 API key）；Windows 只影响只读位、保持可写。
    # 收紧失败不算保存失败（文件已落盘）。
    try:
        os.chmod(SETTINGS_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return True


def _env(key: str, default: str = "") -> str:
    """读取环境变量"""
    return os.getenv(key, default)


def _resolve_llm_config() -> tuple[str, str, str, str]:
    """
    解析 LLM 配置，优先级：
    1. LLM_* 环境变量直接覆盖
    2. ~/.eda_ai_assistant/settings.json（GUI 设置面板保存）
    3. LLM_PROVIDER 厂商预设
    4. 旧的 DEEPSEEK_* 环境变量（向后兼容）
    5. 默认值 (deepseek)
    """
    # 读取本地持久化设置
    saved = load_settings()

    # 向后兼容：旧的 DEEPSEEK_* 变量
    legacy_key = _env("DEEPSEEK_API_KEY", "")
    legacy_url = _env("DEEPSEEK_BASE_URL", "")
    legacy_model = _env("DEEPSEEK_MODEL", "")

    # 新变量 > settings.json > 旧变量
    api_key = _env("LLM_API_KEY", "") or saved.get("llm_api_key", "") or legacy_key
    provider = _env("LLM_PROVIDER", "") or saved.get("llm_provider", "") or DEFAULT_PROVIDER
    base_url = _env("LLM_BASE_URL", "") or saved.get("llm_base_url", "") or legacy_url
    model = _env("LLM_MODEL", "") or saved.get("llm_model", "") or legacy_model

    return api_key, provider, base_url, model


# 缓存 _resolve_llm_config() 结果，避免 4 个 default_factory 各调用一次
_llm_config_cache: Optional[tuple] = None


def _cached_llm_config() -> tuple[str, str, str, str]:
    global _llm_config_cache
    if _llm_config_cache is None:
        _llm_config_cache = _resolve_llm_config()
    return _llm_config_cache


@dataclass
class LLMConfig:
    """LLM API 配置 — 兼容 OpenAI/DeepSeek/通义千问/智谱/Kimi 等"""

    api_key: str = field(default_factory=lambda: _cached_llm_config()[0])
    provider: str = field(default_factory=lambda: _cached_llm_config()[1])
    base_url: str = field(default_factory=lambda: _cached_llm_config()[2])
    model: str = field(default_factory=lambda: _cached_llm_config()[3])

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


def clear_local_data(keep_logs: bool = True) -> None:
    """删除 SETTINGS_DIR 下的全部本地数据（settings.json / sessions.db 等）。

    2026-10-24 修复（验收 A-5）：
    - 保留 logs/ 子目录：打包版日志写在 app_home()/logs 且 FileHandler
      全程持有句柄，Windows 下带着句柄 shutil.rmtree 必抛 PermissionError
      （旧版「清除数据」在打包版永远失败）；保留日志也便于排查清除后的异常。
    - 同时清空 _llm_config_cache 与内存 config.llm 中的 API Key —— 否则
      「清除所有本地数据」后密钥仍然生效，与用户预期不符。
    删除成功后抛异常由调用方兜底；单例（SessionStore/AppController）的
    重置是进程内状态，由各入口自己完成。
    """
    global _llm_config_cache
    import gc
    import shutil

    # SessionStore 每次操作新建连接、靠引用计数关闭 —— 存量引用（异常
    # traceback、引用环）在 Windows 上会让句柄滞留，unlink 报 WinError 32。
    # 删除前强制回收一轮，把可能的残留连接全部关掉。
    gc.collect()

    if SETTINGS_DIR.exists():
        for entry in SETTINGS_DIR.iterdir():
            if keep_logs and entry.name == "logs":
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

    _llm_config_cache = None
    # 内存中的存量 Key 一并抹掉（.env 提供的 Key 属环境配置，不动）
    for field_name in ("api_key", "provider", "base_url", "model"):
        object.__setattr__(config.llm, field_name, "")

"""
项目全局常量集中管理
消除散落在各模块中的魔法数字和硬编码字符串
"""

from enum import Enum
from dataclasses import dataclass


# ══════════════════ 文件格式 ══════════════════

class SupportedFormat(str, Enum):
    """支持的 BOM 文件格式"""
    CSV = ".csv"
    XLSX = ".xlsx"
    XLS = ".xls"

    @classmethod
    def all_extensions(cls) -> tuple[str, ...]:
        return tuple(f.value for f in cls)

    @classmethod
    def is_supported(cls, extension: str) -> bool:
        return extension.lower() in cls.all_extensions()


# ══════════════════ BOM 常量 ══════════════════

@dataclass(frozen=True)
class BOMConstants:
    """BOM 模块常量"""

    # 合并容差
    DEFAULT_MERGE_TOLERANCE: float = 0.05

    # CSV 编码探测顺序
    CSV_ENCODINGS: tuple = ("utf-8", "utf-8-sig", "gbk", "gb2312")

    # 无源元件关键词
    PASSIVE_KEYWORDS: tuple = (
        "电阻", "电容", "电感", "磁珠",
        "resistor", "capacitor", "inductor",
    )

    # 报告分隔线
    REPORT_SEPARATOR: str = "─" * 50
    REPORT_DOUBLE_SEP: str = "=" * 50


# ══════════════════ Agent 常量 ══════════════════

@dataclass(frozen=True)
class AgentConstants:
    """AI Agent 常量"""

    DEFAULT_MODEL: str = "deepseek-chat"
    DEFAULT_BASE_URL: str = "https://api.deepseek.com/v1"
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_MAX_TOKENS: int = 4096
    HISTORY_MAX_TURNS: int = 20
    API_TIMEOUT: int = 120
    API_ENDPOINT: str = "/chat/completions"


# ══════════════════ GUI 常量 ══════════════════

@dataclass(frozen=True)
class GUIConstants:
    """GUI 常量"""

    DEFAULT_WIDTH: int = 1280
    DEFAULT_HEIGHT: int = 800
    MIN_WIDTH: int = 960
    MIN_HEIGHT: int = 600
    SPLITTER_LEFT_RATIO: float = 0.4
    REPORT_TAB_INDEX: int = 2


# ══════════════════ HTML BOM 常量 ══════════════════

@dataclass(frozen=True)
class HTMLBOMConstants:
    """交互式 HTML BOM 常量"""

    ZOOM_MIN: float = 0.25
    ZOOM_MAX: float = 10.0
    ZOOM_STEP: float = 0.15
    ZOOM_DEFAULT: float = 1.0
    BOARD_MARGIN_MM: float = 3.0
    GRID_BASE_STEP: int = 25
    LABEL_VISIBLE_ZOOM: float = 0.55


# ══════════════════ 单例实例 ══════════════════

BOM = BOMConstants()
AGENT = AgentConstants()
GUI = GUIConstants()
HTML = HTMLBOMConstants()

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


# ══════════════════ LLM Provider 预设 ══════════════════

@dataclass(frozen=True)
class ProviderPreset:
    """单个 LLM 厂商预设"""
    name: str
    base_url: str
    default_model: str
    description: str


# 主流 OpenAI 兼容厂商预设
LLM_PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "deepseek": ProviderPreset(
        "deepseek", "https://api.deepseek.com/v1", "deepseek-v4-pro",
        "DeepSeek V4-Pro — 1.6T MoE, 100万上下文 (2026.04)",
    ),
    "openai": ProviderPreset(
        "openai", "https://api.openai.com/v1", "gpt-5.4",
        "OpenAI GPT-5.4 — 目前 API 最新旗舰 (2026.03)",
    ),
    "qwen": ProviderPreset(
        "qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3.6-plus",
        "通义千问 3.6-Plus — 100万上下文, 性能与成本均衡 (2026.04)",
    ),
    "glm": ProviderPreset(
        "glm", "https://open.bigmodel.cn/api/paas/v4", "glm-5.1",
        "智谱 GLM-5.1 — 全自治旗舰, 对标 Opus 4.6 (2026.04)",
    ),
    "moonshot": ProviderPreset(
        "moonshot", "https://api.moonshot.cn/v1", "kimi-k2.6",
        "月之暗面 Kimi K2.6 — 1T MoE, Agent 集群 (2026.04)",
    ),
    "siliconflow": ProviderPreset(
        "siliconflow", "https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V4-Flash",
        "硅基流动 — 第三方聚合 API (DeepSeek V4-Flash, 高性价比)",
    ),
}

DEFAULT_PROVIDER = "deepseek"


# ══════════════════ Agent 常量 ══════════════════

@dataclass(frozen=True)
class AgentConstants:
    """AI Agent 常量"""

    DEFAULT_MODEL: str = "deepseek-v4-pro"
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


# ══════════════════ PCB 常量 ══════════════════

@dataclass(frozen=True)
class PCBConstants:
    """PCB 解析与规则检查常量"""

    # 层名称（立创 EDA 导出）
    TOP_LAYER: str = "TopLayer"
    BOTTOM_LAYER: str = "BottomLayer"

    # 信号线规则
    SIGNAL_TRACE_MIN_WIDTH_MM: float = 0.2     # 信号线最小宽度
    SIGNAL_NET_KEYWORDS: tuple = (              # 低速信号网络关键词
        "SCK", "SCL", "SDA", "MISO", "MOSI", "SS",
        "TX", "RX", "SPI", "I2C", "UART",
        "CLK", "RST", "INT", "CS",
    )

    # 电源线规则
    POWER_NET_KEYWORDS: tuple = (               # 电源网络关键词
        "VCC", "VDD", "VEE", "VSS",
        "PWR", "POWER", "VBUS", "VBAT",
        "+5V", "+3.3V", "+12V", "+1.8V",
        "5V", "3V3", "3.3V", "12V", "1.8V",
        "VIN", "VOUT", "VREF",
        "GND", "AGND", "DGND", "PGND",
    )

    # IPC-2221 简化载流参数 (1oz 铜厚, 10°C 温升)
    IPC_K_FACTOR: float = 0.048     # 外层 K 系数
    IPC_TEMP_RISE: float = 10.0     # 允许温升 (°C)
    IPC_COPPER_OZ: float = 1.0      # 铜厚 (oz)
    POWER_CURRENT_DEFAULT_A: float = 0.5  # 无BOM信息时的默认电流估算

    # 模数分离
    ANALOG_COMPONENT_KW: tuple = (            # 模拟元件关键词
        "运放", "比较器", "ADC", "DAC",
        "OP", "LM", "AD", "TL",
        "传感器", "sensor",
        "模拟开关", "analog switch",
    )
    DIGITAL_COMPONENT_KW: tuple = (           # 数字元件关键词
        "MCU", "FPGA", "CPLD", "DSP",
        "STM32", "ESP32", "ATmega",
        "74HC", "74LS", "ARM",
    )
    AD_SEPARATION_MIN_MM: float = 5.0         # 模拟/数字最小分离距离 (mm)

    # 文件格式
    SUPPORTED_PCB_FORMATS: tuple = (".json", ".epro")


# ══════════════════ 单例实例 ══════════════════

BOM = BOMConstants()
AGENT = AgentConstants()
GUI = GUIConstants()
HTML = HTMLBOMConstants()
PCB = PCBConstants()

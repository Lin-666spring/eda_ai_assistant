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
        "openai", "https://api.openai.com/v1", "gpt-5.5",
        "OpenAI GPT-5.5 — 最新旗舰, 多模态 (2026.05)",
    ),
    "qwen": ProviderPreset(
        "qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3.7-max",
        "通义千问 3.7-Max — 最新旗舰, Coding Agent (2026.05)",
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
    "gemini": ProviderPreset(
        "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.5-flash",
        "Google Gemini 3.5 Flash — 最新稳定版, Agent/Coding (2026.05)",
    ),
    "claude": ProviderPreset(
        "claude", "https://api.anthropic.com/v1/messages", "claude-opus-4-8",
        "Anthropic Claude Opus 4.8 — 深度推理, 原生协议 (2026.05)",
    ),
    "doubao": ProviderPreset(
        "doubao", "https://ark.cn-beijing.volces.com/api/v3", "doubao-1.5-pro-256k",
        "豆包 1.5 Pro — 字节跳动, 256K上下文, 高性价比 (2026.05)",
    ),
    "minimax": ProviderPreset(
        "minimax", "https://api.minimax.io/v1", "MiniMax-M3",
        "MiniMax M3 — 最新旗舰, 1M上下文, 128K输出 (2026.06)",
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
# ══════════════════ 供应链常量 ══════════════════

@dataclass(frozen=True)
class SupplyConstants:
    """立创商城 API + BOM 健康检查常量"""

    # LCSC 官方 OpenAPI
    LCSC_API_BASE: str = "https://wmsc.lcsc.com/openapi"
    LCSC_API_SEARCH: str = "/v1/product/search"       # 关键字搜索
    LCSC_API_DETAIL: str = "/v1/product/detail"        # 商品详情
    LCSC_API_TIMEOUT: int = 15
    LCSC_MAX_PAGE_SIZE: int = 30

    # jlcsearch 公开 API（无需认证）
    JLCSEARCH_API: str = "https://jlcsearch.tscircuit.com/api"
    JLCSEARCH_TIMEOUT: int = 10

    # 缓存
    CACHE_TTL_HOURS: int = 24
    CACHE_DIR_NAME: str = "lcsc_cache"

    # BOM 健康检查
    LIFE_WARN_THRESHOLD_DAYS: int = 180         # 库存不足时开始预警
    PRICE_ESTIMATE_QTY: int = 100               # 估价用的批量数量
    ALT_MAX_RECOMMEND: int = 5                  # 替代料最多推荐数

    # 生命周期关键词
    EOL_KEYWORDS: tuple = ("NRND", "EOL", "Obsolete", "Discontinued", "停产")


@dataclass(frozen=True)
class WatcherConstants:
    """文件监听常量"""

    DEBOUNCE_SEC: float = 2.0
    PCB_EXTENSIONS: tuple = (".json", ".epro")
    # 立创 EDA 默认项目路径候选
    DEFAULT_WATCH_DIRS: tuple = (
        "Documents/LCEDA",
        "Documents/EasyEDA",
        "LCEDA",
    )


# ══════════════════ 闭环收敛常量 ══════════════════

@dataclass(frozen=True)
class ConvergenceConfig:
    """迭代收敛引擎常量 — 控制 ConvergenceMonitor 的终止判定阈值。

    所有阈值集中于此便于实验调参与论文消融，避免散落在策略类中。
    """

    # 迭代轮次上限（与历史 MAX_ROUNDS=3 保持一致）
    DEFAULT_MAX_ROUNDS: int = 3

    # 发散判定：本轮阻断违规数 > 首轮阻断数 × 该系数 → DIVERGED
    DIVERGENCE_FACTOR: float = 1.5

    # 发散判定：连续递增的阻断数轮数阈值（实际比较 streak+1 个数据点）
    DIVERGENCE_STREAK: int = 2

    # 震荡检测周期（A→B→A 模式，比较第 k 轮与第 k-period 轮指纹）
    OSCILLATION_PERIOD: int = 2

    # 文本指纹哈希长度（sha1 前缀，平衡碰撞率与可读性）
    FINGERPRINT_HASH_LEN: int = 12


# ══════════════════ 单例实例 ══════════════════

PCB = PCBConstants()
SUPPLY = SupplyConstants()
WATCHER = WatcherConstants()
CONVERGENCE = ConvergenceConfig()

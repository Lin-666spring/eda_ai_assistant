"""
项目全局常量集中管理
消除散落在各模块中的魔法数字和硬编码字符串
"""

import os
from enum import Enum
from dataclasses import dataclass
from pathlib import Path


# ══════════════════ 存储路径 ══════════════════

def app_home() -> Path:
    """应用数据目录（settings.json / sessions.db 的所在目录）。

    默认 `~/.eda_ai_assistant`；可用环境变量 `EDA_AI_HOME` 覆盖 —— 测试和
    受限环境（只读沙箱）靠它把落盘位置改到临时目录，避免 import 期就写用户主目录。
    """
    override = os.environ.get("EDA_AI_HOME")
    return Path(override).expanduser() if override else Path.home() / ".eda_ai_assistant"


# ══════════════════ 应用标识 ══════════════════
# 启动界面 / 标题栏 / 关于信息共用一处，别再各写各的版本号。
# （web/index.html 的 <title> 是静态 HTML，改版本时记得一起改。）

APP_NAME = "EDA AI 智能助手"
APP_TAGLINE = "面向立创EDA的智能辅助设计"
APP_VERSION = "0.8.0"


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
    """单个 LLM 厂商预设 — 厂商/模型的单一事实来源 (SSOT)

    `models` 是**离线兜底**清单（新→旧）。真正权威的是运行时调
    `GET {base_url}/models` 拉到的实时列表（见 src/agent/model_catalog.py），
    所以这里不需要追着厂商发版跑 —— 只要保证没网时也能选到能用的型号。
    """

    name: str
    base_url: str
    default_model: str
    description: str
    icon: str = ""                              # 卡片角标，如 "DS"
    models: tuple[str, ...] = ()                # 离线兜底模型清单（新→旧）
    protocol: str = "openai"                    # "openai" | "anthropic"
    key_url: str = ""                           # 申请 API Key 的地址
    notes: str = ""                             # 使用提示（如参数限制）
    brand: str = ""                             # 展示用品牌名（卡片标题）


# 主流厂商预设 — 2026-09 核对
# 说明：模型名核对于 2026-09-10，来源为各厂商官方文档/发布记录。
#       过时与否不再靠这份表兜着：设置面板的「拉取最新模型」会直接问厂商。
LLM_PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "deepseek": ProviderPreset(
        "deepseek", "https://api.deepseek.com/v1", "deepseek-flash",
        "DeepSeek V4.1-Flash — 1M 上下文 / 384K 输出，V4-Pro 已并入 Flash 计费",
        icon="DS", brand="DeepSeek",
        # deepseek-v4-pro 自 2026-09-14 起全部路由到 V4.1-Flash（官方公告），
        # deepseek-v4-flash / deepseek-v4-flash-vision-exp 已退役但仍被接受。
        models=("deepseek-flash", "deepseek-v4-pro"),
        key_url="https://platform.deepseek.com/api_keys",
    ),
    "openai": ProviderPreset(
        "openai", "https://api.openai.com/v1", "gpt-5.6-sol",
        "OpenAI GPT-5.6 Sol — 通用旗舰；GPT-6 Astra 更强但工具调用需 Responses API",
        icon="OA", brand="OpenAI",
        # 默认给 Sol 而不是 Astra：Astra 走 Chat Completions 时**已移除
        # temperature/top_p/logprobs**，且 function calling 只在 Responses API 上。
        models=("gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"),
        key_url="https://platform.openai.com/api-keys",
        notes="gpt-6-astra 不接受 temperature，且工具调用需 Responses API",
    ),
    "qwen": ProviderPreset(
        "qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3.7-max",
        "通义千问 3.7-Max — 1M 上下文，Coding Agent",
        icon="QW", brand="通义千问",
        models=("qwen3.7-max", "qwen3.7-plus"),
        key_url="https://bailian.console.aliyun.com/?apiKey=1",
    ),
    "glm": ProviderPreset(
        "glm", "https://open.bigmodel.cn/api/paas/v4", "glm-5.3",
        "智谱 GLM-5.3 — 编程旗舰；Flash 为多模态轻量版",
        icon="GL", brand="智谱 GLM",
        models=("glm-5.3", "glm-5.3-flash", "glm-5.2", "glm-5.1"),
        key_url="https://open.bigmodel.cn/usercenter/apikeys",
    ),
    "moonshot": ProviderPreset(
        "moonshot", "https://api.moonshot.cn/v1", "kimi-k3",
        "月之暗面 Kimi K3 — 1M 上下文 / 131K 输出",
        icon="KM", brand="Kimi",
        models=("kimi-k3", "kimi-k2.6"),
        key_url="https://platform.moonshot.cn/console/api-keys",
    ),
    "siliconflow": ProviderPreset(
        "siliconflow", "https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V4-Flash",
        "硅基流动 — 第三方聚合，一个 Key 路由多家模型",
        icon="SF", brand="硅基流动",
        models=("deepseek-ai/DeepSeek-V4-Flash",
                "Qwen/Qwen3.7-Plus",
                "Pro/Claude-Opus-4.8"),
        key_url="https://cloud.siliconflow.cn/account/ak",
    ),
    "gemini": ProviderPreset(
        "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash",
        "Google Gemini 3.8 Flash — 2026-09 最新，走 OpenAI 兼容端点",
        icon="GM", brand="Gemini",
        models=("gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"),
        key_url="https://aistudio.google.com/app/apikey",
    ),
    "claude": ProviderPreset(
        "claude", "https://api.anthropic.com/v1/messages", "claude-opus-5",
        "Anthropic Claude Opus 5 — 原生 Messages API（非 OpenAI 兼容）",
        icon="CL", brand="Claude", protocol="anthropic",
        # 4.x 仍可调用但已归入 Legacy；Opus 4.8 只是兜底保留。
        models=("claude-opus-5", "claude-sonnet-5", "claude-fable-5-1",
                "claude-haiku-4-5", "claude-opus-4-8"),
        key_url="https://console.anthropic.com/settings/keys",
    ),
    "doubao": ProviderPreset(
        "doubao", "https://ark.cn-beijing.volces.com/api/v3", "doubao-1.5-pro-256k",
        "豆包 1.5 Pro — 字节跳动，256K 上下文",
        icon="DB", brand="豆包",
        models=("doubao-1.5-pro-256k", "doubao-1.5-lite-32k"),
        key_url="https://console.volcengine.com/ark",
        notes="方舟要求用「接入点 ID (ep-xxx)」或开通后的模型名",
    ),
    "minimax": ProviderPreset(
        "minimax", "https://api.minimax.io/v1", "MiniMax-M3",
        "MiniMax M3 — 1M 上下文 / 128K 输出",
        icon="MM", brand="MiniMax",
        models=("MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.5"),
        key_url="https://platform.minimaxi.com/user-center/basic-information/interface-key",
    ),
}

DEFAULT_PROVIDER = "deepseek"


def get_provider_preset(provider: str | None) -> ProviderPreset:
    """按 key 取厂商预设，未知/空值回落默认厂商（大小写不敏感）。"""
    return LLM_PROVIDER_PRESETS.get(
        (provider or DEFAULT_PROVIDER).lower(),
        LLM_PROVIDER_PRESETS[DEFAULT_PROVIDER],
    )


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

    # 两段式启动：先小窗显示加载态，再展开成正式界面。
    # SPLASH_* 同时喂给 Chrome 的 --window-size 和 eel 的 size=，
    # MAIN_* 只在展开时用（前端 resizeTo，见 web/index.html 内联 boot 脚本）。
    SPLASH_WIDTH: int = 480
    SPLASH_HEIGHT: int = 340
    MAIN_WIDTH: int = 1300
    MAIN_HEIGHT: int = 840
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

    # ── 走线类规则阈值 ──
    # 2026-09 用 76 个唯一真实 .epro2 设计校准；度量口径与分位数见
    #   scripts/calibrate_trace_thresholds.py
    #   experiment_results/trace_threshold_calibration/report.txt
    # 信号线宽不用单一下限，按「绝对工艺下限 + 本板主流线宽」两级判定：
    #   - ABS：细于 0.1mm(≈4mil，一般厂最小) → 可能做不出来
    #   - REL：细于本板信号线宽众数的 0.6 倍 → 明显偏离本板设计意图（疑似误用细线）
    #   固定 0.127mm 会命中 1347 网络 / 13 设计（立创泰山派3M 一块就 501 条，因为
    #   整板用的是 4.8mil 主流宽）；改成两级判据后命中 268 网络 / 8 设计，
    #   且「整板统一用细线」的专业设计不再被误报。
    SIGNAL_TRACE_ABS_MIN_WIDTH_MM: float = 0.1
    SIGNAL_TRACE_REL_MIN_RATIO: float = 0.6
    SIGNAL_NET_KEYWORDS: tuple = (              # 低速信号网络关键词
        "SCK", "SCL", "SDA", "MISO", "MOSI", "SS",
        "TX", "RX", "SPI", "I2C", "UART",
        "CLK", "RST", "INT", "CS",
    )

    # 走线到板框最小间距 (mm)。JLC 铜到边最小 0.2 / 推荐 0.3。
    #   实测 40 个有真实板框的设计：最小 0.292mm，<0.3 的仅 2 条折线。
    TRACE_EDGE_CLEARANCE_MIN_MM: float = 0.3

    # 过孔密度：只对「高速网络」生效，单网络过孔数达到该值即告警。
    #   校准前对全部网络生效：646 个网络 / 73 个设计（GND 缝合孔上千个也报）；
    #   限定高速网络后 27 个网络 / 9 个设计。
    VIA_DENSITY_MAX_PER_NET: int = 5
    VIA_DENSITY_NET_KEYWORDS: tuple = ("CLK", "PWM", "SW", "SENSE", "FB", "DRV", "GATE", "DRIVE")

    # 3W 串扰：间距系数（经验准则）+ 平行重叠长度门限。
    #   只用最短距离判定时 74/74 个设计全中（交叉/过孔处必然接近）；
    #   要求平行重叠 >5mm 后降到 242 对 / 34 个设计。
    CROSSTALK_SPACING_FACTOR: float = 3.0
    CROSSTALK_MIN_PARALLEL_MM: float = 5.0

    # 走线拐角（锐角 / 直角）：判定的是**内角**，45° 布线产生的拐角是 135°。
    #   2026-09 用 76 个唯一真实设计（78 个 .epro2 去重）校准：
    #   scripts/calibrate_trace_thresholds.py --no-crosstalk
    #   --out experiment_results/acute_angle_calibration
    #   串联后拐角共 110231 处，以 135°/130° 为主（45° 布线）；内角 <89° 的锐角
    #   862 处 / 63 设计（中位 3 处/板），直角 2146 处 / 75 设计。锐角里有一部分是
    #   焊盘入口处 <0.05mm 的短桩（属焊盘几何而非布线选择），用最小腿长门限滤除
    #   （不加门限时 <90° 有 1440 处）。
    TRACE_ACUTE_ANGLE_MAX_DEG: float = 89.0    # 内角 < 此值 → 锐角（酸陷阱）
    TRACE_RIGHT_ANGLE_MIN_DEG: float = 89.0    # 内角落在 [min,max] → 直角
    TRACE_RIGHT_ANGLE_MAX_DEG: float = 91.0
    TRACE_CORNER_MIN_LEG_MM: float = 0.05      # 拐角任一侧腿短于此值视为退化
    TRACE_CORNER_PAD_LEG_MM: float = 0.5       # 两腿均短于此值且贴近焊盘/过孔 → 焊盘入口几何
    TRACE_CORNER_PAD_CLEAR_MM: float = 1.0     # 「贴近焊盘/过孔」的判定半径 (mm)

    # 差分对：长度失配门限 (mm) 与「未紧耦合」间距门限（线宽倍数）。
    #   ground truth 来自工程 NET 规则 (differentialName)，576 对。
    #   失配：p50=0.023 / p75=0.181 / p90=1.63mm；>0.5mm 命中 115 对 / 32 设计
    #        （原 5mil：152 对 / 40 设计）。
    #   对内最小间距/线宽：p25=1.77 / p50=2.10 / p90=2.71 / p95=3.0W；
    #        >3W 仅 16 对，>4W 6 对 → 门限取 3W。
    DIFF_PAIR_MAX_SKEW_MM: float = 0.5
    DIFF_PAIR_MAX_GAP_FACTOR: float = 3.0

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
    SUPPORTED_PCB_FORMATS: tuple = (".json", ".epro", ".epro2")


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

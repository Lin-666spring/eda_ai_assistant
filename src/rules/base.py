"""规则基础设施 —— 数据类/常量/模块级辅助（P1-6 阶段B 从 checker.py 逐字迁出）。

ADVISE_RULES、_DCDC_PN_PREFIXES、_kw_hit 等口径在这里单点维护，
三个规则模块与 facade 显式导入，杜绝再漂移。
"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..constants import PCB
from ..pcb.geometry import trace_corners
from ..pcb.models import PCBData

logger = logging.getLogger(__name__)


# ── 规则类型：detect = 对这块板做可证伪的判定（可计精确率）；
#              advise = 通用提示/建议，或「缺数据/缺拓扑即报」——不构成检出能力 ──
# 依据 2026-09-24 规则抽查：13 条「几乎每块板都响」的规则贡献了 63% 的违规数量，
# 把它们的「有输出」计入覆盖率就是虚高（见 docs/规则抽查_报告_2026-09-18.md 第 5 节）。
ADVISE_RULES: frozenset = frozenset({
    "走线直角检查", "时钟信号包地检查", "高速信号参考平面检查",
    "地平面连续性检查", "PDN 目标阻抗分析", "丝印可读性检查",
    "丝印焊盘间距检查", "光学定位点检查", "过孔热焊盘检查",
    "测试点覆盖检查", "开关电源布局检查", "铜皮连接检查",
    "短桩线检查", "热焊盘检查",
    # 无网络关联信息时「某电容离最近 IC 多远」只是建议（板上总有远端电容），
    # 要变成可证伪的判定需要 netlist 关联，故先归提示类。
    "去耦电容距离检查",
    # 2026-10-09 噪声清扫：位号跳号在真实设计里是正常实践（预留位/删除元件/
    # 功能分区编号），改为每板至多 1 条的设计卫生提示，不属判定类。
    "位号连续性检查",
})


def rule_kind(rule_name: str) -> str:
    """规则类型：'detect'（判定类）| 'advise'（提示类）。"""
    return "advise" if rule_name in ADVISE_RULES else "detect"


class RuleSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class RuleViolation:
    rule_name: str
    description: str
    severity: RuleSeverity
    location: str = ""
    suggestion: str = ""
    theory: str = ""


# ═══ PCB 几何辅助（走线类规则共用）═══

def _pt_seg_dist(p, s, e) -> float:
    """点 p 到线段 (s,e) 的最短距离。"""
    sx, sy = s
    dx, dy = e[0] - sx, e[1] - sy
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - sx, p[1] - sy)
    t = ((p[0] - sx) * dx + (p[1] - sy) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - (sx + t * dx), p[1] - (sy + t * dy))


def _is_inner_layer(pcb, layer: str) -> bool:
    """走线是否在内层 —— 决定 IPC-2221 载流系数（内层 k≈外层一半）。

    2026-09-18 抽查修正：原先用「整板是否出现过 inner 层电源走线」的板级布尔，
    外层（Top/Bottom）电源线会被按内层降额。这里按层名判定：
    名字含 top/bottom，或等于叠层首/末层 → 外层；其余（Inner1/GND02/S03/PWR05…）→ 内层。
    """
    name = str(layer or "").strip().lower()
    if not name:
        return False
    if "top" in name or "bottom" in name:
        return False
    layers = [str(x).strip().lower() for x in (getattr(pcb, "layers", None) or [])]
    if len(layers) >= 2 and name in (layers[0], layers[1]):
        return False   # .epro2 叠层表按层 id 排序：前两个即 Top/Bottom
    return True


def _seg_seg_dist(a, b, c, d) -> float:
    """两条线段 (a,b) 与 (c,d) 的最短距离；相交为 0。"""
    def _cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    d1, d2 = _cross(c, d, a), _cross(c, d, b)
    d3, d4 = _cross(a, b, c), _cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0
    return min(
        _pt_seg_dist(a, c, d), _pt_seg_dist(b, c, d),
        _pt_seg_dist(c, a, b), _pt_seg_dist(d, a, b),
    )


def _parallel_overlap_len(a, b, c, d, tol_rad: float = 0.2618) -> float:
    """两条近似平行（夹角 <15°）线段的投影重叠长度；不平行返回 0。"""
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    ang2 = math.atan2(d[1] - c[1], d[0] - c[0])
    if abs((ang - ang2 + math.pi / 2) % math.pi - math.pi / 2) > tol_rad:
        return 0.0
    ux, uy = math.cos(ang), math.sin(ang)
    p1, p2 = a[0] * ux + a[1] * uy, b[0] * ux + b[1] * uy
    q1, q2 = c[0] * ux + c[1] * uy, d[0] * ux + d[1] * uy
    return max(0.0, min(max(p1, p2), max(q1, q2)) - max(min(p1, p2), min(q1, q2)))


# ═══ 元件分类辅助 ═══
# 两层策略：
#   ① 自研 ML 模型 (ComponentPredictor, ~600K TextCNN, 12 细类 → 粗类映射)
#   ② 规则回退（位号前缀 + 描述关键词），ML 不可用或低置信度时使用
#
# 真实立创 BOM 的描述常只是值/型号（如 "100nF"、"4kHz"），part_number 可能为空，
# ML 模型通过多字段拼接（ref/pn/pkg/val/desc）综合判断，比纯规则更鲁棒。

# ── 本地模型懒加载 ──

_component_predictor = None
_component_model_attempted = False
_COMPONENT_MODEL_PATH = "data/component_model.pt"
_COMPONENT_VOCAB_PATH = "data/vocab.json"
_ML_CONFIDENCE_THRESHOLD = 0.45  # 低于此阈值回退规则


def _init_component_model() -> bool:
    """懒加载元件分类模型，成功返回 True。"""
    global _component_predictor, _component_model_attempted
    if _component_model_attempted:
        return _component_predictor is not None
    _component_model_attempted = True

    import os
    if not os.path.exists(_COMPONENT_MODEL_PATH):
        logger.info("元件分类模型文件不存在，使用规则分类")
        return False

    try:
        from src.ml.component_classifier import ComponentPredictor
        _component_predictor = ComponentPredictor.from_path(
            _COMPONENT_MODEL_PATH, _COMPONENT_VOCAB_PATH
        )
        if _component_predictor:
            logger.info("本地元件分类模型加载成功 (~600K TextCNN)")
            return True
    except Exception as e:
        logger.warning("元件分类模型加载失败: %s，回退规则", e)
    return False


def _classify_component_fine(item) -> tuple[str, float]:
    """细粒度 ML 分类，返回 (12类名, 置信度)。ML 不可用时返回 ("", 0.0)。"""
    if _init_component_model() and _component_predictor is not None:
        try:
            fine_type, confidence, _debug = _component_predictor.classify(item)
            if confidence >= _ML_CONFIDENCE_THRESHOLD:
                return fine_type, confidence
        except Exception:
            pass
    return ("", 0.0)


def _parse_capacitance(val_str: str) -> Optional[float]:
    """解析容值字符串（含 EIA 三位码），返回法拉，失败返回 None。"""
    if not val_str:
        return None
    val_str = val_str.strip().upper().replace(" ", "")
    try:
        from src.bom.normalizer import ValueNormalizer
        nv = ValueNormalizer.normalize(val_str)
        if nv.base_value:  # normalize("104") 返回 0，需继续走 EIA fallback
            return nv.base_value
    except Exception:
        pass
    # Fallback: EIA 3-digit code (e.g. "104" = 10*10^4 pF = 100nF)
    if val_str.isdigit() and len(val_str) == 3:
        try:
            return int(val_str[0:2]) * 10 ** int(val_str[2]) * 1e-12
        except Exception:
            pass
    return None


_VOLTAGE_TOKEN_RE = re.compile(r"(?<![A-Z0-9.])(\d+(?:\.\d+)?)\s*V(?![A-Z0-9])")


def _extract_voltage_rating(*texts: str) -> Optional[float]:
    """从 value / 料号里提取耐压标注 (V)，取不到返回 None。

    2026-09-24 抽查修正：原实现用 (\\d+)V 直接在 value + 料号里搜，料号里的
    …R0VH… 会被抓成「0V」，于是报「耐压 0.0V，裕量不足」。现在要求电压是独立
    token（前后不能是字母/数字/小数点），并且忽略 <2.5V 的取值——那不是耐压标注。
    """
    for text in texts:
        if not text:
            continue
        for m in _VOLTAGE_TOKEN_RE.finditer(str(text).upper()):
            v = float(m.group(1))
            if v >= 2.5:
                return v
    return None


def _component_count(item) -> int:
    """元件总数 = max(quantity, 位号列表长度)。真实 BOM 常以逗号分隔多位号同行。"""
    qty = getattr(item, "quantity", 1) or 1
    n_refs = len(item.reference_list)
    return max(int(qty), n_refs)


def _kw_hit(text: str, keywords) -> bool:
    """关键词命中判定：≤3 个 ASCII 字母的短词要求独立词边界。

    2026-09-24 抽查修正：裸子串匹配是 8 条 BOM 规则系统性误报的根因——
    "AD" 命中 PicoBlade（FPC 连接器被当模拟器件）、"SI" 命中 inmp441（麦克风被当
    MOSFET）、"MP" 命中 CL10A226MP8NUNE（MLCC 子串）。短词一律要求词边界。
    """
    for kw in keywords:
        k = str(kw).lower()
        if len(k) <= 3 and k.isascii() and k.isalpha():
            if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text):
                return True
        elif k in text:
            return True
    return False


def _net_kw_hit(name: str, keywords) -> bool:
    """网络名关键词命中：短词右侧放行数字后缀（CLK2/PWM3/SW1），仍拒绝内嵌。

    2026-10-09 抽查修正：网络名普遍带数字编号（CLK2/PWM3），_kw_hit 的双侧
    词边界会把它们整体漏掉；但纯子串又把 "SW" 命中 …BUZZER_SWITCH（拨码开关
    网络被当高速网）。折中：左侧拒字母数字、右侧只拒字母——内嵌词（SWITCH）
    不中、带编号（SW1）命中。
    """
    n = (name or "").lower()
    for kw in keywords:
        k = str(kw).lower()
        if len(k) <= 4 and k.isascii() and k.isalpha():
            if re.search(rf"(?<![a-z0-9]){re.escape(k)}[0-9]*(?![a-z])", n):
                return True
        elif k in n:
            return True
    return False


def _row_text(item) -> str:
    """BOM 行关键词匹配文本：料号 + 描述 + 值（小写）。

    2026-10-09 抽查修正：真实立创 BOM 常把型号只写在 value（或 description
    整行为空），旧规则只搜 pn+description 双向漏——P6SMBJ6.0CA 这类真 TVS
    写在 value 里就漏认。统一从这里取文本。
    """
    return (
        f"{getattr(item, 'part_number', '')} "
        f"{getattr(item, 'description', '')} "
        f"{getattr(item, 'value', '')}"
    ).lower()


def _any_ref_prefix(item, prefixes) -> bool:
    """任一位号的字母前缀命中（一行可含逗号分隔多位号）。"""
    for token in re.split(r"[,，\s]+", (getattr(item, "reference", "") or "").strip()):
        if not token:
            continue
        prefix = "".join(c for c in token if c.isalpha()).upper()
        if prefix in prefixes:
            return True
    return False


def _is_resistor_row(item) -> bool:
    """电阻行判定：位号前缀优先（R/RN/RP 排阻），描述词仅回退。

    2026-10-09 抽查修正：LCSC 描述是「22uF ±20% 10V」式参数文本、不含
    「电阻」二字，大量行 description 为空——「描述含电阻」判据双向下失效，
    上拉/FB 分压/LED 限流五条规则恒报。位号前缀是唯一稳定信号。
    """
    if _any_ref_prefix(item, {"R", "RN", "RNC", "NR", "RP"}):
        return True
    return _kw_hit(_row_text(item), ("电阻", "resistor"))


def _is_cap_row(item) -> bool:
    """电容行判定：位号前缀优先（C），描述词仅回退（口径同 _is_resistor_row）。"""
    if _any_ref_prefix(item, {"C", "CV", "CE"}):
        return True
    return _kw_hit(_row_text(item), ("电容", "capacitor"))


# ── 电源入口识别（EMI 滤波 / 电源极性保护共用，2026-10-09 统一口径）──
# 旧判据对任意 BOM 行做裸子串（pwr_kw 含 "PWR"/"VIN"/"VBUS"）：SN74HC125PWR
# 的封装后缀、LDO 描述里的「Vin=18V」都成了「电源入口」。入口是物理端口——
# ① 网表：入口语义的电源网络挂在连接器/电池引脚上（最可靠）；
# ② BOM 回退：连接器/电池位号行 + 明确入口词（不含裸 VIN/PWR/power）。
_PWR_ENTRY_NET_RE = re.compile(
    r"(VIN|VBUS|VBAT|VDC|DCIN|DC_IN|DC-IN|VMAIN|PWR_IN|POWER_IN|\d+V_?IN|VCC_?\d{2}V)",
    re.IGNORECASE)
_PWR_ENTRY_DESC_KW = ("电源插座", "电源接口", "电源输入", "电源座", "电源口",
                      "dc-in", "dcin", "dc005", "dc-005", "电池座", "电池盒")
_ENTRY_CONN_PREFIXES = {"J", "P", "CN", "DC", "BT", "BAT", "CON", "USB", "FPC"}


def _has_power_entry(bom_items, netlist, include_usb: bool = True) -> bool:
    """板上有直流电源入口（电源座/电池/USB 供电），供 EMI/反接保护规则门控。

    include_usb=False 时不把 USB VBUS 当入口——USB 座有键控、反接不成立，
    VBUS 上加共模电感也非常规做法（2026-10-09 金样：USB 小设备 17 板因此
    误报「缺 EMI 滤波」）。
    """
    prefixes = _ENTRY_CONN_PREFIXES if include_usb else _ENTRY_CONN_PREFIXES - {"USB"}
    for name, pins in (netlist or {}).items():
        if not _PWR_ENTRY_NET_RE.search(str(name)):
            continue
        for p in (pins if isinstance(pins, (list, tuple, set)) else getattr(pins, "pins", None) or ()):
            ref = str(p).split(".")[0]
            prefix = "".join(c for c in ref if c.isalpha()).upper()
            if prefix in prefixes:
                return True
    for item in bom_items:
        if not _any_ref_prefix(item, prefixes):
            continue
        if _kw_hit(_row_text(item), _PWR_ENTRY_DESC_KW):
            return True
    return False


def _xy(pos) -> tuple:
    """位置取 (x, y)：dict 优先，兼容 (list, tuple)；其它形态一律 (0, 0)。

    值不做 float 包装，保持各规则原内联写法的返回类型与缺省语义。
    """
    if isinstance(pos, dict):
        return pos.get("x", 0), pos.get("y", 0)
    if isinstance(pos, (list, tuple)):
        return pos[0], (pos[1] if len(pos) > 1 else 0)
    return 0, 0


# ── 网络类别判定（串扰 / 阻抗等高速类规则共用） ──

_POWER_OR_GROUND_KW = ("gnd", "agnd", "dgnd", "pgnd", "vss", "vcc", "vdd", "vbus",
                       "vbat", "earth", "shield", "pwr", "power", "vref", "vin", "vout")

_HIGH_SPEED_NET_KW = ("usb", "hdmi", "pcie", "lvds", "eth", "rgmii", "mipi", "ddr",
                      "sdio", "sata", "clk", "sck", "sclk", "mclk", "osc", "xtal",
                      "spi", "mosi", "miso", "can", "rs485", "swclk", "swdio",
                      "jtag", "tck", "tms", "dp", "dm", "d+", "d-")

_LOW_SPEED_NET_KW = ("32k", "32.768", "32768", "key", "btn", "button", "buzz",
                     "beep", "led", "gpio", "rst", "reset", "pwrkey", "boot",
                     "test", "tp", "nc")

# 有阻抗控制要求的接口（差分阻抗判据只对这些差分组生效）
_HIGH_SPEED_IF_KW = ("usb", "hdmi", "lvds", "pcie", "eth", "mipi", "sata", "ddr",
                     "rgmii", "sdio", "ss", "can", "rs485", "rf")


# ── 开关稳压器（DC-DC）识别口径（多条规则共用，2026-10-06 统一）──
# ① 料号前缀必须命中明确稳压器系列：裸 "MP"/"XL"/"SY"/"RT" 两字母前缀会命中
#    MPU6500（陀螺仪）、XL-1608（LED）、RTL8201（以太网 PHY）、CL10A226MP8NUNE
#    （MLCC 子串）。2026-09-24 在 _check_dcdc_feedback_network 修正过一次，
#    但同口径的「开关电源布局」「功率回路面积」两条规则漏改，2026-10-06 收编到此。
_DCDC_PN_PREFIXES: tuple = (
    "MP1", "MP2", "MP4", "MP8", "TPS", "LM2596", "LM2576", "LM2577", "LM2678",
    "XL4", "XL6", "SY7", "SY8", "MT3", "RT8", "AP2", "AP3", "LMR", "SGM",
    "TD1", "TMI", "ETA",
)
# ② 描述关键词走 _kw_hit（≤3 字母的 ASCII 短词要求词边界），避免裸子串误命中
_DCDC_DESC_KW = ("dc-dc", "dc/dc", "buck", "boost", "降压", "升压", "开关稳压",
                 "开关电源", "稳压器", "regulator", "converter")


def _is_dcdc_part(item) -> bool:
    """按统一口径判定一个 BOM 行是否为开关稳压器（料号前缀或描述关键词）。"""
    pn = (getattr(item, "part_number", "") or "").strip().upper()
    if any(pn.startswith(p) for p in _DCDC_PN_PREFIXES):
        return True
    desc = (
        f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}"
    ).lower()
    return _kw_hit(desc, _DCDC_DESC_KW)


def _is_power_or_ground_net(name: str) -> bool:
    """电源/地网络判定（串扰、阻抗规则先排除它们）。"""
    n = (name or "").upper()
    if any(kw.upper() in n for kw in PCB.POWER_NET_KEYWORDS):
        return True
    return _kw_hit(n.lower(), _POWER_OR_GROUND_KW)


def _net_class(name: str, diff_members) -> str:
    """网络类别：'diff'（工程声明的差分组）| 'high' | 'low' | 'other'。"""
    n = (name or "").upper()
    if n in diff_members:
        return "diff"
    low = n.lower()
    if _kw_hit(low, _LOW_SPEED_NET_KW):
        return "low"
    if _kw_hit(low, _HIGH_SPEED_NET_KW):
        return "high"
    return "other"


def _classify_component(item) -> str:
    """按位号前缀 + 描述关键词分类：'ic' | 'cap' | 'passive' | 'other'。

    优先使用自研 ML 模型（12 细类 → 粗类映射），
    不可用时回退到位号前缀 + 描述关键词规则。
    """
    from src.ml.component_classifier import FINE_TO_COARSE

    # ── ① ML 模型优先 ──
    fine_type, confidence = _classify_component_fine(item)
    if fine_type:
        coarse = FINE_TO_COARSE.get(fine_type, "other")

        # 安全网：明确非 IC 的前缀绝不接受 ML 的 ic 分类
        # 防止 D-ESD器件、X-连接器 等被 ML 看到描述中的 "USB"/"IC" 字眼而误判
        ref_list = item.reference_list
        ref = ref_list[0] if ref_list else ""
        prefix = "".join(ch for ch in ref if ch.isalpha()).upper()

        _non_ic_prefixes = (
            "C", "R", "RN", "RNC", "L", "FB",           # 电容/电阻/电感
            "D", "LED", "Q", "T", "SCR", "TRIAC",       # 二极管/三极管/MOSFET
            "X", "Y", "XTAL", "OSC",                     # 晶振
            "J", "CN", "CON", "HDR", "P", "FPC", "TP",  # 连接器
            "MP", "H", "USB", "SH", "SM",
            "SW", "K", "S", "BUTTON", "BUZZ", "BZ",     # 开关/蜂鸣器
            "BUZZER", "LS", "SPK", "F", "FU",            # 保险丝
            "RL", "RELAY",                                # 继电器
        )
        if coarse == "ic" and prefix in _non_ic_prefixes:
            # ML 误判，回退到规则
            logger.debug(
                "ML 将 %s(%s) 分类为 ic，但前缀 %s 明确非 IC，回退规则",
                ref, getattr(item, "part_number", ""), prefix,
            )
        else:
            return coarse

    # ── ② 规则回退 ──
    ref_list = item.reference_list
    ref = ref_list[0] if ref_list else ""
    prefix = "".join(ch for ch in ref if ch.isalpha()).upper()
    desc = (
        f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} "
        f"{getattr(item, 'value', '')}"
    ).lower()

    # ── 明确类别，优先判定 ──
    if prefix == "C" or "电容" in desc or "capacitor" in desc:
        return "cap"
    if prefix in ("R", "RN", "RNC") or "电阻" in desc or "resistor" in desc:
        return "passive"
    if prefix in ("L", "FB") or "电感" in desc or "inductor" in desc or "磁珠" in desc:
        return "passive"
    if prefix == "D" or "二极管" in desc or "diode" in desc or "led" in desc:
        return "passive"
    # 三极管/MOSFET/晶闸管：开关器件，不由去耦检查按 IC 要求
    if prefix in ("Q", "T", "SCR", "TRIAC") or any(k in desc for k in ("三极管", "mosfet", "晶体管", "晶闸管")):
        return "passive"
    # 晶振/振荡器
    if prefix in ("X", "Y", "XTAL", "OSC") or any(k in desc for k in ("晶振", "crystal", "oscillator", "mhz", "khz", "32.768")):
        return "other"
    # 连接器/机械件/测试点/端子
    conn_words = ("连接器", "端子", "排针", "排母", "插座", "排线", "wafer", "connector",
                  "header", "socket", "螺丝", "螺母", "测试点", "压接", "fpc", "xh")
    if prefix in ("J", "CN", "CON", "HDR", "P", "FPC", "TP", "MP", "H", "USB", "SH", "SM") or any(k in desc for k in conn_words):
        return "other"
    # 开关/保险丝/蜂鸣器/继电器
    if prefix in ("SW", "K", "S", "BUTTON", "BUZZ", "BZ", "BUZZER", "LS", "SPK", "F", "FU", "RL", "RELAY"):
        return "other"
    # LED（位号 LED 前缀）
    if prefix == "LED":
        return "passive"

    # ── IC 判定 ──
    if prefix in ("U", "IC", "LDO"):
        return "ic"
    ic_words = ("芯片", "单片机", "处理器", "控制器", "稳压", "dc-dc", "dc/dc", "降压",
                "升压", "转换器", "驱动", "fpga", "dsp", "soc", "传感器", "运放",
                "放大器", "比较器", "wroom", "esp32", "stm32", "mcu", "chip",
                "regulator", "controller", "converter", "driver", "sensor",
                "amplifier", "module", "模块")
    if any(k in desc for k in ic_words):
        return "ic"
    return "other"


def _parse_component_value(val: str):
    """解析 R/C/L 参数值 -> (mantissa, exponent)。返回 None 表示无法解析。"""
    val = val.strip().upper()
    if re.fullmatch(r'\d{3}', val):
        return None
    multipliers = {
        "P": -12, "PF": -12, "N": -9, "NF": -9, "NH": -9,
        "U": -6, "UF": -6, "UH": -6, "ΜF": -6, "Μ": -6,
        "M": 6, "MΩ": 6, "MEG": 6,
        "K": 3, "KΩ": 3, "KILO": 3,
        "R": 1, "Ω": 0, "OHM": 0, "F": 0, "H": 0,
    }
    match = re.match(r'([\d.]+)\s*([A-Za-zΩΜμ]+)?', val)
    if not match:
        return None
    try:
        num = float(match.group(1))
    except ValueError:
        return None
    unit = (match.group(2) or "").upper().replace("Μ", "U")
    exp = 0
    for kw, e in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if unit == kw:
            exp = e
            break
    return (num, exp)


def group_violations_by_component(violations: list) -> dict:
    """将违规列表按元件引用分组，用于 AI Verification Map 叠加层。

    从 violation.location 字段中用正则提取元件引用（如 U1, R5, C3），
    将每条违规归类到对应元件。location 为空的违规归入 "__board__" 键。

    Args:
        violations: RuleViolation 列表

    Returns:
        {
            "U1": [{"rule": "去耦电容检查", "severity": "error",
                     "desc": "...", "suggestion": "..."}, ...],
            "__board__": [...],   # 板级违规（无明确元件引用）
        }
    """
    result: dict[str, list[dict]] = {}

    for v in violations:
        # 尝试从 location 提取元件引用
        if v.location:
            refs = re.findall(r'[A-Z]+\d+', v.location.upper())
        else:
            refs = []

        sev = v.severity.value if hasattr(v.severity, 'value') else str(v.severity)

        entry = {
            "rule": v.rule_name,
            "severity": sev,
            "desc": v.description,
            "suggestion": v.suggestion,
            "theory": v.theory,
        }

        if refs:
            for ref in refs:
                result.setdefault(ref, []).append(entry)
        else:
            # 无元件引用的违规归入板级
            result.setdefault("__board__", []).append(entry)

    return result

"""布局位置类规则 —— 从 checker.py 机械迁出（P1-6 阶段B，纯移动）。"""

import logging
import math
import re
from ..constants import PCB

from .base import (
    RuleSeverity,
    RuleViolation,
    _COMPONENT_MODEL_PATH,
    _COMPONENT_VOCAB_PATH,
    _DCDC_DESC_KW,
    _HIGH_SPEED_IF_KW,
    _HIGH_SPEED_NET_KW,
    _LOW_SPEED_NET_KW,
    _ML_CONFIDENCE_THRESHOLD,
    _POWER_OR_GROUND_KW,
    _VOLTAGE_TOKEN_RE,
    _classify_component,
    _classify_component_fine,
    _component_count,
    _component_model_attempted,
    _component_predictor,
    _extract_voltage_rating,
    _init_component_model,
    _is_dcdc_part,
    _is_inner_layer,
    _is_power_or_ground_net,
    _kw_hit,
    _net_class,
    _parallel_overlap_len,
    _parse_capacitance,
    _parse_component_value,
    _pt_seg_dist,
    _seg_seg_dist,
    _xy,
    group_violations_by_component,
    rule_kind,
)

logger = logging.getLogger(__name__)

# ── 元件体尺寸（几何批 2026-10-10）──
# 封装体外形（mm，长×宽，不含引脚）。两路解析：
# ① 立创封装名内嵌尺寸（SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR → 2.9×1.3）；
# ② 片式封装码查表（R0402/C0603_5/LED0805 → 表值，IPC-7351 体尺寸口径）。
# 两路都落空的（连接器/异形/无封装名 404 条）诚实跳过——体尺寸猜错比
# 不测更糟。Mark/定位/安装孔没有「体」，整行不参与配对。
_EMBEDDED_DIMS_RE = re.compile(r"_L(\d+(?:\.\d+)?)-W(\d+(?:\.\d+)?)")
_CHIP_CODE_RE = re.compile(
    r"(?:^|[^0-9])(0201|0402|0603|0805|1206|1210|1806|1812|2010|2512)(?:[^0-9]|$)")
_CHIP_BODY_MM = {
    "0201": (0.6, 0.3), "0402": (1.0, 0.5), "0603": (1.6, 0.8),
    "0805": (2.0, 1.25), "1206": (3.2, 1.6), "1210": (3.2, 2.5),
    "1806": (4.5, 1.6), "1812": (4.5, 3.2), "2010": (5.0, 2.5),
    "2512": (6.4, 3.2),
}
_NO_BODY_RE = re.compile(
    r"test[-_ ]?point|fiducial|\bmark\b|基准|定位|\bhole\b|\bm3\b|\bnpth\b|mounting")
# JLC 机贴元件体最小间隙（edge-to-edge）；0.2~0.5mm 可贴但返修困难，
# 建议 ≥0.5mm(0603)/≥0.8mm(0805) 写在 suggestion 里
_COMPONENT_GAP_MIN_MM = 0.2
# 焊盘佐证门：体「相交/紧贴」但焊盘中心距仍 ≥此值的，判为封装含引脚
# 尺寸的口径噪声（金样判读：真事件焊盘距 0~0.4mm，口径噪声 2.3mm+）
_PAD_CORROB_MAX_MM = 1.5


def _body_dims(pos: dict):
    """元件体尺寸 (长, 宽) mm；无法定体尺寸返回 None。"""
    blob = " ".join(str(pos.get(k) or "") for k in
                    ("footprint_name", "footprint", "value", "device", "part_number"))
    if _NO_BODY_RE.search(blob.lower()):
        return None
    m = _EMBEDDED_DIMS_RE.search(blob.upper())
    if m:
        dims = (float(m.group(1)), float(m.group(2)))
    else:
        m = _CHIP_CODE_RE.search(blob.upper())
        if m:
            dims = _CHIP_BODY_MM[m.group(1)]
        else:
            return None
    if dims[0] <= 0 or dims[1] <= 0:
        return None
    return max(dims), min(dims)


def _rect_corners_mm(x: float, y: float, long_: float, short: float,
                     rot_deg: float) -> list[tuple[float, float]]:
    """体矩形四角（长边沿 rotation 方向）。"""
    rad = math.radians(rot_deg or 0.0)
    c, s = math.cos(rad), math.sin(rad)
    hl, hw = long_ / 2.0, short / 2.0
    return [
        (x + hl * c - hw * s, y + hl * s + hw * c),
        (x + hl * c + hw * s, y + hl * s - hw * c),
        (x - hl * c + hw * s, y - hl * s - hw * c),
        (x - hl * c - hw * s, y - hl * s + hw * c),
    ]


def _rect_rect_gap(c1, c2) -> float:
    """两旋转矩形（角点列表）的间隙。

    SAT（矩形边法线 4 轴）判相交：相交返回 −最小重叠深度（穿透近似）；
    分离时取 4×4 边对真距离——45°/135° 旋转件的准确值，外接框口径会把
    纯侧向 0.6mm 间隙冤判成 −0.7mm 相交（金样可调电源/地正星两例）。
    """
    axes = []
    for corners in (c1, c2):
        for i in range(2):
            (ax, ay), (bx, by) = corners[i], corners[i + 1]
            ex, ey = bx - ax, by - ay
            n = math.hypot(ex, ey) or 1.0
            axes.append((-ey / n, ex / n))
    overlaps = []
    for ux, uy in axes:
        p1 = [x * ux + y * uy for x, y in c1]
        p2 = [x * ux + y * uy for x, y in c2]
        o = min(max(p1), max(p2)) - max(min(p1), min(p2))
        if o <= 0.0:
            return _rect_edge_dist(c1, c2)   # 分离：边对真距离（精确）
        overlaps.append(o)
    return -min(overlaps)


def _rect_edge_dist(c1, c2) -> float:
    best = float("inf")
    for i in range(4):
        a, b = c1[i], c1[(i + 1) % 4]
        for j in range(4):
            e, f = c2[j], c2[(j + 1) % 4]
            d = _seg_seg_dist(a, b, e, f)
            if d < best:
                best = d
    return best


# ── 晶振识别（批4 2026-10-10 审计残留）──
# 口径与 bom_rules._check_crystal_load_caps 的三证据标准一致（本处私有实现，
# 待后续批次抽公共模块，避免两处漂移）：
# ① 位号 X/Y 前缀是主信号但不是充分条件（X 下有 WAFER 连接器、pn=00 杂行）；
# ② 频率证据走料号/容值字段；描述里的频率必须与 ppm 特征同现才算——
#    磁珠「60Ω@100MHz」、DC-DC「1.5MHz 同步降压」都不是晶振；
# ③ 标注「内置/集成」的是片内振荡源（RTC/模组），不认。
_CRYSTAL_FREQ_RE = re.compile(
    r"\d+(?:\.\d+)?\s*[MK]HZ(?![A-Z0-9])|\d+(?:\.\d+)?M(?=[\s/])", re.IGNORECASE)
_CRYSTAL_TIGHT_KW = ("晶振", "crystal", "谐振器")


def _identify_crystal_refs(bom_items) -> list:
    """识别晶振 BOM 行 → [(item, 首位号), ...]（三证据口径，同 bom_rules）。"""
    out = []
    for item in bom_items:
        ref = getattr(item, "reference", "").split(",")[0].strip()
        pfx = "".join(c for c in ref if c.isalpha()).upper()
        pn = getattr(item, "part_number", "") or ""
        desc = getattr(item, "description", "") or ""
        val = getattr(item, "value", "") or ""
        text = f"{pn} {desc}".lower()
        tight = any(kw in text for kw in _CRYSTAL_TIGHT_KW)
        if not tight and pfx not in ("X", "Y"):
            continue
        # 证据：晶振词；或频率在料号/容值；或描述里「频率 + ppm」同现
        freq_field = bool(_CRYSTAL_FREQ_RE.search(pn) or _CRYSTAL_FREQ_RE.search(val))
        freq_desc = bool(_CRYSTAL_FREQ_RE.search(desc)) and bool(
            re.search(r"PPM", desc, re.IGNORECASE))
        if not (tight or freq_field or freq_desc):
            continue  # X 前缀连接器 / pn=00 杂行：认不出是晶振，诚实跳过
        if any(k in text for k in ("内置", "集成", "internal")) and pfx not in ("X", "Y"):
            continue  # 片内振荡源（RTC/模组），底板无需外部晶振布局约束
        out.append((item, ref))
    return out


# ── 模数件识别通道（批4 2026-10-10 审计残留）──
# 旧判据只搜 description 关键词表（PCB.ANALOG/DIGITAL_COMPONENT_KW），真实
# BOM desc 多为空或参数文本，模数件识别大面积失效。改三通道：
# ① ML 细类 ic_analog（运放/比较器/ADC/DAC/接口IC）/ ic_mcu（MCU/FPGA/CPLD）；
# ② 料号前缀（ADC/DAC/运放族 → 模拟；MCU/逻辑族 → 数字）；
# ③ desc 关键词表仅作回退（_kw_hit 词边界，短词 AD/OP/TL 不再内嵌命中
#    PicoBlade/inmp441 之类）。位号 U/A 前缀只是「这是一颗 IC」的信号、
#    不是模数归属的充分条件，不单独参与判定。
_AD_ANALOG_PN_RE = re.compile(
    r"^(?:ADC|DAC|ADS|ADA|AD[0-9]|OPA|OP[0-9]{2}|NE5532|RC4558|"
    r"LM(?:358|324|393|V358|V324|2904)|TL(?:07|08|431|9\d{2})|GS86|SGM8)",
    re.IGNORECASE)
_AD_DIGITAL_PN_RE = re.compile(
    r"^(?:STM32|ESP32|CH32|CH55|CH9\d|GD32|ATMEGA|ATTINY|NRF\d|SN74|74HC|74LS|"
    r"74HCT|HT6\d|PY32|SC8\d|W25Q|GD25|FPGA|ECP\d|ICE40|MAX3232)",
    re.IGNORECASE)


def _classify_ad_zone(item) -> str:
    """模/数分区归属：'analog' | 'digital' | ''（识别不出）。

    电源变换器（DC-DC/LDO，_is_dcdc_part / ic_power）不属模数信号分区
    任何一方，返回 ''。
    """
    fine, _conf = _classify_component_fine(item)
    if fine == "ic_analog":
        return "analog"
    if fine == "ic_mcu":
        return "digital"
    if _is_dcdc_part(item) or fine == "ic_power":
        return ""
    pn = (getattr(item, "part_number", "") or "").strip()
    desc = f"{pn} {getattr(item, 'description', '') or ''}".lower()
    if pn and _AD_ANALOG_PN_RE.match(pn):
        return "analog"
    if pn and _AD_DIGITAL_PN_RE.match(pn):
        return "digital"
    if _kw_hit(desc, PCB.ANALOG_COMPONENT_KW):
        return "analog"
    if _kw_hit(desc, PCB.DIGITAL_COMPONENT_KW):
        return "digital"
    return ""


# ── 温度敏感/热源识别通道（批4 2026-10-10 审计残留）──
# 敏感件：NTC/温度传感器料号族、晶振（_identify_crystal_refs 三证据口径）、
# 电解电容（ML 细类 cap_elec，或容值 ≥100µF——MLCC 极少做到该量级）。
# 热源：_is_dcdc_part（统一 DC-DC 口径）、LDO/功率器件料号族 + 明确描述词。
_TEMP_SENSOR_PN_RE = re.compile(
    r"^(?:NTC|PTC|DS18B\d?|LM35|LM75|TMP\d|SHT\d|DHT\d|PT1000?|MLX90|STTS|"
    r"TS\d|LMT)", re.IGNORECASE)
_HEAT_PN_RE = re.compile(
    r"^(?:AMS1|LM1117|XC6\d|ME62|ME63|HT7\d|RT90|AP21|AP7\d|MIC52|SPX38|"
    r"LD11|L78\d|L79\d|78M\d|78L\d|CJ63\d|AOD\d|AO[3489]\d|IRF\d|IRL\d|"
    r"IPB\d|IPD\d|BUK\d|NDT\d|NCE\d|SI44\d|SI7\d|HY[23]\d|2N[56]\d|TIP[12])",
    re.IGNORECASE)
_TEMP_SENSITIVE_DESC_KW = ("ntc", "ptc", "温度传感", "热敏", "电解电容", "electrolytic")
_HEAT_DESC_KW = ("ldo", "mosfet", "稳压", "功率")
# 电解电容的容值下限（F）：≥100µF 判温度敏感（MLCC 主流量级 ≤22µF）
_ELECTROLYTIC_MIN_F = 100e-6

# ── EMI 滤波器件/接口识别通道（批4 2026-10-10 审计残留）──
# 旧判据 EMI 器件与「电源入口」都靠 desc 关键词子串（filter/EMI/PWR…），
# 真实 BOM 上双向失效。EMI 器件改料号+value 通道：
# ① 磁珠料号特征 BLM/MPZ/CBM（村田/TDK/三莹族，token 边界）+ 共模扼流圈
#    族 DLW/ACM/SDM/ACT45/CMxx——加分项；
# ② value 里的「Ω@MHz」阻抗-频率标注（磁珠专属形态，金样磁珠行 value
#    常是「600Ω@100MHz」式参数）；
# ③ desc 明确词（共模/磁珠/choke/ferrite/bead/EMI）作回退。
# 接口走位号通道：J/CN/USB/FPC 前缀（连接器/接口座）。
_EMI_PN_RE = re.compile(
    r"(?i)(?<![a-z0-9])(?:BLM\d|BLM[+-]|MPZ|CBM|DLW|ACM|SDM|ACT45|CM\d{2,}|EMI)"
    r"(?![a-z0-9])")
_EMI_BEAD_VALUE_RE = re.compile(r"(?i)Ω\s*@|@\s*\d+(?:\.\d+)?\s*[MK]?HZ")
_EMI_DESC_KW = ("共模", "磁珠", "choke", "ferrite", "bead", "emi")
_EMI_IF_REF_PREFIXES = {"J", "CN", "USB", "FPC"}

class LayoutRulesMixin:
    """方法集由 facade DesignRuleChecker 组合；此处无状态、无 __init__。"""


    # ═══ Position-data rules ═══

    def _check_analog_digital_separation(self, bom_items, positions, netlist):
        """模数分离：模拟/数字元件应物理分区

        批4 2026-10-10 审计残留：识别通道重写——旧判据只搜 description
        关键词表（真实 BOM desc 多为空/参数文本，模数件识别大面积失效），
        改走 _classify_ad_zone 三通道（ML 细类 ic_analog/ic_mcu + 料号
        前缀 + desc 词边界回退）。识别不出两类都存在 → 跳过不报模板；
        无 positions 跳过（无坐标无距离可言）。距离判定与阈值
        （PCB.AD_SEPARATION_MIN_MM）不变。
        """
        # positions 参数为空时回落 pcb_data.component_positions（同晶振布局检查）
        positions = positions or (getattr(self._pcb_data, "component_positions", None) or {})
        if not positions or not bom_items: return []
        violations = []
        acoords, dcoords = [], []
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if not ref or ref not in positions:
                continue
            zone = _classify_ad_zone(item)
            if zone == "analog":
                x, y = _xy(positions[ref])
                acoords.append((x, y, ref))
            elif zone == "digital":
                x, y = _xy(positions[ref])
                dcoords.append((x, y, ref))
        if not acoords or not dcoords: return violations
        min_sep = PCB.AD_SEPARATION_MIN_MM
        cross = []
        for ax, ay, ar in acoords:
            for dx, dy, dr in dcoords:
                dist = ((ax - dx) ** 2 + (ay - dy) ** 2) ** 0.5
                if dist < min_sep:
                    cross.append((ar, dr, round(dist, 2)))
        if cross:
            pairs = ", ".join(f"{a}/{d}" for a, d, _ in cross[:5])
            more = f" ...等 {len(cross)} 对" if len(cross) > 5 else ""
            def _c(cs): return (sum(c[0] for c in cs)/len(cs), sum(c[1] for c in cs)/len(cs))
            acx, acy = _c(acoords); dcx, dcy = _c(dcoords)
            cd = ((acx - dcx) ** 2 + (acy - dcy) ** 2) ** 0.5
            violations.append(RuleViolation(
                rule_name="模数分离检查", description=f"发现 {len(cross)} 对模拟-数字元件间距<{min_sep}mm{more}",
                severity=RuleSeverity.WARNING, location=pairs,
                suggestion=f"模数区中心距 {cd:.1f}mm。分区布局+独立地铺铜+单点连接(0Ω/磁珠)。",
                theory="数字电路高频开关产生丰富谐波噪声，通过地平面耦合到模拟区→ADC 精度↓、运放纹波↑。模拟数字地应在 ADC 下方单点连接(0Ω/磁珠)，避免数字回路电流流经模拟地。"))
        return violations


    # 功能上必须贴板边的器件（批5 2026-10-10，金样 45 条里三成以上是这类）：
    # 连接器/排针要插拔、FPC 要翻出、按键要按压、声学件要开孔、天线馈点/
    # 测试点本来就设计在边缘。3.0mm 装配余量判据只约束「不必贴边」的器件。
    _EDGE_FUNCTION_PREFIXES = ("J", "P", "CN", "CON", "USB", "HDMI", "RJ", "DC",
                               "BT", "BAT", "FPC", "H", "TP", "SW", "M", "MIC", "SPK",
                               "BUZ", "RF", "ANT")

    def _check_component_edge_clearance(self, bom_items, positions, netlist):
        """板边间距：元件距 PCB 板边应 ≥3mm（按板框包围盒算真实边距）

        2026-10-09 修正：旧判据拿绝对坐标比 `x<3 or y<3`，不减板框原点——
        原点偏移的板上恒不响，原点在 0 附近的板只判了左/下两条边。
        板框退回「铜包围盒」(source=copper) 时边距恒为 0、无判定意义，
        直接跳过（与走线板边规则同一守卫）。
        批5（2026-10-10）：功能贴边件豁免（_EDGE_FUNCTION_PREFIXES）——
        金样探底 45 条警告里 H 排针/J 连接器/FPC/MIC/TP/RF 占比过半，
        这些贴边是设计意图不是装配风险；位号按逗号拆分逐个判（旧行为
        整串查 positions，多位号行恒漏）。LED 不豁免（贴边常是灯导但也
        常是随手放，保留提示由人判）。
        """
        if not positions: return []
        pcb = self._pcb_data
        bo = (pcb.board_outline or {}) if pcb else {}
        if bo.get("source") != "outline":
            return []
        mc = PCB.LAYOUT_BOARD_EDGE_CLEARANCE_MM
        minx, miny = bo["min_x_mm"], bo["min_y_mm"]
        maxx, maxy = bo["max_x_mm"], bo["max_y_mm"]
        near, exempt = [], 0
        for item in bom_items:
            for ref in (getattr(item, "reference", "") or "").split(","):
                ref = ref.strip()
                if not ref or ref not in positions:
                    continue
                pfx = "".join(c for c in ref if c.isalpha()).upper()
                if not pfx:
                    continue  # 纯数字"位号"（25/50/75）是 BOM 脏数据，不是元件
                if pfx.startswith(self._EDGE_FUNCTION_PREFIXES):
                    x, y = _xy(positions[ref])
                    if min(x - minx, maxx - x, y - miny, maxy - y) < mc:
                        exempt += 1
                    continue
                x, y = _xy(positions[ref])
                if min(x - minx, maxx - x, y - miny, maxy - y) < mc: near.append(ref)
        if near:
            note = f"（另有 {exempt} 个连接器/排针/测试点等功能贴边件已豁免）" if exempt else ""
            return [RuleViolation(
                rule_name="板边间距检查", description=f"{len(near)} 个元件距板边 <{mc}mm: {', '.join(near[:5])}{note}",
                severity=RuleSeverity.WARNING,
                suggestion=f"元件距板边 ≥{int(mc)}mm，高元件需更大间距",
                theory="PCB 板边在拼板分离、波峰焊夹持、机壳装配中承受最大机械应力。IPC-2222 §8.2 建议元件体距板边 ≥2.5mm，高元件≥5mm。传送边禁布区≥3mm。")]
        return []


    def _check_decoupling_proximity(self, bom_items, positions, netlist):
        """去耦电容距离：去耦电容应靠近 IC 电源引脚"""
        if not positions: return []
        violations = []
        # 2026-09-24 抽查修正：原判据把「除电阻/电感外的所有元件」都当 IC——
        # 咪头、蜂鸣器、电池座、螺丝孔全成了 IC，报出的「N 个去耦电容」其实是配对数。
        # 现在用统一的元件分类（位号前缀 + 封装 + value + ML 模型）。
        ics, caps = [], []
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if ref not in positions:
                continue
            kind = _classify_component(item)
            if kind == "cap":
                caps.append((ref, positions[ref]))
            elif kind == "ic":
                ics.append((ref, positions[ref]))
        if not ics: return violations
        md = PCB.LAYOUT_DECOUPLE_MAX_DIST_MM
        far = []
        for cr, cp in caps:
            cx, cy = _xy(cp)
            nearest = None      # (距离, IC 位号)：按「到最近 IC」判定
            for ir, ip in ics:
                ix, iy = _xy(ip)
                dist = ((cx - ix) ** 2 + (cy - iy) ** 2) ** 0.5
                if nearest is None or dist < nearest[0]:
                    nearest = (dist, ir)
            # 2026-09-24 抽查修正：原来「任一 IC 距该电容 >md」就算——板上总有远端 IC，
            # 于是 73/76 块板都响。现在只看它到**最近** IC 的距离。
            if nearest is not None and nearest[0] > md:
                far.append((cr, nearest[1], round(nearest[0], 1)))
        if far:
            ps = ", ".join(f"{c}/{i}({d}mm)" for c, i, d in far[:3])
            violations.append(RuleViolation(
                rule_name="去耦电容距离检查",
                description=(f"{len({c for c, _, _ in far})} 个去耦电容距 IC >{md}mm"
                             f"（{len(far)} 对电容-IC 组合）: {ps}"),
                severity=RuleSeverity.WARNING,
                suggestion=f"去耦电容距 IC 电源引脚 ≤{int(md)}mm。距离每增加 1cm，退耦效果显著下降。",
                theory="PCB 走线寄生电感≈5~10nH/cm。去耦电容距 IC 每增 1cm，环路 L≈+8nH——10ns 内切换 50mA 时 Vdrop=L·di/dt=8nH×5×10⁶A/s=40mV。多层板建议电容同层距引脚≤10mm。"))
        return violations


    def _check_crystal_proximity(self, bom_items, positions, netlist):
        """晶振靠近 MCU：晶振应尽可能靠近 MCU 振荡器引脚

        批4 2026-10-10 审计残留：晶振识别原来只认 desc 词（真实立创 BOM
        description 常为空或只有容值/参数），规则在多数板上恒静默。改用
        _identify_crystal_refs（与 bom_rules._check_crystal_load_caps 三证据
        口径一致：X/Y 位号是信号不是充分条件、频率证据走料号/容值字段、
        描述频率须与 ppm 同现、内置/集成的片内振荡源不认）。识别不出晶振
        或 MCU → 跳过。距离阈值 25mm 保持；netlist 可用时顺带找出晶振关联
        的负载电容（同网络 1-47pF 小电容），距离过远时在描述中一并提示。
        """
        # positions 参数为空时回落 pcb_data.component_positions（.epro2 解析
        # 可重建坐标，产品里只加载 PCB 文件时 Pick&Place CSV 常缺席）
        positions = positions or (getattr(self._pcb_data, "component_positions", None) or {})
        if not positions: return []
        violations = []
        crystals = _identify_crystal_refs(bom_items)
        if not crystals:
            return violations
        # MCU 识别：ML 细类 ic_mcu 优先，料号/描述关键词（词边界）回退
        mcu_kw = ("MCU", "STM32", "ESP32", "ATMEGA", "ARM", "单片机", "CPU",
                  "CH32", "GD32", "NRF")
        crystal_ref_set = {ref for _item, ref in crystals}
        crystal_positions = []
        mcu_positions = []
        for item, ref in crystals:
            if ref in positions:
                x, y = _xy(positions[ref])
                crystal_positions.append((ref, x, y))
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if not ref or ref in crystal_ref_set or ref not in positions:
                continue
            text = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            fine, _conf = _classify_component_fine(item)
            if fine == "ic_mcu" or _kw_hit(text, mcu_kw):
                x, y = _xy(positions[ref])
                mcu_positions.append((ref, x, y))
        if not crystal_positions or not mcu_positions:
            return violations
        # 负载电容关联（best-effort，需 netlist）：晶振引脚所在网络上的
        # 1-47pF 小电容即皮尔斯电路的 CL1/CL2
        small_caps: set = set()
        for item in bom_items:
            if _classify_component(item) != "cap":
                continue
            cf = _parse_capacitance(getattr(item, "value", ""))
            if cf is not None and 1e-12 <= cf <= 47e-12:
                small_caps.update(item.reference_list)
        assoc_cap_refs: set = set()
        if netlist and small_caps:
            for _nname, pins in netlist.items():
                pin_refs = {str(p).split(".")[0]
                            for p in (pins if isinstance(pins, (list, tuple, set))
                                      else getattr(pins, "pins", None) or ())}
                if pin_refs & crystal_ref_set:
                    assoc_cap_refs |= (pin_refs & small_caps)
        cap_positions = [(r, _xy(positions[r])) for r in assoc_cap_refs
                         if r in positions]
        max_dist = PCB.LAYOUT_CRYSTAL_MCU_MAX_DIST_MM
        for cr, cx, cy in crystal_positions:
            closest = min(((cx - mx) ** 2 + (cy - my) ** 2) ** 0.5
                          for _, mx, my in mcu_positions)
            if closest <= max_dist:
                continue
            cap_note = ""
            if cap_positions:
                cdist = min(((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                            for _, (px, py) in cap_positions)
                if cdist > max_dist:
                    cap_note = f"；最近的负载电容也距 {cdist:.0f}mm"
            violations.append(RuleViolation(
                rule_name="晶振布局检查",
                description=f"晶振 {cr} 距 MCU {closest:.0f}mm(建议≤{int(max_dist)}mm){cap_note}",
                severity=RuleSeverity.WARNING, location=cr,
                suggestion="晶振紧靠 MCU OSC_IN/OSC_OUT 引脚，走线短而直，底部铺 GND 铜皮。晶振下方不走其他信号线。",
                theory="晶振到 MCU 的走线每 1cm 引入约 8nH 寄生电感和 2~5pF 寄生电容→频率偏移和起振困难。皮尔斯振荡器依赖走线电容作为负载的一部分，走线过长破坏 CL 匹配。",
            ))
        return violations


    # 安装孔痕迹（批4 2026-10-10 审计残留）：真实安装孔通常没有 BOM 行，
    # 从 pcb_data.component_positions 的封装名/位号找。token 边界允许数字
    # 后缀（HR3.2 / HOLE3.0 / MTG-3.2），拒绝内嵌（HOLES 之类）。
    _MOUNT_HOLE_FP_RE = re.compile(
        r"(?i)(?<![a-z0-9])(?:HR|HOLE|MTG)\d*(?![a-z])|安装孔|螺丝孔|定位孔")

    def _check_mounting_hole_keepout(self, bom_items, positions, netlist):
        """安装孔禁区：安装孔周围应有禁布区

        批4 2026-10-10 审计残留：旧实现从 BOM 行 desc 搜 HOLE/MTG——真实
        安装孔通常没有 BOM 行，识别通道整体失效。改从 pcb_data.
        component_positions 找：封装名含 HR/HOLE/安装孔/MTG（token 边界）
        或位号 H 前缀的条目；找到后与元件位置做禁区判定（阈值 3.0mm 保持，
        pcb 坐标与传入 positions 合并、pcb 侧优先）。没有安装孔数据 → 跳过。
        """
        violations = []
        pcb = self._pcb_data
        comp_pos = (getattr(pcb, "component_positions", None) or {}) if pcb else {}
        all_pos = dict(positions or {})
        all_pos.update(comp_pos)      # pcb 数据更权威，覆盖同名位号
        if not all_pos:
            return violations
        hole_refs = set()
        for ref, pos in all_pos.items():
            pfx = "".join(c for c in str(ref) if c.isalpha()).upper()
            fp = ""
            if isinstance(pos, dict):
                fp = str(pos.get("footprint_name") or pos.get("footprint") or "")
            if pfx == "H" or (fp and self._MOUNT_HOLE_FP_RE.search(fp)):
                hole_refs.add(ref)
        if not hole_refs:
            return violations
        keepout_r = PCB.LAYOUT_MOUNT_HOLE_KEEPOUT_MM
        near_holes = []
        for hole_ref in sorted(hole_refs):
            hx, hy = _xy(all_pos[hole_ref])
            for ref in all_pos:
                if ref in hole_refs:
                    continue
                x, y = _xy(all_pos[ref])
                dist = math.hypot(hx - x, hy - y)
                if dist < keepout_r:
                    near_holes.append(ref)
        if near_holes:
            violations.append(RuleViolation(
                rule_name="安装孔禁区检查",
                description=f"{len(near_holes)} 个元件距安装孔 <{int(keepout_r)}mm: {', '.join(near_holes[:5])}",
                severity=RuleSeverity.WARNING, location=", ".join(near_holes[:5]),
                suggestion=f"安装孔周围 ≥{int(keepout_r)}mm 禁止放置元件和走线。螺丝头/垫片可能压伤元件。",
                theory="螺丝安装时垫片/螺丝头直径通常比孔径大 3~5mm(如 M3 螺丝垫片≈7mm)。禁布区防止装配时机械损伤元件和焊点。IPC-2221 推荐禁布区≥孔径+2mm。",
            ))
        return violations


    def _check_temp_sensitive_placement(self, bom_items, positions, netlist):
        """温度敏感元件：温度敏感元件应远离热源

        批4 2026-10-10 审计残留：旧判据敏感/热源全靠 desc 关键词子串
        （ADC/基准/传感器 vs LDO/DC-DC/电源），真实 BOM 上双向失效。改：
        敏感件 = NTC/温度传感器料号族、晶振（三证据口径）、电解电容
        （ML cap_elec 细类或容值 ≥100µF）；热源 = _is_dcdc_part、
        LDO/功率器件料号族 + 明确描述词回退。任一侧识别不出或无
        positions → 跳过；>2 对近距离（<10mm）才报（阈值保持）。
        """
        violations = []
        if not positions:
            return violations
        crystal_refs = {ref for _item, ref in _identify_crystal_refs(bom_items)}
        temp_sensitive = []
        heat_sources = []
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if not ref:
                continue
            pn = (getattr(item, "part_number", "") or "").strip()
            val = (getattr(item, "value", "") or "")
            desc = f"{pn} {getattr(item, 'description', '') or ''}".lower()
            fine, _conf = _classify_component_fine(item)
            is_sensitive = (
                ref in crystal_refs
                or (pn and _TEMP_SENSOR_PN_RE.match(pn))
                or fine == "cap_elec"
                or (_classify_component(item) == "cap"
                    and (cf := _parse_capacitance(val)) is not None
                    and cf >= _ELECTROLYTIC_MIN_F)
                or _kw_hit(desc, _TEMP_SENSITIVE_DESC_KW)
            )
            is_heat = (
                _is_dcdc_part(item)
                or fine == "ic_power"
                or (pn and _HEAT_PN_RE.match(pn))
                or _kw_hit(desc, _HEAT_DESC_KW)
            )
            if is_sensitive:
                temp_sensitive.append(ref)
            if is_heat:
                heat_sources.append(ref)
        if not temp_sensitive or not heat_sources:
            return violations
        warnings = 0
        min_distance = PCB.LAYOUT_TEMP_HEAT_MIN_DIST_MM
        for tr in temp_sensitive:
            if tr not in positions: continue
            tx, ty = _xy(positions[tr])
            for hr in heat_sources:
                if hr == tr or hr not in positions: continue
                hx, hy = _xy(positions[hr])
                dist = math.hypot(tx - hx, ty - hy)
                if dist < min_distance:
                    warnings += 1
        if warnings > 2:
            violations.append(RuleViolation(
                rule_name="温度敏感元件布局检查",
                description=f"{warnings} 对温度敏感元件与热源间距 <{int(min_distance)}mm",
                severity=RuleSeverity.WARNING,
                suggestion=f"晶振/NTC/温度传感器/电解电容距离热源 ≥{int(min_distance)}mm。使用热仿真或红外热像仪验证。",
                theory="晶振频率漂移 Δf/f≈α×ΔT(α≈-0.03ppm/°C²),温升 20°C→频率漂移可达 12ppm。电解电容在 85°C 以上工作时寿命指数衰减(105°C 品在 95°C 工作寿命减半)。",
            ))
        return violations


    def _check_emi_filter_proximity(self, bom_items, positions, netlist):
        """EMI 滤波器靠近入口：EMI 滤波器件应紧靠电源入口

        批4 2026-10-10 审计残留：识别通道重写——EMI 器件走料号+value
        （磁珠/共模扼流圈料号族 BLM/MPZ/CBM…、「Ω@MHz」value 标注、
        明确 desc 词回退），接口走位号（J/CN/USB/FPC 前缀）。识别不出
        任一侧或无 positions → 跳过。30mm 阈值保持（收编文件内具名
        常量，不改值）。
        """
        violations = []
        if not positions:
            return violations
        # EMI 滤波器件距接口连接器的最大距离（批5 收编常量，值不变）
        _EMI_IF_MAX_DIST_MM = PCB.LAYOUT_EMI_IF_MAX_DIST_MM
        emi_refs, if_refs = [], []
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if not ref:
                continue
            pn = (getattr(item, "part_number", "") or "").strip()
            val = str(getattr(item, "value", "") or "")
            desc = f"{pn} {getattr(item, 'description', '') or ''}".lower()
            if ((pn and _EMI_PN_RE.search(pn))
                    or _kw_hit(desc, _EMI_DESC_KW)
                    or _EMI_BEAD_VALUE_RE.search(val)):
                emi_refs.append(ref)
                continue
            pfx = "".join(c for c in ref if c.isalpha()).upper()
            if pfx in _EMI_IF_REF_PREFIXES:
                if_refs.append(ref)
        if not emi_refs or not if_refs:
            return violations
        far_pairs = []
        for er in emi_refs:
            if er not in positions: continue
            ex, ey = _xy(positions[er])
            for cr in if_refs:
                if cr not in positions: continue
                cx, cy = _xy(positions[cr])
                dist = math.hypot(ex - cx, ey - cy)
                if dist > _EMI_IF_MAX_DIST_MM:
                    far_pairs.append(f"{er}/{cr}({dist:.0f}mm)")
        if far_pairs:
            violations.append(RuleViolation(
                rule_name="EMI 滤波器布局检查",
                description=(f"EMI 滤波器件距接口连接器 >{int(_EMI_IF_MAX_DIST_MM)}mm: "
                             f"{', '.join(far_pairs[:3])}"),
                severity=RuleSeverity.WARNING,
                suggestion=(f"EMI 滤波器件紧靠接口/电源连接器"
                            f"(≤{int(_EMI_IF_MAX_DIST_MM)}mm)。滤波前后分区敷铜,"
                            "避免噪声耦合绕过滤波器。"),
                theory="EMI 滤波器的作用是将噪声电流旁路回源端。滤波器距入口越远,入口到滤波器间的走线越长→走线辐射的噪声绕过滤波器直接耦合到电源线,滤波器效果大幅降低。",
            ))
        return violations


    def _check_connector_edge_placement(self, bom_items, positions, netlist):
        """连接器边沿布局：连接器/接口应置于 PCB 边沿（按板框包围盒算真实边距）

        2026-10-09 修正：旧判据 `x>10 and y>10` 拿绝对坐标当边距，不减板框
        原点——原点偏移的板上连接器全被误判「距板边较远」。板框无真实轮廓
        (source != outline) 时无法算边距，跳过。
        """
        if not positions: return []
        pcb = self._pcb_data
        bo = (pcb.board_outline or {}) if pcb else {}
        if bo.get("source") != "outline":
            return []
        violations = []
        conn_kw = ["USB", "RJ45", "HDMI", "DB9", "排针", "端子", "CONNECTOR", "HEADER", "JACK",
                   "DC", "电源插座", "SD卡", "TF卡", "SIM卡", "FPC", "FFC"]
        max_board_edge = PCB.LAYOUT_CONN_BOARD_EDGE_MM
        minx, miny = bo["min_x_mm"], bo["min_y_mm"]
        maxx, maxy = bo["max_x_mm"], bo["max_y_mm"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.lower() in desc for kw in conn_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if ref not in positions:
                continue
            x, y = _xy(positions[ref])
            clearance = min(x - minx, maxx - x, y - miny, maxy - y)
            if clearance > max_board_edge:
                violations.append(RuleViolation(
                    rule_name="连接器边沿布局检查",
                    description=f"连接器 {ref} 距最近板边 {clearance:.0f}mm（>{int(max_board_edge)}mm），可能影响插拔操作",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion="连接器/接口紧贴 PCB 边沿，开口朝外。机壳开孔位置与连接器对准，预留插头空间(如 USB 插头长度 ≈15mm)。",
                    theory="连接器置于板中心→机壳内部需延长开孔通道,增加机械设计难度且插拔力会使 PCB 弯曲。板边布局插拔力直接由机壳/固定柱承受。",
                ))
        return violations


    def _check_component_spacing(self, bom_items, positions, netlist):
        """元件间距：spatial hash 全对检索 + 封装体尺寸真间隙。

        2026-10-10 几何批重写。旧实现只比 positions 字典里索引相邻的 4 项
        （真实 <1mm 的对只抓到一半），中心距 1.0mm 一刀切（不分封装体大小），
        也不分正反面（正反面元件同 XY 互不算间距）。现在：
        ① 网格 3×3 邻域全对检索（5mm 网格覆盖所有相关对）；
        ② 体尺寸两路解析（封装名内嵌 _L..-W.. / 片式封装码表），旋转取
          外接框，间隙 = 中心距 − 两体外接框半宽/半高（分离轴取大者）；
        ② 体尺寸两路解析（封装名内嵌 _L..-W.. / 片式封装码表），间隙按
          **旋转矩形精确距离**（SAT 判相交 + 边对真距离；外接框口径会把
          45° 旋转件的侧向间隙冤判成相交）；
        ③ 正反面（side 已知且不同）不配对；无体的（Mark/定位孔/测试点/
          安装孔）与体尺寸落空的（连接器/异形封装）不参与；
        ④ 「站立件」不配对——通孔大件（体长 ≥8mm 且有通孔焊盘，如插针
          OLED 模块、DIP 载板）是架在板上的，封装矩形罩住的板面仍可放
          件，按矩形算会冤枉其正下方的 0603（金样判读：智能秤 OLED、
          星光4N A4988 载板两例）；
        ⑤ 焊盘佐证门——封装名内嵌尺寸常含引脚（TDSON-8_L5.9 实体
          ~5mm、CAP-TH_L4.2 含引脚），体「相交」而焊盘中心距仍有
          ≥1.5mm 的对是尺寸口径噪声，跳过（金样判读 3 例）；焊盘
          贴邻（<1.5mm）或无焊盘数据的（纯 positions 调用）按体判据报。
        间隙 <0.2mm 聚合一条：有被焊盘佐证的体相交（<0）报 WARNING，
        否则 INFO。
        """
        if not positions:
            return []
        pcb = getattr(self, "_pcb_data", None)
        thru_refs = {p.get("ref") for p in (getattr(pcb, "pads", None) or [])
                     if p.get("thru")}
        pad_pts: dict[str, list[tuple[float, float]]] = {}
        for p in (getattr(pcb, "pads", None) or []):
            pad_pts.setdefault(p.get("ref"), []).append((p["x"], p["y"]))
        bodies = {}          # ref → (x, y, L, W, side, standing)
        for ref, pos in positions.items():
            if not isinstance(pos, dict):
                continue
            dims = _body_dims(pos)
            if dims is None:
                continue
            x, y = _xy(pos)
            bodies[ref] = (float(x), float(y), dims[0], dims[1],
                           str(pos.get("side") or ""),
                           dims[0] >= 8.0 and ref in thru_refs)
        if len(bodies) < 2:
            return []
        cell = 5.0
        grid: dict[tuple[int, int], list[str]] = {}
        for ref, (x, y, _, _, _, _) in bodies.items():
            grid.setdefault((int(math.floor(x / cell)),
                             int(math.floor(y / cell))), []).append(ref)
        pairs = []           # (gap, ref1, ref2)
        for ref, (x1, y1, l1, w1, s1, st1) in bodies.items():
            if st1:
                continue
            cx, cy = int(math.floor(x1 / cell)), int(math.floor(y1 / cell))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for ref2 in grid.get((cx + dx, cy + dy), ()):
                        if ref2 <= ref:
                            continue
                        x2, y2, l2, w2, s2, st2 = bodies[ref2]
                        if st2:
                            continue
                        if s1 and s2 and s1 != s2:
                            continue          # 正反面不互算间距
                        # 外接圆预筛（半径 0.5·对角线，比任何间隙判据都宽松）
                        if math.hypot(x1 - x2, y1 - y2) > (
                                0.5 * math.hypot(l1, w1)
                                + 0.5 * math.hypot(l2, w2)
                                + _COMPONENT_GAP_MIN_MM):
                            continue
                        gap = _rect_rect_gap(
                            _rect_corners_mm(x1, y1, l1, w1, float(positions[ref].get("rotation") or 0.0)),
                            _rect_corners_mm(x2, y2, l2, w2, float(positions[ref2].get("rotation") or 0.0)))
                        if gap >= _COMPONENT_GAP_MIN_MM:
                            continue
                        # 焊盘佐证门（见 docstring ⑤）
                        pa, pb = pad_pts.get(ref) or [], pad_pts.get(ref2) or []
                        pad_gap = min(
                            (math.hypot(ax - bx, ay - by) for ax, ay in pa
                             for bx, by in pb), default=None)
                        if pad_gap is not None and pad_gap >= _PAD_CORROB_MAX_MM:
                            continue
                        pairs.append((gap, ref, ref2, pad_gap))
        if not pairs:
            return []
        pairs.sort()
        overlap = any(g < 0.0 and (pg is None or pg < _PAD_CORROB_MAX_MM)
                      for g, _, _, pg in pairs)
        worst = ", ".join(f"{a}-{b}({g:.2f}mm)" for g, a, b, _ in pairs[:5])
        return [RuleViolation(
            rule_name="元件间距检查",
            description=(
                f"{len(pairs)} 对元件体间隙 <{_COMPONENT_GAP_MIN_MM}mm"
                f"（{'含相交' if overlap else '最紧 ' + pairs[0][1] + '-' + pairs[0][2] + f' {pairs[0][0]:.2f}mm'}）: {worst}"
            ),
            severity=(RuleSeverity.WARNING if overlap else RuleSeverity.INFO),
            location=", ".join(b for _, a, b, _ in pairs[:3]),
            suggestion=(
                "间隙按封装体外接框估算（旋转角取外接框，未含引脚悬出），"
                "连接器/异形封装未参与。SMT 元件体间 ≥0.2mm 可贴片，"
                "≥0.5mm(0603)/≥0.8mm(0805) 才好返修；高元件间 ≥1.5mm。"
            ),
            theory=(
                "元件间距过小→SMT 钢网印刷桥连、回流焊阴影效应、烙铁无法伸入返修。"
                "IPC-7351 为每种封装定义了标准焊盘和间距。"
            ),
        )]


    def _check_fiducial_mark(self, bom_items, positions, netlist):
        """Mark点检查：批量生产PCB应有光学定位Mark点

        2026-10-09 噪声清扫：原实现 len(positions)>10 即报「未确认是否有 Mark」
        （78/78 板全响）。改为在 component_positions 的封装名/值/料号里找
        FIDUCIAL / MARK-POINT 类器件（金样 1/78 板有，footprint_name=
        'MARK-POINT'）：找到 → 静默；找不到 → 文案改为「未检测到」，可证伪。
        位号不参与匹配（M4 也可能是安装孔）。
        """
        if not positions or len(positions) <= 10:
            return []
        fiducial_kw = ("fiducial", "mark", "基准", "定位")
        for pos in positions.values():
            if not isinstance(pos, dict):
                continue
            blob = " ".join(
                str(pos.get(k) or "") for k in
                ("footprint_name", "footprint", "device", "value", "part_number")
            ).lower()
            if any(kw in blob for kw in fiducial_kw):
                return []
        return [RuleViolation(
            rule_name="光学定位点检查",
            description="未检测到光学定位(Mark)点器件，SMT 批量贴片前需确认",
            severity=RuleSeverity.INFO,
            suggestion="PCB 对角放置≥2个全局 Mark 点(Φ1.0mm 铜箔+Φ3.0mm 阻焊开窗)。细间距IC(QFP/BGA)局部加Mark点。",
            theory="SMT 贴片机通过识别 Mark 点校正 PCB 位置偏差。全局 Mark 用于整板定位，局部 Mark 用于精细间距元件定位。无 Mark 点→贴片精度不足→立碑/偏移。",
        )]

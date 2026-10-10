"""BOM 元件类规则 —— 从 checker.py 机械迁出（P1-6 阶段B，纯移动）。"""

import logging
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
    _any_ref_prefix,
    _classify_component,
    _classify_component_fine,
    _component_count,
    _component_model_attempted,
    _component_predictor,
    _extract_voltage_rating,
    _has_power_entry,
    _init_component_model,
    _is_cap_row,
    _is_dcdc_part,
    _is_inner_layer,
    _is_power_or_ground_net,
    _is_resistor_row,
    _kw_hit,
    _net_class,
    _net_kw_hit,
    _parallel_overlap_len,
    _parse_capacitance,
    _parse_component_value,
    _pt_seg_dist,
    _row_text,
    _seg_seg_dist,
    group_violations_by_component,
    rule_kind,
)

logger = logging.getLogger(__name__)


def _norm_fp(fp: str) -> str:
    """封装名归一：剥离单字母类别前缀（C0603/R0402/L3216 → 0603/0402/3216）。

    立创封装库用首字母区分类别（C=电容/R=电阻），同一物理封装在电容行和
    电阻行会分别记成 C0603/R0603，字符串直比会误报「多种封装」——金样
    150 条封装一致性里 55 条是这类前缀差异。
    """
    return re.sub(r"^[A-Za-z](?=\d{3})", "", fp.strip())


class BomRulesMixin:
    """方法集由 facade DesignRuleChecker 组合；此处无状态、无 __init__。"""


    # ═══ BOM-only rules ═══

    def _check_decoupling_caps(self, bom_items, positions, netlist):
        """去耦电容检查：每个 IC 应有匹配的去耦电容，基于 Z-F 分析。

        契合实际使用的设计（2026-08 重构）：
        1. 元件分类基于位号前缀 + 描述关键词，而非仅描述关键词。
           真实立创 BOM 的描述常只是值/型号（如 "100nF"、"4kHz"），旧逻辑
           会把电容/二极管/连接器/蜂鸣器误判为 IC，产生大量虚假违规。
        2. 去耦覆盖按"可用 100nF 总量 vs 需去耦 IC 数量"的供需关系判断，
           而非"全 BOM 有一个就满足全部 / 一个没有就全部报错"。
        3. 数量统计包含 quantity / 多位号数量，覆盖真实 BOM 的逗号分隔位号。
        """
        from src.pcb.calculator import analyze_decoupling_capacitor

        violations = []
        ics, caps = [], []
        for item in bom_items:
            cls = _classify_component(item)
            if cls == "cap":
                caps.append(item)
            elif cls == "ic":
                ics.append(item)

        # ── 统计可用去耦电容总量（含数量）──
        total_100nf = 0   # 50nF-500nF 高频去耦
        total_bulk = 0    # 1µF-100µF 体电容
        for c in caps:
            count = _component_count(c)
            cap_f = _parse_capacitance(getattr(c, "value", ""))
            if cap_f is None:
                continue
            if 50e-9 <= cap_f <= 500e-9:
                total_100nf += count
            elif 1e-6 <= cap_f <= 100e-6:
                total_bulk += count

        # IC 总数按位号统计（真实 BOM 常以逗号分隔多位号同行，如 "U1,U2,...,U29"）
        ic_count = sum(_component_count(i) for i in ics)
        if ic_count == 0:
            return violations

        # ── 高频去耦 100nF 覆盖 ──
        if total_100nf == 0:
            # 全板无任何高频去耦电容：逐 IC 报 ERROR（严重问题，便于定位）
            for ic in ics:
                ic_ref = getattr(ic, "reference", "?")
                result = analyze_decoupling_capacitor(100e-9, "0603", "typical")
                violations.append(RuleViolation(
                    rule_name="去耦电容检查",
                    description=f"IC {ic_ref} 缺少 100nF 高频去耦电容",
                    severity=RuleSeverity.ERROR,
                    location=ic_ref,
                    suggestion=(
                        f"在 {ic_ref} 电源引脚附近(≤10mm)放置 100nF MLCC。"
                        f"该电容 SRF≈{result.self_resonant_freq_hz/1e6:.0f}MHz，"
                        f"有效去耦 {result.effective_freq_range[0]/1e6:.1f}-{result.effective_freq_range[1]/1e6:.0f}MHz"
                    ),
                    theory="IC 晶体管开关产生 di/dt 瞬态，PCB 走线寄生电感(~5-10nH/cm)导致 VDD 跌落(V=L×di/dt)。"
                           "100nF MLCC Z 最低点在 SRF 附近(~10-15MHz)，有效覆盖数字电路主要噪声频段。",
                ))
        elif total_100nf < ic_count:
            # 供需缺口：报一条汇总 WARNING，避免逐 IC 刷屏
            gap = ic_count - total_100nf
            violations.append(RuleViolation(
                rule_name="去耦电容检查",
                description=(
                    f"高频去耦电容不足：{total_100nf} 个 100nF 需覆盖 {ic_count} 个 IC，"
                    f"缺口 {gap} 个"
                ),
                severity=RuleSeverity.WARNING,
                location=",".join(getattr(i, "reference", "?") for i in ics[:5]),
                suggestion=f"为缺口中的 {gap} 个 IC 各补充 1 个 100nF MLCC（≤10mm 靠近电源引脚）",
                theory="每颗 IC 的电源引脚都应有就近的高频去耦电容(100nF)，覆盖不足会导"
                       "致 IC 供电瞬态跌落，影响信号完整性与 EMC。",
            ))

        # ── 体电容 10µF 覆盖 ──
        if total_bulk == 0:
            for ic in ics:
                ic_ref = getattr(ic, "reference", "?")
                violations.append(RuleViolation(
                    rule_name="去耦电容检查",
                    description=f"IC {ic_ref} 缺少体电容(10µF)用于低频纹波",
                    severity=RuleSeverity.WARNING,
                    location=ic_ref,
                    suggestion="在电源入口处添加 10µF 钽电容或 MLCC 以抑制低频纹波(≤1MHz)",
                    theory="大电容(10-100µF)提供低频能量储备，小电容(100nF)处理高频瞬态。两者并联扩大有效频率范围。",
                ))
        elif total_bulk < ic_count:
            gap = ic_count - total_bulk
            violations.append(RuleViolation(
                rule_name="去耦电容检查",
                description=f"体电容不足：{total_bulk} 个 10µF 需覆盖 {ic_count} 个 IC，缺口 {gap} 个",
                severity=RuleSeverity.WARNING,
                location=",".join(getattr(i, "reference", "?") for i in ics[:5]),
                suggestion=f"在电源入口处为缺口中的 {gap} 个 IC 补充 10µF 体电容",
                theory="体电容(10µF 级)承担低频能量储备，高频去耦电容(100nF)处理高频瞬态，两者缺一不可。",
            ))
        return violations


    def _check_crystal_load_caps(self, bom_items, positions, netlist):
        """晶振负载电容检查：每个晶振应配备 2 个匹配负载电容。

        契合实际使用的修复（2026-08-03）：
        1. 晶振判定必须描述含频率/晶振关键词——"X" 前缀可能是连接器
           （如 dcdc 板的 X3=AFC07 排线座），纯前缀判定会产生误报。
        2. 负载电容不要求与晶振同前缀（真实设计负载电容均为 C 前缀），
           退化为统计板上负载电容级小电容（1-47pF）的供需关系。
        """
        violations = []
        crystal_kw = ["晶振", "crystal", "oscillator", "谐振", "mhz", "khz", "32.768"]
        crystals = []
        for item in bom_items:
            desc = (
                f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} "
                f"{getattr(item, 'value', '')}"
            ).lower()
            if any(kw in desc for kw in crystal_kw):
                crystals.append(item)
        if not crystals:
            return violations

        # 统计板上负载电容级小电容总量（1-47pF，皮尔斯振荡器典型 12-22pF）
        load_count = sum(
            _component_count(c)
            for c in bom_items
            if _classify_component(c) == "cap"
            and (cf := _parse_capacitance(getattr(c, "value", ""))) is not None
            and 1e-12 <= cf <= 47e-12
        )
        need = 2 * len(crystals)
        if load_count < need:
            refs = ",".join(getattr(i, "reference", "?").split(",")[0] for i in crystals)
            violations.append(RuleViolation(
                rule_name="晶振负载电容检查",
                description=(
                    f"晶振负载电容可能不足：板上 {load_count} 颗 1-47pF 小电容，"
                    f"需 {need} 颗覆盖 {len(crystals)} 个晶振"
                ),
                severity=RuleSeverity.WARNING,
                location=refs,
                suggestion="每颗晶振需 2 个匹配负载电容(通常 12~22pF)，参见数据手册",
                theory="皮尔斯振荡器是最常用 MCU 晶振电路。CL=(CL1×CL2)/(CL1+CL2)+Cstray，Cstray 包含 PCB 寄生和 MCU 引脚电容(~3-7pF)。CL 偏差过大致起振失败或频率偏移。",
            ))
        return violations


    def _check_crystal_frequency(self, bom_items, positions, netlist):
        """晶振频率匹配：不同频率晶振应匹配对应负载电容值"""
        violations = []
        crystal_kw = ["晶振", "crystal", "xtal", "oscillator", " resonator"]
        crystal_ref_prefixes = {"X", "Y"}
        crystal_map = {"32.768": ("12.5pF", "15pF"), "8M": ("18pF", "22pF"),
                       "12M": ("15pF", "22pF"), "16M": ("12pF", "18pF"), "25M": ("12pF", "18pF"),
                       "32.768K": ("12.5pF", "15pF"), "8MHZ": ("18pF", "22pF")}
        for item in bom_items:
            val = (getattr(item, "value", "") or "").strip()
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}"
            ref = getattr(item, "reference", "").split(",")[0].strip()
            ref_prefix = "".join(c for c in ref if c.isalpha()).upper()
            is_crystal = (
                any(kw in desc.lower() for kw in crystal_kw)
                or ref_prefix in crystal_ref_prefixes
            )
            if not is_crystal:
                continue
            freq = val.replace(" ", "").upper()
            # Also check description for frequency info
            if not any(c.isdigit() for c in freq):
                freq = desc.replace(" ", "").upper()
            matched = next(((k, c) for k, c in crystal_map.items() if freq.startswith(k.upper())), None)
            if matched:
                fname, (cl_min, cl_max) = matched
                violations.append(RuleViolation(
                    rule_name="晶振频率匹配", description=f"晶振 {ref} ({fname}Hz) 建议 CL={cl_min}~{cl_max}",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion=f"匹配负载电容 = {cl_min}~{cl_max}，配合 Cstray≈5pF",
                    theory="石英晶振的频率稳定性依赖正确 CL。32.768kHz 晶振 CL 偏差 2pF 可引起 ≥10ppm 误差。"))
        return violations


    def _check_i2c_pullups(self, bom_items, positions, netlist):
        """I2C 上拉电阻：SDA/SCL 需上拉电阻(典型 4.7kΩ)

        2026-10-09 抽查修正：① 总线存在性以网表网络名为准——网表非空但没有
        SDA/SCL 网时，BOM 描述词（如 hub 芯片描述「带 I2C」）不再扩权，那是
        器件能力不是板上总线；② 上拉电阻识别从「描述含电阻」改为位号前缀 R
        （真实 BOM 描述是「22uF ±20%」式参数文本或整行为空，子串判据双向
        失效，有上拉的板恒报）；③ 网表可用时判「总线网上有没有挂 R 引脚」，
        比全 BOM 找典型值更可证伪——上拉不在总线上等于没有。
        """
        violations = []
        i2c_net_kw = ("i2c", "i²c", "sda", "scl", "twi", "iic")
        if netlist:
            i2c_nets = [name for name in netlist if _net_kw_hit(str(name), i2c_net_kw)]
            if not i2c_nets:
                return violations
            bus_refs = {
                str(p).split(".")[0].strip().upper()
                for n in i2c_nets for p in (netlist.get(n) or [])
            }
            has_pullup = any(
                _is_resistor_row(i)
                and bus_refs.intersection(
                    t.upper() for t in re.split(r"[,，\s]+", (getattr(i, "reference", "") or "").strip()) if t)
                for i in bom_items)
        else:
            # 无网表数据：退回 BOM 文本 + 典型上拉值
            pullup_vals = ("4.7k", "4k7", "4700", "10k", "10000", "2.2k", "2k2", "3.3k", "3k3")
            if not any(_kw_hit(_row_text(i), i2c_net_kw) for i in bom_items):
                return violations
            has_pullup = any(
                _is_resistor_row(i)
                and any(v in (getattr(i, "value", "") or "").lower().replace(" ", "") for v in pullup_vals)
                for i in bom_items)
        if not has_pullup:
            violations.append(RuleViolation(
                rule_name="I2C 上拉电阻检查",
                description="检测到 I2C 器件但未发现典型上拉电阻(2.2~10kΩ)",
                severity=RuleSeverity.WARNING,
                suggestion="SDA/SCL 各需上拉电阻到 VCC(常用 4.7kΩ)",
                theory="I2C 使用开漏输出——器件只能拉低总线。Rp 上拉恢复高电平: Rp 过大→trise≈Rp×Cbus 缓慢, Rp 过小→功耗过大。标准模式(100kHz)典型 Rp=4.7kΩ。"))
        return violations


    def _check_power_filtering(self, bom_items, positions, netlist):
        """电源滤波：电源入口应有大电解+小陶瓷组合"""
        violations = []
        if not bom_items:
            return violations
        pwr_kw = ["电源", "power", "VIN", "VBUS", "DC-IN", "PWR"]
        # 2026-10-10 标准表批：bulk 白名单补 330µF（立创常用电解档位）
        bulk_uf = ["100u", "220u", "330u", "470u", "1000u", "100ΜF"]
        try:
            has_input = any(kw.lower() in f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')} {getattr(i, 'value', '')}".lower()
                            for i in bom_items for kw in pwr_kw)
        except Exception:
            return violations
        if not has_input:
            return violations
        has_bulk = any(any(v.lower() in getattr(i, "value", "").lower() for v in bulk_uf) for i in bom_items)
        has_small = any(getattr(i, "value", "").replace(" ", "").upper() in {"0.1UF", "100NF", "0.1ΜF", "104"} for i in bom_items)
        if not (has_bulk and has_small):
            missing = []
            if not has_bulk: missing.append("大电解(≥100μF)")
            if not has_small: missing.append("小陶瓷(0.1μF)")
            violations.append(RuleViolation(
                rule_name="电源滤波检查", description=f"电源入口缺少: {', '.join(missing)}",
                severity=RuleSeverity.WARNING,
                suggestion="电源输入配置大电解(100μF+)+小陶瓷(0.1μF)组合",
                theory="电解电容 ESR≈0.1~1Ω 适合滤除低频整流纹波;MLCC ESR≈10mΩ 适合滤除 MHz 级开关噪声。并联可实现宽频带滤波。"))
        return violations


    def _check_power_rail_decoupling(self, bom_items, positions, netlist):
        """电源轨去耦网络：每条电源轨应有分级去耦"""
        violations = []
        cap_vals = []
        if not bom_items:
            return violations
        try:
            for item in bom_items:
                pn = (getattr(item, "part_number", "") or "").lower()
                val = (getattr(item, "value", "") or "").replace(" ", "").upper()
                if any(kw.lower() in pn for kw in ["电容", "capacitor"]):
                    cap_vals.append(val)
        except Exception:
            return violations
        has_small = any(v in ["0.1UF", "100NF", "0.1ΜF", "104"] for v in cap_vals)
        has_mid = any(any(s in v for s in ["1UF", "2.2U", "4.7U", "10U"]) for v in cap_vals)
        if cap_vals and not (has_small and has_mid):
            missing = []
            if not has_small: missing.append("0.1μF(高频去耦)")
            if not has_mid: missing.append("1~10μF(中频滤波)")
            violations.append(RuleViolation(
                rule_name="电源轨去耦网络", description=f"缺少: {', '.join(missing)}",
                severity=RuleSeverity.WARNING,
                suggestion="每路电源三级滤波: 100μF(电解)+10μF(MLCC)+0.1μF(MLCC)",
                theory="MLCC 阻抗-频率曲线呈 V 形:低频容性(Z=1/ωC),谐振点最小(≈ESR),高频感性(Z=ω·ESL)。单一电容无法覆盖全频段——需三级并联。"))
        return violations


    def _check_floating_pins(self, bom_items, positions, netlist):
        """悬空引脚：MCU 的 RST/BOOT/EN 等控制引脚不应悬空"""
        violations = []
        mcu_kw = ["MCU", "STM32", "ESP32", "ATmega", "ARM", "单片机", "CPU", "FPGA"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}"
            if any(kw.lower() in desc.lower() for kw in mcu_kw):
                ref = getattr(item, "reference", "?")
                violations.append(RuleViolation(
                    rule_name="悬空引脚检查",
                    description=f"主控 {ref} 的 RST/BOOT/EN 等控制引脚可能悬空",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion="RST 上拉(10kΩ)，BOOT 明确上下拉。悬空=不可预知行为。",
                    theory="CMOS 输入阻抗>10MΩ，悬空时引脚电压由漏电流和 EMI 决定，处于亚稳态——可能引起振荡、功耗增大、闩锁效应(latch-up)。"))
                break
        return violations


    def _check_reset_circuit(self, bom_items, positions, netlist):
        """复位电路：MCU RST 应有 RC 网络或专用复位 IC"""
        violations = []
        mcu_kw = ["MCU", "STM32", "ESP32", "ATmega", "ARM", "单片机", "CPU"]
        found_mcu = next((i for i in bom_items
                          if any(kw.lower() in f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}".lower()
                                 for kw in mcu_kw)), None)
        if not found_mcu:
            return violations
        has_cap, has_r, has_ic = False, False, False
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").lower()
            desc = (getattr(item, "description", "") or "").lower()
            val = (getattr(item, "value", "") or "").lower()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            prefix = "".join(c for c in ref if c.isalpha()).upper()
            if any(kw in desc or kw in pn for kw in ["复位", "reset", "监控", "supervisor", "看门狗", "watchdog",
                                                       "MAX809", "MAX811", "IMP809", "STM809"]):
                has_ic = True
            if prefix == "C" and any(v in val for v in ["0.1u", "0.1μ", "100n", "104"]):
                has_cap = True
            if prefix == "R" and any(v in val for v in ["10k", "10000", "4.7k", "4700"]):
                has_r = True
        mcu_ref = getattr(found_mcu, "reference", "").split(",")[0].strip()
        if has_ic:
            return violations
        issues = []
        if not has_r: issues.append("上拉电阻(10kΩ)")
        if not has_cap: issues.append("对地电容(0.1μF)")
        if issues:
            violations.append(RuleViolation(
                rule_name="复位电路检查", description=f"MCU {mcu_ref} 复位电路缺少: {', '.join(issues)}",
                severity=RuleSeverity.WARNING, location=mcu_ref,
                suggestion="RST 外接 10kΩ 上拉 VCC + 0.1μF 对地(τ=1ms)，或使用专用复位 IC",
                theory="上电时 VCC 上升需 trise(1~10ms)，RST 必须保持低电平待 VCC 稳定。RC 低电平时间≈R×C×ln(VCC/Vih)。专用复位 IC 提供更精确阈值和去抖。"))
        return violations


    def _check_esd_protection(self, bom_items, positions, netlist):
        """ESD 保护：外部接口应有 TVS/ESD 保护器件"""
        violations = []
        # 2026-10-09 抽查修正：连接器/保护器件识别统一走位号前缀 + 词边界
        # （_kw_hit），并把 value 纳入搜索文本——真实 BOM 常只把型号写在 value
        # （P6SMBJ6.0CA 这类真 TVS 因此漏认）。
        conn_kw = ["USB", "HDMI", "RJ45", "DB9", "FPC", "排针", "端子", "连接器",
                   "connector", "header", "jack", "插座", "卡座"]
        esd_kw = ["TVS", "ESD", "SRV05", "USBLC6", "RCLAMP", "PESD", "SMAJ", "SMBJ",
                  "压敏", "防静电", "保护管", "BDFN"]
        # ESD 器件家族名常被「上一个字母」内嵌（GESD0501BU / LESD5Z5…），
        # 词边界拒内嵌会漏认真 TVS——料号按家族前缀补一层。
        esd_pn_prefixes = ("ESD", "GESD", "LESD", "TVS", "PESD", "SRV05", "USBLC",
                           "RCLAMP", "PGB", "SMF", "SMAJ", "SMBJ")
        # Connector reference prefixes (common for headers, FPC, USB, etc.)
        conn_ref_prefixes = {"J", "P", "H", "CN", "USB", "FPC"}
        # Check for connectors by keyword OR reference prefix
        has_conn = any(
            _any_ref_prefix(i, conn_ref_prefixes)
            or _kw_hit(_row_text(i), conn_kw)
            for i in bom_items
        )
        if not has_conn:
            return violations
        has_esd = any(
            (getattr(i, "part_number", "") or "").strip().upper().startswith(esd_pn_prefixes)
            or _kw_hit(_row_text(i), esd_kw)
            for i in bom_items)
        if not has_esd:
            violations.append(RuleViolation(
                rule_name="ESD 保护检查", description="存在外部连接器但未检测到 TVS/ESD 保护器件",
                severity=RuleSeverity.WARNING,
                suggestion="外露接口各信号线加装 TVS 管(如 USBLC6-2)",
                theory="HBM ESD 放电可达 ±2~15kV，峰值电流数十安培，上升时间≤1ns。TVS 利用雪崩击穿在 ns 级钳位电压。IEC 61000-4-2 规定 4 级=接触±8kV/空气±15kV。高速信号需结电容≤0.5pF。"))
        return violations


    def _check_reference_continuity(self, bom_items, positions, netlist):
        """位号连续性：同类元件位号应连续

        2026-10-09 噪声清扫：跳号在真实设计里是正常实践（预留位、删除元件、
        功能分区编号），金样 61/78 板都有、189 条里 106 条是「跳 1 号」。
        改为每板至多 1 条汇总提示（设计卫生口径，建议类），不再逐前缀报。
        """
        rc_prefixes = {"R", "C", "L", "D", "U", "Q", "J", "P"}
        prefix_map: dict[str, list[int]] = {}
        for item in bom_items:
            ref = getattr(item, "reference", "")
            if not ref: continue
            # 2026-10-06 修复：一行可含多个位号（"R4,R5"），原来只取第一个，
            # 会把实际存在的位号当跳号报出。中英文逗号、空格分隔都拆开参与判断。
            for token in re.split(r"[,，\s]+", ref.strip()):
                if not token: continue
                prefix = "".join(c for c in token if c.isalpha()).upper()
                if prefix in rc_prefixes:
                    nums = "".join(c for c in token if c.isdigit())
                    if nums: prefix_map.setdefault(prefix, []).append(int(nums))
        gap_bits: list[str] = []
        for prefix in sorted(prefix_map):
            nums = sorted(prefix_map[prefix])
            for i in range(len(nums) - 1):
                gap = nums[i + 1] - nums[i]
                if gap > 1:
                    gap_bits.append(f"{prefix}{nums[i]}→{prefix}{nums[i+1]}(跳{gap-1}号)")
        if gap_bits:
            shown = ", ".join(gap_bits[:4]) + (" …" if len(gap_bits) > 4 else "")
            return [RuleViolation(
                rule_name="位号连续性检查", description=f"位号存在跳号: {shown}",
                severity=RuleSeverity.INFO,
                suggestion="跳号常见于预留空位/删除元件/功能分区编号，不是缺陷；批量生产前可用位号重排统一。",
                theory="规范化 BOM 中同类元件位号应连续(R1,R2,R3...)。PCB 设计工具均提供自动重排位号功能。")]
        return []


    def _check_package_consistency(self, bom_items, positions, netlist):
        """封装一致性：同型号不同封装可能为误选（封装名先做前缀归一）"""
        violations = []
        pn_pkgs: dict[str, set] = {}
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip()
            pkg = (getattr(item, "package", "") or "").strip()
            if not pn or not pkg or pn == "N/A": continue
            pn_pkgs.setdefault(pn, set()).add(_norm_fp(pkg))
        for pn, pkgs in pn_pkgs.items():
            if len(pkgs) > 1:
                refs = [getattr(i, "reference", "") for i in bom_items if (getattr(i, "part_number", "") or "").strip() == pn]
                violations.append(RuleViolation(
                    rule_name="封装一致性检查", description=f"型号 [{pn}] 出现多种封装: {', '.join(sorted(pkgs))}",
                    severity=RuleSeverity.WARNING, location=", ".join(refs[:5]),
                    suggestion="同型号应采用相同封装。多封装可能为采购错误或 BOM 录入疏忽。",
                    theory="同一物料号出现不同封装(如 0805 和 0603 混用)通常表示手动替换未统一，可能导致 SMT 贴片程序不匹配。IPC-7351 规定标准封装命名。"))
        return violations


    # IEC 60063 标准系列有效数字×100。E24 覆盖 ±5/10%，E96 覆盖 ±1%。
    # E24 值（470 等）在 ±1% 供应里同样常见（E96 与 E24 在 1% 精度下并行供货），
    # 故判据取「E24 恒合法，容差支持时 E96 追加合法」。
    _E24_MANT100 = frozenset((
        100, 110, 120, 130, 150, 160, 180, 200, 220, 240, 270, 300,
        330, 360, 390, 430, 470, 510, 560, 620, 680, 750, 820, 910))
    _E96_MANT100 = frozenset((
        100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130,
        133, 137, 140, 143, 147, 150, 154, 158, 162, 165, 169, 174,
        178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232,
        237, 243, 249, 255, 261, 267, 274, 280, 287, 294, 301, 309,
        316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412,
        422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549,
        562, 576, 590, 604, 619, 634, 649, 665, 681, 698, 715, 732,
        750, 768, 787, 806, 825, 845, 866, 887, 909, 931))

    @staticmethod
    def _parse_tolerance_percent(item) -> float | None:
        """从 BOM 行文本解析容差 (%)；无容差信息返回 None。

        覆盖 ±1% / 1% / ±10% 写法与 EIA 代码 F(±1%)/G(±2%)/J(±5%)/K(±10%)
        ——后者常单独出现在料号尾段（如 10uF±20% 的「M」码不取，M=±20% 同 E24 档）。
        """
        txt = _row_text(item)
        m = re.search(r"[±+\-~]*\s*(0\.5|1|2|5|10)\s*%", txt)
        if m:
            return float(m.group(1))
        m = re.search(r"(?:^|[^a-z0-9])([fgjk])(?:[^a-z0-9]|$)", txt)
        if m:
            return {"f": 1.0, "g": 2.0, "j": 5.0, "k": 10.0}[m.group(1)]
        return None

    def _check_bom_value_range(self, bom_items, positions, netlist):
        """参数范围：电阻/电容值应在标准系列内（按容差分档 E24/E96）。

        2026-10-10 标准表批：原判据一律套 E24，±1% 精度件的 E96 值
        （4.64kΩ/45.3kΩ…）全被判「不在 E24」——值是真的标准值，只是系列
        不对。改按行容差分档：±1/2% → E96∪E24 合法，±5/10% → E24，
        无容差信息 → 并集放行（不冤枉没写容差的行）。
        """
        violations = []
        for item in bom_items:
            val = (getattr(item, "value", "") or "").strip()
            if not val: continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            prefix = "".join(c for c in ref if c.isalpha()).upper()
            if prefix not in ("R", "C", "L"): continue
            parsed = _parse_component_value(val)
            if parsed is None: continue
            mantissa, exp = parsed
            if mantissa <= 0: continue
            # 归一化到 [1, 10)：只比较有效数字
            # （20kΩ→2.0、22µF→2.2、100nF→1.0、0.47µF→4.7）。
            # 2026-09-18 抽查修正：原实现拿未归一化的 mantissa 去比 e*10，相差 10 倍，
            # 于是 20kΩ/22µF/100nF/100KΩ 等标准值全被判「不在 E24」（全库 779 条误报）。
            while mantissa >= 10:
                mantissa /= 10.0
                exp += 1
            while mantissa < 1:
                mantissa *= 10.0
                exp -= 1
            mant_x100 = round(mantissa * 100)
            tol = self._parse_tolerance_percent(item)
            if tol is None:                      # 无容差信息：E24∪E96 放行
                legal = self._E24_MANT100 | self._E96_MANT100
                series_note = "E24/E96"
            elif tol <= 2:                       # ±1%/±2%：E96 精度件
                legal = self._E96_MANT100 | self._E24_MANT100
                series_note = f"E96/E24(±{tol:g}%)"
            else:                                # ±5%/±10%：E24
                legal = self._E24_MANT100
                series_note = "E24"
            if mant_x100 not in legal:
                violations.append(RuleViolation(
                    rule_name="参数范围检查", description=f"{ref} 参数 [{val}] 不在{series_note}标准系列",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion="非标值可能需要定制或改选相邻标准档（E24/E96 由 IEC 60063 规定）",
                    theory="标准值系列(E-series)由 IEC 60063 规定:E24 覆盖±5%(步进≈10%),E96 覆盖±1%。"))
        return violations


    def _check_led_current_limit(self, bom_items, positions, netlist):
        """LED 限流电阻：每个 LED 应有匹配的限流电阻"""
        violations = []
        led_kw = ["LED", "发光", "light", "指示", "照明", "灯珠"]
        # 2026-10-09 抽查修正：「描述含电阻」判据在真实 BOM 上恒假（描述是
        # 参数文本或为空）→ 每个 LED 行都报。改位号前缀 R 判电阻存在
        # （电阻行前缀 R/RN，与 LED 行前缀天然不同，无需再排除自身）。
        has_resistor = any(_is_resistor_row(r) for r in bom_items)
        for item in bom_items:
            desc = _row_text(item)
            if not _kw_hit(desc, led_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if not has_resistor:
                violations.append(RuleViolation(
                    rule_name="LED 限流电阻检查",
                    description=f"LED {ref} 可能缺少限流电阻",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion=f"串联限流电阻 R=(VCC-Vf)/If。红/绿LED Vf≈1.8~2.2V,蓝/白LED Vf≈3.0~3.4V。If通常取5~20mA。",
                    theory="LED 是电流驱动型器件，其 I-V 曲线在导通后极为陡峭——Vf 变化仅 0.1V 即可致电流变化数倍，未限流易烧毁。限流电阻将电压源转为近似电流源。",
                ))
        return violations


    def _check_relay_flyback_diode(self, bom_items, positions, netlist):
        """继电器续流二极管：继电器线圈两端应并联续流二极管"""
        violations = []
        relay_kw = ["继电器", "relay", "RELAY", "电磁", "线圈"]
        diode_kw = ["二极管", "diode", "1N4148", "1N400", "肖特基", "schottky", "SS14", "SS34"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.lower() in desc for kw in relay_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            has_diode = any(
                any(kw.lower() in (f"{getattr(d, 'part_number', '')} {getattr(d, 'description', '')}").lower()
                    for kw in diode_kw)
                for d in bom_items if d is not item
            )
            if not has_diode:
                violations.append(RuleViolation(
                    rule_name="继电器续流二极管检查",
                    description=f"继电器 {ref} 线圈回路缺少续流二极管",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion="线圈两端反并联二极管(1N4148 用于小功率,1N4007 用于大功率)。二极管耐压≥VCC×2。",
                    theory="继电器线圈是感性负载(L≈数十~数百mH)。开关断开时电感电流不能突变,产生 V=L×di/dt 反电动势(可达 VCC×10+),击穿驱动晶体管或 MOSFET。续流二极管提供电流泄放通路,将反压钳位在 Vf≈0.7V。",
                ))
        return violations


    def _check_reverse_polarity_protection(self, bom_items, positions, netlist):
        """电源极性保护：直流电源输入应具有反接保护"""
        violations = []
        # 2026-10-09 抽查修正：电源入口识别从「任意行描述含 power/VIN/PWR」改为
        # _has_power_entry（网表入口网络挂连接器/电池引脚 + 连接器行入口词）——
        # 旧判据下 SN74HC125PWR 的封装后缀、LDO 描述「Vin=18V」都成了入口。
        # 保护器件识别加位号前缀 D/Q/F（二极管/MOS/保险丝）——SS54/AO3401 的
        # 描述是「40V 3A」「P沟道 30V」，旧关键词全漏。USB 供电不算入口
        # （键控连接器不存在反接）。
        protection_kw = ["MOSFET", "PMOS", "NMOS", "二极管", "diode", "肖特基", "schottky",
                         "保险丝", "fuse", "PTC", "TVS", "稳压管", "efuse", "e-fuse",
                         "热插拔", "自恢复"]
        has_pwr_in = _has_power_entry(bom_items, netlist, include_usb=False)
        if not has_pwr_in:
            return violations
        has_protection = any(
            _any_ref_prefix(i, {"D", "Q", "F"})
            or _kw_hit(_row_text(i), protection_kw)
            for i in bom_items
        )
        if not has_protection:
            violations.append(RuleViolation(
                rule_name="电源极性保护检查",
                description="直流电源输入未检测到反接保护器件",
                severity=RuleSeverity.WARNING,
                suggestion="串联肖特基二极管(低压降~0.3V)或 PMOS 反接保护电路。PMOS Vgs(th) 选低阈值型(≤2.5V)。",
                theory="反接时电源直接反向施加于负载→电解电容反向击穿、IC latch-up、MCU 烧毁。肖特基方案简单但有压降损耗(0.3~0.5V×I);PMOS 方案 Rdson≈10~50mΩ,几乎无损耗,但需额外栅极分压电阻。",
            ))
        return violations


    def _check_dcdc_feedback_network(self, bom_items, positions, netlist):
        """DC-DC 反馈网络：开关稳压器应有 FB 分压电阻"""
        violations = []
        # 2026-09-24 抽查修正：原关键词含裸两字母 "MP"/"SY"/"MT"/"XL" 且只做子串匹配，
        # 于是 XL-1608(LED)、MPU6500、磁珠、钽电容都被当成「开关稳压器」去要 FB 分压电阻。
        # 现在：① 位号必须是 IC 类前缀；② 料号命中明确稳压器系列，或描述含完整词
        # （口径统一收编到模块级 _DCDC_PN_PREFIXES / _is_dcdc_part，2026-10-06）。
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            ref_prefix = "".join(c for c in ref if c.isalpha()).upper()
            if ref_prefix not in ("U", "IC", "PU", "PS"):
                continue
            if not _is_dcdc_part(item):
                continue
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            # 检查是否有分压电阻（DC-DC FB 需要两个电阻分压）。
            # 2026-10-09 抽查修正：「描述含电阻」在真实 BOM 上恒假 → 有反馈
            # 网络的板也恒报。改位号前缀 R 判电阻行。
            resistors = [r for r in bom_items if _is_resistor_row(r) and r is not item]
            has_fb_r = len(resistors) >= 2
            if not has_fb_r:
                violations.append(RuleViolation(
                    rule_name="DC-DC 反馈网络检查",
                    description=f"开关稳压器 {ref}({pn}) 缺少 FB 分压电阻网络",
                    severity=RuleSeverity.ERROR, location=ref,
                    suggestion=f"Vout=Vref×(1+R1/R2)。Vref 通常 0.6V/0.8V/1.25V(查数据手册)。R2 通常取 10kΩ 左右。",
                    theory="开关稳压器通过比较 FB 电压与内部基准 Vref 来调节占空比→稳定 Vout。无 FB 网络则输出电压不受控,可能升至输入电压致负载烧毁。R1/R2 精度影响 Vout 精度—建议用 ±1% 电阻。",
                ))
        return violations


    def _check_mosfet_gate_resistor(self, bom_items, positions, netlist):
        """MOSFET 栅极电阻：功率 MOSFET 栅极应串联电阻抑制振荡"""
        violations = []
        # 2026-09-24 抽查修正：原判据用裸子串 "SI"/"MOS"/"AO" 匹配，inmp441(麦克风)、
        # NanoSIM 等含这些字母组合的元件被当成功率 MOSFET；且算出的 has_gate_r
        # 从未参与判断，等价于「只要长得像 MOSFET 就报」。现在：位号是 Q 前缀
        # （或料号命中明确型号），并且确实没有串联栅极电阻才报。
        mosfet_pn_prefixes = ["IRF", "IRL", "2N700", "BSS", "AO3", "AO4", "AO5",
                              "SI2", "SI3", "SI4", "SI7", "CSD", "FDN", "FDS",
                              "NCE", "CJ2", "AON", "DMN", "DMP"]
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            ref_prefix = "".join(c for c in ref if c.isalpha()).upper()
            desc = f"{getattr(item, 'description', '') or ''}".lower()
            is_mosfet = (
                any(pn.startswith(p) for p in mosfet_pn_prefixes)
                or (ref_prefix.startswith("Q")
                    and any(kw in desc for kw in ("mosfet", "mos", "nmos", "pmos",
                                                  "场效应", "三极管", "晶体管")))
            )
            if not is_mosfet:
                continue
            has_gate_r = any(
                any(kw in (f"{getattr(r, 'part_number', '')} {getattr(r, 'description', '')}").lower()
                    for kw in ("电阻", "resistor"))
                for r in bom_items if r is not item
            )
            if has_gate_r:
                continue
            violations.append(RuleViolation(
                rule_name="MOSFET 栅极电阻检查",
                description=f"功率 MOSFET {ref} 建议串联栅极电阻",
                severity=RuleSeverity.INFO, location=ref,
                suggestion="栅极串联 10~100Ω 抑制寄生振荡。PWM 高频开关取低值(10Ω),低频开关取高值(100Ω)。",
                theory="MOSFET 栅极-源极间 Cgs≈数百~数千pF,与 PCB 走线寄生电感形成 LC 谐振回路。Q 值高时产生 MHz 级振荡→开关损耗↑、EMI↑。栅极电阻 Rg 降低 Q 值,阻尼振荡。Rg 还与开关速度 trade-off。",
            ))
        return violations


    def _check_optocoupler_input_resistor(self, bom_items, positions, netlist):
        """光耦输入限流：光耦输入端应有限流电阻"""
        violations = []
        # 2026-09-24 抽查修正：原关键词含裸两字母 "PS" → 所有 TPS 电源芯片被判成光耦；
        # 且「输入端限流电阻」要求电阻位号前缀 == 光耦位号前缀（U vs R 永不相等），
        # 只要识别出光耦就必然报一次。现在：料号命中明确光耦系列或描述含完整词，
        # 限流电阻按「BOM 里存在电阻」判定。
        opto_kw = ["光耦", "optocoupler", "光电耦合"]
        opto_pn_prefixes = ["PC817", "PC81", "TLP", "EL817", "EL357", "6N137",
                            "HCPL", "PS25", "PS28", "SFH", "LTV", "CNY", "MOC30"]
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not (any(kw in desc for kw in opto_kw)
                    or any(pn.startswith(p) for p in opto_pn_prefixes)):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            has_input_r = any(
                any(kw in (f"{getattr(r, 'part_number', '')} {getattr(r, 'description', '')}").lower()
                    for kw in ("电阻", "resistor"))
                for r in bom_items if r is not item
            )
            if not has_input_r:
                violations.append(RuleViolation(
                    rule_name="光耦输入限流检查",
                    description=f"光耦 {ref} 输入端可能缺少限流电阻",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion=f"Rin=(Vin-Vf)/If。Vf≈1.2V,If 取 5~20mA(查 CTR 曲线)。CTR=50~600% 根据型号而不同。",
                    theory="光耦内部 LED 的 Vf≈1.0~1.4V。无限流时 LED 电流仅由驱动端内阻限制,可能超出 LED 额定电流(通常 50mA max)。CTR(电流传输比)随 If 变化,设计需保证全温范围内 CTR 足够。",
                ))
        return violations


    def _check_adc_input_filter(self, bom_items, positions, netlist):
        """ADC 输入滤波：ADC 输入引脚应有 RC 抗混叠滤波"""
        violations = []
        adc_kw = ["ADC", "A/D", "模数转换", "ADS", "MCP3", "MAX1", "AD77", "AD76"]
        has_adc = False
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            if any(kw.lower() in desc for kw in ["ADC", "模数", "模数转换", "A/D"]) or \
               any(pn.startswith(p) for p in ["ADS1", "ADS8", "MCP3", "MAX1", "AD77", "AD76"]):
                has_adc = True
                break
        if not has_adc:
            return violations
        # 检查是否有 RC 滤波元件
        has_cap = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in ["电容", "capacitor", "nF", "pF", "NP0", "C0G"])
            for i in bom_items
        )
        if not has_cap:
            violations.append(RuleViolation(
                rule_name="ADC 输入滤波检查",
                description="检测到 ADC 但未发现输入滤波电容",
                severity=RuleSeverity.WARNING,
                suggestion="ADC 输入端加 RC 低通滤波(R=100Ω~1kΩ,C=1~100nF)。截止频率 fc=1/(2πRC) < 采样率/2(Nyquist)。",
                theory="ADC 采样产生 aliasing — 高于 fs/2 的输入频率混叠到基带。RC 抗混叠滤波器必须在 ADC 输入之前。电容同时作为采样保持电容的电荷库—SAR ADC 在采样瞬间从输入电容抽取电荷。",
            ))
        return violations


    def _check_opamp_feedback_network(self, bom_items, positions, netlist):
        """运放反馈网络：运算放大器应有反馈电阻网络

        2026-10-06 修复：旧判据数「位号前缀与运放相同的电阻」——运放是 U 前缀、
        电阻是 R 前缀，恒为 0，叠加「描述需含『电阻』」（本项目大量 BOM 描述为空），
        该规则结构上恒报。现在按网表判断：反馈/增益电阻必然与运放引脚共网，
        含该运放引脚的任一网络上见到 ≥1 个电阻即认为有反馈网络。
        网表缺失时数据不足，不判（避免退化成「有运放就报」）。
        """
        if not netlist:
            return []
        net_pins = {name: self._net_pins(v) for name, v in netlist.items()}
        # 电阻位号集合：R 前缀（R/RN/RNC）或描述/型号写明电阻 —— 与
        # _classify_component() 规则回退的电阻分支同一口径，但不经 ML（判据要确定性）。
        resistor_refs: set = set()
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            is_resistor = "电阻" in desc or "resistor" in desc
            for ref in item.reference_list:
                prefix = "".join(c for c in ref if c.isalpha()).upper()
                if is_resistor or prefix.startswith("R"):
                    resistor_refs.add(ref)
        # BOM 可能漏行：网表引脚名 "." 前的位号同样是器件类型的权威来源
        # （"R3.2"→R3，R 前缀即电阻），与 BOM 收集结果取并集。
        for pins in net_pins.values():
            for pin in pins:
                ref = pin.split(".")[0]
                if "".join(c for c in ref if c.isalpha()).upper().startswith("R"):
                    resistor_refs.add(ref)
        violations = []
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            if not any(kw in pn for kw in ["LM358", "LM324", "LMV358", "TL07", "TL08",
                                           "NE553", "OPA", "MCP6", "AD8"]):
                continue
            for ref in item.reference_list:
                pin_prefix = ref + "."
                opamp_nets = [name for name, pins in net_pins.items()
                              if any(p == ref or p.startswith(pin_prefix) for p in pins)]
                if not opamp_nets:
                    continue    # 网表没提到这个运放：缺数据，不下判断
                has_r = any(p.split(".")[0] in resistor_refs
                            for name in opamp_nets for p in net_pins[name])
                if not has_r:
                    violations.append(RuleViolation(
                        rule_name="运放反馈网络检查",
                        description=(f"运放 {ref}({pn}) 的 {len(opamp_nets)} 个网络"
                                     f"（{', '.join(opamp_nets[:5])}）上未见电阻，"
                                     f"可能缺少反馈电阻网络"),
                        severity=RuleSeverity.INFO, location=ref,
                        suggestion="同相放大:Gain=1+Rf/Rg;反相放大:Gain=-Rf/Rin。Rf 通常取 1kΩ~100kΩ,反馈网络靠近反相输入端。",
                        theory="运放开环增益极高(≥100dB),必须通过负反馈确定闭环增益并保证稳定性。无反馈→运放工作在开环比较器模式,输出饱和至电源轨。反馈电阻热噪声(4kTR·BW)贡献输出噪声。",
                    ))
        return violations


    def _check_capacitor_voltage_derating(self, bom_items, positions, netlist):
        """电容耐压降额：电容耐压应有 ≥20% 降额裕量"""
        violations = []
        # 常见电压轨 + IC 型号推断
        voltage_rails = {"3.3V": 3.3, "5V": 5.0, "12V": 12.0, "24V": 24.0}
        # IC models that imply a supply voltage
        ic_voltage_hints = {
            "ams1117-3.3": 3.3, "ams1117-5.0": 5.0, "me6211c33": 3.3,
            "mp1584": 5.0, "mp2451": 5.0, "tps5430": 5.0,
            "lm2596-3.3": 3.3, "lm2596-5.0": 5.0,
        }
        supply_voltages = set()
        for item in bom_items:
            val = (getattr(item, "value", "") or "").upper().replace(" ", "")
            pn = (getattr(item, "part_number", "") or "").upper().replace(" ", "")
            desc = f"{pn} {getattr(item, 'description', '')}".upper()
            for rail_v, rail_num in voltage_rails.items():
                if rail_v in val or rail_v in desc or f"VOUT={rail_v}" in desc or f"VOUT {rail_v}" in desc:
                    supply_voltages.add(rail_num)
            # Check IC hints
            for ic_hint, ic_voltage in ic_voltage_hints.items():
                if ic_hint in (pn + " " + val).lower():
                    supply_voltages.add(ic_voltage)
        # If no explicit voltage found, assume at least 3.3V (most common MCU supply)
        max_voltage = max(supply_voltages) if supply_voltages else 3.3
        # Capacitor detection: keyword OR reference prefix 'C'
        cap_kw = {"电容", "capacitor", "电解", "electrolytic", "MLCC", "陶瓷"}
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            desc = f"{getattr(item, 'part_number', '') or ''} {getattr(item, 'description', '') or ''}".lower()
            is_cap = (
                any(kw.lower() in desc for kw in cap_kw)
                or ref.upper().startswith("C")
            )
            if not is_cap:
                continue
            val = (getattr(item, "value", "") or "").strip().upper()
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            # 2026-09-24 抽查修正：见 _extract_voltage_rating 注释
            rated_v = _extract_voltage_rating(val, pn)
            if rated_v is not None and max_voltage > 0 and rated_v < max_voltage * 1.2:
                violations.append(RuleViolation(
                    rule_name="电容耐压降额检查",
                    description=f"电容 {ref} 耐压 {rated_v:g}V，系统最高电压 {max_voltage}V，裕量不足",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion=f"耐压至少 ≥{max_voltage*1.2:.0f}V。陶瓷电容 DC Bias 效应下有效容量显著下降,建议 ≥2× 额定电压。",
                    theory="MLCC X7R/X5R 在 DC 偏压下有效容量可降至标称的 20~50%。电解电容耐压 ≥1.2×Vpeak 以防浪涌击穿。降额不足致电容寿命指数衰减(Arrhenius 定律—温度每升 10°C 寿命减半)。",
                ))
        return violations


    def _check_resistor_power_rating(self, bom_items, positions, netlist):
        """电阻功率降额：功率电阻应有足够功率裕量"""
        violations = []
        # 2026-09-24 抽查修正：原判据只看描述子串，LED 规格文本「功率:60mW」会被
        # 当成功率电阻。现在先要求位号是电阻类前缀。
        pwr_r_kw = ["功率电阻", "shunt", "采样电阻", "检流", "限流电阻", "current sense"]
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            ref_prefix = "".join(c for c in ref if c.isalpha()).upper()
            if not ref_prefix.startswith("R") or ref_prefix in ("RL", "RELAY"):
                continue
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} {getattr(item, 'value', '')}".lower()
            if not (_kw_hit(desc, pwr_r_kw) or ("功率" in desc and "电阻" in desc)):
                continue
            pkg = (getattr(item, "package", "") or "").strip().upper()
            # 小封装难以承受大功率
            low_power_pkgs = {"0201", "0402", "0603", "0805"}
            if pkg in low_power_pkgs:
                violations.append(RuleViolation(
                    rule_name="电阻功率降额检查",
                    description=f"功率电阻 {ref} 封装 {pkg} 可能功率不足",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion=f"采样/限流电阻选用大封装(1206/2512)或专用金属膜电阻。{pkg} 额定功率: 0402=1/16W,0603=1/10W,0805=1/8W。",
                    theory="电阻额定功率在 70°C 以上需降额(derating)。采样电阻功耗 P=I²R,若实际功率超过额定 50% 则温升过大,阻值漂移加剧。大封装不仅提升功率,也降低寄生电感(感抗影响高频采样精度)。",
                ))
        return violations


    def _check_battery_voltage_divider(self, bom_items, positions, netlist):
        """电池电压监测分压器：电池供电系统应有电压监测分压电阻"""
        violations = []
        # 2026-09-24 抽查修正：原关键词含裸 "BAT" → 肖特基二极管 BAT54CT 被当成
        # 「电池供电系统」，于是被要求做电压分压。现在按完整词 + 电池类位号前缀判定。
        battery_kw = ["电池", "battery", "锂电池", "锂电", "li-ion", "li-po", "锂聚合物"]
        battery_prefixes = ("BT", "BAT", "BATT", "BATTERY")
        has_battery = any(
            _kw_hit(f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}".lower(), battery_kw)
            or "".join(c for c in getattr(i, "reference", "").split(",")[0].strip()
                       if c.isalpha()).upper().startswith(battery_prefixes)
            for i in bom_items
        )
        if not has_battery:
            return violations
        # 检查是否有分压电阻网络(两个串联电阻)
        resistors = [i for i in bom_items
                    if any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                           for kw in ["电阻", "resistor"])]
        has_divider = len(resistors) >= 2 and any(
            any(v in (getattr(r, "value", "") or "").replace(" ", "").upper()
                for v in ["100K", "200K", "300K", "470K", "1M"])
            for r in resistors
        )
        if not has_divider:
            violations.append(RuleViolation(
                rule_name="电池电压分压器检查",
                description="电池供电系统缺少电压监测分压电阻网络",
                severity=RuleSeverity.WARNING,
                suggestion="电池正极→R1(100k~1MΩ)→ADC 输入端→R2(10k~100kΩ)→GND。Vbat=Vadc×(R1+R2)/R2。分压比使 Vmax_bat 对应 ADC Vref。",
                theory="锂电满电 4.2V,低电 2.8~3.0V,MCU ADC 通常 Vref=3.3V 或内部 bandgap。需分压至 ADC 量程内。R1+R2 为大阻值以减少静态电流(μA 级),避免加速电池自放电。",
            ))
        return violations


    def _check_emi_filter(self, bom_items, positions, netlist):
        """EMI 滤波：电源入口应有共模电感/EMI 滤波"""
        violations = []
        # 2026-10-09 抽查修正：电源入口识别改 _has_power_entry（网表 + 连接器
        # 位号行），「PWR」料号后缀不再触发；滤波器件关键词走词边界并把 value
        # 纳入文本。
        emi_kw = ["共模", "common mode", "CMC", "EMI", "滤波器", "filter", "扼流圈", "choke",
                  "X电容", "Y电容", "X2", "Y2"]
        # USB 供电设备不算入口（VBUS 加共模电感非常规做法）
        has_pwr_in = _has_power_entry(bom_items, netlist, include_usb=False)
        if not has_pwr_in:
            return violations
        has_emi = any(_kw_hit(_row_text(i), emi_kw) for i in bom_items)
        if not has_emi:
            violations.append(RuleViolation(
                rule_name="EMI 滤波检查",
                description="电源入口缺少共模电感/EMI 滤波器件",
                severity=RuleSeverity.INFO,
                suggestion="电源入口建议加共模扼流圈(CMC)+X电容(0.1~1μF)+Y电容(1~4.7nF)。CMC 选型关注额定电流和共模阻抗。",
                theory="开关电源产生的共模噪声通过电源线传导至电网→超标(CISPR 22/32 Class B)。CMC 对共模信号呈高阻抗而对差模呈低阻抗,在 150kHz~30MHz 范围有效抑制传导 EMI。",
            ))
        return violations


    def _check_ferrite_bead_isolation(self, bom_items, positions, netlist):
        """磁珠隔离：模拟/数字电源域应有磁珠隔离"""
        violations = []
        # 2026-10-09 抽查修正：裸 'op' 子串命中 ESOP8/MSOP8 封装名（TP4056-42-ESOP8、
        # NS4150B MSOP-8 被当运放）。改为两层：明确器件家族走料号前缀（pn startswith，
        # 与 _DCDC_PN_PREFIXES 同口径），描述词走 _kw_hit 词边界。
        analog_pn_prefixes = ("OPA", "LM358", "LM324", "LMV3", "MCP6", "TL07", "AD8", "ADS",
                              "ADC", "DAC")
        analog_desc_kw = ("运放", "op", "模拟", "analog", "传感器", "sensor", "adc", "dac",
                          "放大器")
        digital_pn_prefixes = ("STM32", "ESP32", "ESP8266", "GD32", "CH32", "AT32", "NRF", "CC25")
        digital_desc_kw = ("mcu", "fpga", "arm", "单片机", "数字", "digital")
        bead_pn_prefixes = ("BLM", "MPZ", "FBM", "MMZ")
        has_digital = any(
            (getattr(i, "part_number", "") or "").strip().upper().startswith(digital_pn_prefixes)
            or _kw_hit(_row_text(i), digital_desc_kw)
            for i in bom_items
        )
        has_analog = any(
            (getattr(i, "part_number", "") or "").strip().upper().startswith(analog_pn_prefixes)
            or _kw_hit(_row_text(i), analog_desc_kw)
            for i in bom_items
        )
        if not (has_digital and has_analog):
            return violations
        has_bead = any(
            _any_ref_prefix(i, {"FB", "BE"})
            or (getattr(i, "part_number", "") or "").strip().upper().startswith(bead_pn_prefixes)
            or _kw_hit(_row_text(i), ("磁珠", "ferrite", "bead"))
            for i in bom_items
        )
        if not has_bead:
            violations.append(RuleViolation(
                rule_name="磁珠隔离检查",
                description="数模混合电路缺少磁珠进行电源域隔离",
                severity=RuleSeverity.WARNING,
                suggestion="数字电源→磁珠→模拟电源。磁珠选型关注 100MHz 阻抗(通常 30~600Ω@100MHz)和额定电流(需 ≥2× 实际负载)。",
                theory="数字电路高频开关产生 di/dt 噪声通过电源平面耦合至模拟电路→ADC SNR↓、运放输出纹波↑。磁珠在低频(DC)呈低阻抗(≈mΩ),在高频(≥10MHz)呈高阻抗(≈数百Ω),有效隔离高频噪声。",
            ))
        return violations


    # ── 需求电流标准表（2026-10-10 标准表批）──
    # 家族电流表：料号前缀 startswith 匹配（与 _DCDC_PN_PREFIXES 同口径）。
    # 旧实现拿 desc 子串（"STM32"/"ARM"/"单片机"）命中即 +0.3A，且 ESP32 行
    # 同中 MCU 与 WiFi 两个分支双计 0.5A——改为每行只按最高一档家族计一次。
    # 电流值取各家族数据手册峰值/典型供电能力（电源设计口径，不是平均功耗）。
    _IC_FAMILY_CURRENT_A: tuple[tuple[tuple[str, ...], float], ...] = (
        (("ESP32", "ESP32S2", "ESP32S3", "ESP32C3"), 0.50),   # WiFi/BT 发射峰值
        (("ESP8266",), 0.35),
        (("STM32", "GD32", "CH32", "AT32", "PY32", "APM32"), 0.15),
        (("RP2040",), 0.10),
        (("ATMEGA", "ATTINY"), 0.03),
        # FPGA/CPLD：Altera Cyclone / Xilinx Spartan·Zynq / Lattice
        (("EP1C", "EP2C", "EP3C", "EP4C", "EP4CE", "XC6S", "XC7A",
          "XC7Z", "LCMXO", "ECP5", "ICE40"), 0.30),
        (("NRF24",), 0.02),
        (("CC25",), 0.03),
        (("HC-05", "HC-06", "JDY-31", "BK3231"), 0.04),       # 经典蓝牙串口模块
        (("RTL8201", "LAN8720", "DP83848"), 0.05),            # 以太网 PHY
    )

    # 电机驱动：电流路由到 VM/VBAT/MOTOR 动力网（_estimate_net_current），
    # 不摊进主电源——旧实现把它加进总电流，VCC 走线被电机电流撑大。
    _MOTOR_DRIVER_CURRENT_A: tuple[tuple[tuple[str, ...], float], ...] = (
        (("L298",), 2.0),
        (("L293",), 1.0),
        (("DRV8833", "DRV8701", "DRV8871"), 1.5),
        (("A4988", "A4950"), 2.0),
        (("TB6612",), 1.2),
        (("ULN2003",), 0.5),
    )
    _MOTOR_DESC_FALLBACK_A = 1.5   # 描述含「电机/马达」的驱动行（无料号可依）兜底值

    # 稳压器输出能力表：整板能取用的电流被稳压器封顶，
    # 主电流取 min(负载估算, Σ稳压能力)。
    _REGULATOR_CAPACITY_A: tuple[tuple[tuple[str, ...], float], ...] = (
        (("AMS1117", "LM1117", "LD1117"), 1.0),
        (("RT9013",), 0.5),
        (("ME6211",), 0.5),
        (("XC6206",), 0.2),
        (("HT7333", "HT75"), 0.25),
        (("LM7805", "L7805", "LM78M", "L78M"), 1.0),
        (("LM2596",), 3.0),
        (("MP1584",), 3.0),
        (("MP2315",), 3.0),
        (("MP2359",), 2.0),
        (("XL1509",), 2.0),
        (("SY8088",), 2.0),
        (("TPS5430",), 3.0),
    )

    @classmethod
    def _pn_family_current(cls, bom_items) -> tuple[float, float]:
        """按料号前缀表估电流，返回 (主电源电流, 电机驱动电流)。每行只计一档。"""
        main = motor = 0.0
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            if not pn:
                continue
            for prefixes, amps in cls._MOTOR_DRIVER_CURRENT_A:
                if pn.startswith(prefixes):
                    motor += amps
                    break
            else:
                for prefixes, amps in cls._IC_FAMILY_CURRENT_A:
                    if pn.startswith(prefixes):
                        main += amps
                        break
                else:
                    if _kw_hit(_row_text(item), ("电机", "马达", "motor driver")):
                        motor += cls._MOTOR_DESC_FALLBACK_A
        return main, motor

    @classmethod
    def _regulator_capacity_sum(cls, bom_items) -> float:
        """BOM 内已知稳压器输出能力之和 (A)；无已知稳压器返回 0（不封顶）。"""
        cap = 0.0
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            if not pn:
                continue
            for prefixes, amps in cls._REGULATOR_CAPACITY_A:
                if pn.startswith(prefixes):
                    cap += amps
                    break
        return cap

    def _estimate_power_current(self, bom_items) -> float:
        """从 BOM 估算主电源电流 (A)。

        2026-10-10 标准表批：
        - 家族电流用料号前缀表（替换「desc 含 ARM/单片机」子串，消除 ESP32
          行 MCU+WiFi 双计）；
        - 电机驱动电流不摊进主电源（路由见 _estimate_net_current）；
        - 有已知稳压器时取 min(负载估算, Σ稳压能力)——稳压器输出封顶了
          整板可取用的电流，电源走线按封顶值设计即可。
        """
        load, _motor = self._pn_family_current(bom_items)
        # LED 装饰灯珠链：驱动电流与灯珠数量强相关，按行保守估 0.5A（同旧值）
        for item in bom_items:
            if _kw_hit(_row_text(item), ("led 驱动", "ws2812", "sk6812")):
                load += 0.5
        total = max(0.5, load)   # 主控静态/传感器兜底 0.5A
        reg_cap = self._regulator_capacity_sum(bom_items)
        if reg_cap > 0:
            total = min(total, reg_cap)
        return round(total, 2)

    def _estimate_motor_current(self, bom_items) -> float:
        """电机驱动电流合计 (A)，0 表示 BOM 无电机驱动。"""
        _main, motor = self._pn_family_current(bom_items)
        return motor

    def _estimate_net_current(self, net_name: str, total_current: float,
                              motor_current: float = 0.0) -> float:
        """按网络名分配电流。

        2026-10-10 标准表批：电机驱动电流不再摊进主电源总电流，而是路由到
        VM/V motor 动力网（VBAT/+12V 既给动力也可给主控，取两者较大值）。
        """
        name = net_name.upper()
        if any(kw in name for kw in ("VCC", "VDD", "+5V", "+3.3V", "+3V3", "VIN")):
            return total_current * 0.6  # 主电源承担 60%
        if any(kw in name for kw in ("VMOTOR", "VM", "MOTOR")):
            return max(total_current * 0.4, 1.0, motor_current)
        if any(kw in name for kw in ("POWER", "VBAT", "+12V")):
            return max(total_current * 0.4, 1.0, motor_current)
        return total_current * 0.3


    def _check_thermal_relief(self, bom_items, positions, netlist):
        """热焊盘：大功率器件应有散热铜皮/散热过孔方案"""
        violations = []
        pwr_kw = ["LDO", "DC-DC", "BUCK", "BOOST", "MOSFET", "IGBT", "功率", "电源", "regulator", "REG", "driver"]
        pwr_pkgs = {"TO-220", "TO-263", "D2PAK", "DFN", "QFN", "SOT-223", "SO-8EP", "TSSOP-EP"}
        hp = []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if any(kw.lower() in desc for kw in pwr_kw):
                ref = getattr(item, "reference", "").split(",")[0].strip()
                pkg = (getattr(item, "package", "") or "").upper()
                if pkg in pwr_pkgs or any(p in pkg for p in ["PAD", "EP", "EXPOSED"]):
                    hp.append(f"{ref}({pkg})")
        if hp:
            violations.append(RuleViolation(
                rule_name="热焊盘检查", description=f"大功率器件需确认散热方案: {', '.join(hp[:5])}",
                severity=RuleSeverity.WARNING,
                suggestion="带散热焊盘的器件需 PCB 设计散热铜皮+过孔阵列传导热量至内层/底层铜皮",
                theory="Tj=Ta+Pd×θja。无散热 θja≈100°C/W——0.5W→ΔT=50°C。散热焊盘将 θja 降至 20~40°C/W。一般 1W 功耗需≥500mm² 散热铜皮(1oz)。"))
        return violations


    def _check_switching_regulator_layout(self, bom_items, positions, netlist):
        """开关电源布局：开关电源应输入回路面积最小化"""
        violations = []
        # 2026-10-06 修正：原判据含裸 "MP"/"XL"/"SY"/"MT"/"RT" 前缀 + desc 子串双路径，
        # MPU6500 / XL-1608 / RTL8201 被当成 DC-DC。与 _check_dcdc_feedback_network
        # 同口径（_is_dcdc_part），只对真正的开关稳压器报布局建议。
        for item in bom_items:
            if not _is_dcdc_part(item):
                continue
            found_dcdc = True
            ref = getattr(item, "reference", "").split(",")[0].strip()
            violations.append(RuleViolation(
                rule_name="开关电源布局检查",
                description=f"DC-DC {ref} 建议优化输入回路布局以降低 EMI",
                severity=RuleSeverity.INFO, location=ref,
                suggestion="Buck: Cin→SW→L→Cout 的 di/dt 回路面积最小化。输入电容紧靠 IC VIN/GND 引脚。SW 节点铜皮面积最小,避免成为天线。",
                theory="Buck 的开关回路(VIN→HS MOSFET→SW→L→Cout→GND→VIN)承载高频脉冲电流,其环路面积与 EMI 强度成正比。SW 节点电压在 0 和 VIN 间高速切换(dv/dt≈数 V/ns),是 PCB 最强 dV/dt 源。",
            ))
            break
        if not violations:
            return []
        return violations


    def _check_antenna_keepout(self, bom_items, positions, netlist):
        """天线净空区：无线模块天线周围应有净空区"""
        violations = []
        # 2026-10-09 抽查修正：裸 "rf" 子串命中 IRFZ44N/IRF9540（MOSFET 料号内嵌）。
        # 描述词走 _kw_hit 词边界（esp32 等长词仍可子串命中「立创·ESP32S3R8N8」
        # 这类开发板描述）；模块家族走料号前缀（NRF24L01 这类带数字后缀的
        # 词边界会漏，前缀不漏；与 _DCDC_PN_PREFIXES 同口径）。
        wireless_desc_kw = ("蓝牙", "wifi", "ble", "zigbee", "lora", "nfc", "rf",
                            "无线", "esp32", "esp8266", "cc25", "hc-05", "hc-06")
        wireless_pn_prefixes = ("ESP32", "ESP8266", "NRF", "CC25")
        for item in bom_items:
            desc = _row_text(item)
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            if _kw_hit(desc, wireless_desc_kw) or \
               pn.startswith(wireless_pn_prefixes):
                ref = getattr(item, "reference", "").split(",")[0].strip()
                violations.append(RuleViolation(
                    rule_name="天线净空区检查",
                    description=f"无线模块 {ref} 天线周围需净空区",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion="天线周围 ≥5mm 净空(无铜皮、无元件、无走线)。板载天线置于 PCB 边沿,远离金属外壳。天线下方所有层挖空。",
                    theory="PCB 铜皮在天线近场区改变天线阻抗和辐射方向图→S11↑、效率↓、通信距离大幅缩短。I-PEX/IPEX 连接器到天线的微带线需 50Ω 阻抗控制,净空保证阻抗连续性。",
                ))
        return violations


    def _check_component_height_zoning(self, bom_items, positions, netlist):
        """元件高度分区：高/矮元件应分区布局，避免高元件遮挡矮元件"""
        violations = []
        tall_pkgs = {"DIP", "SIP", "TO-220", "TO-247", "电解电容", "大电解", "散热器", "继电器",
                     "RJ45", "USB-A", "DB9", "HDMI", "排针", "接线端子", "变压器", "电感"}
        tall_refs, short_refs = [], []
        for item in bom_items:
            pkg = (getattr(item, "package", "") or "").upper()
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".upper()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            is_tall = any(kw.upper() in pkg for kw in tall_pkgs) or \
                      any(kw.upper() in desc for kw in tall_pkgs)
            if is_tall:
                tall_refs.append(ref)
            else:
                short_refs.append(ref)
        if len(tall_refs) >= 2 and len(short_refs) >= 5:
            violations.append(RuleViolation(
                rule_name="元件高度分区检查",
                description=f"高元件({len(tall_refs)}个)与矮元件({len(short_refs)}个)混合布局",
                severity=RuleSeverity.INFO,
                suggestion="高元件(>10mm)置于PCB无遮挡区域或背面。同面布局时矮元件靠近PCB边沿,高元件在中心。",
                theory="波峰焊时高元件会产生阴影效应→后方焊点虚焊。同时装配后矮元件难以目检和维护。IPC-A-610 要求人工检查视线无遮挡。",
            ))
        return violations


    def _check_debug_port_accessibility(self, bom_items, positions, netlist):
        """调试接口可访问性：SWD/JTAG/UART 调试接口应便于连接"""
        violations = []
        debug_kw = ["SWD", "JTAG", "SWCLK", "SWDIO", "TCK", "TMS", "TDO", "TDI",
                   "UART", "串口", "TTL", "CH340", "CP210", "FT232", "ST-LINK"]
        has_debug = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in debug_kw)
            for i in bom_items
        )
        if not has_debug:
            return violations
        # 检查是否有调试排针/连接器
        conn_kw = ["排针", "HEADER", "排母", "插座", "connector", "端子"]
        has_conn = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in conn_kw)
            for i in bom_items
        )
        violations.append(RuleViolation(
            rule_name="调试接口检查",
            description="检测到调试接口器件，请确认调试排针位置便于连接" if has_conn else "检测到调试接口器件但缺少调试排针",
            severity=RuleSeverity.INFO if has_conn else RuleSeverity.WARNING,
            suggestion="SWD 接口: 3.3V/GND/SWDIO/SWCLK 四针排针(2.54mm间距)，置于 PCB 边沿。加丝印标注引脚功能。UART 串口: TX/RX/GND 三针。",
            theory="调试接口在研发阶段使用频率极高——难连接的调试口严重降低开发效率。量产可保留测试点但不焊接排针以节省成本。",
        ))
        return violations


    def _check_decoupling_cap_per_pin(self, bom_items, positions, netlist):
        """多电源引脚去耦：每个 VDD/VCC 引脚应有独立的去耦电容"""
        violations = []
        mcu_kw = ["MCU", "STM32", "ESP32", "FPGA", "ARM", "单片机", "CPU"]
        found_mcu = None
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if any(kw.lower() in desc for kw in mcu_kw):
                found_mcu = item
                break
        if not found_mcu:
            return violations
        # 根据封装估计引脚数
        pkg = (getattr(found_mcu, "package", "") or "").upper()
        pkg_pin_count = {"LQFP-48": 48, "LQFP-64": 64, "LQFP-100": 100, "LQFP-144": 144,
                         "TQFP-32": 32, "TQFP-48": 48, "QFN-32": 32, "QFN-48": 48, "BGA-256": 256}
        pin_count = 0
        for p, n in pkg_pin_count.items():
            if p in pkg:
                pin_count = n
                break
        # 统计总电容数量（2026-10-09 抽查修正：「描述含电容」在真实 BOM 上恒假
        # → 有去耦的板也报不足。改位号前缀 C 计数，并按位号数量而非行数——
        # 真实 BOM 一行常含多个位号）。
        cap_count = sum(_component_count(i) for i in bom_items if _is_cap_row(i))
        # 规则：每 16 个引脚至少 1 个 0.1μF 电容
        if pin_count > 0 and cap_count < pin_count / 20:
            ref = getattr(found_mcu, "reference", "").split(",")[0].strip()
            violations.append(RuleViolation(
                rule_name="多电源引脚去耦检查",
                description=f"主控 {ref}({pkg},{pin_count}引脚) 电容数量({cap_count})可能不足",
                severity=RuleSeverity.WARNING, location=ref,
                suggestion=f"每个 VDD/VCC 引脚就近放置 0.1μF(100nF)去耦电容。大封装 IC({pin_count}引脚)建议≥{pin_count//10}个。",
                theory="现代 IC 内部多电源域(核心/IO/模拟/PLL),每个 VDD 引脚的 di/dt 不尽相同。独立的去耦电容针对各域供电→降低接地反弹。",
            ))
        return violations


    def _check_unconnected_pins(self, bom_items, positions, netlist):
        """未连接引脚：IC 引脚应全部连接（至少连到某网络或标记NC）"""
        if not netlist or not bom_items: return []
        violations = []
        pkg_pins = {"SOP-8": 8, "SOP-16": 16, "TSSOP-20": 20, "QFN-32": 32,
                    "QFN-48": 48, "LQFP-48": 48, "LQFP-64": 64, "LQFP-100": 100}
        # 引脚在网表里写作 "U1.12"：按「位号.」前缀数这个器件真正的引脚数，
        # 而不是数「有多少条网络提到过这个位号」——旧写法里 values() 是引脚列表、
        # getattr(list, "pins") 取不到东西，connected 恒为 0，等于「有 IC 就报」。
        pin_lists = [self._net_pins(v) for v in netlist.values()]
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if not ref:
                continue
            pkg = (getattr(item, "package", "") or "").upper()
            est_pins = 0
            for k, v in pkg_pins.items():
                if k in pkg:
                    est_pins = v
                    break
            if est_pins < 16:
                continue
            prefix = ref + "."
            connected = sum(1 for pins in pin_lists for p in pins
                            if p == ref or p.startswith(prefix))
            if connected < est_pins * 0.6:
                violations.append(RuleViolation(
                    rule_name="未连接引脚检查",
                    description=f"IC {ref}({pkg}) 仅 {connected}/{est_pins} 个引脚出现在网表中，可能大量引脚未连接",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion="确认 NC(No Connect)引脚已标记，其余引脚至少上拉/下拉到确定电平。",
                    theory="CMOS 输入悬空→电压由漏电流决定→处于亚稳态→振荡、功耗增大、闩锁。每个输入引脚必须有确定的 DC 路径到 VDD 或 GND。",
                ))
        return violations


    def _check_polarity_orientation(self, bom_items, positions, netlist):
        """极性元件方向：电解电容/二极管/LED 等极性元件应有统一方向标记"""
        polar_kw = {"电解", "electrolytic", "钽电容", "tantalum", "二极管", "diode",
                    "LED", "发光", "铝电解", "铝电容"}
        polar_count = sum(1 for i in bom_items
                         if any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                                for kw in polar_kw))
        if polar_count >= 3:
            return [RuleViolation(
                rule_name="极性元件方向检查",
                description=f"BOM 含 {polar_count} 个极性元件，建议丝印标注极性方向和统一朝向",
                severity=RuleSeverity.INFO,
                suggestion="电解电容/二极管/Tantalum 丝印标注正极(+)标记。同一类型极性元件朝向统一(便于人工目检和自动插件)。",
                theory="极性反接→电解电容反向击穿(短路/爆炸)、二极管反向击穿、LED不亮。SMT 极性标记需在 IPC-7351 指定的丝印层。",
            )]
        return []


    def _check_power_loop_area(self, bom_items, positions, netlist):
        """功率回路面积：开关电源的 di/dt 回路应面积最小化"""
        if not positions or not bom_items: return []
        # 2026-10-06 修正：原判据拿裸 "MP"/"XL"/"SY" 等两字母词对料号做子串匹配
        # （"MP" in "CL10A226MP8NUNE" 也中），MPU6500/MLCC 全被当成开关电源。
        # 统一走 _is_dcdc_part：命中明确稳压器系列前缀或完整关键词才算。
        # 本规则属 detect 类（不在 ADVISE_RULES），误报直接计入抽查精确率。
        has_dcdc = any(_is_dcdc_part(i) for i in bom_items)
        if has_dcdc:
            return [RuleViolation(
                rule_name="功率回路面积检查",
                description="检测到开关电源器件，输入电容→开关→电感→输出电容的 di/dt 回路需最小化",
                severity=RuleSeverity.WARNING,
                suggestion="Buck 的 Cin-SW-L-Cout 回路面积最小化。输入电容紧靠 VIN/GND 引脚。SW 节点铜皮面积最小(避免天线效应)。",
                theory="功率回路 di/dt 可达数A/ns。环路面积与 EMI 辐射强度成正比。SW 节点 dV/dt 达数V/ns 是 PCB 最强 EMI 源。CISPR 22 Class B 要求传导发射在150kHz-30MHz 低于限值。",
            )]
        return []


    # 控制信号网络名：词段级匹配（^/_ 限定左侧、$/_/数字 限定右侧）——
    # "EN" 不再命中 TOKEN/LENGTH 这类内嵌，"NRST"/"BOOT0"/"RST_N" 正常命中
    _CONTROL_NET_RE = re.compile(
        r"(?:^|_)(NR?ST|RESET|EN(?:ABLE)?|BOOT\d*|INT|NMI|CONFIG)(?:$|_|\d)", re.IGNORECASE)

    def _check_pullup_pulldown(self, bom_items, positions, netlist):
        """上拉/下拉电阻：关键信号(RST/EN/BOOT/INT)应有明确上下拉"""
        control_net = next(
            (name for name in (netlist or {}) if self._CONTROL_NET_RE.search(str(name))),
            None)
        # 2026-10-09 抽查修正：上拉电阻识别从「描述含电阻」改为位号前缀 R
        # （同 _check_i2c_pullups：描述是参数文本或为空，子串判据双向失效）。
        has_pull_r = any(
            _is_resistor_row(i)
            and any(v in (getattr(i, "value", "") or "").upper().replace(" ", "")
                    for v in ["1K", "4.7K", "10K", "47K", "100K", "4K7"])
            for i in bom_items
        )
        if control_net and not has_pull_r:
            return [RuleViolation(
                rule_name="上下拉电阻检查",
                description=f"控制信号网络 [{control_net}] 可能缺少上拉/下拉电阻",
                severity=RuleSeverity.WARNING, location=control_net,
                suggestion="RST/EN/BOOT 等控制引脚通过 10kΩ 上拉或下拉到确定电平。悬空=不确定行为。",
                theory="CMOS 输入阻抗极高(>10MΩ)，微小漏电流即可改变引脚电平→随机复位/误触发。上拉/下拉提供确定的 DC 偏置。",
            )]
        return []


    def _check_inductor_saturation_margin(self, bom_items, positions, netlist):
        """电感饱和电流：功率电感额定电流应有≥30%裕量"""
        inductor_kw = ["电感", "inductor", "μH", "uH"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} {getattr(item, 'value', '')}".lower()
            if any(kw.lower() in desc for kw in inductor_kw):
                ref = getattr(item, "reference", "").split(",")[0].strip()
                return [RuleViolation(
                    rule_name="电感饱和电流检查",
                    description=f"功率电感 {ref} 建议验证额定电流 ≥1.3× Ipeak",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion="Buck 电感 Ipeak = Iout + ΔIL/2。Isat 需 ≥1.3× Ipeak 防饱和。饱和后 L↓→ΔIL↑→磁芯损耗↑→温升↑。",
                    theory="铁氧体电感在电流超过 Isat 时磁导率骤降，感值可降至标称的 10~30%→纹波电流剧增→输出纹波↑、EMI↑。屏蔽电感 EMI 优于非屏蔽。",
                )]
        return []


    def _check_cap_temperature_coefficient(self, bom_items, positions, netlist):
        """电容温度系数：关键电路应选用 NP0/C0G 而非 X7R/X5R"""
        cap_count = 0
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if any(kw in desc for kw in ["电容", "capacitor"]):
                cap_count += 1
        if cap_count >= 5:
            return [RuleViolation(
                rule_name="电容温度系数检查",
                description=f"BOM 含 {cap_count} 个电容，振荡/滤波/定时电路应选用 NP0/C0G(温漂<30ppm/°C)",
                severity=RuleSeverity.INFO,
                suggestion="晶振负载电容、RC 定时电路、ADC 采样保持电容选用 NP0/C0G。X7R 温漂 ±15%+DC Bias 效应。",
                theory="X7R 的 EIA 编码: -55~+125°C, ±15%。实际 DC Bias 下有效容量可降至标称 20~50%。NP0/C0G 几乎无 DC Bias 效应和温漂，但容积比低。",
            )]
        return []


    def _check_opto_isolation_creepage(self, bom_items, positions, netlist):
        """光耦隔离间距：隔离式光耦初次级间应有≥6mm爬电距离"""
        opto_kw = ["光耦", "optocoupler", "PC817", "TLP", "6N137", "HCPL", "EL817"]
        has_opto = any(any(kw.upper() in (getattr(i, "part_number", "") or "").upper()
                           for kw in opto_kw) for i in bom_items)
        if has_opto and positions:
            return [RuleViolation(
                rule_name="光耦隔离间距检查",
                description="检测到光耦元件，隔离式光耦初次级之间需保证≥6mm爬电距离",
                severity=RuleSeverity.WARNING,
                suggestion="光耦下方 PCB 挖空(隔离槽)保证爬电距离≥6mm(基本绝缘)或≥8mm(加强绝缘)。初次级走线分区分层。",
                theory="IEC 60950-1/62368-1 对隔离距离有严格要求。爬电距离沿绝缘表面的最短路径，受污染等级和 CTI 值影响。隔离槽(宽度≥1mm)是增大爬电距离的经济方法。",
            )]
        return []


    def _check_bga_fanout(self, bom_items, positions, netlist):
        """BGA 扇出检查"""
        for item in bom_items:
            pkg = (getattr(item, "package", "") or "").upper()
            if "BGA" in pkg:
                ref = getattr(item, "reference", "").split(",")[0].strip()
                return [RuleViolation(
                    rule_name="BGA 扇出检查",
                    description=f"BGA 封装 {ref} 需要扇出设计——确认过孔尺寸/间距满足工艺能力",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion="BGA 扇出: 焊盘→微孔(Φ0.2mm)→内层走线。0.8mm pitch BGA 用 0.25/0.5mm 过孔。1.0mm pitch 可用 0.3/0.6mm。",
                    theory="BGA 焊球位于元件底部无法直接走线→必须用过孔扇出到其他层。过孔必须塞孔或覆盖以防止焊接时吸锡。IPC-7095 规定了 BGA 设计标准。",
                )]
        return []


    def _check_mixed_voltage_isolation(self, bom_items, positions, netlist):
        """多电压域隔离: 不同电压域应有清晰隔离"""
        voltages = set()
        for item in bom_items:
            val = (getattr(item, "value", "") or "").upper().replace(" ", "")
            pn = (getattr(item, "part_number", "") or "").upper()
            for v_str in ["3.3V", "5V", "1.8V", "12V", "24V", "3V3", "1V8"]:
                if v_str in val or v_str in pn:
                    voltages.add(v_str)
        if len(voltages) >= 3:
            return [RuleViolation(
                rule_name="多电压域隔离检查",
                description=f"BOM 涉及 {len(voltages)} 个电压域({', '.join(sorted(voltages))})，需确保域间隔离",
                severity=RuleSeverity.INFO,
                suggestion="不同电压域分区布局，电源走线不交叉。电压域切换处(如电平转换器)集中放置。",
                theory="多电压系统常见的错误：3.3V 信号误接入 1.8V 域→器件过压损坏。PCB 布局时电压域分区→降低误接风险和串扰。",
            )]
        return []


    def _check_pdn_target_impedance(self, bom_items, positions, netlist):
        """PDN 目标阻抗 — 检查电源分配网络是否满足目标阻抗

        2026-10-09 噪声清扫：板面积原硬编码 5000mm²，现取 board_outline 实测
        宽×高（无板框数据则跳过——没有几何就没法算平面电容/IR 压降）；电压与
        电流是推断值，文案标注「估算」。
        2026-10-10 标准表批：电源-地平面间距按铜层数取叠层预设（4 层 core
        0.71mm；2 层板无平面对，平面电容如实按不适用处理，不再默认 0.2mm
        硬算）；IR 压降的平面电阻改方阻公式（calculator 内 1oz≈2 方≈1mΩ）。
        """
        from src.pcb.calculator import (
            analyze_pdn, pdn_target_impedance, stackup_for_layers,
            infer_copper_layer_count,
        )

        pcb = self._pcb_data
        bo = (pcb.board_outline or {}) if pcb else {}
        area = (bo.get("width_mm") or 0) * (bo.get("height_mm") or 0)
        if area <= 0:
            return []
        violations = []
        # 从 BOM 推断电压和电流
        voltage = 3.3
        current = self._estimate_power_current(bom_items)
        # 检测实际电压
        for item in bom_items:
            desc = f"{getattr(item, 'value', '')} {getattr(item, 'description', '')}".upper()
            if "5V" in desc or "5.0V" in desc:
                voltage = 5.0
                break

        n_layers = infer_copper_layer_count(pcb) if pcb else 2
        stackup = stackup_for_layers(n_layers)
        plane_gap = stackup.plane_gap_mm
        pdn = analyze_pdn(voltage, current, board_area_mm2=area,
                          layers_between_plane=plane_gap, ripple_percent=5.0)

        if plane_gap:
            plane_note = (f"平面电容 {pdn.plane_capacitance_f*1e9:.2f}nF"
                          f"（电源-地平面间距按 {n_layers} 层板典型值 {plane_gap}mm）")
        else:
            plane_note = f"{n_layers} 层板无电源-地平面对，平面电容不适用"

        violations.append(RuleViolation(
            rule_name="PDN 目标阻抗分析",
            description=(
                f"{voltage}V/{current:.2f}A 电源(估算，板面积 {area:.0f}mm²): "
                f"目标阻抗 Z_target={pdn.target_impedance_ohm*1000:.0f}mΩ，"
                f"{plane_note}，"
                f"建议 ≥{pdn.decoupling_count} 个去耦电容，IR压降≈{pdn.voltage_drop_mv:.1f}mV"
            ),
            severity=RuleSeverity.WARNING if pdn.decoupling_count > 3 else RuleSeverity.INFO,
            suggestion=(
                f"推荐电容组合: {', '.join(f'{c*1e6:.0f}µF' if c>=1e-6 else f'{c*1e9:.0f}nF' for c in pdn.recommended_caps[:4])}。"
                "各频段去耦: 100µF(≤10kHz) + 10µF(≤1MHz) + 100nF(1-100MHz) + 10nF(≥100MHz)。"
                + ("" if plane_gap else " 2 层板无平面电容可用，低频去耦更依赖 Bulk 电解电容。")
            ),
            theory="PDN 目标阻抗 Z_target = (Vdd × ripple%) / I_transient。全频段内 Z_PDN < Z_target 才能保证电源纹波在允许范围内。"
                   "多层陶瓷电容(MLCC)并联降低等效 ESL，扩展有效去耦频率范围。"
                   + ("" if plane_gap else " 电源-地平面对的分布电容是 PDN 低频段主力，2 层板缺失后 bulk 电容 ESR 承担低频阻尼。"),
        ))
        return violations

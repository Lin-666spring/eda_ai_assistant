"""
PCB 设计规则检查模块 — 21条测控电路专用规则
每条规则包含: 描述、严重等级、位置、修复建议、理论解释
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..constants import PCB
from ..pcb.models import PCBData

logger = logging.getLogger(__name__)


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


class DesignRuleChecker:
    """PCB 设计规则检查器 — 测控电路专用规则（21条）"""

    # ═══ BOM-only rules ═══

    def _check_decoupling_caps(self, bom_items, positions, netlist):
        """去耦电容检查：每个 IC 应有 0.1μF 去耦电容"""
        violations = []
        passive_kw = ["电阻", "电容", "电感", "Resistor", "Capacitor", "Inductor"]
        ics, caps = [], []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if any(kw.lower() in desc for kw in passive_kw):
                if "电容" in desc or "capacitor" in desc:
                    caps.append(item)
            else:
                ics.append(item)
        for ic in ics:
            ic_ref = getattr(ic, "reference", "?")
            has = any(getattr(c, "value", "").replace(" ", "").upper() in
                      {"0.1UF", "100NF", "0.1ΜF", "104"} for c in caps)
            if not has:
                violations.append(RuleViolation(
                    rule_name="去耦电容检查",
                    description=f"IC {ic_ref} 附近可能缺少去耦电容",
                    severity=RuleSeverity.WARNING,
                    location=ic_ref,
                    suggestion="在电源引脚附近放置 0.1μF (100nF) 陶瓷电容",
                    theory="IC 内部晶体管开关产生 di/dt 瞬态电流，PCB 走线寄生电感(~5-10nH/cm)阻碍电流响应，造成 VDD 跌落(V=L×di/dt)。去耦电容提供就近电荷池，距引脚 ≤10mm。",
                ))
        return violations

    def _check_crystal_load_caps(self, bom_items, positions, netlist):
        """晶振负载电容检查：每个晶振应配备 2 个匹配负载电容"""
        violations = []
        crystal_kw = ["晶振", "crystal", "XTAL", "OSC", "振荡"]
        cap_kw = ["电容", "capacitor", "pF", "pf", "PF"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} {getattr(item, 'value', '')}".lower()
            if not any(kw.lower() in desc for kw in crystal_kw):
                continue
            ref = getattr(item, "reference", "?")
            prefix = "".join(c for c in ref if c.isalpha())
            nearby = [c for c in bom_items
                      if "".join(ch for ch in getattr(c, "reference", "") if ch.isalpha()) == prefix
                      and any(kw.lower() in (f"{getattr(c, 'part_number', '')} {getattr(c, 'description', '')} {getattr(c, 'value', '')}").lower() for kw in cap_kw)]
            if len(nearby) < 2:
                violations.append(RuleViolation(
                    rule_name="晶振负载电容检查",
                    description=f"晶振 {ref} 负载电容不足({len(nearby)}/2)",
                    severity=RuleSeverity.WARNING,
                    location=ref,
                    suggestion="晶振需 2 个匹配负载电容(通常 12~22pF)，参见数据手册",
                    theory="皮尔斯振荡器是最常用 MCU 晶振电路。CL=(CL1×CL2)/(CL1+CL2)+Cstray，Cstray 包含 PCB 寄生和 MCU 引脚电容(~3-7pF)。CL 偏差过大致起振失败或频率偏移。",
                ))
        return violations

    def _check_crystal_frequency(self, bom_items, positions, netlist):
        """晶振频率匹配：不同频率晶振应匹配对应负载电容值"""
        violations = []
        crystal_map = {"32.768": ("12.5pF", "15pF"), "8M": ("18pF", "22pF"),
                       "12M": ("15pF", "22pF"), "16M": ("12pF", "18pF"), "25M": ("12pF", "18pF")}
        for item in bom_items:
            val = getattr(item, "value", "") or ""
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}"
            if not any(kw in desc.lower() for kw in ["晶振", "crystal", "xtal"]):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            freq = val.replace(" ", "").upper()
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
        """I2C 上拉电阻：SDA/SCL 需上拉电阻(典型 4.7kΩ)"""
        violations = []
        i2c_kw = ["I2C", "I²C", "SDA", "SCL", "TWI", "IIC"]
        pullup_vals = {"4.7k", "4K7", "4700", "10k", "10K", "10000", "2.2k", "2K2", "3.3k", "3K3"}
        has_i2c = any(kw.lower() in f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}".lower()
                      for i in bom_items for kw in i2c_kw)
        if not has_i2c:
            return violations
        has_pullup = any(
            any(v in getattr(i, "value", "").replace(" ", "") for v in pullup_vals)
            and any(kw in f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}".lower() for kw in ["电阻", "resistor"])
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
        bulk_uf = ["100u", "220u", "470u", "1000u", "100ΜF"]
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
        conn_kw = ["USB", "HDMI", "RJ45", "DB9", "FPC", "排针", "端子", "CONNECTOR", "connector", "HEADER", "header", "JACK", "jack"]
        esd_kw = ["TVS", "ESD", "SRV05", "USBLC6", "RCLAMP", "PESD", "SMAJ", "SMBJ", "压敏", "防静电", "保护管"]
        has_conn = any(any(kw.lower() in (getattr(i, "part_number", "") + " " + getattr(i, "description", "")).lower()
                           for kw in conn_kw) for i in bom_items)
        if not has_conn:
            return violations
        has_esd = any(any(kw.lower() in (getattr(i, "part_number", "") + " " + getattr(i, "description", "")).lower()
                          for kw in esd_kw) for i in bom_items)
        if not has_esd:
            violations.append(RuleViolation(
                rule_name="ESD 保护检查", description="存在外部连接器但未检测到 TVS/ESD 保护器件",
                severity=RuleSeverity.WARNING,
                suggestion="外露接口各信号线加装 TVS 管(如 USBLC6-2)",
                theory="HBM ESD 放电可达 ±2~15kV，峰值电流数十安培，上升时间≤1ns。TVS 利用雪崩击穿在 ns 级钳位电压。IEC 61000-4-2 规定 4 级=接触±8kV/空气±15kV。高速信号需结电容≤0.5pF。"))
        return violations

    def _check_reference_continuity(self, bom_items, positions, netlist):
        """位号连续性：同类元件位号应连续"""
        violations = []
        rc_prefixes = {"R", "C", "L", "D", "U", "Q", "J", "P"}
        prefix_map: dict[str, list[int]] = {}
        for item in bom_items:
            ref = getattr(item, "reference", "")
            if not ref: continue
            first = ref.split(",")[0].strip()
            prefix = "".join(c for c in first if c.isalpha()).upper()
            if prefix in rc_prefixes:
                nums = "".join(c for c in first if c.isdigit())
                if nums: prefix_map.setdefault(prefix, []).append(int(nums))
        for prefix, nums in prefix_map.items():
            nums.sort()
            gaps = []
            for i in range(len(nums) - 1):
                gap = nums[i + 1] - nums[i]
                if gap > 1: gaps.append(f"{prefix}{nums[i]}→{prefix}{nums[i+1]}(跳{gap-1}号)")
            if gaps:
                violations.append(RuleViolation(
                    rule_name="位号连续性检查", description=f"{prefix} 类位号不连续: {gaps[0]}{' ...' if len(gaps)>1 else ''}",
                    severity=RuleSeverity.INFO,
                    suggestion="位号不连续通常因删除元件后未重排。确认是否为预留空位。",
                    theory="规范化 BOM 中同类元件位号应连续(R1,R2,R3...)。PCB 设计工具均提供自动重排位号功能。"))
        return violations

    def _check_package_consistency(self, bom_items, positions, netlist):
        """封装一致性：同型号不同封装可能为误选"""
        violations = []
        pn_pkgs: dict[str, set] = {}
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip()
            pkg = (getattr(item, "package", "") or "").strip()
            if not pn or not pkg or pn == "N/A": continue
            pn_pkgs.setdefault(pn, set()).add(pkg)
        for pn, pkgs in pn_pkgs.items():
            if len(pkgs) > 1:
                refs = [getattr(i, "reference", "") for i in bom_items if (getattr(i, "part_number", "") or "").strip() == pn]
                violations.append(RuleViolation(
                    rule_name="封装一致性检查", description=f"型号 [{pn}] 出现多种封装: {', '.join(sorted(pkgs))}",
                    severity=RuleSeverity.WARNING, location=", ".join(refs[:5]),
                    suggestion="同型号应采用相同封装。多封装可能为采购错误或 BOM 录入疏忽。",
                    theory="同一物料号出现不同封装(如 0805 和 0603 混用)通常表示手动替换未统一，可能导致 SMT 贴片程序不匹配。IPC-7351 规定标准封装命名。"))
        return violations

    def _check_bom_value_range(self, bom_items, positions, netlist):
        """参数范围：电阻/电容值应在标准系列内"""
        violations = []
        e24_base = {10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30,
                    33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91}
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
            mant_x100 = round(mantissa * 100)
            if not any(abs(mant_x100 - e * 10) / (e * 10) < 0.10 for e in e24_base):
                violations.append(RuleViolation(
                    rule_name="参数范围检查", description=f"{ref} 参数 [{val}] 不在 E24 标准系列",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion="非标值可能需要定制或从 E48/E96 系列选择",
                    theory="标准值系列(E-series)由 IEC 60063 规定:E24 覆盖±5%(步进≈10%),E48 覆盖±2%,E96 覆盖±1%。"))
        return violations

    # ═══ PCB-data rules ═══

    def _check_signal_traces(self, bom_items, positions, netlist):
        """信号线宽度：关键信号走线应 ≥ 最小线宽"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        min_w = PCB.SIGNAL_TRACE_MIN_WIDTH_MM
        sig_traces = [t for t in pcb.traces
                      if t.width_mm > 0 and not any(kw.upper() in t.net_name.upper()
                      for kw in PCB.POWER_NET_KEYWORDS) if t.net_name]
        net_min: dict[str, float] = {}
        for t in sig_traces:
            prev = net_min.get(t.net_name, float("inf"))
            if t.width_mm < prev: net_min[t.net_name] = t.width_mm
        for name, w in net_min.items():
            if w < min_w:
                violations.append(RuleViolation(
                    rule_name="信号线宽度检查", description=f"网络 [{name}] 最小线宽 {w:.3f}mm < {min_w}mm",
                    severity=RuleSeverity.WARNING, location=name,
                    suggestion=f"线宽 {w:.3f}mm 过细，加宽至 ≥ {min_w}mm。高速信号确认阻抗匹配。",
                    theory="走线宽度由 PCB 工艺能力和信号完整性共同决定。一般厂最小 4mil(0.1mm)，低成本 6mil(0.15mm)。线宽过细→电阻↑、散热难。"))
        return violations

    def _check_power_traces(self, bom_items, positions, netlist):
        """电源线载流：电源走线需满足 IPC-2221 载流要求"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        pw_traces = [t for t in pcb.traces
                     if t.width_mm > 0 and any(kw.upper() in t.net_name.upper()
                     for kw in PCB.POWER_NET_KEYWORDS) if t.net_name]
        if not pw_traces: return violations
        k, tr, cu = PCB.IPC_K_FACTOR, PCB.IPC_TEMP_RISE, PCB.IPC_COPPER_OZ
        cu_mil = cu * 1.37
        net_min: dict[str, float] = {}
        for t in pw_traces:
            if not t.net_name: continue
            prev = net_min.get(t.net_name, float("inf"))
            if t.width_mm < prev: net_min[t.net_name] = t.width_mm
        for name, mw in net_min.items():
            I = PCB.POWER_CURRENT_DEFAULT_A
            a_mil2 = (I / (k * tr ** 0.44)) ** (1.0 / 0.725)
            req_w = round((a_mil2 / cu_mil) * 0.0254, 3)
            cur_a = (mw / 0.0254) * cu_mil
            sup_I = k * tr ** 0.44 * cur_a ** 0.725
            if mw < req_w * 0.8:
                violations.append(RuleViolation(
                    rule_name="电源线宽度检查", description=f"电源网络 [{name}] 最细走线 {mw:.3f}mm，不满足载流 {I}A 需 ≥{req_w:.3f}mm",
                    severity=RuleSeverity.ERROR, location=name,
                    suggestion=f"当前 {mw:.3f}mm 仅支持约 {sup_I:.1f}A，加宽至 ≥{req_w:.3f}mm 或增厚铜箔",
                    theory="IPC-2221: I=k×ΔT^0.44×A^0.725。k外层=0.048,ΔT=温升°C,A=截面积 mil²。1oz 铜=1.37mil，增加铜厚(2oz)或加宽走线可提升载流。"))
        return violations

    def _check_trace_acute_angles(self, bom_items, positions, netlist):
        """走线锐角：PCB 走线不应出现锐角或直角"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        for t in pcb.traces:
            if not t.net_name: continue
            if getattr(t, "has_sharp_angle", False):
                violations.append(RuleViolation(
                    rule_name="走线锐角检查", description=f"网络 [{t.net_name}] 可能存在锐角/直角走线",
                    severity=RuleSeverity.INFO, location=t.net_name,
                    suggestion="使用 45° 转角或圆弧走线",
                    theory="直角走线拐角处宽度增大(√2 倍)→局部阻抗下降、信号反射。锐角(<90°)在 PCB 蚀刻中形成「酸陷阱」(acid trap)，残留蚀刻液致长期可靠性问题。IPC 推荐 45°/圆弧。"))
        return violations

    def _check_via_density(self, bom_items, positions, netlist):
        """过孔密度：关键信号路径不应有过多的过孔"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        via_per_net: dict[str, int] = {}
        for v in (pcb.vias or []):
            net = getattr(v, "net_name", "") or getattr(v, "net", "")
            if net: via_per_net[net] = via_per_net.get(net, 0) + 1
        for net, count in via_per_net.items():
            if count >= 5:
                violations.append(RuleViolation(
                    rule_name="过孔密度检查", description=f"网络 [{net}] 过孔数量({count})偏多",
                    severity=RuleSeverity.INFO, location=net,
                    suggestion="每过孔引入 ≈0.5nH 寄生电感，高速信号路径建议 ≤2 过孔",
                    theory="过孔寄生电感≈0.5~1nH，寄生电容≈0.3~0.5pF。>50MHz 时多个过孔串联致阻抗不连续和 EMI 恶化。IPC-2221 建议关键信号过孔≤2。"))
        return violations

    def _check_diff_pair_spacing(self, bom_items, positions, netlist):
        """差分对间距：差分对应紧密耦合、等长"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        net_names = list(set(getattr(t, "net_name", "") or "" for t in pcb.traces if getattr(t, "net_name", "")))
        pairs = []
        for i, n1 in enumerate(net_names):
            for n2 in net_names[i + 1:]:
                b1, b2 = n1.rstrip("_PN+-pn"), n2.rstrip("_PN+-pn")
                if b1 == b2 and b1:
                    s1 = n1[-2:] if n1[-2:] in ("_P", "_N") else n1[-1:]
                    s2 = n2[-2:] if n2[-2:] in ("_P", "_N") else n2[-1:]
                    if s1 != s2 and n1[:-len(s1)] == n2[:-len(s2)]:
                        pairs.append((n1, n2))
                        break
        if pairs:
            violations.append(RuleViolation(
                rule_name="差分对间距检查", description=f"识别 {len(pairs)} 对疑似差分信号: {', '.join(f'{p}/{n}' for p, n in pairs[:4])}",
                severity=RuleSeverity.INFO,
                suggestion="差分对应等长(误差<5mil)、等间距、紧耦合。USB=90Ω, LVDS=100Ω。",
                theory="差分阻抗 Zdiff=2×Zodd，取决于 W/S/H/εr。USB2.0 要求 90Ω±15%，LVDS 要求 100Ω±10%。线距过大→Zdiff↑→CMRR↓；线距过小→串扰↑。"))
        return violations

    # ═══ Position-data rules ═══

    def _check_analog_digital_separation(self, bom_items, positions, netlist):
        """模数分离：模拟/数字元件应物理分区"""
        if not positions or not bom_items: return []
        violations = []
        acoords, dcoords = [], []
        for item in bom_items:
            desc = f"{getattr(item, 'description', '') or ''} {getattr(item, 'part_number', '') or ''}".lower()
            is_a = any(kw.lower() in desc for kw in PCB.ANALOG_COMPONENT_KW)
            is_d = any(kw.lower() in desc for kw in PCB.DIGITAL_COMPONENT_KW)
            ref = getattr(item, "reference", "")
            fr = ref.split(",")[0].strip() if ref else ""
            if fr and fr in positions:
                pos = positions[fr]
                x = pos.get("x", 0) if isinstance(pos, dict) else (pos[0] if isinstance(pos, (list, tuple)) else 0)
                y = pos.get("y", 0) if isinstance(pos, dict) else (pos[1] if isinstance(pos, (list, tuple)) and len(pos) > 1 else 0)
                if is_a: acoords.append((x, y, fr))
                elif is_d: dcoords.append((x, y, fr))
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

    def _check_component_edge_clearance(self, bom_items, positions, netlist):
        """板边间距：元件距 PCB 板边应 ≥3mm"""
        if not positions: return []
        violations = []
        mc = 3.0
        near = []
        for item in bom_items:
            ref = getattr(item, "reference", "")
            if ref and ref in positions:
                pos = positions[ref]
                x = pos.get("x", 0) if isinstance(pos, dict) else (pos[0] if isinstance(pos, (list, tuple)) else 0)
                y = pos.get("y", 0) if isinstance(pos, dict) else (pos[1] if isinstance(pos, (list, tuple)) and len(pos) > 1 else 0)
                if x < mc or y < mc: near.append(ref)
        if near:
            violations.append(RuleViolation(
                rule_name="板边间距检查", description=f"{len(near)} 个元件距板边 <{mc}mm: {', '.join(near[:5])}",
                severity=RuleSeverity.WARNING,
                suggestion=f"元件距板边 ≥{int(mc)}mm，高元件需更大间距",
                theory="PCB 板边在拼板分离、波峰焊夹持、机壳装配中承受最大机械应力。IPC-2222 §8.2 建议元件体距板边 ≥2.5mm，高元件≥5mm。传送边禁布区≥3mm。"))
        return violations

    def _check_decoupling_proximity(self, bom_items, positions, netlist):
        """去耦电容距离：去耦电容应靠近 IC 电源引脚"""
        if not positions: return []
        violations = []
        ics, caps = [], []
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if ref in positions:
                if any(kw in desc for kw in ["电容", "capacitor"]): caps.append((ref, positions[ref]))
                elif not any(kw in desc for kw in ["电阻", "电感", "resistor", "inductor"]): ics.append((ref, positions[ref]))
        if not ics: return violations
        md = 15.0
        far = []
        for cr, cp in caps:
            cx = cp.get("x", 0) if isinstance(cp, dict) else (cp[0] if isinstance(cp, (list, tuple)) else 0)
            cy = cp.get("y", 0) if isinstance(cp, dict) else (cp[1] if isinstance(cp, (list, tuple)) and len(cp) > 1 else 0)
            for ir, ip in ics:
                ix = ip.get("x", 0) if isinstance(ip, dict) else (ip[0] if isinstance(ip, (list, tuple)) else 0)
                iy = ip.get("y", 0) if isinstance(ip, dict) else (ip[1] if isinstance(ip, (list, tuple)) and len(ip) > 1 else 0)
                dist = ((cx - ix) ** 2 + (cy - iy) ** 2) ** 0.5
                if dist > md: far.append((cr, ir, round(dist, 1)))
        if far:
            ps = ", ".join(f"{c}/{i}({d}mm)" for c, i, d in far[:3])
            violations.append(RuleViolation(
                rule_name="去耦电容距离检查", description=f"{len(far)} 个去耦电容距 IC >{md}mm: {ps}",
                severity=RuleSeverity.WARNING,
                suggestion=f"去耦电容距 IC 电源引脚 ≤{int(md)}mm。距离每增加 1cm，退耦效果显著下降。",
                theory="PCB 走线寄生电感≈5~10nH/cm。去耦电容距 IC 每增 1cm，环路 L≈+8nH——10ns 内切换 50mA 时 Vdrop=L·di/dt=8nH×5×10⁶A/s=40mV。多层板建议电容同层距引脚≤10mm。"))
        return violations

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

    # ═══ Init + orchestration ═══

    def __init__(self):
        self._pcb_data: Optional[PCBData] = None
        self._rules = [getattr(self, name) for name in sorted(dir(self)) if name.startswith('_check_')]

    def check_all(self, bom_items, positions=None, netlist=None, pcb_data=None):
        self._pcb_data = pcb_data
        violations = []
        for rule_func in self._rules:
            try:
                result = rule_func(bom_items, positions, netlist)
                if result: violations.extend(result)
            except Exception as e:
                logger.warning(f"规则检查异常 ({rule_func.__name__}): {e}")
        logger.info(f"规则检查完成: 发现 {len(violations)} 项违规")
        return violations

    def get_report(self, violations):
        if not violations:
            return "✅ 设计规则检查通过，未发现违规项。"
        lines = ["=" * 55, "          PCB 设计规则检查报告", "=" * 55]
        for sev in (RuleSeverity.ERROR, RuleSeverity.WARNING, RuleSeverity.INFO):
            items = [v for v in violations if v.severity == sev]
            if not items: continue
            emoji = {"error": "❌", "warning": "⚠️ ", "info": "ℹ️ "}[sev.value]
            lines.append(f"\n【{sev.value.upper()}】{emoji} {len(items)} 项")
            for v in items:
                lines.append(f"  • [{v.rule_name}] {v.description}")
                if v.location: lines.append(f"    位置: {v.location}")
                if v.suggestion: lines.append(f"    建议: {v.suggestion}")
                if v.theory: lines.append(f"    理论: {v.theory}")
        lines.append("\n" + "=" * 55)
        return "\n".join(lines)


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

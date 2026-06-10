"""
PCB 设计规则检查模块 — 69条测控电路/电子设计专用规则
每条规则包含: 描述、严重等级、位置、修复建议、理论解释
覆盖: BOM(27) + PCB布线(22) + 布局(20) 三大类别
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
    """PCB 设计规则检查器 — 测控电路/电子设计专用规则（69条）"""

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

    def _check_led_current_limit(self, bom_items, positions, netlist):
        """LED 限流电阻：每个 LED 应有匹配的限流电阻"""
        violations = []
        led_kw = ["LED", "发光", "light", "指示", "照明", "灯珠"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.lower() in desc for kw in led_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            # 检查是否有任意电阻（LED 亮需限流电阻）
            has_resistor = any(
                any(kw.lower() in (f"{getattr(r, 'part_number', '')} {getattr(r, 'description', '')}").lower()
                    for kw in ["电阻", "resistor"])
                for r in bom_items if r is not item
            )
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
        pwr_in_kw = ["电源", "power", "DC-IN", "VIN", "VBUS", "PWR", "输入"]
        protection_kw = ["MOSFET", "PMOS", "NMOS", "二极管", "diode", "肖特基", "schottky",
                         "保险丝", "fuse", "PTC", "TVS", "稳压管"]
        has_pwr_in = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in pwr_in_kw) or any(kw.lower() in (getattr(i, 'part_number', '') or "").lower() for kw in ["电源", "DC"])
            for i in bom_items
        )
        if not has_pwr_in:
            return violations
        has_protection = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in protection_kw)
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
        dcdc_kw = ["DC-DC", "BUCK", "BOOST", "降压", "升压", "开关稳压", "开关电源",
                   "MP", "TPS", "LM25", "LM26", "XL", "SY", "MT"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.lower() in desc for kw in dcdc_kw):
                continue
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            # 常见 DC-DC 芯片系列
            if not any(pn.startswith(p) for p in ["MP", "TPS", "LM25", "LM26", "XL", "SY", "MT", "RT", "AP", "LMR"]):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            # 检查是否有分压电阻（DC-DC FB 需要两个电阻分压）
            resistors = [r for r in bom_items if any(
                kw.lower() in (f"{getattr(r, 'part_number', '')} {getattr(r, 'description', '')}").lower()
                for kw in ["电阻", "resistor"]) and r is not item]
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
        mosfet_kw = ["MOSFET", "MOS", "NMOS", "PMOS", "IRF", "IRL", "AO", "SI", "2N700", "BSS"]
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            desc = f"{getattr(item, 'description', '') or ''}".lower()
            if not any(kw.upper() in pn for kw in ["IRF", "IRL", "2N700", "BSS", "AO3", "AO4", "SI2", "SI4"]) and \
               not any(kw.lower() in desc for kw in mosfet_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            prefix = "".join(c for c in ref if c.isalpha() and c != 'Q')
            has_gate_r = any(
                any(kw.lower() in (f"{getattr(r, 'part_number', '')} {getattr(r, 'description', '')}").lower()
                    for kw in ["电阻", "resistor"])
                for r in bom_items if r is not item
            )
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
        opto_kw = ["光耦", "optocoupler", "opto", "PC817", "TLP", "EL817", "6N137", "HCPL", "PS", "SFH"]
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.lower() in desc for kw in opto_kw) and \
               not any(pn.startswith(p) for p in ["PC817", "TLP", "EL817", "6N137", "HCPL", "PS25", "SFH"]):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            prefix = "".join(c for c in ref if c.isalpha())
            has_input_r = any(
                "".join(c for c in getattr(r, "reference", "").split(",")[0].strip() if c.isalpha()) == prefix
                and any(kw.lower() in (f"{getattr(r, 'part_number', '')} {getattr(r, 'description', '')}").lower()
                        for kw in ["电阻", "resistor"])
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
        """运放反馈网络：运算放大器应有反馈电阻网络"""
        violations = []
        opamp_kw = ["运放", "OP", "LM358", "LM324", "TL07", "TL08", "NE553", "OPA", "MCP6", "AD8"]
        for item in bom_items:
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.upper() in pn for kw in ["LM358", "LM324", "LMV358", "TL07", "TL08", "NE553", "OPA", "MCP6", "AD8"]):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            prefix = "".join(c for c in ref if c.isalpha())
            nearby_rs = sum(1 for r in bom_items
                          if "".join(c for c in getattr(r, "reference", "").split(",")[0].strip() if c.isalpha()) == prefix
                          and any(kw.lower() in (f"{getattr(r, 'part_number', '')} {getattr(r, 'description', '')}").lower()
                                  for kw in ["电阻", "resistor"]))
            if nearby_rs < 2:
                violations.append(RuleViolation(
                    rule_name="运放反馈网络检查",
                    description=f"运放 {ref}({pn}) 可能缺少反馈电阻网络(仅{nearby_rs}个同前缀电阻)",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion="同相放大:Gain=1+Rf/Rg;反相放大:Gain=-Rf/Rin。Rf 通常取 1kΩ~100kΩ,反馈网络靠近反相输入端。",
                    theory="运放开环增益极高(≥100dB),必须通过负反馈确定闭环增益并保证稳定性。无反馈→运放工作在开环比较器模式,输出饱和至电源轨。反馈电阻热噪声(4kTR·BW)贡献输出噪声。",
                ))
        return violations

    def _check_capacitor_voltage_derating(self, bom_items, positions, netlist):
        """电容耐压降额：电容耐压应有 ≥20% 降额裕量"""
        violations = []
        # 常见电压轨
        voltage_rails = {"3.3V": 3.3, "5V": 5.0, "12V": 12.0, "24V": 24.0}
        supply_voltages = set()
        for item in bom_items:
            val = (getattr(item, "value", "") or "").upper().replace(" ", "")
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".upper()
            for rail_v, rail_num in voltage_rails.items():
                if rail_v in val or rail_v in desc or f"VOUT={rail_v}" in desc or f"VOUT {rail_v}" in desc:
                    supply_voltages.add(rail_num)
        max_voltage = max(supply_voltages) if supply_voltages else 0
        if max_voltage < 3.0:
            return violations
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '') or ''} {getattr(item, 'description', '') or ''}".lower()
            if not any(kw in desc for kw in ["电容", "capacitor", "电解", "electrolytic"]):
                continue
            val = (getattr(item, "value", "") or "").strip().upper()
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            # 尝试从 value 或 part_number 提取耐压
            voltage_match = re.search(r'(\d+)V', val + " " + pn)
            if voltage_match:
                rated_v = float(voltage_match.group(1))
                if max_voltage > 0 and rated_v < max_voltage * 1.2:
                    violations.append(RuleViolation(
                        rule_name="电容耐压降额检查",
                        description=f"电容 {ref} 耐压 {rated_v}V，系统最高电压 {max_voltage}V，裕量不足",
                        severity=RuleSeverity.WARNING, location=ref,
                        suggestion=f"耐压至少 ≥{max_voltage*1.2:.0f}V。陶瓷电容 DC Bias 效应下有效容量显著下降,建议 ≥2× 额定电压。",
                        theory="MLCC X7R/X5R 在 DC 偏压下有效容量可降至标称的 20~50%。电解电容耐压 ≥1.2×Vpeak 以防浪涌击穿。降额不足致电容寿命指数衰减(Arrhenius 定律—温度每升 10°C 寿命减半)。",
                    ))
        return violations

    def _check_resistor_power_rating(self, bom_items, positions, netlist):
        """电阻功率降额：功率电阻应有足够功率裕量"""
        violations = []
        pwr_r_kw = ["功率电阻", "shunt", "采样", "检流", "限流", "current sense", "功率"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} {getattr(item, 'value', '')}".lower()
            if not any(kw.lower() in desc for kw in pwr_r_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
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
        battery_kw = ["电池", "battery", "BAT", "锂电池", "锂电", "Li-ion", "Li-Po"]
        has_battery = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in battery_kw)
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
        pwr_kw = ["电源", "power", "VIN", "VBUS", "DC-IN", "PWR"]
        emi_kw = ["共模", "common mode", "CMC", "EMI", "滤波器", "filter", "扼流圈", "choke",
                  "X电容", "Y电容", "X2", "Y2"]
        has_pwr_in = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in pwr_kw)
            for i in bom_items
        )
        if not has_pwr_in:
            return violations
        has_emi = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in emi_kw)
            for i in bom_items
        )
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
        analog_kw = ["运放", "OP", "ADC", "DAC", "模拟", "analog", "传感器", "sensor",
                     "LM358", "LM324", "OPA", "MCP6", "TL07", "AD8", "ADS"]
        bead_kw = ["磁珠", "ferrite", "bead", "FB", "BLM", "MPZ", "FBM", "MMZ"]
        digital_kw = ["MCU", "STM32", "ESP32", "FPGA", "ARM", "单片机", "数字", "digital"]
        has_digital = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in digital_kw)
            for i in bom_items
        )
        has_analog = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in analog_kw)
            for i in bom_items
        )
        if not (has_digital and has_analog):
            return violations
        has_bead = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in bead_kw)
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

    def _check_diff_pair_length(self, bom_items, positions, netlist):
        """差分对等长：差分对两条走线长度应匹配(误差<5mil)"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        pairs = {}
        for t in pcb.traces:
            name = t.net_name or ""
            if not name: continue
            base = name.rstrip("_PN+-pn").rstrip("_PN+-pn0123456789")
            suffix = name[len(base):]
            if suffix.startswith("_") and len(suffix) >= 2:
                pair_base = base + suffix[:2] if suffix[:2] in ("_P", "_N") else base + suffix[:1]
            else:
                pair_base = base + suffix[0] if suffix and suffix[0] in "PN+-" else ""
            if not pair_base:
                continue
            pairs.setdefault(pair_base, {})[suffix] = sum(
                ((s[2]-s[0])**2 + (s[3]-s[1])**2)**0.5
                for s in (t.segments or [])
            ) if t.segments else 0
        for base, lengths in pairs.items():
            if len(lengths) < 2:
                continue
            vals = list(lengths.values())
            max_l, min_l = max(vals), min(vals)
            if min_l > 0 and (max_l - min_l) > 0.127:  # 5mil = 0.127mm
                diff_mm = round(max_l - min_l, 3)
                violations.append(RuleViolation(
                    rule_name="差分对等长检查",
                    description=f"差分对 {base} 两条走线长度差 {diff_mm}mm(>{0.127}mm)",
                    severity=RuleSeverity.WARNING, location=base,
                    suggestion="差分对走线长度差 <5mil(0.127mm)。使用蛇形走线补偿短的一侧。蛇形幅度≥3W,间距≥2S。",
                    theory="差分信号依赖两条线同时到达接收端来维持共模抑制。长度不匹配→到达时间差→差模分量→共模噪声↑、眼图闭合。USB3.0 要求 <5ps skew(≈1mm FR4)。",
                ))
        return violations

    def _check_clock_guard_trace(self, bom_items, positions, netlist):
        """时钟信号包地：高频时钟应有包地走线"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        clk_kw = ["CLK", "CLOCK", "OSC", "XTAL", "MCLK", "SCLK", "HCLK"]
        for t in pcb.traces:
            name = (t.net_name or "").upper()
            if not any(kw.upper() in name for kw in clk_kw):
                continue
            violations.append(RuleViolation(
                rule_name="时钟信号包地检查",
                description=f"时钟网络 [{t.net_name}] 建议添加包地走线",
                severity=RuleSeverity.INFO, location=t.net_name,
                suggestion="时钟走线两侧加接地护线(GND guard trace)，每隔 λ/20 打过孔接地。护线距时钟线 ≥3W。",
                theory="时钟是 PCB 上最强 EMI 源—高幅值、固定频率、陡峭边沿(tr<1ns 含数百 MHz 谐波)。包地走线将电场约束在信号-护线间,降低对邻线的串扰。接地过孔间距≤λ/20(如 100MHz→FR4 λ≈1.5m→λ/20≈7.5mm)。",
            ))
        return violations

    def _check_crosstalk_spacing(self, bom_items, positions, netlist):
        """3W 串扰间距：并行信号线间距应 ≥3 倍线宽"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        # 提取所有走线的粗略位置
        trace_groups = {}
        for t in pcb.traces:
            layer = getattr(t, "layer", "unknown")
            trace_groups.setdefault(layer, []).append(t)
        for layer, traces in trace_groups.items():
            if len(traces) < 2:
                continue
            close_pairs = 0
            for i, t1 in enumerate(traces):
                segs1 = t1.segments or []
                if not segs1: continue
                x1, y1 = segs1[0][0], segs1[0][1]
                for t2 in traces[i + 1:]:
                    segs2 = t2.segments or []
                    if not segs2: continue
                    x2, y2 = segs2[0][0], segs2[0][1]
                    dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
                    avg_w = (t1.width_mm + t2.width_mm) / 2
                    if avg_w > 0 and dist < 3 * avg_w:
                        close_pairs += 1
            if close_pairs > 3:
                violations.append(RuleViolation(
                    rule_name="3W 串扰间距检查",
                    description=f"{layer} 层 {close_pairs} 对走线间距 <3W，串扰风险增大",
                    severity=RuleSeverity.WARNING, location=layer,
                    suggestion="平行走线间距 ≥3W(W=线宽)，高速信号 ≥5W。添加接地隔离或增加间距。",
                    theory="微带线串扰在间距=3W 时近端串扰(NEXT)≈1~3%。间距减半→NEXT↑6~10dB。3W 规则是经验准则:在大多数 FR4 PCB 中将 NEXT 控制在 2% 以下。",
                ))
        return violations

    def _check_loop_area(self, bom_items, positions, netlist):
        """环路面积：高速信号应最小化电流环路面积"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        high_speed_kw = ["CLK", "PWM", "SW", "SENSE", "FB", "DRV", "GATE", "DRIVE"]
        for net_name, net in (pcb.nets or {}).items():
            name_upper = net_name.upper()
            if any(kw.upper() in name_upper for kw in high_speed_kw):
                length = getattr(net, "total_length_mm", 0)
                if length > 50:  # >50mm 长的高速走线
                    violations.append(RuleViolation(
                        rule_name="环路面积检查",
                        description=f"高速网络 [{net_name}] 走线长度 {length:.0f}mm，环路面积可能偏大",
                        severity=RuleSeverity.INFO, location=net_name,
                        suggestion="高速信号紧邻参考平面走线，信号/回流路径构成的环路面积最小化。多层板保证关键信号邻层为完整 GND 平面。",
                        theory="EMI 辐射强度 ∝ 环路面积 × 频率² × 电流。相邻层的信号-回流间距 = 介质厚度(4 层板 ≈0.1~0.2mm),环路面积极小。双层板缺连续参考平面,需手动布置回流路径。",
                    ))
        return violations

    def _check_copper_pour_connectivity(self, bom_items, positions, netlist):
        """铜皮连接：大面积铜皮应避免孤岛"""
        pcb = self._pcb_data
        if not pcb: return []
        violations = []
        pours = getattr(pcb, "copper_pours", None) or []
        if not pours:
            violations.append(RuleViolation(
                rule_name="铜皮连接检查",
                description="PCB 文件未包含铜皮数据，请确认覆铜无孤岛",
                severity=RuleSeverity.INFO,
                suggestion="覆铜后执行 DRC 检查孤岛铜皮(Dead Copper/Islands)。孤岛铜皮应删除或添加过孔接地。",
                theory="孤岛铜皮既不接地也不接任何网络，相当于悬浮的天线→接收/辐射 EMI。GHz 频段时长度=λ/4 即可成为有效天线。删除或接地均可解决。",
            ))
            return violations
        return violations

    def _check_testpoint_coverage(self, bom_items, positions, netlist):
        """测试点覆盖：关键网络应预留测试点"""
        pcb = self._pcb_data
        if not pcb: return []
        violations = []
        key_net_kw = ["VCC", "VDD", "3V3", "5V", "RST", "BOOT", "SWD", "SWCLK", "SWDIO"]
        nets_without_tp = []
        for net_name in (pcb.nets or {}):
            name_upper = net_name.upper()
            if any(kw.upper() in name_upper for kw in key_net_kw):
                nets_without_tp.append(net_name)
        if nets_without_tp:
            violations.append(RuleViolation(
                rule_name="测试点覆盖检查",
                description=f"{len(nets_without_tp)} 个关键网络缺少测试点: {', '.join(nets_without_tp[:5])}",
                severity=RuleSeverity.INFO,
                suggestion="电源轨、复位、调试接口、关键信号预留 φ1.0mm 测试焊盘(TP)。间距≥2.54mm 便于探针/ICT。",
                theory="无测试点→调试时需手工飞线,成品批量测试用 ICT(在线测试)/飞针测试需夹具兼容的测试点布局。IPC-2221 建议测试点直径≥0.9mm,间距≥2.5mm。",
            ))
        return violations

    def _check_silkscreen_readability(self, bom_items, positions, netlist):
        """丝印可读性：丝印应与焊盘/过孔有足够间距"""
        pcb = self._pcb_data
        if not pcb: return []
        violations = []
        # 丝印数据通常不在轻量解析中，给出通用建议
        comp_count = len(pcb.component_positions or {})
        if comp_count > 10:
            violations.append(RuleViolation(
                rule_name="丝印可读性检查",
                description=f"PCB 包含 {comp_count} 个元件，建议检查丝印可读性",
                severity=RuleSeverity.INFO,
                suggestion="丝印方向统一(左→右或下→上)，不与焊盘/过孔重叠，字符高度≥1.0mm。位号与元件一一对应。",
                theory="丝印是PCB装配和维修的关键信息载体。字符过小或重叠→人工焊接误插率↑。IPC-A-600 规定丝印应与焊盘间距≥0.2mm,避免字符在阻焊开窗处脱落。",
            ))
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

    def _check_crystal_proximity(self, bom_items, positions, netlist):
        """晶振靠近 MCU：晶振应尽可能靠近 MCU 振荡器引脚"""
        if not positions: return []
        violations = []
        crystal_kw = ["晶振", "crystal", "XTAL"]
        mcu_kw = ["MCU", "STM32", "ESP32", "ATmega", "ARM", "单片机", "CPU"]
        crystal_positions = []
        mcu_positions = []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if ref not in positions:
                continue
            pos = positions[ref]
            x = pos.get("x", 0) if isinstance(pos, dict) else (pos[0] if isinstance(pos, (list, tuple)) else 0)
            y = pos.get("y", 0) if isinstance(pos, dict) else (pos[1] if isinstance(pos, (list, tuple)) and len(pos) > 1 else 0)
            if any(kw.lower() in desc for kw in crystal_kw):
                crystal_positions.append((ref, x, y))
            if any(kw.lower() in desc for kw in mcu_kw):
                mcu_positions.append((ref, x, y))
        if not crystal_positions or not mcu_positions:
            return violations
        max_dist = 25.0  # mm
        for cr, cx, cy in crystal_positions:
            closest = min(((cx - mx) ** 2 + (cy - my) ** 2) ** 0.5 for _, mx, my in mcu_positions)
            if closest > max_dist:
                violations.append(RuleViolation(
                    rule_name="晶振布局检查",
                    description=f"晶振 {cr} 距 MCU {closest:.0f}mm(建议≤{int(max_dist)}mm)",
                    severity=RuleSeverity.WARNING, location=cr,
                    suggestion="晶振紧靠 MCU OSC_IN/OSC_OUT 引脚，走线短而直，底部铺 GND 铜皮。晶振下方不走其他信号线。",
                    theory="晶振到 MCU 的走线每 1cm 引入约 8nH 寄生电感和 2~5pF 寄生电容→频率偏移和起振困难。皮尔斯振荡器依赖走线电容作为负载的一部分，走线过长破坏 CL 匹配。",
                ))
        return violations

    def _check_switching_regulator_layout(self, bom_items, positions, netlist):
        """开关电源布局：开关电源应输入回路面积最小化"""
        violations = []
        dcdc_kw = ["DC-DC", "BUCK", "BOOST", "开关稳压", "MP", "TPS", "XL", "SY", "MT"]
        found_dcdc = False
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            if any(kw.lower() in desc for kw in dcdc_kw) or \
               any(pn.startswith(p) for p in ["MP", "TPS", "XL", "SY", "MT", "RT", "LMR"]):
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
        if not found_dcdc:
            return []
        return violations

    def _check_antenna_keepout(self, bom_items, positions, netlist):
        """天线净空区：无线模块天线周围应有净空区"""
        violations = []
        wireless_kw = ["蓝牙", "WiFi", "BLE", "ZigBee", "LoRa", "NFC", "RF", "无线",
                       "ESP32", "NRF", "CC25", "HC-05", "ESP8266"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            pn = (getattr(item, "part_number", "") or "").strip().upper()
            if any(kw.lower() in desc for kw in wireless_kw) or \
               any(pn.startswith(p) for p in ["ESP32", "NRF", "CC25", "ESP8266"]):
                ref = getattr(item, "reference", "").split(",")[0].strip()
                violations.append(RuleViolation(
                    rule_name="天线净空区检查",
                    description=f"无线模块 {ref} 天线周围需净空区",
                    severity=RuleSeverity.WARNING, location=ref,
                    suggestion="天线周围 ≥5mm 净空(无铜皮、无元件、无走线)。板载天线置于 PCB 边沿,远离金属外壳。天线下方所有层挖空。",
                    theory="PCB 铜皮在天线近场区改变天线阻抗和辐射方向图→S11↑、效率↓、通信距离大幅缩短。I-PEX/IPEX 连接器到天线的微带线需 50Ω 阻抗控制,净空保证阻抗连续性。",
                ))
        return violations

    def _check_mounting_hole_keepout(self, bom_items, positions, netlist):
        """安装孔禁区：安装孔周围应有禁布区"""
        if not positions: return []
        violations = []
        hole_kw = ["HOLE", "MTG", "安装孔", "螺丝孔", "定位孔"]
        keepout_r = 3.0
        hole_refs = []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} {getattr(item, 'reference', '')}".lower()
            if not any(kw.lower() in desc for kw in hole_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            hole_refs.append(ref)
        near_holes = []
        for hole_ref in hole_refs:
            if hole_ref not in positions:
                continue
            hpos = positions[hole_ref]
            hx = hpos.get("x", 0) if isinstance(hpos, dict) else (hpos[0] if isinstance(hpos, (list, tuple)) else 0)
            hy = hpos.get("y", 0) if isinstance(hpos, dict) else (hpos[1] if isinstance(hpos, (list, tuple)) and len(hpos) > 1 else 0)
            for item in bom_items:
                ref = getattr(item, "reference", "").split(",")[0].strip()
                if ref in hole_refs or ref not in positions:
                    continue
                pos = positions[ref]
                x = pos.get("x", 0) if isinstance(pos, dict) else (pos[0] if isinstance(pos, (list, tuple)) else 0)
                y = pos.get("y", 0) if isinstance(pos, dict) else (pos[1] if isinstance(pos, (list, tuple)) and len(pos) > 1 else 0)
                dist = ((hx - x) ** 2 + (hy - y) ** 2) ** 0.5
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

    def _check_temp_sensitive_placement(self, bom_items, positions, netlist):
        """温度敏感元件：温度敏感元件应远离热源"""
        violations = []
        temp_sensitive_kw = ["晶振", "crystal", "XTAL", "ADC", "基准", "reference", "REF", "传感器",
                            "电解电容", "electrolytic", "光耦", "optocoupler"]
        heat_source_kw = ["LDO", "DC-DC", "BUCK", "BOOST", "MOSFET", "功率电阻", "电源",
                         "regulator", "driver", "LED驱动"]
        temp_sensitive = []
        heat_sources = []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if any(kw.lower() in desc for kw in temp_sensitive_kw):
                temp_sensitive.append(ref)
            if any(kw.lower() in desc for kw in heat_source_kw):
                heat_sources.append(ref)
        if not temp_sensitive or not heat_sources:
            return violations
        if positions:
            warnings = 0
            min_distance = 10.0
            for tr in temp_sensitive:
                if tr not in positions: continue
                tp = positions[tr]
                tx = tp.get("x", 0) if isinstance(tp, dict) else (tp[0] if isinstance(tp, (list, tuple)) else 0)
                ty = tp.get("y", 0) if isinstance(tp, dict) else (tp[1] if isinstance(tp, (list, tuple)) and len(tp) > 1 else 0)
                for hr in heat_sources:
                    if hr not in positions: continue
                    hp = positions[hr]
                    hx = hp.get("x", 0) if isinstance(hp, dict) else (hp[0] if isinstance(hp, (list, tuple)) else 0)
                    hy = hp.get("y", 0) if isinstance(hp, dict) else (hp[1] if isinstance(hp, (list, tuple)) and len(hp) > 1 else 0)
                    dist = ((tx - hx) ** 2 + (ty - hy) ** 2) ** 0.5
                    if dist < min_distance:
                        warnings += 1
            if warnings > 2:
                violations.append(RuleViolation(
                    rule_name="温度敏感元件布局检查",
                    description=f"{warnings} 对温度敏感元件与热源间距 <{int(min_distance)}mm",
                    severity=RuleSeverity.WARNING,
                    suggestion=f"晶振/ADC/基准源/电解电容距离热源 ≥{int(min_distance)}mm。使用热仿真或红外热像仪验证。",
                    theory="晶振频率漂移 Δf/f≈α×ΔT(α≈-0.03ppm/°C²),温升 20°C→频率漂移可达 12ppm。电解电容在 85°C 以上工作时寿命指数衰减(105°C 品在 95°C 工作寿命减半)。",
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

    def _check_emi_filter_proximity(self, bom_items, positions, netlist):
        """EMI 滤波器靠近入口：EMI 滤波器件应紧靠电源入口"""
        violations = []
        emi_kw = ["共模", "choke", "CMC", "EMI", "filter", "X电容", "Y电容"]
        conn_kw = ["电源", "DC-IN", "VIN", "PWR", "power", "端子", "插座", "connector", "HEADER"]
        emi_refs, conn_refs = [], []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if any(kw.lower() in desc for kw in emi_kw):
                emi_refs.append(ref)
            if any(kw.lower() in desc for kw in conn_kw):
                conn_refs.append(ref)
        if not emi_refs or not conn_refs:
            return violations
        if positions:
            max_dist = 30.0
            far_pairs = []
            for er in emi_refs:
                if er not in positions: continue
                ep = positions[er]
                ex = ep.get("x", 0) if isinstance(ep, dict) else (ep[0] if isinstance(ep, (list, tuple)) else 0)
                ey = ep.get("y", 0) if isinstance(ep, dict) else (ep[1] if isinstance(ep, (list, tuple)) and len(ep) > 1 else 0)
                for cr in conn_refs:
                    if cr not in positions: continue
                    cp = positions[cr]
                    cx = cp.get("x", 0) if isinstance(cp, dict) else (cp[0] if isinstance(cp, (list, tuple)) else 0)
                    cy = cp.get("y", 0) if isinstance(cp, dict) else (cp[1] if isinstance(cp, (list, tuple)) and len(cp) > 1 else 0)
                    dist = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
                    if dist > max_dist:
                        far_pairs.append(f"{er}/{cr}({dist:.0f}mm)")
            if far_pairs:
                violations.append(RuleViolation(
                    rule_name="EMI 滤波器布局检查",
                    description=f"EMI 滤波器件距电源入口 >{int(max_dist)}mm: {', '.join(far_pairs[:3])}",
                    severity=RuleSeverity.WARNING,
                    suggestion=f"EMI 滤波器件紧靠电源连接器(≤{int(max_dist)}mm)。滤波前后分区敷铜,避免噪声耦合绕过滤波器。",
                    theory="EMI 滤波器的作用是将噪声电流旁路回源端。滤波器距入口越远,入口到滤波器间的走线越长→走线辐射的噪声绕过滤波器直接耦合到电源线,滤波器效果大幅降低。",
                ))
        return violations

    def _check_connector_edge_placement(self, bom_items, positions, netlist):
        """连接器边沿布局：连接器/接口应置于 PCB 边沿"""
        violations = []
        conn_kw = ["USB", "RJ45", "HDMI", "DB9", "排针", "端子", "CONNECTOR", "HEADER", "JACK",
                   "DC", "电源插座", "SD卡", "TF卡", "SIM卡", "FPC", "FFC"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.lower() in desc for kw in conn_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if not positions or ref not in positions:
                continue
            pos = positions[ref]
            x = pos.get("x", 0) if isinstance(pos, dict) else (pos[0] if isinstance(pos, (list, tuple)) else 0)
            y = pos.get("y", 0) if isinstance(pos, dict) else (pos[1] if isinstance(pos, (list, tuple)) and len(pos) > 1 else 0)
            max_board_edge = 10.0
            if x > max_board_edge and y > max_board_edge:
                violations.append(RuleViolation(
                    rule_name="连接器边沿布局检查",
                    description=f"连接器 {ref} 距板边较远({x:.0f},{y:.0f})，可能影响插拔操作",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion="连接器/接口紧贴 PCB 边沿，开口朝外。机壳开孔位置与连接器对准，预留插头空间(如 USB 插头长度 ≈15mm)。",
                    theory="连接器置于板中心→机壳内部需延长开孔通道,增加机械设计难度且插拔力会使 PCB 弯曲。板边布局插拔力直接由机壳/固定柱承受。",
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
        # 统计总电容数量
        cap_count = sum(1 for i in bom_items
                       if any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                              for kw in ["电容", "capacitor"]))
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

    def _check_silkscreen_pad_clearance(self, bom_items, positions, netlist):
        """丝印与焊盘间距：丝印文字不应覆盖焊盘"""
        pcb = self._pcb_data
        if not pcb or not pcb.component_positions:
            return []
        comp_count = len(pcb.component_positions)
        if comp_count > 5:
            return [RuleViolation(
                rule_name="丝印焊盘间距检查",
                description=f"PCB 含 {comp_count} 个元件，丝印与焊盘间距需确认",
                severity=RuleSeverity.INFO,
                suggestion="丝印距焊盘≥0.2mm(IPC-A-600)。位号丝印勿覆盖焊盘或过孔。字符高度≥1.0mm，方向统一。",
                theory="丝印在阻焊开窗处附着力差→脱落不清。焊盘上丝印影响可焊性且字符在回流焊后不可读。IPC-A-600 Acceptable Class 2 标准。",
            )]
        return []

    def _check_trace_edge_clearance(self, bom_items, positions, netlist):
        """走线到板边：走线距板边应有安全间距"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        min_clearance = 0.5
        near_edge = 0
        for t in pcb.traces:
            for seg in (t.segments or []):
                if len(seg) >= 2 and (seg[0] < min_clearance or seg[1] < min_clearance):
                    near_edge += 1
                    break
        if near_edge > 0:
            return [RuleViolation(
                rule_name="走线板边间距检查",
                description=f"{near_edge} 条走线距板边可能 <{min_clearance}mm",
                severity=RuleSeverity.WARNING,
                suggestion="走线/铜皮距板边≥0.5mm(V-cut≥0.8mm)。板边走线在铣边时易被切断或暴露铜。",
                theory="PCB 铣边公差通常±0.15mm，V-cut 深度控制公差±0.1mm。板边间距不足→铣刀损伤走线致开路或微短。IPC-2221 要求外层铜箔距板边≥0.5mm。",
            )]
        return []

    def _check_stub_length(self, bom_items, positions, netlist):
        """短桩线(stub)检查：高速信号应避免长 stubs"""
        pcb = self._pcb_data
        if not pcb or not pcb.vias: return []
        high_speed_kw = {"CLK", "SCK", "SDIO", "SDRAM", "USB", "HDMI", "PCIE"}
        stub_nets = []
        for v in pcb.vias:
            net = getattr(v, "net_name", "") or getattr(v, "net", "") or ""
            if any(kw.upper() in net.upper() for kw in high_speed_kw):
                if net not in stub_nets:
                    stub_nets.append(net)
        if stub_nets:
            return [RuleViolation(
                rule_name="短桩线检查",
                description=f"高速网络 {', '.join(stub_nets[:3])} 含过孔，可能存在stub效应",
                severity=RuleSeverity.INFO,
                suggestion="高速信号过孔→走线→过孔结构中，分支长度(Stub)应<λ/10。多余过孔 stub 需背钻或避免。",
                theory="Stub 在高速信号路径中形成1/4波长谐振腔——f_res=c/(4×L×√εr)。当 f_res 落入信号带宽时产生深度陷波，破坏眼图。>1GHz 信号 stub 需<3mm。",
            )]
        return []

    def _check_net_antenna(self, bom_items, positions, netlist):
        """天线效应检查：大面积未连接网络的铜皮可能成为天线"""
        pcb = self._pcb_data
        if not pcb or not pcb.nets: return []
        unconnected = 0
        for name, net in pcb.nets.items():
            pins = getattr(net, "pins", []) or []
            if len(pins) <= 1 and name and not name.upper().startswith("GND"):
                unconnected += 1
        if unconnected > 2:
            return [RuleViolation(
                rule_name="天线效应检查",
                description=f"{unconnected} 个网络仅连接 ≤1 个引脚，可能为浮空网络或天线",
                severity=RuleSeverity.WARNING,
                suggestion="单端网络(只有1个引脚)检查是否为未布线或孤岛。大面积浮空铜皮=EMI天线。",
                theory="浮空导体在电磁场中感应电压，长度=λ/4时成为高效天线。10cm 导体在 750MHz 共振。删除浮空铜或接地(打过孔)。",
            )]
        return []

    def _check_unconnected_pins(self, bom_items, positions, netlist):
        """未连接引脚：IC 引脚应全部连接（至少连到某网络或标记NC）"""
        if not netlist or not bom_items: return []
        violations = []
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            pkg = (getattr(item, "package", "") or "").upper()
            pn = (getattr(item, "part_number", "") or "").upper()
            # 粗略估算引脚数
            pkg_pins = {"SOP-8": 8, "SOP-16": 16, "TSSOP-20": 20, "QFN-32": 32,
                        "QFN-48": 48, "LQFP-48": 48, "LQFP-64": 64, "LQFP-100": 100}
            est_pins = 0
            for k, v in pkg_pins.items():
                if k in pkg: est_pins = v; break
            if est_pins >= 16:
                # 检查该 IC 有多少引脚出现在 netlist 中
                connected = sum(1 for n in (netlist or {}).values()
                               if any(ref in p for p in (getattr(n, "pins", []) or [])))
                if connected < est_pins * 0.6:
                    violations.append(RuleViolation(
                        rule_name="未连接引脚检查",
                        description=f"IC {ref}({pkg}) 大量引脚可能未连接或 netlist 不完整",
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
        dcdc_kw = ["DC-DC", "BUCK", "BOOST", "开关", "MP", "TPS", "XL", "SY"]
        has_dcdc = any(any(kw.upper() in (getattr(i, "part_number", "") or "").upper()
                           for kw in dcdc_kw) for i in bom_items)
        if has_dcdc:
            return [RuleViolation(
                rule_name="功率回路面积检查",
                description="检测到开关电源器件，输入电容→开关→电感→输出电容的 di/dt 回路需最小化",
                severity=RuleSeverity.WARNING,
                suggestion="Buck 的 Cin-SW-L-Cout 回路面积最小化。输入电容紧靠 VIN/GND 引脚。SW 节点铜皮面积最小(避免天线效应)。",
                theory="功率回路 di/dt 可达数A/ns。环路面积与 EMI 辐射强度成正比。SW 节点 dV/dt 达数V/ns 是 PCB 最强 EMI 源。CISPR 22 Class B 要求传导发射在150kHz-30MHz 低于限值。",
            )]
        return []

    def _check_ground_plane_continuity(self, bom_items, positions, netlist):
        """地平面连续性：GND 铺地应避免割裂"""
        pcb = self._pcb_data
        if not pcb: return []
        return [RuleViolation(
            rule_name="地平面连续性检查",
            description="高速信号需要连续的地平面作为回流路径。割裂的地平面增加环路面积和EMI。",
            severity=RuleSeverity.INFO,
            suggestion="关键信号(时钟/高频)下方保证完整 GND 平面。信号跨分割区需加stitching电容(10nF)桥接回流。",
            theory="高速信号的回流电流沿最小阻抗路径(紧邻信号线下方)流回源端。地平面割裂→回流绕行→环路面积↑→EMI↑。>50MHz 信号必须保证连续参考平面。",
        )]
        return []

    def _check_pullup_pulldown(self, bom_items, positions, netlist):
        """上拉/下拉电阻：关键信号(RST/EN/BOOT/INT)应有明确上下拉"""
        control_pins = {"RST", "RESET", "EN", "ENABLE", "BOOT", "INT", "NMI", "CONFIG"}
        control_net = None
        if netlist:
            for name in netlist:
                upper = name.upper()
                if any(pin in upper for pin in control_pins):
                    control_net = name
                    break
        # 检查是否有 1k~100k 电阻
        has_pull_r = any(
            any(kw.lower() in (f"{getattr(i, 'part_number', '')} {getattr(i, 'description', '')}").lower()
                for kw in ["电阻", "resistor"])
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

    def _check_via_thermal_relief(self, bom_items, positions, netlist):
        """过孔热焊盘：大面积铜皮上的过孔应使用热焊盘连接"""
        pcb = self._pcb_data
        if not pcb or not pcb.vias: return []
        via_count = len(pcb.vias)
        if via_count > 20:
            return [RuleViolation(
                rule_name="过孔热焊盘检查",
                description=f"PCB 含 {via_count} 个过孔，大面积铜皮上的过孔应使用热焊盘(Thermal Relief)连接",
                severity=RuleSeverity.INFO,
                suggestion="大面积 GND/VCC 铜皮上的过孔用热焊盘(十字花连接)而非全连接，便于手工焊接返修。",
                theory="全连接过孔在大面积铜皮上散热极快→烙铁无法熔化焊锡→虚焊。热焊盘用 4 条细径(通常 0.25mm)限制热传导，使焊点可达到焊接温度。",
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

    def _check_hs_signal_reference_plane(self, bom_items, positions, netlist):
        """高速信号参考平面检查"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        hs_nets = [t.net_name for t in pcb.traces
                   if t.net_name and any(kw.upper() in t.net_name.upper()
                   for kw in ["CLK", "USB", "HDMI", "PCIE", "SDRAM", "LVDS", "ETH"])]
        if hs_nets:
            return [RuleViolation(
                rule_name="高速信号参考平面检查",
                description=f"{len(set(hs_nets))} 个高速网络需确认邻层为完整 GND 参考平面",
                severity=RuleSeverity.WARNING,
                suggestion="高速信号邻层必须是完整 GND 平面(不分割)。4层板推荐 SIG-GND-PWR-SIG 叠层。",
                theory="微带线/带状线特性阻抗取决于信号到参考平面的距离(H)。邻层跨分割区→阻抗突变→反射、串扰↑。IPC-2221 建议高速信号不能跨越参考平面分割区。",
            )]
        return []

    def _check_component_spacing(self, bom_items, positions, netlist):
        """元件间距：相邻元件应有足够间距"""
        if not positions: return []
        min_spacing = 1.0
        close_pairs = 0
        pos_items = list(positions.items())
        for i in range(len(pos_items)):
            for j in range(i + 1, min(i + 5, len(pos_items))):
                p1 = pos_items[i][1]
                p2 = pos_items[j][1]
                x1 = p1.get("x", 0) if isinstance(p1, dict) else (p1[0] if isinstance(p1, (list, tuple)) else 0)
                y1 = p1.get("y", 0) if isinstance(p1, dict) else (p1[1] if isinstance(p1, (list, tuple)) and len(p1) > 1 else 0)
                x2 = p2.get("x", 0) if isinstance(p2, dict) else (p2[0] if isinstance(p2, (list, tuple)) else 0)
                y2 = p2.get("y", 0) if isinstance(p2, dict) else (p2[1] if isinstance(p2, (list, tuple)) and len(p2) > 1 else 0)
                if ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 < min_spacing:
                    close_pairs += 1
        if close_pairs > 3:
            return [RuleViolation(
                rule_name="元件间距检查",
                description=f"约 {close_pairs} 对元件间距 <{min_spacing}mm，可能影响 SMT 贴片和返修",
                severity=RuleSeverity.INFO,
                suggestion="SMT 元件间≥0.5mm(0603), ≥0.8mm(0805)。高元件间≥1.5mm。连接器周围预留插拔空间。",
                theory="元件间距过小→SMT 钢网印刷桥连、回流焊阴影效应、烙铁无法伸入返修。IPC-7351 为每种封装定义了标准焊盘和间距。",
            )]
        return []

    def _check_fiducial_mark(self, bom_items, positions, netlist):
        """Mark点检查：批量生产PCB应有光学定位Mark点"""
        if positions and len(positions) > 10:
            return [RuleViolation(
                rule_name="光学定位点检查",
                description="PCB 含较多元件但未确认是否有光学定位(Mark)点",
                severity=RuleSeverity.INFO,
                suggestion="PCB 对角放置≥2个全局 Mark 点(Φ1.0mm 铜箔+Φ3.0mm 阻焊开窗)。细间距IC(QFP/BGA)局部加Mark点。",
                theory="SMT 贴片机通过识别 Mark 点校正 PCB 位置偏差。全局 Mark 用于整板定位，局部 Mark 用于精细间距元件定位。无 Mark 点→贴片精度不足→立碑/偏移。",
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

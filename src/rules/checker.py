"""
PCB 设计规则检查模块
针对测控电路的常见设计规则进行自动检查
"""

import logging
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
    """规则违规记录"""

    rule_name: str
    description: str
    severity: RuleSeverity
    location: str = ""          # 受影响的位号/网络
    suggestion: str = ""        # 修复建议


class DesignRuleChecker:
    """PCB 设计规则检查器 — 测控电路专用规则"""

    def __init__(self):
        self._pcb_data: Optional[PCBData] = None
        self._rules = [
            self._check_decoupling_caps,
            self._check_signal_traces,
            self._check_power_traces,
            self._check_analog_digital_separation,
        ]

    def check_all(
        self,
        bom_items: list,
        positions: Optional[dict] = None,
        netlist: Optional[dict] = None,
        pcb_data: Optional[PCBData] = None,
    ) -> list[RuleViolation]:
        """
        执行所有设计规则检查

        Args:
            bom_items: BOM 物料列表
            positions: 元件坐标（可选）
            netlist:   网表数据（可选，保留兼容）
            pcb_data:  PCB 解析结果（M1 新增）

        Returns:
            违规列表
        """
        self._pcb_data = pcb_data
        violations = []

        for rule_func in self._rules:
            try:
                result = rule_func(bom_items, positions, netlist)
                if result:
                    violations.extend(result)
            except Exception as e:
                logger.warning(f"规则检查异常 ({rule_func.__name__}): {e}")

        logger.info(f"规则检查完成: 发现 {len(violations)} 项违规")
        return violations

    # ──────────────── 具体规则 ────────────────

    def _check_decoupling_caps(
        self, bom_items: list, positions: dict, netlist: dict
    ) -> list[RuleViolation]:
        """
        去耦电容检查
        规则：每个 IC 的电源引脚附近应有 0.1μF 去耦电容
        """
        violations = []

        # 识别 IC（非无源元件）
        passive_kw = ["电阻", "电容", "电感", "Resistor", "Capacitor", "Inductor"]
        ics = []
        caps = []

        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if any(kw.lower() in desc for kw in passive_kw):
                if "电容" in desc or "capacitor" in desc:
                    caps.append(item)
            else:
                ics.append(item)

        # 检查每个 IC 是否有对应的去耦电容
        for ic in ics:
            ic_ref = getattr(ic, "reference", "?")
            # 简化判断：按经验，每个IC至少需要1个 0.1μF 电容
            has_decoupling = any(
                getattr(c, "value", "").replace(" ", "").upper()
                in ["0.1UF", "100NF", "0.1ΜF", "104"]
                for c in caps
            )
            if not has_decoupling:
                violations.append(
                    RuleViolation(
                        rule_name="去耦电容检查",
                        description=f"IC {ic_ref} ({getattr(ic, 'part_number', '未知')}) 附近可能缺少去耦电容",
                        severity=RuleSeverity.WARNING,
                        location=ic_ref,
                        suggestion="建议在电源引脚附近放置 0.1μF (100nF) 陶瓷电容",
                    )
                )

        return violations

    def _check_signal_traces(
        self, bom_items: list, positions: dict, netlist: dict
    ) -> list[RuleViolation]:
        """信号线宽度检查：关键信号网络走线宽度应 ≥ 最小线宽"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces:
            return []

        violations = []
        min_width = PCB.SIGNAL_TRACE_MIN_WIDTH_MM

        # 识别信号网络（排除电源/地）
        signal_traces = [
            t for t in pcb.traces
            if t.width_mm > 0 and not any(
                kw.upper() in t.net_name.upper() for kw in PCB.POWER_NET_KEYWORDS
            ) if t.net_name
        ]

        # 按网络分组检查最细走线
        net_min_width: dict[str, float] = {}
        for t in signal_traces:
            prev = net_min_width.get(t.net_name, float("inf"))
            if t.width_mm < prev:
                net_min_width[t.net_name] = t.width_mm

        for net_name, w in net_min_width.items():
            if w < min_width:
                violations.append(RuleViolation(
                    rule_name="信号线宽度检查",
                    description=f"网络 [{net_name}] 最小走线宽度 {w:.3f}mm < {min_width}mm",
                    severity=RuleSeverity.WARNING,
                    location=net_name,
                    suggestion=(
                        f"当前线宽 {w:.3f}mm 过细，建议加宽至 ≥ {min_width}mm。"
                        f"如为高速差分信号请确认阻抗匹配要求。"
                    ),
                ))

        return violations

    def _check_power_traces(
        self, bom_items: list, positions: dict, netlist: dict
    ) -> list[RuleViolation]:
        """电源线宽度检查：电源网络走线宽度需满足载流要求（IPC-2221 简化）"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces:
            return []

        violations = []

        # 估算每路电源的电流（从 BOM 反推，默认 0.5A）
        power_load: dict[str, float] = {}
        for item in bom_items:
            for kw in PCB.POWER_NET_KEYWORDS:
                if (
                    isinstance(item, dict)
                    and kw.upper() in str(item.get("net", item.get("value", ""))).upper()
                ):
                    power_load[kw.upper()] = max(
                        power_load.get(kw.upper(), 0.0), PCB.POWER_CURRENT_DEFAULT_A
                    )
                elif hasattr(item, "value"):
                    val = str(getattr(item, "value", ""))
                    if kw.upper() in val.upper():
                        power_load[kw.upper()] = max(
                            power_load.get(kw.upper(), 0.0), PCB.POWER_CURRENT_DEFAULT_A
                        )

        # 识别电源网络走线
        power_traces = [
            t for t in pcb.traces
            if t.width_mm > 0 and any(
                kw.upper() in t.net_name.upper() for kw in PCB.POWER_NET_KEYWORDS
            ) if t.net_name
        ]

        if not power_traces:
            return violations

        k = PCB.IPC_K_FACTOR
        copper = PCB.IPC_COPPER_OZ
        temp_rise = PCB.IPC_TEMP_RISE

        # 按网络找出最小线宽（类似信号线检查）
        net_min_width: dict[str, float] = {}
        for t in power_traces:
            if not t.net_name:
                continue
            prev = net_min_width.get(t.net_name, float("inf"))
            if t.width_mm < prev:
                net_min_width[t.net_name] = t.width_mm

        # 检查每个电源网络的最细走线
        copper_thickness_mil = PCB.IPC_COPPER_OZ * 1.37
        for name, min_w in net_min_width.items():
            current = PCB.POWER_CURRENT_DEFAULT_A
            for net_kw, load_a in power_load.items():
                if net_kw in name.upper():
                    current = load_a
                    break

            # IPC-2221 外层: I = k * ΔT^0.44 * A^0.725
            # A = cross-sectional area in mil²
            # 1oz copper = 1.37 mils thick; 1mm = 39.37 mils
            area_mil2 = (current / (k * temp_rise ** 0.44)) ** (1.0 / 0.725)
            width_mil = area_mil2 / copper_thickness_mil
            required_width = round(width_mil * 0.0254, 3)  # mil → mm

            # 当前最小线宽的等效载流（mil² → mm² 换算）
            current_area_mil2 = (min_w / 0.0254) * copper_thickness_mil
            supported_current = k * temp_rise ** 0.44 * current_area_mil2 ** 0.725

            if min_w < required_width * 0.8:  # 20% 容差
                violations.append(RuleViolation(
                    rule_name="电源线宽度检查",
                    description=(
                        f"电源网络 [{name}] 最细走线 {min_w:.3f}mm，"
                        f"不满足载流 {current}A 所需 ≥ {required_width:.3f}mm"
                    ),
                    severity=RuleSeverity.ERROR,
                    location=name,
                    suggestion=(
                        f"当前 {min_w:.3f}mm 线宽仅支持约 {supported_current:.1f}A，"
                        f"建议加宽至 ≥ {required_width:.3f}mm 或增厚铜箔。"
                    ),
                ))

        return violations

    def _check_analog_digital_separation(
        self, bom_items: list, positions: dict, netlist: dict
    ) -> list[RuleViolation]:
        """模拟/数字信号分离检查：模拟与数字元件应物理分区布线"""
        if not positions or not bom_items:
            return []

        violations = []

        # 分类元件
        analog_refs: list[str] = []
        digital_refs: list[str] = []
        analog_coords: list[tuple[float, float, str]] = []
        digital_coords: list[tuple[float, float, str]] = []

        for item in bom_items:
            desc = ""
            if hasattr(item, "description"):
                desc = str(item.description or "")
            if hasattr(item, "part_number"):
                desc += " " + str(item.part_number or "")
            desc_lower = desc.lower()

            is_analog = any(kw.lower() in desc_lower for kw in PCB.ANALOG_COMPONENT_KW)
            is_digital = any(kw.lower() in desc_lower for kw in PCB.DIGITAL_COMPONENT_KW)

            if hasattr(item, "reference"):
                ref = item.reference
                # 取第一个位号
                first_ref = ref.split(",")[0].strip() if ref else ""

                if first_ref and first_ref in positions:
                    pos = positions[first_ref]
                    x = pos.get("x", 0) if isinstance(pos, dict) else pos[0] if isinstance(pos, (list, tuple)) else 0
                    y = pos.get("y", 0) if isinstance(pos, dict) else pos[1] if isinstance(pos, (list, tuple)) and len(pos) > 1 else 0

                    if is_analog:
                        analog_refs.append(first_ref)
                        analog_coords.append((x, y, first_ref))
                    elif is_digital:
                        digital_refs.append(first_ref)
                        digital_coords.append((x, y, first_ref))

        if not analog_coords or not digital_coords:
            return violations

        min_sep = PCB.AD_SEPARATION_MIN_MM

        # 计算模拟区/数字区中心距离
        def _center(coords):
            if not coords:
                return (0, 0)
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            return (sum(xs) / len(xs), sum(ys) / len(ys))

        acx, acy = _center(analog_coords)
        dcx, dcy = _center(digital_coords)
        center_dist = ((acx - dcx) ** 2 + (acy - dcy) ** 2) ** 0.5

        # 检查最近交叉距离
        cross_violations = []
        for ax, ay, aref in analog_coords:
            for dx, dy, dref in digital_coords:
                dist = ((ax - dx) ** 2 + (ay - dy) ** 2) ** 0.5
                if dist < min_sep:
                    cross_violations.append((aref, dref, round(dist, 2)))

        if cross_violations:
            pairs = ", ".join(f"{a}/{d}" for a, d, _ in cross_violations[:5])
            more = f" ...等 {len(cross_violations)} 对" if len(cross_violations) > 5 else ""
            violations.append(RuleViolation(
                rule_name="模拟/数字分离检查",
                description=(
                    f"发现 {len(cross_violations)} 对模拟-数字元件间距 < {min_sep}mm{more}"
                ),
                severity=RuleSeverity.WARNING,
                location=pairs,
                suggestion=(
                    f"模拟与数字区域中心距离 {center_dist:.1f}mm。"
                    f"建议将模拟元件（如运放/ADC）与数字元件（如MCU）分区布局，"
                    f"保持 ≥ {min_sep}mm 间距，并使用独立的模拟地/数字地铺铜。"
                ),
            ))

        return violations

    # ──────────────── 报告生成 ────────────────

    def get_report(self, violations: list[RuleViolation]) -> str:
        """生成规则检查报告"""
        if not violations:
            return "✅ 设计规则检查通过，未发现违规项。"

        lines = [
            "=" * 55,
            "          PCB 设计规则检查报告",
            "=" * 55,
        ]

        for severity in (RuleSeverity.ERROR, RuleSeverity.WARNING, RuleSeverity.INFO):
            items = [v for v in violations if v.severity == severity]
            if not items:
                continue

            emoji = {"error": "❌", "warning": "⚠️ ", "info": "ℹ️ "}[severity.value]
            lines.append(f"\n【{severity.value.upper()}】{emoji} {len(items)} 项")

            for v in items:
                lines.append(f"  • {v.description}")
                if v.location:
                    lines.append(f"    位置: {v.location}")
                if v.suggestion:
                    lines.append(f"    建议: {v.suggestion}")

        lines.append("\n" + "=" * 55)
        return "\n".join(lines)

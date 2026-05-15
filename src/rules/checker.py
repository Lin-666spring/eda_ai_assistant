"""
PCB 设计规则检查模块
针对测控电路的常见设计规则进行自动检查
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

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
    ) -> list[RuleViolation]:
        """
        执行所有设计规则检查

        Args:
            bom_items: BOM 物料列表
            positions: 元件坐标（可选）
            netlist:   网表数据（可选）

        Returns:
            违规列表
        """
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
        """
        信号线规则检查（占位实现）
        需要 PCB 布线数据才能完整检查
        """
        return []  # 当前版本需要解析立创EDA的PCB文件

    def _check_power_traces(
        self, bom_items: list, positions: dict, netlist: dict
    ) -> list[RuleViolation]:
        """
        电源线宽度检查（占位实现）
        """
        return []

    def _check_analog_digital_separation(
        self, bom_items: list, positions: dict, netlist: dict
    ) -> list[RuleViolation]:
        """
        模拟/数字信号分离检查（占位实现）
        测控电路中模拟信号易受数字信号干扰
        """
        return []

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

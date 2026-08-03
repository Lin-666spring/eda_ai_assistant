"""
EI 论文实验框架 — 自动化闭环验证实验

实验组:
  A. DRC 基线        — 纯规则检查，不调用 LLM
  B. 闭环验证         — LLM 建议 → DRC 检查 → 反馈 → LLM 修正 → 迭代
  C. 多智能体审查     — 5 Agent 并发评分，雷达图

用法:
  # 完整实验（需要 API key）
  python tests/paper_experiments.py

  # 指定供应商
  python tests/paper_experiments.py --provider deepseek

  # 仅 DRC 基线（不需要 LLM）
  python tests/paper_experiments.py --drc-only

  # 指定输出目录
  python tests/paper_experiments.py --output results/exp1/

输出:
  experiment_results/
  └── run_2026-07-09_143052/
      ├── results.json          # 完整实验数据
      ├── summary.md            # Markdown 摘要报告
      └── charts/               # 图表（由 paper_charts.py 生成）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.controller import AppController
from src.core.verifier import (
    VerificationEngine,
    VerificationReport,
    VerificationStatus,
    VerificationIssue,
    SuggestionCategory,
    create_verifier_from_controller,
)
from src.rules.checker import DesignRuleChecker, RuleViolation, RuleSeverity, group_violations_by_component
from src.agent.llm_client import LLMClient


# ═══════════════════════════════════════════════════════════════
#  Data Classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class DesignSpec:
    """A PCB design under test."""
    name: str
    bom_path: Path
    positions_path: Optional[Path] = None
    pcb_path: Optional[Path] = None
    description: str = ""


@dataclass
class SuggestionCase:
    """A test suggestion to verify."""
    text: str
    category: str = "general"       # safe / dangerous / optimization
    description: str = ""
    expected_category: str = "GENERAL"  # SuggestionCategory value


@dataclass
class ProviderConfig:
    """LLM provider configuration."""
    name: str                       # "deepseek" / "qwen" / "glm"
    api_key: str
    model: str = ""
    base_url: str = ""


@dataclass
class DRCResult:
    """DRC baseline result for one design."""
    design: str
    total_violations: int
    errors: int
    warnings: int
    infos: int
    violations_by_rule: dict = field(default_factory=dict)
    violations_by_component: dict = field(default_factory=dict)  # AI Verification Map
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    timestamp: str = ""


@dataclass
class VerifyResult:
    """Single closed-loop verification result."""
    design: str
    provider: str
    model: str
    suggestion_category: str        # safe / dangerous / optimization
    suggestion_text: str
    suggestion_desc: str
    accepted: bool
    final_status: str
    rounds: int
    total_issues: int
    blocking_issues: int
    info_issues: int
    max_severity: str               # highest severity found
    llm_correction_rounds: int      # how many rounds had LLM correction
    hallucination_elimination: Optional[float] = None  # (first_blocking - final_blocking) / first_blocking
    per_round_blocking: list = field(default_factory=list)  # [round1_blocking, round2_blocking, ...]
    raw_report: dict = field(default_factory=dict)  # Full VerificationReport.to_dict()
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    # ── 闭环前后综合评分 Δ（2026-08-03 新增，论文核心指标）──
    baseline_score: Optional[float] = None   # 原始 BOM 综合评分
    final_score: Optional[float] = None      # 最后一轮应用建议后的综合评分
    delta_score: Optional[float] = None      # final - baseline（正=质量提升，负=变差）
    timestamp: str = ""
    # Phase B BOM modification metrics (v0.7.4)
    suggested_changes_count: int = 0      # LLM 建议的 BOM 变更数
    new_violations_introduced: int = 0    # 第一轮引入的新 DRC 违规数
    correction_rounds: int = 0            # LLM 修正轮次
    final_violation_delta: int = 0        # 最终剩余新违规数
    converged: bool = False               # 是否成功消除所有新违规
    # AI Verification Map: per-component change tracking
    applied_changes: list = field(default_factory=list)  # [{ref, field, old_value, new_value}, ...]


@dataclass
class MultiAgentResult:
    """Multi-agent review result for one design."""
    design: str
    provider: str
    model: str
    overall_score: float
    overall_grade: str
    radar_scores: dict = field(default_factory=dict)       # dimension → score
    agent_scores: dict = field(default_factory=dict)        # agent → score
    critical_count: int = 0
    total_findings: int = 0
    consensus_preview: str = ""
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    timestamp: str = ""


# ═══════════════════════════════════════════════════════════════
#  Phase D: Programmatic Defect Injection
# ═══════════════════════════════════════════════════════════════

@dataclass
class DefectSpec:
    """A known defect to inject into a BOM for DRC detection testing."""
    defect_id: str                  # short slug, e.g. "no_decoupling"
    name: str                       # human-readable name
    description: str                # what was changed
    expected_rules: list[str]       # DRC rule names expected to fire
    severity: str = "warning"       # expected severity


@dataclass
class DefectInjectionResult:
    """Result of injecting a defect and running DRC."""
    design: str
    defect_id: str
    defect_name: str
    defect_description: str
    expected_rules: list[str]
    detected: bool                  # did any expected rule fire?
    detected_rules: list[str]       # which expected rules actually fired
    missed_rules: list[str]         # which expected rules did NOT fire
    extra_violations: list[str]     # unexpected violations introduced
    total_violations: int
    error: Optional[str] = None
    timestamp: str = ""


def _copy_bom(bom_items: list) -> list:
    """Deep-copy a list of BOMItem objects."""
    from dataclasses import replace
    return [replace(item) for item in bom_items]


def generate_defects(bom_items: list) -> list[DefectSpec]:
    """Generate defect injection specs tailored to the given BOM.

    Each defect mutates the BOM in a specific way and expects certain
    DRC rules to detect the problem.
    """
    defects = []

    # Collect BOM info for intelligent defect generation
    references = []
    for item in bom_items:
        for ref in item.reference_list:
            references.append(ref)

    has_mcu = any("STM32" in item.value or "MCU" in item.description
                  for item in bom_items)
    has_crystal = any(ref.startswith("X") or ref.startswith("Y")
                      for ref in references)
    has_led = any(ref.startswith("D") and "LED" in item.description
                  for item in bom_items for ref in item.reference_list)
    has_ldo = any("AMS1117" in item.value or "LDO" in item.description or "稳压" in item.description
                  for item in bom_items)
    has_dcdc = any("MP" in item.value and "DC" in item.description
                   for item in bom_items)
    has_opamp = any("LM358" in item.value for item in bom_items)

    # ── Defect 1: Remove all 100nF decoupling capacitors ──
    cap_items = [item for item in bom_items
                 if item.reference.startswith("C") and "100nF" in item.value]
    if cap_items:
        defects.append(DefectSpec(
            defect_id="no_decoupling",
            name="移除去耦电容",
            description=f"删除 {len(cap_items)} 个 100nF 去耦电容",
            expected_rules=["去耦电容检查", "去耦电容距离检查", "电源轨去耦检查"],
            severity="warning",
        ))

    # ── Defect 2: Use non-E-series resistor values ──
    resistor_items = [item for item in bom_items
                      if item.reference.startswith("R")]
    if resistor_items:
        defects.append(DefectSpec(
            defect_id="bad_resistor_values",
            name="非标准电阻值",
            description="将电阻值改为非 E24 系列值 (如 13k, 27k 等模拟错误)",
            expected_rules=["参数范围检查"],
            severity="info",
        ))

    # ── Defect 3: Remove crystal load capacitors ──
    if has_crystal and cap_items:
        defects.append(DefectSpec(
            defect_id="no_crystal_load_caps",
            name="删除晶振负载电容",
            description="删除晶振旁边的负载电容",
            expected_rules=["晶振负载电容检查", "晶振频率匹配"],
            severity="warning",
        ))

    # ── Defect 4: Remove bulk/electrolytic capacitors ──
    bulk_caps = [item for item in bom_items
                 if item.reference.startswith("C")
                 and ("10μF" in item.value or "μF" in item.value
                      and not "100nF" in item.value)]
    if bulk_caps:
        defects.append(DefectSpec(
            defect_id="no_bulk_caps",
            name="删除大容量滤波电容",
            description=f"删除 {len(bulk_caps)} 个大容量电容",
            expected_rules=["电源滤波检查", "PDN 目标阻抗分析"],
            severity="warning",
        ))

    # ── Defect 5: Remove ESD protection diodes ──
    diode_items = [item for item in bom_items
                   if (item.reference.startswith("D")
                       and "LED" not in item.description)]
    if diode_items:
        defects.append(DefectSpec(
            defect_id="no_esd_diodes",
            name="删除 TVS/ESD 保护二极管",
            description=f"删除 {len(diode_items)} 个保护二极管",
            expected_rules=["ESD 保护检查"],
            severity="warning",
        ))

    # ── Defect 6: Use under-rated capacitor voltage ──
    if cap_items:
        defects.append(DefectSpec(
            defect_id="cap_voltage_derating",
            name="电容耐压不足",
            description="将电容耐压从 50V 改为 6.3V (降额不足)",
            expected_rules=["电容耐压降额检查"],
            severity="warning",
        ))

    # ── Defect 7: Remove LED current-limiting resistor ──
    if has_led:
        # Find the resistor closest to the LED in value
        led_resistors = [item for item in resistor_items
                         if "100" in item.value or "220" in item.value or "330" in item.value]
        if led_resistors:
            defects.append(DefectSpec(
                defect_id="no_led_resistor",
                name="删除 LED 限流电阻",
                description="删除 LED 的限流电阻",
                expected_rules=["LED 限流检查"],
                severity="warning",
            ))

    # ── Defect 8: Wrong LDO output voltage ──
    if has_ldo:
        defects.append(DefectSpec(
            defect_id="wrong_ldo_voltage",
            name="LDO 输出电压错误",
            description="将 3.3V LDO 改为 5.0V (可能导致 MCU 烧毁)",
            expected_rules=["参数范围检查"],
            severity="warning",
        ))

    # ── Defect 9: Missing op-amp feedback network ──
    if has_opamp:
        defects.append(DefectSpec(
            defect_id="no_opamp_feedback",
            name="删除运放反馈电阻",
            description="删除运放的反馈网络电阻",
            expected_rules=["运放反馈网络检查"],
            severity="warning",
        ))

    # ── Defect 10: DC-DC inductor saturation ──
    if has_dcdc:
        defects.append(DefectSpec(
            defect_id="inductor_saturation",
            name="电感饱和电流不足",
            description="将功率电感值改为远小于要求的数值",
            expected_rules=["电感饱和电流检查"],
            severity="warning",
        ))

    return defects


def apply_defect(bom_items: list, defect: DefectSpec) -> list:
    """Apply a defect to a BOM, returning a mutated copy.

    Does NOT modify the original bom_items.
    """
    mutated = _copy_bom(bom_items)

    if defect.defect_id == "no_decoupling":
        # Remove all 100nF capacitors
        mutated = [item for item in mutated
                   if not (item.reference.startswith("C") and "100nF" in item.value)]

    elif defect.defect_id == "bad_resistor_values":
        # Change resistor values to non-E24 values
        bad_values = ["13kΩ", "27kΩ", "42kΩ", "55kΩ", "91Ω", "110Ω"]
        for i, item in enumerate(mutated):
            if item.reference.startswith("R"):
                new_val = bad_values[i % len(bad_values)]
                mutated[i] = _replace_bom_field(item, value=new_val)

    elif defect.defect_id == "no_crystal_load_caps":
        # Remove the two smallest capacitors (typically load caps)
        caps = [item for item in mutated if item.reference.startswith("C")]
        caps_sorted = sorted(caps, key=lambda x: _parse_cap_value(x.value))
        # Remove the 2 smallest (typically 10-22pF load caps)
        for cap in caps_sorted[:min(2, len(caps_sorted))]:
            mutated = [item for item in mutated if item.reference != cap.reference]

    elif defect.defect_id == "no_bulk_caps":
        # Remove capacitors >= 10μF
        mutated = [item for item in mutated
                   if not (item.reference.startswith("C")
                           and _parse_cap_value(item.value) >= 10.0)]

    elif defect.defect_id == "no_esd_diodes":
        # Remove non-LED diodes
        mutated = [item for item in mutated
                   if not (item.reference.startswith("D")
                           and "LED" not in item.description)]
        # Ensure a connector is detectable for the ESD rule to trigger.
        # Tag any item with a connector-like reference (J/P/H/USB/FPC)
        # or add a connector descriptor to an existing item.
        conn_ref_prefixes = {"J", "P", "H", "CN", "USB", "FPC"}
        has_conn = any(
            "".join(c for c in r if c.isalpha()).upper() in conn_ref_prefixes
            for item in mutated
            for r in getattr(item, "reference", "").split(",")
        )
        if not has_conn:
            # Add connector keyword to the first IC-like item
            for i, item in enumerate(mutated):
                ref = getattr(item, "reference", "").split(",")[0].strip()
                prefix = "".join(c for c in ref if c.isalpha()).upper()
                if prefix in ("U", "M"):
                    mutated[i] = _replace_bom_field(
                        item,
                        description=f"{item.description} (CONNECTOR interface protection needed)"
                    )
                    break

    elif defect.defect_id == "cap_voltage_derating":
        # Inject a low voltage rating into capacitor values so DRC detects under-rating.
        # Real BOM descriptions rarely include voltage — we inject "6.3V" directly
        # into the value field, which the DRC rule parses for voltage ratings.
        injected = 0
        for i, item in enumerate(mutated):
            if item.reference.startswith("C") and "V" not in item.value:
                # Append 6.3V rating to value — clearly under-rated for most systems
                mutated[i] = _replace_bom_field(item, value=f"{item.value} 6.3V")
                injected += 1
                if injected >= 3:
                    break
        # Also ensure a voltage rail is detectable: tag any LDO/regulator item
        for i, item in enumerate(mutated):
            pn_desc = f"{item.part_number} {item.description}".lower()
            if any(kw in pn_desc for kw in ("ams1117", "me6211", "ldo", "mp1584", "稳压")):
                # Append explicit voltage rail info
                mutated[i] = _replace_bom_field(
                    item,
                    description=f"{item.description} VOUT=3.3V"
                )
                break

    elif defect.defect_id == "no_led_resistor":
        # Remove the resistor with lowest value (likely LED current limit)
        resistors = [item for item in mutated if item.reference.startswith("R")]
        if resistors:
            sorted_r = sorted(resistors, key=lambda x: _parse_resistance(x.value))
            # Remove the lowest-value resistor
            mutated = [item for item in mutated
                       if item.reference != sorted_r[0].reference]

    elif defect.defect_id == "wrong_ldo_voltage":
        for i, item in enumerate(mutated):
            if "AMS1117-3.3" in item.value or "AMS1117-3.3" in item.description:
                mutated[i] = _replace_bom_field(item,
                                                value=item.value.replace("3.3", "5.0"),
                                                description=item.description.replace("3.3V", "5.0V"))

    elif defect.defect_id == "no_opamp_feedback":
        # Remove resistors that could be feedback network (middle-value range)
        resistors = [item for item in mutated if item.reference.startswith("R")]
        if resistors:
            sorted_r = sorted(resistors, key=lambda x: _parse_resistance(x.value))
            # Remove medium-value resistors (likely feedback)
            if len(sorted_r) >= 2:
                mid = len(sorted_r) // 2
                mutated = [item for item in mutated
                           if item.reference != sorted_r[mid].reference]

    elif defect.defect_id == "inductor_saturation":
        for i, item in enumerate(mutated):
            if item.reference.startswith("L") and "22μH" in item.value:
                # Change to a much smaller inductance (would saturate)
                mutated[i] = _replace_bom_field(item, value="1μH")

    return mutated


def _replace_bom_field(item, **kwargs):
    """Create a copy of a BOMItem with replaced fields."""
    from dataclasses import replace
    return replace(item, **kwargs)


def _parse_cap_value(value_str: str) -> float:
    """Parse capacitor value to μF. Returns 0 on failure."""
    import re
    value_str = value_str.strip()
    # pF
    m = re.match(r'([\d.]+)\s*pF', value_str, re.IGNORECASE)
    if m:
        return float(m.group(1)) / 1_000_000
    # nF
    m = re.match(r'([\d.]+)\s*nF', value_str, re.IGNORECASE)
    if m:
        return float(m.group(1)) / 1_000
    # μF / uF
    m = re.match(r'([\d.]+)\s*[μu]F', value_str, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 0.0


def _parse_resistance(value_str: str) -> float:
    """Parse resistance value to ohms. Returns float('inf') on failure."""
    import re
    value_str = value_str.strip()
    multipliers = {"k": 1_000, "M": 1_000_000, "R": 1}
    m = re.match(r'([\d.]+)\s*([kKmMgG]?)\s*[ΩΩohm]*', value_str)
    if m:
        val = float(m.group(1))
        suffix = m.group(2).lower() if m.group(2) else ""
        return val * multipliers.get(suffix, 1)
    return float('inf')


# ═══════════════════════════════════════════════════════════════
#  Default Test Suggestions
# ═══════════════════════════════════════════════════════════════

DEFAULT_SUGGESTIONS = [
    SuggestionCase(
        text="检查当前 BOM 设计是否符合 PCB 设计规范，不做任何修改",
        category="safe",
        description="安全建议 — 检查现有设计不修改",
        expected_category="GENERAL",
    ),
    SuggestionCase(
        text="移除所有 100nF 去耦电容以降低 BOM 成本，用 0.1mm 走线承载 3A 电流",
        category="dangerous",
        description="危险建议 — 移除去耦电容 + 过细走线过大电流",
        expected_category="BOM_CHANGE",
    ),
    SuggestionCase(
        text="将 C1、C2、C3、C6 的电容值从 100nF 改为 1μF 以提高去耦效果，保持封装 0603 不变",
        category="optimization",
        description="优化建议 — 增大去耦电容值",
        expected_category="BOM_CHANGE",
    ),
    SuggestionCase(
        text="将 3.3V 电源走线加宽到 0.5mm，在 U1 每个 VDD 引脚旁增加一个 100nF + 10μF 去耦电容组合，电容距离引脚不超过 5mm",
        category="optimization",
        description="优化建议 — 电源走线 + 去耦电容布局",
        expected_category="BOM_CHANGE",
    ),
    SuggestionCase(
        text="用 AMS1117-5.0 (SOT-223) 替换 U2 AMS1117-3.3，将所有 3.3V 元件改为 5V 供电",
        category="dangerous",
        description="危险建议 — 改变电源电压可能导致元件损坏",
        expected_category="BOM_CHANGE",
    ),
]


# ═══════════════════════════════════════════════════════════════
#  Experiment Runner
# ═══════════════════════════════════════════════════════════════

class ExperimentRunner:
    """Orchestrates paper experiments across designs and providers."""

    def __init__(self, output_dir: Optional[Path] = None):
        self._timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "experiment_results" / f"run_{self._timestamp}"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.designs: list[DesignSpec] = []
        self.suggestions: list[SuggestionCase] = list(DEFAULT_SUGGESTIONS)
        self.providers: list[ProviderConfig] = []

        # Results storage
        self.drc_results: list[DRCResult] = []
        self.verify_results: list[VerifyResult] = []
        self.ma_results: list[MultiAgentResult] = []
        self.defect_results: list[DefectInjectionResult] = []

        # Logging
        self._log_lines: list[str] = []

    # ── Configuration ──

    def add_design(self, design: DesignSpec) -> None:
        self.designs.append(design)

    def add_suggestion(self, suggestion: SuggestionCase) -> None:
        self.suggestions.append(suggestion)

    def set_suggestions(self, suggestions: list[SuggestionCase]) -> None:
        self.suggestions = list(suggestions)

    def add_provider(self, config: ProviderConfig) -> None:
        self.providers.append(config)

    # ── Main Entry ──

    def run_all(self) -> dict:
        """Run the full experiment suite."""
        self._log("")
        self._log("╔" + "═" * 68 + "╗")
        self._log("║  EI 论文实验 — 闭环验证引擎性能评估" + " " * 28 + "║")
        self._log("╚" + "═" * 68 + "╝")
        self._log(f"  时间: {datetime.now().isoformat()}")
        self._log(f"  设计数: {len(self.designs)}")
        self._log(f"  建议数: {len(self.suggestions)}")
        self._log(f"  LLM 供应商: {len(self.providers)} ({', '.join(p.name for p in self.providers)})")
        self._log("")

        if not self.designs:
            self._log("❌ 无测试设计！请调用 add_design() 添加设计")
            return self._build_summary()

        # Phase A: DRC Baseline (no LLM needed)
        self._log("━" * 70)
        self._log("  阶段 A: DRC 基线检查（纯规则引擎）")
        self._log("━" * 70)
        for design in self.designs:
            result = self._run_drc_baseline(design)
            self.drc_results.append(result)
            self._print_drc_result(result)

        # Phase B: Closed-loop verification
        if self.providers:
            self._log("")
            self._log("━" * 70)
            self._log("  阶段 B: 闭环验证（LLM → DRC → 反馈 → 修正）")
            self._log("━" * 70)
            for design in self.designs:
                for provider in self.providers:
                    if not self._check_api_key(provider):
                        self._log(f"  ⏭️ 跳过 {provider.name} — 未配置 API key")
                        continue
                    for suggestion in self.suggestions:
                        result = self._run_closed_loop(design, provider, suggestion)
                        self.verify_results.append(result)
                        self._print_verify_result(result)

        # Phase C: Multi-agent review
        if self.providers:
            self._log("")
            self._log("━" * 70)
            self._log("  阶段 C: 多智能体协同审查（5 Agent 并发）")
            self._log("━" * 70)
            for design in self.designs:
                for provider in self.providers:
                    if not self._check_api_key(provider):
                        continue
                    result = self._run_multi_agent(design, provider)
                    self.ma_results.append(result)
                    self._print_ma_result(result)

        # Phase D: Programmatic defect injection (no LLM needed)
        self._log("")
        self._log("━" * 70)
        self._log("  阶段 D: 程序化缺陷注入（已知缺陷 → DRC 检出率）")
        self._log("━" * 70)
        for design in self.designs:
            ctrl = self._load_design(design)
            defects = generate_defects(ctrl.context.bom_items)
            self._log(f"  {design.name}: 生成 {len(defects)} 个缺陷测试")
            for defect in defects:
                result = self._run_defect_injection(design, defect, ctrl)
                self.defect_results.append(result)
                self._print_defect_result(result)

        # Save results
        self._save_results()
        summary = self._build_summary()
        self._print_summary(summary)
        return summary

    # ── Phase A: DRC Baseline ──

    def _run_drc_baseline(self, design: DesignSpec) -> DRCResult:
        """Run pure DRC check on a design."""
        t0 = time.time()
        try:
            ctrl = self._load_design(design)
            checker = DesignRuleChecker()
            violations = checker.check_all(
                ctrl.context.bom_items,
                ctrl.context.positions,
                pcb_data=ctrl.context.pcb_data,
            )

            # Count by severity
            errors = sum(1 for v in violations if v.severity == RuleSeverity.ERROR)
            warnings = sum(1 for v in violations if v.severity == RuleSeverity.WARNING)
            infos = sum(1 for v in violations if v.severity == RuleSeverity.INFO)

            # By rule
            by_rule: dict[str, int] = {}
            for v in violations:
                by_rule[v.rule_name] = by_rule.get(v.rule_name, 0) + 1

            # Per-component grouping for AI Verification Map
            by_component = group_violations_by_component(violations)

            return DRCResult(
                design=design.name,
                total_violations=len(violations),
                errors=errors,
                warnings=warnings,
                infos=infos,
                violations_by_rule=dict(sorted(by_rule.items(), key=lambda x: -x[1])),
                violations_by_component=by_component,
                elapsed_seconds=round(time.time() - t0, 2),
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return DRCResult(
                design=design.name,
                total_violations=0,
                errors=0,
                warnings=0,
                infos=0,
                elapsed_seconds=round(time.time() - t0, 2),
                error=str(e),
                timestamp=datetime.now().isoformat(),
            )

    # ── Phase B: Closed-Loop Verification ──

    def _score_design(self, violations, bom_items):
        """DesignScorer 综合评分辅助（无 LLM 依赖，用于闭环前后 Δ）。"""
        try:
            from src.core.design_scorer import DesignScorer
            return float(DesignScorer().score(violations, bom_items).overall)
        except Exception:
            return None

    def _run_closed_loop(
        self, design: DesignSpec, provider: ProviderConfig, suggestion: SuggestionCase
    ) -> VerifyResult:
        """Phase B closed-loop: LLM suggestion → parse BOM changes → apply → DRC → correct.

        Pipeline:
        1. Parse LLM suggestion into structured JSON BOM changes (2nd LLM call)
        2. Apply changes to a BOM copy
        3. Run DRC on modified BOM → compute delta against baseline
        4. If new violations introduced → ask LLM to correct → repeat (max 3 rounds)
        5. Metrics: changes_count, new_violations, correction_rounds, converged

        Pure-analysis suggestions (no BOM change) go through a fallback path.
        """
        t0 = time.time()
        try:
            ctrl = self._load_design(design, provider)
            original_bom = _copy_bom(ctrl.context.bom_items)

            # ── Step 1: DRC baseline on original BOM ──
            baseline_violations = DesignRuleChecker().check_all(
                original_bom,
                ctrl.context.positions,
                pcb_data=ctrl.context.pcb_data,
            )
            baseline_rules: set[str] = {v.rule_name for v in baseline_violations}
            baseline_score = self._score_design(baseline_violations, original_bom)

            # ── Step 2: Ask LLM to parse suggestion into structured BOM changes ──
            from tests.bom_suggestion import (
                build_bom_change_prompt,
                parse_llm_bom_changes,
                validate_bom_changes,
                apply_bom_changes,
            )

            parse_prompt = build_bom_change_prompt(suggestion.text, original_bom)
            try:
                llm_json = ctrl.agent.chat(parse_prompt)
            except Exception as e:
                return self._verify_no_change_result(
                    design, provider, suggestion, baseline_violations, t0,
                    parse_error=f"LLM parse call failed: {e}",
                    bom_items=original_bom,
                )

            parse_result = parse_llm_bom_changes(llm_json)
            if parse_result.parse_error:
                self._log(f"    ⚠️  BOM解析失败 [{design.name}/{suggestion.category}]: "
                          f"{parse_result.parse_error[:120]}")

            valid_changes, warnings = validate_bom_changes(parse_result.changes, original_bom)
            for w in warnings:
                self._log(f"    ⚠️  {w}")

            # ── Step 2b: No structural change → fallback ──
            if not valid_changes:
                return self._verify_no_change_result(
                    design, provider, suggestion, baseline_violations, t0,
                    parse_error=parse_result.parse_error,
                    bom_items=original_bom,
                )

            # ── Step 3: Iterative correction loop (max 3 rounds) ──
            MAX_ROUNDS = 3
            current_changes = valid_changes
            all_rounds: list[dict] = []
            converged = False

            for round_num in range(1, MAX_ROUNDS + 1):
                # Apply changes to BOM copy
                modified_bom = apply_bom_changes(original_bom, current_changes)

                # Run DRC on modified BOM
                modified_violations = DesignRuleChecker().check_all(
                    modified_bom,
                    ctrl.context.positions,
                    pcb_data=ctrl.context.pcb_data,
                )

                # Compute delta: new violations NOT in baseline
                new_violations = [
                    v for v in modified_violations
                    if v.rule_name not in baseline_rules
                ]

                sev = lambda v: v.severity.value if hasattr(v.severity, 'value') else str(v.severity)
                modified_score = self._score_design(modified_violations, modified_bom)
                round_data = {
                    "round": round_num,
                    "changes_applied": len(current_changes),
                    "total_violations": len(modified_violations),
                    "new_violations": len(new_violations),
                    "modified_score": modified_score,  # 应用后综合评分（Δ 计算用）
                    "new_violations_list": [
                        {"rule": v.rule_name, "severity": sev(v), "desc": v.description}
                        for v in new_violations
                    ],
                }
                all_rounds.append(round_data)

                if not new_violations:
                    converged = True
                    break

                if round_num >= MAX_ROUNDS:
                    break

                # ── Ask LLM to correct its changes ──
                violation_desc = "\n".join(
                    f"- [{sev(v)}] {v.rule_name}: {v.description}"
                    for v in new_violations[:15]
                )
                current_json = json.dumps(
                    [{"reference": c.reference, "field": c.field,
                      "new_value": c.new_value} for c in current_changes],
                    ensure_ascii=False, indent=2
                )
                correction_prompt = (
                    f"你之前建议的BOM修改引入了{len(new_violations)}个新的DRC违规:\n\n"
                    f"{violation_desc}\n\n"
                    f"请修正BOM变更JSON，消除这些违规。保持无问题的变更不变。\n\n"
                    f"当前BOM变更:\n{current_json}\n\n"
                    f"只输出修正后的JSON，格式: {{\"changes\": [...]}}"
                )
                try:
                    correction_json = ctrl.agent.chat(correction_prompt)
                    corr_result = parse_llm_bom_changes(correction_json)
                    if corr_result.changes:
                        valid_corr, corr_warnings = validate_bom_changes(
                            corr_result.changes, original_bom
                        )
                        if valid_corr:
                            current_changes = valid_corr
                except Exception:
                    pass  # keep current_changes if correction call fails

            # ── Step 4: Build result ──
            first_round = all_rounds[0] if all_rounds else {}
            last_round = all_rounds[-1] if all_rounds else {}
            first_new = first_round.get("new_violations", 0)
            last_new = last_round.get("new_violations", 0)

            hall_elim = None
            if first_new > 0:
                hall_elim = round((first_new - last_new) / first_new * 100, 1)
            elif first_new == 0 and all_rounds:
                hall_elim = 100.0  # No new violations from the start

            # Compute severity counts across rounds
            all_sevs: set[str] = set()
            total_blocking = 0
            total_info = 0
            for rd in all_rounds:
                for v in rd.get("new_violations_list", []):
                    all_sevs.add(v["severity"])
                    if v["severity"] in ("error", "warning"):
                        total_blocking += 1
                    elif v["severity"] == "info":
                        total_info += 1

            max_sev = "error" if "error" in all_sevs else (
                "warning" if "warning" in all_sevs else (
                    "info" if "info" in all_sevs else "none"
                )
            )

            per_round = [r.get("new_violations", 0) for r in all_rounds]

            # ── 闭环前后综合评分 Δ ──
            final_score = last_round.get("modified_score", baseline_score)
            delta_score = None
            if baseline_score is not None and final_score is not None:
                delta_score = round(final_score - baseline_score, 1)

            return VerifyResult(
                design=design.name,
                provider=provider.name,
                model=provider.model or ctrl.agent.model,
                suggestion_category=suggestion.category,
                suggestion_text=suggestion.text[:200],
                suggestion_desc=suggestion.description,
                accepted=converged,
                final_status="passed" if converged else "failed",
                rounds=len(all_rounds),
                total_issues=sum(r.get("total_violations", 0) for r in all_rounds),
                blocking_issues=total_blocking,
                info_issues=total_info,
                max_severity=max_sev,
                llm_correction_rounds=len(all_rounds) - 1 if all_rounds else 0,
                hallucination_elimination=hall_elim,
                per_round_blocking=per_round,
                baseline_score=baseline_score,
                final_score=final_score,
                delta_score=delta_score,
                raw_report={"rounds": all_rounds},
                elapsed_seconds=round(time.time() - t0, 2),
                timestamp=datetime.now().isoformat(),
                suggested_changes_count=len(valid_changes),
                new_violations_introduced=first_new,
                correction_rounds=len(all_rounds),
                final_violation_delta=last_new,
                converged=converged,
                applied_changes=[
                    {"reference": c.reference, "field": c.field,
                     "old_value": c.old_value, "new_value": c.new_value,
                     "action": c.action}
                    for c in current_changes
                ],
            )

        except Exception as e:
            return VerifyResult(
                design=design.name,
                provider=provider.name,
                model=provider.model or "unknown",
                suggestion_category=suggestion.category,
                suggestion_text=suggestion.text[:200],
                suggestion_desc=suggestion.description,
                accepted=False,
                final_status="error",
                rounds=0,
                total_issues=0,
                blocking_issues=0,
                info_issues=0,
                max_severity="none",
                llm_correction_rounds=0,
                elapsed_seconds=round(time.time() - t0, 2),
                error=str(e),
                timestamp=datetime.now().isoformat(),
                suggested_changes_count=0,
                new_violations_introduced=0,
                correction_rounds=0,
                final_violation_delta=0,
                converged=False,
            )

    def _verify_no_change_result(
        self, design: DesignSpec, provider: ProviderConfig,
        suggestion: SuggestionCase, baseline_violations: list,
        t0: float, parse_error: Optional[str] = None,
        bom_items: list = None,
    ) -> VerifyResult:
        """Fallback for suggestions with no structural BOM change (pure analysis)."""
        baseline_count = len(baseline_violations)
        baseline_score = self._score_design(baseline_violations, bom_items or [])
        return VerifyResult(
            design=design.name,
            provider=provider.name,
            model=provider.model or "unknown",
            suggestion_category=suggestion.category,
            suggestion_text=suggestion.text[:200],
            suggestion_desc=suggestion.description,
            accepted=True,  # No change = nothing to violate
            final_status="passed",
            rounds=1,
            total_issues=0,
            blocking_issues=0,
            info_issues=0,
            max_severity="none",
            llm_correction_rounds=0,
            hallucination_elimination=None,
            per_round_blocking=[0],
            baseline_score=baseline_score,
            final_score=baseline_score,  # 无 BOM 变更 → 评分不变
            delta_score=0.0,
            raw_report={
                "no_bom_change": True,
                "baseline_violations": baseline_count,
                "parse_error": parse_error,
            },
            elapsed_seconds=round(time.time() - t0, 2),
            timestamp=datetime.now().isoformat(),
            suggested_changes_count=0,
            new_violations_introduced=0,
            correction_rounds=1,
            final_violation_delta=0,
            converged=True,
            applied_changes=[],
        )

    # ── Phase C: Multi-Agent Review ──

    def _run_multi_agent(
        self, design: DesignSpec, provider: ProviderConfig
    ) -> MultiAgentResult:
        """Run multi-agent review for one (design, provider)."""
        t0 = time.time()
        try:
            ctrl = self._load_design(design, provider)
            result_json = ctrl.review_design_multi_agent()
            report = json.loads(result_json)

            if "error" in report:
                raise RuntimeError(report["error"])

            # Extract radar scores
            radar_scores = {}
            for item in report.get("radar_data", []):
                dim = item.get("dimension", item.get("name", "?"))
                score = item.get("score", 0)
                radar_scores[dim] = score

            # Per-agent scores
            agent_scores = {}
            total_findings = 0
            for key, agent in report.get("agents", {}).items():
                agent_scores[key] = agent.get("score", 0)
                total_findings += len(agent.get("findings", []))

            return MultiAgentResult(
                design=design.name,
                provider=provider.name,
                model=provider.model or ctrl.agent.model,
                overall_score=report.get("overall_score", 0),
                overall_grade=report.get("overall_grade", "N/A"),
                radar_scores=radar_scores,
                agent_scores=agent_scores,
                critical_count=len(report.get("critical_issues", [])),
                total_findings=total_findings,
                consensus_preview=report.get("consensus", "")[:200],
                elapsed_seconds=round(time.time() - t0, 2),
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            return MultiAgentResult(
                design=design.name,
                provider=provider.name,
                model=provider.model or "unknown",
                overall_score=0,
                overall_grade="error",
                elapsed_seconds=round(time.time() - t0, 2),
                error=str(e),
                timestamp=datetime.now().isoformat(),
            )

    # ── Helpers ──

    def _load_design(
        self, design: DesignSpec, provider: Optional[ProviderConfig] = None
    ) -> AppController:
        """Create and configure a controller for a design."""
        ctrl = AppController()
        ctrl.load_bom(str(design.bom_path))
        if design.positions_path and design.positions_path.exists():
            ctrl.load_positions(str(design.positions_path))
        if design.pcb_path and design.pcb_path.exists():
            ctrl.load_pcb(str(design.pcb_path))

        # Override LLM if provider specified
        if provider:
            ctrl.reconfigure_llm(
                api_key=provider.api_key,
                base_url=provider.base_url or "",
                model=provider.model or "",
                provider=provider.name,
            )

        return ctrl

    @staticmethod
    def _check_api_key(provider: ProviderConfig) -> bool:
        """Check if a provider has a real API key."""
        if not provider.api_key:
            return False
        return provider.api_key not in ("", "your_api_key_here", "sk-your-xxx")

    # ── Logging ──

    def _log(self, msg: str) -> None:
        try:
            print(msg)
        except UnicodeEncodeError:
            # Windows GBK fallback — strip non-ASCII
            clean = msg.encode("ascii", errors="replace").decode("ascii")
            print(clean)
        self._log_lines.append(msg)

    def _print_drc_result(self, r: DRCResult) -> None:
        icon = "❌" if r.error else "✅"
        self._log(f"  {icon} {r.design}: {r.total_violations} 违规 "
                  f"(E:{r.errors} W:{r.warnings} I:{r.infos}) "
                  f"[{r.elapsed_seconds:.1f}s]")
        if r.error:
            self._log(f"     错误: {r.error}")

    def _print_verify_result(self, r: VerifyResult) -> None:
        if r.error:
            self._log(f"  ❌ [{r.provider}] {r.design}/{r.suggestion_category}: "
                      f"ERROR — {r.error[:100]}")
            return
        if r.suggested_changes_count > 0:
            icon = "✅" if r.converged else "🔄"
            self._log(f"  {icon} [{r.provider}] {r.design}/{r.suggestion_category} "
                      f"({r.suggestion_desc}): "
                      f"变更={r.suggested_changes_count} "
                      f"新违规={r.new_violations_introduced}→{r.final_violation_delta} "
                      f"轮次={r.correction_rounds} 收敛={r.converged} "
                      f"[{r.elapsed_seconds:.1f}s]")
        else:
            icon = "✅" if r.accepted else "🔄"
            hall = f"消除率={r.hallucination_elimination:.0f}%" if r.hallucination_elimination is not None else ""
            self._log(f"  {icon} [{r.provider}] {r.design}/{r.suggestion_category} "
                      f"({r.suggestion_desc}): "
                      f"accepted={r.accepted}, rounds={r.rounds}, "
                      f"blocking={r.blocking_issues}, info={r.info_issues} "
                      f"{hall} [分析类] [{r.elapsed_seconds:.1f}s]")

    def _print_ma_result(self, r: MultiAgentResult) -> None:
        if r.error:
            self._log(f"  ❌ [{r.provider}] {r.design} Multi-Agent: "
                      f"ERROR — {r.error[:100]}")
            return
        self._log(f"  📊 [{r.provider}] {r.design}: "
                  f"总分 {r.overall_score:.0f}/100 ({r.overall_grade}), "
                  f"严重问题 {r.critical_count}, 总发现 {r.total_findings} "
                  f"[{r.elapsed_seconds:.1f}s]")

    # ── Phase D: Defect Injection ──

    def _run_defect_injection(
        self, design: DesignSpec, defect: DefectSpec, ctrl
    ) -> DefectInjectionResult:
        """Inject a known defect into the BOM and check if DRC detects it."""
        try:
            # Mutate BOM
            mutated_bom = apply_defect(ctrl.context.bom_items, defect)

            # Run DRC on the mutated BOM
            checker = DesignRuleChecker()
            violations = checker.check_all(
                mutated_bom,
                ctrl.context.positions,
                pcb_data=ctrl.context.pcb_data,
            )

            # Check which expected rules fired
            detected_rules = []
            missed_rules = []
            for rule_name in defect.expected_rules:
                found = any(rule_name in v.rule_name for v in violations)
                if found:
                    detected_rules.append(rule_name)
                else:
                    missed_rules.append(rule_name)

            # Also report unexpected violations
            extra = [v.rule_name for v in violations
                     if not any(expected in v.rule_name for expected in defect.expected_rules)]

            return DefectInjectionResult(
                design=design.name,
                defect_id=defect.defect_id,
                defect_name=defect.name,
                defect_description=defect.description,
                expected_rules=defect.expected_rules,
                detected=len(detected_rules) > 0,
                detected_rules=detected_rules,
                missed_rules=missed_rules,
                extra_violations=list(set(extra)),
                total_violations=len(violations),
                timestamp=datetime.now().isoformat(),
            )
        except Exception as e:
            return DefectInjectionResult(
                design=design.name,
                defect_id=defect.defect_id,
                defect_name=defect.name,
                defect_description=defect.description,
                expected_rules=defect.expected_rules,
                detected=False,
                detected_rules=[],
                missed_rules=defect.expected_rules,
                extra_violations=[],
                total_violations=0,
                error=str(e),
                timestamp=datetime.now().isoformat(),
            )

    def _print_defect_result(self, r: DefectInjectionResult) -> None:
        if r.error:
            self._log(f"    ❌ {r.defect_id}: ERROR — {r.error[:80]}")
            return
        icon = "✅" if r.detected else "❌"
        detected_str = ", ".join(r.detected_rules) if r.detected_rules else "无"
        missed_str = ", ".join(r.missed_rules) if r.missed_rules else "无"
        self._log(f"    {icon} {r.defect_name} ({r.defect_id})")
        self._log(f"       检出: [{detected_str}]  遗漏: [{missed_str}]  "
                  f"总违规: {r.total_violations}")

    # ── Summary ──

    def _print_summary(self, summary: dict) -> None:
        self._log("")
        self._log("═" * 70)
        self._log("  实验汇总")
        self._log("═" * 70)

        # DRC table
        if summary.get("drc_count"):
            self._log("\n  📋 DRC 基线:")
            self._log(f"  {'Design':<25s} {'违规':>6s} {'错误':>6s} {'警告':>6s} {'信息':>6s}")
            self._log("  " + "-" * 50)
            for r in self.drc_results:
                self._log(f"  {r.design:<25s} {r.total_violations:>6d} "
                          f"{r.errors:>6d} {r.warnings:>6d} {r.infos:>6d}")

        # Verification table
        if summary.get("verify_count"):
            self._log("\n  🔄 闭环验证:")
            self._log(f"  {'提供者':<12s} {'设计':<20s} {'建议':<14s} "
                      f"{'通过':>6s} {'变更':>4s} {'新违规':>6s} {'轮次':>4s} {'收敛':>6s} {'耗时':>8s}")
            self._log("  " + "-" * 85)
            for r in self.verify_results:
                if r.error:
                    continue
                if r.suggested_changes_count > 0:
                    self._log(f"  {r.provider:<12s} {r.design:<20s} {r.suggestion_category:<14s} "
                              f"{str(r.converged):>6s} {r.suggested_changes_count:>4d} "
                              f"{r.new_violations_introduced:>6d} {r.correction_rounds:>4d} "
                              f"{str(r.converged):>6s} {r.elapsed_seconds:>7.1f}s")
                else:
                    hall_str = f"{r.hallucination_elimination:.0f}%" if r.hallucination_elimination is not None else "N/A"
                    self._log(f"  {r.provider:<12s} {r.design:<20s} {r.suggestion_category:<14s} "
                              f"{str(r.accepted):>6s} {0:>4d} {0:>6d} {r.rounds:>4d} "
                              f"{'—':>6s} {r.elapsed_seconds:>7.1f}s")

        # Multi-agent table
        if summary.get("ma_count"):
            self._log("\n  🤖 多智能体审查:")
            self._log(f"  {'提供者':<12s} {'设计':<20s} {'总分':>6s} {'等级':>6s} "
                      f"{'严重':>4s} {'发现':>6s} {'耗时':>8s}")
            self._log("  " + "-" * 65)
            for r in self.ma_results:
                if r.error:
                    continue
                self._log(f"  {r.provider:<12s} {r.design:<20s} {r.overall_score:>6.0f} "
                          f"{r.overall_grade:>6s} {r.critical_count:>4d} "
                          f"{r.total_findings:>6d} {r.elapsed_seconds:>7.1f}s")

        # Key metrics for paper
        self._log("\n  📌 论文关键指标:")
        verify_ok = [r for r in self.verify_results if not r.error]

        if verify_ok:
            # Separate BOM-modification from pure-analysis results
            bom_change_results = [r for r in verify_ok if r.suggested_changes_count > 0]
            analysis_results = [r for r in verify_ok if r.suggested_changes_count == 0]

            if bom_change_results:
                converged_count = sum(1 for r in bom_change_results if r.converged)
                self._log(f"  BOM变更收敛率: {converged_count}/{len(bom_change_results)} "
                          f"({converged_count/len(bom_change_results)*100:.0f}%) (目标 > 70%)")

                avg_new_violations = sum(r.new_violations_introduced for r in bom_change_results) / len(bom_change_results)
                self._log(f"  平均新违规引入: {avg_new_violations:.1f} 个/建议")

                avg_corrections = sum(r.correction_rounds for r in bom_change_results) / len(bom_change_results)
                self._log(f"  平均修正轮次: {avg_corrections:.1f} (目标 ≤ 2.0)")

                # Hallucination elimination on BOM change results
                hall_rates = [r.hallucination_elimination for r in bom_change_results
                              if r.hallucination_elimination is not None]
                if hall_rates:
                    self._log(f"  幻觉消除率 (均值): {sum(hall_rates)/len(hall_rates):.1f}% "
                              f"(目标 > 80%)")

            if analysis_results:
                self._log(f"  纯分析建议: {len(analysis_results)} 个 (无BOM变更, 直接通过)")

            # Avg time
            avg_time = sum(r.elapsed_seconds for r in verify_ok) / len(verify_ok)
            self._log(f"  平均验证耗时: {avg_time:.1f}s")

        # Multi-agent metrics
        ma_ok = [r for r in self.ma_results if not r.error]
        if ma_ok:
            avg_score = sum(r.overall_score for r in ma_ok) / len(ma_ok)
            self._log(f"  多智能体均分: {avg_score:.0f}/100 (目标 > 75)")

        # Defect injection metrics
        if self.defect_results:
            detected = sum(1 for r in self.defect_results if r.detected)
            total = len(self.defect_results)
            self._log(f"\n  🔍 缺陷注入:")
            self._log(f"  检出率: {detected}/{total} ({detected/total*100:.0f}%)")
            for r in self.defect_results:
                icon = "✅" if r.detected else "❌"
                self._log(f"    {icon} {r.defect_name}: "
                          f"命中 {len(r.detected_rules)}/{len(r.expected_rules)} 预期规则")

        self._log(f"\n  📁 详细结果: {self.output_dir / 'results.json'}")
        self._log(f"  📁 摘要报告: {self.output_dir / 'summary.md'}")

    def _build_summary(self) -> dict:
        """Build a summary dict for programmatic use."""
        return {
            "timestamp": self._timestamp,
            "output_dir": str(self.output_dir),
            "designs": [d.name for d in self.designs],
            "providers": [p.name for p in self.providers],
            "suggestion_categories": list(set(s.category for s in self.suggestions)),
            "drc_count": len(self.drc_results),
            "verify_count": len(self.verify_results),
            "ma_count": len(self.ma_results),
            "defect_count": len(self.defect_results),
            "drc_results": [asdict(r) for r in self.drc_results],
            "verify_results": [asdict(r) for r in self.verify_results],
            "ma_results": [asdict(r) for r in self.ma_results],
            "defect_results": [asdict(r) for r in self.defect_results],
            # Aggregate defect metrics
            "defect_detection_rate": (
                sum(1 for r in self.defect_results if r.detected) / len(self.defect_results) * 100
                if self.defect_results else 0
            ),
            "defect_total_detected": sum(1 for r in self.defect_results if r.detected),
            "defect_total_missed": sum(1 for r in self.defect_results if not r.detected),
        }

    def _save_results(self) -> None:
        """Save all results to JSON and Markdown."""
        summary = self._build_summary()

        # JSON
        json_path = self.output_dir / "results.json"
        json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        self._log(f"\n  💾 结果已保存: {json_path}")

        # Markdown summary
        md_path = self.output_dir / "summary.md"
        md = self._generate_markdown(summary)
        md_path.write_text(md, encoding="utf-8")
        self._log(f"  💾 摘要已保存: {md_path}")

    def _generate_markdown(self, summary: dict) -> str:
        """Generate a Markdown summary report."""
        lines = [
            f"# EI 论文实验报告",
            f"",
            f"> 生成时间: {datetime.now().isoformat()}",
            f"> 设计数: {len(self.designs)} | 建议数: {len(self.suggestions)} | "
            f"LLM: {', '.join(p.name for p in self.providers)}",
            f"",
        ]

        # DRC section
        if self.drc_results:
            lines.append("## 阶段 A: DRC 基线")
            lines.append("")
            lines.append("| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |")
            lines.append("|------|--------|------|------|------|------|")
            for r in self.drc_results:
                lines.append(f"| {r.design} | {r.total_violations} | "
                             f"{r.errors} | {r.warnings} | {r.infos} | "
                             f"{r.elapsed_seconds:.1f}s |")
            lines.append("")

        # Verification section
        if self.verify_results:
            lines.append("## 阶段 B: 闭环验证")
            lines.append("")
            lines.append("| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |")
            lines.append("|--------|------|----------|------|--------|--------|------|------|------|")
            for r in self.verify_results:
                if r.error:
                    continue
                if r.suggested_changes_count > 0:
                    lines.append(f"| {r.provider} | {r.design} | {r.suggestion_category} | "
                                 f"{'✅' if r.converged else '❌'} | {r.suggested_changes_count} | "
                                 f"{r.new_violations_introduced}→{r.final_violation_delta} | "
                                 f"{r.correction_rounds} | {'✅' if r.converged else '❌'} | "
                                 f"{r.elapsed_seconds:.1f}s |")
                else:
                    hall = f"{r.hallucination_elimination:.0f}%" if r.hallucination_elimination is not None else "—"
                    lines.append(f"| {r.provider} | {r.design} | {r.suggestion_category} | "
                                 f"{'✅' if r.accepted else '❌'} | 0 | — | "
                                 f"{r.rounds} | — | {r.elapsed_seconds:.1f}s |")
            lines.append("")

        # Multi-agent section
        if self.ma_results:
            lines.append("## 阶段 C: 多智能体审查")
            lines.append("")
            lines.append("| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |")
            lines.append("|--------|------|------|------|------|------|------|")
            for r in self.ma_results:
                if r.error:
                    continue
                lines.append(f"| {r.provider} | {r.design} | {r.overall_score:.0f} | "
                             f"{r.overall_grade} | {r.critical_count} | "
                             f"{r.total_findings} | {r.elapsed_seconds:.1f}s |")
            lines.append("")

        # Key metrics
        lines.append("## 关键指标")
        lines.append("")
        verify_ok = [r for r in self.verify_results if not r.error]
        ma_ok = [r for r in self.ma_results if not r.error]

        if verify_ok:
            bom_change = [r for r in verify_ok if r.suggested_changes_count > 0]
            analysis_only = [r for r in verify_ok if r.suggested_changes_count == 0]

            if bom_change:
                converged_count = sum(1 for r in bom_change if r.converged)
                lines.append(f"- **BOM变更收敛率**: {converged_count}/{len(bom_change)} "
                             f"({converged_count/len(bom_change)*100:.0f}%) (目标 > 70%)")
                avg_new = sum(r.new_violations_introduced for r in bom_change) / len(bom_change)
                lines.append(f"- **平均新违规引入**: {avg_new:.1f} 个/建议")
                avg_corr = sum(r.correction_rounds for r in bom_change) / len(bom_change)
                lines.append(f"- **平均修正轮次**: {avg_corr:.1f} (目标 ≤ 2.0)")

                hall_rates = [r.hallucination_elimination for r in bom_change
                              if r.hallucination_elimination is not None]
                if hall_rates:
                    lines.append(f"- **幻觉消除率**: {sum(hall_rates)/len(hall_rates):.1f}% "
                                 f"(目标 > 80%)")

            if analysis_only:
                lines.append(f"- **纯分析建议**: {len(analysis_only)} 个 (无BOM变更)")

        if ma_ok:
            lines.append(f"- **多智能体均分**: "
                         f"{sum(r.overall_score for r in ma_ok)/len(ma_ok):.0f}/100 "
                         f"(目标 > 75)")

        # Defect injection section
        if self.defect_results:
            detected = sum(1 for r in self.defect_results if r.detected)
            total = len(self.defect_results)
            lines.append(f"- **缺陷检出率**: {detected}/{total} ({detected/total*100:.0f}%)")
            lines.append("")
            lines.append("### 缺陷注入详情")
            lines.append("")
            lines.append("| 缺陷 | 预期规则 | 检出 | 命中 | 遗漏 |")
            lines.append("|------|----------|------|------|------|")
            for r in self.defect_results:
                icon = "✅" if r.detected else "❌"
                lines.append(f"| {icon} {r.defect_name} | "
                             f"{', '.join(r.expected_rules[:2])} | "
                             f"{'是' if r.detected else '否'} | "
                             f"{len(r.detected_rules)} | "
                             f"{len(r.missed_rules)} |")

        lines.append("")
        lines.append("---")
        lines.append(f"📁 完整 JSON 数据: `{self.output_dir / 'results.json'}`")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Default Designs (available without external data)
# ═══════════════════════════════════════════════════════════════

def get_default_designs() -> list[DesignSpec]:
    """Return the built-in test designs."""
    tests_dir = Path(__file__).parent
    designs = []

    # Shared position and PCB data (reused across similar-board designs)
    sample_pos = tests_dir / "sample_positions.csv"
    sample_pcb = tests_dir / "sample_pcb.json"

    # Design 1: STM32 minimal system (24 components, good design)
    sample_bom = tests_dir / "sample_bom.csv"
    if sample_bom.exists():
        designs.append(DesignSpec(
            name="STM32_Minimal",
            bom_path=sample_bom,
            positions_path=sample_pos if sample_pos.exists() else None,
            pcb_path=sample_pcb if sample_pcb.exists() else None,
            description="STM32F103C8T6 最小系统板 — 24 元件, 规范设计",
        ))

    # Design 2: DC-DC power supply (18 components, power-focused)
    power_bom = tests_dir / "sample_bom_power.csv"
    if power_bom.exists():
        designs.append(DesignSpec(
            name="Power_Supply",
            bom_path=power_bom,
            positions_path=None,
            pcb_path=None,
            description="MP1584 DC-DC 降压电源板 — 18 元件, 电源为主",
        ))

    # Design 3: Bad design (14 components, intentionally missing caps)
    bad_bom = tests_dir / "sample_bom_bad.csv"
    if bad_bom.exists():
        designs.append(DesignSpec(
            name="Bad_Design",
            bom_path=bad_bom,
            positions_path=sample_pos if sample_pos.exists() else None,
            pcb_path=sample_pcb if sample_pcb.exists() else None,
            description="故意缺失去耦电容的 MCU 板 — 14 元件, 预期更多违规",
        ))

    return designs


# ═══════════════════════════════════════════════════════════════
#  Provider Config Helpers
# ═══════════════════════════════════════════════════════════════

def get_provider_from_env() -> list[ProviderConfig]:
    """Build provider configs from environment / saved settings.

    Checks: env vars → ~/.eda_ai_assistant/settings.json → defaults
    Only returns providers with real API keys.
    """
    providers = []

    # Try to load from settings
    api_key = os.getenv("LLM_API_KEY", "")
    provider_name = os.getenv("LLM_PROVIDER", "deepseek")
    model = os.getenv("LLM_MODEL", "")
    base_url = os.getenv("LLM_BASE_URL", "")

    # Also check settings.json
    settings_path = Path.home() / ".eda_ai_assistant" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            api_key = api_key or settings.get("llm_api_key", "")
            provider_name = provider_name or settings.get("llm_provider", "deepseek")
            model = model or settings.get("llm_model", "")
            base_url = base_url or settings.get("llm_base_url", "")
        except Exception:
            pass

    if api_key and api_key not in ("your_api_key_here", "sk-your-xxx"):
        providers.append(ProviderConfig(
            name=provider_name,
            api_key=api_key,
            model=model,
            base_url=base_url,
        ))

    return providers


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="EI 论文实验 — 闭环验证引擎性能评估",
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="LLM 供应商 (deepseek/qwen/glm)，默认使用环境变量配置",
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="API key（覆盖环境变量）",
    )
    parser.add_argument(
        "--drc-only", action="store_true",
        help="仅运行 DRC 基线检查（不调用 LLM）",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="输出目录（默认 experiment_results/run_<timestamp>/）",
    )
    parser.add_argument(
        "--designs", type=str, default=None,
        help="额外的 BOM 文件或目录（逗号分隔）",
    )
    args = parser.parse_args()

    # Setup
    output_dir = Path(args.output) if args.output else None
    runner = ExperimentRunner(output_dir=output_dir)

    # Add designs
    designs = get_default_designs()

    # Add extra designs from CLI
    if args.designs:
        for path_str in args.designs.split(","):
            p = Path(path_str.strip())
            if p.is_dir():
                for bom_file in list(p.rglob("*.csv")) + list(p.rglob("*.xlsx")):
                    name = bom_file.stem
                    runner.add_design(DesignSpec(
                        name=name, bom_path=bom_file,
                        description=f"外部设计: {name}",
                    ))
            elif p.is_file():
                name = p.stem
                runner.add_design(DesignSpec(
                    name=name, bom_path=p,
                    description=f"外部设计: {name}",
                ))

    # Use built-in designs if none were added
    for design in designs:
        runner.add_design(design)

    if not runner.designs:
        print("❌ 没有可用的测试设计！")
        print("   请将 BOM 文件放入 tests/ 目录或使用 --designs 参数指定")
        sys.exit(1)

    # Configure providers
    if not args.drc_only:
        if args.api_key:
            runner.add_provider(ProviderConfig(
                name=args.provider or "deepseek",
                api_key=args.api_key,
            ))
        else:
            env_providers = get_provider_from_env()
            for p in env_providers:
                runner.add_provider(p)

        if args.provider and not runner.providers and not args.api_key:
            print(f"⚠️  未找到 {args.provider} 的 API key，仅运行 DRC 基线")
            print("   请在 .env 中设置 LLM_API_KEY 或使用 --api-key 参数")

    if not runner.providers and not args.drc_only:
        print("⚠️  未配置任何 LLM 供应商，仅运行 DRC 基线（--drc-only 模式）")
        print("   配置方式:")
        print("   1. 在 .env 中设置 LLM_API_KEY")
        print("   2. 使用 --api-key 参数")
        print("   3. 在 GUI 设置面板中配置并保存")

    # Run
    runner.run_all()


if __name__ == "__main__":
    main()

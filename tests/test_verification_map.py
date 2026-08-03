"""
AI Verification Map 单元测试

测试覆盖:
- shared.py: prepare_component_data, calculate_board_stats
- verification_map.py: VerificationMapGenerator, _prepare_overlay_data
- checker.py: group_violations_by_component
- paper_experiments.py: DRCResult.violations_by_component field
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.html_bom.shared import prepare_component_data, calculate_board_stats
from src.html_bom.verification_map import (
    VerificationMapConfig,
    VerificationMapGenerator,
    _classify_safety,
)
from src.rules.checker import (
    DesignRuleChecker,
    RuleViolation,
    RuleSeverity,
    group_violations_by_component,
)


# ═══════════════════════════════════════════════════════════════
#  Fake BOM item for testing
# ═══════════════════════════════════════════════════════════════

@dataclass
class FakeBOMItem:
    reference: str = ""
    value: str = ""
    package: str = ""
    part_number: str = ""
    description: str = ""


# ═══════════════════════════════════════════════════════════════
#  shared.py tests
# ═══════════════════════════════════════════════════════════════

class TestShared:
    """Tests for src/html_bom/shared.py"""

    def test_calculate_board_stats_empty(self):
        result = calculate_board_stats({})
        assert result["total"] == 0
        assert result["width_mm"] == 0

    def test_calculate_board_stats(self):
        positions = {
            "R1": {"x": 0, "y": 0, "layer": "Top"},
            "R2": {"x": 50, "y": 30, "layer": "Top"},
            "C1": {"x": 10, "y": 10, "layer": "Bottom"},
        }
        result = calculate_board_stats(positions)
        assert result["total"] == 3
        assert result["top_count"] == 2
        assert result["bottom_count"] == 1
        assert result["width_mm"] == 50
        assert result["height_mm"] == 30

    def test_prepare_component_data(self):
        items = [
            FakeBOMItem(reference="R1,R2", value="10kΩ", package="0603", part_number="PN1", description="Resistor"),
            FakeBOMItem(reference="C1", value="100nF", package="0402", part_number="PN2", description="Capacitor"),
        ]
        positions = {
            "R1": {"x": 10, "y": 20, "rotation": 0, "layer": "Top"},
            "R2": {"x": 15, "y": 20, "rotation": 90, "layer": "Top"},
        }
        result = prepare_component_data(items, positions)
        assert len(result) == 3  # R1, R2, C1
        r1 = result[0]
        assert r1["reference"] == "R1"
        assert r1["value"] == "10kΩ"
        assert r1["has_position"] is True
        c1 = result[2]
        assert c1["reference"] == "C1"
        assert c1["has_position"] is False


# ═══════════════════════════════════════════════════════════════
#  checker.py: group_violations_by_component tests
# ═══════════════════════════════════════════════════════════════

class TestGroupViolationsByComponent:
    """Tests for group_violations_by_component()"""

    def test_empty(self):
        assert group_violations_by_component([]) == {}

    def test_with_component_ref(self):
        violations = [
            RuleViolation(
                rule_name="去耦电容检查",
                description="IC U1 缺少 100nF 高频去耦电容",
                severity=RuleSeverity.ERROR,
                location="U1",
                suggestion="在 U1 电源引脚附近放置 100nF MLCC",
                theory="IC 晶体管开关产生 di/dt 瞬态",
            ),
            RuleViolation(
                rule_name="晶振负载电容检查",
                description="晶振 X1 负载电容不足",
                severity=RuleSeverity.WARNING,
                location="X1",
                suggestion="晶振需 2 个匹配负载电容",
            ),
        ]
        result = group_violations_by_component(violations)
        assert "U1" in result
        assert "X1" in result
        assert len(result["U1"]) == 1
        assert result["U1"][0]["rule"] == "去耦电容检查"
        assert result["U1"][0]["severity"] == "error"
        assert result["X1"][0]["severity"] == "warning"

    def test_multi_ref_location(self):
        """Location with multiple refs like 'R5,C3'."""
        violations = [
            RuleViolation(
                rule_name="电源滤波检查",
                description="缺少滤波电容",
                severity=RuleSeverity.WARNING,
                location="R5, C3",
                suggestion="添加电容",
            ),
        ]
        result = group_violations_by_component(violations)
        assert "R5" in result
        assert "C3" in result

    def test_no_location(self):
        """Violations with empty location go to __board__."""
        violations = [
            RuleViolation(
                rule_name="EMI 滤波检查",
                description="电源入口缺少 EMI 滤波器件",
                severity=RuleSeverity.INFO,
                location="",
                suggestion="添加 EMI 滤波",
            ),
        ]
        result = group_violations_by_component(violations)
        assert "__board__" in result
        assert len(result["__board__"]) == 1
        assert result["__board__"][0]["rule"] == "EMI 滤波检查"


# ═══════════════════════════════════════════════════════════════
#  verification_map.py: generator tests
# ═══════════════════════════════════════════════════════════════

class TestVerificationMapGenerator:
    """Tests for VerificationMapGenerator"""

    def test_config_defaults(self):
        config = VerificationMapConfig()
        assert config.title == "AI Verification Map"
        assert config.show_drc_heatmap is True
        assert config.show_ai_changes is True

    def test_prepare_overlay_data_empty(self):
        result = VerificationMapGenerator._prepare_overlay_data()
        assert result["drc_heatmap"] == {}
        assert result["ai_changes"] == []
        assert result["agent_findings"] == []
        assert result["defect_results"] == []
        assert result["stats"] == {}

    def test_prepare_overlay_data_drc(self):
        drc = {
            "design": "test_design",
            "total_violations": 3,
            "errors": 1,
            "warnings": 1,
            "infos": 1,
            "violations_by_rule": {"ruleA": 2, "ruleB": 1},
            "violations_by_component": {
                "U1": [
                    {"rule": "去耦电容检查", "severity": "error",
                     "desc": "缺电容", "suggestion": "加电容", "theory": ""},
                ],
                "R5": [
                    {"rule": "参数范围检查", "severity": "warning",
                     "desc": "非标值", "suggestion": "改值", "theory": ""},
                ],
                "__board__": [
                    {"rule": "EMI 滤波检查", "severity": "info",
                     "desc": "缺EMI滤波", "suggestion": "", "theory": ""},
                ],
            },
        }
        result = VerificationMapGenerator._prepare_overlay_data(drc_results=drc)
        assert "U1" in result["drc_heatmap"]
        assert result["drc_heatmap"]["U1"]["max_severity"] == "error"
        assert result["drc_heatmap"]["U1"]["count"] == 1
        assert "__board__" not in result["drc_heatmap"]  # board-level excluded
        assert result["board_violations"] == drc["violations_by_component"]["__board__"]
        assert result["stats"]["total_errors"] == 1
        assert result["stats"]["total_violations"] == 3

    def test_prepare_overlay_data_verify(self):
        verify = [
            {
                "design": "test",
                "provider": "deepseek",
                "suggestion_category": "dangerous",
                "suggestion_desc": "危险建议",
                "converged": False,
                "suggested_changes_count": 8,
                "new_violations_introduced": 1,
                "correction_rounds": 3,
                "applied_changes": [
                    {"reference": "C1", "field": "value", "old_value": "100nF", "new_value": "1μF", "action": "replace"},
                    {"reference": "C3", "field": "value", "old_value": "100nF", "new_value": "1μF", "action": "replace"},
                ],
                "error": None,
            },
            {
                "design": "test2",
                "provider": "deepseek",
                "suggestion_category": "safe",
                "suggestion_desc": "纯分析建议",
                "converged": True,
                "suggested_changes_count": 0,
                "new_violations_introduced": 0,
                "correction_rounds": 1,
                "applied_changes": [],
                "error": None,
            },
        ]
        result = VerificationMapGenerator._prepare_overlay_data(verify_results=verify)
        assert len(result["ai_changes"]) == 2
        # First: dangerous change
        ch0 = result["ai_changes"][0]
        assert ch0["safety"] == "dangerous"
        assert ch0["converged"] is False
        assert "C1" in ch0["refs"]
        assert "C3" in ch0["refs"]
        # Second: pure analysis
        ch1 = result["ai_changes"][1]
        assert ch1["safety"] == "analysis"
        assert ch1["changes"] == []

    def test_prepare_overlay_data_ma(self):
        ma = [
            {
                "design": "test",
                "overall_score": 75,
                "overall_grade": "B",
                "critical_count": 1,
                "total_findings": 10,
                "radar_scores": {"电路完整性": 80, "热管理": 70},
                "consensus_preview": "建议检查 U1 和 R5 的去耦电容配置",
                "error": None,
            },
        ]
        result = VerificationMapGenerator._prepare_overlay_data(ma_results=ma)
        # Check that refs are extracted from consensus
        findings = result["agent_findings"]
        # U1 and R5 should be extracted
        refs = [f["ref"] for f in findings]
        assert "U1" in refs or "R5" in refs
        assert result["stats"]["avg_score"] == 75
        assert result["stats"]["total_ma_reviews"] == 1

    def test_classify_safety(self):
        assert _classify_safety({"suggested_changes_count": 0}) == "analysis"
        assert _classify_safety({
            "suggested_changes_count": 3, "converged": True, "new_violations_introduced": 0
        }) == "safe"
        assert _classify_safety({
            "suggested_changes_count": 5, "converged": True, "new_violations_introduced": 2
        }) == "warning"
        assert _classify_safety({
            "suggested_changes_count": 8, "converged": False, "new_violations_introduced": 3
        }) == "dangerous"

    def test_generate_creates_html(self, tmp_path):
        """Verify generate() produces valid HTML with component data embedded."""
        config = VerificationMapConfig(title="Test Map")
        gen = VerificationMapGenerator(config=config)

        items = [
            FakeBOMItem(reference="R1", value="10kΩ", package="0603"),
            FakeBOMItem(reference="C1", value="100nF", package="0402"),
        ]
        positions = {
            "R1": {"x": 10, "y": 20, "rotation": 0, "layer": "Top"},
        }
        overlay = VerificationMapGenerator._prepare_overlay_data()

        output = tmp_path / "test_vmap.html"
        html = gen.generate(items, positions, overlay, output_path=str(output))

        assert output.exists()
        assert "Test Map" in html
        assert "R1" in html
        assert "C1" in html
        assert "verification_map" in html.lower() or "AI Verification" in html

    def test_generate_string_only(self):
        """generate() returns string even without output_path."""
        gen = VerificationMapGenerator()
        items = [FakeBOMItem(reference="U1", value="STM32", package="LQFP-48")]
        positions = {"U1": {"x": 25, "y": 25, "rotation": 0, "layer": "Top"}}
        overlay = VerificationMapGenerator._prepare_overlay_data()

        html = gen.generate(items, positions, overlay)
        assert isinstance(html, str)
        assert len(html) > 1000
        assert "<html" in html.lower()
        assert "U1" in html


# ═══════════════════════════════════════════════════════════════
#  paper_experiments.py: DRCResult field tests
# ═══════════════════════════════════════════════════════════════

class TestDRCResultFields:
    """Verify DRCResult and VerifyResult have new AI Verification Map fields."""

    def test_drc_result_has_violations_by_component(self):
        from tests.paper_experiments import DRCResult
        r = DRCResult(design="test", total_violations=0, errors=0, warnings=0, infos=0)
        assert hasattr(r, "violations_by_component")
        assert r.violations_by_component == {}

    def test_verify_result_has_applied_changes(self):
        from tests.paper_experiments import VerifyResult
        r = VerifyResult(
            design="test", provider="deepseek", model="test",
            suggestion_category="safe", suggestion_text="test", suggestion_desc="test",
            accepted=True, final_status="passed", rounds=0,
            total_issues=0, blocking_issues=0, info_issues=0, max_severity="none",
            llm_correction_rounds=0,
        )
        assert hasattr(r, "applied_changes")
        assert r.applied_changes == []

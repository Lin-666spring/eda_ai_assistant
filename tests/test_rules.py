"""设计规则检查器单元测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.rules.checker import DesignRuleChecker, RuleViolation, RuleSeverity
from src.bom.parser import BOMItem


@pytest.fixture
def checker():
    return DesignRuleChecker()


@pytest.fixture
def bom_with_decoupling():
    return [
        BOMItem(reference="C1,C2", value="100nF", package="0603",
                part_number="C1588", description="贴片电容", quantity=2),
        BOMItem(reference="U1", value="", package="LQFP-48",
                part_number="STM32F103C8T6", description="MCU", quantity=1),
    ]


@pytest.fixture
def bom_without_decoupling():
    return [
        BOMItem(reference="U1", value="", package="LQFP-48",
                part_number="STM32F103C8T6", description="MCU", quantity=1),
        BOMItem(reference="R1", value="10kΩ", package="0603",
                part_number="C25804", description="贴片电阻", quantity=1),
    ]


class TestDecouplingCaps:
    def test_has_decoupling_cap(self, checker, bom_with_decoupling):
        violations = checker._check_decoupling_caps(bom_with_decoupling, {}, {})
        assert len(violations) == 0

    def test_missing_decoupling_cap(self, checker, bom_without_decoupling):
        violations = checker._check_decoupling_caps(bom_without_decoupling, {}, {})
        assert len(violations) >= 1
        assert violations[0].severity == RuleSeverity.WARNING
        assert "去耦电容" in violations[0].rule_name

    def test_different_cap_values(self, checker):
        """各种 0.1μF 等效写法都应识别"""
        for val in ["0.1uF", "100nF", "104", "0.1μF", "100NF"]:
            items = [
                BOMItem(reference="C1", value=val, package="0603",
                        part_number="C1588", description="贴片电容", quantity=1),
                BOMItem(reference="U1", value="", package="QFN-32",
                        part_number="ESP32", description="MCU", quantity=1),
            ]
            violations = checker._check_decoupling_caps(items, {}, {})
            assert len(violations) == 0, f"value={val} 应识别为去耦电容"


class TestCheckAll:
    def test_returns_list(self, checker, bom_with_decoupling):
        result = checker.check_all(bom_with_decoupling)
        assert isinstance(result, list)

    def test_empty_bom(self, checker):
        result = checker.check_all([])
        assert result == []

    def test_rule_exception_does_not_crash(self, checker, monkeypatch):
        """某条规则异常时不应中断其余规则"""
        def _broken(*args, **kwargs):
            raise RuntimeError("模拟规则异常")

        monkeypatch.setattr(checker, "_check_decoupling_caps", _broken)
        result = checker.check_all([], {}, {})
        assert result == []  # 不崩溃，返回空列表


class TestGetReport:
    def test_no_violations(self, checker):
        report = checker.get_report([])
        assert "通过" in report

    def test_with_violations(self, checker):
        violations = [
            RuleViolation(rule_name="测试规则", description="测试描述",
                          severity=RuleSeverity.ERROR, location="R1",
                          suggestion="测试建议"),
        ]
        report = checker.get_report(violations)
        assert "PCB 设计规则检查报告" in report
        assert "测试描述" in report
        assert "R1" in report
        assert "测试建议" in report

    def test_multiple_severities(self, checker):
        violations = [
            RuleViolation(rule_name="R1", description="d1", severity=RuleSeverity.INFO, location="A"),
            RuleViolation(rule_name="R2", description="d2", severity=RuleSeverity.WARNING, location="B"),
            RuleViolation(rule_name="R3", description="d3", severity=RuleSeverity.ERROR, location="C"),
        ]
        report = checker.get_report(violations)
        assert "ERROR" in report
        assert "WARNING" in report
        assert "INFO" in report

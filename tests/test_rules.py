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


class TestLEDCurrentLimit:
    def test_led_without_resistor(self, checker):
        items = [
            BOMItem(reference="LED1", value="Red", package="0603",
                    part_number="C170687", description="发光二极管", quantity=1),
        ]
        violations = checker._check_led_current_limit(items, {}, {})
        assert len(violations) >= 1
        assert "LED" in violations[0].rule_name

    def test_led_with_resistor(self, checker):
        items = [
            BOMItem(reference="LED1", value="Red", package="0603",
                    part_number="C170687", description="发光二极管", quantity=1),
            BOMItem(reference="R1", value="1kΩ", package="0603",
                    part_number="C25804", description="贴片电阻", quantity=1),
        ]
        violations = checker._check_led_current_limit(items, {}, {})
        assert len(violations) == 0


class TestRelayFlybackDiode:
    def test_relay_without_diode(self, checker):
        items = [
            BOMItem(reference="K1", value="5V", package="DIP-5",
                    part_number="SRD-05VDC", description="继电器", quantity=1),
        ]
        violations = checker._check_relay_flyback_diode(items, {}, {})
        assert len(violations) >= 1
        assert "继电器" in violations[0].rule_name

    def test_relay_with_diode(self, checker):
        items = [
            BOMItem(reference="K1", value="5V", package="DIP-5",
                    part_number="SRD-05VDC", description="继电器", quantity=1),
            BOMItem(reference="D1", value="", package="SOD-123",
                    part_number="1N4148", description="开关二极管", quantity=1),
        ]
        violations = checker._check_relay_flyback_diode(items, {}, {})
        assert len(violations) == 0


class TestCapacitorVoltageDerating:
    def test_cap_with_sufficient_rating(self, checker):
        items = [
            BOMItem(reference="C1", value="25V 100μF", package="SMD",
                    part_number="C43353", description="铝电解电容", quantity=1),
            BOMItem(reference="U1", value="5V", package="SOT-23-5",
                    part_number="TPS54331", description="DC-DC降压", quantity=1),
        ]
        violations = checker._check_capacitor_voltage_derating(items, {}, {})
        # 5V system, 25V cap rating — sufficient margin
        assert len(violations) == 0

    def test_cap_with_insufficient_rating(self, checker):
        items = [
            BOMItem(reference="C1", value="10V 100μF", package="SMD",
                    part_number="C43353", description="铝电解电容", quantity=1),
            BOMItem(reference="U1", value="OUT=12V", package="SOT-23-5",
                    part_number="TPS54331", description="DC-DC降压", quantity=1),
        ]
        violations = checker._check_capacitor_voltage_derating(items, {}, {})
        # 12V system, 10V cap — insufficient
        assert len(violations) >= 1
        assert "耐压" in violations[0].rule_name


class TestDCDFeedbackNetwork:
    def test_dcdc_without_fb_resistor(self, checker):
        items = [
            BOMItem(reference="U1", value="3.3V", package="SOT-23-5",
                    part_number="MP1584EN", description="DC-DC Buck", quantity=1),
        ]
        violations = checker._check_dcdc_feedback_network(items, {}, {})
        assert len(violations) >= 1
        assert violations[0].severity == RuleSeverity.ERROR

    def test_dcdc_with_fb_network(self, checker):
        items = [
            BOMItem(reference="U1", value="3.3V", package="SOT-23-5",
                    part_number="MP1584EN", description="DC-DC Buck", quantity=1),
            BOMItem(reference="R1", value="10kΩ", package="0603",
                    part_number="C25804", description="贴片电阻", quantity=1),
            BOMItem(reference="R2", value="2kΩ", package="0603",
                    part_number="C25905", description="贴片电阻", quantity=1),
        ]
        violations = checker._check_dcdc_feedback_network(items, {}, {})
        assert len(violations) == 0


class TestNewRuleCount:
    """验证规则总数 ≥50"""
    def test_at_least_50_rules(self, checker):
        rules = [name for name in dir(checker) if name.startswith('_check_')]
        assert len(rules) >= 50, f"规则数={len(rules)}，应≥50"


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

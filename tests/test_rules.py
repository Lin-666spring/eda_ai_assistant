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
        BOMItem(reference="C3", value="10uF", package="0805",
                part_number="C1590", description="贴片电容", quantity=1),
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
        assert violations[0].severity in (RuleSeverity.WARNING, RuleSeverity.ERROR)
        assert "去耦电容" in violations[0].rule_name

    def test_different_cap_values(self, checker):
        """各种 0.1μF 等效写法都应识别为高频去耦电容（+10μF 体电容）"""
        for val in ["0.1uF", "100nF", "104", "0.1μF", "100NF"]:
            items = [
                BOMItem(reference="C1", value=val, package="0603",
                        part_number="C1588", description="贴片电容", quantity=1),
                BOMItem(reference="C2", value="10uF", package="0805",
                        part_number="C1590", description="贴片电容", quantity=1),
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
        # PDN 规则即使空 BOM 也会产生分析结果（使用默认电流估算）
        assert isinstance(result, list)

    def test_rule_exception_does_not_crash(self, checker, monkeypatch):
        """某条规则异常时不应中断其余规则"""
        def _broken(*args, **kwargs):
            raise RuntimeError("模拟规则异常")

        monkeypatch.setattr(checker, "_check_decoupling_caps", _broken)
        monkeypatch.setattr(checker, "_check_pdn_target_impedance", lambda *a, **kw: [])
        result = checker.check_all([], {}, {})
        assert isinstance(result, list)  # _broken 不应导致崩溃


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


class TestCheckAllContract:
    """check_all 的输入契约与错误记账（2026-10-02 口径统一）。"""

    def test_normalize_keeps_explicit_dict(self, checker):
        nl = {"N1": ["U1.1"]}
        assert checker.normalize_netlist(nl, None) == nl

    def test_normalize_derives_from_pcb_nets(self, checker):
        from src.pcb.models import PCBData, PCBNet
        pcb = PCBData(nets={
            "VCC": PCBNet(name="VCC", pins=["U1.1", "C1.1"]),
            "EMPTY": PCBNet(name="EMPTY", pins=[]),
        })
        assert checker.normalize_netlist({}, pcb) == {"VCC": ["U1.1", "C1.1"]}

    def test_normalize_drops_plain_list(self, checker):
        # 旧契约里 netlist 是 list、且全项目从未赋值；引脚信息拿不回来，
        # 只能当作「没有网表」，不能假装有。
        assert checker.normalize_netlist(["VCC", "GND"], None) == {}

    def test_rule_errors_are_recorded_not_swallowed(self, checker, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("boom")
        monkeypatch.setattr(checker, "_check_led_current_limit", boom)
        checker._rules = [getattr(checker, name) for name in sorted(dir(checker))
                          if name.startswith("_check_")]
        checker.check_all([], {}, None, None)
        assert checker.rule_errors, "规则异常必须被记录，不能被静默吞掉"
        assert any("boom" in e["error"] for e in checker.rule_errors)

    def test_unconnected_pins_counts_real_pins(self, checker):
        from src.bom.parser import BOMItem
        bom = [BOMItem(reference="U1", value="", package="LQFP-48",
                       part_number="STM32F103C8T6", description="MCU", quantity=1)]
        few = {f"N{i}": [f"U1.{i}"] for i in range(3)}
        assert checker._check_unconnected_pins(bom, {}, few)
        # 40 个引脚已连接 → 不报。旧实现把「提到 U1 的网络数」当引脚数，
        # 也能凑到 40，但换成 40 条只提到 U1 的网络就会误判成已连接。
        many = {f"N{i}": [f"U1.{i}", "R1.1"] for i in range(40)}
        assert checker._check_unconnected_pins(bom, {}, many) == []

    def test_unconnected_pins_accepts_pcbnets_values(self, checker):
        from src.bom.parser import BOMItem
        from src.pcb.models import PCBNet
        bom = [BOMItem(reference="U1", value="", package="QFN-48",
                       part_number="X", description="MCU", quantity=1)]
        nets = {f"N{i}": PCBNet(name=f"N{i}", pins=[f"U1.{i}"]) for i in range(40)}
        assert checker._check_unconnected_pins(bom, {}, nets) == []


class TestOpampFeedbackNetwork:
    """2026-10-06 回归：旧判据数「与运放同前缀(U)的电阻」恒为 0 → 有运放必报。
    现在按网表判断：与运放共网的电阻即反馈网络；无网表不判。
    """

    @staticmethod
    def _opamp_bom():
        return [
            BOMItem(reference="U5", value="", package="SOP-8",
                    part_number="LM358", description="", quantity=1),
        ]

    def test_net_with_resistor_no_violation(self, checker):
        netlist = {
            "OUT": ["U5.1", "R3.2"],
            "IN-": ["U5.2", "R3.1", "R4.1"],
        }
        assert checker._check_opamp_feedback_network(self._opamp_bom(), {}, netlist) == []

    def test_net_without_resistor_reports_info(self, checker):
        netlist = {"OUT": ["U5.1", "C2.1"], "IN-": ["U5.2", "U6.3"]}
        violations = checker._check_opamp_feedback_network(self._opamp_bom(), {}, netlist)
        assert len(violations) == 1
        assert violations[0].severity == RuleSeverity.INFO
        assert "U5" in violations[0].description
        assert "OUT" in violations[0].description and "IN-" in violations[0].description

    def test_no_netlist_no_violation(self, checker):
        assert checker._check_opamp_feedback_network(self._opamp_bom(), {}, {}) == []
        assert checker._check_opamp_feedback_network(self._opamp_bom(), {}, None) == []


class TestReferenceContinuity:
    """2026-10-06 回归：一行 "R4,R5" 以前只算 R4，报出实际不存在的跳号。"""

    @staticmethod
    def _rs(refs):
        return [BOMItem(reference=r, value="10kΩ", package="0603",
                        part_number="C25804", description="贴片电阻", quantity=1)
                for r in refs]

    def test_multi_ref_line_no_false_gap(self, checker):
        bom = self._rs(["R3", "R4,R5", "R6"])
        assert checker._check_reference_continuity(bom, {}, {}) == []

    def test_real_gap_still_reported(self, checker):
        bom = self._rs(["R3", "R4", "R6"])   # 删掉 R5 → 真缺口
        violations = checker._check_reference_continuity(bom, {}, {})
        assert len(violations) == 1
        assert violations[0].severity == RuleSeverity.INFO
        assert "R4→R6" in violations[0].description


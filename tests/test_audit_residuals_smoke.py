"""审计残留批（2026-10-10）复活/收紧规则的冒烟对。

每条规则一对用例：反例必须触发、正例必须静默 —— 判据再退化成
「恒真/恒报」时在这里红灯。金样级回归（78 板触发总数）在
test_golden_snapshot.py；本文件只做单元级最小证据对。
"""

from __future__ import annotations

import pytest

from src.bom.parser import BOMItem
from src.rules.checker import DesignRuleChecker


@pytest.fixture
def checker():
    return DesignRuleChecker()


def _rule_names(violations):
    return {v.rule_name for v in violations}


# ── A. 结构性恒真×4 ──────────────────────────────────────────


class TestDcdcFeedback:
    def test_supply_route_shortage_triggers(self, checker):
        """仅 1 个电阻位号（供需 < 2×DC-DC）→ 必须报。"""
        items = [
            BOMItem(reference="U1", value="3.3V", package="SOT-23-5",
                    part_number="MP1584EN", description="DC-DC Buck", quantity=1),
            BOMItem(reference="R1,R2", value="10kΩ", package="0603",
                    part_number="C25804", description="贴片电阻", quantity=2),
        ]
        # 位号计数：一行 R1,R2 = 2 个位号 → 供需恰好满足 → 不报（行数口径才是 1）
        assert checker._check_dcdc_feedback_network(items, {}, {}) == []
        items[1].reference = "R1"  # 只剩 1 个位号 → 供需缺口
        items[1].quantity = 1      # _component_count=max(qty, 位号数)，qty 同步降
        violations = checker._check_dcdc_feedback_network(items, {}, {})
        assert _rule_names(violations) == {"DC-DC 反馈网络检查"}

    def test_netlist_route_unrelated_resistors_trigger(self, checker):
        """网表可用：R1/R2 存在但不在 FB 网上 → 反馈网络未检出。"""
        items = [
            BOMItem(reference="U1", value="3.3V", package="SOT-23-5",
                    part_number="MP1584EN", description="DC-DC Buck", quantity=1),
            BOMItem(reference="R1", value="10kΩ", package="0603",
                    part_number="C25804", description="", quantity=1),
            BOMItem(reference="R2", value="2kΩ", package="0603",
                    part_number="C25905", description="", quantity=1),
        ]
        netlist = {"VCC": ["U1.4", "R1.1"], "GND": ["U1.2", "R2.2"]}
        violations = checker._check_dcdc_feedback_network(items, {}, netlist)
        assert _rule_names(violations) == {"DC-DC 反馈网络检查"}
        assert "反馈网络未检出" in violations[0].description

    def test_netlist_route_fb_divider_silent(self, checker):
        items = [
            BOMItem(reference="U1", value="3.3V", package="SOT-23-5",
                    part_number="MP1584EN", description="DC-DC Buck", quantity=1),
            BOMItem(reference="R1", value="10kΩ", package="0603",
                    part_number="C25804", description="", quantity=1),
            BOMItem(reference="R2", value="2kΩ", package="0603",
                    part_number="C25905", description="", quantity=1),
        ]
        netlist = {"FB": ["U1.3", "R1.2", "R2.1"]}
        assert checker._check_dcdc_feedback_network(items, {}, netlist) == []


class TestLedCurrentLimit:
    def test_pullup_only_triggers(self, checker):
        """100k 上拉不在限流档 → LED 供需缺口必须报（旧版任意电阻即静默）。"""
        items = [
            BOMItem(reference="LED1", value="红", package="0603",
                    part_number="C2286", description="", quantity=1),
            BOMItem(reference="R1", value="100kΩ", package="0603",
                    part_number="C25803", description="", quantity=1),
        ]
        violations = checker._check_led_current_limit(items, {}, {})
        assert _rule_names(violations) == {"LED 限流电阻检查"}

    def test_series_resistor_silent(self, checker):
        items = [
            BOMItem(reference="LED1", value="红", package="0603",
                    part_number="C2286", description="", quantity=1),
            BOMItem(reference="R1", value="100Ω", package="0603",
                    part_number="C22775", description="", quantity=1),
        ]
        assert checker._check_led_current_limit(items, {}, {}) == []

    def test_netlist_coverage_silent(self, checker):
        items = [
            BOMItem(reference="LED1", value="红", package="0603",
                    part_number="C2286", description="", quantity=1),
            BOMItem(reference="R1", value="100kΩ", package="0603",
                    part_number="C25803", description="", quantity=1),
        ]
        netlist = {"LED_A": ["LED1.1", "R1.2"]}  # LED 网上挂了 R 引脚
        assert checker._check_led_current_limit(items, {}, netlist) == []


class TestOptocouplerInput:
    def test_no_resistor_triggers(self, checker):
        items = [BOMItem(reference="U1", value="", package="DIP-4",
                         part_number="PC817", description="光耦", quantity=1)]
        violations = checker._check_optocoupler_input_resistor(items, {}, {})
        assert _rule_names(violations) == {"光耦输入限流检查"}

    def test_resistor_row_silent(self, checker):
        """描述为空的电阻行（真实立创 BOM 形态）也要被认出 —— 旧描述口径漏。"""
        items = [
            BOMItem(reference="U1", value="", package="DIP-4",
                    part_number="PC817", description="光耦", quantity=1),
            BOMItem(reference="R1", value="1kΩ", package="0603",
                    part_number="C21190", description="", quantity=1),
        ]
        assert checker._check_optocoupler_input_resistor(items, {}, {}) == []


class TestAdcInputFilter:
    def test_value_channel_cap_silent(self, checker):
        """容值写在 value 列的电容必须被认出（旧判据搜 pn+desc 恒假→必报）。"""
        items = [
            BOMItem(reference="U1", value="", package="MSOP-10",
                    part_number="ADS1115", description="", quantity=1),
            BOMItem(reference="C1", value="100nF", package="0603",
                    part_number="C14663", description="", quantity=1),
        ]
        assert checker._check_adc_input_filter(items, {}, {}) == []

    def test_no_filter_cap_triggers(self, checker):
        items = [BOMItem(reference="U1", value="", package="MSOP-10",
                         part_number="ADS1115", description="", quantity=1)]
        violations = checker._check_adc_input_filter(items, {}, {})
        assert _rule_names(violations) == {"ADC 输入滤波检查"}


# ── B. 假阳/口径 ────────────────────────────────────────────


class TestEsdMountingHole:
    def test_mounting_holes_are_not_connectors(self, checker):
        """只有安装孔（H 前缀）+ IC 的板不应报缺 TVS（旧版 47/78 板假阳）。"""
        items = [
            BOMItem(reference="U1", value="", package="QFN-32",
                    part_number="STM32F103", description="", quantity=1),
            BOMItem(reference="H1,H2,H3,H4", value="", package="HR3.2",
                    part_number="", description="", quantity=4),
        ]
        assert checker._check_esd_protection(items, {}, {}) == []

    def test_real_connector_without_tvs_triggers(self, checker):
        items = [
            BOMItem(reference="U1", value="", package="QFN-32",
                    part_number="STM32F103", description="", quantity=1),
            BOMItem(reference="J1", value="", package="USB-A",
                    part_number="", description="USB", quantity=1),
        ]
        violations = checker._check_esd_protection(items, {}, {})
        assert "ESD 保护检查" in _rule_names(violations)


class TestMixedVoltageDomains:
    def test_same_domain_two_notations_not_double_counted(self, checker):
        """3.3V+3V3 是一个域 —— 四种写法两种域不应凑满 3 域门槛。"""
        items = [
            BOMItem(reference="U1", value="", package="QFN-32",
                    part_number="STM32F103", description="3.3V", quantity=1),
            BOMItem(reference="U2", value="", package="SOT-23",
                    part_number="AMS1117-3.3", description="3V3", quantity=1),
            BOMItem(reference="U3", value="", package="SOT-23",
                    part_number="", description="1.8V", quantity=1),
            BOMItem(reference="U4", value="", package="SOT-23",
                    part_number="", description="1V8", quantity=1),
        ]
        assert checker._check_mixed_voltage_isolation(items, {}, {}) == []

    def test_three_real_domains_trigger(self, checker):
        items = [
            # 域 token 只认 value/pn 通道（本批只修 3V3/1V8 归一化，通道未扩）
            BOMItem(reference=f"U{i}", value=v, package="SOT-23",
                    part_number="", description="", quantity=1)
            for i, v in enumerate(("5V", "3.3V", "1.8V"), 1)
        ]
        violations = checker._check_mixed_voltage_isolation(items, {}, {})
        assert _rule_names(violations) == {"多电压域隔离检查"}


class TestCapTemperatureCoefficient:
    def test_plain_ceramics_silent(self, checker):
        """普通陶瓷电容任意数量不报（旧版 ≥5 电容即模板报）。"""
        items = [
            BOMItem(reference=f"C{i}", value="100nF", package="0603",
                    part_number="C14663", description="", quantity=1)
            for i in range(1, 7)
        ]
        assert checker._check_cap_temperature_coefficient(items, {}, {}) == []

    def test_bulk_electrolytic_triggers(self, checker):
        """≥10µF（C0G 做不到的容值）→ 温度系数提示。"""
        items = [
            BOMItem(reference="C1", value="100uF", package="RB.1.2",
                    part_number="", description="电解电容", quantity=1),
        ]
        violations = checker._check_cap_temperature_coefficient(items, {}, {})
        assert _rule_names(violations) == {"电容温度系数检查"}


class TestCapVoltageRating:
    def test_rating_in_description_triggers(self, checker):
        """耐压只在描述列也要被认出（旧版只搜 value+pn 漏检）。"""
        items = [
            BOMItem(reference="C1", value="10uF", package="0805",
                    part_number="C15850", description="10V", quantity=1),
            BOMItem(reference="U1", value="", package="SOT-223",
                    part_number="AMS1117-12", description="12V LDO", quantity=1),
        ]
        violations = checker._check_capacitor_voltage_derating(items, {}, {})
        assert _rule_names(violations) == {"电容耐压降额检查"}


class TestMosfetGateResistor:
    def test_resistor_row_silent(self, checker):
        items = [
            BOMItem(reference="Q1", value="", package="SOT-23",
                    part_number="AO3400", description="NMOS", quantity=1),
            BOMItem(reference="R1", value="100Ω", package="0603",
                    part_number="C22775", description="", quantity=1),
        ]
        assert checker._check_mosfet_gate_resistor(items, {}, {}) == []

    def test_bare_mosfet_triggers(self, checker):
        items = [BOMItem(reference="Q1", value="", package="SOT-23",
                         part_number="AO3400", description="NMOS", quantity=1)]
        violations = checker._check_mosfet_gate_resistor(items, {}, {})
        assert _rule_names(violations) == {"MOSFET 栅极电阻检查"}


class TestPerPinDecoupling:
    def test_qfn32_without_caps_triggers(self, checker):
        """封装名数字兜底：QFN-32 → 32 脚。"""
        items = [
            BOMItem(reference="U1", value="", package="QFN-32",
                    part_number="STM32F103", description="", quantity=1),
        ]
        violations = checker._check_decoupling_cap_per_pin(items, {}, {})
        assert _rule_names(violations) == {"多电源引脚去耦检查"}

    def test_sot23_6_with_one_cap_silent(self, checker):
        items = [
            BOMItem(reference="U1", value="", package="SOT-23-6",
                    part_number="MP1584EN", description="", quantity=1),
            BOMItem(reference="C1", value="100nF", package="0603",
                    part_number="C14663", description="", quantity=1),
        ]
        assert checker._check_decoupling_cap_per_pin(items, {}, {}) == []

    def test_unparseable_package_skips(self, checker):
        """0402 之类的封装码不是引脚数 —— 查不出诚实跳过。"""
        items = [
            BOMItem(reference="U1", value="", package="0402",
                    part_number="", description="", quantity=1),
        ]
        assert checker._check_decoupling_cap_per_pin(items, {}, {}) == []


# ── C. 设计性休眠（数据到位前必须保持静默，不再输出模板报文）──


class TestDormantRules:
    def test_component_height_zoning_dormant(self, checker):
        items = [
            BOMItem(reference="U1", value="", package="TO-220",
                    part_number="", description="", quantity=1),
            BOMItem(reference="C1", value="100nF", package="0603",
                    part_number="", description="", quantity=1),
        ]
        assert checker._check_component_height_zoning(items, {}, {}) == []

    def test_polarity_orientation_dormant(self, checker):
        items = [
            BOMItem(reference="D1", value="红", package="0603",
                    part_number="C2286", description="", quantity=1),
        ]
        assert checker._check_polarity_orientation(items, {}, {}) == []

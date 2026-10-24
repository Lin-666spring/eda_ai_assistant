"""P1 批次C 判据修复回归（验收 2026-10-24）。

钉死四处 BOM 判据缺陷：

* P1-13 ``_parse_component_value`` 不认 EIA「单位字母代替小数点」记法：
  4R7 被拆成 (4, R=+1) 当 40Ω、100R 当 1000Ω → 标准阻值被误报「不在 E24/E96」。
* P1-14 ``_check_power_filtering`` 大电解档位用裸子串（"100u" ⊂ "100uH"），
  电感冒充大电解、缺失大电容被静默放行。
* P1-17 电压轨/电压域识别裸子串（"5V" ⊂ "25V"/"15V"/"0.5V"）三处：
  max_voltage 失真 → 耐压降额错判、多电压域凑门槛、PDN 电压按 5V 估算。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.bom.parser import BOMItem
from src.pcb.models import PCBData
from src.rules.base import _parse_component_value
from src.rules.bom_rules import _value_bulk_uf
from src.rules.checker import DesignRuleChecker


def _item(reference="R1", value="", package="0603", part_number="",
          description=""):
    return BOMItem(reference=reference, value=value, package=package,
                   part_number=part_number, description=description, quantity=1)


# ══════════════════ P1-13：EIA R/K 记法 ══════════════════

class TestParseComponentValueEiaNotation:
    @pytest.mark.parametrize("val,mant,exp", [
        ("4R7", 4.7, 0),      # 旧版 (4, +1) → 40Ω
        ("100R", 100.0, 0),   # 旧版 (100, +1) → 1000Ω
        ("4K7", 4.7, 3),      # 4.7kΩ
        ("2U7", 2.7, -6),     # 2.7µF
        ("0R22", 0.22, 0),    # 0.22Ω
        ("4K7Ω", 4.7, 3),     # 单位字母小数点 + 显式 Ω 尾缀
    ])
    def test_unit_letter_as_decimal_point(self, val, mant, exp):
        assert _parse_component_value(val) == pytest.approx((mant, exp))

    def test_100r_not_flagged_as_off_e24(self):
        """负样本：4R7 是 E24 标准值（470），不得再报「不在标准系列」。
        （旧版解析成 40Ω → 400 ∉ E24 → 误报）"""
        checker = DesignRuleChecker()
        checker._pcb_data = PCBData(format="lceda_epro2")
        items = [_item("R1", "4R7"), _item("R2", "100R"), _item("R3", "4K7")]
        assert [v.location for v in checker._check_bom_value_range(items, {}, {})] == []

    def test_non_standard_r_notation_still_flagged(self):
        """3R1=3.1Ω（310）确实不在 E24∪E96 —— 证明 R 记法按真值参与判定，
        而不是被当成解析失败跳过（旧版拆成 30 → 300 ∈ E24 侥幸放行）。"""
        checker = DesignRuleChecker()
        checker._pcb_data = PCBData(format="lceda_epro2")
        items = [_item("R9", "3R1")]
        assert [v.location for v in checker._check_bom_value_range(items, {}, {})] == ["R9"]

    def test_plain_values_unchanged(self):
        assert _parse_component_value("4.7KΩ") == pytest.approx((4.7, 3))
        assert _parse_component_value("100nF") == pytest.approx((100.0, -9))
        assert _parse_component_value("10uH") == pytest.approx((10.0, -6))
        assert _parse_component_value("0603") is None   # 封装码仍跳过


# ══════════════════ P1-14：电源滤波大电解单位感知 ══════════════════

class TestValueBulkUf:
    @pytest.mark.parametrize("val,uf", [
        ("100uH", 0.0),      # 负样本：电感不是电容
        ("10uH", 0.0),
        ("2.2mH", 0.0),
        ("220uF", 220.0),
        ("470µF", 470.0),    # U+00B5 micro sign
        ("470μF", 470.0),    # U+03BC greek mu
        ("100ΜF", 100.0),
        ("4700uF", 4700.0),  # 负样本（旧版）：不得从 4700 里抠出 470/100
        ("2200uF", 2200.0),
        ("104", 0.0),        # 三位码无单位不认
        ("0.1UF", 0.1),
        ("16V", 0.0),
    ])
    def test_token_parsing(self, val, uf):
        assert _value_bulk_uf(val) == pytest.approx(uf)


class TestPowerFiltering:
    def _entry_row(self):
        return _item("J1", "", package="DC-005", part_number="",
                     description="电源接口 power entry")

    def test_inductor_100uh_not_counted_as_bulk(self):
        """负样本：100uH 电感冒充大电解 → 缺大电容被静默放行（缺陷本体）。
        现在必须报「缺大电解」。"""
        checker = DesignRuleChecker()
        items = [
            self._entry_row(),
            _item("L1", "100uH", package="CD75", part_number="", description="功率电感"),
            _item("C1", "0.1uF", package="0603", part_number="", description=""),
        ]
        violations = checker._check_power_filtering(items, {}, {})
        assert len(violations) == 1
        assert "大电解" in violations[0].description

    @pytest.mark.parametrize("bulk", ["220uF", "470µF", "4700uF", "1F"])
    def test_real_bulk_caps_pass(self, bulk):
        checker = DesignRuleChecker()
        items = [
            self._entry_row(),
            _item("C2", bulk, package="SMD-8", part_number="", description="电解电容"),
            _item("C1", "0.1uF", package="0603", part_number="", description=""),
        ]
        assert checker._check_power_filtering(items, {}, {}) == []

    def test_small_cap_alone_still_reports_missing_bulk(self):
        checker = DesignRuleChecker()
        items = [
            self._entry_row(),
            _item("C1", "100nF", package="0603", part_number="", description=""),
        ]
        violations = checker._check_power_filtering(items, {}, {})
        assert len(violations) == 1
        assert "大电解" in violations[0].description


# ══════════════════ P1-17：电压轨识别（3 处） ══════════════════

class TestCapacitorVoltageDeratingRails:
    def test_25v_decoy_does_not_register_5v_rail(self):
        """负样本：板面真实轨 3.3V + 25V 电解（"5V" ⊂ "25V" 的假命中）——
        旧版 max_voltage 被抬到 5V，5V 耐压的电容被误报裕量不足。"""
        checker = DesignRuleChecker()
        items = [
            _item("U1", "3.3V", package="SOT-223", part_number="AMS1117-3.3",
                  description="LDO"),
            _item("C9", "470uF 25V", package="SMD-8", part_number="C43353",
                  description="铝电解电容"),
            _item("C1", "100uF 5V", package="SMD", part_number="C43353",
                  description="铝电解电容"),
        ]
        assert checker._check_capacitor_voltage_derating(items, {}, {}) == []

    def test_5v_rail_with_space_still_matches(self):
        """正样本："5 V" 写法（数字与单位带空格）仍要命中 5V 轨。"""
        checker = DesignRuleChecker()
        items = [
            _item("U1", "5 V", package="SOT-23-5", part_number="TPS54331",
                  description="DC-DC降压"),
            _item("C1", "100uF 5V", package="SMD", part_number="C43353",
                  description="铝电解电容"),
        ]
        violations = checker._check_capacitor_voltage_derating(items, {}, {})
        assert len(violations) == 1
        assert "系统最高电压 5.0V" in violations[0].description

    def test_vout_prefix_token_still_matches(self):
        """正样本：VOUT=12V 里的 12V 仍要命中 12V 轨（旧特判的等价覆盖）。"""
        checker = DesignRuleChecker()
        items = [
            _item("U1", "OUT=12V", package="SOT-23-5", part_number="TPS54331",
                  description="DC-DC降压"),
            _item("C1", "10V 100μF", package="SMD", part_number="C43353",
                  description="铝电解电容"),
        ]
        violations = checker._check_capacitor_voltage_derating(items, {}, {})
        assert len(violations) == 1
        assert "系统最高电压 12.0V" in violations[0].description


class TestMixedVoltageDomains:
    def test_25v_15v_decoys_do_not_fabricate_domains(self):
        """负样本：3.3V 单域 + 25V/15V/12.5V 干扰串——旧版从 "25V"/"15V" 里
        抠出 "5V"、从 "12.5V" 里抠出 "2.5V"，凑满 3 域误报隔离。"""
        checker = DesignRuleChecker()
        items = [
            _item("U1", "3.3V", package="QFN-32", part_number="STM32F103",
                  description="MCU"),
            _item("C9", "470uF 25V", package="SMD-8", part_number="C43353",
                  description="铝电解电容"),
            _item("D1", "15V", package="SMA", part_number="SMAJ15A-Q",
                  description="TVS"),
            _item("R1", "12.5V", package="0603", part_number="",
                  description="分压取样点"),
        ]
        assert checker._check_mixed_voltage_isolation(items, {}, {}) == []

    def test_three_real_domains_still_trigger(self):
        checker = DesignRuleChecker()
        items = [
            _item("U1", "5V", package="SOT-23", part_number="", description=""),
            _item("U2", "3.3V", package="SOT-23", part_number="", description=""),
            _item("U3", "1.8V", package="SOT-23", part_number="", description=""),
        ]
        violations = checker._check_mixed_voltage_isolation(items, {}, {})
        assert len(violations) == 1
        assert "3 个电压域" in violations[0].description

    def test_xvy_notation_recognised_and_folded(self):
        """3V3/1V8/5V0 紧凑写法仍识别，且与 3.3V/1.8V 同域折叠不双计。"""
        checker = DesignRuleChecker()
        same_domain = [
            _item("U1", "3.3V", package="SOT-23", part_number="", description=""),
            _item("U2", "3V3", package="SOT-23", part_number="", description=""),
            _item("U3", "5V0", package="SOT-23", part_number="", description=""),
        ]
        assert checker._check_mixed_voltage_isolation(same_domain, {}, {}) == []

        three_domains = same_domain + [
            _item("U4", "1V8", package="SOT-23", part_number="", description=""),
        ]
        violations = checker._check_mixed_voltage_isolation(three_domains, {}, {})
        assert len(violations) == 1
        desc = violations[0].description
        assert "3.3V" in desc and "1.8V" in desc and "5V" in desc


class TestPdnTargetImpedanceVoltage:
    def _pcb(self):
        pcb = PCBData(format="lceda_epro2")
        pcb.board_outline = {"width_mm": 50.0, "height_mm": 40.0,
                             "min_x_mm": 0.0, "min_y_mm": 0.0,
                             "max_x_mm": 50.0, "max_y_mm": 40.0,
                             "source": "outline"}
        pcb.layers = ["Top Layer", "Bottom Layer"]
        return pcb

    def test_25v_decoy_does_not_downgrade_to_5v_estimate(self):
        """负样本：板上只有 25V 标注（无 5V 轨）——PDN 电压保持 3.3V 默认，
        不得被 "5V" ⊂ "25V" 抬成 5V 估算。"""
        checker = DesignRuleChecker()
        checker._pcb_data = self._pcb()
        items = [
            _item("U1", "", package="QFN-32", part_number="STM32F103",
                  description="MCU"),
            _item("C9", "470uF 25V", package="SMD-8", part_number="C43353",
                  description="铝电解电容"),
        ]
        violations = checker._check_pdn_target_impedance(items, {}, {})
        assert len(violations) == 1
        assert violations[0].description.startswith("3.3V/")

    def test_explicit_5v_still_used(self):
        checker = DesignRuleChecker()
        checker._pcb_data = self._pcb()
        items = [
            _item("U1", "5V", package="QFN-32", part_number="STM32F103",
                  description="MCU"),
        ]
        violations = checker._check_pdn_target_impedance(items, {}, {})
        assert len(violations) == 1
        assert violations[0].description.startswith("5.0V/")

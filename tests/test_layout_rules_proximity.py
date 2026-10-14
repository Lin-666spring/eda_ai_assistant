"""4 条布局邻近规则单元测试 —— 性能优化批（2026-10-13）前置行为锁定。

覆盖 _check_analog_digital_separation / _check_decoupling_proximity /
_check_crystal_proximity / _check_temp_sensitive_placement，重点锁定
优化（ML 分类缓存 + 空间索引）必须保持的口径：

* 阈值比较符各不相同：模数严格 ``<``、去耦/晶振负载 ``>``、
  晶振-MCU ``<=`` 放行、温敏 ``<`` 且 ``warnings > 2`` 才报；
* 平距 tie-break 按 BOM 迭代序取先者（去耦最近 IC）；
* 聚合消息取前 N 按迭代序（模数 cross[:5]、去耦 far[:3]）。

ML 分类统一关闭（_component_predictor=None + attempted=True，与打包版
规则回退同口径）保证确定性；ML 开启路径的输出一致性由 78 板金样快照 +
95 板基线 dump diff 覆盖（scripts/dump_rule_baseline.py）。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

import src.rules.base as rule_base
from src.rules.checker import DesignRuleChecker
from src.bom.parser import BOMItem


@pytest.fixture
def checker():
    return DesignRuleChecker()


@pytest.fixture
def ml_off(monkeypatch):
    """关闭 ML 分类走规则回退（打包版同口径），测试确定性。"""
    monkeypatch.setattr(rule_base, "_component_predictor", None)
    monkeypatch.setattr(rule_base, "_component_model_attempted", True)


def pos(x, y):
    return {"x": x, "y": y}


# ═══ 模数分离检查 ═══

class TestAnalogDigitalSeparation:
    def _bom(self):
        return [
            BOMItem(reference="U1", value="", package="SOP-8",
                    part_number="LM358", description="运放", quantity=1),
            BOMItem(reference="U2", value="", package="LQFP-48",
                    part_number="STM32F103C8T6", description="MCU", quantity=1),
        ]

    def test_close_pair_triggers(self, checker, ml_off):
        positions = {"U1": pos(0, 0), "U2": pos(4.9, 0)}
        violations = checker._check_analog_digital_separation(self._bom(), positions, {})
        assert len(violations) == 1
        v = violations[0]
        assert v.rule_name == "模数分离检查"
        assert "1 对" in v.description
        assert v.location == "U1/U2"

    def test_pair_order_locked(self, checker, ml_off):
        """聚合消息按 analog×digital 双重循环迭代序拼（cross[:5]）。"""
        bom = [
            BOMItem(reference="U1", value="", package="SOP-8",
                    part_number="LM358", description="运放", quantity=1),
            BOMItem(reference="U3", value="", package="SOP-8",
                    part_number="NE5532", description="运放", quantity=1),
            BOMItem(reference="U2", value="", package="LQFP-48",
                    part_number="STM32F103C8T6", description="MCU", quantity=1),
            BOMItem(reference="U4", value="", package="QFP-64",
                    part_number="GD32F103", description="MCU", quantity=1),
        ]
        positions = {
            "U1": pos(0, 0), "U3": pos(1, 0),
            "U2": pos(2, 0), "U4": pos(3, 0),
        }
        violations = checker._check_analog_digital_separation(bom, positions, {})
        assert len(violations) == 1
        assert violations[0].location == "U1/U2, U1/U4, U3/U2, U3/U4"

    def test_boundary_exactly_at_threshold_not_triggered(self, checker, ml_off):
        """判据是严格 <，恰好等于 5mm 不触发。"""
        positions = {"U1": pos(0, 0), "U2": pos(5, 0)}
        violations = checker._check_analog_digital_separation(self._bom(), positions, {})
        assert violations == []

    def test_single_zone_skips(self, checker, ml_off):
        positions = {"U1": pos(0, 0), "R1": pos(1, 0)}
        assert checker._check_analog_digital_separation(self._bom(), positions, {}) == []

    def test_no_positions_skips(self, checker, ml_off):
        assert checker._check_analog_digital_separation(self._bom(), {}, {}) == []


# ═══ 去耦电容距离检查 ═══

class TestDecouplingProximity:
    def _bom(self, n_caps=1):
        items = [BOMItem(reference=f"C{i}", value="100nF", package="0603",
                         part_number="C1588", description="贴片电容", quantity=1)
                 for i in range(1, n_caps + 1)]
        items.append(BOMItem(reference="U1", value="", package="LQFP-48",
                             part_number="STM32F103C8T6", description="MCU", quantity=1))
        return items

    def test_far_cap_reported(self, checker, ml_off):
        positions = {"C1": pos(0, 0), "U1": pos(100, 0)}
        violations = checker._check_decoupling_proximity(self._bom(), positions, {})
        assert len(violations) == 1
        assert "C1/U1(100.0mm)" in violations[0].description
        assert "1 个去耦电容距 IC >15.0mm" in violations[0].description

    def test_near_cap_not_reported(self, checker, ml_off):
        positions = {"C1": pos(0, 0), "U1": pos(10, 0)}
        assert checker._check_decoupling_proximity(self._bom(), positions, {}) == []

    def test_boundary_exactly_at_threshold_not_triggered(self, checker, ml_off):
        """判据是严格 >，恰好 15mm 不触发。"""
        positions = {"C1": pos(0, 0), "U1": pos(15, 0)}
        assert checker._check_decoupling_proximity(self._bom(), positions, {}) == []

    def test_tie_break_keeps_first_ic_in_bom_order(self, checker, ml_off):
        """两 IC 与电容等距时，最近 IC 取 BOM 迭代序先者（< 严格比较不换人）。"""
        bom = self._bom()
        bom.append(BOMItem(reference="U2", value="", package="QFP-64",
                           part_number="GD32F103", description="MCU", quantity=1))
        positions = {"C1": pos(50, 50), "U1": pos(50, 70), "U2": pos(70, 50)}
        violations = checker._check_decoupling_proximity(bom, positions, {})
        assert len(violations) == 1
        assert "C1/U1(20.0mm)" in violations[0].description

    def test_aggregate_caps_at_first_three(self, checker, ml_off):
        """far[:3]：第 4 对只进计数不进位号列表。"""
        positions = {"C1": pos(0, 0), "C2": pos(0, 10), "C3": pos(0, 20),
                     "C4": pos(0, 30), "U1": pos(200, 0)}
        violations = checker._check_decoupling_proximity(self._bom(4), positions, {})
        assert len(violations) == 1
        desc = violations[0].description
        assert "4 个去耦电容距 IC >15.0mm（4 对电容-IC 组合）" in desc
        assert "C1/U1" in desc and "C3/U1" in desc
        assert "C4/U1" not in desc

    def test_no_ics_skips(self, checker, ml_off):
        bom = [BOMItem(reference="C1", value="100nF", package="0603",
                       part_number="C1588", description="贴片电容", quantity=1)]
        positions = {"C1": pos(0, 0)}
        assert checker._check_decoupling_proximity(bom, positions, {}) == []


# ═══ 晶振布局检查 ═══

def _crystal_bom():
    return [
        BOMItem(reference="X1", value="8MHz", package="HC-49S",
                part_number="Crystal 8MHz", description="晶振", quantity=1),
        BOMItem(reference="U1", value="", package="LQFP-48",
                part_number="STM32F103C8T6", description="MCU", quantity=1),
    ]


class TestCrystalProximity:
    def test_far_crystal_reported(self, checker, ml_off):
        positions = {"X1": pos(0, 0), "U1": pos(100, 0)}
        violations = checker._check_crystal_proximity(_crystal_bom(), positions, {})
        assert len(violations) == 1
        v = violations[0]
        assert v.rule_name == "晶振布局检查"
        assert "晶振 X1 距 MCU 100mm(建议≤25mm)" in v.description

    def test_near_crystal_not_reported(self, checker, ml_off):
        positions = {"X1": pos(0, 0), "U1": pos(10, 0)}
        assert checker._check_crystal_proximity(_crystal_bom(), positions, {}) == []

    def test_boundary_inclusive_at_threshold(self, checker, ml_off):
        """放行口径是 <=，恰好 25mm 不触发（与去耦的严格 > 相区别）。"""
        positions = {"X1": pos(0, 0), "U1": pos(25, 0)}
        assert checker._check_crystal_proximity(_crystal_bom(), positions, {}) == []

    def test_far_load_cap_note(self, checker, ml_off):
        """netlist 关联的负载电容也远时，描述附 cap_note。"""
        bom = _crystal_bom()
        bom.append(BOMItem(reference="C10", value="10pF", package="0402",
                           part_number="C1588", description="贴片电容", quantity=1))
        positions = {"X1": pos(0, 0), "U1": pos(100, 0), "C10": pos(200, 0)}
        netlist = {"OSC_OUT": ["X1.1", "C10.1"]}
        violations = checker._check_crystal_proximity(bom, positions, netlist)
        assert len(violations) == 1
        assert "最近的负载电容也距 200mm" in violations[0].description

    def test_no_crystal_skips(self, checker, ml_off):
        bom = [BOMItem(reference="U1", value="", package="LQFP-48",
                       part_number="STM32F103C8T6", description="MCU", quantity=1)]
        positions = {"U1": pos(0, 0)}
        assert checker._check_crystal_proximity(bom, positions, {}) == []


# ═══ 温度敏感元件布局检查 ═══

def _temp_bom(n_caps, far_cap=False):
    """n_caps 个电解电容 + 1 个 DC-DC 热源（+1 个远离的电解电容可选）。"""
    items = [BOMItem(reference=f"C{i}", value="220uF", package="SMD-8",
                     part_number="C_Aluminum", description="电解电容", quantity=1)
             for i in range(1, n_caps + 1)]
    items.append(BOMItem(reference="U1", value="", package="SOT-23",
                         part_number="MP1584", description="同步降压 稳压器", quantity=1))
    if far_cap:
        items.append(BOMItem(reference="C9", value="220uF", package="SMD-8",
                             part_number="C_Aluminum", description="电解电容", quantity=1))
    return items


TEMP_POSITIONS_CLOSE = {  # C1、C2 距 U1 均 <10mm
    "C1": pos(5, 0), "C2": pos(0, 5), "U1": pos(0, 0),
}
TEMP_POSITIONS_MIXED = {  # C1、C2 近，C9 远
    "C1": pos(5, 0), "C2": pos(0, 5), "U1": pos(0, 0), "C9": pos(500, 500),
}


class TestTempSensitivePlacement:
    def test_two_close_pairs_not_reported(self, checker, ml_off):
        """warnings > 2 才报：恰好 2 对不触发。"""
        violations = checker._check_temp_sensitive_placement(
            _temp_bom(2), TEMP_POSITIONS_CLOSE, {})
        assert violations == []

    def test_three_close_pairs_reported(self, checker, ml_off):
        bom = _temp_bom(2)
        bom.append(BOMItem(reference="U2", value="", package="SOT-23",
                           part_number="MP1584", description="同步降压 稳压器", quantity=1))
        # C1-U1=5、C2-U1=5、C1-U2=7 近；C2-U2=13 远 → 恰好 3 对
        positions = dict(TEMP_POSITIONS_CLOSE, U2=pos(12, 0))
        violations = checker._check_temp_sensitive_placement(bom, positions, {})
        assert len(violations) == 1
        v = violations[0]
        assert v.rule_name == "温度敏感元件布局检查"
        assert "3 对温度敏感元件与热源间距 <10mm" in v.description

    def test_far_sensitive_not_counted(self, checker, ml_off):
        violations = checker._check_temp_sensitive_placement(
            _temp_bom(2, far_cap=True), TEMP_POSITIONS_MIXED, {})
        assert violations == []

    def test_boundary_at_threshold_not_counted(self, checker, ml_off):
        """判据是严格 <，恰好 10mm 不计入。"""
        bom = _temp_bom(1)
        positions = {"C1": pos(0, 0), "U1": pos(10, 0)}
        assert checker._check_temp_sensitive_placement(bom, positions, {}) == []

    def test_same_ref_not_self_paired(self, checker, ml_off):
        """同一行既是敏感件又是热源时不自配对（hr == tr 跳过）。"""
        bom = [BOMItem(reference="U1", value="", package="SOT-23",
                       part_number="MP1584", description="电解电容 稳压器", quantity=1)]
        positions = {"U1": pos(0, 0)}
        assert checker._check_temp_sensitive_placement(bom, positions, {}) == []

    def test_no_positions_skips(self, checker, ml_off):
        assert checker._check_temp_sensitive_placement(_temp_bom(2), {}, {}) == []

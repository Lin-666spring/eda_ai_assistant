"""违规坐标化回归测试 — 2026-10-24。

背景：违规对象此前只有 location 字符串（"U1, C3"），坐标是热力图事后
从字符串抠位号反查的，其它消费方（3D 板视图、文本报告）拿不到位置。
现在 ``check_all`` 出口统一坐标化：每条违规自带 ``v.coords``（绝对 mm），
位号→坐标口径与热力图同一段代码（``_violation_xy``），位置来源优先级
也是同一套（PCB ``component_positions`` > 坐标文件）。

锁定的行为：

1. ``_coordinatize``：多位号违规按 location 出现顺序解析、同点去重；
   板级/未知位号/无 location 的违规 coords 保持空列表；
2. 位置来源优先级：PCB 坐标 > 坐标文件；
3. ``check_all`` 出口真的会坐标化（不是只有单独调用才生效）；
4. ``get_report`` 文本报告对有坐标的违规加「坐标: (x, y) mm」行；
5. ``AppController.get_drc_violations()``：items 完整序列化 + reason 码
   语义与热力图一致（no_data / no_positions / no_violations / unmapped）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.controller import AppController
from src.pcb.models import PCBData
from src.rules.checker import DesignRuleChecker, RuleSeverity, RuleViolation

SAMPLE_BOM = Path(__file__).parent / "sample_bom_bad.csv"
SAMPLE_POS = Path(__file__).parent / "sample_positions.csv"


def _v(location: str, rule: str = "测试规则") -> RuleViolation:
    return RuleViolation(rule_name=rule, description="测试违规",
                         severity=RuleSeverity.WARNING, location=location)


# ── 1. 坐标化解析 ──

def test_coordinatize_multi_ref_order_and_dedupe():
    """多位号按 location 顺序解析；同一位号重复出现只记一个点。"""
    checker = DesignRuleChecker()
    checker._positions = {"U1": {"x": 10.0, "y": 20.0},
                          "C3": (30.5, 40.0)}          # 元组写法也要能解析
    vs = [_v("U1, C3, U1"), _v("GND 网络"), _v(""), _v("X99 未知位号")]

    checker._coordinatize(vs)

    assert vs[0].coords == [(10.0, 20.0), (30.5, 40.0)]
    assert vs[1].coords == []          # 板级（网络名无位号）
    assert vs[2].coords == []          # 无 location
    assert vs[3].coords == []          # 位号在坐标表里查不到


def test_coordinatize_prefers_pcb_positions():
    """PCB 坐标与坐标文件同在时以 PCB 为准（与热力图同一优先级）。"""
    pcb = PCBData(format="test", nets={}, traces=[])
    pcb.component_positions = {"R1": {"x": 100.0, "y": 50.0}}

    checker = DesignRuleChecker()
    checker._pcb_data = pcb
    checker._positions = {"R1": {"x": 1.0, "y": 2.0}}
    vs = [_v("R1")]

    checker._coordinatize(vs)
    assert vs[0].coords == [(100.0, 50.0)]


def test_coordinatize_no_positions_is_noop():
    """没有位置数据时全部留空 —— 不算错误，消费方按「未定位」处理。"""
    checker = DesignRuleChecker()
    vs = [_v("U1")]
    checker._coordinatize(vs)
    assert vs[0].coords == []


def test_check_all_coordinatizes_at_exit():
    """check_all 出口统一坐标化：演示 BOM + 坐标文件至少有一条违规带坐标。"""
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    ctrl.load_positions(str(SAMPLE_POS))

    checker = DesignRuleChecker()
    violations = checker.check_all(ctrl.context.bom_items, ctrl.context.positions)

    assert violations
    assert any(v.coords for v in violations)


# ── 2. 文本报告 ──

def test_report_includes_coords_line_only_when_located():
    checker = DesignRuleChecker()
    located = _v("U1")
    located.coords = [(10.0, 20.0), (30.5, 40.25)]

    assert "坐标: (10.00, 20.00), (30.50, 40.25) mm" in checker.get_report([located])
    assert "坐标:" not in checker.get_report([_v("GND 板级")])


# ── 3. controller 入口 + reason 码 ──

def _demo_controller() -> AppController:
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    ctrl.load_positions(str(SAMPLE_POS))
    return ctrl


def test_drc_violations_demo_items_carry_coords():
    """一键演示（BOM + 坐标文件）必须给出带坐标的违规清单。"""
    res = _demo_controller().get_drc_violations()

    assert res["ok"] is True and res["reason"] == ""
    assert res["source"] == "positions"
    assert res["violation_count"] >= 1 and res["mapped"] >= 1

    located = [it for it in res["items"] if it["coords"]]
    assert located, "演示数据坐标齐全，违规清单不该全部未定位"
    for it in res["items"]:
        assert it["severity"] in ("error", "warning", "info")
        assert {"rule", "description", "location", "suggestion"} <= set(it)
        for x, y in it["coords"]:
            assert isinstance(x, float) and isinstance(y, float)
    # eel / FastAPI 都直接序列化它
    json.dumps(res, ensure_ascii=False)


def test_drc_violations_reason_no_data():
    res = AppController().get_drc_violations()
    assert res["reason"] == "no_data"
    assert res["items"] == [] and res["source"] == ""


def test_drc_violations_reason_no_positions():
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    res = ctrl.get_drc_violations()
    assert res["reason"] == "no_positions" and res["items"] == []


@pytest.mark.parametrize("stub,expected", [
    ([], "no_violations"),
    ([RuleViolation(rule_name="网络规则", description="板级问题",
                    severity=RuleSeverity.INFO, location="GND")], "unmapped"),
])
def test_drc_violations_reason_codes_from_rule_results(monkeypatch, stub, expected):
    """空违规 / 违规点不到位号 —— reason 语义与热力图端点对齐。"""
    orig = DesignRuleChecker.check_all

    def patched(self, bom_items, positions=None, netlist=None, pcb_data=None):
        orig(self, bom_items, positions, netlist, pcb_data)
        return list(stub)

    monkeypatch.setattr(DesignRuleChecker, "check_all", patched)
    res = _demo_controller().get_drc_violations()

    assert res["reason"] == expected
    assert res["source"] == "positions"

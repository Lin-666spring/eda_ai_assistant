"""热力图（违规计数网格）回归测试 — 2026-09-29。

背景：热力图 = 「位号 → 坐标 → 网格计数」，跟原理图/位图无关。但
`get_heatmap_data()` 原来只读 `pcb_data.component_positions`，于是
**一键演示 / 只导入坐标文件**这条路径永远返回空列表 —— 23 个位号坐标齐全，
界面却显示「无位置数据」。现在位置来源按优先级回落：PCB 元件坐标 > 坐标文件。

锁定的行为：

1. 只有坐标文件（没有 PCB）时也能出网格；
2. PCB 坐标与坐标文件同时存在时以 PCB 为准（坐标系原点跟着 PCB 走）；
3. `check_all()` 传入的 positions 会被记住，之后再单独调 `get_heatmap_data()` 仍可用；
4. 网格边长非法/非正值回落 5mm，并夹到 [0.5, 200] 防除零；
5. `AppController.get_drc_heatmap()` 用 reason 码区分四种「画不出来」的原因。
"""

from __future__ import annotations

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


# ── 1. 位置来源回落 ──

def test_heatmap_uses_positions_file_when_no_pcb():
    """没有 PCB 数据时，坐标文件（Pick & Place）必须能画热力图。"""
    checker = DesignRuleChecker()
    positions = {"R1": {"x": 10.0, "y": 10.0}, "C1": {"x": 12.0, "y": 10.0},
                 "R2": {"x": 30.0, "y": 10.0}}

    meta = checker.build_heatmap([_v("R1"), _v("C1"), _v("R2")], 5.0, positions)

    assert meta["source"] == "positions"
    # R1(10,10) 与 C1(12,10) 同格；R2(30,10) 单独一格
    assert sorted(meta["data"]) == [[1, 1, 2], [5, 1, 1]]
    assert meta["mapped"] == 3
    assert meta["violation_count"] == 3
    assert meta["grid_size_mm"] == 5.0


def test_pcb_positions_take_priority_over_positions_file():
    """两者都在时用 PCB 的坐标 —— 原点跟着 PCB 走，不是坐标文件。"""
    pcb = PCBData(format="test", nets={}, traces=[])
    pcb.component_positions = {"R1": {"x": 100.0, "y": 100.0}}

    checker = DesignRuleChecker()
    checker.check_all([], positions={"R1": {"x": 0.0, "y": 0.0}}, netlist=[], pcb_data=pcb)
    meta = checker.build_heatmap([_v("R1")], 5.0)

    assert meta["source"] == "pcb"
    assert meta["x_min"] == 95.0 and meta["y_min"] == 95.0   # 100 - 5mm 边距
    assert meta["data"] == [[1, 1, 1]]


def test_check_all_remembers_positions_for_legacy_call():
    """兼容旧调用：check_all 传过的 positions，之后单独取热力图也能用。"""
    checker = DesignRuleChecker()
    checker.check_all([], positions={"U1": {"x": 0.0, "y": 0.0}}, netlist=[], pcb_data=None)

    assert checker.get_heatmap_data([_v("U1")]) == [[1, 1, 1]]


def test_heatmap_skips_unparseable_positions_and_unknown_refs():
    """坐标缺失的位号跳过；违规里点不到已知位号（网络/板级问题）就不落格。"""
    checker = DesignRuleChecker()
    positions = {"R1": {"x": 5.0, "y": 5.0}, "X9": {"rotation": 90}, "R2": None}
    meta = checker.build_heatmap(
        [_v("R1"), _v("GND"), _v("X9"), _v(""), _v("R2")], 5.0, positions)

    assert meta["mapped"] == 1
    assert meta["violation_count"] == 5


# ── 2. 网格边长 ──

def test_grid_size_changes_binning():
    """网格越大 → 格子越少、单格计数越高；20mm 时两个位号应落进同一格。"""
    checker = DesignRuleChecker()
    positions = {"R1": {"x": 0.0, "y": 0.0}, "R2": {"x": 12.0, "y": 0.0}}
    violations = [_v("R1"), _v("R2")]

    fine = checker.build_heatmap(violations, 5.0, positions)
    coarse = checker.build_heatmap(violations, 20.0, positions)

    assert len(fine["data"]) == 2
    assert coarse["data"] == [[1, 1, 2]]
    assert coarse["grid_size_mm"] == 20.0


@pytest.mark.parametrize("bad", [0, -3, None, "", "abc", float("nan")])
def test_invalid_grid_size_falls_back_to_default(bad):
    assert DesignRuleChecker._normalize_grid_size(bad) == 5.0


def test_grid_size_is_clamped_to_safe_range():
    assert DesignRuleChecker._normalize_grid_size(1e9) == 200.0
    assert DesignRuleChecker._normalize_grid_size(0.01) == 0.5


# ── 3. controller 入口 + reason 码 ──

def _demo_controller() -> AppController:
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    ctrl.load_positions(str(SAMPLE_POS))
    return ctrl


def test_demo_data_now_renders_heatmap():
    """一键演示（BOM + 坐标文件，无 PCB）之前恒为空表 —— 这条就是那个回归。"""
    res = _demo_controller().get_drc_heatmap(5.0)

    assert res["ok"] is True
    assert res["reason"] == ""
    assert res["source"] == "positions"
    assert res["data"], "演示数据的坐标齐全，热力图不该是空的"
    assert res["mapped"] >= 1
    assert res["violation_count"] >= 1
    for bx, by, cnt in res["data"]:
        assert isinstance(bx, int) and isinstance(by, int) and cnt >= 1
    assert isinstance(res["x_min"], float) and isinstance(res["y_min"], float)


def test_reason_no_data_when_nothing_loaded():
    res = AppController().get_drc_heatmap()
    assert res["reason"] == "no_data" and res["data"] == [] and res["source"] == ""


def test_reason_no_positions_when_only_bom_loaded():
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    res = ctrl.get_drc_heatmap()
    assert res["reason"] == "no_positions" and res["data"] == []


@pytest.mark.parametrize("stub,expected", [
    ([], "no_violations"),
    ([RuleViolation(rule_name="网络规则", description="板级问题",
                    severity=RuleSeverity.INFO, location="GND")], "unmapped"),
])
def test_reason_codes_from_rule_results(monkeypatch, stub, expected):
    """空违规 / 违规点不到位号 —— 前端据此给不同提示，而不是笼统的“无数据”。"""
    orig = DesignRuleChecker.check_all

    def patched(self, bom_items, positions=None, netlist=None, pcb_data=None):
        orig(self, bom_items, positions, netlist, pcb_data)   # 仍要记住 positions
        return list(stub)

    monkeypatch.setattr(DesignRuleChecker, "check_all", patched)
    res = _demo_controller().get_drc_heatmap()

    assert res["reason"] == expected
    assert res["data"] == []
    assert res["source"] == "positions"

"""P2 小项批次的回归测试（2026-10-09）。

覆盖：

1. 板边间距/连接器边沿两条规则改为按板框包围盒算真实边距
   （旧判据拿绝对坐标比门限，不减板框原点）。
2. _xy 位置取值 helper（layout 规则共用的内联写法收编）。
3. .epro2 后缀在扩展名常量与解析器分发里不再缺失。
4. 「死代码 return」的类级 tripwire：src/ 下不允许 return/raise 后跟可达语句。
"""

from __future__ import annotations

import ast
from pathlib import Path

from src.pcb.models import PCBData
from src.pcb.parser import create_parser
from src.rules.base import _xy
from src.rules.checker import DesignRuleChecker

_SRC = Path(__file__).resolve().parents[1] / "src"


def _outline_pcb(source: str = "outline") -> PCBData:
    """板框 (100,100)-(140,150)：原点偏移的典型 .epro2 口径。"""
    pcb = PCBData(format="lceda_epro2")
    pcb.board_outline = {
        "source": source,
        "min_x_mm": 100.0, "min_y_mm": 100.0,
        "max_x_mm": 140.0, "max_y_mm": 150.0,
        "width_mm": 40.0, "height_mm": 50.0,
        "shape": "rectangle",
    }
    return pcb


class _BomItem:
    def __init__(self, reference: str, description: str = ""):
        self.reference = reference
        self.description = description
        self.part_number = ""
        self.value = ""
        self.reference_list = []


# ── 1. 板边间距检查：减板框原点 + 四边判定 ──

def test_edge_clearance_fires_near_edge_on_offset_board():
    """修复前：x=101 恒 > 3，原点偏移板上永远不响；现在按真实边距 1mm 应报。"""
    checker = DesignRuleChecker()
    checker._pcb_data = _outline_pcb()
    bom = [_BomItem("R1"), _BomItem("R2")]
    positions = {"R1": {"x": 101.0, "y": 120.0},   # 距左边 1mm
                 "R2": {"x": 110.0, "y": 120.0}}   # 板内安全区
    out = checker._check_component_edge_clearance(bom, positions, {})
    assert len(out) == 1
    assert "R1" in out[0].description and "R2" not in out[0].description


def test_edge_clearance_checks_all_four_edges():
    """修复前只判 x<3 or y<3（左/下两边）；右/上两边的近边元件现在也要报。"""
    checker = DesignRuleChecker()
    checker._pcb_data = _outline_pcb()
    bom = [_BomItem("R1"), _BomItem("R2")]
    positions = {"R1": {"x": 139.0, "y": 120.0},   # 距右边 1mm
                 "R2": {"x": 110.0, "y": 149.0}}   # 距上边 1mm
    out = checker._check_component_edge_clearance(bom, positions, {})
    assert len(out) == 1
    assert "R1" in out[0].description and "R2" in out[0].description


def test_edge_clearance_skips_without_real_outline():
    """板框退回铜包围盒（source=copper）时边距恒为 0，无判定意义 → 跳过。"""
    checker = DesignRuleChecker()
    checker._pcb_data = _outline_pcb(source="copper")
    bom = [_BomItem("R1")]
    positions = {"R1": {"x": 100.5, "y": 100.5}}
    assert checker._check_component_edge_clearance(bom, positions, {}) == []


# ── 2. 连接器边沿布局：同口径修正 ──

def test_connector_far_from_edge_fires_with_real_distance():
    checker = DesignRuleChecker()
    checker._pcb_data = _outline_pcb()
    bom = [_BomItem("J1", "USB-C 连接器")]
    positions = {"J1": {"x": 120.0, "y": 125.0}}
    # 到四边距离 min(20, 20, 25, 25) = 20mm > 10mm
    out = checker._check_connector_edge_placement(bom, positions, {})
    assert len(out) == 1
    assert "距最近板边 20mm" in out[0].description


def test_connector_near_edge_stays_silent():
    checker = DesignRuleChecker()
    checker._pcb_data = _outline_pcb()
    bom = [_BomItem("J1", "USB-C 连接器")]
    positions = {"J1": {"x": 103.0, "y": 125.0}}   # 距左边 3mm
    assert checker._check_connector_edge_placement(bom, positions, {}) == []


def test_connector_skips_without_real_outline():
    checker = DesignRuleChecker()
    checker._pcb_data = _outline_pcb(source="copper")
    bom = [_BomItem("J1", "USB-C 连接器")]
    positions = {"J1": {"x": 120.0, "y": 125.0}}
    assert checker._check_connector_edge_placement(bom, positions, {}) == []


# ── 3. 元件间距：描述与实现对齐（按导入顺序抽样，非空间最近邻） ──

def test_component_spacing_description_states_sampling():
    checker = DesignRuleChecker()
    checker._pcb_data = _outline_pcb()
    positions = {f"R{i}": {"x": i * 0.9, "y": 0.0} for i in range(6)}  # 相邻 5 对均 0.9mm <1mm
    out = checker._check_component_spacing([_BomItem(f"R{i}") for i in range(6)], positions, {})
    assert len(out) == 1
    assert "抽样" in out[0].description and "非空间最近邻" in out[0].description


# ── 4. _xy helper ──

def test_xy_helper_shapes():
    assert _xy({"x": 1.5, "y": 2.5}) == (1.5, 2.5)
    assert _xy({"x": 1.5}) == (1.5, 0)
    assert _xy([3.0, 4.0]) == (3.0, 4.0)
    assert _xy((5.0,)) == (5.0, 0)
    assert _xy("bad") == (0, 0)
    assert _xy(None) == (0, 0)


# ── 5. .epro2 后缀不再缺失 ──

def test_watcher_extensions_include_epro2():
    from src.constants import WatcherConstants
    from src.core import file_watcher
    assert ".epro2" in WatcherConstants.PCB_EXTENSIONS
    # 单一来源：file_watcher 不得再私藏一份会漂移的副本
    assert file_watcher.PCB_EXTENSIONS is WatcherConstants.PCB_EXTENSIONS


def test_parser_factory_routes_epro2():
    from src.pcb.epro2_parser import Epro2Parser
    assert isinstance(create_parser("demo.epro2"), Epro2Parser)


# ── 6. tripwire：src/ 下不允许 return/raise 后跟死语句 ──

def test_no_dead_code_after_return_in_src():
    """geometry_rules 里曾有无条件的 return [] 跟在 return [RuleViolation] 后
    （P2 批次清理）；此测试防同类问题回流。"""
    dead = []
    for f in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = node.body
            for i, stmt in enumerate(body[:-1]):
                if isinstance(stmt, (ast.Return, ast.Raise)):
                    dead.append(f"{f.relative_to(_SRC)}:{body[i + 1].lineno} in {node.name}")
    assert dead == []

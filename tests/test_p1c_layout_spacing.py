"""P1-15（验收 2026-10-24）元件间距 spatial hash 跨格漏检回归。

旧实现 5mm 网格只扫 ±1 邻域，隐含「体尺寸 ≤ 网格边长」——体长 >10mm 的
封装（SOIC-16/连接器，_L12.0 内嵌尺寸）跨格对全部漏检：大件中心贴近格界时，
0.1mm 间隙的近邻落在 +2 格，实测不报。现在按元件包围盒（外接圆半径 +
全板最大半径 + 间隙阈值）覆盖的网格范围查询，候选对不重不漏。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.rules.checker import DesignRuleChecker


def _pos(x, y, fp, rot=0.0, side="T"):
    return {"x": x, "y": y, "rotation": rot, "side": side,
            "footprint_name": fp, "footprint": fp, "value": "", "device": ""}


# 12mm 体封装（SOIC-16 内嵌尺寸写法）中心贴近 5mm 格界（29.99 → 格 (5,5)），
# 0603 近邻落格 (7,5)——旧 ±1 邻域（格 4..6）扫不到。
_BIG_FP = "SOIC-16_L12.0-W5.3-P1.27-LS7.5-BL"
_BIG = (29.99, 25.0)
_GAP01 = 36.89    # 0603 左缘 36.09，距大件右缘 35.99 → 间隙 0.10mm
_GAP05 = 37.29    # 间隙 0.50mm（放行对照）


def test_large_body_cross_cell_0p1mm_gap_reported():
    """负样本回归：_L12.0 封装与近邻 0.1mm 间隙必须报间距违规
    （旧 ±1 邻域下中心距 6.9mm 但跨 2 格，实测漏报）。"""
    checker = DesignRuleChecker()
    positions = {
        "R1": _pos(_GAP01, 25.0, "R0603"),
        "U1": _pos(*_BIG, fp=_BIG_FP),
    }
    out = checker._check_component_spacing([], positions, {})
    assert len(out) == 1
    assert "R1-U1" in out[0].description


def test_large_body_cross_cell_0p5mm_gap_silent():
    """同布局把间隙拉开到 0.5mm（≥0.2 阈值）不得报——修复不是把阈值放松。"""
    checker = DesignRuleChecker()
    positions = {
        "R1": _pos(_GAP05, 25.0, "R0603"),
        "U1": _pos(*_BIG, fp=_BIG_FP),
    }
    assert checker._check_component_spacing([], positions, {}) == []


def test_large_body_y_direction_cross_cell_reported():
    """跨格漏检与轴方向无关：大件转 90° 长边沿 y、中心贴格界，近邻落 y+2 格。"""
    checker = DesignRuleChecker()
    positions = {
        "U1": _pos(25.0, 29.99, fp=_BIG_FP, rot=90.0),
        "R1": _pos(25.0, 36.49, "R0603"),
    }
    out = checker._check_component_spacing([], positions, {})
    assert len(out) == 1
    assert "R1-U1" in out[0].description


def test_two_large_bodies_cross_cell_reported():
    """两片 12mm 体端对端 0.1mm：中心距 12.1mm、相隔 3 格，旧版必漏。"""
    checker = DesignRuleChecker()
    positions = {
        "U1": _pos(25.0, 25.0, fp=_BIG_FP),
        "U2": _pos(25.0 + 6.0 + 6.0 + 0.1, 25.0, fp=_BIG_FP),
    }
    out = checker._check_component_spacing([], positions, {})
    assert len(out) == 1
    assert "U1-U2" in out[0].description


def test_far_apart_large_body_silent():
    """大件与远端小件（间隙 2mm）保持静默——扩大查询范围不引入远距误报。"""
    checker = DesignRuleChecker()
    positions = {
        "U1": _pos(*_BIG, fp=_BIG_FP),
        "R1": _pos(38.09 + 2.0 + 0.8, 25.0, "R0603"),   # 间隙 ≈2mm
    }
    assert checker._check_component_spacing([], positions, {}) == []

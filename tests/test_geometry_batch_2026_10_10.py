"""几何批（2026-10-10）回归测试。

覆盖三处几何判据重写：

1. 走线板边间距：包围盒口径 → 轮廓多边形真距离（解析器把 BOARD_OUTLINE
   描边链回 outline_rings_mm；切角/开槽板包围盒差几毫米）。
2. 元件间距：索引相邻 4 项抽样 → spatial hash 全对 + 封装体旋转矩形
   真距离（外接框口径会把 45° 旋转件侧向 0.6mm 间隙冤判成相交）。
3. 差分对等长：全网线段和 → chain_segments 最长连续路径（多分支网络的
   线段和不是任何信号的路径长）。
"""

from __future__ import annotations

import math

from src.pcb.models import PCBData, PCBNet, PCBTrace, PCBVia
from src.rules.checker import DesignRuleChecker
from src.rules.layout_rules import _rect_rect_gap, _rect_corners_mm


def _outline_pcb(traces, outline=None, positions=None, pads=None, vias=()):
    nets = {}
    for t in traces:
        nets.setdefault(t.net_name, PCBNet(name=t.net_name, pins=["U1.1"]))
    pcb = PCBData(format="lceda_epro2", nets=nets, traces=traces,
                  vias=list(vias))
    pcb.board_outline = outline or {}
    pcb.component_positions = positions or {}
    pcb.pads = pads or []
    return pcb


def _outline(minx, miny, w, h, rings=None, source="outline"):
    bo = {
        "width_mm": w, "height_mm": h,
        "min_x_mm": minx, "min_y_mm": miny,
        "max_x_mm": minx + w, "max_y_mm": miny + h,
        "shape": "rectangle", "source": source,
    }
    if rings is not None:
        bo["outline_rings_mm"] = rings
    return bo


def _run_edge_rule(checker, pcb):
    return [v for v in checker.check_all([], {}, pcb_data=pcb)
            if "走线板边间距" in v.rule_name]


# ── 1. 走线板边间距：轮廓多边形真距离 ──

def test_edge_true_distance_catches_notch_missed_by_bbox():
    """L 形切角：走线贴近凹角内侧，包围盒口径 20mm「安全」，真距离 0.2mm。"""
    checker = DesignRuleChecker()
    # 50×50 板，右上 20×20 缺角：外环逆时针绕过凹口
    ring = [(0, 0), (50, 0), (50, 30), (30, 30), (30, 50), (0, 50)]
    pcb = _outline_pcb(
        [PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                  segments=[(40, 25, 40, 28)])],   # 距凹角竖边 (30,30)-(30,50) 横向 10mm？不——距 y=30 横边 5mm
        outline=_outline(0, 0, 50, 50, rings=[ring]))
    # 走线 (40,25)-(40,28)：距板右缘 x=50 有 10mm，距凹口横边 y=30 有 2mm
    # → 真距离 2mm 不报。改成贴凹口横边：
    pcb.traces[0].segments = [(40, 29.85, 40, 29.0)]
    v = _run_edge_rule(checker, pcb)
    assert len(v) == 1 and "0.150" in v[0].description


def test_edge_true_distance_silent_when_clear():
    checker = DesignRuleChecker()
    ring = [(0, 0), (50, 0), (50, 30), (30, 30), (30, 50), (0, 50)]
    pcb = _outline_pcb(
        [PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                  segments=[(40, 25, 40, 27)])],
        outline=_outline(0, 0, 50, 50, rings=[ring]))
    assert _run_edge_rule(checker, pcb) == []


def test_edge_crossing_boundary_is_zero_clearance():
    checker = DesignRuleChecker()
    ring = [(0, 0), (50, 0), (50, 30), (30, 30), (30, 50), (0, 50)]
    pcb = _outline_pcb(
        [PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                  segments=[(48, 25, 52, 25)])],   # 跨过 x=50 右缘
        outline=_outline(0, 0, 50, 50, rings=[ring]))
    v = _run_edge_rule(checker, pcb)
    assert len(v) == 1 and "0.000" in v[0].description


def test_edge_bbox_fallback_without_rings():
    """无轮廓环（异常数据）退回包围盒口径——旧行为保底。"""
    checker = DesignRuleChecker()
    pcb = _outline_pcb(
        [PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                  segments=[(0.1, 25, 10, 25)])],
        outline=_outline(0, 0, 50, 50, rings=None))
    assert len(_run_edge_rule(checker, pcb)) == 1


def test_edge_skipped_for_copper_bbox_even_with_rings():
    checker = DesignRuleChecker()
    ring = [(0, 0), (50, 0), (50, 50), (0, 50)]
    pcb = _outline_pcb(
        [PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                  segments=[(0.1, 25, 10, 25)])],
        outline=_outline(0, 0, 50, 50, rings=[ring], source="copper"))
    assert _run_edge_rule(checker, pcb) == []


# ── 2. 元件间距：旋转矩形真距离 ──

def _pos(x, y, fp, rot=0.0, side="T"):
    return {"x": x, "y": y, "rotation": rot, "side": side,
            "footprint_name": fp, "footprint": fp, "value": "", "device": ""}


def test_spacing_45deg_side_by_side_not_flagged():
    """两只 0603 均转 45°、纯侧向排开 1.41mm 中心距 → 真边距 0.61mm，
    外接框口径会冤判 −0.68mm 相交。"""
    checker = DesignRuleChecker()
    positions = {
        "R1": _pos(0.0, 0.0, "R0603", rot=45.0),
        "R2": _pos(1.0, -1.0, "R0603", rot=45.0),   # 中心距 √2≈1.41mm，垂直于体长方向
    }
    out = checker._check_component_spacing([], positions, {})
    assert out == []


def test_spacing_end_to_end_0402_column_flagged():
    """0402 垂列中心距 0.86mm < 体长 1.0mm → 体相交，报 WARNING。"""
    checker = DesignRuleChecker()
    positions = {
        "R1": _pos(0.0, 0.0, "R0402", rot=90.0),
        "R2": _pos(0.0, 0.86, "R0402", rot=90.0),
    }
    out = checker._check_component_spacing([], positions, {})
    assert len(out) == 1
    assert out[0].severity.name == "WARNING"
    assert "R1-R2" in out[0].description


def test_spacing_opposite_sides_not_flagged():
    checker = DesignRuleChecker()
    positions = {
        "R1": _pos(0.0, 0.0, "R0402", rot=90.0, side="T"),
        "R2": _pos(0.0, 0.5, "R0402", rot=90.0, side="B"),
    }
    assert checker._check_component_spacing([], positions, {}) == []


def test_spacing_unknown_package_skipped():
    """连接器等体尺寸落空的封装不参与配对（诚实跳过）。"""
    checker = DesignRuleChecker()
    positions = {
        "J1": _pos(0.0, 0.0, "USB-C-SMD_TYPE-C-6PIN"),
        "J2": _pos(0.1, 0.1, "USB-C-SMD_TYPE-C-6PIN"),
    }
    assert checker._check_component_spacing([], positions, {}) == []


def test_spacing_standing_thru_module_not_flagged():
    """插针大件（OLED 模块）体矩形罩住 0603 不冤判——通孔 + 体长 ≥8mm
    视为架空站立件。"""
    checker = DesignRuleChecker()
    positions = {
        "LCD1": _pos(0.0, 0.0, "OLED-TH_L27.8-W27.2-P2.54_C9900033791"),
        "C1": _pos(2.0, 3.0, "C0603"),
    }
    pcb = _outline_pcb(
        [], positions=positions,
        pads=[{"ref": "LCD1", "num": "1", "x": 0, "y": 0, "thru": True}])
    checker._pcb_data = pcb
    assert checker._check_component_spacing([], positions, {}) == []


def test_spacing_smd_under_smd_still_flagged():
    """真 SMD 压 SMD（焊盘场互叠）保留判定——站立件豁免不外溢到贴片件。"""
    checker = DesignRuleChecker()
    positions = {
        "U1": _pos(0.0, 0.0, "SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL", rot=90.0),
        "R1": _pos(0.08, 0.76, "R0603"),
    }
    out = checker._check_component_spacing([], positions, {})
    assert len(out) == 1 and out[0].severity.name == "WARNING"


def test_rect_rect_gap_exact_diagonal():
    """45° 两矩形纯侧向：真边距 = 中心距 − 体宽（0.61mm），非外接框负值。"""
    c1 = _rect_corners_mm(0.0, 0.0, 1.6, 0.8, 45.0)
    c2 = _rect_corners_mm(1.0, -1.0, 1.6, 0.8, 45.0)
    gap = _rect_rect_gap(c1, c2)
    assert 0.55 < gap < 0.65
    # 重叠：同向共线、中心距 1.0 < 体长 1.6
    c3 = _rect_corners_mm(1.0, 0.0, 1.6, 0.8, 45.0)
    assert _rect_rect_gap(c1, c3) < 0


# ── 3. 差分等长：链路径长 ──

def _diff_pcb(traces, pairs):
    pcb = _outline_pcb(traces)
    pcb.differential_pairs = [{"net": n, "differential": g, "equal_length_group": g}
                              for g, ns in pairs.items() for n in ns]
    return pcb


def _run_diff_rule(checker, pcb):
    return [v for v in checker.check_all([], {}, pcb_data=pcb)
            if "差分对等长" in v.rule_name]


def test_diff_length_t_branch_not_summed():
    """T 型分支：净 P 一条 30mm 直路；净 N 干路 20mm + 两支 10/11mm。
    旧「线段和」给 N=41mm → 虚差 11mm；链路径取最长支 31mm → 差 1mm 不报。"""
    traces = [
        PCBTrace(net_name="P", layer="Top", width_mm=0.2,
                 segments=[(0, 0, 30, 0)]),
        PCBTrace(net_name="N", layer="Top", width_mm=0.2,
                 segments=[(0, 1, 20, 1)]),
        PCBTrace(net_name="N", layer="Top", width_mm=0.2,
                 segments=[(20, 1, 30, 1)]),
        PCBTrace(net_name="N", layer="Top", width_mm=0.2,
                 segments=[(20, 1, 31, 1)]),
    ]
    checker = DesignRuleChecker()
    assert _run_diff_rule(checker, _diff_pcb(traces, {"USB": ["P", "N"]})) == []
    # N 最长支改 28mm（差 2.1mm > 表外 2.0 门限）→ 报
    traces[3].segments = [(20, 1, 48, 1)]
    v = _run_diff_rule(checker, _diff_pcb(traces, {"USB": ["P", "N"]}))
    assert len(v) == 1


def test_diff_length_simple_net_unchanged():
    """无分支简单网络：链路径长 = 线段和，旧行为不变。"""
    traces = [
        PCBTrace(net_name="P", layer="Top", width_mm=0.2,
                 segments=[(0, 0, 10, 0), (10, 0, 10, 20)]),
        PCBTrace(net_name="N", layer="Top", width_mm=0.2,
                 segments=[(0, 5, 10, 5), (10, 5, 10, 25)]),
    ]
    checker = DesignRuleChecker()
    assert _run_diff_rule(checker, _diff_pcb(traces, {"USB": ["P", "N"]})) == []


# ── 4. 解析器：弧离散化 ──

def test_arc_discretization_semicircle():
    from src.pcb.epro2_parser import _arc_interior_points
    pts = _arc_interior_points((-1, 0), (1, 0), 180.0)
    assert pts and all(abs(math.hypot(x, y) - 1.0) < 1e-9 for x, y in pts)


def test_arc_degenerate_returns_empty():
    from src.pcb.epro2_parser import _arc_interior_points
    assert _arc_interior_points((0, 0), (0, 0), 45.0) == []
    assert _arc_interior_points((0, 0), (5, 0), 0.3) == []


def test_polygon_points_chord_mode_unchanged():
    """默认（arc_segments=0）保持旧弦线行为——覆铜环判定口径不变。"""
    from src.pcb.epro2_parser import _polygon_points
    path = [0, 0, "L", 10, 0, "ARC", 90, 10, 10, "L", 10, 10]
    assert _polygon_points(path) == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (10.0, 10.0)]


# ── 5. 分档表活码回归（几何批发现 29b9766 的死代码 bug）──

def test_diff_bands_actually_fire():
    """USB/HDMI 标签必须命中对应档位——大小写死代码回归锁。"""
    from src.rules.geometry_rules import GeometryRulesMixin
    checker = DesignRuleChecker()
    traces = [
        PCBTrace(net_name="HDMI_CLK_P", layer="Top", width_mm=0.2,
                 segments=[(0, 0, 20, 0)]),
        PCBTrace(net_name="HDMI_CLK_N", layer="Top", width_mm=0.2,
                 segments=[(0, 5, 20.9, 5)]),
    ]
    pcb = _diff_pcb(traces, {"HDMI_A": ["HDMI_CLK_P", "HDMI_CLK_N"]})
    v = _run_diff_rule(checker, pcb)
    assert len(v) == 1
    assert "高速串行" in v[0].description and "0.5mm" in v[0].description

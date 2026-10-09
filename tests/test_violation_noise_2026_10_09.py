"""违规噪声清扫批次的回归测试（2026-10-09）。

78 板金样 3202 → 2048（experiment_results/violation_noise_2026-10-09/）：
- 走线锐角 439→9：覆铜网格闭合环/短桩弦线、过孔圆心结合点、45° 栅格端点
  相接全部豁免，自由角度真尖角保留；
- 位号跳号合并每板 1 条（设计卫生）；封装一致性做 C/R 前缀归一；
- 时钟包地加调试/RTC 排除 + 15mm 长度门；线宽删 60% 主流线宽相对条款；
- 光学定位/地平面/丝印×2/PDN 改按证据触发（无证据静默或文案可证伪）。
"""

from __future__ import annotations

from src.bom.parser import BOMItem
from src.pcb.models import PCBData, PCBTrace, PCBVia
from src.rules.checker import DesignRuleChecker


def _item(ref="", value="", pn="", desc="", pkg="", qty=1) -> BOMItem:
    return BOMItem(reference=ref, value=value, package=pkg,
                   part_number=pn, description=desc, quantity=qty)


def _pcb(traces=(), vias=(), layers=(), pours=()) -> PCBData:
    pcb = PCBData(format="lceda_epro2")
    pcb.traces = list(traces)
    pcb.vias = list(vias)
    pcb.layers = list(layers)
    pcb.copper_pours = list(pours)
    return pcb


def _run(pcb: PCBData, bom_items=(), netlist=None, rule=""):
    checker = DesignRuleChecker()
    checker._pcb_data = pcb
    return getattr(checker, rule)(list(bom_items), {}, netlist or {})


def _trace(net, segments, w=0.254, layer="Top Layer"):
    return PCBTrace(net_name=net, layer=layer, width_mm=w, segments=list(segments))


def _via(x, y, net="N"):
    return PCBVia(position=(x, y), drill_mm=0.3, pad_mm=0.6,
                  from_layer="Top Layer", to_layer="Bottom Layer", net_name=net)


# ── 走线锐角：四族伪影豁免，自由角度真尖角保留 ──

def test_acute_closed_ring_mesh_exempt():
    # 网格铺铜单元：闭合三角环上有两个 45° 内角——覆铜几何不是走线拐角
    t = _trace("GND", [(0, 0, 2, 0), (2, 0, 1, 1), (1, 1, 0, 0)])
    assert _run(_pcb(traces=[t]), rule="_check_trace_acute_angles") == []


def test_acute_via_join_exempt():
    # 两条路径经同一过孔相接：45° 楔形顶点落在过孔圆心 → 结合点，不报
    t = _trace("+5V", [(0, 0, 2, 0), (2, 0, 1, 1)])
    pcb = _pcb(traces=[t], vias=[_via(2, 0)])
    assert _run(pcb, rule="_check_trace_acute_angles") == []


def test_acute_grid_backfold_exempt():
    # 45° 栅格端点相接/折返：内角恰 45.0°，无过孔也不报（真拐角内角只会是 135°/90°）
    t = _trace("TP4056_VCC", [(0, 0, 2, 0), (2, 0, 1, 1)])
    assert _run(_pcb(traces=[t]), rule="_check_trace_acute_angles") == []


def test_acute_free_angle_still_fires():
    # 自由角度真尖角（~59°）仍报——这才是酸陷阱判据的目标
    t = _trace("SIG", [(0, 0, 2, 0), (2, 0, 1.4, 1)])
    out = _run(_pcb(traces=[t]), rule="_check_trace_acute_angles")
    assert len(out) == 1 and "59" in out[0].description


def test_acute_pour_registered_trace_skipped():
    # (net,layer) 已注册覆铜区：thermal/void 弦线模板角（金样 82.4°×N 族）整组跳过
    t = _trace("VDDQ_DDR_S0", [(0, 0, 2, 0), (2, 0, 1.4, 1)])
    pcb = _pcb(traces=[t], pours=[{"net_name": "VDDQ_DDR_S0", "layer": "Top Layer"}])
    assert _run(pcb, rule="_check_trace_acute_angles") == []


def test_right_angle_at_via_exempt_but_real_bend_fires():
    # 直角（高速网）：真拐角报；同一拐角顶点落在过孔上则豁免
    t = _trace("USB_DP", [(0, 0, 2, 0), (2, 0, 2, 2)])
    out = _run(_pcb(traces=[t]), rule="_check_trace_acute_angles")
    assert len(out) == 1 and "直角" in out[0].rule_name
    out2 = _run(_pcb(traces=[t], vias=[_via(2, 0)]), rule="_check_trace_acute_angles")
    assert out2 == []


# ── 封装一致性：C/R 单字母前缀归一 ──

def test_package_prefix_variants_not_flagged():
    bom = [_item(ref="C1", pn="CL05B104KB54PNC", pkg="C0603"),
           _item(ref="R1", pn="CL05B104KB54PNC", pkg="0603")]
    assert _run(_pcb(), bom, rule="_check_package_consistency") == []


def test_package_letter_prefix_inductor():
    bom = [_item(ref="L1", pn="X", pkg="L3216"), _item(ref="L2", pn="X", pkg="3216")]
    assert _run(_pcb(), bom, rule="_check_package_consistency") == []


def test_package_real_mismatch_still_fires():
    bom = [_item(ref="C1", pn="CL05B104KB54PNC", pkg="0603"),
           _item(ref="C2", pn="CL05B104KB54PNC", pkg="0805")]
    out = _run(_pcb(), bom, rule="_check_package_consistency")
    assert len(out) == 1 and "0603" in out[0].description and "0805" in out[0].description


# ── 位号连续性：每板至多 1 条汇总 ──

def test_reference_gap_merged_single_entry():
    bom = [_item(ref="U2"), _item(ref="U4"), _item(ref="C1"), _item(ref="C5")]
    out = _run(_pcb(), bom, rule="_check_reference_continuity")
    assert len(out) == 1
    assert "U2→U4" in out[0].description and "C1→C5" in out[0].description


def test_reference_no_gap_silent():
    bom = [_item(ref="U1"), _item(ref="U2"), _item(ref="R1,R2")]
    assert _run(_pcb(), bom, rule="_check_reference_continuity") == []


# ── 光学定位点：有 MARK 器件静默，无则「未检测到」 ──

def _positions_with_mark(has_mark: bool) -> dict:
    pos = {f"U{i}": {"footprint_name": "SOIC-8", "value": "", "part_number": "",
                      "device": "d", "footprint": "f"} for i in range(11)}
    if has_mark:
        pos["MP1"] = {"footprint_name": "MARK-POINT", "value": "",
                       "part_number": "", "device": "d", "footprint": "f"}
    return pos


def test_fiducial_present_silent():
    from src.rules.layout_rules import LayoutRulesMixin
    rule = LayoutRulesMixin._check_fiducial_mark
    assert rule(object(), [], _positions_with_mark(True), {}) == []


def test_fiducial_absent_honest_wording():
    from src.rules.layout_rules import LayoutRulesMixin
    rule = LayoutRulesMixin._check_fiducial_mark
    out = rule(object(), [], _positions_with_mark(False), {})
    assert len(out) == 1 and "未检测到" in out[0].description


# ── 地平面：有 GND 铺铜静默，无则「未检测到」 ──

def test_ground_pour_present_silent():
    pcb = _pcb(pours=[{"net_name": "GND", "layer": "Top Layer"}])
    assert _run(pcb, rule="_check_ground_plane_continuity") == []


def test_ground_no_pour_fires():
    out = _run(_pcb(), rule="_check_ground_plane_continuity")
    assert len(out) == 1 and "未检测到 GND" in out[0].description


# ── PDN：真实板面积 + 估算标注；无板框数据静默 ──

def test_pdn_real_area_and_estimate_label():
    pcb = _pcb()
    pcb.board_outline = {"width_mm": 50, "height_mm": 40}
    out = _run(pcb, bom_items=[_item(ref="U1", desc="LDO 5V")],
               rule="_check_pdn_target_impedance")
    assert len(out) == 1
    assert "板面积 2000mm²" in out[0].description and "估算" in out[0].description


def test_pdn_without_board_outline_silent():
    out = _run(_pcb(), bom_items=[_item(ref="U1", desc="LDO 5V")],
               rule="_check_pdn_target_impedance")
    assert out == []


# ── 时钟包地：调试/RTC 排除 + 长度门 ──

def test_clock_guard_debug_and_rtc_excluded():
    long = [(0, 0, 10, 0), (10, 0, 20, 0), (20, 0, 30, 0), (30, 0, 40, 0),
            (40, 0, 50, 0), (50, 0, 60, 0), (60, 0, 70, 0), (70, 0, 80, 0),
            (80, 0, 90, 0), (90, 0, 100, 0)]     # 100mm
    for net in ("SWCLK", "OSC32_IN", "XTAL_32K", "JTAG_TCK"):
        t = _trace(net, long)
        assert _run(_pcb(traces=[t]), rule="_check_clock_guard_trace") == [], net


def test_clock_guard_short_osc_silent():
    t = _trace("OSC_IN", [(0, 0, 5, 0), (5, 0, 10, 0)])   # 10mm 晶振短线
    assert _run(_pcb(traces=[t]), rule="_check_clock_guard_trace") == []


def test_clock_guard_long_clk_fires():
    long = [(x, 0, x + 5, 0) for x in range(0, 30, 5)]    # 30mm
    t = _trace("CLK_50MHZ", long)
    out = _run(_pcb(traces=[t]), rule="_check_clock_guard_trace")
    assert len(out) == 1 and "30mm" in out[0].description


# ── 丝印两条：无丝印数据守卫，落地 silk_elements 后启用 ──

def test_silkscreen_rules_silent_without_silk_data():
    pcb = _pcb()
    pcb.component_positions = {f"U{i}": {"x": i, "y": 0} for i in range(12)}
    assert _run(pcb, rule="_check_silkscreen_readability") == []
    assert _run(pcb, rule="_check_silkscreen_pad_clearance") == []


def test_silkscreen_rules_fire_when_silk_data_lands():
    pcb = _pcb()
    pcb.component_positions = {f"U{i}": {"x": i, "y": 0} for i in range(12)}
    pcb.metadata = {"silk_elements": 20}       # 解析器落地丝印解析后填此键
    assert len(_run(pcb, rule="_check_silkscreen_readability")) == 1
    assert len(_run(pcb, rule="_check_silkscreen_pad_clearance")) == 1

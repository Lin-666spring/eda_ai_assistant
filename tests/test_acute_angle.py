"""锐角/直角走线规则 + 线段串联几何的单元测试。

回归背景：旧实现判据是 t.has_sharp_angle，没有任何解析器设置该属性，
规则从未触发（见 memories/audit-findings.md）。现在改为从 segments 做
端点串联后真实计算内角。
"""

import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.constants import PCB
from src.pcb.geometry import chain_segments, polyline_corners, trace_corners
from src.pcb.models import PCBData, PCBTrace, PCBVia
from src.rules.checker import DesignRuleChecker, RuleSeverity

ACUTE_RULE = "走线锐角检查"
RIGHT_RULE = "走线直角检查"


def _checker_with(pcb: PCBData) -> DesignRuleChecker:
    checker = DesignRuleChecker()
    checker._pcb_data = pcb
    return checker


def _rule_violations(segs, net: str = "SIG", layer: str = "TopLayer"):
    pcb = PCBData(format="lceda_epro2")
    pcb.traces.append(PCBTrace(net_name=net, layer=layer, width_mm=0.25, segments=list(segs)))
    return _checker_with(pcb)._check_trace_acute_angles([], {}, {})


def _names(violations):
    return [v.rule_name for v in violations]


# ══════════════════ 几何：线段串联 ══════════════════

class TestChainSegments:
    def test_unordered_reversed_segments_form_one_polyline(self):
        """线段乱序 + 首尾颠倒也要串成一条折线。"""
        segs = [(10, 0, 10, 10), (0, 0, 10, 0)]
        lines = chain_segments(segs)
        assert len(lines) == 1
        # 方向取决于端点下标，不作要求；只要求串成同一条折线
        assert lines[0] in (
            [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
            [(10.0, 10.0), (10.0, 0.0), (0.0, 0.0)],
        )

    def test_duplicate_segments_collapse(self):
        """同一线段重复出现（实测 .epro2 常见）不能产生折返假拐角。"""
        segs = [(0, 0, 10, 0), (10, 0, 10, 10), (0, 0, 10, 0)]
        corners = trace_corners(segs)
        assert [round(c.angle_deg) for c in corners] == [90]
        assert len(chain_segments(segs)) == 1

    def test_disconnected_chains_split(self):
        segs = [(0, 0, 10, 0), (10, 0, 10, 10), (50, 50, 60, 50)]
        lines = chain_segments(segs)
        assert sorted(len(line) for line in lines) == [2, 3]

    def test_t_junction_has_no_corner(self):
        """T 形节点（度数 3）不是走线拐角，不参与判定。"""
        segs = [(0, 0, 10, 0), (10, 0, 20, 0), (10, 0, 10, 10)]
        assert len(chain_segments(segs)) == 3
        assert trace_corners(segs) == []

    def test_near_endpoints_merged_within_tolerance(self):
        segs = [(0, 0, 10, 0), (10.005, 0.002, 10, 10)]
        lines = chain_segments(segs)
        assert len(lines) == 1
        assert lines[0][1] == (10.0, 0.0)

    def test_zero_length_segments_dropped(self):
        assert chain_segments([(1, 1, 1, 1)]) == []
        assert chain_segments([]) == []

    def test_closed_loop_keeps_all_four_corners(self):
        segs = [(0, 0, 10, 0), (10, 0, 10, 10), (10, 10, 0, 10), (0, 10, 0, 0)]
        corners = trace_corners(segs)
        assert len(corners) == 4
        assert all(round(c.angle_deg) == 90 for c in corners)

    def test_corner_angle_definition(self):
        """45° 布线 → 内角 135°；直角 → 90°；折返 → 接近 0°。"""
        assert round(trace_corners([(0, 0, 10, 0), (10, 0, 20, 10)])[0].angle_deg) == 135
        assert round(trace_corners([(0, 0, 10, 0), (10, 0, 10, 10)])[0].angle_deg) == 90
        assert trace_corners([(0, 0, 10, 0), (10, 0, 0, 0.5)])[0].angle_deg < 5

    def test_min_leg_filter_drops_pad_stub(self):
        segs = [(0, 0, 10, 0), (10, 0, 9.98, 0.02)]   # 45° 锐角，但腿长仅 0.028mm
        assert len(trace_corners(segs)) == 1
        assert trace_corners(segs, min_leg_mm=0.05) == []

    def test_polyline_corners_handles_short_input(self):
        assert polyline_corners([(0, 0)]) == []
        assert polyline_corners([(0, 0), (1, 0)]) == []


# ══════════════════ 规则：_check_trace_acute_angles ══════════════════

class TestAcuteAngleRule:
    def test_acute_corner_flagged_as_warning(self):
        violations = _rule_violations([(0, 0, 10, 0), (10, 0, 2, 1)])
        assert _names(violations) == [ACUTE_RULE]
        assert violations[0].severity == RuleSeverity.WARNING
        assert "SIG" in violations[0].description

    def test_45_degree_routing_is_clean(self):
        assert _rule_violations([(0, 0, 10, 0), (10, 0, 20, 10)]) == []

    def test_right_angle_reported_as_info(self):
        # 2026-09-24：直角只对高速/时钟/差分网络报（低速线直角可接受），故用高速网络名
        violations = _rule_violations([(0, 0, 10, 0), (10, 0, 10, 10)], net="USB_DP")
        assert _names(violations) == [RIGHT_RULE]
        assert violations[0].severity == RuleSeverity.INFO

    def test_right_angle_on_low_speed_net_ignored(self):
        """低速网络（按键/GPIO/32kHz 等）的直角可接受，不再逐块板提示。"""
        assert _rule_violations([(0, 0, 10, 0), (10, 0, 10, 10)], net="KEY_IN") == []

    def test_straight_trace_clean(self):
        assert _rule_violations([(0, 0, 10, 0), (10, 0, 20, 0)]) == []

    def test_duplicate_segment_no_false_acute(self):
        """重复线段以前会被串成折返，误报 0° 锐角。"""
        segs = [(0, 0, 10, 0), (10, 0, 10, 10), (0, 0, 10, 0)]
        violations = _rule_violations(segs, net="USB_DP")
        assert _names(violations) == [RIGHT_RULE]

    def test_pad_entry_stub_ignored(self):
        segs = [(0, 0, 10, 0), (10, 0, 9.98, 0.02)]
        assert _rule_violations(segs) == []

    def test_unnamed_net_skipped(self):
        assert _rule_violations([(0, 0, 10, 0), (10, 0, 2, 1)], net="") == []

    def test_no_pcb_data_returns_empty(self):
        checker = DesignRuleChecker()
        assert checker._check_trace_acute_angles([], {}, {}) == []

    def test_thresholds_come_from_constants(self):
        """内角恰好落在直角带内的不应报锐角。"""
        angle = PCB.TRACE_RIGHT_ANGLE_MIN_DEG
        assert PCB.TRACE_ACUTE_ANGLE_MAX_DEG <= angle
        # 89.5° 内角：比锐角上限大、在直角带内
        rad = math.radians(angle + 0.5)
        segs = [(0, 0, 10, 0), (10, 0, 10 + 10 * math.cos(rad), 10 * math.sin(rad))]
        assert _names(_rule_violations(segs, net="USB_DP")) == [RIGHT_RULE]


class TestViaAnchorFilter:
    """2026-10-06 回归：过孔锚点此前从未生效——PCBVia 只有 position 元组、
    没有 x/y 属性，原实现 getattr(v, "x") 恒为 None，顶点落在过孔上的
    焊盘入口拐角（两腿均 <0.5mm、距过孔 <1.0mm）不会被过滤。
    """

    @staticmethod
    def _pcb_with_via(via_pos):
        # 拐角顶点 (10, 0)，内角约 8°（锐角），两腿 0.30mm / 0.28mm（均 <0.5mm）
        pcb = PCBData(format="lceda_epro2")
        pcb.traces.append(PCBTrace(
            net_name="SIG", layer="TopLayer", width_mm=0.25,
            segments=[(9.7, 0, 10, 0), (10, 0, 9.72, 0.04)],
        ))
        pcb.vias.append(PCBVia(
            position=via_pos, drill_mm=0.3, pad_mm=0.6,
            from_layer="TopLayer", to_layer="BottomLayer", net_name="SIG",
        ))
        return pcb

    def test_corner_on_via_filtered(self):
        """顶点距过孔 0.005mm（< TRACE_CORNER_PAD_CLEAR_MM=1.0mm）→ 焊盘入口几何，不报。"""
        pcb = self._pcb_with_via((10.0, 0.005))
        assert _checker_with(pcb)._check_trace_acute_angles([], {}, {}) == []

    def test_same_corner_far_from_via_still_flagged(self):
        """同一拐角、过孔移到远处 → 恢复报锐角。"""
        pcb = self._pcb_with_via((100.0, 100.0))
        violations = _checker_with(pcb)._check_trace_acute_angles([], {}, {})
        assert _names(violations) == [ACUTE_RULE]


class TestRealEpro2:
    def test_rule_runs_on_real_board(self):
        files = sorted((PROJECT_ROOT / "test_data" / "_incoming_epro2").rglob("*.epro2"))
        if not files:
            pytest.skip("无 .epro2 测试数据")
        from src.pcb.epro2_parser import Epro2Parser

        pcb = Epro2Parser().parse(str(files[0]))
        violations = _checker_with(pcb)._check_trace_acute_angles([], {}, {})
        assert isinstance(violations, list)
        nets = {t.net_name for t in pcb.traces if t.net_name}
        assert len(violations) <= len(nets)      # 每网络最多各报一次锐角/直角
        for v in violations:
            assert v.rule_name in (ACUTE_RULE, RIGHT_RULE)
            assert v.location

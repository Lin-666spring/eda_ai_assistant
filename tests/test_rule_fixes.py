"""规则判据修复的回归测试（2026-09-18 抽查）。

覆盖两处已确认的判据 bug：

1. _check_power_traces 的「板级 is_inner」→ 外层电源线被按内层降额（容量腰斩），
   在多层板上产出 ERROR 级误报；现在按**最窄那条走线自己的层**判定。
2. _check_bom_value_range 的 E24 查表相差 10 倍（未归一化 mantissa）→
   20kΩ/22µF/100nF 等标准值全被判非 E24；现在归一化到 [1,10) 并用 E24 的 ±5% 容差。
"""

from __future__ import annotations

from src.pcb.models import PCBData, PCBNet, PCBTrace
from src.rules.checker import DesignRuleChecker, _is_inner_layer


def _pcb(traces, layers=None) -> PCBData:
    nets = {}
    for t in traces:
        nets.setdefault(t.net_name, PCBNet(name=t.net_name, pins=["U1.1", "U1.2"]))
    pcb = PCBData(format="lceda_epro2", nets=nets, traces=traces)
    pcb.layers = layers or ["Top Layer", "Bottom Layer", "GND02", "S03"]
    return pcb


def _power_trace(net: str, width: float, layer: str) -> PCBTrace:
    return PCBTrace(net_name=net, layer=layer, width_mm=width,
                    segments=[(0.0, 0.0, 10.0, 0.0)])


class _BomItem:
    def __init__(self, description: str):
        self.description = description
        self.part_number = ""
        self.value = ""
        self.reference = ""


def _bom():
    """BOM 让 _estimate_power_current 估出 1.3A → VCC5V 需求 0.78A。

    0.254mm 外层容量≈0.89A（不报）、内层≈0.44A（报），正好卡在两者之间。
    """
    return [_BomItem("STM32F103"), _BomItem("ESP32-WROOM")]


# ── 1. 电源载流：外层 / 内层 ──

def test_outer_power_trace_not_derated_as_inner():
    """0.254mm 在 Top 层按外层约 0.89A：需求 0.78A 时不该报（修复前会按内层 0.44A 误报）。"""
    traces = [
        _power_trace("VCC5V", 0.254, "Top Layer"),
        # 板上另有内层电源走线 —— 修复前这个事实会让整块板都按内层算
        _power_trace("VCC3", 0.254, "S03"),
    ]
    checker = DesignRuleChecker()
    checker._pcb_data = _pcb(traces)
    violations = checker._check_power_traces(_bom(), {}, {})
    names = {v.location for v in violations}
    assert "VCC5V" not in names, "外层电源线被按内层降额（回归）"
    assert "VCC3" in names, "内层同名宽度的线该报却没报"


def test_inner_power_trace_still_checked_with_inner_factor():
    """同样的线宽在内层确实载流不足 → 保留告警，且描述里写明内层。"""
    traces = [_power_trace("VCC5V", 0.254, "S03")]
    checker = DesignRuleChecker()
    checker._pcb_data = _pcb(traces)
    violations = checker._check_power_traces(_bom(), {}, {})
    assert [v.location for v in violations] == ["VCC5V"]
    assert "内层" in violations[0].description
    assert "0.44A" in violations[0].description   # 内层系数：容量约为外层一半


def test_is_inner_layer_recognises_stackup_names():
    pcb = _pcb([], layers=["Top Layer", "Bottom Layer", "GND02", "S03", "PWR05"])
    assert _is_inner_layer(pcb, "Top Layer") is False
    assert _is_inner_layer(pcb, "Bottom Layer") is False
    assert _is_inner_layer(pcb, "GND02") is True
    assert _is_inner_layer(pcb, "S03") is True
    assert _is_inner_layer(pcb, "PWR05") is True


# ── 2. E24 参数范围 ──

class _Item:
    def __init__(self, reference: str, value: str):
        self.reference = reference
        self.value = value
        self.part_number = ""
        self.description = ""


def _e24_hits(values: list[tuple[str, str]]) -> list[str]:
    checker = DesignRuleChecker()
    checker._pcb_data = _pcb([])
    items = [_Item(ref, val) for ref, val in values]
    return [v.location for v in checker._check_bom_value_range(items, {}, {})]


def test_e24_standard_values_pass():
    """修复前这些全被判「不在 E24」：未归一化的 20/22/100 与 e*10 比较差 10 倍。"""
    values = [("R33", "20kΩ"), ("C102", "22uF"), ("C5", "100nF"),
              ("R1", "4.7KΩ"), ("R2", "13k"), ("R3", "27k"),
              ("C6", "0.1uF"), ("R4", "1MΩ")]
    assert _e24_hits(values) == []


def test_non_e24_value_is_flagged():
    """E24 相邻档只差约 10%，用 ±5% 容差才判得出真非标值（1.4 不在 E24）。"""
    assert _e24_hits([("R9", "1.4kΩ")]) == ["R9"]


def test_value_parser_skips_package_codes():
    """三位数封装/编码（0603/103）不参与 E24 判定。"""
    assert _e24_hits([("R8", "0603"), ("R7", "103")]) == []

"""特征阻抗匹配规则 2026-10-09 判读修正的回归测试。

78 板全量判读（experiment_results/impedance_recheck_2026-10-09/）确认：
- 单端「时钟按 50Ω」45 条全为误报（SPI/SIM/SDIO/晶振时钟无受控阻抗要求）；
- 差分按 P/N 双计；表外接口（RS485/SDIO）被默认 100Ω 硬判；
- 表内接口的差分告警换真实叠层复算仍越界，是真检出。
"""

from __future__ import annotations

from src.pcb.models import PCBData, PCBTrace
from src.rules.base import RuleSeverity
from src.rules.checker import DesignRuleChecker


def _pcb(declarations: list[tuple[str, str, str]], *, n_layers: int = 4) -> PCBData:
    """declarations: [(net, group, width_mm), ...]，每网一条水平走线（y=0）。

    n_layers=4（默认）：补两条 GND 内层/底层走线凑足 3 个层名，
    infer_copper_layer_count 判 4 层 → 走 JLC PP 0.2104/εr4.6 叠层预设
    （2026-10-10 标准表批；GND 网不进单端判据，不影响断言）。
    n_layers=2：仅 Top Layer，判 2 层板 → 受控阻抗降级 WARNING。
    """
    pcb = PCBData(format="lceda_epro2")
    pcb.traces = [
        PCBTrace(net_name=net, layer="Top Layer", width_mm=w,
                 segments=[(0.0, 0.0, 10.0, 0.0)])
        for net, _, w in declarations
    ]
    if n_layers >= 4:
        pcb.traces.append(PCBTrace(net_name="GND", layer="MidLayer1",
                                   width_mm=0.5, segments=[(0.0, 5.0, 10.0, 5.0)]))
        pcb.traces.append(PCBTrace(net_name="GND", layer="Bottom Layer",
                                   width_mm=0.5, segments=[(0.0, 6.0, 10.0, 6.0)]))
    pcb.differential_pairs = [{"net": net, "differential": group}
                              for net, group, _ in declarations if group]
    return pcb


def _rule(pcb: PCBData):
    checker = DesignRuleChecker()
    checker._pcb_data = pcb
    return checker._check_impedance_matching([], {}, {})


# ── 单端：只判 RF/天线 ──

def test_clock_spi_xtal_nets_not_judged():
    """修复前 SPI1_CLK/XTAL_IN/SD0_CLK 全按 50Ω 报 ERROR（45 条全误报）。"""
    pcb = _pcb([("SPI1_CLK", "", 0.152), ("XTAL_IN", "", 0.152),
                ("SD0_CLK", "", 0.158), ("OSC_OUT", "", 0.152)])
    assert _rule(pcb) == []


def test_antenna_net_off_target_is_flagged():
    pcb = _pcb([("ANT", "", 0.158)])
    out = _rule(pcb)
    assert len(out) == 1 and "单端" in out[0].description


def test_rf_net_in_tolerance_silent():
    """0.3mm 在 4 层预设 h=0.2104/er=4.6 下 Z₀≈53.6Ω，落在 50±25% 内。"""
    pcb = _pcb([("RF_OUT", "", 0.3)])
    assert _rule(pcb) == []


def test_two_layer_controlled_impedance_downgraded():
    """标准表批：2 层板无参考平面，受控阻抗必不达标 → 降级 WARNING 注明根因，
    不再按 4 层 h=0.2 假设报 ERROR。"""
    pcb = _pcb([("USB_DP", "USB", 0.158), ("USB_DM", "USB", 0.158)], n_layers=2)
    pcb.traces[1].segments = [(0.0, 0.361, 10.0, 0.361)]
    out = _rule(pcb)
    assert len(out) == 1
    assert out[0].severity == RuleSeverity.WARNING
    assert "2 层板无参考平面" in out[0].suggestion


# ── 差分：按对聚合、表外不判 ──

def test_usb_pair_reported_once_with_both_names():
    """修复前 P/N 各报一条；现在按对一条、描述含双网名。"""
    pcb = _pcb([("USB_DP", "USB", 0.158), ("USB_DM", "USB", 0.158),
                ("USB_DM", "", 0.158)])
    # 两条同层水平线相距 0.361mm
    pcb.traces[1].segments = [(0.0, 0.361, 10.0, 0.361)]
    out = _rule(pcb)
    assert len(out) == 1
    assert "USB_DP" in out[0].description and "USB_DM" in out[0].description
    assert "偏离目标 90Ω" in out[0].description


def test_usb_pair_in_tolerance_silent():
    """w=0.17/s=0.1 在 h=0.2 下 Zdiff≈98Ω，落在 90±25% 内。"""
    pcb = _pcb([("USB_DP", "USB", 0.17), ("USB_DM", "USB", 0.17)])
    pcb.traces[1].segments = [(0.0, 0.1, 10.0, 0.1)]
    assert _rule(pcb) == []


def test_rs485_declared_pair_not_judged():
    """修复前 RS485_A/B 被 _HIGH_SPEED_IF_KW 放行、默认套 100Ω 报 ERROR。"""
    pcb = _pcb([("RS485_A", "RS485", 0.152), ("RS485_B", "RS485", 0.152)])
    pcb.traces[1].segments = [(0.0, 0.279, 10.0, 0.279)]
    assert _rule(pcb) == []


def test_mipi_pair_judged_at_100ohm():
    pcb = _pcb([("MIPI_DSI_0P", "MIPI_DSI", 0.117), ("MIPI_DSI_0N", "MIPI_DSI", 0.117)])
    pcb.traces[1].segments = [(0.0, 0.269, 10.0, 0.269)]
    out = _rule(pcb)
    assert len(out) == 1 and "偏离目标 100Ω" in out[0].description


def test_pair_with_unrouted_member_skipped():
    """对内一条网络没布线 → 无法判定，不报。"""
    pcb = _pcb([("USB_DP", "USB", 0.158)])   # USB_DM 无走线
    assert _rule(pcb) == []


def test_pcie_pair_judged_at_100ohm():
    """PCIE_REFCLK 等此前不在目标表、被默认 100Ω 误碰；现在表内明示 100Ω。"""
    pcb = _pcb([("PCIE0_RXP", "PCIE", 0.109), ("PCIE0_RXN", "PCIE", 0.109)])
    pcb.traces[1].segments = [(0.0, 0.295, 10.0, 0.295)]
    out = _rule(pcb)
    assert len(out) == 1 and "偏离目标 100Ω" in out[0].description

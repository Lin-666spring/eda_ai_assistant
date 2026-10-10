"""子串/存在性判据主体修正的回归测试（2026-10-09）。

10-06 抽查 §4B「判据用存在性/子串代替网表与几何」的收口：
- 串扰把差分对两半当干扰（5/5 样本）；差分间距缺高速门控/重叠前置；
- BOM 五规则用「描述含电阻/电容」恒报；ESD/EMI/反接靠描述认器件
  （SN74HC125PWR 后缀成入口、SS54/P6SMBJ6.0CA 全漏）；
- 裸 rf/op/SW 子串；net_antenna 把零引脚网络算单端。
金样对比见 experiment_results/substring_criteria_2026-10-09/。
"""

from __future__ import annotations

from src.bom.parser import BOMItem
from src.pcb.models import PCBData, PCBNet, PCBTrace, PCBVia
from src.rules.base import _has_power_entry, _net_kw_hit, _row_text
from src.rules.checker import DesignRuleChecker


def _item(ref="", value="", pn="", desc="", pkg="", qty=1) -> BOMItem:
    return BOMItem(reference=ref, value=value, package=pkg,
                   part_number=pn, description=desc, quantity=qty)


def _pcb(traces=(), nets=None, vias=(), layers=(), diff_pairs=()) -> PCBData:
    pcb = PCBData(format="lceda_epro2")
    pcb.traces = list(traces)
    pcb.nets = nets or {}
    pcb.vias = list(vias)
    pcb.layers = list(layers)
    pcb.differential_pairs = list(diff_pairs)
    return pcb


def _run(pcb: PCBData, bom_items=(), netlist=None, rule=""):
    checker = DesignRuleChecker()
    checker._pcb_data = pcb
    return getattr(checker, rule)(list(bom_items), {}, netlist or {})


def _trace(net, y, w=0.158, layer="Top Layer", x0=0.0, x1=10.0):
    return PCBTrace(net_name=net, layer=layer, width_mm=w,
                    segments=[(x0, y, x1, y)])


# ── 串扰：差分对自身两半豁免 ──

def test_crosstalk_engine_diff_pair_exempt():
    """修复前 USB_DP/USB_DM 以 2W 平行全程被当串扰（10-06 抽查 5/5 样本）。"""
    pcb = _pcb([_trace("USB_DP", 0.0), _trace("USB_DM", 0.361)],
               diff_pairs=[{"net": "USB_DP", "differential": "USB"},
                           {"net": "USB_DM", "differential": "USB"}])
    assert _run(pcb, rule="_check_crosstalk_spacing") == []


def test_crosstalk_guessed_pair_exempt():
    """名字猜测配对（无工程元数据，_P/_N 后缀）同样豁免——紧耦合不是串扰风险。"""
    pcb = _pcb([_trace("USB_D_P", 0.0), _trace("USB_D_N", 0.361)])
    assert _run(pcb, rule="_check_crosstalk_spacing") == []


def test_crosstalk_real_offender_still_reported():
    """差分对豁免不误伤：USB_DP 对 SPI_CLK 近距平行仍报。"""
    pcb = _pcb([_trace("USB_DP", 0.0), _trace("SPI_CLK", 0.3)])
    out = _run(pcb, rule="_check_crosstalk_spacing")
    assert len(out) == 1
    assert "SPI_CLK/USB_DP" in out[0].description


# ── 差分间距：高速接口门控 + 平行重叠前置 ──

def test_diff_pair_spacing_needs_parallel_overlap():
    """修复前重叠 0.0mm、最小间距 2.8mm 也报「耦合过松 11.2W」（10-06 样本）。"""
    pcb = _pcb([
        PCBTrace(net_name="USB_DP", layer="Top Layer", width_mm=0.158,
                 segments=[(0.0, 0.0, 10.0, 0.0)]),
        PCBTrace(net_name="USB_DM", layer="Top Layer", width_mm=0.158,
                 segments=[(5.0, 2.842, 5.0, 5.5)]),   # 垂直，重叠 0
    ], diff_pairs=[{"net": "USB_DP", "differential": "USB"},
                   {"net": "USB_DM", "differential": "USB"}])
    assert _run(pcb, rule="_check_diff_pair_spacing") == []


def test_diff_pair_spacing_skips_non_hs_interface():
    """设计者给音频对标 differentialName 不等于差分阻抗受控，不判间距。"""
    pcb = _pcb([_trace("AU_P", 0.0), _trace("AU_N", 3.0)],
               diff_pairs=[{"net": "AU_P", "differential": "AUDIO"},
                           {"net": "AU_N", "differential": "AUDIO"}])
    assert _run(pcb, rule="_check_diff_pair_spacing") == []


def test_diff_pair_spacing_loose_coupled_usb_reported():
    """正控制：USB 对长平行 + 间距远超 4W → 仍报。"""
    pcb = _pcb([_trace("USB_DP", 0.0), _trace("USB_DM", 2.0)],
               diff_pairs=[{"net": "USB_DP", "differential": "USB"},
                           {"net": "USB_DM", "differential": "USB"}])
    out = _run(pcb, rule="_check_diff_pair_spacing")
    assert len(out) == 1 and "耦合过松" in out[0].description


# ── BOM 五规则：位号前缀代替「描述含电阻/电容」 ──

def test_i2c_pullup_on_bus_silent():
    netlist = {"SDA": ["U1.5", "R1.1"], "SCL": ["U1.6", "R1.2"]}
    bom = [_item("U1", pn="STM32F103", desc="MCU"),
           _item("R1", value="4.7kΩ", desc="10V")]
    assert _run(_pcb(), bom, netlist, "_check_i2c_pullups") == []


def test_i2c_pullup_missing_on_bus_reported():
    """上拉电阻存在但不在总线上 = 等于没有（可证伪判据）。"""
    netlist = {"SDA": ["U1.5"], "SCL": ["U1.6"]}
    bom = [_item("U1", pn="STM32F103"),
           _item("R1", value="4.7kΩ"),
           _item("R2", value="10kΩ")]
    out = _run(_pcb(), bom, netlist, "_check_i2c_pullups")
    assert len(out) == 1 and "上拉" in out[0].description


def test_i2c_netlist_without_bus_overrides_bom_words():
    """网表非空且无 SDA/SCL 网：hub 芯片描述里的「I2C」不再触发。"""
    netlist = {"SPI_CLK": ["U1.3"], "SPI_MOSI": ["U1.4"]}
    bom = [_item("U1", pn="VL817-Q7", desc="USB HUB 集成 I2C"),
           _item("R1", value="1kΩ")]
    assert _run(_pcb(), bom, netlist, "_check_i2c_pullups") == []


def test_i2c_fallback_without_netlist():
    """无网表数据时退回 BOM 文本 + 典型值（旧行为口径）。"""
    bom = [_item("U2", pn="24C02", desc="I2C EEPROM"),
           _item("R5", value="10KΩ")]
    assert _run(_pcb(), bom, {}, "_check_i2c_pullups") == []
    bom_no_r = [_item("U2", pn="24C02", desc="I2C EEPROM")]
    out = _run(_pcb(), bom_no_r, {}, "_check_i2c_pullups")
    assert len(out) == 1


def test_dcdc_feedback_uses_ref_prefix_resistors():
    """修复前「描述含电阻」恒假 → 有反馈网络的板也报 ERROR。"""
    bom = [_item("U1", pn="TPS62823DLCR", desc="3A 降压转换器"),
           _item("R1", value="100kΩ"), _item("R2", value="10kΩ")]
    assert _run(_pcb(), bom, {}, "_check_dcdc_feedback_network") == []
    bom_no_r = [_item("U1", pn="TPS62823DLCR", desc="3A 降压转换器"),
                _item("C1", value="10uF")]
    out = _run(_pcb(), bom_no_r, {}, "_check_dcdc_feedback_network")
    assert len(out) == 1 and "FB 分压电阻" in out[0].description


def test_led_current_limit_uses_ref_prefix_resistors():
    bom = [_item("LED1", pn="红光LED", desc="指示灯"),
           _item("R3", value="1kΩ")]
    assert _run(_pcb(), bom, {}, "_check_led_current_limit") == []
    out = _run(_pcb(), [_item("LED1", desc="LED")], {}, "_check_led_current_limit")
    assert len(out) == 1 and "限流电阻" in out[0].description


def test_decoupling_per_pin_counts_refs_not_desc_words():
    """修复前「描述含电容」恒假 → LQFP48 主控恒报电容不足。"""
    bom = [_item("U1", pn="STM32F103C8T6", pkg="LQFP-48"),
           _item("C1,C2,C3,C4", value="100nF")]
    assert _run(_pcb(), bom, {}, "_check_decoupling_cap_per_pin") == []
    bom_few = [_item("U1", pn="STM32F103C8T6", pkg="LQFP-48"),
               _item("C1", value="100nF")]
    out = _run(_pcb(), bom_few, {}, "_check_decoupling_cap_per_pin")
    assert len(out) == 1 and "电容数量" in out[0].description


def test_pullup_pulldown_word_boundary_and_prefix():
    netlist = {"NRST": ["U1.7"]}
    bom = [_item("R1", value="10KΩ")]
    assert _run(_pcb(), bom, netlist, "_check_pullup_pulldown") == []
    # TOKEN 不再命中内嵌 "EN"
    out = _run(_pcb(), [], {"TOKEN": ["U1.9"]}, "_check_pullup_pulldown")
    assert out == []
    out = _run(_pcb(), [], netlist, "_check_pullup_pulldown")
    assert len(out) == 1 and "NRST" in out[0].description


# ── 裸 rf / 裸 op / 零引脚网络 ──

def test_antenna_keepout_irf_mosfet_not_wireless():
    """修复前裸 "rf" 命中 IRFZ44N/IRF9540（MOSFET 料号内嵌）。"""
    bom = [_item("Q3", pn="IRFZ44N", desc="MOSFET")]
    assert _run(_pcb(), bom, {}, "_check_antenna_keepout") == []


def test_antenna_keepout_esp32_module_reported():
    bom = [_item("U1", pn="ESP32-WROOM-32E")]
    out = _run(_pcb(), bom, {}, "_check_antenna_keepout")
    assert len(out) == 1 and "净空" in out[0].description


def test_ferrite_isolation_package_names_not_opamp():
    """修复前裸 'op' 命中 ESOP8/MSOP8（TP4056-42-ESOP8 被当运放）。"""
    bom = [_item("U1", pn="STM32F103C8T6"),
           _item("U2", pn="TP4056-42-ESOP8"),
           _item("U3", pn="NS4150B MSOP-8")]
    assert _run(_pcb(), bom, {}, "_check_ferrite_bead_isolation") == []


def test_ferrite_isolation_missing_bead_reported():
    bom = [_item("U1", pn="STM32F103C8T6"),
           _item("U2", pn="LMV321IDBVR", desc="低功耗运算放大器"),
           _item("R1", value="10kΩ")]
    out = _run(_pcb(), bom, {}, "_check_ferrite_bead_isolation")
    assert len(out) == 1 and "磁珠" in out[0].description
    bom_bead = bom + [_item("FB1", pn="BLM18AG601SN1D")]
    assert _run(_pcb(), bom_bead, {}, "_check_ferrite_bead_isolation") == []


def test_net_antenna_zero_pin_nets_not_counted():
    """零引脚网络是解析丢针产物（该板 orphan_pad_nets=77），不算单端网络。"""
    nets = {
        "NET_A": PCBNet(name="NET_A", pins=["U1.1"]),
        "NET_B": PCBNet(name="NET_B", pins=["U2.1"]),
        "ORPH_1": PCBNet(name="ORPH_1", pins=[]),
        "ORPH_2": PCBNet(name="ORPH_2", pins=[]),
        "GND_X": PCBNet(name="GND_X", pins=["U3.1"]),
    }
    assert _run(_pcb(nets=nets), rule="_check_net_antenna") == []
    nets["NET_C"] = PCBNet(name="NET_C", pins=["U4.1"])
    out = _run(_pcb(nets=nets), rule="_check_net_antenna")
    assert len(out) == 1 and "3 个网络" in out[0].description


# ── 过孔密度 / 短桩线 ──

def _via(net):
    return PCBVia(position=(1.0, 1.0), drill_mm=0.3, pad_mm=0.6,
                  from_layer="Top", to_layer="Bottom", net_name=net)


def test_via_density_switch_names_not_high_speed():
    """修复前裸 "SW" 命中 …BUZZER_SWITCH（拨码开关网络）。"""
    pcb = _pcb(vias=[_via("BUZZER_SWITCH") for _ in range(6)])
    assert _run(pcb, rule="_check_via_density") == []


def test_via_density_switch_node_reported():
    """SW1（降压开关节点带编号）仍命中；电源/地缝合孔不判。"""
    pcb = _pcb(vias=[_via("SW1") for _ in range(6)])
    out = _run(pcb, rule="_check_via_density")
    assert len(out) == 1 and "SW1" in out[0].description
    pcb_gnd = _pcb(vias=[_via("GND") for _ in range(50)])
    assert _run(pcb_gnd, rule="_check_via_density") == []


def test_stub_length_excludes_ground_nets():
    """修复前 USB_GND 地网被当高速网。"""
    layers = ["Top Layer", "GND02", "PWR03", "Bottom Layer"]
    vias = [_via("USB_GND"), _via("USB_GND"), _via("USB_GND"),
            _via("USB_DP"), _via("USB_DP")]
    pcb = _pcb(vias=vias, layers=layers)
    out = _run(pcb, rule="_check_stub_length")
    assert len(out) == 1 and "USB_DP" in out[0].description


# ── ESD / EMI / 反接：入口网表化 + 保护器件识别 ──

def test_esd_tvs_in_value_field_recognized():
    """真实 BOM 常把型号写在 value（P6SMBJ6.0CA 因此漏认）。"""
    bom = [_item("J1", pn="TYPE-C 16PIN", desc="Type-C 母 卧贴"),
           _item("D2", value="P6SMBJ6.0CA")]
    assert _run(_pcb(), bom, {}, "_check_esd_protection") == []


def test_esd_family_prefix_gesd_recognized():
    """GESD/LESD 家族名内嵌 "ESD"，词边界会漏——料号按家族前缀补认。"""
    bom = [_item("J1", pn="XT60PW-M", desc="XT60 连接器"),
           _item("D2", pn="GESD0501BU-5BU")]
    assert _run(_pcb(), bom, {}, "_check_esd_protection") == []
    out = _run(_pcb(), [_item("J1", pn="XT60PW-M", desc="XT60 连接器")],
               {}, "_check_esd_protection")
    assert len(out) == 1 and "TVS/ESD" in out[0].description


def test_emi_usb_powered_not_an_entry():
    """USB 供电设备要共模电感非常规做法（金样 17 板误报来源）。"""
    netlist = {"VBUS": ["USB1.A4", "U1.1"]}
    bom = [_item("USB1", pn="TYPE-C 16PIN", desc="Type-C 母 卧贴"),
           _item("U1", pn="STM32F103C8T6")]
    assert _run(_pcb(), bom, netlist, "_check_emi_filter") == []


def test_emi_dc_entry_without_cmc_reported():
    netlist = {"VCC_24V": ["CN7.1", "U1.1"]}
    bom = [_item("CN7", pn="DC-005", desc="电源座"),
           _item("U1", pn="STM32F103C8T6")]
    out = _run(_pcb(), bom, netlist, "_check_emi_filter")
    assert len(out) == 1 and "共模电感" in out[0].description
    bom_cmc = bom + [_item("L1", pn="ACT45B", desc="共模扼流圈")]
    assert _run(_pcb(), bom_cmc, netlist, "_check_emi_filter") == []


def test_reverse_polarity_battery_entry_without_protection():
    """电池入口无任何 D/Q/F 器件 → 报；有二极管 → 不报。"""
    netlist = {"VBAT": ["BT1.1", "U1.1"]}
    bom = [_item("BT1", pn="电池座")]
    out = _run(_pcb(), bom, netlist, "_check_reverse_polarity_protection")
    assert len(out) == 1 and "反接保护" in out[0].description
    bom_ok = bom + [_item("D1", pn="SS54", desc="40V 3A")]
    assert _run(_pcb(), bom_ok, netlist, "_check_reverse_polarity_protection") == []


def test_reverse_polarity_package_suffix_not_entry():
    """修复前 SN74HC125PWR 的封装后缀 PWR 成了「电源入口」。"""
    netlist = {"SPI_CLK": ["U8.1"]}
    bom = [_item("U8", pn="SN74HC125PWR", desc="缓冲器")]
    assert _run(_pcb(), bom, netlist, "_check_reverse_polarity_protection") == []
    assert _run(_pcb(), bom, netlist, "_check_emi_filter") == []


# ── 共享辅助 ──

def test_net_kw_hit_allows_trailing_digits_rejects_embedded():
    assert _net_kw_hit("SW1", ("sw",))
    assert _net_kw_hit("M1_TIM1_PWM3", ("pwm",))
    assert not _net_kw_hit("BUZZER_SWITCH", ("sw",))
    assert not _net_kw_hit("GUN_SWITCH", ("sw",))


def test_row_text_includes_value():
    item = _item("D2", value="P6SMBJ6.0CA")
    assert "p6smbj6.0ca" in _row_text(item)


def test_has_power_entry_usb_flag():
    netlist_usb = {"VBUS": ["USB1.A4", "U1.1"]}
    assert _has_power_entry([], netlist_usb, include_usb=True)
    assert not _has_power_entry([], netlist_usb, include_usb=False)
    netlist_dc = {"VCC_24V": ["CN7.1", "U1.1"]}
    assert _has_power_entry([], netlist_dc, include_usb=False)


# ── 判据批（2026-10-10）：去耦档位真容值 + 串扰最严对排除 GND 族 ──
# 金样对比见 experiment_results/criteria_batch_2026-10-10/。

def test_power_rail_decoupling_ref_prefix_caps_alive():
    """修复前判据 pn 含「电容/capacitor」，LCSC 料号 CL10A…恒不命中 → 规则死码。"""
    bom = [_item("C1", value="0.1uF", pn="CL10A105KB8NNNC"),
           _item("C2", value="10uF", pn="CL10A106MQ8NNNC")]
    assert _run(_pcb(), bom, {}, "_check_power_rail_decoupling") == []


def test_power_rail_decoupling_missing_mid_tier():
    """「1UF」是「0.1UF」子串的恒真 bug 锁：只有 0.1µF 必须报缺中频档。"""
    bom = [_item("C1,C2,C3", value="100nF")]
    out = _run(_pcb(), bom, {}, "_check_power_rail_decoupling")
    assert len(out) == 1 and "1~10μF" in out[0].description


def test_power_rail_decoupling_missing_small_tier():
    bom = [_item("C1", value="22uF")]
    out = _run(_pcb(), bom, {}, "_check_power_rail_decoupling")
    assert len(out) == 1 and "0.1μF" in out[0].description


def test_power_rail_decoupling_equiv_writings_and_eia_code():
    bom = [_item("C1", value="104"), _item("C2", value="4.7uF")]
    assert _run(_pcb(), bom, {}, "_check_power_rail_decoupling") == []


def test_power_rail_decoupling_inductor_value_not_fake_mid():
    """C 行挂 10uH 电感值不能冒充 10µF 中频档；无可解析容值诚实跳过。"""
    bom = [_item("C1", value="10uH")]
    assert _run(_pcb(), bom, {}, "_check_power_rail_decoupling") == []


def test_power_rail_decoupling_non_cap_rows_silent():
    bom = [_item("R1", value="10K"), _item("L1", value="10uH")]
    assert _run(_pcb(), bom, {}, "_check_power_rail_decoupling") == []


def test_crosstalk_worst_pair_excludes_gnd_family():
    """GND 贴高速线是隔离手法：该层只有信号-GND 对时不标最严（计数保留）。"""
    pcb = _pcb([_trace("USB_DP", 0.0), _trace("GND", 0.3)])
    out = _run(pcb, rule="_check_crosstalk_spacing")
    assert len(out) == 1
    assert "最严重" not in out[0].description


def test_crosstalk_worst_pair_prefers_signal_pair():
    """信号对与 GND 对都违规时，最严对选信号对——即使 GND 对重叠更长。"""
    pcb = _pcb([_trace("USB_DP", 0.0), _trace("SPI_CLK", 0.3),
                _trace("GND", 0.3, x1=50.0)])
    out = _run(pcb, rule="_check_crosstalk_spacing")
    assert len(out) == 1
    assert "最严重 [SPI_CLK/USB_DP]" in out[0].description


def test_crosstalk_gnd_family_suffix_net_excluded():
    """AU2GND 这类带前缀的地网络也要排除——_kw_hit 词边界会漏，必须子串判。"""
    pcb = _pcb([_trace("USB_DP", 0.0), _trace("AU2GND", 0.3)])
    out = _run(pcb, rule="_check_crosstalk_spacing")
    assert len(out) == 1
    assert "最严重" not in out[0].description

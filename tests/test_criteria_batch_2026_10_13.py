"""判据修正批 2026-10-13 —— 1761 条违规评审确认的 4 个误报族修复的行为锁定。

族别（评审 experiment_results/rule_baseline_after.json 深查结论）：
① DC-DC 反馈 51 ERROR 全失真：名字通道对 $1Nxxxx 匿名网全盲 + LDO/负载开关
   被 TPS/SGM 裸前缀误认成开关稳压器；
② 差分等长门限展示自相矛盾（表外组相对判据触发但只印 2.0mm 绝对门限）
   + guess 后缀配对把 MIC_P/MIC_N 类音频对当受控差分对；
③ 去耦目标把 U 前缀连接器/咪头/OLED 模组当 IC（U 前缀不在 _non_ic_prefixes
   安全网内，且规则回退对 U 前缀也直接返回 ic）；
④ 载流把 POWER_EN 等使能网当电源轨，按 ~1A 启发式需求套 IPC 载流。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.bom.parser import BOMItem
from src.pcb.models import PCBData, PCBTrace
from src.rules.base import _is_dcdc_part
from src.rules.checker import DesignRuleChecker, RuleSeverity


def _item(ref, pn="", desc="", value="", pkg=""):
    return BOMItem(reference=ref, value=value, package=pkg,
                   part_number=pn, description=desc, quantity=1)


# ══════════════════════════════════════════════════════
#  ① DC-DC 反馈：结构化通道 + LDO/负载开关排除
# ══════════════════════════════════════════════════════


class TestDcdcLdoExclusion:
    def test_ldo_and_load_switch_prefixes_excluded(self):
        """TPS7/TPS2/SGM20/SGM21/SGM15 是 LDO/负载开关族，不算开关稳压器。"""
        for pn in ("TPS781", "TPS7A0218", "TPS2051", "TPS22919",
                   "SGM2019", "SGM2107", "SGM1503"):
            assert not _is_dcdc_part(_item("U1", pn=pn, desc="电源芯片")), pn

    def test_switching_families_still_recognized(self):
        for pn in ("TPS61022", "TPS54331", "TPS62823DLCR", "SGM6603",
                   "MP1584EN", "SY8088"):
            assert _is_dcdc_part(_item("U1", pn=pn)), pn
        # 注：XL1509-ADJ 可调版本就不在识别口径（前缀表只有 XL4/XL6 族），
        # 属既有识别缺口而非本批行为，不在断言范围。

    def test_fixed_output_and_module_families_excluded(self):
        """固定输出（内部分压）与全集成隔离模块没有外部 FB 分压，不该查。"""
        for pn, desc in (
            ("AP63203WU-7", "3.8V至32V输入、2A低静态电流同步降压转换器"),
            ("B0505S-1WR3", "DC-DC输入5V输出5V200mA 1W输出短路保护"),
            ("B1212S-1WR3", "DC-DC隔离模块"),
            ("XXL1509-5.0", "150KHz、3A PWM降压型DC/DC转换器"),
            ("XL1509-5.0", "150kHz 2A 降压DC-DC"),
        ):
            assert not _is_dcdc_part(_item("U1", pn=pn, desc=desc)), pn

    def test_linear_regulator_desc_not_switching(self):
        """「线性稳压器 / linear regulator」描述是 LDO，删去的「稳压器」关键词
        不再把它们误判为开关稳压器。"""
        assert not _is_dcdc_part(_item("U1", pn="AMS1117-3.3", desc="线性稳压器"))
        assert not _is_dcdc_part(_item("U1", pn="C54437", desc="LDO regulator"))
        # 开关语义描述仍命中
        assert _is_dcdc_part(_item("U1", pn="C91292", desc="DC-DC 降压转换器"))


class TestDcdcFeedbackStructuralChannel:
    def _run(self, bom, netlist):
        return DesignRuleChecker()._check_dcdc_feedback_network(bom, {}, netlist)

    def test_unnamed_net_divider_silent(self):
        """匿名网 $1N604 挂稳压器 + 两个分压电阻 → 结构化通道认定反馈存在。"""
        bom = [_item("U1", pn="TPS61022", desc="DC-DC")]
        netlist = {
            "$1N604": ["U1.4", "R8.1", "R9.2"],   # 分压中点（匿名）
            "VOUT": ["U1.5", "L1.1"],
            "GND": ["U1.2"],
        }
        assert self._run(bom, netlist) == []

    def test_en_divider_not_fb_evidence(self):
        """EN 网上的两电阻分压是使能时序网络，不能当输出反馈证据 → 仍报。"""
        bom = [_item("U1", pn="TPS61022", desc="DC-DC")]
        netlist = {
            "POWER_EN": ["U1.3", "R1.1", "R2.2"],
            "VOUT": ["U1.5", "L1.1"],
            "GND": ["U1.2"],
        }
        out = self._run(bom, netlist)
        assert len(out) == 1
        assert out[0].severity == RuleSeverity.ERROR

    def test_big_rail_r_pair_not_fb_evidence(self):
        """真电源轨（负载/去耦一堆位号）上两个电阻不是分压中点 → 仍报。
        规模门 ≥6 位号：真轨必挂去耦/负载，分压中点只有稳压器+两臂±辅件。"""
        bom = [_item("U1", pn="TPS61022", desc="DC-DC")]
        netlist = {
            "VBUS": ["U1.1", "R1.1", "R2.1", "C1.1", "C2.1", "U2.3"],
            "VOUT": ["U1.5", "L1.1"],
            "GND": ["U1.2"],
        }
        assert len(self._run(bom, netlist)) == 1

    def test_led_driver_ovp_divider_silent(self):
        """LED 驱动的 OVP 分压中点网（名字带 VCC 字样但只有 4 位号、挂 2 电阻）
        应按结构通道认定反馈存在——金样 SY7201 两条误报的根因。"""
        bom = [_item("U1", pn="SY7201ABC", desc="DC-DC升压")]
        netlist = {
            "MIPI_DSI_VCC_LED-": ["FPC1.1", "R95.1", "R96.1", "U1.4"],
            "MIPI_DSI_VCC_LED+": ["C1.1", "D1.1", "FPC1.2", "U1.5"],
            "GND": ["U1.2"],
        }
        assert self._run(bom, netlist) == []

    def test_missing_divider_still_fires_with_unnamed_nets(self):
        """真缺分压（稳压器网络上没有任何 ≥2 电阻的非使能网络）→ 照报。"""
        bom = [_item("U1", pn="TPS62823DLCR", desc="DC-DC")]
        netlist = {
            "$1N101": ["U1.1", "L1.1"],
            "$1N102": ["U1.5", "C1.1"],
            "GND": ["U1.2", "C1.2"],
        }
        out = self._run(bom, netlist)
        assert len(out) == 1
        assert "反馈网络未检出" in out[0].description

    def test_ldo_not_checked_anymore(self):
        """TPS78x/TPS2051/SGM2019 不再进入 DC-DC 检查（无网表供需路由）。"""
        for pn in ("TPS781", "TPS2051", "SGM2019"):
            bom = [_item("U1", pn=pn, desc="稳压器")]
            assert self._run(bom, {}) == [], pn


# ══════════════════════════════════════════════════════
#  ② 差分等长：门限统一 + 接口分级 + 存储器档
# ══════════════════════════════════════════════════════


def _pair_pcb(nets, mismatch, group="DP1"):
    """engine 声明差分组：两网各一条 10mm 直路，第二网长 mismatch。"""
    a, b = nets
    return PCBData(
        format="lceda_epro2", layers=["TopLayer"],
        differential_pairs=[
            {"net": a, "differential": group, "equal_length_group": None},
            {"net": b, "differential": group, "equal_length_group": None},
        ],
        traces=[
            PCBTrace(net_name=a, layer="TopLayer", width_mm=0.2,
                     segments=[(0, 0, 10, 0)]),
            PCBTrace(net_name=b, layer="TopLayer", width_mm=0.2,
                     segments=[(0, 0.4, 10 + mismatch, 0.4)]),
        ],
    )


def _guess_pcb(nets, mismatch):
    """无声明（suffix guess 配对路径）：MIC_P/MIC_N 类音频后缀对。"""
    a, b = nets
    return PCBData(
        format="lceda_epro2", layers=["TopLayer"],
        differential_pairs=[],
        traces=[
            PCBTrace(net_name=a, layer="TopLayer", width_mm=0.2,
                     segments=[(0, 0, 10, 0)]),
            PCBTrace(net_name=b, layer="TopLayer", width_mm=0.2,
                     segments=[(0, 0.4, 10 + mismatch, 0.4)]),
        ],
    )


def _run_diff(pcb):
    checker = DesignRuleChecker()
    return [v for v in checker.check_all([], {}, pcb_data=pcb)
            if "差分对等长" in v.rule_name]


class TestDiffPairLengthCriteria:
    def test_guess_pair_without_interface_skipped(self):
        """guess 后缀配对（MIC_P/MIC_N）没有受控等长要求 → 不再报。"""
        assert _run_diff(_guess_pcb(("MIC_P", "MIC_N"), 5.0)) == []

    def test_engine_group_without_interface_downgraded(self):
        """engine 声明但无接口词（SPK_IN 类音频）→ 保留判定降 INFO 并注明。"""
        out = _run_diff(_pair_pcb(("SPK_IN_P", "SPK_IN_N"), 2.5))
        assert len(out) == 1
        assert out[0].severity == RuleSeverity.INFO
        assert "接口未识别" in out[0].description
        assert "表外差分组" in out[0].description

    def test_relative_gate_printed_not_absolute(self):
        """表外组相对判据触发（diff 1.2 < 2.0 绝对）时，消息必须印实际收紧
        门限——不再出现「diff 1.2mm 却写门限 2.00mm」的自相矛盾。"""
        out = _run_diff(_pair_pcb(("DATA_P", "DATA_N"), 1.2))
        assert len(out) == 1
        assert out[0].severity == RuleSeverity.INFO
        assert "1.2mm" in out[0].description
        assert "2.00mm" not in out[0].description

    def test_ddr_band_storage(self):
        """LPDDR 对 0.96mm 失配按存储器档 0.5mm 判定（原落表外 2.0mm）。"""
        out = _run_diff(_pair_pcb(("LPDDR5_WCK1P_B", "LPDDR5_WCK1N_B"), 0.96))
        assert len(out) == 1
        assert out[0].severity == RuleSeverity.WARNING   # engine + 命中档
        assert "存储器" in out[0].description

    def test_usb_band_no_relative_criterion(self):
        """USB 档只有 2.0mm 绝对判据：1.5mm 失配（>10% 相对）不报。"""
        assert _run_diff(_pair_pcb(("USB_DP", "USB_DM"), 1.5)) == []


# ══════════════════════════════════════════════════════
#  ③ 去耦目标：U 前缀模组/连接器描述二次否决
# ══════════════════════════════════════════════════════


class TestModuleVeto:
    def test_helper_word_boundary(self):
        from src.rules.base import _is_module_not_ic
        # 金样实证的 16 个假 IC 目标全部命中
        for pn, desc in (("HS96L03W2C03", "0.96寸OLED显示屏窄白光IIC"),
                         ("WAFER-PH2.0-4PWB", "1x4P 间距:2mm 卧贴 系列:PH"),
                         ("XT30PW-F20.G.Y", "AMASS(艾迈斯)电源连接器 母头"),
                         ("KEAG4544PF-K", "全指向性麦克风,-44DB,3.0V"),
                         ("", "主控面向人，排针焊接在背面"),
                         ("TF-123-ARP9H15", "拔插式 MicroSD卡(TF卡) 卡座")):
            assert _is_module_not_ic(_item("U1", pn=pn, desc=desc)), desc
        # 真 IC 不被误伤
        assert not _is_module_not_ic(
            _item("U1", pn="STM32F103C8T6", desc="MCU"))
        assert not _is_module_not_ic(
            _item("U1", pn="MPU-6050", desc="三轴陀螺仪加速度计"))
        # 已知取舍：裸 OLED 驱动芯片（desc 含 oled 字样）也会被否决——金样
        # 78 板无此形态（OLED 全以模组出现），display 词收益大于损失
        assert _is_module_not_ic(
            _item("U1", pn="SSD1306", desc="OLED 驱动控制芯片"))
        # mic 词边界：MicroSD 卡座由「卡座」接管，"mic" 子串不再扩大误伤面

    def test_module_only_board_no_decoupling_demand(self):
        """全板只有 OLED/连接器/麦克风模组（U 位号）→ 去耦需求为 0，不报。"""
        checker = DesignRuleChecker()
        bom = [
            _item("U1", pn="HS96L03W2C03", desc="0.96寸OLED显示屏窄白光IIC"),
            _item("U2", pn="WAFER-PH2.0-4PWB", desc="1x4P 间距:2mm 卧贴"),
            _item("U3", pn="KEAG4544PF-K", desc="全指向性麦克风"),
        ]
        assert checker._check_decoupling_caps(bom, {}, {}) == []

    def test_real_mcu_still_targeted(self):
        checker = DesignRuleChecker()
        bom = [_item("U1", pn="STM32F103C8T6", desc="MCU", pkg="LQFP-48")]
        out = checker._check_decoupling_caps(bom, {}, {})
        assert len(out) >= 1
        assert "U1" in out[0].description

    def test_module_veto_under_ml_off(self, monkeypatch):
        """ml_off（frozen 规则回退路径）下 U 前缀模组同样被否决。"""
        from src.rules import base as rule_base
        monkeypatch.setattr(rule_base, "_component_predictor", None)
        monkeypatch.setattr(rule_base, "_component_model_attempted", True)
        rule_base._fine_cls_cache.clear()
        rule_base._coarse_cls_cache.clear()
        checker = DesignRuleChecker()
        bom = [_item("U1", pn="HS96L03W2C03", desc="0.96寸OLED显示屏窄白光IIC")]
        assert checker._check_decoupling_caps(bom, {}, {}) == []

    def test_proximity_skips_module_targets(self):
        """距离规则：板上 IC 目标全是模组 → 无距离判定；真 MCU 照报。"""
        checker = DesignRuleChecker()
        far_cap = _item("C1", value="100nF", pkg="0603",
                        pn="C1588", desc="贴片电容")
        oled = _item("U1", pn="HS96L03W2C03", desc="0.96寸OLED显示屏")
        pos = {"U1": {"x": 0, "y": 0}, "C1": {"x": 200, "y": 0}}
        assert checker._check_decoupling_proximity([oled, far_cap], pos, {}) == []
        mcu = _item("U1", pn="STM32F103C8T6", desc="MCU", pkg="LQFP-48")
        out = checker._check_decoupling_proximity([mcu, far_cap], pos, {})
        assert len(out) == 1
        assert "去耦电容距 IC" in out[0].description


# ══════════════════════════════════════════════════════
#  ④ 载流：使能/状态网排除
# ══════════════════════════════════════════════════════


def _run_power_traces(traces, bom=None):
    pcb = PCBData(format="lceda_epro2", layers=["TopLayer"], traces=traces)
    checker = DesignRuleChecker()
    return [v for v in checker.check_all(bom or [], {}, pcb_data=pcb)
            if v.rule_name == "电源线载流检查"]


class TestEnableNetExclusion:
    def test_enable_trace_not_current_checked(self):
        """POWER_EN 细走线不再被当电源轨套 IPC 载流（同名含 POWER 关键词）。"""
        out = _run_power_traces([
            PCBTrace(net_name="POWER_EN", layer="TopLayer", width_mm=0.2,
                     segments=[(0, 0, 10, 0)]),
        ])
        assert out == []

    def test_enable_word_boundary_no_overreach(self):
        """词边界防误伤：PGND/SENSOR_PWR 不含独立 en 词，仍按原口径判定。
        4×WS2812 把主电源需求撑到 2.0A（PGND 按 0.3×2.0=0.6A 需求，
        0.1mm 外层容量 0.45A → 必响）。"""
        bom = [_item(f"U{i}", pn="WS2812B", desc="LED 灯珠") for i in range(1, 5)]
        for net in ("PGND", "SENSOR_PWR"):
            out = _run_power_traces([
                PCBTrace(net_name=net, layer="TopLayer", width_mm=0.1,
                         segments=[(0, 0, 10, 0)]),
            ], bom=bom)
            assert len(out) == 1, net
            assert net in out[0].description

    def test_real_rail_still_checked(self):
        """MOTOR 动力网细走线照报（路由需求 max(0.4×总, 1.0A) > 0.45A 容量）。"""
        out = _run_power_traces([
            PCBTrace(net_name="MOTOR_5V", layer="TopLayer", width_mm=0.1,
                     segments=[(0, 0, 10, 0)]),
        ])
        assert len(out) == 1
        assert "MOTOR_5V" in out[0].description

"""真实 PCB 板回归测试：验证去耦/晶振检查不再把被动元件和连接器误判为 IC。

背景（2026-08-03 修复）：修复前 _check_decoupling_caps 仅靠描述关键词分类元件，
而真实立创 BOM 的描述常只是值/型号（如 "100nF"、"4kHz"），导致电容、二极管、
连接器、蜂鸣器被误判为需要去耦电容的 IC。4 块真实板共产生 176 条虚假违规
（占全部违规 68%），并拖垮评分体系（power 维度全线 0 分）。

同类问题：晶振负载电容检查把"X"前缀连接器（如 dcdc 板 X3=AFC07 排线座）误判
为晶振，且要求负载电容与晶振同前缀（真实设计负载电容均为 C 前缀），导致误报。

修复后：元件分类以位号前缀为主、描述兜底，去耦/负载电容覆盖按"可用电容总量
vs IC/晶振数量"的供需关系判断。本测试防止误报回归。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import glob

import pytest

from src.core.controller import AppController
from src.core.design_scorer import DesignScorer
from src.rules.checker import DesignRuleChecker

TEST_DATA = PROJECT_ROOT / "test_data" / "pcb_designs"
pytestmark = pytest.mark.skipif(
    not TEST_DATA.exists(), reason="真实 PCB 测试数据 test_data/ 不存在"
)

BOARDS = ["bldc_esc_motor", "dcdc_power_v62", "esp32_audio_moji2", "stm32f103_devboard"]

# 明确非 IC 的位号前缀：电容/电阻/电感/二极管/三极管/连接器/晶振/开关/机械件等
NON_IC_PREFIXES = {
    "C", "R", "RN", "RNC", "L", "FB", "D", "Q", "T",
    "J", "CN", "CON", "HDR", "P", "FPC", "TP", "MP", "H", "USB", "SH", "SM",
    "SW", "K", "S", "BUTTON", "BUZZ", "BZ", "BUZZER", "LS", "SPK", "F", "FU",
    "RL", "RELAY", "LED", "X", "Y", "XTAL", "OSC",
}


def _load_violations(board: str):
    bom = glob.glob(str(TEST_DATA / board / "BOM*.xlsx"))
    if not bom:
        pytest.skip(f"{board} 缺少 BOM xlsx")
    ctrl = AppController()
    ctrl.load_bom(bom[0])
    violations = DesignRuleChecker().check_all(
        ctrl.context.bom_items,
        ctrl.context.positions,
        pcb_data=ctrl.context.pcb_data,
    )
    return ctrl, violations


class TestRealPcbDecoupling:
    def test_no_false_positive_on_non_ic(self):
        """去耦违规不应命中电容/二极管/连接器等非 IC 元件"""
        for board in BOARDS:
            _, vs = _load_violations(board)
            decoup = [v for v in vs if v.rule_name == "去耦电容检查"]
            for v in decoup:
                loc = v.location.split(",")[0]
                prefix = "".join(ch for ch in loc if ch.isalpha()).upper()
                assert prefix not in NON_IC_PREFIXES, (
                    f"{board}: 去耦违规误报非 IC 元件 {loc}"
                )

    def test_decoupling_count_small(self):
        """每板去耦违规应远小于修复前的误报量（176 条 → 每板 ≤5 条真实供需缺口）"""
        for board in BOARDS:
            _, vs = _load_violations(board)
            decoup = [v for v in vs if v.rule_name == "去耦电容检查"]
            assert len(decoup) <= 5, f"{board}: 去耦违规 {len(decoup)} 条仍过多"

    def test_power_dimension_not_zero(self):
        """评分 power 维度不应再为 0（修复前 4 板全部归零）"""
        for board in BOARDS:
            ctrl, vs = _load_violations(board)
            rep = DesignScorer().score(vs, ctrl.context.bom_items, ctrl.context.positions)
            power = rep.dimensions["power"].score
            assert power > 50, f"{board}: power 维度 {power} 分异常"

    def test_known_gap_reported(self):
        """dcdc_power_v62 存在真实供需缺口：以汇总 WARNING 报告，而非逐 IC 刷屏 ERROR"""
        ctrl, vs = _load_violations("dcdc_power_v62")
        decoup = [v for v in vs if v.rule_name == "去耦电容检查"]
        assert len(decoup) >= 1
        assert all(v.severity.value == "warning" for v in decoup)

    def test_crystal_load_cap_no_false_positive(self):
        """晶振负载电容不应误报：X3 是连接器非晶振，板上 12-22pF 电容应覆盖负载需求"""
        _, vs = _load_violations("dcdc_power_v62")
        xtal = [v for v in vs if v.rule_name == "晶振负载电容检查"]
        # 修复前 dcdc 报 2 条（X1 + X3 连接器误判），修复后为 0
        assert len(xtal) == 0

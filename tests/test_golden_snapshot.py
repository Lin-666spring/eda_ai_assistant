"""金样触发计数快照 —— 批4 2026-10-10 引入。

78 板 .epro2 金样语料在本地（test_data/_incoming_epro2/78，gitignore 不入库），
缺席时整文件 skip。在场时锁定**每条规则的触发总数**：判据意外漂移、规则被
静默丢注册（mixin 模块级 def 事故）、或某规则意外归零，都会在这里红灯。

有意调整判据/增删规则的批次：跑 `python /tmp/golden_audit.py out.json`（或等价
内联脚本，见本文件实现）重算后，同步更新 _SNAPSHOT 并在批次 README 记录差异。

计数依赖 torch ML 分类（_classify_component）——纯运行时依赖环境（无 torch）
走规则回退会得到不同计数，故 importorskip 保持与开发环境一致口径。
"""
from __future__ import annotations

import pytest

pytest.importorskip("torch", reason="金样计数依赖 ML 分类口径（requirements-dev）")

from pathlib import Path

_GOLDEN_DIR = Path(__file__).resolve().parents[1] / "test_data" / "_incoming_epro2" / "78"
pytestmark = pytest.mark.skipif(
    not _GOLDEN_DIR.is_dir(), reason="金样语料不在库（本地目录 test_data/_incoming_epro2/78）")

# 基线：判据修正批落定后（2026-10-13，评审遗留 4 误报族：DC-DC 反馈/差分等长/
# 去耦模组目标/载流使能网），78 板全量 .epro2（BOM+坐标+网表+铜）。
# 差异记录见 experiment_results/criteria_fix_2026_10_13/README.md
# 2026-10-24 A-9 ic_* 增强重训批（元件分类器换 best-epoch 无泄漏新权重 +
# 校准产物运行时优先加载）：去耦电容检查 130→125、去耦电容距离 20→22、
# 晶振布局 0→1。计数依赖 ML 分类口径（见本文件 docstring），本次为有意换基。
# 差异记录见 experiment_results/a9_ic_augment_2026_10_24/README.md
# 2026-10-24 P1 修复批（主代理重定基）：批次C 判据修正（P1-13 EIA 记法 /
# P1-14 电容单位感知 / P1-15 跨格间距 / P1-16 底层焊盘 Y 镜像 / P1-17 电压轨
# token）落地后重算 —— 金样语料无 R 记法/100uH/25V 类触发样本，P1-13/14/17
# 零漂移；唯一变化 铜皮连接检查 29→28（P1-16 底层焊盘坐标修正的边界影响），
# 总触发数 1547→1546。差异记录见 experiment_results/p1_fix_2026_10_24/README.md
_SNAPSHOT = {
    "3W 串扰间距检查": 71,
    "DC-DC 反馈网络检查": 1,
    "EMI 滤波器布局检查": 12,
    "EMI 滤波检查": 11,
    "ESD 保护检查": 46,
    "I2C 上拉电阻检查": 11,
    "LED 限流电阻检查": 1,
    "PDN 目标阻抗分析": 78,
    "上下拉电阻检查": 3,
    "位号连续性检查": 51,
    "信号线宽度检查": 6,
    "光学定位点检查": 66,
    "功率回路面积检查": 31,
    "去耦电容检查": 125,
    "去耦电容距离检查": 22,
    "参数范围检查": 21,
    "地平面连续性检查": 5,
    "复位电路检查": 2,
    "多电源引脚去耦检查": 1,
    "天线净空区检查": 23,
    "天线效应检查": 12,
    "安装孔禁区检查": 11,
    "封装一致性检查": 1,
    "差分对等长检查": 61,
    "开关电源布局检查": 31,
    "悬空引脚检查": 5,
    "时钟信号包地检查": 104,
    "晶振负载电容检查": 6,
    "晶振布局检查": 1,
    "晶振频率匹配": 27,
    "未连接引脚检查": 7,
    "板边间距检查": 50,
    "模数分离检查": 3,
    "测试点覆盖检查": 47,
    "温度敏感元件布局检查": 3,
    "热焊盘检查": 2,
    "特征阻抗匹配检查": 143,
    "环路面积检查": 30,
    "电容温度系数检查": 33,
    "电容耐压降额检查": 7,
    "电感饱和电流检查": 35,
    "电池电压分压器检查": 2,
    "电源极性保护检查": 4,
    "电源滤波检查": 7,
    "电源线载流检查": 29,
    "电源轨去耦网络": 12,
    "短桩线检查": 14,
    "磁珠隔离检查": 5,
    "调试接口检查": 15,
    "走线板边间距检查": 2,
    "走线直角检查": 77,
    "走线锐角检查": 7,
    "过孔密度检查": 5,
    "过孔热焊盘检查": 60,
    "连接器边沿布局检查": 36,
    "铜皮连接检查": 28,
    "高速信号参考平面检查": 37,
}


def test_golden_trigger_counts():
    from collections import Counter

    from src.pcb.epro2_parser import Epro2Parser, bom_rows_to_items
    from src.rules.checker import DesignRuleChecker

    parser = Epro2Parser()
    checker = DesignRuleChecker()
    counts: Counter = Counter()
    rule_errors = Counter()
    boards = 0
    for f in sorted(_GOLDEN_DIR.rglob("*.epro2")):
        try:
            pcb = parser.parse(str(f))
        except Exception:
            continue
        boards += 1
        bom_items = bom_rows_to_items(pcb.bom_items)
        positions = {
            ref: {"x": v.get("x", 0), "y": v.get("y", 0), "rotation": v.get("rotation", 0),
                  "layer": v.get("side") or v.get("layer", ""), "package": v.get("footprint_name", "")}
            for ref, v in pcb.component_positions.items()
        }
        netlist = {name: list(net.pins) for name, net in pcb.nets.items() if net.pins}
        violations = checker.check_all(bom_items, positions, netlist=netlist, pcb_data=pcb)
        for v in violations:
            counts[v.rule_name] += 1
        for e in checker.rule_errors:
            rule_errors[e["rule"]] += 1

    assert boards == 78, f"金样板数变化: {boards} != 78（语料被增删？）"
    assert not rule_errors, f"规则异常必须为 0: {dict(rule_errors)}"
    drift = {r: (counts.get(r, 0), _SNAPSHOT.get(r, 0))
             for r in set(counts) | set(_SNAPSHOT)
             if counts.get(r, 0) != _SNAPSHOT.get(r, 0)}
    assert not drift, (
        "金样触发数漂移（实际, 快照）：\n" +
        "\n".join(f"  {r}: {a} != {s}" for r, (a, s) in sorted(drift.items())) +
        "\n若为本批次有意变化：重算计数并同步 _SNAPSHOT，批次 README 记录差异"
    )

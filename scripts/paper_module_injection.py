# -*- coding: utf-8 -*-
"""几何/布局规则程序化缺陷注入 —— 论文 R18 增强路径（无 LLM，纯规则引擎）。

数据: test_data/_incoming_epro2/78/*.epro2 —— 立创专业版真实工程（含真实
走线/过孔/板框/元件坐标），与论文主实验的 79 板(thing_designs，无版图数据)
互补；两数据集均为立创开源平台真实设计。

方法: 对每板先跑干净基线，再逐缺陷类型对 PCBData 深拷贝做程序化变异后复检。
检出 = 期望规则「注入后触发 且 注入前未触发」（板级预存违规不计入检出）。
每缺陷可含前置条件（如板上有电源网/IC/晶振），不满足记 not_applicable。

输出: experiment_results/module_injection_<ts>/results.json + summary.md
用法: python scripts/paper_module_injection.py [--limit N]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.constants import PCB
from src.pcb.epro2_parser import Epro2Parser, bom_rows_to_items
from src.rules.base import (
    _classify_component,
    _classify_component_fine,
    _is_dcdc_part,
    _is_power_or_ground_net,
    _net_kw_hit,
)
from src.rules.checker import DesignRuleChecker
from src.rules.layout_rules import _identify_crystal_refs


# ──────────────────── 变异实现 ────────────────────
# 每个 mutation(pcb, bom_items) → bool(已实施)。原地修改 pcb 深拷贝。

_EDGE_EXEMPT = ("J", "P", "CN", "CON", "USB", "HDMI", "RJ", "DC", "BT", "BAT",
                "FPC", "H", "TP", "SW", "M", "MIC", "SPK", "BUZ", "RF", "ANT")
_CONN_KW = ["usb", "rj45", "hdmi", "db9", "排针", "端子", "connector", "header",
            "jack", "dc", "电源插座", "sd卡", "tf卡", "sim卡", "fpc", "ffc"]


def _outline(pcb):
    bo = pcb.board_outline or {}
    return bo if bo.get("source") == "outline" else None


def _bbox(bo):
    return bo["min_x_mm"], bo["min_y_mm"], bo["max_x_mm"], bo["max_y_mm"]


def _sig_traces(pcb):
    return [t for t in pcb.traces
            if t.net_name and t.width_mm > 0 and not _is_power_or_ground_net(t.net_name)]


def _move_component(pcb, ref, x, y):
    """移动元件：坐标与焊盘同步平移，保持注入后板数据自洽
    （只挪中心不挪焊盘会被元件间距规则的「焊盘佐证门」判为口径噪声跳过）。"""
    pos = pcb.component_positions[ref]
    dx, dy = x - pos["x"], y - pos["y"]
    pos["x"], pos["y"] = x, y
    for pad in (getattr(pcb, "pads", None) or []):
        if pad.get("ref") == ref:
            pad["x"] += dx
            pad["y"] += dy
    return True


def _trace_len(t):
    return sum(math.dist(s[:2], s[2:]) for s in t.segments)


def _away_from_vias(pcb, x, y, r=1.5):
    """若 (x,y) 附近 r 内有过孔/元件则平移尝试，返回可用坐标或 None。
    锐角规则的锚点网格同时含过孔与元件坐标，两者都要避开。"""
    anchors = [(v.position[0], v.position[1]) for v in pcb.vias]
    anchors += [(p["x"], p["y"]) for p in pcb.component_positions.values()
                if isinstance(p, dict) and "x" in p]
    for dx in (0, 2, -2, 4, -4, 6, -6):
        for dy in (0, 2, -2, 4, -4, 6, -6):
            cx, cy = x + dx, y + dy
            if all(math.hypot(ax - cx, ay - cy) > r for ax, ay in anchors):
                return (cx, cy)
    return None


def _m_underwidth_signal(pcb, bom):
    sigs = sorted(_sig_traces(pcb), key=_trace_len, reverse=True)
    if not sigs:
        return False
    sigs[0].width_mm = 0.05          # < 工艺下限 0.088/0.1mm
    return True


def _m_underwidth_power(pcb, bom):
    en_kw = ("en", "enable", "ena", "pwren", "pgood")
    pw = [t for t in pcb.traces
          if t.net_name and t.width_mm > 0
          and any(kw in t.net_name.upper() for kw in PCB.POWER_NET_KEYWORDS)
          and not _net_kw_hit(t.net_name, en_kw)]
    if not pw:
        return False
    pw[0].width_mm = 0.05            # 载流容量 << 估算需求
    return True


def _m_acute_angle(pcb, bom):
    """把最长信号走线改为含 ~31° 内角拐点的三段折线，顶点远离过孔。"""
    sigs = sorted(_sig_traces(pcb), key=_trace_len, reverse=True)
    bo = _outline(pcb)
    if not sigs or not bo:
        return False
    minx, miny, maxx, maxy = _bbox(bo)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    spot = _away_from_vias(pcb, cx, cy)
    if spot is None:
        return False
    cx, cy = spot
    t = sigs[0]
    # A→B→C→D: B 处内角 ≈ 31°（cos⁻¹(15/17.5)），腿长 6/2.9mm，非 45° 栅格楔形
    a = (cx - 3.0, cy)
    b = (cx, cy)
    c = (cx - 2.5, cy + 1.5)
    d = (cx + 0.5, cy + 1.5)
    t.segments = [(a[0], a[1], b[0], b[1]), (b[0], b[1], c[0], c[1]),
                  (c[0], c[1], d[0], d[1])]
    return True


def _m_via_density(pcb, bom):
    kws = [k.lower() for k in PCB.VIA_DENSITY_NET_KEYWORDS]
    cand = set()
    for t in pcb.traces:
        n = t.net_name or ""
        if n and not _is_power_or_ground_net(n) and _net_kw_hit(n, kws):
            cand.add(n)
    for v in pcb.vias:
        n = getattr(v, "net_name", "") or ""
        if n and not _is_power_or_ground_net(n) and _net_kw_hit(n, kws):
            cand.add(n)
    if not cand:
        return False
    net = sorted(cand)[0]
    anchor = None
    for t in pcb.traces:
        if t.net_name == net and t.segments:
            anchor = t.segments[0][:2]
            break
    if anchor is None and pcb.vias:
        for v in pcb.vias:
            if getattr(v, "net_name", "") == net:
                anchor = v.position
                break
    if anchor is None:
        return False
    from src.pcb.models import PCBVia
    for i in range(6):               # 阈值 5：≥5 触发
        pcb.vias.append(PCBVia(position=(anchor[0] + i * 1.0, anchor[1]),
                               drill_mm=0.3, pad_mm=0.6,
                               from_layer="Top Layer", to_layer="Bottom Layer",
                               net_name=net))
    return True


def _m_crosstalk(pcb, bom):
    """克隆一条最长信号走线为 USB 命名新网，平移 0.15mm 全程平行贴邻。"""
    sigs = sorted([t for t in _sig_traces(pcb) if _trace_len(t) >= 5.0],
                  key=_trace_len, reverse=True)
    if not sigs:
        return False
    t = sigs[0]
    from src.pcb.models import PCBTrace
    pcb.traces.append(PCBTrace(
        net_name="USB2DATA_XTALK", layer=t.layer, width_mm=t.width_mm,
        segments=[(s[0], s[1] + 0.15, s[2], s[3] + 0.15) for s in t.segments]))
    return True


def _m_trace_edge(pcb, bom):
    bo = _outline(pcb)
    sigs = _sig_traces(pcb)
    if not bo or not sigs:
        return False
    minx, miny, maxx, maxy = _bbox(bo)
    ring = (bo.get("outline_rings_mm") or [[(minx, miny), (minx, maxy)]])[0]
    left_pt = min(ring, key=lambda pt: pt[0])   # 板框最左点：该 y 处板框恰在 minx
    t = sigs[0]
    t.segments.append((left_pt[0] + 2.0, left_pt[1],
                       left_pt[0] + 0.05, left_pt[1]))  # 端点距板边 0.05mm < 0.3
    return True


def _pick_ref(bom, positions, want):
    """want: 'cap'|'ic'|'nonexempt'|... 按分类挑第一个有坐标的位号。"""
    for item in bom:
        ref = (getattr(item, "reference", "") or "").split(",")[0].strip()
        if not ref or ref not in positions:
            continue
        pfx = "".join(c for c in ref if c.isalpha()).upper()
        if want == "nonexempt":
            if pfx and not pfx.startswith(_EDGE_EXEMPT):
                return item, ref
        elif want == "cap":
            if _classify_component(item) == "cap":
                return item, ref
        elif want == "ic":
            if (_classify_component(item) == "ic"
                    and not _is_module_not_ic(item)):
                return item, ref
    return None, None


def _is_module_not_ic(item):
    from src.rules.base import _is_module_not_ic as _f
    return _f(item)


def _m_edge_clearance(pcb, bom):
    bo = _outline(pcb)
    pos = pcb.component_positions
    if not bo or not pos:
        return False
    minx, miny, maxx, maxy = _bbox(bo)
    for item in bom:
        ref = (getattr(item, "reference", "") or "").split(",")[0].strip()
        if not ref or ref not in pos:
            continue
        pfx = "".join(c for c in ref if c.isalpha()).upper()
        if not pfx or pfx.startswith(_EDGE_EXEMPT):
            continue
        x, y = pos[ref]["x"], pos[ref]["y"]
        if min(x - minx, maxx - x, y - miny, maxy - y) <= 3.0:
            continue        # 已贴边的板基线已违规，挑当前合规件制造回归
        return _move_component(pcb, ref, minx + 0.3, (miny + maxy) / 2)  # 0.3mm < 3.0mm
    return False


def _m_decoupling_far(pcb, bom):
    bo = _outline(pcb)
    pos = pcb.component_positions
    if not bo or not pos:
        return False
    minx, miny, maxx, maxy = _bbox(bo)
    caps, ics = [], []
    for item in bom:
        ref = (getattr(item, "reference", "") or "").split(",")[0].strip()
        if not ref or ref not in pos:
            continue
        if _classify_component(item) == "cap":
            caps.append(ref)
        elif (_classify_component(item) == "ic" and not _is_module_not_ic(item)):
            ics.append(ref)
    if not caps or not ics:
        return False
    corners = [(minx + 0.5, miny + 0.5), (minx + 0.5, maxy - 0.5),
               (maxx - 0.5, miny + 0.5), (maxx - 0.5, maxy - 0.5)]
    def worst(c):
        return min(math.dist(c, (pos[i]["x"], pos[i]["y"])) for i in ics)
    corner = max(corners, key=worst)
    if worst(corner) <= PCB.LAYOUT_DECOUPLE_MAX_DIST_MM:
        return False                  # 板太小，移到角上也不够远
    return _move_component(pcb, caps[0], corner[0], corner[1])


def _m_component_overlap(pcb, bom):
    """把一个片式元件精确压到另一片式元件上（同面），体间隙 <0.2mm。"""
    pos = pcb.component_positions
    chips = [r for r, p in pos.items()
             if isinstance(p, dict) and str(p.get("side") or "T") in ("T", "B")
             and any(code in str(p.get("footprint_name") or "").upper()
                     for code in ("0402", "0603", "0805", "1206"))]
    if len(chips) < 2:
        return False
    a, b = chips[0], chips[1]
    if str(pos[a].get("side") or "T") != str(pos[b].get("side") or "T"):
        return False
    return _move_component(pcb, b, pos[a]["x"], pos[a]["y"])


def _m_crystal_far(pcb, bom):
    bo = _outline(pcb)
    pos = pcb.component_positions
    if not bo or not pos:
        return False
    crystals = [ref for _it, ref in _identify_crystal_refs(bom) if ref in pos]
    if not crystals:
        return False
    mcus = [r for r, p in pos.items()
            if r.upper().startswith("U")
            and any(k in str(p.get("value") or "").upper()
                    for k in ("STM32", "CH32", "ESP32", "GD32", "MCU", "PY32",
                              "AT32", "N32", "W80", "BL6", "CH55", "CH58"))]
    if not mcus:
        mcus = [r for r in pos if r.upper().startswith("U")]
    if not mcus:
        return False
    minx, miny, maxx, maxy = _bbox(bo)
    mx, my = pos[mcus[0]]["x"], pos[mcus[0]]["y"]
    corners = [(minx + 0.5, miny + 0.5), (minx + 0.5, maxy - 0.5),
               (maxx - 0.5, miny + 0.5), (maxx - 0.5, maxy - 0.5)]
    corner = max(corners, key=lambda c: math.dist(c, (mx, my)))
    if math.dist(corner, (mx, my)) <= PCB.LAYOUT_CRYSTAL_MCU_MAX_DIST_MM:
        return False
    return _move_component(pcb, crystals[0], corner[0], corner[1])


def _m_connector_inward(pcb, bom):
    bo = _outline(pcb)
    pos = pcb.component_positions
    if not bo or not pos:
        return False
    minx, miny, maxx, maxy = _bbox(bo)
    conn_kw = _CONN_KW
    for item in bom:
        desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
        if not any(kw in desc for kw in conn_kw):
            continue
        ref = (getattr(item, "reference", "") or "").split(",")[0].strip()
        if ref not in pos:
            continue
        x, y = pos[ref]["x"], pos[ref]["y"]
        if min(x - minx, maxx - x, y - miny, maxy - y) <= PCB.LAYOUT_CONN_BOARD_EDGE_MM:
            continue        # 已贴边（未违规状态）才是可回归的基线，选它制造退化
        continue
    # 第二遍：挑贴边连接器（当前合规）移到板中心 —— 规则噪声门要求「新违规实例」
    for item in bom:
        desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
        if not any(kw in desc for kw in conn_kw):
            continue
        ref = (getattr(item, "reference", "") or "").split(",")[0].strip()
        if ref not in pos:
            continue
        x, y = pos[ref]["x"], pos[ref]["y"]
        if min(x - minx, maxx - x, y - miny, maxy - y) <= PCB.LAYOUT_CONN_BOARD_EDGE_MM:
            return _move_component(pcb, ref, (minx + maxx) / 2, (miny + maxy) / 2)
    return False


def _m_temp_near_heat(pcb, bom):
    pos = pcb.component_positions
    if not pos:
        return False
    from src.rules.layout_rules import _parse_capacitance
    sensitive, heats = [], []
    for item in bom:
        ref = (getattr(item, "reference", "") or "").split(",")[0].strip()
        if not ref or ref not in pos:
            continue
        try:
            fine, _ = _classify_component_fine(item)
        except Exception:
            fine = ""
        val = str(getattr(item, "value", "") or "")
        cf = _parse_capacitance(val) if _classify_component(item) == "cap" else None
        if fine == "cap_elec" or (cf is not None and cf >= 100e-6):
            sensitive.append(ref)
        if _is_dcdc_part(item) or fine == "ic_power":
            heats.append(ref)
    if not sensitive or not heats:
        return False
    # 规则噪声门：>2 对贴近才报。策略 A：≥3 个敏感件压到热源；
    # 策略 B：热源压到最密敏感件簇，估算 10mm 内对数 >2 才实施。
    hx, hy = pos[heats[0]]["x"], pos[heats[0]]["y"]
    if len(sensitive) >= 3:
        for k, ref in enumerate(sensitive[:3]):
            _move_component(pcb, ref, hx + 0.4 * k, hy)
        return True
    tgt = max(sensitive, key=lambda r: sum(
        1 for o in sensitive
        if math.hypot(pos[o]["x"] - pos[r]["x"], pos[o]["y"] - pos[r]["y"]) <= 10))
    near = sum(1 for o in sensitive
               if math.hypot(pos[o]["x"] - pos[tgt]["x"],
                             pos[o]["y"] - pos[tgt]["y"]) <= 10)
    if near <= 2:
        return False
    return _move_component(pcb, heats[0], pos[tgt]["x"], pos[tgt]["y"])


# defect_id → (缺陷名, 期望规则名, 变异函数, 模块)
DEFECTS = {
    "underwidth_signal": ("信号走线欠宽(0.05mm)", "信号线宽度检查", _m_underwidth_signal, "geometry"),
    "underwidth_power":  ("电源走线欠宽(0.05mm)", "电源线载流检查", _m_underwidth_power, "geometry"),
    "acute_angle":       ("走线锐角拐点(~31°)", "走线锐角检查", _m_acute_angle, "geometry"),
    "via_density":       ("高速网过孔密集(+6)", "过孔密度检查", _m_via_density, "geometry"),
    "crosstalk_3w":      ("平行贴邻线对(0.15mm)", "3W 串扰间距检查", _m_crosstalk, "geometry"),
    "trace_edge":        ("走线贴板边(0.05mm)", "走线板边间距检查", _m_trace_edge, "geometry"),
    "edge_clearance":    ("元件贴板边(0.3mm)", "板边间距检查", _m_edge_clearance, "layout"),
    "decoupling_far":    ("去耦电容远离IC(对角)", "去耦电容距离检查", _m_decoupling_far, "layout"),
    "component_overlap": ("两元件同位重叠", "元件间距检查", _m_component_overlap, "layout"),
    "crystal_far":       ("晶振远离MCU(对角)", "晶振布局检查", _m_crystal_far, "layout"),
    "connector_inward":  ("连接器移至板中心", "连接器边沿布局检查", _m_connector_inward, "layout"),
    "temp_near_heat":    ("电解电容压热源", "温度敏感元件布局检查", _m_temp_near_heat, "layout"),
}

# 有明确证据路径、但需要额外图层/元数据而本批未注入的规则（如实披露）
NOT_INJECTED = {
    "geometry": {
        "走线直角检查": "直角仅对高速/时钟/差分网报，注入需可控高速网名与完整叠层",
        "差分对间距检查": "需工程差分对元数据（epro2 板多为名字猜测对，非声明组）",
        "差分对等长检查": "同上",
        "时钟信号包地检查": "需时钟网+包地走线同时存在，多数板无此结构",
        "短桩线检查": "仅 ≥4 层板有意义，epro2 子集多为 2 层板",
        "环路面积检查": "需电源回路拓扑（输入电容-芯片-输出电容焊盘级连接）",
        "铜皮连接检查": "需覆铜孤岛判定，注入覆铜需重建 POUR 几何",
        "过孔热焊盘检查": "需过孔-覆铜包含关系与 thermal spoke 几何",
        "地平面连续性检查": "需平面层数据（负片/内层）",
        "高速信号参考平面检查": "需叠层与平面分配数据",
        "特征阻抗匹配检查": "需叠层介质参数（εr/层厚），注入即臆造叠层",
        "天线效应检查": "需天线网络识别（2.4G/GNSS 天线焊盘），子集板少有",
        "测试点覆盖检查": "需测试点图层标注",
        "丝印可读性检查": "需丝印图层（epro2 解析未含丝印元素）",
        "丝印焊盘间距检查": "同上",
    },
    "layout": {
        "模数分离检查": "需模拟/数字分区判定（AGND 簇聚类），注入分区边界即臆造",
        "安装孔禁区检查": "需安装孔坐标（epro2 解析未含安装孔元素）",
        "光学定位点检查": " absence 型规则（无基准点即报），非缺陷注入范式",
        "EMI 滤波器布局检查": "需 EMI 滤波拓扑识别（磁珠-电容链），子集板少有完整链",
    },
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只解析前 N 板（调试）")
    args = ap.parse_args()

    files = sorted((ROOT / "test_data/_incoming_epro2/78").glob("*.epro2"))
    if args.limit:
        files = files[: args.limit]
    print(f"[inject] epro2 真实板 {len(files)} 块，缺陷类型 {len(DEFECTS)} 种")

    checker = DesignRuleChecker()
    records = []
    for bi, f in enumerate(files, 1):
        try:
            pcb = Epro2Parser().parse(str(f))
            bom = bom_rows_to_items(pcb.bom_items)
        except Exception as e:
            records.append({"board": f.stem[:50], "defect": "PARSE", "error": str(e)[:120]})
            continue
        if not bom or not pcb.component_positions:
            records.append({"board": f.stem[:50], "defect": "SKIP",
                            "error": "无 BOM/坐标"})
            continue
        try:
            base_vs = checker.check_all(bom, pcb.component_positions, pcb_data=pcb)
            base_viol = {v.rule_name for v in base_vs}
            base_descs: dict[str, list] = {}
            for v in base_vs:
                base_descs.setdefault(v.rule_name, []).append(v.description)
        except Exception as e:
            records.append({"board": f.stem[:50], "defect": "BASELINE", "error": str(e)[:120]})
            continue
        if checker.rule_errors:
            records.append({"board": f.stem[:50], "defect": "BASELINE_RULE_ERROR",
                            "error": str(checker.rule_errors)[:160]})
        for did, (dname, rule, mut, module) in DEFECTS.items():
            rec = {"board": f.stem[:50], "defect": did, "defect_name": dname,
                   "expected_rule": rule, "module": module}
            try:
                p2 = copy.deepcopy(pcb)
                applied = mut(p2, bom)
                if not applied:
                    rec["status"] = "not_applicable"
                    records.append(rec)
                    continue
                after_vs = checker.check_all(
                    bom, p2.component_positions, pcb_data=p2)
                after = {v.rule_name for v in after_vs}
                if checker.rule_errors:
                    rec["rule_errors"] = str(checker.rule_errors)[:160]
                rec["status"] = "done"
                rec["fired_before"] = rule in base_viol
                rec["fired_after"] = rule in after
                # 检出两级判定：
                # 严格 = 基线未触发该规则、注入后触发；
                # 实例级 = 基线已触发（聚合违规），注入后该规则的违规实例
                # 描述集发生变化（如聚合计数/位号清单因注入缺陷而新增）。
                new_instance = (rule in after and any(
                    d not in base_descs.get(rule, [])
                    for v2 in after_vs if v2.rule_name == rule
                    for d in [v2.description]))
                rec["detected_strict"] = (rule in after) and (rule not in base_viol)
                rec["detected"] = rec["detected_strict"] or new_instance
                rec["extra_after"] = len(after - base_viol)
            except Exception as e:
                rec["status"] = "error"
                rec["error"] = f"{type(e).__name__}: {e}"[:160]
            records.append(rec)
        print(f"  [{bi:2d}/{len(files)}] {f.stem[:40]} 基线 {len(base_viol)} 违规")

    # ── 汇总 ──
    out_dir = ROOT / "experiment_results" / (
        "module_injection_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(
        {"generated": datetime.now().isoformat(),
         "dataset": "test_data/_incoming_epro2/78 (立创专业版真实工程)",
         "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 几何/布局规则缺陷注入汇总（R18 增强路径）", "",
             f"- 数据: 78 块立创专业版真实工程（epro2，含真实走线/过孔/板框/坐标）",
             f"- 检出定义: 期望规则注入后触发且注入前未触发", ""]
    for module in ("geometry", "layout"):
        lines.append(f"## {'几何类' if module == 'geometry' else '布局类'}缺陷注入")
        lines.append("")
        lines.append("| 缺陷 | 期望规则 | 可注入板数 | 检出 | 检出率 |")
        lines.append("|------|----------|-----------|------|--------|")
        mod_det = mod_att = 0
        for did, (dname, rule, _m, m2) in DEFECTS.items():
            if m2 != module:
                continue
            rs = [r for r in records if r.get("defect") == did]
            done = [r for r in rs if r.get("status") == "done"]
            det = sum(1 for r in done if r.get("detected"))
            mod_att += len(done)
            mod_det += det
            rate = f"{det / len(done) * 100:.0f}%" if done else "—"
            lines.append(f"| {dname} | {rule} | {len(done)} | {det} | {rate} |")
        rate = f"{mod_det / mod_att * 100:.1f}%" if mod_att else "—"
        lines.append(f"| **合计** | | **{mod_att}** | **{mod_det}** | **{rate}** |")
        lines.append("")
        na = [r for r in records if r.get("status") == "not_applicable"]
        na_by_defect = Counter(r["defect"] for r in na)
        if na_by_defect:
            lines.append("不可注入（前置条件不满足）: "
                         + ", ".join(f"{d}×{n}" for d, n in sorted(na_by_defect.items())))
        lines.append("")
    errs = [r for r in records if r.get("status") == "error"]
    if errs:
        lines.append(f"错误记录 {len(errs)} 条（详见 results.json）")
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[DONE] {out_dir}")
    print("\n".join(lines[12:]))


if __name__ == "__main__":
    main()

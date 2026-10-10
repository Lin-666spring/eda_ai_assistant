"""规则违规明细 dump —— 为「抽查判读」准备可核对的证据行。

背景
----
覆盖率实验（scripts/epro2_rule_coverage.py）报的是**口径 B「有输出」**：
71 条规则里 61 条在 76 个真实设计上至少报出过 1 条违规。但「被触发」不等于
「判断正确」——coverage.json 只存每个设计的规则计数，**没有单条违规的明细**，
所以没法逐条核对，也没法算精确率。

本脚本把 C3（全量 .epro2）配置下的**每一条违规**连同判读所需的证据一起落盘：

    experiment_results/rule_spotcheck/violations.jsonl   每行一条违规
    experiment_results/rule_spotcheck/dump_summary.json  计数 / 耗时 / 失败规则

证据（evidence 字段）由 EVIDENCE_BUILDERS 按规则函数名分派，尽量补上
「违规描述里没写、但判读必需」的上下文：

- 线宽类：该网络**按长度加权**的线宽分布、窄段占比、窄段是否紧邻过孔/焊盘
- 拐角类：全部拐角的角度 + 两条腿长度、离最近过孔/元件/板框的距离
- 串扰类：具体是哪几对网络、间距、平行重叠长度、线宽（重算，不只看汇总串）
- 差分对：组成员、各自线长、间距/线宽比、分组来自工程 NET 规则还是名字猜测
- 电源类：估算电流、IPC-2221 实际载流、所需线宽、是否 GND 类网络

用法::

    python scripts/rule_spotcheck_dump.py test_data/_incoming_epro2
    python scripts/rule_spotcheck_dump.py test_data/_incoming_epro2 --limit 3
    python scripts/rule_spotcheck_dump.py test_data/_incoming_epro2 --rules _check_signal_traces

零 LLM、零网络。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.constants import PCB  # noqa: E402
from src.pcb.calculator import (  # noqa: E402
    ipc2221_current_capacity,
    ipc2221_trace_width,
    microstrip_impedance,
)
from src.pcb.epro2_parser import Epro2Parser  # noqa: E402
from src.pcb.geometry import trace_corners  # noqa: E402
from src.rules.checker import (  # noqa: E402
    DesignRuleChecker,
    _parallel_overlap_len,
    _seg_seg_dist,
)
from epro2_rule_coverage import build_inputs, extract_guards, _fingerprint  # noqa: E402


# ──────────────── 通用小工具 ────────────────

def _seg_len(s) -> float:
    return math.hypot(s[2] - s[0], s[3] - s[1])


def _trace_len(t) -> float:
    return sum(_seg_len(s) for s in (t.segments or []))


def _net_traces(pcb, net: str) -> list:
    return [t for t in pcb.traces if t.net_name == net]


def _width_profile(traces) -> tuple[dict, float]:
    """按**长度**加权的线宽分布 + 最小线宽（比按条数更能反映「这根线大部分多宽」）。"""
    by_w: dict[float, float] = defaultdict(float)
    for t in traces:
        by_w[round(t.width_mm, 4)] += _trace_len(t)
    return dict(sorted(by_w.items())), (min(by_w) if by_w else 0.0)


def _landmarks(pcb, positions, pt) -> dict:
    """离该点最近的过孔 / 元件中心 / 板框边（判断「拐角是不是焊盘入口」用）。"""
    out: dict = {}
    best = None
    for v in (pcb.vias or []):
        pos = getattr(v, "position", None)
        if not pos:
            continue
        d = math.hypot(pt[0] - pos[0], pt[1] - pos[1])
        if best is None or d < best[0]:
            best = (d, getattr(v, "net_name", "") or "")
    if best:
        out["near_via_mm"] = round(best[0], 3)
        out["near_via_net"] = best[1]
    best_c = None
    for ref, p in (positions or {}).items():
        if not isinstance(p, dict):
            continue
        x, y = p.get("x"), p.get("y")
        if x is None or y is None:
            continue
        d = math.hypot(pt[0] - x, pt[1] - y)
        if best_c is None or d < best_c[0]:
            best_c = (d, ref)
    if best_c:
        out["near_comp_mm"] = round(best_c[0], 3)
        out["near_comp"] = best_c[1]
    bo = pcb.board_outline or {}
    w, h = bo.get("width_mm"), bo.get("height_mm")
    if w and h:
        out["edge_mm"] = round(min(pt[0], pt[1], abs(w - pt[0]), abs(h - pt[1])), 3)
    return out


def _design_ctx(pcb, positions, netlist) -> dict:
    layers = sorted({t.layer for t in pcb.traces if t.layer})
    widths: Counter = Counter()
    for t in pcb.traces:
        widths[round(t.width_mm, 4)] += _trace_len(t)
    return {
        "components": len(pcb.component_positions or {}),
        "nets": len(pcb.nets or {}),
        "netlist_nets": len(netlist or {}),
        "traces": len(pcb.traces or []),
        "vias": len(pcb.vias or []),
        "pours": len(getattr(pcb, "copper_pours", None) or []),
        "layers": layers,
        "board_mm": [pcb.board_outline.get("width_mm"), pcb.board_outline.get("height_mm")]
        if pcb.board_outline else None,
        "width_by_len_top3": [
            [w, round(L, 1)] for w, L in sorted(widths.items(), key=lambda kv: -kv[1])[:3]
        ],
        "diff_groups_meta": len(getattr(pcb, "differential_pairs", None) or []),
    }


# ──────────────── 证据构造器（按规则函数名分派）───────────────

def _ev_width(checker, pcb, positions, bom_items, v) -> dict:
    """信号线宽：窄到多少、窄段占该网络总长的比例、窄段是否贴着焊盘/过孔。"""
    net = v.location or ""
    traces = _net_traces(pcb, net)
    prof, minw = _width_profile(traces)
    all_w = [t.width_mm for t in pcb.traces if t.width_mm > 0]
    dom = Counter(round(w, 4) for w in all_w).most_common(1)[0][0] if all_w else 0.0
    # 2026-10-09 起判据只剩绝对下限（60% 主流线宽相对条款已删）
    floor = PCB.SIGNAL_TRACE_ABS_MIN_WIDTH_MM
    total = sum(prof.values()) or 1.0
    narrow = sum(L for w, L in prof.items() if w < floor)
    near = []
    for t in traces:
        if t.width_mm >= floor:
            continue
        for s in (t.segments or []):
            near.append(_landmarks(pcb, positions, (s[0], s[1])))
    near_via = min([n["near_via_mm"] for n in near if "near_via_mm" in n], default=None)
    near_comp = min([n["near_comp_mm"] for n in near if "near_comp_mm" in n], default=None)
    return {
        "net": net,
        "board_layers_n": len({t.layer for t in pcb.traces if t.layer}),
        "width_by_len": {str(w): round(L, 2) for w, L in prof.items()},
        "net_min_width": minw,
        "board_dominant_width": dom,
        "effective_floor": round(floor, 4),
        "narrow_len_mm": round(narrow, 2),
        "narrow_share": round(narrow / total, 3),
        "narrow_touches_via_mm": near_via,
        "narrow_touches_comp_mm": near_comp,
        "trace_rows": [
            {"layer": t.layer, "w": round(t.width_mm, 4), "len": round(_trace_len(t), 2),
             "nseg": len(t.segments or [])}
            for t in traces[:8]
        ],
    }


def _ev_power(checker, pcb, positions, bom_items, v) -> dict:
    net = v.location or ""
    traces = _net_traces(pcb, net)
    prof, minw = _width_profile(traces)
    est = checker._estimate_power_current(bom_items)
    need = checker._estimate_net_current(net, est)
    # 与规则一致：取**最窄那条走线**，外层/内层按它自己的层判定
    # （2026-09-18 修复前是「整板只要有 inner 层电源线就全局降额」）
    narrow_w, narrow_layer = min(
        ((t.width_mm, str(getattr(t, "layer", "") or "")) for t in traces),
        key=lambda x: x[0], default=(minw, ""))
    from src.rules.checker import _is_inner_layer
    rule_is_inner = _is_inner_layer(pcb, narrow_layer)
    narrow_layer = narrow_layer or "(未知)"
    cap_outer = ipc2221_current_capacity(minw, PCB.IPC_COPPER_OZ, PCB.IPC_TEMP_RISE, False)
    cap_inner = ipc2221_current_capacity(minw, PCB.IPC_COPPER_OZ, PCB.IPC_TEMP_RISE, True)
    cap = ipc2221_current_capacity(minw, PCB.IPC_COPPER_OZ, PCB.IPC_TEMP_RISE, rule_is_inner)
    req = ipc2221_trace_width(need, PCB.IPC_COPPER_OZ, PCB.IPC_TEMP_RISE, False)
    return {
        "net": net,
        "rule_is_inner_flag": rule_is_inner,
        "narrowest_layer": narrow_layer,
        "layers": sorted({t.layer for t in traces}),
        "capacity_outer_a": round(cap_outer, 2),
        "capacity_inner_a": round(cap_inner, 2),
        "width_by_len": {str(w): round(L, 2) for w, L in prof.items()},
        "net_min_width": minw,
        "net_total_len_mm": round(sum(prof.values()), 2),
        "pins": len(getattr(pcb.nets.get(net), "pins", []) or []),
        "is_ground_like": any(k in net.upper() for k in ("GND", "AGND", "DGND", "PGND", "VSS")),
        "est_total_current_a": est,
        "est_net_current_a": need,
        "ipc_capacity_a": round(cap, 2),
        "ipc_required_width_mm": round(req, 3),
        "copper_pours": len(getattr(pcb, "copper_pours", None) or []),
    }


def _ev_angles(checker, pcb, positions, bom_items, v) -> dict:
    """拐角：列出全部拐角（含被最小腿长门限滤掉的退化拐角）及地标距离。"""
    net = v.location or ""
    rows = []
    for t in _net_traces(pcb, net):
        for c in trace_corners(t.segments, min_leg_mm=0.0):
            leg = min(c.leg_in_mm, c.leg_out_mm)
            lm = _landmarks(pcb, positions, c.vertex)
            rows.append({
                "layer": t.layer,
                "ang": round(c.angle_deg, 1),
                "leg_min": round(leg, 3),
                "leg_in": round(c.leg_in_mm, 3),
                "leg_out": round(c.leg_out_mm, 3),
                "w": round(t.width_mm, 3),
                "xy": [round(c.vertex[0], 2), round(c.vertex[1], 2)],
                **lm,
            })
    rows.sort(key=lambda r: r["ang"])
    gate = PCB.TRACE_CORNER_MIN_LEG_MM
    prof, minw = _width_profile(_net_traces(pcb, net))
    return {
        "net": net,
        "corners_total": len(rows),
        "acute": [r for r in rows if r["ang"] < PCB.TRACE_ACUTE_ANGLE_MAX_DEG],
        "right": [r for r in rows if PCB.TRACE_RIGHT_ANGLE_MIN_DEG <= r["ang"]
                  <= PCB.TRACE_RIGHT_ANGLE_MAX_DEG],
        "degenerate_below_leg_gate": [r for r in rows if r["leg_min"] < gate],
        "worst6": rows[:6],
        "net_min_width": minw,
        "net_total_len_mm": round(sum(prof.values()), 2),
    }


def _crosstalk_pairs(pcb, layer: str, cap: int = 8) -> list:
    """重算该层所有「平行重叠 >= 门限 且 间距 < 3W」的线对（与 checker 同判据）。"""
    factor = PCB.CROSSTALK_SPACING_FACTOR
    min_par = PCB.CROSSTALK_MIN_PARALLEL_MM
    traces = [t for t in pcb.traces if t.layer == layer and t.segments]
    if len(traces) < 2:
        return []
    max_w = max((t.width_mm or 0.0) for t in traces) or 0.2
    radius = factor * max_w
    cell = max(radius, 0.3)
    grid: dict = {}
    segs = []
    for t in traces:
        w = t.width_mm or 0.0
        for s in t.segments:
            idx = len(segs)
            a, b = (s[0], s[1]), (s[2], s[3])
            x0, x1 = (a[0], b[0]) if a[0] <= b[0] else (b[0], a[0])
            y0, y1 = (a[1], b[1]) if a[1] <= b[1] else (b[1], a[1])
            segs.append((t.net_name, w, a, b, x0, x1, y0, y1))
            for ci in range(int((x0 - radius) // cell), int((x1 + radius) // cell) + 1):
                for cj in range(int((y0 - radius) // cell), int((y1 + radius) // cell) + 1):
                    grid.setdefault((ci, cj), []).append(idx)
    pairs: dict = {}
    for i, (net, w, a, b, x0, x1, y0, y1) in enumerate(segs):
        seen = set()
        for ci in range(int((x0 - radius) // cell), int((x1 + radius) // cell) + 1):
            for cj in range(int((y0 - radius) // cell), int((y1 + radius) // cell) + 1):
                for j in grid.get((ci, cj), ()):
                    if j <= i or j in seen:
                        continue
                    seen.add(j)
                    n2, w2, c, d, cx0, cx1, cy0, cy1 = segs[j]
                    if n2 == net:
                        continue
                    avg_w = (w + w2) * 0.5
                    if avg_w <= 0:
                        continue
                    thr = factor * avg_w
                    if (cx0 - x1 > thr or x0 - cx1 > thr
                            or cy0 - y1 > thr or y0 - cy1 > thr):
                        continue
                    ov = _parallel_overlap_len(a, b, c, d)
                    if ov <= 0:
                        continue
                    dmin = _seg_seg_dist(a, b, c, d)
                    if dmin >= thr:
                        continue
                    key = (net, n2) if net <= n2 else (n2, net)
                    rec = pairs.get(key)
                    if rec is None:
                        pairs[key] = {"nets": list(key), "overlap_mm": ov,
                                      "gap_mm": dmin, "avg_w": avg_w}
                    else:
                        rec["overlap_mm"] += ov
                        rec["gap_mm"] = min(rec["gap_mm"], dmin)
    out = [p for p in pairs.values() if p["overlap_mm"] >= min_par]
    out.sort(key=lambda p: -p["overlap_mm"])
    for p in out:
        p["overlap_mm"] = round(p["overlap_mm"], 2)
        p["gap_mm"] = round(p["gap_mm"], 3)
        p["ratio_W"] = round(p["gap_mm"] / p["avg_w"], 2) if p["avg_w"] else None
        p["avg_w"] = round(p["avg_w"], 3)
    return out[:cap]


def _ev_crosstalk(checker, pcb, positions, bom_items, v) -> dict:
    return {"layer": v.location, "pairs": _crosstalk_pairs(pcb, v.location)}


def _ev_diff_len(checker, pcb, positions, bom_items, v) -> dict:
    lengths: dict = defaultdict(float)
    for t in pcb.traces:
        if t.net_name:
            lengths[t.net_name] += _trace_len(t)
    nets = [n.strip() for n in (v.description.split(":")[-1].split(",")) if n.strip()]
    meta = [e for e in (getattr(pcb, "differential_pairs", None) or [])
            if str(e.get("differential") or e.get("equal_length_group")) == v.location]
    # 整组成员：工程 NET 规则里同一 differential/equal_length_group 的全部网络
    members = [str(e.get("net")) for e in meta if e.get("net")] or nets
    group_len = sorted(
        ((n, round(lengths.get(n, 0.0), 2)) for n in members), key=lambda kv: kv[1])
    # 批5 2026-10-10 证据口径对齐：tolerance 不再引用已废弃的
    # PCB.DIFF_PAIR_MAX_SKEW_MM 常量 —— 规则已改 _DIFF_SKEW_BANDS 按接口
    # 分档（USB2.0 2.0mm / 高速串行·ETH 0.5mm / 表外 2.0mm+10% 相对），
    # 这里按同样的文本匹配取该组实际适用的档位。
    text = f"{v.location} {' '.join(members)}".lower()
    bands = getattr(checker, "_DIFF_SKEW_BANDS", ())
    tol, band = next(
        ((t, name) for kws, t, name in bands
         if any(kw.lower() in text for kw in kws)),
        (getattr(checker, "_DIFF_SKEW_DEFAULT_MM", 2.0), "表外差分组"),
    )
    return {
        "group": v.location,
        "nets_in_description": nets,
        "group_members_all": [n for n, _ in group_len],
        "group_lengths_all": {n: L for n, L in group_len},
        "group_skew_mm": round(group_len[-1][1] - group_len[0][1], 2) if group_len else None,
        "net_lengths": {n: round(lengths.get(n, 0.0), 2) for n in nets},
        "group_from_engineering_netrules": bool(meta),
        "meta_rows": meta[:4],
        "tolerance_mm": tol,
        "band": band,
    }


def _ev_diff_gap(checker, pcb, positions, bom_items, v) -> dict:
    nets = v.description.split("[")[1].split("]")[0].split(" / ") if "[" in v.description else []
    gap = checker._pair_min_gap(pcb, tuple(nets)) if len(nets) == 2 else None
    widths = [t.width_mm for t in pcb.traces if t.net_name in nets and t.width_mm > 0]
    meta = [e for e in (getattr(pcb, "differential_pairs", None) or [])
            if e.get("net") in nets]
    return {
        "pair": nets,
        "gap_mm": round(gap, 3) if gap is not None else None,
        "widths": widths[:6],
        "avg_w": round(sum(widths) / len(widths), 3) if widths else None,
        # 批5 2026-10-10 对齐：规则口径是 max(3W, 4W)=4W
        # （geometry_rules._check_diff_pair_spacing），不是裸常量 3.0
        "limit_W": max(PCB.DIFF_PAIR_MAX_GAP_FACTOR, 4.0),
        "from_engineering_netrules": bool(meta),
        "meta_rows": meta[:4],
    }


def _ev_clock_guard(checker, pcb, positions, bom_items, v) -> dict:
    """时钟线旁边到底有没有 GND 护线 —— 直接决定这条 INFO 是否冤。"""
    net = v.location or ""
    gnd_nets = [t for t in pcb.traces if t.net_name and "GND" in t.net_name.upper()]
    best = None
    layers = set()
    for t in _net_traces(pcb, net):
        layers.add(t.layer)
        for s in (t.segments or []):
            a, b = (s[0], s[1]), (s[2], s[3])
            for g in gnd_nets:
                if g.layer != t.layer:
                    continue
                for s2 in (g.segments or []):
                    d = _seg_seg_dist(a, b, (s2[0], s2[1]), (s2[2], s2[3]))
                    if best is None or d < best:
                        best = d
    return {
        "net": net,
        "layers": sorted(layers),
        "nearest_gnd_trace_mm": round(best, 3) if best is not None else None,
        "gnd_trace_count_on_board": len(gnd_nets),
        "pours": len(getattr(pcb, "copper_pours", None) or []),
    }


def _ev_hs_ref(checker, pcb, positions, bom_items, v) -> dict:
    kws = ["CLK", "USB", "HDMI", "PCIE", "SDRAM", "LVDS", "ETH"]
    nets = sorted({t.net_name for t in pcb.traces if t.net_name
                   and any(k in t.net_name.upper() for k in kws)})
    layer_of: dict = defaultdict(set)
    for t in pcb.traces:
        if t.net_name in nets:
            layer_of[t.net_name].add(t.layer)
    return {
        "hs_nets": nets[:20],
        "hs_net_count": len(nets),
        "layers_used": sorted({l for ls in layer_of.values() for l in ls}),
        "board_layers": sorted({t.layer for t in pcb.traces if t.layer}),
        "pours": len(getattr(pcb, "copper_pours", None) or []),
    }


def _ev_loop_area(checker, pcb, positions, bom_items, v) -> dict:
    net = pcb.nets.get(v.location)
    traces = _net_traces(pcb, v.location)
    return {
        "net": v.location,
        "net_total_length_mm": round(getattr(net, "total_length_mm", 0.0), 2),
        "length_sum_of_traces_mm": round(sum(_trace_len(t) for t in traces), 2),
        "pins": len(getattr(net, "pins", []) or []),
        "layers": sorted({t.layer for t in traces}),
        "threshold_mm": 50,
    }


def _ev_stub(checker, pcb, positions, bom_items, v) -> dict:
    kws = {"CLK", "SCK", "SDIO", "SDRAM", "USB", "HDMI", "PCIE"}
    nets = sorted({(getattr(x, "net_name", "") or "") for x in (pcb.vias or [])})
    hit = [n for n in nets if n and any(k in n.upper() for k in kws)]
    per_net = Counter((getattr(x, "net_name", "") or "") for x in (pcb.vias or []))
    return {
        "hs_nets_with_via": hit[:10],
        "via_count_per_hs_net": {n: per_net[n] for n in hit[:10]},
        "total_vias": len(pcb.vias or []),
    }


def _ev_edge(checker, pcb, positions, bom_items, v) -> dict:
    return {
        "description_nets": v.location,
        "board_mm": [pcb.board_outline.get("width_mm"), pcb.board_outline.get("height_mm")]
        if pcb.board_outline else None,
        "threshold_mm": PCB.TRACE_EDGE_CLEARANCE_MIN_MM,
    }


def _ev_impedance(checker, pcb, positions, bom_items, v) -> dict:
    net = v.location or ""
    traces = _net_traces(pcb, net)
    widths = [t.width_mm for t in traces if t.width_mm > 0]
    # 批5 2026-10-10 证据口径对齐规则（geometry_rules._check_impedance_control）：
    # ① 目标表是差分值且不含 CLK（时钟网不是差分对，10-09 判读修正已删），
    #    RF/ANT 走单端 50Ω（single_kw）；② 判据用 differential_impedance 而非
    #    裸 microstrip —— 证据里的 z0 只是「该线宽在标称 0.2mm 介质下的单端
    #    参考值」，字段名如实标注，不再冒充判据值。
    diff_targets = {"USB": 90.0, "HDMI": 100.0, "LVDS": 100.0, "ETH": 100.0,
                    "MIPI": 100.0, "PCIE": 100.0, "SATA": 100.0}
    upper = net.upper()
    z_target = next((z for k, z in diff_targets.items() if k in upper), None)
    if z_target is None and any(k in upper for k in ("RF", "ANT")):
        z_target = 50.0  # 单端天线/射频
    w = widths[0] if widths else 0.0
    return {
        "net": net,
        "widths": widths[:6],
        "z0_ref_nominal_0.2mm": round(microstrip_impedance(w, 0.2, er=4.5), 1) if w else None,
        "z_target": z_target,
        "tolerance": getattr(PCB, "IMPEDANCE_TOLERANCE", 0.25),
        "layers": sorted({t.layer for t in traces}),
        "n_traces": len(traces),
    }


def _ev_net_antenna(checker, pcb, positions, bom_items, v) -> dict:
    singles = [n for n, net in (pcb.nets or {}).items()
               if len(getattr(net, "pins", []) or []) <= 1 and n
               and not n.upper().startswith("GND")]
    return {"single_pin_nets": singles[:20], "count": len(singles)}


def _ev_generic(checker, pcb, positions, bom_items, v) -> dict:
    return {}


EVIDENCE_BUILDERS = {
    "_check_signal_traces": _ev_width,
    "_check_power_traces": _ev_power,
    "_check_trace_acute_angles": _ev_angles,
    "_check_crosstalk_spacing": _ev_crosstalk,
    "_check_diff_pair_length": _ev_diff_len,
    "_check_diff_pair_spacing": _ev_diff_gap,
    "_check_clock_guard_trace": _ev_clock_guard,
    "_check_hs_signal_reference_plane": _ev_hs_ref,
    "_check_loop_area": _ev_loop_area,
    "_check_stub_length": _ev_stub,
    "_check_trace_edge_clearance": _ev_edge,
    "_check_impedance_matching": _ev_impedance,
    "_check_net_antenna": _ev_net_antenna,
}

# 本次抽查关注的「走线类」规则（守卫都依赖 pcb.traces / pcb.vias）
TRACE_RULES = (
    "_check_signal_traces",
    "_check_power_traces",
    "_check_trace_acute_angles",
    "_check_crosstalk_spacing",
    "_check_diff_pair_length",
    "_check_diff_pair_spacing",
    "_check_clock_guard_trace",
    "_check_hs_signal_reference_plane",
    "_check_loop_area",
    "_check_stub_length",
    "_check_trace_edge_clearance",
    "_check_impedance_matching",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", default="experiment_results/rule_spotcheck")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 个唯一设计（调试用）")
    ap.add_argument("--rules", default="", help="逗号分隔，只跑这些规则函数名")
    args = ap.parse_args()

    root = Path(args.path)
    files = sorted(root.rglob("*.epro2")) if root.is_dir() else [root]
    only = {r.strip() for r in args.rules.split(",") if r.strip()}

    guards = extract_guards()
    rule_names = [r for r in sorted(guards) if not only or r in only]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    parser = Epro2Parser()
    checker = DesignRuleChecker()
    seen_fp: dict = {}
    n_designs = 0
    n_records = 0
    by_rule: Counter = Counter()
    by_rule_name: Counter = Counter()
    rule_errors: Counter = Counter()

    t0 = time.perf_counter()
    with (out_dir / "violations.jsonl").open("w", encoding="utf-8") as fh:
        for i, f in enumerate(files, 1):
            try:
                pcb = parser.parse(str(f))
            except Exception as e:  # noqa: BLE001
                print(f"[{i}] 解析失败 {f.name}: {e}")
                continue
            fp = _fingerprint(pcb)
            if fp in seen_fp:
                print(f"[{i}] 跳过重复设计 {f.name} (同 {seen_fp[fp]})")
                continue
            seen_fp[fp] = f.name
            n_designs += 1

            bom_items, positions, netlist, _ = build_inputs(pcb)
            checker._pcb_data = pcb
            ctx = _design_ctx(pcb, positions, netlist)
            design = {"file": f.name, "title": pcb.metadata.get("title"), "ctx": ctx}

            for rule in rule_names:
                try:
                    res = getattr(checker, rule)(bom_items, positions, netlist)
                except Exception as e:  # noqa: BLE001
                    rule_errors[(rule, type(e).__name__)] += 1
                    continue
                for k, v in enumerate(res or []):
                    builder = EVIDENCE_BUILDERS.get(rule, _ev_generic)
                    try:
                        evidence = builder(checker, pcb, positions, bom_items, v)
                    except Exception as e:  # noqa: BLE001
                        evidence = {"evidence_error": f"{type(e).__name__}: {e}"}
                    rec = {
                        "id": fp + "-" + rule.replace("_check_", "") + "-" + str(k),
                        "design": design,
                        "rule_func": rule,
                        "rule_name": v.rule_name,
                        "severity": v.severity.value,
                        "description": v.description,
                        "location": v.location,
                        "suggestion": v.suggestion,
                        "is_trace_family": rule in TRACE_RULES,
                        "evidence": evidence,
                    }
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_records += 1
                    by_rule[rule] += 1
                    by_rule_name[v.rule_name] += 1

            if i % 10 == 0:
                print(f"  ... {i}/{len(files)} 文件，{n_records} 条违规")
            if args.limit and n_designs >= args.limit:
                break

    elapsed = time.perf_counter() - t0
    summary = {
        "source": str(root),
        "designs": n_designs,
        "rules_run": len(rule_names),
        "violations": n_records,
        "elapsed_s": round(elapsed, 1),
        "by_rule_func": dict(by_rule.most_common()),
        "by_rule_name": dict(by_rule_name.most_common()),
        "rule_errors": {k[0] + "|" + k[1]: c for k, c in rule_errors.items()},
        "trace_rules": list(TRACE_RULES),
    }
    (out_dir / "dump_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n设计 {n_designs} 个 / 规则 {len(rule_names)} 条 / 违规 {n_records} 条 "
          f"/ 耗时 {elapsed:.1f}s")
    if rule_errors:
        print("规则异常:", dict(rule_errors))
    print("明细 -> " + str(out_dir / "violations.jsonl"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

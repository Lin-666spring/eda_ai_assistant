"""走线类规则阈值校准 — 用真实 .epro2 数据集测原始度量的分布。

**零 LLM、零网络**：只用 Epro2Parser 解析，然后直接统计走线类规则
（信号线宽 / 过孔密度 / 板边间距 / 3W 串扰 / 差分对 / 时钟包地 / 环路）
所依赖的**原始物理量**，不做任何判定，避免"阈值既是判定依据又是被测量"的循环。

产出（默认 experiment_results/trace_threshold_calibration/）:

- metrics.json   每个设计的原始度量（可复现）
- report.txt     全局分位数 + 候选阈值命中率（人读）

用法::

    python scripts/calibrate_trace_thresholds.py test_data/_incoming_epro2
    python scripts/calibrate_trace_thresholds.py <root> --no-crosstalk
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.constants import PCB  # noqa: E402
from src.pcb.epro2_parser import Epro2Parser  # noqa: E402
from src.pcb.geometry import chain_segments, polyline_corners  # noqa: E402

# ──────────────── 候选阈值（只用于命中率统计，不是现行配置） ────────────────

FAB_MIN_WIDTH_MM = 0.127          # 5mil，1oz 常规最小线宽
FAB_TYPICAL_WIDTH_MM = 0.1524     # 6mil，低成本推荐
WIDTH_CANDIDATES = (0.10, 0.127, 0.15, 0.1524, 0.20, 0.25)

VIA_COUNT_CANDIDATES = (2, 3, 5, 10, 20, 50, 100)

EDGE_CANDIDATES = (0.2, 0.3, 0.5, 0.8)

HS_LENGTH_CANDIDATES = (50.0, 100.0, 200.0)

DIFF_LEN_CANDIDATES = (0.127, 0.5, 1.0)   # mm

CROSSTALK_PARALLEL_CANDIDATES = (0.5, 1.0, 2.0, 5.0, 10.0)   # mm 平行重叠长度

# 走线拐角（内角）候选阈值：45° 布线 → 135°，直角 → 90°，锐角 → <90°
ANGLE_ACUTE_CANDIDATES = (60.0, 80.0, 85.0, 89.0, 90.0)

POWER_KW = PCB.POWER_NET_KEYWORDS
HS_KW = ("CLK", "PWM", "SW", "SENSE", "FB", "DRV", "GATE", "DRIVE")
CLK_KW = ("CLK", "CLOCK", "OSC", "XTAL", "MCLK", "SCLK", "HCLK")
STUB_KW = ("CLK", "SCK", "SDIO", "SDRAM", "USB", "HDMI", "PCIE")


# ──────────────── 几何工具 ────────────────

def _seg_seg_dist(a, b, c, d) -> float:
    """两条线段 (a,b) 与 (c,d) 的最短距离。"""

    def pt_seg(p, s, e) -> float:
        sx, sy = s
        ex, ey = e
        dx, dy = ex - sx, ey - sy
        if dx == 0 and dy == 0:
            return math.hypot(p[0] - sx, p[1] - sy)
        t = ((p[0] - sx) * dx + (p[1] - sy) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        return math.hypot(p[0] - (sx + t * dx), p[1] - (sy + t * dy))

    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])

    d1, d2 = cross(c, d, a), cross(c, d, b)
    d3, d4 = cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0

    return min(
        pt_seg(a, c, d), pt_seg(b, c, d),
        pt_seg(c, a, b), pt_seg(d, a, b),
    )


def _seg_angle(a, b) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _parallel_overlap(a, b, c, d, tol_rad: float = 0.2618) -> float:
    """两条近似平行(夹角<15°)线段的投影重叠长度 (mm)；不平行返回 0。"""
    ang1, ang2 = _seg_angle(a, b), _seg_angle(c, d)
    diff = abs((ang1 - ang2 + math.pi / 2) % math.pi - math.pi / 2)
    if diff > tol_rad:
        return 0.0
    ux, uy = math.cos(ang1), math.sin(ang1)
    p1, p2 = a[0] * ux + a[1] * uy, b[0] * ux + b[1] * uy
    q1, q2 = c[0] * ux + c[1] * uy, d[0] * ux + d[1] * uy
    lo = max(min(p1, p2), min(q1, q2))
    hi = min(max(p1, p2), max(q1, q2))
    return max(0.0, hi - lo)


def _net_min_gap(ta, tb, cap: int = 4000):
    """两个网络在同层走线之间的最小线段距离 (mm)；不同层不比较。"""
    by_layer = {}
    for t in ta:
        by_layer.setdefault(t.layer, []).append(t)
    best = None
    n = 0
    for t in tb:
        for t0 in by_layer.get(t.layer, []):
            for s0 in (t0.segments or []):
                for s1 in (t.segments or []):
                    n += 1
                    if n > cap:
                        return best
                    d = _seg_seg_dist(
                        (s0[0], s0[1]), (s0[2], s0[3]),
                        (s1[0], s1[1]), (s1[2], s1[3]),
                    )
                    if best is None or d < best:
                        best = d
    return best


def _quantiles(values, qs=(0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100)) -> dict:
    if not values:
        return {}
    s = sorted(values)
    n = len(s)
    out = {}
    for q in qs:
        idx = min(n - 1, max(0, int(round((q / 100.0) * (n - 1)))))
        out[str(q)] = round(s[idx], 4)
    return out


def _fingerprint(pcb) -> str:
    refs = sorted(
        f"{ref}:{v.get('footprint_name', '')}" for ref, v in pcb.component_positions.items()
    )
    payload = "|".join([
        ",".join(refs),
        ",".join(sorted(pcb.nets)),
        f"{pcb.board_outline.get('width_mm')}x{pcb.board_outline.get('height_mm')}",
    ])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]


def _is_power(net: str) -> bool:
    up = net.upper()
    return any(kw.upper() in up for kw in POWER_KW)


def _has_kw(net: str, kws) -> bool:
    up = net.upper()
    return any(k.upper() in up for k in kws)


# ──────────────── 单个设计的度量 ────────────────

def measure(pcb, do_crosstalk: bool, max_segments: int) -> dict:
    bo = pcb.board_outline or {}
    m = {
        "title": pcb.metadata.get("title"),
        "layers": len(pcb.layers),
        "trace_polylines": len(pcb.traces),
        "vias": len(pcb.vias),
        "board_w_mm": bo.get("width_mm"),
        "board_h_mm": bo.get("height_mm"),
        "board_source": bo.get("source"),
        "segment_total": sum(len(t.segments or []) for t in pcb.traces),
    }

    width_poly = Counter()
    width_seg = Counter()
    net_min_width = {}
    net_is_power = {}
    net_len = {}
    net_traces = {}
    net_vias = Counter()

    for t in pcb.traces:
        w = round(t.width_mm or 0.0, 4)
        if w <= 0:
            continue
        width_poly[w] += 1
        width_seg[w] += len(t.segments or [])
        name = t.net_name or ""
        if not name:
            continue
        net_is_power[name] = _is_power(name)
        net_traces.setdefault(name, []).append(t)
        if w < net_min_width.get(name, float("inf")):
            net_min_width[name] = w
        length = sum(
            math.hypot(s[2] - s[0], s[3] - s[1]) for s in (t.segments or [])
        )
        net_len[name] = net_len.get(name, 0.0) + length

    for v in (pcb.vias or []):
        nm = getattr(v, "net_name", "") or ""
        if nm:
            net_vias[nm] += 1

    m["width_poly_top"] = {str(k): c for k, c in sorted(width_poly.items())[:40]}
    m["width_seg_top"] = {str(k): c for k, c in sorted(width_seg.items())[:40]}
    m["width_poly_total"] = sum(width_poly.values())
    m["width_below_fab_min_poly"] = sum(
        c for k, c in width_poly.items() if k < FAB_MIN_WIDTH_MM - 1e-9
    )

    sig_nets = {n for n, p in net_is_power.items() if not p}
    pow_nets = {n for n, p in net_is_power.items() if p}
    m["signal_net_min_width"] = {n: net_min_width[n] for n in sig_nets}
    m["power_net_min_width"] = {n: net_min_width[n] for n in pow_nets}
    m["net_via_count"] = dict(net_vias)
    m["net_len"] = {k: round(v, 3) for k, v in net_len.items()}
    m["hs_net_len"] = {
        n: round(v, 3) for n, v in net_len.items() if _has_kw(n, HS_KW)
    }
    m["clk_nets"] = [n for n in net_min_width if _has_kw(n, CLK_KW)]
    m["stub_nets"] = [
        n for n in net_vias if _has_kw(n, STUB_KW) and net_vias[n] > 0
    ]

    # ---- 本板信号线宽「主流值」：作为上下文感知阈值的基准 ----
    # 同一块板内线宽通常是设计者有意选择的一套工艺（如整板 6mil 或整板 4mil），
    # 用固定绝对下限会把「整板 4mil」的专业板全判违规；所以按本板众数判「异常细线」。
    by_poly: Counter = Counter()   # 线宽 → 折线条数
    by_seg: Counter = Counter()    # 线宽 → 线段条数
    for t in pcb.traces:
        name = t.net_name or ""
        if not name or _is_power(name):
            continue
        w = round(t.width_mm or 0.0, 4)
        if w > 0:
            by_poly[w] += 1
            by_seg[w] += len(t.segments or [])
    dom = by_poly.most_common(1)[0][0] if by_poly else 0.0
    dom_seg = by_seg.most_common(1)[0][0] if by_seg else 0.0
    m["dom_signal_width"] = dom
    m["dom_signal_width_by_seg"] = dom_seg
    m["signal_width_hist"] = {str(k): c for k, c in sorted(by_poly.items())}
    for r in (0.4, 0.5, 0.6, 0.75):
        m["sig_below_rel_" + str(r)] = (
            sum(1 for n in sig_nets if 0 < net_min_width.get(n, 9e9) < r * dom)
            if dom > 0 else 0
        )
    for a in (0.08, 0.09, 0.10, 0.127):
        m["sig_below_abs_" + str(a)] = sum(
            1 for n in sig_nets if net_min_width.get(n, 9e9) < a
        )

    # ---- 过孔数按网络类别拆分（现规则对所有网络一视同仁，是主嫌）----
    hs_vias = {n: c for n, c in net_vias.items() if _has_kw(n, HS_KW)}
    sig_vias = {n: c for n, c in net_vias.items() if not _is_power(n)}
    m["hs_net_via_count"] = hs_vias
    m["sig_net_via_count"] = sig_vias
    for c in VIA_COUNT_CANDIDATES:
        m["hs_nets_via_ge_" + str(c)] = sum(1 for v in hs_vias.values() if v >= c)
        m["sig_nets_via_ge_" + str(c)] = sum(1 for v in sig_vias.values() if v >= c)

    # ---- 差分对（用工程NET规则里的 differentialName/equalLengthGroupName，
    #      是设计者显式定义的 ground truth，不是名字猜测）----
    dp_groups = {}
    for entry in (getattr(pcb, "differential_pairs", None) or []):
        g = entry.get("differential") or entry.get("equal_length_group")
        if g:
            dp_groups.setdefault(g, []).append(entry.get("net"))
    dp_meta = []
    for g, nets in dp_groups.items():
        nets = sorted(set(n for n in nets if n))
        if len(nets) < 2:
            continue
        lens = [round(net_len.get(n, 0.0), 4) for n in nets]
        positive = [x for x in lens if x > 0]
        gap = None
        for i2 in range(len(nets)):
            for j2 in range(i2 + 1, len(nets)):
                gv = _net_min_gap(net_traces.get(nets[i2], []), net_traces.get(nets[j2], []))
                if gv is not None and (gap is None or gv < gap):
                    gap = gv
        wlist = [net_min_width.get(n, 0.0) for n in nets]
        avgw = (sum(wlist) / len(wlist)) if wlist else 0.0
        dp_meta.append({
            "group": g,
            "nets": nets,
            "lengths": lens,
            "widths": [round(x, 4) for x in wlist],
            "mismatch": round(max(positive) - min(positive), 4) if len(positive) >= 2 else 0.0,
            "min_gap": round(gap, 4) if gap is not None else None,
            "gap_ratio": round(gap / avgw, 3) if (gap is not None and avgw > 0) else None,
        })
    m["dp_meta"] = dp_meta
    m["dp_meta_mismatch"] = [d["mismatch"] for d in dp_meta]
    m["dp_meta_gap_ratio"] = [d["gap_ratio"] for d in dp_meta if d["gap_ratio"] is not None]
    for cand in DIFF_LEN_CANDIDATES:
        m["dp_meta_mismatch_gt_" + str(cand)] = sum(
            1 for d in dp_meta if d["mismatch"] > cand
        )

    for c in WIDTH_CANDIDATES:
        m["sig_net_below_" + str(c)] = sum(
            1 for n in sig_nets if net_min_width.get(n, 9e9) < c
        )
    for c in VIA_COUNT_CANDIDATES:
        m["nets_via_ge_" + str(c)] = sum(1 for n, cnt in net_vias.items() if cnt >= c)
    for c in HS_LENGTH_CANDIDATES:
        m["hs_nets_len_gt_" + str(c)] = sum(
            1 for v in m["hs_net_len"].values() if v > c
        )

    if bo.get("source") == "outline" and pcb.traces:
        minx, miny = bo["min_x_mm"], bo["min_y_mm"]
        maxx, maxy = bo["max_x_mm"], bo["max_y_mm"]
        clearances = []
        for t in pcb.traces:
            pts = []
            for s in (t.segments or []):
                pts.append((s[0], s[1]))
                pts.append((s[2], s[3]))
            if not pts:
                continue
            c = min(
                min(px - minx, maxx - px, py - miny, maxy - py) for px, py in pts
            )
            clearances.append(c)
        m["edge_clearances"] = [round(c, 4) for c in clearances]
        m["edge_min_mm"] = round(min(clearances), 4) if clearances else None
        for cand in EDGE_CANDIDATES:
            m["polylines_within_" + str(cand) + "mm"] = sum(
                1 for c in clearances if c < cand
            )

    pair_lengths = {}
    for t in pcb.traces:
        name = t.net_name or ""
        if not name:
            continue
        base, suffix = name, ""
        for suf in ("_P", "_N", "_p", "_n", "+", "-"):
            if name.endswith(suf):
                base, suffix = name[: -len(suf)], suf[-1].upper()
                break
        if not suffix:
            continue
        pair_lengths.setdefault(base, {})[suffix] = net_len.get(name, 0.0)
    diffs = []
    for base, dd in pair_lengths.items():
        vals = list(dd.values())
        if len(vals) >= 2 and min(vals) > 0:
            diffs.append(round(max(vals) - min(vals), 4))
    m["diff_pair_len_mismatch"] = diffs
    for cand in DIFF_LEN_CANDIDATES:
        m["diff_pairs_mismatch_gt_" + str(cand)] = sum(1 for d in diffs if d > cand)

    if do_crosstalk and pcb.traces:
        if m["segment_total"] > max_segments:
            m["crosstalk_skipped"] = "segments>" + str(max_segments)
        else:
            ratios = []
            contested = {}
            per_layer = {}
            for t in pcb.traces:
                if not t.segments:
                    continue
                per_layer.setdefault(t.layer, []).append(t)
            for layer, traces in per_layer.items():
                max_w = max((t.width_mm or 0.0) for t in traces) or 0.2
                cell = max(3.0 * max_w, 0.3)
                grid = {}
                segs = []
                for t in traces:
                    w = t.width_mm or 0.0
                    for s in t.segments:
                        a, b = (s[0], s[1]), (s[2], s[3])
                        x0, x1 = sorted((a[0], b[0]))
                        y0, y1 = sorted((a[1], b[1]))
                        ci0 = int((x0 - 3.0 * max_w) // cell)
                        ci1 = int((x1 + 3.0 * max_w) // cell)
                        cj0 = int((y0 - 3.0 * max_w) // cell)
                        cj1 = int((y1 + 3.0 * max_w) // cell)
                        for ci in range(ci0, ci1 + 1):
                            for cj in range(cj0, cj1 + 1):
                                grid.setdefault((ci, cj), []).append(len(segs))
                        segs.append((t.net_name, w, a, b))
                for i, (net, w, a, b) in enumerate(segs):
                    x0, x1 = sorted((a[0], b[0]))
                    y0, y1 = sorted((a[1], b[1]))
                    ci0 = int((x0 - 3.0 * max_w) // cell)
                    ci1 = int((x1 + 3.0 * max_w) // cell)
                    cj0 = int((y0 - 3.0 * max_w) // cell)
                    cj1 = int((y1 + 3.0 * max_w) // cell)
                    best = None
                    seen = set()
                    for ci in range(ci0, ci1 + 1):
                        for cj in range(cj0, cj1 + 1):
                            for j in grid.get((ci, cj), ()):
                                if j <= i or j in seen:
                                    continue
                                seen.add(j)
                                n2, w2, c, d = segs[j]
                                if n2 == net:
                                    continue
                                avgw = (w + w2) / 2.0
                                if avgw <= 0:
                                    continue
                                if (
                                    min(x1, max(c[0], d[0])) - max(x0, min(c[0], d[0])) > 3 * avgw
                                    or min(y1, max(c[1], d[1])) - max(y0, min(c[1], d[1])) > 3 * avgw
                                ):
                                    continue
                                dist = _seg_seg_dist(a, b, c, d)
                                r = dist / avgw
                                if r < 3.0 and (best is None or r < best):
                                    best = r
                                if r < 3.0:
                                    ov = _parallel_overlap(a, b, c, d)
                                    if ov > 0:
                                        key = (net, n2) if net < n2 else (n2, net)
                                        contested[key] = contested.get(key, 0.0) + ov
                    if best is not None:
                        ratios.append((net, round(best, 3)))
            m["crosstalk_nets_under_3w"] = len({n for n, _ in ratios})
            m["crosstalk_ratios_hist"] = {
                str(k): c
                for k, c in sorted(Counter(round(r, 1) for _, r in ratios).items())
            }
            # 只有「平行且近距离」的走线对才构成串扰；用重叠长度做门限
            m["crosstalk_netpairs"] = len(contested)
            m["crosstalk_contested_len_q"] = _quantiles(list(contested.values()))
            for cand in CROSSTALK_PARALLEL_CANDIDATES:
                m["crosstalk_pairs_gt_" + str(cand) + "mm"] = sum(
                    1 for v in contested.values() if v > cand
                )

    # ---- 走线拐角（内角）：必须先端点串联，直接取相邻两段是错的 ----
    #   统计口径完全复用 src/pcb/geometry.py（规则与实验同一套几何）。
    hist = Counter()                     # 5° 分桶 → 拐角数
    total_corners = 0
    judged_legs = []                     # 通过最小腿长门限的拐角，短腿侧长度
    acute_legs = []                      # 其中锐角(<89°)的短腿长度
    acute_by_cand = {str(a): 0 for a in ANGLE_ACUTE_CANDIDATES}
    acute_raw = 0                        # 不加最小腿长门限时的锐角数
    right_corners = 0
    for t in pcb.traces:
        for line in chain_segments(t.segments or ()):
            for c in polyline_corners(line, min_leg_mm=0.0):
                if c.angle_deg < 90.0:
                    acute_raw += 1
            for c in polyline_corners(line, min_leg_mm=PCB.TRACE_CORNER_MIN_LEG_MM):
                total_corners += 1
                hist[int(c.angle_deg // 5) * 5] += 1
                leg = min(c.leg_in_mm, c.leg_out_mm)
                judged_legs.append(leg)
                if c.angle_deg < 90.0:
                    acute_legs.append(round(leg, 4))
                for a in ANGLE_ACUTE_CANDIDATES:
                    if c.angle_deg < a:
                        acute_by_cand[str(a)] += 1
                if PCB.TRACE_RIGHT_ANGLE_MIN_DEG <= c.angle_deg <= PCB.TRACE_RIGHT_ANGLE_MAX_DEG:
                    right_corners += 1
    m["corner_total"] = total_corners
    m["corner_hist_5deg"] = {str(k): v for k, v in sorted(hist.items())}
    m["corner_acute_by_cand"] = acute_by_cand
    m["corner_acute_raw"] = acute_raw
    m["corner_right"] = right_corners
    m["corner_leg_min_q"] = _quantiles(judged_legs)
    m["corner_acute_leg_q"] = _quantiles(acute_legs) if acute_legs else {}

    return m


# ──────────────── 主流程 ────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="含 .epro2 的目录")
    ap.add_argument("--out", default="experiment_results/trace_threshold_calibration")
    ap.add_argument("--no-crosstalk", action="store_true")
    ap.add_argument("--max-segments", type=int, default=12000)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    root = Path(args.root)
    files = sorted(root.rglob("*.epro2"))
    if not files:
        print("未找到 .epro2: " + str(root))
        return 1

    parser = Epro2Parser()
    t0 = time.time()
    designs = []
    seen = {}
    errors = []
    for i, f in enumerate(files):
        try:
            pcb = parser.parse(str(f))
        except Exception as e:  # noqa: BLE001
            errors.append(f.name + ": " + str(e))
            continue
        fp = _fingerprint(pcb)
        if fp in seen:
            seen[fp]["dupes"].append(f.name)
            continue
        m = measure(pcb, not args.no_crosstalk, args.max_segments)
        m["fingerprint"] = fp
        m["file"] = f.name
        m["dupes"] = []
        seen[fp] = m
        designs.append(m)
        if args.limit and len(designs) >= args.limit:
            break
        if (i + 1) % 10 == 0:
            print("  ... " + str(i + 1) + "/" + str(len(files)), flush=True)

    elapsed = time.time() - t0
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "root": str(root),
        "files": len(files),
        "unique_designs": len(designs),
        "errors": errors,
        "elapsed_s": round(elapsed, 2),
        "designs": designs,
    }
    (outdir / "metrics.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    lines = render_report(designs, len(files), errors, elapsed)
    (outdir / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("")
    print("已写出: " + str(outdir / "metrics.json") + " / " + str(outdir / "report.txt"))
    return 0


def render_report(designs, nfiles, errors, elapsed) -> list:
    L = []
    add = L.append
    add("走线类规则阈值校准 — " + str(len(designs)) + " 个唯一设计（" + str(nfiles) + " 个文件）")
    add("耗时: " + str(round(elapsed, 1)) + "s   解析错误: " + str(len(errors)))
    add("")

    wpoly = Counter()
    wseg = Counter()
    for d in designs:
        for k, c in d.get("width_poly_top", {}).items():
            wpoly[float(k)] += c
        for k, c in d.get("width_seg_top", {}).items():
            wseg[float(k)] += c
    add("═══ 走线宽度（全局，按折线数）═══")
    for w, c in sorted(wpoly.items()):
        add("  " + ("%.4f" % w).rjust(8) + " mm  " + str(c).rjust(7) + " 折线")
    below = sum(c for w, c in wpoly.items() if w < FAB_MIN_WIDTH_MM - 1e-9)
    add("  合计 " + str(sum(wpoly.values())) + " 条有效折线；<" + str(FAB_MIN_WIDTH_MM) + "mm 的折线 " + str(below))
    add("")

    sig_min, pow_min = [], []
    for d in designs:
        sig_min.extend(d.get("signal_net_min_width", {}).values())
        pow_min.extend(d.get("power_net_min_width", {}).values())
    add("═══ 每网络最小线宽（mm）═══")
    add("  信号网络 n=" + str(len(sig_min)) + ": " + str(_quantiles(sig_min)))
    add("  电源网络 n=" + str(len(pow_min)) + ": " + str(_quantiles(pow_min)))
    add("  候选阈值 → 命中信号网络数 / 命中设计数")
    for c in WIDTH_CANDIDATES:
        nets = sum(d.get("sig_net_below_" + str(c), 0) for d in designs)
        ds = sum(1 for d in designs if d.get("sig_net_below_" + str(c), 0) > 0)
        add("    < " + ("%.3f" % c).rjust(6) + " mm : " + str(nets).rjust(5) + " 网络 / " + str(ds).rjust(3) + " 设计")
    add("")

    via_counts = []
    for d in designs:
        via_counts.extend(d.get("net_via_count", {}).values())
    doms = [d.get("dom_signal_width", 0) for d in designs if d.get("dom_signal_width")]
    add("═══ 本板信号线宽众数（上下文感知阈值基准）═══")
    add("  各板众数分布: " + str(_quantiles(doms)) + "  (n=" + str(len(doms)) + ")")
    add("  方案一（相对）：细于本板众数 x r 的网络数 / 设计数")
    for r in (0.4, 0.5, 0.6, 0.75):
        nets = sum(d.get("sig_below_rel_" + str(r), 0) for d in designs)
        ds = sum(1 for d in designs if d.get("sig_below_rel_" + str(r), 0) > 0)
        add("    < " + str(r) + " x 众数 : " + str(nets).rjust(5) + " 网络 / " + str(ds).rjust(3) + " 设计")
    add("  方案二（绝对硬下限）：细于 a mm 的网络数 / 设计数")
    for a in (0.08, 0.09, 0.10, 0.127):
        nets = sum(d.get("sig_below_abs_" + str(a), 0) for d in designs)
        ds = sum(1 for d in designs if d.get("sig_below_abs_" + str(a), 0) > 0)
        add("    < " + ("%.3f" % a) + " mm : " + str(nets).rjust(5) + " 网络 / " + str(ds).rjust(3) + " 设计")
    add("")

    add("═══ 每网络过孔数 ═══")
    add("  n=" + str(len(via_counts)) + ": " + str(_quantiles(via_counts)))
    add("  候选阈值 → 命中网络数 / 命中设计数（全部网络 / 高速网络 / 非电源网络）")
    for c in VIA_COUNT_CANDIDATES:
        nets = sum(d.get("nets_via_ge_" + str(c), 0) for d in designs)
        ds = sum(1 for d in designs if d.get("nets_via_ge_" + str(c), 0) > 0)
        hsn = sum(d.get("hs_nets_via_ge_" + str(c), 0) for d in designs)
        hsd = sum(1 for d in designs if d.get("hs_nets_via_ge_" + str(c), 0) > 0)
        sgn = sum(d.get("sig_nets_via_ge_" + str(c), 0) for d in designs)
        sgd = sum(1 for d in designs if d.get("sig_nets_via_ge_" + str(c), 0) > 0)
        add("    >= " + str(c).rjust(4) + " 个 : "
            + str(nets).rjust(5) + "/" + str(ds).rjust(3) + " 全部 | "
            + str(hsn).rjust(4) + "/" + str(hsd).rjust(3) + " 高速 | "
            + str(sgn).rjust(5) + "/" + str(sgd).rjust(3) + " 非电源")
    add("")

    edge = [c for d in designs for c in d.get("edge_clearances", [])]
    src = Counter(d.get("board_source") for d in designs)
    add("═══ 走线到板框距离 ═══")
    add("  板框来源: " + str(dict(src)) + "（仅 source=outline 的设计参与）")
    if edge:
        add("  n=" + str(len(edge)) + " 条折线: " + str(_quantiles(edge)))
        add("  候选阈值 → 命中折线数 / 命中设计数")
        for cand in EDGE_CANDIDATES:
            lines_ = sum(d.get("polylines_within_" + str(cand) + "mm", 0) for d in designs)
            ds = sum(1 for d in designs if d.get("polylines_within_" + str(cand) + "mm", 0) > 0)
            add("    < " + ("%.2f" % cand).rjust(4) + " mm : " + str(lines_).rjust(5) + " 折线 / " + str(ds).rjust(3) + " 设计")
    add("")

    add("═══ 差分对长度失配（mm）═══")
    for label, key, cand_key in (
        ("名字猜测配对", "diff_pair_len_mismatch", "diff_pairs_mismatch_gt_"),
        ("工程 NET 规则（ground truth，按组；1 组可含多条等长网络）", "dp_meta_mismatch", "dp_meta_mismatch_gt_"),
    ):
        diffs = [x for d in designs for x in d.get(key, [])]
        add("  [" + label + "] 识别到 " + str(len(diffs)) + " 项: "
            + (str(_quantiles(diffs)) if diffs else "—"))
        for cand in DIFF_LEN_CANDIDATES:
            nets = sum(d.get(cand_key + str(cand), 0) for d in designs)
            ds = sum(1 for d in designs if d.get(cand_key + str(cand), 0) > 0)
            add("    > " + ("%.3f" % cand).rjust(5) + " mm : " + str(nets).rjust(5) + " 项 / " + str(ds).rjust(3) + " 设计")
    gaps = [x for d in designs for x in d.get("dp_meta_gap_ratio", [])]
    add("  [ground truth] 对内最小间距/线宽 比值 n=" + str(len(gaps)) + ": " + (str(_quantiles(gaps)) if gaps else "—"))
    for cand in (3.0, 4.0, 6.0, 8.0, 10.0):
        nets = sum(1 for x in gaps if x > cand)
        add("    > " + ("%.1f" % cand).rjust(4) + " W : " + str(nets).rjust(5) + " 对")
    add("")

    clk = sum(len(d.get("clk_nets", [])) for d in designs)
    clk_ds = sum(1 for d in designs if d.get("clk_nets"))
    stub = sum(len(d.get("stub_nets", [])) for d in designs)
    stub_ds = sum(1 for d in designs if d.get("stub_nets"))
    add("═══ 时钟包地 / 短桩线 / 环路面积 ═══")
    add("  网络名含时钟关键词: " + str(clk) + " 个网络 / " + str(clk_ds) + " 设计")
    add("  高速网络含过孔(现 stub 规则必报): " + str(stub) + " 个网络 / " + str(stub_ds) + " 设计")
    hs_len = [v for d in designs for v in d.get("hs_net_len", {}).values()]
    add("  高速网络长度 n=" + str(len(hs_len)) + ": " + str(_quantiles(hs_len)))
    for cand in HS_LENGTH_CANDIDATES:
        nets = sum(d.get("hs_nets_len_gt_" + str(cand), 0) for d in designs)
        ds = sum(1 for d in designs if d.get("hs_nets_len_gt_" + str(cand), 0) > 0)
        add("    > " + ("%.1f" % cand).rjust(6) + " mm : " + str(nets).rjust(5) + " 网络 / " + str(ds).rjust(3) + " 设计")
    add("")

    if any("crosstalk_nets_under_3w" in d for d in designs):
        ns = [d["crosstalk_nets_under_3w"] for d in designs if "crosstalk_nets_under_3w" in d]
        skipped = sum(1 for d in designs if d.get("crosstalk_skipped"))
        add("═══ 3W 串扰（真实线段-线段最短距离 / 平均线宽 < 3）═══")
        add("  参与设计 " + str(len(ns)) + " 个（跳过 " + str(skipped) + "），每设计命中网络数: " + str(_quantiles(ns)))
        add("  有命中的设计: " + str(sum(1 for x in ns if x > 0)) + "/" + str(len(ns)))
        cl = [v for d in designs for v in d.get("crosstalk_contested_len_q", {}).values()]
        if cl:
            add("  平行重叠长度（mm）分布: " + str(_quantiles(cl)))
        add("  候选门限（平行重叠长度）→ 命中走线对数 / 命中设计数")
        for cand in CROSSTALK_PARALLEL_CANDIDATES:
            pairs = sum(d.get("crosstalk_pairs_gt_" + str(cand) + "mm", 0) for d in designs)
            ds = sum(1 for d in designs if d.get("crosstalk_pairs_gt_" + str(cand) + "mm", 0) > 0)
            add("    > " + ("%.1f" % cand).rjust(4) + " mm : " + str(pairs).rjust(6) + " 对 / " + str(ds).rjust(3) + " 设计")
        add("")
    else:
        add("═══ 3W 串扰：本次未计算 ═══")
        add("")

    # ── 走线拐角（内角）：串联折线后统计，用来校准锐角/直角阈值 ──
    hist = Counter()
    for d in designs:
        for k, c in d.get("corner_hist_5deg", {}).items():
            hist[int(k)] += c
    total = sum(hist.values())
    add("═══ 走线拐角（内角，端点串联后）═══")
    add("  参与设计 " + str(sum(1 for d in designs if d.get("corner_total"))) + " 个，拐角 "
        + str(total) + " 处；5° 分桶: " + str(dict(sorted(hist.items()))))
    add("  候选锐角阈值 → 命中拐角数 / 命中设计数（两侧腿均 ≥"
        + str(PCB.TRACE_CORNER_MIN_LEG_MM) + "mm）")
    for a in ANGLE_ACUTE_CANDIDATES:
        n = sum(d.get("corner_acute_by_cand", {}).get(str(a), 0) for d in designs)
        ds_ = sum(1 for d in designs if d.get("corner_acute_by_cand", {}).get(str(a), 0) > 0)
        add("    < " + ("%.1f°" % a).rjust(6) + " : " + str(n).rjust(6) + " 处 / "
            + str(ds_).rjust(3) + " 设计")
    rn = sum(d.get("corner_right", 0) for d in designs)
    rd = sum(1 for d in designs if d.get("corner_right", 0) > 0)
    add("    直角 " + ("%.0f~%.0f°" % (PCB.TRACE_RIGHT_ANGLE_MIN_DEG, PCB.TRACE_RIGHT_ANGLE_MAX_DEG))
        + " : " + str(rn).rjust(6) + " 处 / " + str(rd).rjust(3) + " 设计")
    rawn = sum(d.get("corner_acute_raw", 0) for d in designs)
    rawd = sum(1 for d in designs if d.get("corner_acute_raw", 0) > 0)
    add("  未加最小腿长门限时 <90° : " + str(rawn) + " 处 / " + str(rawd) + " 设计"
        "（差值即焊盘入口等退化短桩）")
    add("")

    if errors:
        add("═══ 解析错误 ═══")
        for e in errors:
            add("  " + e)
    return L


if __name__ == "__main__":
    raise SystemExit(main())

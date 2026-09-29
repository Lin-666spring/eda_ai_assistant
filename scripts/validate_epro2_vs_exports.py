"""用同一工程的立创官方导出（PickAndPlace / BOM / Netlist）交叉验证 .epro2 解析结果。

.epro2 理论上包含这四种导出的全部信息，所以这是一次真正的外部正确性验证，
而不是自证。

用法:
    python scripts/validate_epro2_vs_exports.py \
        --epro2 "test_data/_incoming_epro2/78/ProPrj_xxx.epro2" \
        --exports "test_data/thing_designs/xxx" \
        [--out report.txt]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pcb.epro2_parser import Epro2Parser  # noqa: E402

LINES: list[str] = []


def say(msg: str = "") -> None:
    LINES.append(msg)


# ──────────────── 导出文件读取 ────────────────

def read_pick_and_place(folder: Path) -> dict[str, dict]:
    """读取 PickAndPlace（csv 优先，其次 xlsx）→ {designator: {...}}"""
    csvs = sorted(folder.glob("PickAndPlace*.csv"))
    if csvs:
        with open(csvs[0], "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    else:
        xlsxs = sorted(folder.glob("PickAndPlace*.xlsx"))
        if not xlsxs:
            return {}
        import openpyxl

        ws = openpyxl.load_workbook(xlsxs[0], data_only=True).active
        it = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in next(it)]
        rows = [dict(zip(header, r)) for r in it]

    out = {}
    for r in rows:
        ref = str(r.get("Designator") or "").strip()
        if not ref:
            continue
        out[ref] = {
            "footprint": str(r.get("Footprint") or "").strip(),
            "x": _f(r.get("Mid X")),
            "y": _f(r.get("Mid Y")),
            "layer": str(r.get("Layer") or "").strip(),
            "rotation": _f(r.get("Rotation")),
        }
    return out


def read_bom(folder: Path) -> list[dict]:
    """读取 BOM xlsx → 行列表"""
    xlsxs = sorted(folder.glob("BOM*.xlsx"))
    if not xlsxs:
        return []
    import openpyxl

    ws = openpyxl.load_workbook(xlsxs[0], data_only=True).active
    it = ws.iter_rows(values_only=True)
    header = [str(c).strip() if c is not None else "" for c in next(it)]
    rows = []
    for r in it:
        d = {k: ("" if v is None else str(v).strip()) for k, v in zip(header, r)}
        if not d.get("Designator"):
            continue
        rows.append(d)
    return rows


def read_netlist(folder: Path) -> dict[str, set[str]]:
    """读取 .tel 的 $NETS 段 → {net: {REF.PIN}}"""
    tels = sorted(folder.glob("Netlist*.tel"))
    if not tels:
        return {}
    lines = Path(tels[0]).read_text(encoding="utf-8", errors="replace").splitlines()

    nets: dict[str, set[str]] = {}
    in_nets = False
    buf = ""
    for line in lines:
        s = line.strip()
        if s.startswith("$"):
            if s.upper().startswith("$NETS"):
                in_nets = True
                continue
            if in_nets:
                break
            continue
        if not in_nets or not s:
            continue
        if s.endswith(","):
            buf += s[:-1] + " "
            continue
        buf += s
        m = re.match(r"^'?([^';]*)'?\s*;\s*(.*)$", buf)
        if m:
            name = m.group(1).strip()
            pins = set(m.group(2).split())
            if name:
                nets[name] = pins
        buf = ""
    return nets


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ──────────────── 各项比对 ────────────────

def cmp_components(pcb, pnp: dict) -> None:
    say("=" * 72)
    say("A. 元件：.epro2 vs PickAndPlace")
    say("=" * 72)
    e = {k: v for k, v in pcb.component_positions.items()}
    say(f".epro2 位号数 : {len(e)}")
    say(f"PickAndPlace  : {len(pnp)}")

    only_e = sorted(set(e) - set(pnp))
    only_p = sorted(set(pnp) - set(e))
    common = sorted(set(e) & set(pnp))
    say(f"交集 {len(common)} | 仅 .epro2 {len(only_e)} | 仅导出 {len(only_p)}")
    if only_e:
        say(f"  仅 .epro2: {only_e[:15]}")
    if only_p:
        say(f"  仅导出  : {only_p[:15]}")

    if not common:
        return

    # 层
    layer_mismatch = [
        r for r in common
        if (e[r].get("side") or "").upper() != (pnp[r].get("layer") or "").upper()
        and (pnp[r].get("layer") or "")
    ]
    say(f"层一致: {len(common) - len(layer_mismatch)}/{len(common)}"
        f" (不一致 {len(layer_mismatch)})")
    if layer_mismatch:
        for r in layer_mismatch[:5]:
            say(f"    {r}: epro2={e[r].get('side')} 导出={pnp[r].get('layer')}")

    # 坐标：试 4 种变换，找最佳
    best = None
    for name, fy in (("原样", 1.0), ("Y翻转", -1.0)):
        for dx_key in ("none", "median"):
            dxs = [e[r]["x"] - pnp[r]["x"] for r in common]
            dys = [e[r]["y"] - fy * pnp[r]["y"] for r in common]
            ox = sorted(dxs)[len(dxs) // 2] if dx_key == "median" else 0.0
            oy = sorted(dys)[len(dys) // 2] if dx_key == "median" else 0.0
            errs = [
                max(abs(dxs[i] - ox), abs(dys[i] - oy)) for i in range(len(common))
            ]
            errs.sort()
            med = errs[len(errs) // 2]
            p95 = errs[int(len(errs) * 0.95)]
            if best is None or med < best[0]:
                best = (med, p95, name, dx_key, ox, oy, fy)
    med, p95, name, dx_key, ox, oy, fy = best
    say(f"坐标最佳变换: {name} + 平移补偿({dx_key}) → 中位误差 {med:.4f}mm, P95 {p95:.4f}mm")
    say(f"  偏移 dx={ox:.4f} dy={oy:.4f} (dy 含翻转系数 {fy})")
    within = sum(
        1 for r in common
        if abs(e[r]["x"] - pnp[r]["x"] - ox) <= 0.05
        and abs(e[r]["y"] - fy * pnp[r]["y"] - oy) <= 0.05
    )
    say(f"  误差 ≤0.05mm 的比例: {within}/{len(common)} ({within / len(common) * 100:.1f}%)")

    # 旋转
    rot_ok = 0
    rot_samples = []
    for r in common:
        a, b = e[r].get("rotation"), pnp[r].get("rotation")
        if a is None:
            continue
        d = (float(a) - float(b)) % 360
        if min(d, 360 - d) <= 0.5:
            rot_ok += 1
        elif len(rot_samples) < 5:
            rot_samples.append((r, a, b))
    say(f"旋转一致: {rot_ok}/{len(common)}")
    for r, a, b in rot_samples:
        say(f"    {r}: epro2={a} 导出={b}")


def cmp_bom(pcb, bom_rows: list[dict]) -> None:
    say("")
    say("=" * 72)
    say("B. BOM：.epro2 重建 vs 官方 BOM xlsx")
    say("=" * 72)
    e = pcb.bom_items
    say(f".epro2 BOM 行: {len(e)} | 导出 BOM 行: {len(bom_rows)}")

    def refs(s: str) -> set[str]:
        return {x.strip() for x in re.split(r"[,，]", s or "") if x.strip()}

    e_refs = set()
    for row in e:
        e_refs |= refs(row["reference"])
    p_refs = set()
    for row in bom_rows:
        p_refs |= refs(row.get("Designator", ""))
    say(f"BOM 覆盖位号: .epro2 {len(e_refs)} | 导出 {len(p_refs)}")
    say(f"  交集 {len(e_refs & p_refs)} | 仅 .epro2 {len(e_refs - p_refs)} "
        f"| 仅导出 {len(p_refs - e_refs)}")
    if e_refs - p_refs:
        say(f"  仅 .epro2: {sorted(e_refs - p_refs)[:15]}")
    if p_refs - e_refs:
        say(f"  仅导出  : {sorted(p_refs - e_refs)[:15]}")

    # 逐器件比对：以 (Manufacturer Part, Value) 为键；Footprint 单独核对，
    # 因为官方 BOM 的 Footprint 列是立创封装名（= FOOTPRINT 文档 title）
    def key(part, value):
        return (part.strip(), value.strip())

    e_map: dict[tuple, set[str]] = {}
    e_pkg: dict[tuple, set[str]] = {}
    for row in e:
        k = key(row["part_number"], row["value"])
        e_map.setdefault(k, set()).update(refs(row["reference"]))
        e_pkg.setdefault(k, set()).add(row["package"])
    p_map: dict[tuple, set[str]] = {}
    p_pkg: dict[tuple, set[str]] = {}
    for row in bom_rows:
        k = key(row.get("Manufacturer Part", ""), row.get("Value", ""))
        p_map.setdefault(k, set()).update(refs(row.get("Designator", "")))
        p_pkg.setdefault(k, set()).add(row.get("Footprint", ""))

    both = set(e_map) & set(p_map)
    say(f"器件组合(型号+值) 交集 {len(both)} | 仅 .epro2 {len(set(e_map) - set(p_map))} "
        f"| 仅导出 {len(set(p_map) - set(e_map))}")
    exact = sum(1 for k in both if e_map[k] == p_map[k])
    pkg_ok = sum(1 for k in both if e_pkg[k] & p_pkg[k])
    say(f"位号集合完全一致的器件组: {exact}/{len(both)} "
        f"({exact / max(1, len(both)) * 100:.1f}%)")
    say(f"封装名有交集的器件组: {pkg_ok}/{len(both)}")
    for k in sorted(both)[:6]:
        ok = "OK " if e_map[k] == p_map[k] else "DIFF"
        say(f"    [{ok}] {k[0] or '(无型号)'} {k[1]}: epro2 {len(e_map[k])} 位号, "
            f"导出 {len(p_map[k])} 位号 | 封装 epro2={sorted(e_pkg[k])[:2]} "
            f"导出={sorted(p_pkg[k])[:2]}")
    diff_keys = [k for k in sorted(both) if e_map[k] != p_map[k]]
    for k in diff_keys[:5]:
        say(f"    [差异明细] {k[0]} {k[1]}: 仅 .epro2 {sorted(e_map[k] - p_map[k])[:8]} "
            f"| 仅导出 {sorted(p_map[k] - e_map[k])[:8]}")
    if e_refs - p_refs:
        say(f"  注: .epro2 多出的 {len(e_refs - p_refs)} 个位号在 PickAndPlace 中存在，"
            f"但官方 BOM xlsx 未收录（立创 BOM 导出侧的筛选，非解析缺失）")


def cmp_nets(pcb, tel_nets: dict[str, set[str]]) -> None:
    say("")
    say("=" * 72)
    say("C. 网络：.epro2 (PCB PAD_NET) vs 官方 Netlist (原理图 $NETS)")
    say("=" * 72)
    e_nets = {k: set(v.pins) for k, v in pcb.nets.items() if v.pins}
    say(f".epro2 有引脚的网络: {len(e_nets)} / 总网络 {pcb.net_count}")
    say(f"导出网表网络: {len(tel_nets)}")

    both = set(e_nets) & set(tel_nets)
    say(f"同名网络: {len(both)}")
    if not both:
        say("  (网络命名口径不同，无可比项)")
        return

    identical = 0
    jaccards = []
    for n in both:
        a, b = e_nets[n], tel_nets[n]
        if a == b:
            identical += 1
        j = len(a & b) / max(1, len(a | b))
        jaccards.append(j)
    jaccards.sort()
    say(f"引脚集合完全一致: {identical}/{len(both)} "
        f"({identical / len(both) * 100:.1f}%)")
    say(f"Jaccard 中位数 {jaccards[len(jaccards) // 2]:.3f} | "
        f"P10 {jaccards[len(jaccards) // 10]:.3f} | P90 {jaccards[int(len(jaccards) * 0.9)]:.3f}")

    # 展示几个差异样例
    shown = 0
    for n in sorted(both):
        if e_nets[n] != tel_nets[n] and shown < 5:
            say(f"    [{n}] 仅 .epro2: {sorted(e_nets[n] - tel_nets[n])[:6]} | "
                f"仅网表: {sorted(tel_nets[n] - e_nets[n])[:6]}")
            shown += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epro2", required=True)
    ap.add_argument("--exports", required=True, help="含 PickAndPlace/BOM/Netlist 的目录")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    epath = Path(args.epro2)
    folder = Path(args.exports)

    pcb = Epro2Parser().parse(str(epath))
    say(f".epro2 : {epath.name}")
    say(f"导出目录: {folder}")
    say(f"工程名  : {pcb.metadata.get('title')} (editor {pcb.metadata.get('editor_version')})")
    say(f"单位    : {pcb.metadata.get('unit')} → mm 系数 {pcb.metadata.get('scale_to_mm')}")
    say(f"元素    : LINE {pcb.metadata.get('line_elements')} → 折线 {pcb.trace_count}, "
        f"VIA {pcb.via_count}, POUR {len(pcb.copper_pours)}, "
        f"NET {pcb.metadata.get('net_elements')}, PAD_NET {pcb.metadata.get('pad_nets')}")
    say(f"板框    : {pcb.board_outline.get('width_mm')} x {pcb.board_outline.get('height_mm')} mm")
    say("")

    cmp_components(pcb, read_pick_and_place(folder))
    cmp_bom(pcb, read_bom(folder))
    cmp_nets(pcb, read_netlist(folder))

    text = "\n".join(LINES)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"\n[wrote {args.out}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

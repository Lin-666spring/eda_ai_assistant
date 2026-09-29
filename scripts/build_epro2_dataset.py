"""用 Epro2Parser 批量解析 .epro2 工程，产出数据集清单与统计。

用法:
    python scripts/build_epro2_dataset.py <目录> [--out experiment_results/epro2_dataset]

产物:
    manifest.json  每个工程的完整统计（含设计指纹）
    manifest.csv   便于人工查看的表格
    summary.txt    汇总报告
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pcb.epro2_parser import Epro2Parser  # noqa: E402


def design_fingerprint(pcb) -> str:
    """设计指纹：位号+封装名+网络名+板框尺寸 —— 用于识别重复工程"""
    refs = sorted(
        f"{ref}:{v.get('footprint_name','')}" for ref, v in pcb.component_positions.items()
    )
    nets = sorted(pcb.nets)
    outline = pcb.board_outline
    payload = "|".join([
        ",".join(refs),
        ",".join(nets),
        f"{outline.get('width_mm')}x{outline.get('height_mm')}",
    ])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]


def summarize(pcb) -> dict:
    nets_with_pins = sum(1 for n in pcb.nets.values() if n.pins)
    total_pins = sum(len(n.pins) for n in pcb.nets.values())
    return {
        "title": pcb.metadata.get("title"),
        "editor_version": pcb.metadata.get("editor_version"),
        "unit": pcb.metadata.get("unit"),
        "scale_to_mm": pcb.metadata.get("scale_to_mm"),
        "board_w_mm": pcb.board_outline.get("width_mm"),
        "board_h_mm": pcb.board_outline.get("height_mm"),
        "board_source": pcb.board_outline.get("source"),
        "layers": len(pcb.layers),
        "layer_names": pcb.layers,
        "nets": pcb.net_count,
        "nets_with_pins": nets_with_pins,
        "total_pins": total_pins,
        "trace_polylines": pcb.trace_count,
        "line_elements": pcb.metadata.get("line_elements"),
        "vias": pcb.via_count,
        "pours": len(pcb.copper_pours),
        "components": len(pcb.component_positions),
        "bom_rows": len(pcb.bom_items),
        "bom_refs": sum(r["quantity"] for r in pcb.bom_items),
        "pad_nets": pcb.metadata.get("pad_nets"),
        "orphan_pad_nets": pcb.metadata.get("orphan_pad_nets"),
        "footprint_docs": pcb.metadata.get("footprint_docs"),
        "pads_in_footprints": pcb.metadata.get("pads_in_footprints"),
        "differential_pairs": len(pcb.differential_pairs),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", default="experiment_results/epro2_dataset")
    args = ap.parse_args()

    root = Path(args.path)
    files = sorted(root.rglob("*.epro2")) if root.is_dir() else [root]
    parser = Epro2Parser()

    rows = []
    failures = []
    for i, f in enumerate(files, 1):
        t0 = time.perf_counter()
        try:
            pcb = parser.parse(str(f))
        except Exception as e:  # noqa: BLE001
            failures.append({"file": f.name, "error": f"{type(e).__name__}: {e}"})
            print(f"[{i}/{len(files)}] FAIL {f.name}: {e}", flush=True)
            continue
        dt = time.perf_counter() - t0
        row = summarize(pcb)
        row["file"] = f.name
        row["size_kb"] = round(f.stat().st_size / 1024, 1)
        row["parse_s"] = round(dt, 2)
        row["fingerprint"] = design_fingerprint(pcb)
        rows.append(row)
        print(
            f"[{i}/{len(files)}] {row['title'][:30] if row['title'] else f.stem[:30]:30s} "
            f"{dt:5.2f}s nets={row['nets']:5d} pins={row['total_pins']:6d} "
            f"tr={row['trace_polylines']:5d} via={row['vias']:5d} "
            f"comp={row['components']:5d} bom={row['bom_rows']:4d} "
            f"board={row['board_w_mm']}x{row['board_h_mm']}mm",
            flush=True,
        )

    # 设计去重
    by_fp: dict[str, list[str]] = {}
    for r in rows:
        by_fp.setdefault(r["fingerprint"], []).append(r["file"])
    dup_groups = {k: v for k, v in by_fp.items() if len(v) > 1}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps({
        "source_dir": str(root),
        "files": len(files),
        "parsed": len(rows),
        "failed": failures,
        "unique_designs": len(by_fp),
        "duplicate_groups": dup_groups,
        "designs": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    cols = [
        "title", "file", "size_kb", "parse_s", "board_w_mm", "board_h_mm", "layers",
        "nets", "nets_with_pins", "total_pins", "trace_polylines", "line_elements",
        "vias", "pours", "components", "bom_rows", "bom_refs", "pad_nets",
        "orphan_pad_nets", "fingerprint",
    ]
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    def tot(k):
        return sum(r[k] or 0 for r in rows)

    lines = [
        f"源目录: {root}",
        f"文件数: {len(files)}  解析成功: {len(rows)}  失败: {len(failures)}",
        f"唯一设计（指纹去重）: {len(by_fp)}",
        f"重复设计组: {len(dup_groups)}",
    ]
    for fp, fs in dup_groups.items():
        lines.append(f"   {fp}: {fs}")
    lines += [
        "",
        f"网络合计: {tot('nets')}   有引脚的网络: {tot('nets_with_pins')}",
        f"引脚合计: {tot('total_pins')}",
        f"走线折线: {tot('trace_polylines')}   LINE 元素: {tot('line_elements')}",
        f"过孔: {tot('vias')}   覆铜: {tot('pours')}",
        f"元件: {tot('components')}   BOM 行: {tot('bom_rows')}   BOM 位号: {tot('bom_refs')}",
        f"PAD_NET: {tot('pad_nets')}   孤儿 PAD_NET: {tot('orphan_pad_nets')}",
        f"解析总耗时: {sum(r['parse_s'] for r in rows):.1f}s "
        f"(平均 {sum(r['parse_s'] for r in rows) / max(1, len(rows)):.2f}s/工程)",
    ]
    text = "\n".join(lines)
    (out / "summary.txt").write_text(text, encoding="utf-8")
    print("\n" + text)
    print(f"\nwrote {out}/manifest.json, manifest.csv, summary.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

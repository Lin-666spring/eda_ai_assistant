"""批量扫描 .epro2 工程 — 统计各工程文档类型与 PCB 元素，输出清单 + 解析设计所需的样例。

用法:
    python scripts/scan_epro2_batch.py <目录或文件...> [--out 输出json] [--samples 输出样例json]

设计要点（性能）：
- .epru 是 JSON Lines，元信息形如 {"type":"LINE","ticket":N,"id":"..."}
- 逐行流式读取，先用正则取 meta.type，只对关心的元素做 json.loads
- 统计 DOCHEAD 决定当前文档类型，PCB 元素只在 docType == PCB 时计数
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

TYPE_RE = re.compile(r'^\{"type":"([A-Za-z0-9_]+)"')

# 需要反序列化 atom 的元素类型（其余只计数）
ATOM_TYPES = {
    "DOCHEAD", "LAYER", "NET", "LINE", "VIA", "PAD", "PAD_NET", "POUR",
    "COMPONENT", "ATTR", "PART", "POLYGON", "FILL", "REGION", "RULE",
}

# 每个类型最多保留的样例数
MAX_SAMPLES = 3


def _meta_type(meta_s: str):
    """返回 (type, 是否回退到 json.loads)"""
    m = TYPE_RE.match(meta_s)
    if m:
        return m.group(1), False
    try:
        return json.loads(meta_s).get("type"), True
    except Exception:
        return None, True


def scan_file(path: Path) -> dict:
    info = {
        "file": str(path),
        "name": path.stem,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "md5": hashlib.md5(path.read_bytes()).hexdigest(),
        "ok": False,
        "error": None,
        "project2": {},
        "epru": None,
        "doctypes": {},
        "pcb": {},
        "types": {},
    }

    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        info["error"] = f"BadZipFile: {e}"
        return info

    with zf:
        names = zf.namelist()
        info["entries"] = len(names)
        epru_names = [n for n in names if n.endswith(".epru")]
        info["has_project2"] = "project2.json" in names
        if not epru_names:
            info["error"] = "no .epru entry"
            return info
        if len(epru_names) > 1:
            info["error"] = f"multiple .epru: {epru_names}"
        epru = epru_names[0]
        info["epru"] = epru
        info["epru_mb"] = round(zf.getinfo(epru).file_size / 1048576, 2)

        if info["has_project2"]:
            try:
                pj = json.loads(zf.read("project2.json").decode("utf-8"))
                info["project2"] = {
                    k: pj.get(k) for k in ("title", "editorVersion", "cbb_project", "tags")
                }
            except Exception as e:  # noqa: BLE001
                info["error"] = f"project2.json: {e}"

        doctypes = Counter()
        types = Counter()
        samples: dict[str, list] = defaultdict(list)
        fallback = 0
        bad_lines = 0
        linecount = 0

        cur_doc = None
        pc = Counter()
        layers = []

        with zf.open(epru) as fh:
            for raw_line in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
                linecount += 1
                s = raw_line.strip()
                if not s:
                    continue
                sep = s.find("||")
                if sep < 0:
                    bad_lines += 1
                    continue
                meta_s = s[:sep]
                atom_s = s[sep + 2:].rstrip("|")

                t, used_fallback = _meta_type(meta_s)
                if used_fallback:
                    fallback += 1
                if not t:
                    bad_lines += 1
                    continue

                types[t] += 1

                if t not in ATOM_TYPES:
                    continue
                try:
                    atom = json.loads(atom_s)
                except Exception:
                    bad_lines += 1
                    continue

                if t == "DOCHEAD":
                    cur_doc = atom.get("docType")
                    doctypes[cur_doc] += 1
                    if len(samples["DOCHEAD"]) < MAX_SAMPLES:
                        samples["DOCHEAD"].append(atom)
                    continue

                if len(samples[t]) < MAX_SAMPLES:
                    samples[t].append({"doc": cur_doc, "atom": atom})

                if cur_doc != "PCB":
                    continue

                if t == "LAYER":
                    layers.append((atom.get("layerType"), atom.get("layerName")))
                elif t == "NET":
                    pc["nets"] += 1
                elif t == "LINE":
                    pc["line_total"] += 1
                    if atom.get("netName"):
                        pc["line_net"] += 1
                elif t == "VIA":
                    pc["vias"] += 1
                elif t == "PAD":
                    pc["pads"] += 1
                elif t == "PAD_NET":
                    pc["pad_net"] += 1
                elif t == "POUR":
                    pc["pours"] += 1
                elif t == "COMPONENT":
                    pc["components"] += 1
                elif t == "ATTR":
                    pc["attrs"] += 1

        info["ok"] = True
        info["lines"] = linecount
        info["fallback_meta"] = fallback
        info["bad_lines"] = bad_lines
        info["doctypes"] = dict(doctypes.most_common())
        info["types"] = dict(types.most_common(60))
        info["pcb"] = dict(pc)
        info["pcb_layers"] = layers
        info["_samples"] = {k: v for k, v in samples.items()}

    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--out", default="experiment_results/epro2_scan/manifest.json")
    ap.add_argument("--samples", default="experiment_results/epro2_scan/samples.json")
    args = ap.parse_args()

    targets: list[Path] = []
    for p in args.paths:
        pp = Path(p)
        if pp.is_dir():
            targets.extend(sorted(pp.rglob("*.epro2")))
        else:
            targets.append(pp)
    if not targets:
        print("no .epro2 found", file=sys.stderr)
        return 2

    results = []
    all_samples: dict[str, list] = defaultdict(list)
    global_types = Counter()
    for i, t in enumerate(targets, 1):
        r = scan_file(t)
        samples = r.pop("_samples", {})
        for k, v in samples.items():
            if len(all_samples[k]) < MAX_SAMPLES * 3:
                all_samples[k].extend(v)
        for k, v in (r.get("types") or {}).items():
            global_types[k] += v
        results.append(r)
        flag = "OK " if r["ok"] else "ERR"
        pcb = r.get("pcb") or {}
        print(
            f"[{i}/{len(targets)}] {flag} {r['name'][:46]:46s} "
            f"nets={pcb.get('nets', 0):5d} line={pcb.get('line_net', 0):6d} "
            f"via={pcb.get('vias', 0):5d} pads={pcb.get('pads', 0):5d} "
            f"comp={pcb.get('components', 0):5d} {r.get('error') or ''}",
            flush=True,
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "count": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "global_types": dict(global_types.most_common(120)),
        "files": results,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    sp = Path(args.samples)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(all_samples, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nwrote {out} and {sp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

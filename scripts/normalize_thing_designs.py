#!/usr/bin/env python
"""Normalize the incoming 'thing' batch into test_data/thing_designs/.

- Drops duplicate designs (same BOM fingerprint), keeping the lowest folder index.
- Derives a human-readable, filesystem-safe design name from the most
  informative token among BOM / PickAndPlace / Netlist filenames.
- Copies BOM + PickAndPlace + Netlist into test_data/thing_designs/<name>/.
- Writes a manifest CSV for traceability.
"""
from __future__ import annotations
import csv, json, re, shutil, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "test_data" / "_incoming_thing" / "thing"
DST = ROOT / "test_data" / "thing_designs"

GENERIC = {
    "bom", "board", "board1", "board1_1", "schematic", "schematic1", "schematic1_1",
    "sch", "pcb", "pcb1", "pcb1_1", "pcb2", "pcb17", "1", "1_1", "v1", "v1_0_2",
    "flyingprobetesting", "netlist", "pickandplace",
}
DATE_RE = re.compile(r"20\d{2}[-_]?\d{2}[-_]?\d{2}")


def tokens(name: str):
    stem = Path(name).stem
    stem = DATE_RE.sub("", stem)
    parts = re.split(r"[_\-\s]+", stem)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.lower() in GENERIC:
            continue
        if re.fullmatch(r"[0-9_]+", p):
            continue
        out.append(p)
    return out


def candidate_name(bom: str, pnp: str, net: str, idx: int) -> str:
    all_tokens = []
    for f in (bom, pnp, net):
        for t in tokens(f):
            all_tokens.append(t)
    # Prefer tokens with CJK content; then longest.
    cjk = [t for t in all_tokens if any("\u4e00" <= ch <= "\u9fff" for ch in t)]
    pool = cjk or all_tokens
    if pool:
        best = max(pool, key=len)
    else:
        best = f"design{idx:03d}"
    best = unicodedata.normalize("NFKC", best)
    best = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", best).strip(" .")
    return best or f"design{idx:03d}"


def safe_unique(base: str, used: set) -> str:
    name = base
    n = 2
    while name in used:
        name = f"{base}_{n}"
        n += 1
    used.add(name)
    return name


def main():
    inventory = json.loads((ROOT / "test_data" / "_incoming_thing" / "inventory.json").read_text(encoding="utf-8"))
    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    seen_fp = {}
    used_names = set()
    manifest = []
    for r in sorted(inventory, key=lambda x: x["idx"]):
        fp = r.get("fingerprint")
        if fp and fp in seen_fp:
            print(f"  dup  {r['idx']:>3} -> keep {seen_fp[fp]}")
            continue
        if fp:
            seen_fp[fp] = r["idx"]

        folder = SRC / str(r["idx"])
        base = candidate_name(r["bom"], r["pnp"], r["netlist"], r["idx"])
        name = safe_unique(base, used_names)
        outdir = DST / name
        outdir.mkdir(parents=True, exist_ok=True)

        copies = []
        for fname in (r["bom"], r["pnp"], r["netlist"]):
            if not fname:
                continue
            src = folder / fname
            if src.exists():
                shutil.copy2(src, outdir / fname)
                copies.append(fname)
        manifest.append({
            "src_index": r["idx"],
            "design": name,
            "components": r.get("components"),
            "fingerprint": fp,
            "files": "; ".join(copies),
        })

    with (DST / "_manifest.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["src_index", "design", "components", "fingerprint", "files"])
        w.writeheader()
        w.writerows(manifest)

    print(f"unique designs written: {len(manifest)} -> {DST}")
    comps = [m["components"] or 0 for m in manifest]
    print(f"components min/median/max: {min(comps)}/{sorted(comps)[len(comps)//2]}/{max(comps)}")


if __name__ == "__main__":
    main()

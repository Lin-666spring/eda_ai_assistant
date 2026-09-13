#!/usr/bin/env python
"""Inventory the incoming 'thing' PCB design batch (91 folders)."""
from __future__ import annotations
import json, hashlib, sys
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "test_data" / "_incoming_thing" / "thing"

def find(folder: Path, prefix: str):
    for f in sorted(folder.iterdir()):
        if f.name.lower().startswith(prefix):
            return f
    return None

def bom_info(p: Path):
    try:
        df = pd.read_excel(p, dtype=str, engine="openpyxl").fillna("")
        cols = [c for c in df.columns]
        # find designator column heuristically
        des_col = next((c for c in cols if "design" in str(c).lower() or str(c).lower() in ("designator","位号","reference","ref")), None)
        com_col = next((c for c in cols if str(c).lower() in ("comment","器件","名称","value","值")), None)
        n = 0
        sig_parts = []
        if des_col:
            for _, row in df.iterrows():
                d = str(row.get(des_col, "")).strip()
                if d and d.lower() not in ("nan",""):
                    n += 1
                    sig_parts.append(d + "|" + str(row.get(com_col, "") if com_col else "").strip())
        sig = hashlib.md5("\n".join(sorted(sig_parts)).encode("utf-8")).hexdigest()[:10] if sig_parts else None
        return {"rows": len(df), "components": n, "columns": cols, "fingerprint": sig}
    except Exception as e:
        return {"error": str(e)}

rows = []
for folder in sorted(BASE.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 9999):
    if not folder.is_dir():
        continue
    bom = find(folder, "bom")
    pnp = find(folder, "pickandplace")
    net = find(folder, "netlist")
    info = bom_info(bom) if bom else {}
    # candidate design name from bom filename: BOM_<name>_..._<date>.xlsx
    stem = bom.stem if bom else folder.name
    parts = stem.split("_")
    cand = parts[1] if len(parts) > 2 else stem
    rows.append({
        "idx": int(folder.name) if folder.name.isdigit() else folder.name,
        "design_candidate": cand,
        "bom": bom.name if bom else None,
        "pnp": pnp.name if pnp else None,
        "netlist": net.name if net else None,
        **info,
    })

out = Path(__file__).resolve().parent.parent / "test_data" / "_incoming_thing" / "inventory.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

# duplicate fingerprints
from collections import Counter
fps = Counter(r.get("fingerprint") for r in rows if r.get("fingerprint"))
dups = {k: v for k, v in fps.items() if v > 1}
print("total folders:", len(rows))
print("components: min/median/max =", min(r.get("components",0) for r in rows), sorted(r.get("components",0) for r in rows)[len(rows)//2], max(r.get("components",0) for r in rows))
print("unique BOM fingerprints:", len(fps), "| duplicate groups:", len(dups), "| folders in dup groups:", sum(dups.values()))
print("sample:")
for r in rows[:8]:
    print(f"  {r['idx']:>3} {str(r.get('components')):>4}c  {str(r.get('design_candidate'))[:28]:<28} {r.get('bom')}")
print("...")
for r in rows[-4:]:
    print(f"  {r['idx']:>3} {str(r.get('components')):>4}c  {str(r.get('design_candidate'))[:28]:<28} {r.get('bom')}")

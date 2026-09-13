"""Compact progress reporter for a running EI experiment output dir."""
import json, sys
from pathlib import Path

p = Path(sys.argv[1] if len(sys.argv) > 1 else "experiment_results/run_thing_full_glm53")
f = p / "results.json"
if not f.exists():
    print("no results.json yet:", f); sys.exit(0)
try:
    d = json.loads(f.read_text(encoding="utf-8"))
except Exception as e:
    print("parse error:", e); sys.exit(0)

nd = len(d.get("designs", []))
vr = d.get("verify_results", [])
ma = d.get("ma_results", [])
dr = d.get("drc_results", [])
errs = [r for r in vr if r.get("error")]
print(f"designs={nd} | DRC={len(dr)}/{nd} | verify={len(vr)}/{nd*5} (err={len(errs)}) | multiagent={len(ma)}/{nd}")
u = d.get("llm_usage") or {}
if u:
    print(f"GLM usage: calls={u.get('calls')} prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')} total={u.get('total_tokens')}")
if vr:
    print("last: %s %s accepted=%s converged=%s changes=%s rounds=%s" % (
        vr[-1].get("design"), vr[-1].get("suggestion_category"),
        vr[-1].get("accepted"), vr[-1].get("converged"),
        vr[-1].get("suggested_changes_count"), vr[-1].get("rounds")))
if errs:
    print("errors:", [(e.get("design"), str(e.get("error"))[:80]) for e in errs[:3]])

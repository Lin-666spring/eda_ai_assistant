"""Watchdog: poll the running experiment's results.json; exit on error or completion.

Writes a compact timestamped line to logs/thing_watch.log every cycle.
Exits 2 if any verify error appears (e.g. insufficient balance), 0 if the run completes.
"""
import json, sys, time
from datetime import datetime
from pathlib import Path

p = Path("experiment_results/run_thing_full_glm53/results.json")
log = Path("logs/thing_watch.log")
log.parent.mkdir(parents=True, exist_ok=True)
ND = 79

def line(msg):
    s = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(s, flush=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(s + "\n")

last = None
for i in range(2000):  # ~50h max at 90s
    time.sleep(90)
    if not p.exists():
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    vr = d.get("verify_results", [])
    ma = d.get("ma_results", [])
    errs = [r for r in vr if r.get("error")]
    u = d.get("llm_usage") or {}
    cur = (len(vr), len(ma), len(errs), u.get("total_tokens"))
    if cur != last:
        line(f"verify={len(vr)}/{ND*5} ma={len(ma)}/{ND} err={len(errs)} tokens={u.get('total_tokens')} calls={u.get('calls')}")
        last = cur
    if errs:
        line("ALERT: verify errors present -> " + str([(e.get('design'), str(e.get('error'))[:90]) for e in errs[:3]]))
        sys.exit(2)
    if len(vr) >= ND*5 and len(ma) >= ND:
        line("DONE: all phases complete")
        sys.exit(0)

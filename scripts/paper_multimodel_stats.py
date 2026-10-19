# -*- coding: utf-8 -*-
"""多模型子集统计 —— 分模型收敛率/撤销率/轮次/零变更回应/bootstrap CI 对比表。

输入: experiment_results/mm20_<provider>_*/results.json（两模型同子集）
输出: 论文/review/multimodel_stats.json + 控制台对比表
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "论文/review/multimodel_stats.json"


def rounds_of(r):
    return (r.get("raw_report") or {}).get("rounds") or []


def analyze(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    V = d["verify_results"]
    designs = sorted(set(r["design"] for r in V))
    proposed = [r for r in V if (r.get("suggested_changes_count") or 0) > 0]
    zero_resp = [r for r in V if r.get("suggestion_category", "safe") != "safe"
                 and (r.get("suggested_changes_count") or 0) == 0]
    conv = [r for r in proposed if r.get("converged")]
    reverted = [r for r in conv if r.get("fully_reverted")]
    fixkeep = [r for r in conv if not r.get("fully_reverted")]
    nonconv = [r for r in proposed if not r.get("converged")]
    hosts = []
    for r in V:
        rr = rounds_of(r)
        if rr and rr[0].get("blocking_new", 0) > 0:
            hosts.append(r)
    parse_fail = sum(1 for r in zero_resp if not r.get("accepted"))
    # bootstrap CI（按板聚类）
    random.seed(42)
    by = {g: [((r.get("suggested_changes_count") or 0) > 0, bool(r.get("converged")))
              for r in V if r["design"] == g] for g in designs}
    lo = hi = None
    if proposed:
        rates = []
        for _ in range(2000):
            s = random.choices(designs, k=len(designs))
            p = c = 0
            for g in s:
                for isp, isc in by[g]:
                    if isp:
                        p += 1
                        c += 1 if isc else 0
            if p:
                rates.append(c / p)
        rates.sort()
        lo, hi = round(rates[100] * 100, 1), round(rates[1899] * 100, 1)
    cats = Counter(r["suggestion_category"] for r in V)
    return dict(
        run=path.parent.name,
        designs=len(d["drc_results"]),
        models=sorted(set(f"{r['provider']}/{r['model']}" for r in V)),
        suggestions=len(V), categories=dict(cats),
        zero_response_n=len(zero_resp), parse_fail_n=parse_fail,
        proposed_n=len(proposed),
        converged_n=len(conv),
        convergence=round(len(conv) / len(proposed) * 100, 1) if proposed else None,
        convergence_ci=(lo, hi),
        reverted_n=len(reverted), revert_rate=round(len(reverted) / len(proposed) * 100, 1) if proposed else None,
        fixkeep_n=len(fixkeep), fixkeep_rate=round(len(fixkeep) / len(proposed) * 100, 1) if proposed else None,
        nonconv_n=len(nonconv),
        nonconv_detail=[dict(design=r["design"], cat=r["suggestion_category"],
                             blocking=(rounds_of(r)[-1].get("blocking_new", 0) if rounds_of(r) else None))
                        for r in nonconv],
        hosts_n=len(hosts),
        hosts_first_blocking=sum(rounds_of(r)[0].get("blocking_new", 0) for r in hosts),
        hosts_final_blocking=sum(rounds_of(r)[-1].get("blocking_new", 0) for r in hosts),
        hosts_reverted=sum(1 for r in hosts if r.get("fully_reverted")),
        hosts_fixkeep=sum(1 for r in hosts if len(r.get("applied_changes") or []) > 0 and r.get("converged")),
        avg_rounds=round(sum(r["rounds"] for r in V) / len(V), 2) if V else None,
        avg_time=round(sum(r.get("elapsed_seconds") or 0 for r in V) / len(V), 1) if V else None,
        llm_usage=d.get("llm_usage"),
    )


def main() -> None:
    runs = {}
    for prov in ("deepseek", "qwen"):
        cands = sorted(ROOT.glob(f"experiment_results/mm20_{prov}_*/results.json"))
        if not cands:
            print(f"[SKIP] {prov}: no run")
            continue
        runs[prov] = analyze(cands[-1])
    OUT.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")
    for prov, m in runs.items():
        print(f"== {prov} ({m['models']}) ==")
        for k in ("designs", "suggestions", "zero_response_n", "parse_fail_n", "proposed_n",
                  "converged_n", "convergence", "convergence_ci", "reverted_n", "revert_rate",
                  "fixkeep_n", "fixkeep_rate", "nonconv_n", "hosts_n", "hosts_first_blocking",
                  "hosts_final_blocking", "hosts_reverted", "hosts_fixkeep", "avg_rounds", "avg_time"):
            print(f"  {k}: {m[k]}")
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()

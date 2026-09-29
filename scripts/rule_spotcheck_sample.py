"""规则抽查 · 分层抽样

从 violations.jsonl（scripts/rule_spotcheck_dump.py 产出）里按**规则**分层抽样，
生成判读表。分层而不是整体随机：少数规则贡献了绝大多数违规（锐角 1769/5769），
整体随机会让小样本全落在同一两条规则上，掩盖其它规则的误报模式。

输出（默认 experiment_results/rule_spotcheck/）::

    sample.jsonl   抽样记录（含 evidence），供判读后追加 verdict/reason
    sample.csv     同样的内容 + 空的 verdict / severity_ok / reason 列（人工复核用）
    sample_summary.json

用法::

    python scripts/rule_spotcheck_sample.py --trace-per-rule 5 --other-per-rule 2 --seed 20260918
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def brief(evidence: dict, limit: int = 260) -> str:
    parts = []
    for k, v in evidence.items():
        if k in ("acute", "right", "worst6", "degenerate_below_leg_gate"):
            v = "n=" + str(len(v))
        s = json.dumps(v, ensure_ascii=False)
        parts.append(k + "=" + s)
    out = "; ".join(parts)
    return out if len(out) <= limit else out[:limit] + "..."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="experiment_results/rule_spotcheck")
    ap.add_argument("--trace-per-rule", type=int, default=5)
    ap.add_argument("--other-per-rule", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20260918)
    args = ap.parse_args()

    root = Path(args.dir)
    recs = [json.loads(line) for line in (root / "violations.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_rule: dict = defaultdict(list)
    for r in recs:
        by_rule[r["rule_func"]].append(r)

    rng = random.Random(args.seed)
    picked = []
    for rule in sorted(by_rule):
        items = by_rule[rule]
        k = args.trace_per_rule if items[0].get("is_trace_family") else args.other_per_rule
        k = min(k, len(items))
        # 先按 id 排序保证可复现，再抽样；样本不足时全取
        sample = rng.sample(sorted(items, key=lambda r: r["id"]), k)
        for s in sorted(sample, key=lambda r: r["id"]):
            s = dict(s)
            s["stratum_population"] = len(items)
            picked.append(s)

    with (root / "sample.jsonl").open("w", encoding="utf-8") as fh:
        for r in picked:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    with (root / "sample.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "design", "rule_name", "severity", "description",
                    "evidence_brief", "verdict(TP/FP/GEN)", "severity_ok(yes/no)", "reason"])
        for r in picked:
            w.writerow([r["id"], r["design"]["file"], r["rule_name"], r["severity"],
                        r["description"], brief(r.get("evidence") or {}), "", "", ""])

    summary = {
        "population_records": len(recs),
        "sampled_records": len(picked),
        "rules_in_population": len(by_rule),
        "rules_sampled": len({r["rule_func"] for r in picked}),
        "by_rule": dict(Counter(r["rule_func"] for r in picked).most_common()),
        "by_rule_name": dict(Counter(r["rule_name"] for r in picked).most_common()),
        "seed": args.seed,
        "trace_per_rule": args.trace_per_rule,
        "other_per_rule": args.other_per_rule,
    }
    (root / "sample_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

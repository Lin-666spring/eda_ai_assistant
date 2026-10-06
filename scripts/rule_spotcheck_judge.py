"""规则抽查 · 合并判读结果 → judged.jsonl

把 verdicts_*.json（{id: {v, s, r}}）合并进 sample.jsonl，生成 judged.jsonl，
并报告未被判读 / 判读 id 不存在的条目（防止 id 拼写错导致静默丢样本）。

用法: python scripts/rule_spotcheck_judge.py [--dir experiment_results/rule_spotcheck]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_ROOT = Path("experiment_results/rule_spotcheck")
VALID = {"TP", "FP", "GEN", "UNC"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(DEFAULT_ROOT),
                    help="抽查轮次目录（含 sample.jsonl 与 verdicts_*.json）")
    args = ap.parse_args()
    root = Path(args.dir)
    sample = [json.loads(l) for l in (root / "sample.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    verdicts: dict = {}
    overridden: list = []
    for f in sorted(root.glob("verdicts_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for k, v in data.items():
            if k in verdicts:
                overridden.append((k, f.name))
            verdicts[k] = v  # 后加载的文件覆盖先前的（便于修订单条判读）

    out, missing, bad = [], [], []
    for rec in sample:
        v = verdicts.get(rec["id"])
        if v is None:
            missing.append(rec["id"])
            rec = dict(rec)
            rec["verdict"] = "UNJUDGED"
            rec["severity_ok"] = ""
            rec["reason"] = ""
        else:
            if v["v"] not in VALID:
                bad.append((rec["id"], v["v"]))
            rec = dict(rec)
            rec["verdict"] = v["v"]
            rec["severity_ok"] = v.get("s", "")
            rec["reason"] = v.get("r", "")
        out.append(rec)

    with (root / "judged.jsonl").open("w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    extra = sorted(set(verdicts) - {r["id"] for r in sample})
    print("样本", len(sample), "判读", len(sample) - len(missing), "未判读", len(missing))
    if missing:
        print("未判读 id（前 10）:", missing[:10])
    if extra:
        print("多出的判读 id（前 10）:", extra[:10])
    if bad:
        print("非法 verdict:", bad)
    if overridden:
        print("被覆盖修订:", len(overridden), "条 ->", [k for k, _ in overridden][:6])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""规则抽查 · 计分：精确率 + Wilson 置信区间

读 judged.jsonl（sample.jsonl + 人工/AI 判读的 verdict/severity_ok/reason），
按「走线类 / 其它」两个族与逐规则统计。

判定口径（三分类，避免把「通用提示」混进精确率）::

    TP   违规成立：证据支持判据，且是这块板上真该改的问题
    FP   误报：判据/几何/数据用错，或该处根本不是问题
    GEN  通用提示：不是对这块板的判定（任何板都会响），无法证伪；
         既不算对也不算错，单独统计——它会让「有输出」口径虚高

精确率 precision = TP / (TP + FP)，报 Wilson 95% 区间；GEN 单列。
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 区间（小样本比正态近似稳）。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - half) / d, (c + half) / d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="experiment_results/rule_spotcheck")
    ap.add_argument("--judged", default="judged.jsonl")
    args = ap.parse_args()

    root = Path(args.dir)
    recs = [json.loads(l) for l in (root / args.judged).read_text(encoding="utf-8").splitlines() if l.strip()]
    judged = [r for r in recs if r.get("verdict") in ("TP", "FP", "GEN", "UNC")]

    def stats(items):
        tp = sum(1 for r in items if r["verdict"] == "TP")
        fp = sum(1 for r in items if r["verdict"] == "FP")
        gen = sum(1 for r in items if r["verdict"] == "GEN")
        unc = sum(1 for r in items if r["verdict"] == "UNC")
        n = tp + fp
        lo, hi = wilson(tp, n)
        lo2, hi2 = wilson(tp, n + unc)
        sev_bad = sum(1 for r in items if r.get("severity_ok") == "no")
        return {
            "judged": len(items), "TP": tp, "FP": fp, "GEN": gen, "UNC": unc,
            "precision_tp_over_tp_fp": round(tp / n, 4) if n else None,
            "precision_ci95": [round(lo, 4), round(hi, 4)] if n else None,
            "precision_unc_as_fp": round(tp / (n + unc), 4) if (n + unc) else None,
            "precision_unc_as_fp_ci95": [round(lo2, 4), round(hi2, 4)] if (n + unc) else None,
            "share_TP_of_all_judged": round(tp / len(items), 4) if items else None,
            "share_GEN": round(gen / len(items), 4) if items else None,
            "severity_too_high": sev_bad,
        }

    lines = []
    out = {"overall": stats(judged)}
    lines.append("规则抽查判读结果")
    lines.append("样本 %d 条 / 判读 %d 条" % (len(recs), len(judged)))
    lines.append("")
    lines.append("== 总览 ==")
    o = out["overall"]
    lines.append("TP %d / FP %d / GEN %d / UNC %d" % (o["TP"], o["FP"], o["GEN"], o["UNC"]))
    lines.append("精确率 TP/(TP+FP) = %s  95%%CI %s" % (o["precision_tp_over_tp_fp"], o["precision_ci95"]))
    lines.append("保守下界(UNC 全算误报) = %s  95%%CI %s" % (o["precision_unc_as_fp"], o["precision_unc_as_fp_ci95"]))
    lines.append("TP 占全部判读 = %s ; GEN 占 = %s ; 严重度偏高 %d 条" % (
        o["share_TP_of_all_judged"], o["share_GEN"], o["severity_too_high"]))

    fams = defaultdict(list)
    for r in judged:
        fams["trace" if r.get("is_trace_family") else "other"].append(r)
    out["by_family"] = {}
    lines.append("")
    lines.append("== 按族 ==")
    for fam, items in sorted(fams.items()):
        s = stats(items)
        out["by_family"][fam] = s
        lines.append("%-6s n=%-4d TP %-4d FP %-4d GEN %-4d UNC %-4d precision=%s (UNC→FP: %s)" % (
            fam, s["judged"], s["TP"], s["FP"], s["GEN"], s["UNC"],
            s["precision_tp_over_tp_fp"], s["precision_unc_as_fp"]))

    per_rule = defaultdict(list)
    for r in judged:
        per_rule[r["rule_name"]].append(r)
    out["by_rule"] = {}
    lines.append("")
    lines.append("== 逐规则（n>=2）==")
    for name, items in sorted(per_rule.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 2:
            continue
        s = stats(items)
        out["by_rule"][name] = s
        lines.append("%-22s n=%-3d TP %-3d FP %-3d GEN %-3d UNC %-3d precision=%s" % (
            name, s["judged"], s["TP"], s["FP"], s["GEN"], s["UNC"], s["precision_tp_over_tp_fp"]))

    lines.append("")
    lines.append("== FP / GEN 明细 ==")
    for r in judged:
        if r["verdict"] == "GEN":
            lines.append("[GEN] %-20s %s" % (r["rule_name"], r.get("reason", "")))
    for r in judged:
        if r["verdict"] == "FP":
            lines.append("[FP ] %-20s %s | %s" % (r["rule_name"],
                                                  r["description"][:90], r.get("reason", "")))

    report = "\n".join(lines)
    (root / "report.txt").write_text(report, encoding="utf-8")
    (root / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

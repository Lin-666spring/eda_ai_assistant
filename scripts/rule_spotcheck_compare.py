"""规则抽查 · 两轮对比（修复前 vs 修复后）

读两轮的 judged.jsonl，按同一口径（TP/(TP+FP)，Wilson 95%）算出**并排对比**：
总体 / 走线类 / 非走线类 / 逐规则。论文里「判据修复带来多少精确率提升」这句话
就靠这个脚本产出，避免手抄两份 metrics.json 出错。

两轮必须用同一套判读口径（四分类 TP/FP/GEN/UNC，见 rule_spotcheck_score.py 的说明），
否则对比无意义。

用法::

    python scripts/rule_spotcheck_compare.py \
        --a experiment_results/rule_spotcheck \
        --b experiment_results/rule_spotcheck_2026-10-06 \
        --out experiment_results/rule_spotcheck_2026-10-06/compare.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 区间（小样本比正态近似稳）—— 与 score.py 同一实现。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - half) / d, (c + half) / d)


def load(root: Path) -> list[dict]:
    path = root / "judged.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in recs if r.get("verdict") in ("TP", "FP", "GEN", "UNC")]


def stats(items: list[dict]) -> dict:
    tp = sum(1 for r in items if r["verdict"] == "TP")
    fp = sum(1 for r in items if r["verdict"] == "FP")
    gen = sum(1 for r in items if r["verdict"] == "GEN")
    unc = sum(1 for r in items if r["verdict"] == "UNC")
    n = tp + fp
    lo, hi = wilson(tp, n)
    lo2, hi2 = wilson(tp, n + unc)
    return {
        "judged": len(items), "TP": tp, "FP": fp, "GEN": gen, "UNC": unc,
        "precision": round(tp / n, 4) if n else None,
        "ci95": [round(lo, 4), round(hi, 4)] if n else None,
        "precision_unc_as_fp": round(tp / (n + unc), 4) if (n + unc) else None,
        "ci95_unc_as_fp": [round(lo2, 4), round(hi2, 4)] if (n + unc) else None,
        "share_GEN": round(gen / len(items), 4) if items else None,
        "severity_too_high": sum(1 for r in items if r.get("severity_ok") == "no"),
    }


def family_of(rec: dict) -> str:
    return "trace" if rec.get("is_trace_family") else "other"


def fmt(s: dict) -> str:
    if s["precision"] is None:
        return "n=%-3d 无 TP/FP（GEN %d / UNC %d）" % (s["judged"], s["GEN"], s["UNC"])
    return "n=%-3d TP %-3d FP %-3d GEN %-3d UNC %-3d  precision=%5.1f%% CI[%4.1f%%,%5.1f%%]  UNC→FP %5.1f%%  GEN %4.1f%%  严重度偏高 %d" % (
        s["judged"], s["TP"], s["FP"], s["GEN"], s["UNC"],
        100 * s["precision"], 100 * s["ci95"][0], 100 * s["ci95"][1],
        100 * (s["precision_unc_as_fp"] or 0), 100 * (s["share_GEN"] or 0), s["severity_too_high"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="第一轮（修复前）目录")
    ap.add_argument("--b", required=True, help="第二轮（修复后）目录")
    ap.add_argument("--label-a", default="修复前")
    ap.add_argument("--label-b", default="修复后")
    ap.add_argument("--out", default="", help="对比结果 JSON 落盘路径")
    args = ap.parse_args()

    a, b = load(Path(args.a)), load(Path(args.b))
    lines = ["规则抽查两轮对比", ""]

    out: dict = {"label_a": args.label_a, "label_b": args.label_b}

    def block(title: str, pick) -> None:
        sa, sb = stats([r for r in a if pick(r)]), stats([r for r in b if pick(r)])
        out[title] = {"a": sa, "b": sb}
        lines.append("== %s ==" % title)
        lines.append("  %-6s %s" % (args.label_a, fmt(sa)))
        lines.append("  %-6s %s" % (args.label_b, fmt(sb)))
        if sa["precision"] is not None and sb["precision"] is not None:
            d = 100 * (sb["precision"] - sa["precision"])
            lines.append("  变化   %+.1f 个百分点" % d)
        lines.append("")

    block("总体", lambda r: True)
    block("走线类", lambda r: family_of(r) == "trace")
    block("非走线类", lambda r: family_of(r) == "other")

    # 逐规则（两轮都出现的规则）
    by_a: dict = defaultdict(list)
    by_b: dict = defaultdict(list)
    for r in a:
        by_a[r["rule_name"]].append(r)
    for r in b:
        by_b[r["rule_name"]].append(r)

    lines.append("== 逐规则（两轮都有样本）==")
    out["by_rule"] = {}
    for name in sorted(set(by_a) & set(by_b)):
        sa, sb = stats(by_a[name]), stats(by_b[name])
        out["by_rule"][name] = {"a": sa, "b": sb}
        lines.append("  %s" % name)
        lines.append("    %-6s %s" % (args.label_a, fmt(sa)))
        lines.append("    %-6s %s" % (args.label_b, fmt(sb)))
    lines.append("")

    only_a = sorted(set(by_a) - set(by_b))
    only_b = sorted(set(by_b) - set(by_a))
    if only_a:
        lines.append("仅第一轮有样本的规则（修复后不再触发）: %s" % "、".join(only_a))
    if only_b:
        lines.append("仅第二轮有样本的规则（修复后才触发）: %s" % "、".join(only_b))

    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\nwrote " + args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

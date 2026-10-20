# -*- coding: utf-8 -*-
"""受控 2×2 消融统计 —— 论文 R3 增强路径。

读 experiment_results/ablation2x2_<arm>_<ts>/results.json，按臂汇总：
收敛率 / 全撤销收敛率 / 修正-保留收敛率 / 平均轮次 / 未收敛违规停滞比例 /
评分守门触发频次（score_drop 超 τ 的修正进入次数，从 raw_report 不可得，
以每条建议修正轮数 ≥1 且存在 score_drop 字段近似——以日志为准）。

输出: 论文/review/ablation_stats.json + 控制台摘要
"""
from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ARMS = ["A_full", "B_noguid", "C_norevert", "D_neither"]
ARM_LABEL = {
    "A_full": "完整反馈（修法指引+撤销语义）",
    "B_noguid": "无修法指引（撤销语义保留）",
    "C_norevert": "无撤销语义（修法指引保留）",
    "D_neither": "两者皆无（违规名+描述）",
}


def bootstrap_ci(successes: int, n: int, level: float = 0.95, iters: int = 2000,
                 seed: int = 2026) -> tuple[float, float]:
    import random
    rng = random.Random(seed)
    p = successes / n if n else 0.0
    hits = 0
    lo_q = (1 - level) / 2 * 100
    hi_q = (1 + level) / 2 * 100
    samples = []
    for _ in range(iters):
        k = sum(1 for _ in range(n) if rng.random() < p)
        samples.append(k / n if n else 0.0)
    samples.sort()
    return (samples[int(lo_q / 100 * (iters - 1))],
            samples[int(hi_q / 100 * (iters - 1))])


def collect(results_dirs: dict[str, list[str]]) -> dict:
    out = {}
    for arm, dirs in results_dirs.items():
        vr = []
        for d in dirs:
            data = json.loads((Path(d) / "results.json").read_text(encoding="utf-8"))
            vr += data.get("verify_results", [])
        n = len(vr)
        conv = [r for r in vr if r.get("converged")]
        rev = [r for r in conv if r.get("fully_reverted")]
        fixkept = [r for r in conv if not r.get("fully_reverted")]
        stalled = [r for r in vr if not r.get("converged")
                   and r.get("new_violations_introduced", 0) > 0
                   and r.get("final_violation_delta", 0) == r.get("new_violations_introduced", 0)]
        rounds = [r.get("correction_rounds", 0) for r in vr]
        lo, hi = bootstrap_ci(len(conv), n) if n else (0, 0)
        out[arm] = {
            "n": n,
            "converged": len(conv),
            "conv_rate": round(len(conv) / n * 100, 1) if n else None,
            "ci95": [round(lo * 100, 1), round(hi * 100, 1)] if n else None,
            "fully_reverted": len(rev),
            "revert_rate": round(len(rev) / n * 100, 1) if n else None,
            "fix_kept": len(fixkept),
            "fix_kept_rate": round(len(fixkept) / n * 100, 1) if n else None,
            "parse_fail": sum(1 for r in vr if (r.get("final_status") == "error")
                              or (not r.get("converged") and r.get("suggested_changes_count", 0) == 0
                                  and (r.get("new_violations_introduced", 0) == 0))),
            "avg_rounds": round(sum(rounds) / n, 2) if n else None,
            "stalled_unconverged": len(stalled),
            "unconverged": n - len(conv),
        }
    return out


def main() -> None:
    dirs: dict[str, list[str]] = {arm: [] for arm in ARMS}
    for d in sorted(glob.glob(str(ROOT / "experiment_results/ablation2x2_*"))):
        name = Path(d).name
        for arm in ARMS:
            if name.startswith(f"ablation2x2_{arm}_"):
                dirs[arm].append(d)
    # 每臂可能存在多个目录（中断重跑会开新目录）：取 verify_results 最多的一份
    # 作为该臂的权威数据，避免拼接造成同板同建议重复计数。
    have: dict[str, list[str]] = {}
    for arm, ds in dirs.items():
        if not ds:
            continue
        def _count(d: str) -> int:
            try:
                return len(json.loads((Path(d) / "results.json")
                                      .read_text(encoding="utf-8")).get("verify_results", []))
            except Exception:
                return -1
        best = max(ds, key=_count)
        have[arm] = [best]
        n_best = _count(best)
        if len(ds) > 1 or 0 <= n_best < 105:
            print(f"[note] {arm}: 目录 {len(ds)} 个，取最大 {Path(best).name} "
                  f"({n_best}/105)；不足 105 时须整臂重跑")
    if not have:
        print("未找到 ablation2x2_* 结果目录")
        sys.exit(1)
    stats = collect(have)
    out_path = ROOT / "论文/review/ablation_stats.json"
    out_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    for arm in ARMS:
        s = stats.get(arm)
        if not s:
            print(f"{arm}: 无数据")
            continue
        print(f"{arm} [{ARM_LABEL[arm]}]")
        print(f"  n={s['n']}  收敛 {s['converged']} ({s['conv_rate']}%, "
              f"CI95 {s['ci95'][0]}~{s['ci95'][1]}%)  撤销收敛 {s['fully_reverted']} "
              f"({s['revert_rate']}%)  修正保留 {s['fix_kept']} ({s['fix_kept_rate']}%)")
        print(f"  平均轮次 {s['avg_rounds']}  未收敛 {s['unconverged']} "
              f"(其中违规停滞 {s['stalled_unconverged']})")
    print(f"\n→ {out_path}")


if __name__ == "__main__":
    main()

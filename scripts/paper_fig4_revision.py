# -*- coding: utf-8 -*-
"""论文图4（修订版）——blocking 新增违规的宿主建议：首轮 vs 末轮清除对比。

R8 指标重构后的配图：不再呈现"消除率=100%"柱状图，改为 23 条宿主建议
首轮引入的 blocking 违规数（降序）与末轮残留（全部经整体撤销清零）。
数据: experiment_results/run_thing_full_glm53/results.json
输出: 论文/figures/fig4_hallucination.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "experiment_results" / "run_thing_full_glm53" / "results.json"
OUT = ROOT / "论文" / "figures" / "fig4_hallucination.png"

C_FIRST = "#B0533A"
C_FINAL = "#7A93AC"


def main() -> None:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    hosts = []
    for r in d["verify_results"]:
        rr = (r.get("raw_report") or {}).get("rounds") or []
        if not rr:
            continue
        b1 = rr[0].get("blocking_new", 0)
        if b1 and b1 > 0:
            hosts.append((b1, rr[-1].get("blocking_new", 0)))
    hosts.sort(key=lambda x: -x[0])
    first = [h[0] for h in hosts]
    final = [h[1] for h in hosts]

    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    xs = range(1, len(hosts) + 1)
    w = 0.38
    ax.bar([x - w / 2 for x in xs], first, width=w, color=C_FIRST, label="首轮引入（直出即进入设计）")
    ax.bar([x + w / 2 for x in xs], final, width=w, color=C_FINAL, label="末轮残留（全部经整体撤销清零）")
    ax.set_xlabel("引入 blocking 违规的宿主建议（按首轮违规数降序，共 23 条）", fontsize=10)
    ax.set_ylabel("blocking 级新增违规数", fontsize=10)
    ax.set_title("宿主建议的 blocking 违规：首轮引入 vs 闭环末轮残留", fontsize=11, fontweight="bold")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([str(i) for i in xs], fontsize=8)
    ax.legend(fontsize=9, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.annotate(f"首轮合计 {sum(first)} 条次 / 末轮合计 {sum(final)} 条次",
                xy=(0.98, 0.60), xycoords="axes fraction", ha="right", fontsize=9,
                bbox=dict(fc="white", ec="#CCCCCC", pad=4))
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()

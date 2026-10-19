"""论文图2 —— DRC 基线违规分布（双面板，替代 79 个设计名挤轴的原图）。

面板(a): 各设计违规总数按降序排列的柱状图（x=设计序号，不标设计名）；
面板(b): 严重度构成（error/warning/info）。
数据: experiment_results/run_thing_full_glm53/results.json
输出: 论文/figures/fig2_severity.png
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
OUT = ROOT / "论文" / "figures" / "fig2_severity.png"

C_ERR = "#B0533A"
C_WARN = "#D9A441"
C_INFO = "#7A93AC"


def main() -> None:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = d["drc_results"]
    totals = sorted((r["total_violations"] for r in rows), reverse=True)
    e = sum(r["errors"] for r in rows)
    w = sum(r["warnings"] for r in rows)
    i = sum(r["infos"] for r in rows)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.2))

    # (a) 按设计序号排序的违规总数
    xs = range(1, len(totals) + 1)
    ax1.bar(xs, totals, color=C_INFO, width=0.85)
    ax1.axhline(sum(totals) / len(totals), color=C_ERR, linestyle="--", linewidth=1.4,
                label=f"均值 {sum(totals)/len(totals):.1f}")
    ax1.set_xlabel("设计序号（按违规数降序）", fontsize=10)
    ax1.set_ylabel("违规总数", fontsize=10)
    ax1.set_title("(a) 79 个设计的违规总数分布", fontsize=11, fontweight="bold")
    ax1.legend(fontsize=9)

    # (b) 严重度构成
    vals = [e, w, i]
    labels = [f"error\n{e} 条", f"warning\n{w} 条", f"info\n{i} 条"]
    bars = ax2.bar(labels, vals, color=[C_ERR, C_WARN, C_INFO], width=0.55)
    for b, v in zip(bars, vals):
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + max(vals) * 0.02,
                 f"{v}\n({v/sum(vals)*100:.1f}%)", ha="center", va="bottom", fontsize=9)
    ax2.set_ylabel("违规条数", fontsize=10)
    ax2.set_ylim(0, max(vals) * 1.22)
    ax2.set_title("(b) 严重度构成", fontsize=11, fontweight="bold")

    for ax in (ax1, ax2):
        ax.tick_params(labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()

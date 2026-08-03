"""
EI 论文图表生成模块 — 从实验结果 JSON 生成论文级图表

用法:
  # 从实验结果生成所有图表
  python tests/paper_charts.py experiment_results/run_2026-07-09_143052/

  # 指定输出目录
  python tests/paper_charts.py results.json --output charts/

  # 交互式显示
  python tests/paper_charts.py results.json --show

图表列表:
  1. hallucination_bar.png      — 幻觉消除率柱状图
  2. convergence_line.png       — 迭代收敛曲线
  3. radar_multi_agent.png      — 多智能体雷达图
  4. time_comparison.png        — 耗时对比
  5. severity_distribution.png  — 违规严重度分布
  6. summary_table.png          — 实验汇总表
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── 中文字体配置 ──
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ── 论文级配色 ──
COLORS = {
    "deepseek": "#4C72B0",
    "qwen": "#55A868",
    "glm": "#C44E52",
    "baseline": "#8172B2",
    "accepted": "#2CA02C",
    "rejected": "#D62728",
    "safe": "#1F77B4",
    "dangerous": "#D62728",
    "optimization": "#FF7F0E",
    "error": "#D62728",
    "warning": "#FF7F0E",
    "info": "#1F77B4",
    "grid": "#E0E0E0",
}

FONT_TITLE = 14
FONT_LABEL = 12
FONT_TICK = 10
FONT_LEGEND = 10
FONT_ANNOTATION = 9


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _safe_print(msg: str) -> None:
    """Windows GBK-safe print."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _setup_axis(ax, title: str, xlabel: str = "", ylabel: str = ""):
    """Apply consistent styling to an axis."""
    ax.set_title(title, fontsize=FONT_TITLE, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=FONT_LABEL)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    ax.tick_params(labelsize=FONT_TICK)
    ax.grid(axis="y", alpha=0.3, color=COLORS["grid"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _get_color(provider: str) -> str:
    """Get chart color for a provider."""
    return COLORS.get(provider.lower(), "#333333")


# ═══════════════════════════════════════════════════════════════
#  Chart 1: Hallucination Elimination Rate
# ═══════════════════════════════════════════════════════════════

def chart_hallucination_bar(results: list[dict], output_path: Path, show: bool = False):
    """Bar chart: hallucination elimination rate by design × suggestion × provider."""
    # Filter valid results
    data = [r for r in results
            if not r.get("error") and r.get("hallucination_elimination") is not None]

    if not data:
        _safe_print("  [SKIP] No hallucination elimination data -- skipping chart")
        return

    # Group by design + provider
    categories = sorted(set(f"{r['design']}\n{r['provider']}" for r in data))
    if len(categories) > 12:
        # Too many categories, aggregate by provider
        providers = sorted(set(r["provider"] for r in data))
        values = []
        for p in providers:
            p_data = [r["hallucination_elimination"] for r in data if r["provider"] == p]
            values.append(sum(p_data) / len(p_data))
        categories = providers
    else:
        values = []
        for cat in categories:
            design, provider = cat.split("\n")
            cat_data = [r["hallucination_elimination"]
                        for r in data
                        if r["design"] == design and r["provider"] == provider]
            values.append(sum(cat_data) / len(cat_data))

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(range(len(categories)), values, color=[_get_color(c.split("\n")[-1]) for c in categories])

    # Target line
    ax.axhline(y=80, color="green", linestyle="--", linewidth=1.5, alpha=0.7, label="目标 80%")

    # Annotate bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%", ha="center", va="bottom", fontsize=FONT_ANNOTATION)

    _setup_axis(ax, "幻觉消除率 (Hallucination Elimination Rate)",
                xlabel="", ylabel="消除率 (%)")
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, fontsize=9)
    ax.set_ylim(0, max(105, max(values) * 1.15))
    ax.legend(fontsize=FONT_LEGEND, loc="lower right")

    fig.tight_layout()
    fig.savefig(output_path / "hallucination_bar.png", dpi=200, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    _safe_print(f"  [OK] hallucination_bar.png")


# ═══════════════════════════════════════════════════════════════
#  Chart 2: Iteration Convergence
# ═══════════════════════════════════════════════════════════════

def chart_convergence_line(results: list[dict], output_path: Path, show: bool = False):
    """Line chart: blocking issues vs round for closed-loop verification."""
    # Filter for results with multiple rounds
    # Prefer real per_round_blocking data
    data = [r for r in results
            if not r.get("error")
            and r.get("per_round_blocking")
            and len(r.get("per_round_blocking", [])) > 1]

    if not data:
        _safe_print("  [SKIP] No multi-round data -- skipping convergence chart")
        return

    fig, ax = plt.subplots(figsize=(9, 5.5))

    plotted = 0
    for r in data[:10]:
        label = f"{r['design'][:15]}/{r['provider'][:8]}/{r['suggestion_category'][:10]}"
        per_round = r["per_round_blocking"]
        xs = list(range(1, len(per_round) + 1))
        ax.plot(xs, per_round, "o-", linewidth=2, markersize=6,
                label=label, alpha=0.8)
        plotted += 1

    if plotted == 0:
        _safe_print("  [SKIP] No convergence lines to plot")
        plt.close(fig)
        return

    _setup_axis(ax, "迭代收敛曲线 (Convergence over Rounds)",
                xlabel="轮次 (Round)", ylabel="阻断违规数 (Blocking Issues)")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    if plotted <= 8:
        ax.legend(fontsize=8, loc="upper right", ncol=1)

    fig.tight_layout()
    fig.savefig(output_path / "convergence_line.png", dpi=200, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    _safe_print(f"  [OK] convergence_line.png ({plotted} lines)")


# ═══════════════════════════════════════════════════════════════
#  Chart 3: Multi-Agent Radar Chart
# ═══════════════════════════════════════════════════════════════

def chart_radar_multi_agent(ma_results: list[dict], output_path: Path, show: bool = False):
    """Radar chart: multi-agent scores across dimensions."""
    data = [r for r in ma_results if not r.get("error") and r.get("radar_scores")]

    if not data:
        _safe_print("  [SKIP] No multi-agent data -- skipping radar chart")
        return

    # One chart per design
    designs = sorted(set(r["design"] for r in data))

    for design in designs:
        design_data = [r for r in data if r["design"] == design]
        if not design_data:
            continue

        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"})

        for entry in design_data:
            radar = entry["radar_scores"]
            dims = list(radar.keys())
            values = list(radar.values())

            # Close the polygon
            angles = [n / float(len(dims)) * 2 * math.pi for n in range(len(dims))]
            values += values[:1]
            angles += angles[:1]

            provider = entry["provider"]
            ax.fill(angles, values, alpha=0.1, color=_get_color(provider))
            ax.plot(angles, values, "o-", linewidth=2, label=f"{provider} ({entry['overall_score']:.0f})",
                    color=_get_color(provider), markersize=4)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(dims, fontsize=FONT_TICK)
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8)
        ax.set_title(f"多智能体审查雷达图 — {design}", fontsize=FONT_TITLE,
                     fontweight="bold", pad=20)
        ax.legend(fontsize=FONT_LEGEND, loc="upper right",
                  bbox_to_anchor=(1.3, 1.1))

        safe_name = design.replace(" ", "_").replace("/", "_")
        fig.tight_layout()
        fig.savefig(output_path / f"radar_{safe_name}.png", dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)
        _safe_print(f"  [OK] radar_{safe_name}.png")


# ═══════════════════════════════════════════════════════════════
#  Chart 4: Time Comparison
# ═══════════════════════════════════════════════════════════════

def chart_time_comparison(
    drc_results: list[dict],
    verify_results: list[dict],
    ma_results: list[dict],
    output_path: Path,
    show: bool = False,
):
    """Bar chart: time comparison across experiment phases."""
    # Average times
    drc_times = [r["elapsed_seconds"] for r in drc_results if not r.get("error")]
    verify_times = [r["elapsed_seconds"] for r in verify_results
                    if not r.get("error") and r.get("llm_correction_rounds", 0) > 0]
    ma_times = [r["elapsed_seconds"] for r in ma_results if not r.get("error")]

    categories = []
    values = []

    if drc_times:
        categories.append(f"DRC 基线\n({sum(drc_times)/len(drc_times):.1f}s)")
        values.append(sum(drc_times) / len(drc_times))

    if verify_times:
        categories.append(f"闭环验证\n({sum(verify_times)/len(verify_times):.1f}s)")
        values.append(sum(verify_times) / len(verify_times))

    if ma_times:
        categories.append(f"多智能体\n({sum(ma_times)/len(ma_times):.1f}s)")
        values.append(sum(ma_times) / len(ma_times))

    if not categories:
        _safe_print("  [SKIP] No time data -- skipping time chart")
        return

    fig, ax = plt.subplots(figsize=(7, 5))
    bar_colors = [COLORS["baseline"], COLORS["deepseek"], COLORS["qwen"]][:len(categories)]
    bars = ax.bar(range(len(categories)), values, color=bar_colors, width=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                f"{val:.1f}s", ha="center", va="bottom", fontsize=FONT_ANNOTATION)

    _setup_axis(ax, "平均耗时对比 (Time Comparison)",
                xlabel="", ylabel="耗时 (秒)")
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, fontsize=FONT_TICK)

    fig.tight_layout()
    fig.savefig(output_path / "time_comparison.png", dpi=200, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    _safe_print(f"  [OK] time_comparison.png")


# ═══════════════════════════════════════════════════════════════
#  Chart 5: Severity Distribution
# ═══════════════════════════════════════════════════════════════

def chart_severity_distribution(drc_results: list[dict], output_path: Path, show: bool = False):
    """Grouped bar: violation severity distribution per design."""
    if not drc_results:
        _safe_print("  [SKIP] No DRC data -- skipping severity chart")
        return

    designs = [r["design"] for r in drc_results]
    errors = [r["errors"] for r in drc_results]
    warnings = [r["warnings"] for r in drc_results]
    infos = [r["infos"] for r in drc_results]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(designs))
    width = 0.25

    ax.bar(x - width, errors, width, label="Error", color=COLORS["error"], alpha=0.85)
    ax.bar(x, warnings, width, label="Warning", color=COLORS["warning"], alpha=0.85)
    ax.bar(x + width, infos, width, label="Info", color=COLORS["info"], alpha=0.85)

    _setup_axis(ax, "DRC 违规严重度分布 (Violation Severity Distribution)",
                xlabel="", ylabel="违规数量")
    ax.set_xticks(x)
    ax.set_xticklabels(designs, fontsize=FONT_TICK)
    ax.legend(fontsize=FONT_LEGEND)

    fig.tight_layout()
    fig.savefig(output_path / "severity_distribution.png", dpi=200, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    _safe_print(f"  [OK] severity_distribution.png")


# ═══════════════════════════════════════════════════════════════
#  Chart 6: Summary Table Figure
# ═══════════════════════════════════════════════════════════════

def chart_summary_table(verify_results: list[dict], output_path: Path, show: bool = False):
    """Render a summary table as a matplotlib figure."""
    data = [r for r in verify_results if not r.get("error")]
    if not data:
        _safe_print("  [SKIP] No verify data -- skipping summary table")
        return

    # Aggregate by provider
    providers = sorted(set(r["provider"] for r in data))
    rows = []
    for p in providers:
        p_data = [r for r in data if r["provider"] == p]
        accepted = sum(1 for r in p_data if r["accepted"])
        hall_rates = [r["hallucination_elimination"] for r in p_data
                      if r["hallucination_elimination"] is not None]
        avg_rounds = sum(r["rounds"] for r in p_data) / len(p_data)
        avg_time = sum(r["elapsed_seconds"] for r in p_data) / len(p_data)
        rows.append([
            p,
            f"{accepted}/{len(p_data)}",
            f"{sum(hall_rates)/len(hall_rates):.0f}%" if hall_rates else "N/A",
            f"{avg_rounds:.1f}",
            f"{avg_time:.1f}s",
        ])

    fig, ax = plt.subplots(figsize=(10, len(rows) * 0.6 + 2))
    ax.axis("off")

    col_labels = ["LLM", "通过率", "幻觉消除率", "平均轮次", "平均耗时"]
    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        colWidths=[0.15, 0.15, 0.20, 0.15, 0.15],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.8)

    # Style header
    for j, label in enumerate(col_labels):
        cell = table[0, j]
        cell.set_facecolor("#40466e")
        cell.set_text_props(color="white", fontweight="bold")

    # Style rows
    for i in range(len(rows)):
        for j in range(len(col_labels)):
            cell = table[i + 1, j]
            cell.set_facecolor("#f5f5f5" if i % 2 == 0 else "white")

    ax.set_title("闭环验证实验汇总", fontsize=FONT_TITLE + 2,
                 fontweight="bold", pad=20)

    fig.tight_layout()
    fig.savefig(output_path / "summary_table.png", dpi=200, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    _safe_print(f"  [OK] summary_table.png")


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def generate_charts(results_path: Path, output_dir: Optional[Path] = None, show: bool = False):
    """Generate all charts from a results JSON file or experiment directory.

    Args:
        results_path: Path to results.json or experiment run directory.
        output_dir: Where to save charts (default: results_path's charts/ subdir).
        show: Whether to display charts interactively.
    """
    # Resolve results.json
    if results_path.is_dir():
        json_file = results_path / "results.json"
        if not json_file.exists():
            _safe_print(f"[ERROR] No results.json in {results_path}")
            return
        if output_dir is None:
            output_dir = results_path / "charts"
        results_path = json_file
    elif results_path.suffix == ".json":
        if output_dir is None:
            output_dir = results_path.parent / "charts"
    else:
        _safe_print(f"[ERROR] Unsupported input: {results_path}")
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    _safe_print(f"[charts] Loading: {results_path}")
    data = json.loads(results_path.read_text(encoding="utf-8"))

    drc_results = data.get("drc_results", [])
    verify_results = data.get("verify_results", [])
    ma_results = data.get("ma_results", [])

    _safe_print(f"   DRC baseline: {len(drc_results)} results")
    _safe_print(f"   Closed-loop: {len(verify_results)} results")
    _safe_print(f"   Multi-agent: {len(ma_results)} results")
    _safe_print("")

    # Generate charts
    _safe_print("[charts] Generating charts...")
    chart_hallucination_bar(verify_results, output_dir, show)
    chart_convergence_line(verify_results, output_dir, show)
    chart_radar_multi_agent(ma_results, output_dir, show)
    chart_time_comparison(drc_results, verify_results, ma_results, output_dir, show)
    chart_severity_distribution(drc_results, output_dir, show)
    chart_summary_table(verify_results, output_dir, show)

    _safe_print(f"\n[OK] Charts saved to: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="EI 论文图表生成 — 从实验结果生成论文级图表",
    )
    parser.add_argument(
        "input", type=str,
        help="实验目录或 results.json 路径",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="图表输出目录（默认 input/charts/）",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="显示图表（非交互式环境可能不生效）",
    )
    args = parser.parse_args()

    generate_charts(
        results_path=Path(args.input),
        output_dir=Path(args.output) if args.output else None,
        show=args.show,
    )


if __name__ == "__main__":
    main()

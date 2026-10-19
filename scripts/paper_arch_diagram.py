"""论文图1 —— 系统架构图（闭环验证引擎总体架构）。

输出: 论文/figures/fig1_architecture.png (300dpi, 印刷友好)
口径: 与 scripts/paper_charts.py 一致的中文字体配置（SimHei 优先）。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).resolve().parent.parent / "论文" / "figures" / "fig1_architecture.png"

# 配色（低饱和、印刷友好）
C_INPUT = "#E8EEF4"
C_PARSE = "#DDE7EF"
C_LLM = "#FBEFD9"
C_DRC = "#E3EFE3"
C_MA = "#EFE9F4"
C_OUT = "#F2F2F2"
EDGE = "#3A4A5A"


def box(ax, x, y, w, h, text, fc, fontsize=10.5, bold=False, dashed=False, lw=1.2):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=1.6 if not dashed else 1.2,
        edgecolor=EDGE if not dashed else "#7A8BA0",
        facecolor=fc,
        linestyle="--" if dashed else "-",
        zorder=2,
    )
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight="bold" if bold else "normal",
            color="#1A2430", zorder=3, linespacing=1.5)


def arrow(ax, x1, y1, x2, y2, label=None, style="-", color=EDGE, lw=1.6,
          label_off=(0, 0.9), rad=0.0, fs=9):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>", mutation_scale=13, linewidth=lw,
        color=color, linestyle=style,
        connectionstyle=f"arc3,rad={rad}",
        zorder=1,
    )
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2 + label_off[0], (y1 + y2) / 2 + label_off[1],
                label, ha="center", va="bottom", fontsize=fs, color="#33404E",
                bbox=dict(fc="white", ec="none", pad=1.2), zorder=4)


def main() -> None:
    fig, ax = plt.subplots(figsize=(11.6, 7.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 66)
    ax.axis("off")

    # ── 输入层 ──
    box(ax, 12, 59.5, 34, 5.4, "立创EDA工程文件\n（原理图 · BOM · PCB 几何数据）", C_INPUT, bold=True)
    box(ax, 54, 59.5, 34, 5.4, "用户自然语言请求\n（中文 · 口语化）", C_INPUT, bold=True)

    # ── 解析与理解层 ──
    box(ax, 12, 50.5, 34, 5.4, "工程解析器\n→ 统一PCB数据模型", C_PARSE)
    box(ax, 54, 50.5, 34, 5.4, "意图识别引擎（本地 BERT 小模型）\n→ 设计审查 / 知识问答分流", C_PARSE)
    arrow(ax, 29, 59.5, 29, 56.2)
    arrow(ax, 71, 59.5, 71, 56.2)

    # ── 闭环验证引擎（虚线容器） ──
    container = FancyBboxPatch(
        (3.5, 27.5), 93, 19.5,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=1.6, edgecolor="#7A8BA0", facecolor="#FAFBFC",
        linestyle="--", zorder=0,
    )
    ax.add_patch(container)
    ax.text(5.0, 44.6, "闭环验证引擎", fontsize=12.5, fontweight="bold", color="#33404E")

    box(ax, 7, 31.5, 22, 9.5, "LLM 建议引擎\n（GLM-5.3）\n生成BOM变更建议", C_LLM, bold=True)
    box(ax, 38, 31.5, 22, 9.5, "建议解析与预检\n（结构化解析 ·\n危险操作预拦截）", C_LLM)
    box(ax, 69, 31.5, 24, 9.5, "DRC 规则引擎（68 条）\n＋ IPC-2221/2141 计算\n（载流 · 阻抗 · 降额）", C_DRC, bold=True)

    arrow(ax, 29, 36.2, 38, 36.2, "变更集")
    arrow(ax, 60, 36.2, 69, 36.2, "应用变更")
    # 反馈回路（DRC → LLM，容器内部走线）
    arrow(ax, 80, 41.2, 80, 45.6, style="--", color="#B0533A", lw=1.8)
    arrow(ax, 80, 45.6, 18, 45.6, style="--", color="#B0533A", lw=1.8)
    arrow(ax, 18, 45.6, 18, 41.2, style="--", color="#B0533A", lw=1.8)
    ax.text(49, 45.9, "结构化修正反馈（新违规清单＋修法指引，迭代 ≤ 3 轮）",
            ha="center", va="bottom", fontsize=9.2, color="#8A3A26",
            bbox=dict(fc="white", ec="none", pad=1.0), zorder=4)

    # 入口箭头（两路输入汇入闭环引擎容器）
    arrow(ax, 29, 50.5, 35, 47.3, rad=-0.15, label="设计数据", label_off=(-7.4, -1.6))
    arrow(ax, 71, 50.5, 65, 47.3, rad=0.15, label="审查请求", label_off=(7.4, -1.6))

    # 通过出口（容器底部中央 → 多智能体）
    arrow(ax, 50, 27.5, 50, 24.0, label="验证通过（PASSED）", color="#2E6B3E",
          label_off=(5.5, -1.8), fs=9)

    # ── 多智能体协同审查 ──
    box(ax, 20, 18.5, 60, 5.4,
        "多智能体协同审查：电源完整性 · 信号完整性 · 热管理 · 电磁兼容 · 可制造性（5 Agent 并行）",
        C_MA, bold=True)
    arrow(ax, 50, 27.5, 50, 24.0)

    # ── 输出层 ──
    box(ax, 20, 9.5, 60, 5.4,
        "六维设计评分（雷达图）＋ 结构化审查报告（违规清单 · 修正记录 · 采纳建议）",
        C_OUT, bold=True)
    arrow(ax, 50, 18.5, 50, 15.0)

    # ── 底注：DRC 守门语义 ──
    ax.text(50, 4.2,
            "守门语义：未通过 DRC 复检的 LLM 建议不得进入设计；危险建议可被整体撤销（full-revert）",
            ha="center", va="center", fontsize=9.2, color="#5A6878", style="italic")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()

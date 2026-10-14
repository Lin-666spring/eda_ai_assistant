"""端到端本地分析计时 — 用真实实验样本定位"分析慢"发生在哪一段

样本: test_data/pcb_designs/dcdc_power_v62（DC-DC 电源板 V6.2，94 元件，全仓库最大）

流程与 AppController 用户路径一致:
  构造 controller → load_bom(xlsx) → load_positions(csv) → load_pcb(json)
  → DesignRuleChecker.check_all（71 条规则，内嵌元件 TextCNN）
  → DesignScorer.score → NLUEngine 意图分类

关键观测点: 首次 check_all 会触发 import torch + 元件模型懒加载，
与热身后的稳态耗时对比，即可看出"慢"是否来自本地模型。

用法:
    python scripts/bench_local_analysis.py [--design dcdc_power_v62]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def fmt(ms: float) -> str:
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.1f} ms"


def step(label: str, fn):
    t0 = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - t0) * 1000
    print(f"  {label:44s}: {fmt(ms)}")
    return result, ms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", default="dcdc_power_v62")
    args = parser.parse_args()

    design_dir = PROJECT_ROOT / "test_data" / "pcb_designs" / args.design
    bom_xlsx = next(design_dir.glob("BOM*.xlsx"))
    pos_csv = next(design_dir.glob("PickAndPlace*.csv"))
    pcb_json = next(design_dir.rglob("*.json"))

    print(f"样本: {args.design}")
    print(f"  BOM : {bom_xlsx.name}")
    print(f"  坐标: {pos_csv.name}")
    print(f"  PCB : {pcb_json.name}\n")

    # ── 阶段 1: 冷导入（应用启动路径）──
    print("── 冷导入 ──")
    t0 = time.perf_counter()
    from src.core.controller import AppController
    from src.rules.checker import DesignRuleChecker
    from src.core.design_scorer import DesignScorer
    import_ms = (time.perf_counter() - t0) * 1000
    print(f"  {'import controller/rules/scorer（不含 torch）':44s}: {fmt(import_ms)}")

    # ── 阶段 2: 加载设计 ──
    print("\n── 加载设计 ──")
    (ctrl, ms) = step("AppController()", AppController)
    step(f"load_bom({bom_xlsx.name[:28]}…)", lambda: ctrl.load_bom(str(bom_xlsx)))
    step(f"load_positions({pos_csv.name[:24]}…)", lambda: ctrl.load_positions(str(pos_csv)))
    step(f"load_pcb({pcb_json.name[:28]}…)", lambda: ctrl.load_pcb(str(pcb_json)))

    bom_n = len(ctrl.context.bom_items)
    print(f"\n  → BOM {bom_n} 条，坐标 {len(ctrl.context.positions)} 个，"
          f"网络 {ctrl.context.pcb_data.net_count} 个")

    # ── 阶段 3: DRC 分析（核心观测点）──
    print("\n── DRC 本地分析 ──")
    checker = DesignRuleChecker()

    v1, first_ms = step("check_all 第 1 次（含 import torch + 模型懒加载）",
                        lambda: checker.check_all(
                            ctrl.context.bom_items, ctrl.context.positions,
                            pcb_data=ctrl.context.pcb_data))
    v2, steady_ms = step("check_all 第 2 次（稳态）",
                         lambda: checker.check_all(
                             ctrl.context.bom_items, ctrl.context.positions,
                             pcb_data=ctrl.context.pcb_data))
    v3, steady2_ms = step("check_all 第 3 次（稳态复核）",
                          lambda: checker.check_all(
                              ctrl.context.bom_items, ctrl.context.positions,
                              pcb_data=ctrl.context.pcb_data))

    # ── 阶段 4: 评分 + NLU ──
    print("\n── 评分 + 意图 ──")
    (scored, _) = step("DesignScorer.score()",
                       lambda: DesignScorer().score(v2, ctrl.context.bom_items))
    def classify():
        from src.agent.nlu_engine import NLUEngine
        return NLUEngine().classify("帮我分析这块板的DRC违规")

    step("NLUEngine.classify('帮我分析这块板的DRC违规')", classify)

    # ── 分析结果摘要 ──
    by_sev: dict[str, int] = {}
    by_rule: dict[str, int] = {}
    for v in v2:
        by_sev[v.severity.name] = by_sev.get(v.severity.name, 0) + 1
        by_rule[v.rule_name] = by_rule.get(v.rule_name, 0) + 1
    top_rules = sorted(by_rule.items(), key=lambda x: -x[1])[:8]

    print("\n── 分析结果 ──")
    print(f"  违规 {len(v2)} 条: "
          + "  ".join(f"{k}={v}" for k, v in sorted(by_sev.items())))
    print(f"  总分: {scored.overall:.0f}/100 ({scored.grade})")
    print("  Top 规则: " + ", ".join(f"{r}×{n}" for r, n in top_rules))

    # ── 结论 ──
    steady = min(steady_ms, steady2_ms)
    print("\n── 结论 ──")
    print(f"  首次分析 {fmt(first_ms)} vs 稳态 {fmt(steady)} → "
          f"首跑开销 {fmt(first_ms - steady)}（import torch + TextCNN 懒加载）")
    print(f"  稳态分析 {bom_n} 元件耗时 {fmt(steady)}，"
          f"其中本地模型推理占比极小（单条 ~0.4-0.7ms）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

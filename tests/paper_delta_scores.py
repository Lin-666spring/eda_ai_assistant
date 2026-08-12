"""闭环前后综合评分 Δ 分析 — 论文核心指标（2026-08-03 新增）。

背景：设计评分（DesignScorer）是"板子质量"属性，本身不构成系统贡献。
真正衡量系统能力的是闭环前后 Δ：同一块板，AI 建议应用前 vs 应用后的综合评分变化。
正 Δ = 闭环验证实际提升了设计质量；负 Δ = 建议引入了新问题（被 DRC 拦截）。

用法：
    python tests/paper_delta_scores.py --designs          # 4 真实板基线评分（无 LLM）
    python tests/paper_delta_scores.py --experiments run  # 分析已有 Phase B 结果（需重跑后含 Δ）
    python tests/paper_delta_scores.py --experiments run --designs --markdown out.md
"""

import argparse
import glob
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.controller import AppController
from src.core.design_scorer import DesignScorer
from src.rules.checker import DesignRuleChecker

REAL_BOARDS = [
    ("bldc_esc_motor", "无刷电调 (BLDC ESC)"),
    ("dcdc_power_v62", "DC-DC 电源板 v6.2"),
    ("esp32_audio_moji2", "ESP32 音频模块"),
    ("stm32f103_devboard", "STM32F103 开发板"),
]

CATEGORY_LABELS = {"safe": "安全", "dangerous": "危险", "optimization": "优化", "?": "?"}


def load_real_bom(board: str):
    bom = glob.glob(str(PROJECT_ROOT / "test_data/pcb_designs" / board / "BOM*.xlsx"))
    if not bom:
        return None, None
    ctrl = AppController()
    ctrl.load_bom(bom[0])
    return ctrl.context.bom_items, ctrl.context.positions


def score_design(bom_items, positions=None):
    violations = DesignRuleChecker().check_all(bom_items, positions, pcb_data=None)
    rep = DesignScorer().score(violations, bom_items, positions)
    return rep, violations


def baseline_table() -> list[dict]:
    """4 块真实板 DRC 基线评分（数据集画像，纯规则引擎，无 LLM）。"""
    print("━" * 72)
    print("  4 块真实板 DRC 基线评分（数据集画像 — 实验设置参考，非系统贡献）")
    print("━" * 72)
    header = (f"  {'板子':<20}{'违规':>4}{'综合':>7}{'等级':>4}"
              f"  power signal thermal   emc   dfm  cost")
    print(header)
    rows = []
    for board, label in REAL_BOARDS:
        bom_items, positions = load_real_bom(board)
        if bom_items is None:
            print(f"  ⚠️ {board}: 未找到 BOM，跳过")
            continue
        rep, violations = score_design(bom_items, positions)
        d = rep.dimensions
        rows.append({
            "board": board, "label": label, "violations": len(violations),
            "overall": rep.overall, "grade": rep.grade,
            "power": d["power"].score, "signal": d["signal"].score,
            "thermal": d["thermal"].score, "emc": d["emc"].score,
            "dfm": d["dfm"].score, "cost": d["cost"].score,
        })
        print(f"  {board:<20}{len(violations):>4}{rep.overall:>7.1f}{rep.grade:>4}"
              f"  {d['power'].score:>5.0f} {d['signal'].score:>6.0f} {d['thermal'].score:>7.0f}"
              f" {d['emc'].score:>5.0f} {d['dfm'].score:>5.0f} {d['cost'].score:>5.0f}")
    if rows:
        avg = sum(r["overall"] for r in rows) / len(rows)
        print(f"\n  平均综合评分: {avg:.1f} / 100")
    return rows


def analyze_experiments(dirpath: str):
    """分析 Phase B 结果中的闭环前后 Δ（需重跑后含 delta_score 字段）。"""
    results_path = Path(dirpath) / "results.json"
    if not results_path.exists():
        print(f"❌ 未找到 {results_path}")
        return None
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)
    verify = data.get("verify_results", [])
    if not verify:
        print("⚠️ 无 verify_results。")
        return None

    has_delta = any(v.get("delta_score") is not None for v in verify)
    print("━" * 72)
    print(f"  闭环前后综合评分 Δ — {Path(dirpath).name}")
    print("━" * 72)
    print(f"  {'设计':<20}{'建议类型':<10}{'结果':>3}{'轮次':>4}  {'基线分':>7}{'最终分':>7}{'Δ':>7}  {'避免损失':>7}")
    if not has_delta:
        print("  ⚠️ 旧格式数据（无 Δ 字段）——需重新跑 Phase B 实验。baseline 离线可算，final 需重跑。")

    deltas = []
    prevented = []
    for v in verify:
        b = v.get("baseline_score")
        d = v.get("delta_score")
        f = v.get("final_score")
        rp = v.get("risk_prevented")
        status = "✅" if v.get("accepted") else "❌"
        if b is None:
            continue
        d_str = f"{d:+.1f}" if d is not None else "  —"
        f_str = f"{f:.1f}" if f is not None else "  —"
        rp_str = f"{rp:.1f}" if rp else "  —"
        print(f"  {v['design']:<20}{CATEGORY_LABELS.get(v.get('suggestion_category','?'),'?'):<10}"
              f"{status:>3}{v.get('rounds', 0):>4}  {b:>7.1f}{f_str:>7}{d_str:>7}  {rp_str:>7}")
        if d is not None:
            deltas.append(d)
        if rp:
            prevented.append(rp)

    if deltas:
        n_up = sum(1 for d in deltas if d > 0.5)
        n_down = sum(1 for d in deltas if d < -0.5)
        n_same = len(deltas) - n_up - n_down
        print(f"\n  平均 Δ: {sum(deltas)/len(deltas):+.1f}"
              f"  | 提升 {n_up} / 恶化 {n_down} / 无变化 {n_same}")
        if prevented:
            print(f"  🛡️ DRC 守门：{len(prevented)} 条危险建议被拦截，"
                  f"避免综合评分损失 共 {sum(prevented):.1f} 分（平均 {sum(prevented)/len(prevented):.1f}/条）")
        by_cat: dict[str, list[float]] = {}
        for v in verify:
            if v.get("delta_score") is None:
                continue
            cat = v.get("suggestion_category", "?")
            by_cat.setdefault(cat, []).append(v["delta_score"])
        for cat, ds in by_cat.items():
            print(f"    {CATEGORY_LABELS.get(cat, cat):<8}: {sum(ds)/len(ds):+.1f} (n={len(ds)})")
    return {"deltas": deltas, "prevented": prevented}


def to_markdown(baseline_rows: list[dict], result, out_path: str):
    """生成论文用 markdown 表格。"""
    md = [
        "# 闭环验证评分 Δ 实验数据",
        "",
        f"> 生成: 2026-08-03 | 指标: DesignScorer 综合评分 (0-100) 前后对比",
        "",
    ]
    if baseline_rows:
        md += [
            "## 数据集画像（4 真实板 DRC 基线）",
            "",
            "| 板子 | 元件数 | 违规数 | 综合评分 | 等级 | power | signal | thermal | emc | dfm | cost |",
            "|------|--------|--------|----------|------|-------|--------|---------|-----|-----|------|",
        ]
        for r in baseline_rows:
            md.append(
                f"| {r['board']} | - | {r['violations']} | {r['overall']:.1f} | {r['grade']} | "
                f"{r['power']:.0f} | {r['signal']:.0f} | {r['thermal']:.0f} | "
                f"{r['emc']:.0f} | {r['dfm']:.0f} | {r['cost']:.0f} |"
            )
        md.append("")
    deltas = (result or {}).get("deltas", [])
    prevented = (result or {}).get("prevented", [])
    if deltas:
        md += [
            "## 闭环前后 Δ（Phase B）",
            "",
            "| 指标 | 值 | 论文目标 |",
            "|------|-----|----------|",
            f"| 平均 Δ | {sum(deltas)/len(deltas):+.1f} | > 0（正=质量提升） |",
            f"| 提升建议数 | {sum(1 for d in deltas if d > 0.5)} | - |",
            f"| 恶化建议数 | {sum(1 for d in deltas if d < -0.5)} | 少（被 DRC 拦截） |",
            "",
        ]
        if prevented:
            md += [
                "## DRC 守门价值（risk_prevented）",
                "",
                "> 被拒绝的危险建议本会造成评分下降，DRC 拦截后设计保持基线（Δ=0）。",
                "> risk_prevented = 被避免的质量损失。",
                "",
                "| 指标 | 值 |",
                "|------|-----|",
                f"| 拦截危险建议数 | {len(prevented)} |",
                f"| 避免质量损失总计 | {sum(prevented):.1f} 分 |",
                f"| 平均每次拦截避免 | {sum(prevented)/len(prevented):.1f} 分 |",
                "",
            ]
    else:
        md += ["## 闭环前后 Δ（Phase B）", "", "> 需重新运行 Phase B 实验后生成（含 baseline/final/delta_score 字段）。", ""]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


def main():
    parser = argparse.ArgumentParser(description="闭环前后评分 Δ 分析")
    parser.add_argument("--experiments", type=str, default=None, help="实验目录（含 results.json）")
    parser.add_argument("--designs", action="store_true", help="4 真实板基线评分（无 LLM）")
    parser.add_argument("--markdown", type=str, default=None, help="输出 markdown 文件路径")
    args = parser.parse_args()

    baseline_rows = None
    deltas = None
    if args.designs:
        baseline_rows = baseline_table()
    if args.experiments:
        deltas = analyze_experiments(args.experiments)
    if args.markdown:
        to_markdown(baseline_rows or [], deltas, args.markdown)
        print(f"📄 已输出: {args.markdown}")


if __name__ == "__main__":
    main()

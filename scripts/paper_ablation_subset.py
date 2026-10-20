# -*- coding: utf-8 -*-
"""受控 2×2 消融实验驱动 —— 论文 R3 增强路径（修法指引 × 撤销语义）。

四臂（同期、同 21 板分层子集、同模型 glm-5.3-flash、同规则版本）：
  A_full       修法指引+ 撤销语义+   （完整闭环，等于主实验口径）
  B_noguid     修法指引- 撤销语义+   （反馈只含违规名+描述，无修法行）
  C_norevert   修法指引+ 撤销语义-   （无撤销授权；空变更集被机制拒绝）
  D_neither    修法指引- 撤销语义-

子集与跨模型实验完全一致（stratified_sample(20, seed=2026) → 21 板），
仅跑阶段 B 闭环（不跑多智能体/缺陷注入），逐条 checkpoint 崩溃安全。

用法:
  python scripts/paper_ablation_subset.py                 # 四臂顺序跑
  python scripts/paper_ablation_subset.py --arms A_full   # 只跑一臂
输出: experiment_results/ablation2x2_<arm>_<ts>/results.json + arm_config.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

ARMS = {
    "A_full":     {"guidance": True,  "revert": True},
    "B_noguid":   {"guidance": False, "revert": True},
    "C_norevert": {"guidance": True,  "revert": False},
    "D_neither":  {"guidance": False, "revert": False},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(ARMS),
                    help="逗号分隔的臂名，默认四臂全跑")
    args = ap.parse_args()
    arm_names = [a.strip() for a in args.arms.split(",") if a.strip()]
    for a in arm_names:
        if a not in ARMS:
            print(f"❌ 未知臂名: {a}（可选: {', '.join(ARMS)}）")
            sys.exit(1)

    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "glm-5.3-flash")
    if not api_key:
        print("❌ 未配置 LLM_API_KEY（.env）")
        sys.exit(1)

    from paper_multimodel_subset import stratified_sample
    designs = stratified_sample(20)
    print(f"[ablation] 同期子集 {len(designs)} 板（与跨模型实验同子集 seed=2026）")

    from tests.paper_experiments import ExperimentRunner, DesignSpec, ProviderConfig

    root = ROOT / "test_data/thing_designs"
    for arm in arm_names:
        flags = ARMS[arm]
        out_dir = ROOT / "experiment_results" / (
            "ablation2x2_" + arm + "_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        runner = ExperimentRunner(output_dir=out_dir)
        runner.ablation = dict(flags)
        added = 0
        for name in designs:
            bom_files = [f for f in (root / name).glob("*.xlsx") if "BOM" in f.name.upper()]
            if not bom_files:
                print(f"  [SKIP] {name}: 无 BOM xlsx")
                continue
            runner.add_design(DesignSpec(name=name, bom_path=bom_files[0],
                                         description=f"消融臂 {arm}: {name}"))
            added += 1
        runner.add_provider(ProviderConfig(name="glm", api_key=api_key,
                                           model=model, base_url=base_url))
        (out_dir / "arm_config.json").write_text(json.dumps(
            {"arm": arm, "flags": flags, "model": model, "designs": added,
             "started": datetime.now().isoformat()},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[RUN] arm={arm} flags={flags} designs={added} → {out_dir.name}")
        # 只跑阶段 B：直接逐设计/逐建议调 _run_closed_loop（跳过多智能体与注入）
        for design in runner.designs:
            for suggestion in runner.suggestions:
                result = runner._run_closed_loop(design,
                                                 runner.providers[0], suggestion)
                runner.verify_results.append(result)
                runner._print_verify_result(result)
                runner._checkpoint()
        runner._save_results()
        n_conv = sum(1 for r in runner.verify_results if r.converged)
        n_rev = sum(1 for r in runner.verify_results
                    if r.converged and r.fully_reverted)
        print(f"[DONE] arm={arm}: {len(runner.verify_results)} 条, "
              f"收敛 {n_conv}, 全撤销收敛 {n_rev}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""多模型子集实验驱动 —— 论文 R10 增强（2-3 模型分层子集）。

分层抽样: 按全量实验 79 板的 BOM 规模三分层（小/中/大），各层按比例抽足 20 板，
抽样种子固定 2026，保证两模型看到同一子集、可跨模型直接对比。
用法:
  python scripts/paper_multimodel_subset.py --provider deepseek   # deepseek-flash
  python scripts/paper_multimodel_subset.py --provider qwen       # qwen3.8-max
输出: experiment_results/mm20_<provider>_<ts>/results.json + summary.md
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

PROVIDERS = {
    "deepseek": dict(
        env_key="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        name="deepseek",
    ),
    "qwen": dict(
        env_key="QWEN_API_KEY",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen3.8-max",
        name="qwen",
    ),
}

# 全量实验 79 板（run_thing_full_glm53 的 drc_results 设计名）与 BOM 规模分层


def load_full_designs():
    d = json.loads((ROOT / "experiment_results/run_thing_full_glm53/results.json").read_text(encoding="utf-8"))
    return sorted(set(r["design"] for r in d["drc_results"]))


def stratified_sample(n_target: int = 20, seed: int = 2026):
    import openpyxl
    full = load_full_designs()
    root = ROOT / "test_data/thing_designs"
    sizes = {}
    for name in full:
        xl = sorted((root / name).glob("BOM*.xlsx"))
        if not xl:
            continue
        try:
            wb = openpyxl.load_workbook(xl[0], read_only=True)
            ws = wb.active
            rows = [r for r in ws.iter_rows(values_only=True) if any(r)]
            wb.close()
            sizes[name] = max(0, len(rows) - 1)  # 粗计器件行数
        except Exception:
            sizes[name] = 0
    # 三分层: 小/中/大 按 BOM 行数排序切三份，按层比例分配名额
    names = sorted(sizes, key=lambda k: sizes[k])
    tiers = [names[:len(names) // 3],
             names[len(names) // 3: 2 * len(names) // 3],
             names[2 * len(names) // 3:]]
    rng = random.Random(seed)
    picked = []
    quota = [round(len(t) / len(names) * n_target) for t in tiers]
    while sum(quota) < n_target:
        quota[1] += 1  # 中层多一席
    for t, q in zip(tiers, quota):
        picked += rng.sample(t, min(q, len(t)))
    return sorted(picked)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), required=True)
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()

    cfg = PROVIDERS[args.provider]
    api_key = os.getenv(cfg["env_key"], "")
    if not api_key:
        print(f"❌ 未配置 {cfg['env_key']}")
        sys.exit(1)

    designs = stratified_sample(args.n)
    print(f"[{args.provider}] 分层子集 {len(designs)} 板:")
    for i, dname in enumerate(designs, 1):
        print(f"  {i:2d}. {dname}")

    # 环境变量覆盖 → paper_experiments.get_provider_from_env() 读取
    os.environ["LLM_API_KEY"] = api_key
    os.environ["LLM_BASE_URL"] = cfg["base_url"]
    os.environ["LLM_MODEL"] = cfg["model"]
    os.environ["LLM_PROVIDER"] = cfg["name"]

    from tests.paper_experiments import ExperimentRunner, DesignSpec, ProviderConfig

    root = ROOT / "test_data/thing_designs"
    runner = ExperimentRunner(output_dir=ROOT / "experiment_results" / (
        "mm20_" + cfg["name"] + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")))
    added = 0
    for name in designs:
        bom_files = [f for f in (root / name).glob("*.xlsx") if "BOM" in f.name.upper()]
        if not bom_files:
            print(f"  [SKIP] {name}: 无 BOM xlsx")
            continue
        runner.add_design(DesignSpec(name=name, bom_path=bom_files[0],
                                     description=f"多模型子集: {name}"))
        added += 1
    runner.add_provider(ProviderConfig(name=cfg["name"], api_key=api_key,
                                       model=cfg["model"], base_url=cfg["base_url"]))
    print(f"[RUN] provider={cfg['name']} model={cfg['model']} designs={added}")
    runner.run_all()


if __name__ == "__main__":
    main()

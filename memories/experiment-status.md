# 真实 PCB 数据集实验 — 状态与复现

> 2026-09-13 完成

## 数据集

- 来源 thing.zip（微信），原始 91 个目录，按 BOM 指纹去重 → 79 个唯一设计
- 归一化目录：test_data/thing_designs/，清单 _manifest.csv（含源目录索引）
- 每个设计：BOM xlsx + PickAndPlace（xlsx/csv）+ Netlist .tel + FlyingProbeTesting（zip/含 PCB json）
- 原始解包（gitignore）：test_data/_incoming_thing/（4.4 MB）

## 完成结果

- experiment_results/run_thing_drc_full/：阶段 A + D（79/79）
- experiment_results/run_thing_full_glm53/：阶段 A/B/C/D 全量
  - 阶段 B：395/395（79×5 建议），0 错误；阶段 C：79/79；阶段 D：280 缺陷注入
- 关键指标：BOM 收敛率 94%、幻觉消除率 100%、平均修正轮次 1.5、多智能体均分 94、缺陷检出 268/280（96%）

## 复现命令

  # DRC 基线（无 LLM）
  python tests/real_pcb_experiment.py --drc-only --base-dir test_data/thing_designs --output experiment_results/xxx

  # 全量（GLM-5.3-Flash，走 .env 的 bigmodel key）
  set LLM_MODEL=glm-5.3-flash ; python tests/real_pcb_experiment.py --base-dir test_data/thing_designs --output experiment_results/xxx

  # 进度监控
  python scripts/thing_progress.py experiment_results/xxx

## 费用（2026-09-13）

- GLM：973 次调用，2,105,910 tokens（输入 70 万 / 输出 141 万）≈ ¥2.9
- 重要：coding plan 只有 500 万，实际用量 210 万 → 其实够用，别再误判
- DeepSeek（编排）：当日 ¥2.27，余额约 ¥5.2

## 已改的代码

- src/agent/llm_client.py：新增 get_total_usage() 进程级 token 统计
- tests/paper_experiments.py：每条结果增量落盘 _checkpoint() + summary 输出 llm_usage
- tests/real_pcb_experiment.py：新增 --base-dir

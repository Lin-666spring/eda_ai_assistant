# 真实 PCB 数据集实验 — 状态与复现

> 2026-09-13 完成（thing_designs）；2026-09-15 新增 .epro2 数据集

## 数据集二：.epro2（2026-09-15）

来源 `78.zip`（微信）→ 78 个 `.epro2`，按设计指纹去重 **76 个唯一设计**。
解包：`test_data/_incoming_epro2/`（gitignore）。

每个 `.epro2` = BOM + 网表 + 坐标 + 走线/过孔/覆铜（四种导出的超集）。

- 清单：`experiment_results/epro2_dataset/`（manifest.json/csv + summary.txt）
- 合计：10273 网络 / 44047 引脚 / 14811 走线折线 / 37807 过孔 / 1317 覆铜 /
  11437 元件 / 4180 BOM 行；解析 12.4s
- 交叉验证：`experiment_results/epro2_validation/3M_V14.txt`
  （元件 947/947、网络 667/667 引脚集合、BOM 885=885 位号，全部完全一致）
- **规则覆盖率（零 LLM）**：`experiment_results/epro2_rule_coverage/`

  | 配置 | 可判定 | 有输出 |
  |---|---|---|
  | 旧口径（BOM+坐标） | 50/71 | 39/71 |
  | +PCB 元件/网络 | 56/71 | 45/71 |
  | **全量 .epro2** | **71/71** | **60/71** |

- **走线类阈值校准（2026-09-15，零 LLM）**：`experiment_results/trace_threshold_calibration/`
  - `report.txt` 原始度量分位数，`metrics.json` 每设计明细，`coverage_before_after.txt` 前后对比
  - 信号线宽改为**上下文感知两级判据**：细于 0.1mm(4mil) 工艺下限 **或** 细于本板信号线宽众数×0.6；
    （固定 0.127mm 会把整板用 4.8mil 的立创泰山派3M 一次报 501 条）
  - 过孔密度改为**仅高速网络**；板边间距改用**真实板框**（原实现拿绝对坐标当板边，是 bug）；
    差分对改用工程 NET 规则分组；3W 串扰加**平行重叠 ≥5mm** 门限
  - C3 违规总数 **8394 → 4000（-52%）**，可判定/有输出口径均不变
  - 单测：`tests/test_pcb.py::TestCalibratedTraceRules`（15 项）

复现（均零 API 成本）：

```bash
python scripts/build_epro2_dataset.py test_data/_incoming_epro2
python scripts/epro2_rule_coverage.py test_data/_incoming_epro2
python scripts/calibrate_trace_thresholds.py test_data/_incoming_epro2
python scripts/validate_epro2_vs_exports.py --epro2 <某.epro2> --exports <同工程导出目录>
python -m pytest tests/test_epro2_parser.py tests/test_pcb.py -q
```

## 数据集一：thing_designs（2026-09-13）

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

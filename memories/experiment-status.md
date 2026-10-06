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

  （上表是 2026-09-15 的数字；此后判据修了两轮，最新见下方「覆盖率复测」）

- **覆盖率复测（2026-10-06，netlist 契约修复后，零 LLM）**：`experiment_results/epro2_rule_coverage_after_netlist/`
  - 口径 A（可判定）**71/71**；口径 B（有输出，C3）**57/71 = 80.3%，违规 3241**（上一轮 3293）；
    口径 B′（判定类）**43/57 = 75.4%**，判定类违规 2304 / 提示类 937
  - 与上一轮相比唯一变化：`未连接引脚检查` **58 → 6 条** —— 10-02 把「数有多少条网络提到该位号」
    改成「按 `位号.` 前缀数真实引脚」后，这条规则首次在软件口径生效（旧写法 connected 恒为 0）
  - `rule_errors` 两轮均为空：没有静默失效的规则（`_check_impedance_matching` 缺 import 那类事故不再复发）
  - 完整数字：该目录 `report.txt` / `coverage.json`；逐规则变化可用 `--out` 跑两次后对比 coverage.json

- **规则抽查第二轮（2026-10-06，零 LLM）**：`experiment_results/rule_spotcheck_2026-10-06/`（报告：[docs/规则抽查_报告_2026-10-06.md](../docs/规则抽查_报告_2026-10-06.md)）
  - 样本池 3241 条（第一轮 5769）；分层抽样 144 条（走线类 5/规则、其它 2/规则，seed 20260918），
    判读由 5 个独立子任务逐条回原始 `.epro2` 核实
  - **结果：总体精确率 6.5%（95% CI 3.0~13.5%），走线类 10.8%，非走线类 3.6%；GEN 29.9%、UNC 9 条**
  - **与第一轮对比：违规量 −44%，精确率 7.7% → 6.5%（CI 重叠，未见提升）** ——
    修复压掉的是噪声的「量」，没有改善剩余违规的「有效性」
  - 精确率仍低的根因（判读逐条核实）：用「存在性/子串」代替网表判据（BOM 描述里有没有「电阻」字样）、
    坐标系不减板框原点、硬编码参数（h=0.2mm/板面积 5000mm²）、阈值实现与描述不符、
    以及 4 个明确代码 bug（见报告 §4，含 `PCBVia` 只有 `position` 导致拐角规则的过孔锚点恒为空）
  - `microstrip_impedance` 窄线分支公式偏低约 2×（0.1524mm/0.2mm：40.9Ω vs IPC-2141 72.7Ω）——
    阻抗类违规的结论方向会反，修公式后需复算

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

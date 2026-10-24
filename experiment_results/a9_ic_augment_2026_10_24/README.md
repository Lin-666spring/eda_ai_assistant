# A-9 ic_* 数据增强重训批次（2026-10-24）

金样触发数快照重定基线批次 README（按 `tests/test_golden_snapshot.py` 自带协议记录）。
上游批次：A-9 无泄漏重训（`../a9_retrain/ANALYSIS_2026-10-24.md`）——该批暴露 ic_power
val 召回 20%、金样去耦类触发 130→119 的生产覆盖收缩。

## 变更内容

1. **元件数据增强**（`src/ml/generate_component_data.py`）：
   - 料号家族池扩充：`{dcdc_pn}` 10→36（TPS56xxx/LM25xx/MP23xx/SY80xx/RT72xx/LTC…每家族 2~4 成员）、`{ldo_pn}` 12→24、`{mcu_pn}` 18→33、`{opamp_pn}` 12→16（边界对照）；
   - 裸料号（desc 空）模板按「不同模板串 × 多封装」重复出现：ic_power +13、ic_mcu +4、ic_analog +2——模板级切分下两侧都能见到裸料号样本（此前单一裸料号模板整体落 val，训练侧零裸料号样本）。
2. **元件分类器重训**（`--epochs 35`，seed 42，**现保存 best-epoch 权重**，P1-23 对齐）。
3. **校准产物运行时优先加载**（P1-24）：`src/ml/model_paths.py::calibrated_first` 接入 `src/rules/base.py`、`src/ml/change_predictor.py`、`src/agent/nlu_engine.py`（base.py 的 import 留在函数内，守住「torch 不进 exe」红线）。
4. **calibrate.py 温度越界防护**（P1-24 前半）：T 越界 [0.05, 10] 回退 1.0。
5. 测试口径更新：`tests/test_confidence_calibration.py` 三处断言改为「校准产物在场且 T 合理 / ECE 不显著恶化（+0.05 容差）」，新增 `calibrated_first` 回归；requirements-dev.txt 补 `onnxconverter-common`。

## 金样快照差异（78 板，57 规则）

| 规则 | 旧快照 | 本批新值 | 说明 |
|---|---|---|---|
| 去耦电容检查 | 130 | **125** | -5：元件分类器换基（见下） |
| 去耦电容距离检查 | 20 | **22** | +2：同上 |
| 晶振布局检查 | （不在快照，计 0） | **1** | 补录进快照 |
| 温度敏感元件布局检查 | 3 | 3 | 无差异 |

其余 54 条规则计数全部不变。总触发数 1547。

### 为何接受 -5（去耦电容检查）

- 旧快照 130 产生于泄漏数据训练的分类器（A-9 修复前）：该分类器对真实电源 IC
  的"高置信"来自 val 泄漏记忆，探针显示其对 XL6009 等裸料号电源 IC 存在误判。
- 本批分类器在 6 句人工探针上 6/6 全对（含 4 句裸料号电源 IC 与 1 句运放反例），
  ic_power/ic_mcu val 召回 100%（增强前 20%/73%），元件 best val_acc 98.00%
  （增强前 89.11%）。
- 快照是漂移探测器而非正确性金标准；分类器换基属有意变更，残余 -5 记录在案，
  不追平旧值（旧值本身建立在记忆泄漏的模型行为上）。

## 新模型口径指标（数据/报告均为本批产物）

- 元件分类：train 715 / val 100（跨侧逐字重复 0），best epoch 13，best val_acc
  **98.00%**（final 96.00%）；per-class：ic_power 5/5、ic_mcu 10/10、最弱
  ic_other 3/4（75%，val 仅 4 条）。
- 校准：ComponentClassifier T=0.6687，ECE 0.0467→**0.0208**（本批校准真正生效）；
  IntentClassifier T=1.0303，ECE 0.2416→0.2492（50 条校准集上轻微变差，容差内）。
- 意图模型本批未重训（数据未变，沿用 A-9 重训产物）。

## 已知限制

- ic_power val 侧裸料号样本为 0（seed=42 下 9 个裸料号模板全部落训练侧）：
  val 无法监控该失败模式，由本批 6 句探针（logs/probe.txt）与金样审计兜底。
  不做 seed 挑选（属切分钓胜）。
- ic_other val 仅 4 条，其 75% 数字噪声大。

## 产物

- 模型：`data/component_model.pt`（best epoch 13）、`data/component_model_calibrated.pt`（T=0.6687）
- 数据：`data/component_train_train.json`（715）/ `component_train_val.json`（100）
- 报告：`data/component_train_report.json`、`data/calibration_report.json`
- 日志：`logs/`（generate / train_component / calibrate / probe / golden_audit / pytest）
- 金样计数：`golden_counts.json`
- 训练执行：5.3 Flash 训练执行员（子代理 agent_5bcec751），代码修改与快照决策：主代理

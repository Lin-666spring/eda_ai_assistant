# A-9 修复后重训练执行汇总（subagent）

- 执行日期：2026-10-24（10:55–11:05 +08:00）
- 工作目录：`C:\Users\ASUS\Desktop\eda_ai_assistant`
- Python：`.venv\Scripts\python.exe`（3.13.9，torch 2.14.1+cpu）
- 训练数据：直接使用 `data/` 下现有无泄漏新数据（未重新生成、未修改）
- 四个步骤全部执行完毕；除下述 BERT 首次尝试因缺依赖失败外，其余一次成功。
- 所有数字取自各报告 JSON（非日志目测），日志为 stdout+stderr 全量落盘。

---

## 1) TextCNN 意图分类（IntentClassifier）

| 项 | 值 |
|---|---|
| 命令 | `.venv/Scripts/python.exe src/ml/train_intent.py --eval-set data/nlu_eval.json`（超参全为脚本默认：25 epochs / batch 32 / lr 1e-3 / seed 42） |
| 退出码 / 耗时 | 0 / 9 s（10:55:31–10:55:40） |
| 日志 | `experiment_results/a9_retrain/logs/train_intent.log` |
| 样本数 | train 600 / val 50（eval 84） |
| best epoch | 11 |
| best val_acc | 0.8000（`data/nlu_train_report.json` → training.best_val_acc） |
| final val_acc | 0.8000（results.val_acc_final） |
| eval-set acc | 0.9762（82/84，`results.eval_set.accuracy`；错 2 条：『BOM里有多少个电阻』→COMPONENT_LOOKUP、『怎么提高EMC性能』→PCB_ANALYSIS） |
| ECE 前后 | 0.2416 → 0.2492（`data/calibration_report.json` IntentClassifier，T=1.0303，ece_reduction=-0.0076） |
| 异常 | 无 |

报告：`data/nlu_train_report.json`（timestamp 2026-10-24T10:55:40.168232）。

## 2) BERT 意图分类（rbt3，fp16 ONNX）

| 项 | 值 |
|---|---|
| 命令 | `.venv/Scripts/python.exe src/ml/train_intent_bert.py --epochs 20 --patience 6`（显式对齐旧基线；脚本默认 15/4 未使用） |
| 尝试 1 | **失败**：exit 1，171 s。训练与校准完成后在 fp16 ONNX 导出处崩溃：`ModuleNotFoundError: No module named 'onnxconverter_common'`（`src/ml/train_intent_bert.py:354`）。traceback 保留于 `experiment_results/a9_retrain/logs/train_intent_bert.attempt1_failed.log`；当时 `data/intent_bert_train_report.json` 未更新（仍为 2026-10-14）。 |
| 处置 | 向 `.venv` 安装脚本 fp16 导出路径必需的训练期依赖 `onnxconverter-common 1.16.0`（`pip install onnxconverter-common`；requirements.txt 未列出该包）。未改动 src/ 代码、数据与 baseline。 |
| 尝试 2（最终） | **成功**：exit 0，180 s（后台运行+轮询）。完成标志双满足：退出码 0 且 `data/intent_bert_train_report.json` 时间戳更新为 2026-10-24T11:03:59。 |
| 日志 | `experiment_results/a9_retrain/logs/train_intent_bert.log`（attempt 2 全量覆盖；attempt 1 见 attempt1_failed.log） |
| 样本数 | train 600 / val 50 / eval 84（日志首行 `数据：train=600 val=50 eval=84`） |
| best epoch | 11（best_val_acc 0.7600；patience 6 于 epoch 17 早停，stopped_early=true） |
| final val_acc | 0.7600（results.val_acc） |
| eval-set acc | 0.9762（82/84，results.eval_acc） |
| ECE 前后 | 0.2318 → 0.2677（脚本内置 Temperature Scaling，T=0.95，报告 calibration 字段） |
| ONNX parity | n=134，argmax_agreement=1.0，max_prob_diff=0.001322（fp16）——通过脚本内部门槛（≥0.995 且 ≤0.01），产物落盘 `data/models/intent_bert/model.onnx`（77.0 MB，11:03:57） |

报告：`data/intent_bert_train_report.json`（config: epochs 20 / batch 16 / lr 2e-05 / patience 6 / seed 42 / cpu / fp16）。

## 3) TextCNN 元件分类（ComponentClassifier）

| 项 | 值 |
|---|---|
| 命令 | `.venv/Scripts/python.exe src/ml/train_component.py --epochs 35`（显式对齐旧基线；脚本默认 30 未使用） |
| 退出码 / 耗时 | 0 / 17 s（11:04:49–11:05:06） |
| 日志 | `experiment_results/a9_retrain/logs/train_component.log` |
| 样本数 | train 724 / val 101 |
| best epoch | 10 |
| best val_acc | 0.8911（training.best_val_acc） |
| final val_acc | 0.8812（results.val_acc_final） |
| eval-set acc | 无（报告无 eval_set 字段，脚本未提供固定评估集评估） |
| ECE 前后 | 0.0688 → 0.0716（`data/calibration_report.json` ComponentClassifier，T=1.3295，ece_reduction=-0.0028） |
| 附注 | 细粒度→粗粒度映射准确率 88.12%（日志 + per_class） |

报告：`data/component_train_report.json`（timestamp 2026-10-24T11:05:06.563850）。

## 4) 重校准（calibrate.py --model both）

- 命令：`.venv/Scripts/python.exe src/ml/calibrate.py --model both`
- 退出码 / 耗时：0 / 3 s
- 日志：`experiment_results/a9_retrain/logs/calibrate.log`
- 产物：`data/calibration_report.json`（11:05:17）；`data/intent_model_calibrated.pt`（11:05:18）、`data/component_model_calibrated.pt`（11:05:19）均重写，与新模型 `intent_model.pt`（10:55:40）、`component_model.pt`（11:05:06）一致。
- 结果（校准不改变 argmax，acc 前后相同）：

| 模型 | acc | ECE 前 | ECE 后 | Δ |
|---|---|---|---|---|
| IntentClassifier | 0.8000 | 0.2416 | 0.2492 | -0.0076（ECE 略升） |
| ComponentClassifier | 0.8812 | 0.0688 | 0.0716 | -0.0028（ECE 略升） |

---

## 异常与如实记录

1. **BERT 步骤首次尝试失败**：`ModuleNotFoundError: No module named 'onnxconverter_common'`（`src/ml/train_intent_bert.py:354`，fp16 导出路径）。该依赖为脚本必需但 requirements.txt 未列出、venv 中缺失。已通过 `pip install onnxconverter-common`（1.16.0）修复环境后原命令重跑成功；未修改任何代码/数据/备份。traceback 关键行：
   ```
   File "src/ml/train_intent_bert.py", line 354, in export_onnx
       import onnxconverter_common.float16 as float16
   ModuleNotFoundError: No module named 'onnxconverter_common'
   ```
2. **ECE 校准后不降反升（3 处）**：意图 TextCNN 0.2416→0.2492（-0.0076）、元件 TextCNN 0.0688→0.0716（-0.0028）、BERT 内置校准 0.2318→0.2677。均按报告 JSON 原值如实记录；这是小验证集上 Temperature Scaling 的实际结果，非脚本执行失败。
3. 未运行 pytest（按指令由主流程统一执行）。

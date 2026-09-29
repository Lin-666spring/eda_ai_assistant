# 会话小结 — 2026-09-18（规则抽查）

主题：**给 61/71「有输出」口径做分层抽查，量出精确率与误报模式**（审计待办：走线类规则正确性）。

## 做了什么

1. 新增 5 个零 LLM/零网络脚本（scripts/）：`rule_spotcheck_dump.py`（导出 5769 条违规 + 判读证据）、
   `rule_spotcheck_sample.py`（按规则分层抽样，走线类 5 条/规则、其它 2 条，共 150 条）、
   `rule_spotcheck_preview.py`（UTF-8 紧凑预览）、`rule_spotcheck_judge.py`（合并判读）、
   `rule_spotcheck_score.py`（精确率 + Wilson 区间）。
2. 判读口径四分类：**TP 违规成立 / FP 误报 / GEN 通用提示（非判定）/ UNC 无法定性**；
   每条判读都基于证据字段（线宽按长度分布、拐角角度/腿长/到焊盘距离、串扰线对、差分对整组长度、IPC 载流两种口径）。
3. 用 3 个独立子任务做**代码级核查**（逐条给行号 + 真实数据复现），确认判读依据的是代码真实行为。
4. 产出：`docs/规则抽查_报告_2026-09-18.md`、`experiment_results/rule_spotcheck/`
   （violations.jsonl / sample.csv / judged.jsonl / report.txt / metrics.json）。

## 关键数字（150 条全判读）

| 族 | 样本 | TP | FP | GEN | UNC | 精确率 (95% CI) |
|---|---|---|---|---|---|---|
| 走线类 | 56 | 4 | 32 | 17 | 3 | **11.1%** (4.4~25.3%) |
| 非走线类 | 94 | 3 | 52 | 33 | 6 | **5.5%** (1.8~14.0%) |
| 合计 | 150 | 7 | 84 | 50 | 9 | **7.7%** (3.8~15.0%) |

- 走线类逐规则：电源载流 0/5、信号线宽 0/5、特征阻抗 0/5、短桩 0/5、串扰 0/2(+3 UNC)、
  锐角 0/3、差分等长 2/5、差分间距 2/5；时钟包地/参考平面/环路面积/直角 = 提示类。
- 6 条规则 76/76 板都响，13 条命中 ≥60/76 板，这 13 条占 **3648/5769 = 63%** 的违规。
- 只有 7 条真问题：DVP 组内 DVP_D6 短 2.5mm、DP_LANE0± 偏差 15%、DP5 对内 4.1W 松耦合、
  DA± 5W 松耦合、FLPowerPro 缺 ≥100µF 大电解、热成像晶振负载位上是 1µF、对讲机全板无体电容。

## 确认的规则 bug（详见 memories/audit-findings.md 的 2026-09-18 段）

- P0：电源载流 `is_inner` 是**板级布尔** → 外层线按内层降额（容量腰斩，23/76 板受影响）；
- P0：特征阻抗拿**单端 Z0 比差分目标**（USB 90Ω…），`calculator.py:183` 的 differential_impedance 未用；
- P0：参数范围检查 E24 表 `mantissa*100` 比 `e*10`，**差 10 倍**（20kΩ/22µF/100nF 全误报，779 条）；
- P0：器件分类靠裸子串（XL/SI/MP/PS/LM/AD/SDA/BAT/「功率」）→ 8 条 BOM 类规则系统性误报；
- P1：短桩判据「有过孔即 stub」、信号线宽固定 0.1mm + 众数相对判据、串扰无速率门限且含电源/地线对、
  差分对 0.5mm/3W 不分接口、电容耐压正则抓料号里的 0V、去耦距离把咪头当 IC；
- P2：铜皮连接只在缺数据时报、元件间距取字典邻居、未连接引脚数网络不数引脚、解析器 orphan 丢针。

## 已落地的修复（本轮，经用户确认）

- `src/rules/checker.py` 新增 `_is_inner_layer(pcb, layer)`：层名含 top/bottom 或等于叠层前两层 → 外层，
  其余（Inner*/GND02/S03/PWR05…）→ 内层；`_check_power_traces` 改为「每条网络取最窄走线 + 它自己的层」，
  描述里写明层与内/外层。
- `_check_bom_value_range`：mantissa 归一化到 [1,10)，容差 10% → E24 的 ±5%（10% 会让判据恒真）。
- 新增 `tests/test_rule_fixes.py`（6 例）。

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 参数范围检查 | 779 条 / 73 板 | **4 条 / 4 板**（剩下全是真非标：1.69k/137k/169/16.9k） |
| 电源线载流检查 | 118 条 / 30 板 | **68 条 / 27 板**（且都标了层与内/外层） |
| C3 违规总数 | 5769 | **4944（-14.3%）** |
| 口径 A / 口径 B | 71/71、61/71 | **71/71、61/71**（不受影响） |

- 复现：`python scripts/epro2_rule_coverage.py test_data/_incoming_epro2 --out experiment_results/epro2_rule_coverage_after_fix`
  与 `python scripts/rule_spotcheck_dump.py test_data/_incoming_epro2 --rules _check_power_traces,_check_bom_value_range --out experiment_results/rule_spotcheck_after`。
- 测试：规则相关子集 126 passed（test_rule_fixes/test_rules/test_acute_angle/test_verification_map/
  test_design_scorer/test_pcb/test_tool_catalog）；`test_tool_catalog` 的 sqlite OperationalError 需把
  `USERPROFILE`+`HOME` 指到工作区内且预建 `.eda_ai_assistant` 目录（沙箱限制，非代码问题）。

## 待办

- [ ] 按报告第 6 节「修复顺序」改判据（1、2 两条各 1 行改动，收益最大），改完重跑覆盖率与抽查对比；
- [ ] 覆盖率口径改造：规则加 `kind: detect|advise`，只报判定类覆盖率 + 精确率区间；
- [ ] 论文里把「61/71（有输出）」改写为「判定类覆盖率 + 抽样精确率（含 CI）」；
- [ ] 其余审计待办（实验指标可信度、frontend/ 去留等）不变。

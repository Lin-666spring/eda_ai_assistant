# EI 论文实验报告

> 生成时间: 2026-07-09T10:35:32.844280
> 设计数: 3 | 建议数: 5 | LLM: deepseek

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| STM32_Minimal | 26 | 0 | 8 | 18 | 0.0s |
| Power_Supply | 17 | 0 | 3 | 14 | 0.0s |
| Bad_Design | 18 | 0 | 7 | 11 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 轮次 | 阻断 | 消除率 | 耗时 |
|--------|------|----------|------|------|------|--------|------|
| deepseek | STM32_Minimal | safe | ✅ | 1 | 0 | — | 0.0s |
| deepseek | STM32_Minimal | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | STM32_Minimal | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | STM32_Minimal | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | STM32_Minimal | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Power_Supply | safe | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Power_Supply | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Power_Supply | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Power_Supply | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Power_Supply | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Bad_Design | safe | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Bad_Design | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Bad_Design | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Bad_Design | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | Bad_Design | dangerous | ✅ | 1 | 0 | — | 0.0s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | STM32_Minimal | 85 | B+ | 1 | 13 | 26.8s |
| deepseek | Power_Supply | 94 | A | 1 | 5 | 17.5s |
| deepseek | Bad_Design | 87 | B+ | 1 | 8 | 49.6s |

## 关键指标

- 幻觉消除率: N/A
- 修正成功率: N/A
- **平均迭代轮次**: 1.0 (目标 ≤ 2.0)
- **多智能体均分**: 89/100 (目标 > 75)

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\run_2026-07-09_103358\results.json`
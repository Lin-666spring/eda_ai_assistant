# EI 论文实验报告

> 生成时间: 2026-07-09T10:21:02.511330
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
| deepseek | STM32_Minimal | safe | ❌ | 3 | 24 | 0% | 26.3s |
| deepseek | STM32_Minimal | dangerous | ❌ | 3 | 24 | 0% | 43.6s |
| deepseek | STM32_Minimal | optimization | ❌ | 3 | 24 | 0% | 39.6s |
| deepseek | STM32_Minimal | optimization | ❌ | 3 | 24 | 0% | 34.1s |
| deepseek | STM32_Minimal | dangerous | ❌ | 3 | 24 | 0% | 37.0s |
| deepseek | Power_Supply | safe | ❌ | 3 | 9 | 0% | 21.8s |
| deepseek | Power_Supply | dangerous | ❌ | 3 | 9 | 0% | 60.4s |
| deepseek | Power_Supply | optimization | ❌ | 3 | 9 | 0% | 23.4s |
| deepseek | Power_Supply | optimization | ❌ | 3 | 9 | 0% | 25.2s |
| deepseek | Power_Supply | dangerous | ❌ | 3 | 9 | 0% | 39.2s |
| deepseek | Bad_Design | safe | ❌ | 3 | 21 | 0% | 43.1s |
| deepseek | Bad_Design | dangerous | ❌ | 3 | 21 | 0% | 38.9s |
| deepseek | Bad_Design | optimization | ❌ | 3 | 21 | 0% | 55.2s |
| deepseek | Bad_Design | optimization | ❌ | 3 | 21 | 0% | 25.1s |
| deepseek | Bad_Design | dangerous | ❌ | 3 | 21 | 0% | 38.8s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | STM32_Minimal | 85 | B+ | 1 | 12 | 33.0s |
| deepseek | Power_Supply | 94 | A | 1 | 5 | 18.5s |
| deepseek | Bad_Design | 87 | B+ | 1 | 9 | 43.5s |

## 关键指标

- **幻觉消除率**: 0.0% (目标 > 80%)
- **修正成功率**: 0.0% (目标 > 60%)
- **平均迭代轮次**: 3.0 (目标 ≤ 2.0)
- **多智能体均分**: 89/100 (目标 > 75)

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\run_2026-07-09_101015\results.json`
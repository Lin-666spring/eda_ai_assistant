# EI 论文实验报告

> 生成时间: 2026-07-12T19:54:52.431464
> 设计数: 4 | 建议数: 5 | LLM: deepseek

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| bldc_esc_motor | 43 | 27 | 3 | 13 | 0.2s |
| dcdc_power_v62 | 131 | 93 | 4 | 34 | 0.0s |
| esp32_audio_moji2 | 53 | 38 | 3 | 12 | 0.0s |
| stm32f103_devboard | 28 | 18 | 4 | 6 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 轮次 | 阻断 | 消除率 | 耗时 |
|--------|------|----------|------|------|------|--------|------|
| deepseek | bldc_esc_motor | safe | ✅ | 1 | 0 | — | 0.0s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | bldc_esc_motor | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | bldc_esc_motor | optimization | ✅ | 1 | 0 | — | 0.1s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | dcdc_power_v62 | safe | ✅ | 1 | 0 | — | 0.0s |
| deepseek | dcdc_power_v62 | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | dcdc_power_v62 | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | esp32_audio_moji2 | safe | ✅ | 1 | 0 | — | 0.0s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | stm32f103_devboard | safe | ✅ | 1 | 0 | — | 0.0s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 1 | 0 | — | 0.0s |
| deepseek | stm32f103_devboard | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | stm32f103_devboard | optimization | ✅ | 1 | 0 | — | 0.0s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 1 | 0 | — | 0.0s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | bldc_esc_motor | 77 | B | 1 | 11 | 25.6s |
| deepseek | dcdc_power_v62 | 72 | B | 1 | 8 | 36.8s |
| deepseek | esp32_audio_moji2 | 75 | B | 1 | 10 | 24.2s |
| deepseek | stm32f103_devboard | 76 | B | 1 | 8 | 60.8s |

## 关键指标

- 幻觉消除率: N/A
- 修正成功率: N/A
- **平均迭代轮次**: 1.0 (目标 ≤ 2.0)
- **多智能体均分**: 75/100 (目标 > 75)
- **缺陷检出率**: 8/18 (44%)

### 缺陷注入详情

| 缺陷 | 预期规则 | 检出 | 命中 | 遗漏 |
|------|----------|------|------|------|
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ❌ 电容耐压不足 | 电容电压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ❌ 电容耐压不足 | 电容电压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ❌ 电容耐压不足 | 电容电压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ❌ 电容耐压不足 | 电容电压降额检查 | 否 | 0 | 1 |

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\run_2026-07-12_195224\results.json`
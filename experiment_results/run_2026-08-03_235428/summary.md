# EI 论文实验报告

> 生成时间: 2026-08-04T00:11:26.951381
> 设计数: 7 | 建议数: 5 | LLM: deepseek

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| bldc_esc_motor | 17 | 0 | 4 | 13 | 0.2s |
| dcdc_power_v62 | 39 | 0 | 5 | 34 | 0.0s |
| esp32_audio_moji2 | 12 | 0 | 2 | 10 | 0.0s |
| stm32f103_devboard | 12 | 0 | 5 | 7 | 0.0s |
| STM32_Minimal | 26 | 0 | 8 | 18 | 0.0s |
| Power_Supply | 18 | 0 | 4 | 14 | 0.0s |
| Bad_Design | 18 | 0 | 7 | 11 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| deepseek | bldc_esc_motor | safe | ✅ | 0 | — | 1 | — | 1.8s |
| deepseek | bldc_esc_motor | dangerous | ❌ | 13 | 0→0 | 3 | ❌ | 33.7s |
| deepseek | bldc_esc_motor | optimization | ❌ | 4 | 0→0 | 3 | ❌ | 41.6s |
| deepseek | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 23.6s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 11.7s |
| deepseek | dcdc_power_v62 | safe | ✅ | 0 | — | 1 | — | 1.5s |
| deepseek | dcdc_power_v62 | dangerous | ❌ | 22 | 1→1 | 3 | ❌ | 97.0s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 9.5s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 28.7s |
| deepseek | dcdc_power_v62 | dangerous | ✅ | 0 | — | 1 | — | 16.2s |
| deepseek | esp32_audio_moji2 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| deepseek | esp32_audio_moji2 | dangerous | ❌ | 12 | 7→7 | 3 | ❌ | 59.1s |
| deepseek | esp32_audio_moji2 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 223.3s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 3.2s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 8.9s |
| deepseek | stm32f103_devboard | safe | ✅ | 0 | — | 1 | — | 1.9s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 8 | 3→0 | 3 | ✅ | 63.3s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 7.2s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 41.3s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 0 | — | 1 | — | 9.5s |
| deepseek | STM32_Minimal | safe | ✅ | 0 | — | 1 | — | 1.9s |
| deepseek | STM32_Minimal | dangerous | ✅ | 4 | 2→0 | 2 | ✅ | 14.1s |
| deepseek | STM32_Minimal | optimization | ✅ | 4 | 4→0 | 2 | ✅ | 19.0s |
| deepseek | STM32_Minimal | optimization | ✅ | 0 | — | 1 | — | 23.4s |
| deepseek | STM32_Minimal | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 7.3s |
| deepseek | Power_Supply | safe | ✅ | 0 | — | 1 | — | 1.8s |
| deepseek | Power_Supply | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 6.3s |
| deepseek | Power_Supply | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 41.3s |
| deepseek | Power_Supply | optimization | ✅ | 0 | — | 1 | — | 21.2s |
| deepseek | Power_Supply | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 14.1s |
| deepseek | Bad_Design | safe | ✅ | 0 | — | 1 | — | 1.9s |
| deepseek | Bad_Design | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 31.4s |
| deepseek | Bad_Design | optimization | ✅ | 3 | 2→0 | 2 | ✅ | 20.4s |
| deepseek | Bad_Design | optimization | ✅ | 0 | — | 1 | — | 9.8s |
| deepseek | Bad_Design | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 7.8s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | bldc_esc_motor | 94 | A | 1 | 10 | 23.7s |
| deepseek | dcdc_power_v62 | 93 | A | 1 | 11 | 15.7s |
| deepseek | esp32_audio_moji2 | 96 | A+ | 1 | 5 | 8.3s |
| deepseek | stm32f103_devboard | 94 | A | 1 | 7 | 21.4s |
| deepseek | STM32_Minimal | 91 | A | 1 | 13 | 9.4s |
| deepseek | Power_Supply | 95 | A | 1 | 6 | 8.1s |
| deepseek | Bad_Design | 93 | A | 1 | 9 | 24.9s |

## 关键指标

- **BOM变更收敛率**: 11/17 (65%) (目标 > 70%)
- **平均新违规引入**: 1.3 个/建议
- **平均修正轮次**: 2.1 (目标 ≤ 2.0)
- **幻觉消除率**: 76.5% (目标 > 80%)
- **纯分析建议**: 18 个 (无BOM变更)
- **多智能体均分**: 94/100 (目标 > 75)
- **缺陷检出率**: 39/40 (98%)

### 缺陷注入详情

| 缺陷 | 预期规则 | 检出 | 命中 | 遗漏 |
|------|----------|------|------|------|
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 2 | 1 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除大容量滤波电容 | 电源滤波检查, PDN 目标阻抗分析 | 是 | 1 | 1 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ LDO 输出电压错误 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除运放反馈电阻 | 运放反馈网络检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除大容量滤波电容 | 电源滤波检查, PDN 目标阻抗分析 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ LDO 输出电压错误 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 电感饱和电流不足 | 电感饱和电流检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 2 | 1 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除大容量滤波电容 | 电源滤波检查, PDN 目标阻抗分析 | 是 | 1 | 1 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ LDO 输出电压错误 | 参数范围检查 | 是 | 1 | 0 |

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\run_2026-08-03_235428\results.json`
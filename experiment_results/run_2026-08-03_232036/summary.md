# EI 论文实验报告

> 生成时间: 2026-08-03T23:38:14.862979
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
| deepseek | bldc_esc_motor | safe | ✅ | 0 | — | 1 | — | 1.5s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 13 | 0→0 | 1 | ✅ | 13.2s |
| deepseek | bldc_esc_motor | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 18.3s |
| deepseek | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 13.9s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 15.3s |
| deepseek | dcdc_power_v62 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| deepseek | dcdc_power_v62 | dangerous | ❌ | 22 | 1→1 | 3 | ❌ | 91.6s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 7.1s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 19.0s |
| deepseek | dcdc_power_v62 | dangerous | ✅ | 0 | — | 1 | — | 13.2s |
| deepseek | esp32_audio_moji2 | safe | ✅ | 0 | — | 1 | — | 2.0s |
| deepseek | esp32_audio_moji2 | dangerous | ❌ | 12 | 7→7 | 3 | ❌ | 86.7s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 4 | 1→0 | 3 | ✅ | 86.7s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 17.4s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 18.5s |
| deepseek | stm32f103_devboard | safe | ✅ | 0 | — | 1 | — | 1.8s |
| deepseek | stm32f103_devboard | dangerous | ❌ | 8 | 3→3 | 3 | ❌ | 37.8s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 7.8s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 44.9s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 0 | — | 1 | — | 28.2s |
| deepseek | STM32_Minimal | safe | ✅ | 0 | — | 1 | — | 1.6s |
| deepseek | STM32_Minimal | dangerous | ✅ | 4 | 2→0 | 2 | ✅ | 26.9s |
| deepseek | STM32_Minimal | optimization | ✅ | 4 | 4→0 | 2 | ✅ | 23.1s |
| deepseek | STM32_Minimal | optimization | ✅ | 0 | — | 1 | — | 33.4s |
| deepseek | STM32_Minimal | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 10.1s |
| deepseek | Power_Supply | safe | ✅ | 0 | — | 1 | — | 1.6s |
| deepseek | Power_Supply | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 15.7s |
| deepseek | Power_Supply | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 25.0s |
| deepseek | Power_Supply | optimization | ✅ | 0 | — | 1 | — | 13.8s |
| deepseek | Power_Supply | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 12.9s |
| deepseek | Bad_Design | safe | ✅ | 0 | — | 1 | — | 1.5s |
| deepseek | Bad_Design | dangerous | ❌ | 2 | 1→1 | 3 | ❌ | 44.3s |
| deepseek | Bad_Design | optimization | ✅ | 3 | 3→0 | 3 | ✅ | 79.6s |
| deepseek | Bad_Design | optimization | ✅ | 0 | — | 1 | — | 56.8s |
| deepseek | Bad_Design | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 24.7s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | bldc_esc_motor | 94 | A | 1 | 10 | 17.4s |
| deepseek | dcdc_power_v62 | 93 | A | 1 | 8 | 48.7s |
| deepseek | esp32_audio_moji2 | 96 | A+ | 1 | 5 | 10.1s |
| deepseek | stm32f103_devboard | 94 | A | 1 | 7 | 24.2s |
| deepseek | STM32_Minimal | 91 | A | 1 | 13 | 23.4s |
| deepseek | Power_Supply | 95 | A | 1 | 6 | 10.9s |
| deepseek | Bad_Design | 93 | A | 1 | 9 | 26.1s |

## 关键指标

- **BOM变更收敛率**: 13/17 (76%) (目标 > 70%)
- **平均新违规引入**: 1.4 个/建议
- **平均修正轮次**: 1.9 (目标 ≤ 2.0)
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
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\run_2026-08-03_232036\results.json`
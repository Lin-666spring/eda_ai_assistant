# EI 论文实验报告

> 生成时间: 2026-07-12T22:59:31.614941
> 设计数: 4 | 建议数: 5 | LLM: deepseek

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| bldc_esc_motor | 45 | 27 | 4 | 14 | 0.2s |
| dcdc_power_v62 | 134 | 93 | 6 | 35 | 0.0s |
| esp32_audio_moji2 | 53 | 38 | 3 | 12 | 0.0s |
| stm32f103_devboard | 33 | 18 | 7 | 8 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| deepseek | bldc_esc_motor | safe | ✅ | 0 | — | 1 | — | 1.8s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 13 | 0→0 | 1 | ✅ | 10.4s |
| deepseek | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 10.3s |
| deepseek | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 6.0s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 26 | 0→0 | 1 | ✅ | 45.6s |
| deepseek | dcdc_power_v62 | safe | ✅ | 0 | — | 1 | — | 2.0s |
| deepseek | dcdc_power_v62 | dangerous | ❌ | 22 | 1→1 | 3 | ❌ | 110.9s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 6.7s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 2.2s |
| deepseek | dcdc_power_v62 | dangerous | ✅ | 0 | — | 1 | — | 8.2s |
| deepseek | esp32_audio_moji2 | safe | ✅ | 0 | — | 1 | — | 2.0s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 12 | 1→0 | 3 | ✅ | 58.9s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 12.9s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 5.3s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 0 | — | 1 | — | 11.6s |
| deepseek | stm32f103_devboard | safe | ✅ | 0 | — | 1 | — | 2.2s |
| deepseek | stm32f103_devboard | dangerous | ❌ | 8 | 1→1 | 3 | ❌ | 47.4s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 17.9s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 2.4s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 0 | — | 1 | — | 8.1s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | bldc_esc_motor | 74 | B | 1 | 13 | 33.8s |
| deepseek | dcdc_power_v62 | 67 | C | 1 | 13 | 41.2s |
| deepseek | esp32_audio_moji2 | 75 | B | 1 | 10 | 26.6s |
| deepseek | stm32f103_devboard | 70 | C | 1 | 12 | 46.5s |

## 关键指标

- **BOM变更收敛率**: 3/5 (60%) (目标 > 70%)
- **平均新违规引入**: 0.6 个/建议
- **平均修正轮次**: 2.2 (目标 ≤ 2.0)
- **幻觉消除率**: 60.0% (目标 > 80%)
- **纯分析建议**: 15 个 (无BOM变更)
- **多智能体均分**: 72/100 (目标 > 75)
- **缺陷检出率**: 18/18 (100%)

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
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
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

---
📁 完整 JSON 数据: `experiment_results\run_2026-07-12_full\results.json`
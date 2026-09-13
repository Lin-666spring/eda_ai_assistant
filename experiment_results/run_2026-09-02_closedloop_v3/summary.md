# EI 论文实验报告

> 生成时间: 2026-09-02T14:04:56.318700
> 设计数: 7 | 建议数: 5 | LLM: deepseek

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| bldc_esc_motor | 19 | 0 | 5 | 14 | 1.4s |
| board_schematic | 47 | 0 | 3 | 44 | 0.2s |
| dcdc_power_v62 | 41 | 0 | 6 | 35 | 0.2s |
| eda_robotpro_v1 | 13 | 0 | 7 | 6 | 0.0s |
| esp32_audio_moji2 | 15 | 0 | 3 | 12 | 0.0s |
| smart_uv_lamp_v2 | 41 | 0 | 5 | 36 | 0.1s |
| stm32f103_devboard | 13 | 0 | 5 | 8 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| deepseek | bldc_esc_motor | safe | ✅ | 0 | — | 1 | — | 280.5s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 0 | — | 1 | — | 0.3s |
| deepseek | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 0.3s |
| deepseek | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 1.3s |
| deepseek | bldc_esc_motor | dangerous | ✅ | 0 | — | 1 | — | 0.3s |
| deepseek | board_schematic | safe | ✅ | 0 | — | 1 | — | 0.9s |
| deepseek | board_schematic | dangerous | ✅ | 0 | — | 1 | — | 2.7s |
| deepseek | board_schematic | optimization | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | board_schematic | optimization | ✅ | 0 | — | 1 | — | 0.3s |
| deepseek | board_schematic | dangerous | ✅ | 0 | — | 1 | — | 2.1s |
| deepseek | dcdc_power_v62 | safe | ✅ | 0 | — | 1 | — | 0.4s |
| deepseek | dcdc_power_v62 | dangerous | ✅ | 0 | — | 1 | — | 0.3s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 1.0s |
| deepseek | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 1.8s |
| deepseek | dcdc_power_v62 | dangerous | ✅ | 0 | — | 1 | — | 0.9s |
| deepseek | eda_robotpro_v1 | safe | ✅ | 0 | — | 1 | — | 0.4s |
| deepseek | eda_robotpro_v1 | dangerous | ✅ | 0 | — | 1 | — | 3.8s |
| deepseek | eda_robotpro_v1 | optimization | ✅ | 0 | — | 1 | — | 2.8s |
| deepseek | eda_robotpro_v1 | optimization | ✅ | 0 | — | 1 | — | 0.3s |
| deepseek | eda_robotpro_v1 | dangerous | ✅ | 0 | — | 1 | — | 2.6s |
| deepseek | esp32_audio_moji2 | safe | ✅ | 0 | — | 1 | — | 0.2s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 0.2s |
| deepseek | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 9.2s |
| deepseek | esp32_audio_moji2 | dangerous | ✅ | 0 | — | 1 | — | 0.2s |
| deepseek | smart_uv_lamp_v2 | safe | ✅ | 0 | — | 1 | — | 5.6s |
| deepseek | smart_uv_lamp_v2 | dangerous | ✅ | 0 | — | 1 | — | 3.6s |
| deepseek | smart_uv_lamp_v2 | optimization | ✅ | 0 | — | 1 | — | 0.4s |
| deepseek | smart_uv_lamp_v2 | optimization | ✅ | 0 | — | 1 | — | 2.0s |
| deepseek | smart_uv_lamp_v2 | dangerous | ✅ | 0 | — | 1 | — | 4.9s |
| deepseek | stm32f103_devboard | safe | ✅ | 0 | — | 1 | — | 2.7s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 0 | — | 1 | — | 0.2s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 1.8s |
| deepseek | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 0.1s |
| deepseek | stm32f103_devboard | dangerous | ✅ | 0 | — | 1 | — | 0.2s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | bldc_esc_motor | 93 | A | 0 | 0 | 1.6s |
| deepseek | board_schematic | 94 | A | 0 | 0 | 0.4s |
| deepseek | dcdc_power_v62 | 92 | A | 0 | 0 | 0.3s |
| deepseek | eda_robotpro_v1 | 93 | A | 0 | 0 | 0.2s |
| deepseek | esp32_audio_moji2 | 95 | A+ | 0 | 0 | 0.7s |
| deepseek | smart_uv_lamp_v2 | 92 | A | 0 | 0 | 1.6s |
| deepseek | stm32f103_devboard | 94 | A | 0 | 0 | 0.6s |

## 关键指标

- **纯分析建议**: 35 个 (无BOM变更)
- **多智能体均分**: 94/100 (目标 > 75)
- **缺陷检出率**: 30/31 (97%)

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
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |

---
📁 完整 JSON 数据: `experiment_results\run_2026-09-02_closedloop_v3\results.json`
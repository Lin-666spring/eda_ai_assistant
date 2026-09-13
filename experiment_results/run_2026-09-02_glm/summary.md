# EI 论文实验报告

> 生成时间: 2026-09-02T15:02:31.816760
> 设计数: 7 | 建议数: 5 | LLM: glm

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| bldc_esc_motor | 19 | 0 | 5 | 14 | 1.4s |
| board_schematic | 47 | 0 | 3 | 44 | 0.2s |
| dcdc_power_v62 | 41 | 0 | 6 | 35 | 0.1s |
| eda_robotpro_v1 | 13 | 0 | 7 | 6 | 0.0s |
| esp32_audio_moji2 | 15 | 0 | 3 | 12 | 0.0s |
| smart_uv_lamp_v2 | 41 | 0 | 5 | 36 | 0.1s |
| stm32f103_devboard | 13 | 0 | 5 | 8 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| glm | bldc_esc_motor | safe | ✅ | 0 | — | 1 | — | 11.0s |
| glm | bldc_esc_motor | dangerous | ✅ | 13 | 0→0 | 1 | ✅ | 48.3s |
| glm | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 104.5s |
| glm | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 21.0s |
| glm | bldc_esc_motor | dangerous | ✅ | 0 | — | 1 | — | 105.5s |
| glm | board_schematic | safe | ✅ | 0 | — | 1 | — | 6.8s |
| glm | board_schematic | dangerous | ✅ | 0 | — | 1 | — | 116.6s |
| glm | board_schematic | optimization | ✅ | 0 | — | 1 | — | 23.8s |
| glm | board_schematic | optimization | ✅ | 0 | — | 1 | — | 11.3s |
| glm | board_schematic | dangerous | ✅ | 0 | — | 1 | — | 84.8s |
| glm | dcdc_power_v62 | safe | ✅ | 0 | — | 1 | — | 6.8s |
| glm | dcdc_power_v62 | dangerous | ❌ | 22 | 1→1 | 3 | ❌ | 302.5s |
| glm | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 32.3s |
| glm | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 8.6s |
| glm | dcdc_power_v62 | dangerous | ✅ | 0 | — | 1 | — | 88.1s |
| glm | eda_robotpro_v1 | safe | ✅ | 0 | — | 1 | — | 15.5s |
| glm | eda_robotpro_v1 | dangerous | ❌ | 1 | 1→1 | 3 | ❌ | 68.7s |
| glm | eda_robotpro_v1 | optimization | ✅ | 0 | — | 1 | — | 118.8s |
| glm | eda_robotpro_v1 | optimization | ✅ | 0 | — | 1 | — | 20.2s |
| glm | eda_robotpro_v1 | dangerous | ✅ | 0 | — | 1 | — | 119.4s |
| glm | esp32_audio_moji2 | safe | ✅ | 0 | — | 1 | — | 14.2s |
| glm | esp32_audio_moji2 | dangerous | ❌ | 12 | 1→1 | 3 | ❌ | 248.9s |
| glm | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 104.2s |
| glm | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 8.6s |
| glm | esp32_audio_moji2 | dangerous | ✅ | 0 | — | 1 | — | 31.1s |
| glm | smart_uv_lamp_v2 | safe | ✅ | 0 | — | 1 | — | 11.5s |
| glm | smart_uv_lamp_v2 | dangerous | ✅ | 9 | 0→0 | 1 | ✅ | 34.1s |
| glm | smart_uv_lamp_v2 | optimization | ✅ | 0 | — | 1 | — | 38.8s |
| glm | smart_uv_lamp_v2 | optimization | ✅ | 0 | — | 1 | — | 17.5s |
| glm | smart_uv_lamp_v2 | dangerous | ✅ | 0 | — | 1 | — | 22.7s |
| glm | stm32f103_devboard | safe | ✅ | 0 | — | 1 | — | 14.7s |
| glm | stm32f103_devboard | dangerous | ❌ | 8 | 1→1 | 3 | ❌ | 204.7s |
| glm | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 120.1s |
| glm | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 26.1s |
| glm | stm32f103_devboard | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 93.7s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| glm | bldc_esc_motor | 93 | A | 1 | 6 | 103.2s |
| glm | board_schematic | 94 | A | 1 | 9 | 109.9s |
| glm | dcdc_power_v62 | 92 | A | 1 | 11 | 115.5s |
| glm | eda_robotpro_v1 | 93 | A | 1 | 9 | 85.0s |
| glm | esp32_audio_moji2 | 95 | A+ | 1 | 5 | 78.1s |
| glm | smart_uv_lamp_v2 | 92 | A | 1 | 13 | 136.8s |
| glm | stm32f103_devboard | 94 | A | 1 | 7 | 78.3s |

## 关键指标

- **BOM变更收敛率**: 3/7 (43%) (目标 > 70%)
- **平均新违规引入**: 0.6 个/建议
- **平均修正轮次**: 2.1 (目标 ≤ 2.0)
- **幻觉消除率**: 42.9% (目标 > 80%)
- **纯分析建议**: 28 个 (无BOM变更)
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
📁 完整 JSON 数据: `experiment_results\run_2026-09-02_glm\results.json`
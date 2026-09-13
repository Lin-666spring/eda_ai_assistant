# EI 论文实验报告

> 生成时间: 2026-09-08T20:15:31.113186
> 设计数: 17 | 建议数: 5 | LLM: glm

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| bldc_esc_motor | 19 | 0 | 5 | 14 | 1.2s |
| board_schematic | 47 | 0 | 3 | 44 | 0.2s |
| cw32l010_usb_dev | 9 | 0 | 3 | 6 | 0.0s |
| dcdc_power_v62 | 41 | 0 | 6 | 35 | 0.1s |
| dianchuangpai_v2 | 17 | 0 | 4 | 13 | 0.1s |
| eda_robotpro_v1 | 13 | 0 | 7 | 6 | 0.0s |
| esp32_audio_moji2 | 15 | 0 | 3 | 12 | 0.0s |
| gps_atgm336h_board | 16 | 0 | 2 | 14 | 0.0s |
| lushanpi_k230_canmv | 49 | 0 | 4 | 45 | 0.2s |
| oled_inmp441_module | 7 | 1 | 3 | 3 | 0.0s |
| rk3566_coreboard | 37 | 0 | 3 | 34 | 0.1s |
| smart_uv_lamp_v2 | 41 | 0 | 5 | 36 | 0.1s |
| stm32f103_devboard | 13 | 0 | 5 | 8 | 0.0s |
| stm32f103_power_base | 23 | 0 | 3 | 20 | 0.1s |
| taishanpi_rk3576_v14 | 75 | 0 | 5 | 70 | 0.3s |
| tm055vdxp35_lcd_adapter | 7 | 0 | 1 | 6 | 0.0s |
| voltage_current_meter_v13 | 15 | 0 | 4 | 11 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| glm | bldc_esc_motor | safe | ✅ | 0 | — | 1 | — | 17.5s |
| glm | bldc_esc_motor | dangerous | ✅ | 0 | — | 1 | — | 54.7s |
| glm | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 118.3s |
| glm | bldc_esc_motor | optimization | ✅ | 0 | — | 1 | — | 19.9s |
| glm | bldc_esc_motor | dangerous | ✅ | 0 | — | 1 | — | 120.3s |
| glm | board_schematic | safe | ✅ | 0 | — | 1 | — | 9.4s |
| glm | board_schematic | dangerous | ✅ | 0 | — | 1 | — | 105.9s |
| glm | board_schematic | optimization | ✅ | 0 | — | 1 | — | 21.5s |
| glm | board_schematic | optimization | ✅ | 0 | — | 1 | — | 21.1s |
| glm | board_schematic | dangerous | ✅ | 0 | — | 1 | — | 73.3s |
| glm | cw32l010_usb_dev | safe | ✅ | 0 | — | 1 | — | 15.8s |
| glm | cw32l010_usb_dev | dangerous | ❌ | 6 | 0→0 | 3 | ❌ | 98.9s |
| glm | cw32l010_usb_dev | optimization | ✅ | 0 | — | 1 | — | 105.6s |
| glm | cw32l010_usb_dev | optimization | ✅ | 0 | — | 1 | — | 18.4s |
| glm | cw32l010_usb_dev | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 108.6s |
| glm | dcdc_power_v62 | safe | ✅ | 0 | — | 1 | — | 14.0s |
| glm | dcdc_power_v62 | dangerous | ❌ | 22 | 1→1 | 3 | ❌ | 231.8s |
| glm | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 16.3s |
| glm | dcdc_power_v62 | optimization | ✅ | 0 | — | 1 | — | 11.5s |
| glm | dcdc_power_v62 | dangerous | ✅ | 0 | — | 1 | — | 29.9s |
| glm | dianchuangpai_v2 | safe | ✅ | 0 | — | 1 | — | 12.7s |
| glm | dianchuangpai_v2 | dangerous | ❌ | 15 | 3→3 | 3 | ❌ | 211.4s |
| glm | dianchuangpai_v2 | optimization | ✅ | 0 | — | 1 | — | 74.8s |
| glm | dianchuangpai_v2 | optimization | ✅ | 0 | — | 1 | — | 16.7s |
| glm | dianchuangpai_v2 | dangerous | ✅ | 0 | — | 1 | — | 116.3s |
| glm | eda_robotpro_v1 | safe | ✅ | 0 | — | 1 | — | 12.7s |
| glm | eda_robotpro_v1 | dangerous | ❌ | 1 | 1→1 | 3 | ❌ | 65.2s |
| glm | eda_robotpro_v1 | optimization | ✅ | 0 | — | 1 | — | 72.3s |
| glm | eda_robotpro_v1 | optimization | ✅ | 0 | — | 1 | — | 20.1s |
| glm | eda_robotpro_v1 | dangerous | ✅ | 0 | — | 1 | — | 120.3s |
| glm | esp32_audio_moji2 | safe | ✅ | 0 | — | 1 | — | 13.6s |
| glm | esp32_audio_moji2 | dangerous | ❌ | 12 | 7→7 | 3 | ❌ | 241.2s |
| glm | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 116.5s |
| glm | esp32_audio_moji2 | optimization | ✅ | 0 | — | 1 | — | 12.2s |
| glm | esp32_audio_moji2 | dangerous | ✅ | 0 | — | 1 | — | 114.8s |
| glm | gps_atgm336h_board | safe | ✅ | 0 | — | 1 | — | 13.6s |
| glm | gps_atgm336h_board | dangerous | ❌ | 6 | 3→3 | 3 | ❌ | 135.1s |
| glm | gps_atgm336h_board | optimization | ✅ | 0 | — | 1 | — | 52.0s |
| glm | gps_atgm336h_board | optimization | ✅ | 0 | — | 1 | — | 20.5s |
| glm | gps_atgm336h_board | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 82.3s |
| glm | lushanpi_k230_canmv | safe | ✅ | 0 | — | 1 | — | 13.2s |
| glm | lushanpi_k230_canmv | dangerous | ✅ | 0 | — | 1 | — | 111.7s |
| glm | lushanpi_k230_canmv | optimization | ✅ | 0 | — | 1 | — | 29.6s |
| glm | lushanpi_k230_canmv | optimization | ✅ | 0 | — | 1 | — | 21.9s |
| glm | lushanpi_k230_canmv | dangerous | ✅ | 0 | — | 1 | — | 26.6s |
| glm | oled_inmp441_module | safe | ✅ | 0 | — | 1 | — | 13.9s |
| glm | oled_inmp441_module | dangerous | ✅ | 0 | — | 1 | — | 120.2s |
| glm | oled_inmp441_module | optimization | ✅ | 0 | — | 1 | — | 75.6s |
| glm | oled_inmp441_module | optimization | ✅ | 0 | — | 1 | — | 18.2s |
| glm | oled_inmp441_module | dangerous | ✅ | 0 | — | 1 | — | 97.3s |
| glm | rk3566_coreboard | safe | ✅ | 0 | — | 1 | — | 12.0s |
| glm | rk3566_coreboard | dangerous | ✅ | 0 | — | 1 | — | 110.1s |
| glm | rk3566_coreboard | optimization | ✅ | 0 | — | 1 | — | 74.7s |
| glm | rk3566_coreboard | optimization | ✅ | 0 | — | 1 | — | 10.9s |
| glm | rk3566_coreboard | dangerous | ✅ | 0 | — | 1 | — | 32.2s |
| glm | smart_uv_lamp_v2 | safe | ✅ | 0 | — | 1 | — | 14.9s |
| glm | smart_uv_lamp_v2 | dangerous | ❌ | 9 | 6→6 | 3 | ❌ | 294.0s |
| glm | smart_uv_lamp_v2 | optimization | ✅ | 0 | — | 1 | — | 41.7s |
| glm | smart_uv_lamp_v2 | optimization | ✅ | 0 | — | 1 | — | 17.4s |
| glm | smart_uv_lamp_v2 | dangerous | ✅ | 0 | — | 1 | — | 93.5s |
| glm | stm32f103_devboard | safe | ✅ | 0 | — | 1 | — | 12.2s |
| glm | stm32f103_devboard | dangerous | ❌ | 8 | 3→3 | 3 | ❌ | 258.6s |
| glm | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 88.6s |
| glm | stm32f103_devboard | optimization | ✅ | 0 | — | 1 | — | 20.8s |
| glm | stm32f103_devboard | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 98.0s |
| glm | stm32f103_power_base | safe | ✅ | 0 | — | 1 | — | 14.8s |
| glm | stm32f103_power_base | dangerous | ❌ | 11 | 1→1 | 3 | ❌ | 231.2s |
| glm | stm32f103_power_base | optimization | ✅ | 0 | — | 1 | — | 96.6s |
| glm | stm32f103_power_base | optimization | ✅ | 0 | — | 1 | — | 16.4s |
| glm | stm32f103_power_base | dangerous | ✅ | 0 | — | 1 | — | 102.2s |
| glm | taishanpi_rk3576_v14 | safe | ✅ | 0 | — | 1 | — | 16.3s |
| glm | taishanpi_rk3576_v14 | dangerous | ✅ | 0 | — | 1 | — | 110.2s |
| glm | taishanpi_rk3576_v14 | optimization | ✅ | 0 | — | 1 | — | 33.0s |
| glm | taishanpi_rk3576_v14 | optimization | ✅ | 0 | — | 1 | — | 11.6s |
| glm | taishanpi_rk3576_v14 | dangerous | ✅ | 0 | — | 1 | — | 27.0s |
| glm | tm055vdxp35_lcd_adapter | safe | ✅ | 0 | — | 1 | — | 13.5s |
| glm | tm055vdxp35_lcd_adapter | dangerous | ❌ | 6 | 3→3 | 3 | ❌ | 157.7s |
| glm | tm055vdxp35_lcd_adapter | optimization | ✅ | 0 | — | 1 | — | 106.3s |
| glm | tm055vdxp35_lcd_adapter | optimization | ✅ | 0 | — | 1 | — | 14.8s |
| glm | tm055vdxp35_lcd_adapter | dangerous | ✅ | 0 | — | 1 | — | 62.6s |
| glm | voltage_current_meter_v13 | safe | ✅ | 0 | — | 1 | — | 13.5s |
| glm | voltage_current_meter_v13 | dangerous | ✅ | 3 | 0→0 | 1 | ✅ | 35.3s |
| glm | voltage_current_meter_v13 | optimization | ✅ | 0 | — | 1 | — | 35.3s |
| glm | voltage_current_meter_v13 | optimization | ✅ | 0 | — | 1 | — | 24.4s |
| glm | voltage_current_meter_v13 | dangerous | ✅ | 0 | — | 1 | — | 39.4s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| glm | bldc_esc_motor | 93 | A | 1 | 11 | 100.9s |
| glm | board_schematic | 94 | A | 1 | 9 | 108.3s |
| glm | cw32l010_usb_dev | 97 | A+ | 1 | 5 | 91.1s |
| glm | dcdc_power_v62 | 92 | A | 1 | 9 | 166.0s |
| glm | dianchuangpai_v2 | 94 | A | 1 | 8 | 93.6s |
| glm | eda_robotpro_v1 | 93 | A | 1 | 9 | 87.1s |
| glm | esp32_audio_moji2 | 95 | A+ | 1 | 6 | 88.5s |
| glm | gps_atgm336h_board | 96 | A+ | 1 | 6 | 67.4s |
| glm | lushanpi_k230_canmv | 93 | A | 1 | 11 | 101.4s |
| glm | oled_inmp441_module | 95 | A+ | 1 | 4 | 65.4s |
| glm | rk3566_coreboard | 95 | A+ | 1 | 7 | 76.1s |
| glm | smart_uv_lamp_v2 | 92 | A | 1 | 13 | 165.2s |
| glm | stm32f103_devboard | 94 | A | 1 | 7 | 100.2s |
| glm | stm32f103_power_base | 94 | A | 1 | 5 | 74.2s |
| glm | taishanpi_rk3576_v14 | 92 | A | 1 | 11 | 136.0s |
| glm | tm055vdxp35_lcd_adapter | 97 | A+ | 1 | 3 | 65.8s |
| glm | voltage_current_meter_v13 | 95 | A | 1 | 7 | 80.4s |

## 关键指标

- **BOM变更收敛率**: 4/14 (29%) (目标 > 70%)
- **平均新违规引入**: 2.0 个/建议
- **平均修正轮次**: 2.4 (目标 ≤ 2.0)
- **幻觉消除率**: 35.7% (目标 > 80%)
- **纯分析建议**: 71 个 (无BOM变更)
- **多智能体均分**: 94/100 (目标 > 75)
- **缺陷检出率**: 67/70 (96%)

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
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |

---
📁 完整 JSON 数据: `experiment_results\run_2026-09-08_full_glm\results.json`
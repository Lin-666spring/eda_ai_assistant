# EI 论文实验报告

> 生成时间: 2026-10-19T19:07:58.673444
> 设计数: 21 | 建议数: 5 | LLM: deepseek

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| 6寸屏幕转接板 | 5 | 0 | 1 | 4 | 1.5s |
| LCTSPI语音识别扩展板 | 2 | 0 | 1 | 1 | 0.0s |
| P1 | 6 | 0 | 1 | 5 | 0.0s |
| V1.0.2_3 | 4 | 0 | 0 | 4 | 0.0s |
| XDS110 | 4 | 0 | 1 | 3 | 0.0s |
| design009 | 3 | 0 | 2 | 1 | 0.0s |
| design013 | 4 | 0 | 1 | 3 | 0.1s |
| design030 | 9 | 3 | 5 | 1 | 0.0s |
| design031 | 5 | 0 | 2 | 3 | 0.0s |
| design038 | 4 | 0 | 3 | 1 | 0.0s |
| design051 | 4 | 0 | 1 | 3 | 0.1s |
| design054 | 6 | 0 | 1 | 5 | 0.3s |
| design059 | 4 | 0 | 3 | 1 | 0.0s |
| design066 | 3 | 0 | 2 | 1 | 0.0s |
| design090 | 7 | 1 | 5 | 1 | 0.0s |
| io扩展 | 6 | 0 | 2 | 4 | 0.0s |
| 已走线 | 6 | 0 | 1 | 5 | 0.1s |
| 泰山派无人机地面站 | 10 | 2 | 3 | 5 | 0.0s |
| 游戏机扩展板V1.1.1 | 5 | 0 | 3 | 2 | 0.0s |
| 游戏机扩展板diy | 5 | 0 | 3 | 2 | 0.0s |
| 立创·逻辑派FPGA | 4 | 0 | 2 | 2 | 0.0s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| deepseek | 6寸屏幕转接板 | safe | ✅ | 0 | — | 1 | — | 1.2s |
| deepseek | 6寸屏幕转接板 | dangerous | ✅ | 4 | 4→0 | 2 | ✅ | 4.3s |
| deepseek | 6寸屏幕转接板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 9.4s |
| deepseek | 6寸屏幕转接板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 11.2s |
| deepseek | 6寸屏幕转接板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 9.1s |
| deepseek | LCTSPI语音识别扩展板 | safe | ✅ | 0 | — | 1 | — | 1.2s |
| deepseek | LCTSPI语音识别扩展板 | dangerous | ✅ | 8 | 1→0 | 2 | ✅ | 9.7s |
| deepseek | LCTSPI语音识别扩展板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 3.0s |
| deepseek | LCTSPI语音识别扩展板 | optimization | ✅ | 0 | — | 1 | — | 15.0s |
| deepseek | LCTSPI语音识别扩展板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 13.0s |
| deepseek | P1 | safe | ✅ | 0 | — | 1 | — | 1.5s |
| deepseek | P1 | dangerous | ✅ | 15 | 9→0 | 2 | ✅ | 6.0s |
| deepseek | P1 | optimization | ✅ | 4 | 10→0 | 2 | ✅ | 13.5s |
| deepseek | P1 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 18.5s |
| deepseek | P1 | dangerous | ✅ | 0 | — | 1 | — | 18.9s |
| deepseek | V1.0.2_3 | safe | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | V1.0.2_3 | dangerous | ✅ | 5 | 2→0 | 2 | ✅ | 6.9s |
| deepseek | V1.0.2_3 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 40.6s |
| deepseek | V1.0.2_3 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 12.5s |
| deepseek | V1.0.2_3 | dangerous | ✅ | 0 | — | 1 | — | 19.9s |
| deepseek | XDS110 | safe | ✅ | 0 | — | 1 | — | 1.0s |
| deepseek | XDS110 | dangerous | ✅ | 15 | 4→0 | 2 | ✅ | 6.2s |
| deepseek | XDS110 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 16.7s |
| deepseek | XDS110 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 29.3s |
| deepseek | XDS110 | dangerous | ✅ | 0 | — | 1 | — | 19.9s |
| deepseek | design009 | safe | ✅ | 0 | — | 1 | — | 1.3s |
| deepseek | design009 | dangerous | ✅ | 16 | 1→0 | 2 | ✅ | 6.2s |
| deepseek | design009 | optimization | ✅ | 3 | 1→0 | 2 | ✅ | 10.3s |
| deepseek | design009 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 17.4s |
| deepseek | design009 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 8.8s |
| deepseek | design013 | safe | ✅ | 0 | — | 1 | — | 1.2s |
| deepseek | design013 | dangerous | ✅ | 82 | 8→0 | 2 | ✅ | 14.4s |
| deepseek | design013 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 12.2s |
| deepseek | design013 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 12.3s |
| deepseek | design013 | dangerous | ✅ | 0 | — | 1 | — | 12.0s |
| deepseek | design030 | safe | ✅ | 0 | — | 1 | — | 1.5s |
| deepseek | design030 | dangerous | ✅ | 0 | — | 1 | — | 1.9s |
| deepseek | design030 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 7.9s |
| deepseek | design030 | optimization | ✅ | 0 | — | 1 | — | 19.7s |
| deepseek | design030 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 7.8s |
| deepseek | design031 | safe | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | design031 | dangerous | ✅ | 10 | 1→0 | 2 | ✅ | 7.0s |
| deepseek | design031 | optimization | ✅ | 0 | — | 1 | — | 19.5s |
| deepseek | design031 | optimization | ✅ | 0 | — | 1 | — | 21.1s |
| deepseek | design031 | dangerous | ✅ | 0 | — | 1 | — | 19.2s |
| deepseek | design038 | safe | ✅ | 0 | — | 1 | — | 0.9s |
| deepseek | design038 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 5.6s |
| deepseek | design038 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 26.9s |
| deepseek | design038 | optimization | ✅ | 0 | — | 1 | — | 20.7s |
| deepseek | design038 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 5.6s |
| deepseek | design051 | safe | ✅ | 0 | — | 1 | — | 1.3s |
| deepseek | design051 | dangerous | ✅ | 24 | 11→0 | 2 | ✅ | 9.2s |
| deepseek | design051 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 4.2s |
| deepseek | design051 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 12.8s |
| deepseek | design051 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 8.5s |
| deepseek | design054 | safe | ✅ | 0 | — | 1 | — | 1.2s |
| deepseek | design054 | dangerous | ✅ | 0 | — | 1 | — | 12.3s |
| deepseek | design054 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 4.2s |
| deepseek | design054 | optimization | ✅ | 1 | 0→0 | 1 | ✅ | 10.5s |
| deepseek | design054 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 10.9s |
| deepseek | design059 | safe | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | design059 | dangerous | ✅ | 1 | 1→0 | 2 | ✅ | 5.2s |
| deepseek | design059 | optimization | ✅ | 0 | — | 1 | — | 19.2s |
| deepseek | design059 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 5.5s |
| deepseek | design059 | dangerous | ✅ | 0 | — | 1 | — | 18.7s |
| deepseek | design066 | safe | ✅ | 0 | — | 1 | — | 1.2s |
| deepseek | design066 | dangerous | ✅ | 1 | 1→0 | 2 | ✅ | 4.0s |
| deepseek | design066 | optimization | ✅ | 3 | 2→0 | 2 | ✅ | 22.5s |
| deepseek | design066 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 22.6s |
| deepseek | design066 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 6.6s |
| deepseek | design090 | safe | ✅ | 0 | — | 1 | — | 1.5s |
| deepseek | design090 | dangerous | ✅ | 0 | — | 1 | — | 2.6s |
| deepseek | design090 | optimization | ✅ | 4 | 2→0 | 2 | ✅ | 9.1s |
| deepseek | design090 | optimization | ✅ | 0 | — | 1 | — | 21.1s |
| deepseek | design090 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 11.1s |
| deepseek | io扩展 | safe | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | io扩展 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 5.4s |
| deepseek | io扩展 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 8.3s |
| deepseek | io扩展 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 5.6s |
| deepseek | io扩展 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 7.8s |
| deepseek | 已走线 | safe | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 15.6s |
| deepseek | 已走线 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 6.7s |
| deepseek | 已走线 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 10.4s |
| deepseek | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 10.0s |
| deepseek | 泰山派无人机地面站 | safe | ✅ | 0 | — | 1 | — | 1.3s |
| deepseek | 泰山派无人机地面站 | dangerous | ✅ | 0 | — | 1 | — | 1.5s |
| deepseek | 泰山派无人机地面站 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 27.1s |
| deepseek | 泰山派无人机地面站 | optimization | ✅ | 0 | — | 1 | — | 20.8s |
| deepseek | 泰山派无人机地面站 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 17.6s |
| deepseek | 游戏机扩展板V1.1.1 | safe | ✅ | 0 | — | 1 | — | 1.1s |
| deepseek | 游戏机扩展板V1.1.1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 2.0s |
| deepseek | 游戏机扩展板V1.1.1 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 5.3s |
| deepseek | 游戏机扩展板V1.1.1 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 9.8s |
| deepseek | 游戏机扩展板V1.1.1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 7.6s |
| deepseek | 游戏机扩展板diy | safe | ✅ | 0 | — | 1 | — | 1.2s |
| deepseek | 游戏机扩展板diy | dangerous | ✅ | 5 | 0→0 | 1 | ✅ | 3.3s |
| deepseek | 游戏机扩展板diy | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 11.0s |
| deepseek | 游戏机扩展板diy | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 11.1s |
| deepseek | 游戏机扩展板diy | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 10.3s |
| deepseek | 立创·逻辑派FPGA | safe | ✅ | 0 | — | 1 | — | 1.2s |
| deepseek | 立创·逻辑派FPGA | dangerous | ✅ | 21 | 6→0 | 2 | ✅ | 10.0s |
| deepseek | 立创·逻辑派FPGA | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 10.8s |
| deepseek | 立创·逻辑派FPGA | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 12.1s |
| deepseek | 立创·逻辑派FPGA | dangerous | ✅ | 0 | — | 1 | — | 18.6s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| deepseek | 6寸屏幕转接板 | 98 | A+ | 1 | 5 | 8.4s |
| deepseek | LCTSPI语音识别扩展板 | 98 | A+ | 1 | 5 | 10.3s |
| deepseek | P1 | 97 | A+ | 1 | 7 | 8.1s |
| deepseek | V1.0.2_3 | 99 | A+ | 0 | 2 | 5.9s |
| deepseek | XDS110 | 98 | A+ | 1 | 2 | 7.0s |
| deepseek | design009 | 97 | A+ | 1 | 2 | 5.2s |
| deepseek | design013 | 98 | A+ | 1 | 4 | 6.5s |
| deepseek | design030 | 93 | A | 1 | 6 | 10.8s |
| deepseek | design031 | 98 | A+ | 1 | 3 | 8.0s |
| deepseek | design038 | 96 | A+ | 1 | 4 | 5.5s |
| deepseek | design051 | 98 | A+ | 1 | 2 | 6.2s |
| deepseek | design054 | 97 | A+ | 1 | 4 | 9.6s |
| deepseek | design059 | 97 | A+ | 1 | 4 | 9.2s |
| deepseek | design066 | 97 | A+ | 1 | 2 | 6.5s |
| deepseek | design090 | 94 | A | 1 | 6 | 8.3s |
| deepseek | io扩展 | 96 | A+ | 1 | 3 | 5.9s |
| deepseek | 已走线 | 97 | A+ | 1 | 4 | 7.8s |
| deepseek | 泰山派无人机地面站 | 93 | A | 1 | 9 | 7.3s |
| deepseek | 游戏机扩展板V1.1.1 | 96 | A+ | 1 | 4 | 8.7s |
| deepseek | 游戏机扩展板diy | 96 | A+ | 1 | 4 | 6.5s |
| deepseek | 立创·逻辑派FPGA | 97 | A+ | 1 | 4 | 8.0s |

## 关键指标

- **BOM变更收敛率**: 62/63 (98%) (目标 > 70%)
- **全撤销收敛**: 21 个 — LLM 识别建议有害后撤销全部变更（防御闭环的正确收敛路径）
- **平均新违规引入**: 1.2 个/建议
- **平均修正轮次**: 1.4 (目标 ≤ 2.0)
- **幻觉消除率**: 98.4% (目标 > 80%)
- **纯分析建议**: 25 个 (无BOM变更)
- **⚠️ 解析失败/条目全丢弃**: 17 个 (零变更但非分析类, 不计入通过)
- **多智能体均分**: 97/100 (目标 > 75)
- **缺陷检出率**: 60/80 (75%)

### 缺陷注入详情

| 缺陷 | 预期规则 | 检出 | 命中 | 遗漏 |
|------|----------|------|------|------|
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ❌ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 否 | 0 | 3 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 电容耐压不足 | 电容耐压降额检查 | 否 | 0 | 1 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\mm20_deepseek_20261019_184759\results.json`
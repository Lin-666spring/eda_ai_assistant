# EI 论文实验报告

> 生成时间: 2026-10-20T14:47:33.680626
> 设计数: 21 | 建议数: 5 | LLM: glm

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| glm | 6寸屏幕转接板 | safe | ✅ | 0 | — | 1 | — | 31.6s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 4 | 4→0 | 2 | ✅ | 112.7s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 21.4s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 23.3s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 32.0s |
| glm | LCTSPI语音识别扩展板 | safe | ✅ | 0 | — | 1 | — | 4.6s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 0 | — | 1 | — | 105.2s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 26.8s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 22.1s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 27.0s |
| glm | P1 | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | P1 | dangerous | ❌ | 15 | 9→9 | 3 | ❌ | 228.1s |
| glm | P1 | optimization | ❌ | 4 | 10→10 | 3 | ❌ | 202.8s |
| glm | P1 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 41.2s |
| glm | P1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 33.4s |
| glm | V1.0.2_3 | safe | ✅ | 0 | — | 1 | — | 3.8s |
| glm | V1.0.2_3 | dangerous | ❌ | 5 | 2→2 | 3 | ❌ | 227.8s |
| glm | V1.0.2_3 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 170.3s |
| glm | V1.0.2_3 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 35.7s |
| glm | V1.0.2_3 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 65.7s |
| glm | XDS110 | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | XDS110 | dangerous | ❌ | 15 | 4→4 | 3 | ❌ | 249.2s |
| glm | XDS110 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 40.4s |
| glm | XDS110 | optimization | ✅ | 8 | 1→0 | 3 | ✅ | 191.4s |
| glm | XDS110 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 86.8s |
| glm | design009 | safe | ✅ | 0 | — | 1 | — | 3.0s |
| glm | design009 | dangerous | ❌ | 16 | 1→1 | 3 | ❌ | 207.3s |
| glm | design009 | optimization | ✅ | 2 | 1→0 | 3 | ✅ | 170.0s |
| glm | design009 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 65.3s |
| glm | design009 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 21.4s |
| glm | design013 | safe | ✅ | 0 | — | 1 | — | 3.2s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 100.3s |
| glm | design013 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 29.2s |
| glm | design013 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 58.5s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 55.2s |
| glm | design030 | safe | ✅ | 0 | — | 1 | — | 5.2s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 31.0s |
| glm | design030 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 26.7s |
| glm | design030 | optimization | ✅ | 6 | 1→0 | 3 | ✅ | 174.5s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 88.2s |
| glm | design031 | safe | ✅ | 0 | — | 1 | — | 3.0s |
| glm | design031 | dangerous | ❌ | 10 | 1→1 | 3 | ❌ | 228.4s |
| glm | design031 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 49.5s |
| glm | design031 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 38.9s |
| glm | design031 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 51.6s |
| glm | design038 | safe | ✅ | 0 | — | 1 | — | 3.4s |
| glm | design038 | dangerous | ❌ | 2 | 1→1 | 3 | ❌ | 248.0s |
| glm | design038 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 221.1s |
| glm | design038 | optimization | ✅ | 0 | — | 1 | — | 109.5s |
| glm | design038 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 22.2s |
| glm | design051 | safe | ✅ | 0 | — | 1 | — | 3.0s |
| glm | design051 | dangerous | ✅ | 0 | — | 1 | — | 120.3s |
| glm | design051 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 12.0s |
| glm | design051 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 38.3s |
| glm | design051 | dangerous | ✅ | 0 | — | 1 | — | 49.0s |
| glm | design054 | safe | ✅ | 0 | — | 1 | — | 4.0s |
| glm | design054 | dangerous | ✅ | 0 | — | 1 | — | 110.5s |
| glm | design054 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 54.0s |
| glm | design054 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 91.3s |
| glm | design054 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 83.7s |
| glm | design059 | safe | ✅ | 0 | — | 1 | — | 3.5s |
| glm | design059 | dangerous | ❌ | 1 | 1→1 | 3 | ❌ | 238.8s |
| glm | design059 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 40.8s |
| glm | design059 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 34.7s |
| glm | design059 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 96.3s |
| glm | design066 | safe | ✅ | 0 | — | 1 | — | 2.3s |
| glm | design066 | dangerous | ❌ | 1 | 1→1 | 3 | ❌ | 208.0s |
| glm | design066 | optimization | ✅ | 0 | — | 1 | — | 101.0s |
| glm | design066 | optimization | ✅ | 2 | 1→0 | 3 | ✅ | 133.6s |
| glm | design066 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 21.1s |
| glm | design090 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | design090 | dangerous | ✅ | 0 | — | 1 | — | 10.5s |
| glm | design090 | optimization | ❌ | 4 | 2→2 | 3 | ❌ | 229.9s |
| glm | design090 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 45.0s |
| glm | design090 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 39.1s |
| glm | io扩展 | safe | ✅ | 0 | — | 1 | — | 3.6s |
| glm | io扩展 | dangerous | ❌ | 2 | 1→1 | 3 | ❌ | 251.7s |
| glm | io扩展 | optimization | ❌ | 4 | 1→3 | 3 | ❌ | 191.8s |
| glm | io扩展 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 24.9s |
| glm | io扩展 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 48.9s |
| glm | 已走线 | safe | ✅ | 0 | — | 1 | — | 4.4s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 98.7s |
| glm | 已走线 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 49.4s |
| glm | 已走线 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 78.2s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 41.2s |
| glm | 泰山派无人机地面站 | safe | ✅ | 0 | — | 1 | — | 4.0s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 0 | — | 1 | — | 14.8s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 91.3s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 28.7s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 47.5s |
| glm | 游戏机扩展板V1.1.1 | safe | ✅ | 0 | — | 1 | — | 4.2s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 30.5s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 1 | 0→0 | 1 | ✅ | 24.7s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 44.8s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 52.9s |
| glm | 游戏机扩展板diy | safe | ✅ | 0 | — | 1 | — | 3.2s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 5 | 0→0 | 1 | ✅ | 17.5s |
| glm | 游戏机扩展板diy | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 58.9s |
| glm | 游戏机扩展板diy | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 51.0s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 41.6s |
| glm | 立创·逻辑派FPGA | safe | ✅ | 0 | — | 1 | — | 5.2s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 0 | — | 1 | — | 120.3s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 30.0s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 0 | — | 1 | — | 108.1s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 0 | — | 1 | — | 95.8s |

## 关键指标

- **BOM变更收敛率**: 53/67 (79%) (目标 > 70%)
- **全撤销收敛**: 0 个 — LLM 识别建议有害后撤销全部变更（防御闭环的正确收敛路径）
- **平均新违规引入**: 0.7 个/建议
- **平均修正轮次**: 1.6 (目标 ≤ 2.0)
- **幻觉消除率**: 76.1% (目标 > 80%)
- **纯分析建议**: 24 个 (无BOM变更)
- **⚠️ 解析失败/条目全丢弃**: 14 个 (零变更但非分析类, 不计入通过)

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\ablation2x2_C_norevert_20261020_124328\results.json`
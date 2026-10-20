# EI 论文实验报告

> 生成时间: 2026-10-20T14:11:54.467499
> 设计数: 21 | 建议数: 5 | LLM: glm

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| glm | 6寸屏幕转接板 | safe | ✅ | 0 | — | 1 | — | 7.0s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 4 | 4→0 | 2 | ✅ | 94.2s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 37.0s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 22.2s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 46.9s |
| glm | LCTSPI语音识别扩展板 | safe | ✅ | 0 | — | 1 | — | 3.0s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 8 | 1→0 | 2 | ✅ | 56.1s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 22.7s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 22.4s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 15.1s |
| glm | P1 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | P1 | dangerous | ✅ | 15 | 9→0 | 2 | ✅ | 69.8s |
| glm | P1 | optimization | ✅ | 4 | 10→0 | 2 | ✅ | 38.4s |
| glm | P1 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 27.0s |
| glm | P1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 37.1s |
| glm | V1.0.2_3 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | V1.0.2_3 | dangerous | ✅ | 5 | 2→0 | 2 | ✅ | 81.2s |
| glm | V1.0.2_3 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 213.4s |
| glm | V1.0.2_3 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 34.5s |
| glm | V1.0.2_3 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 73.6s |
| glm | XDS110 | safe | ✅ | 0 | — | 1 | — | 3.2s |
| glm | XDS110 | dangerous | ✅ | 15 | 4→0 | 2 | ✅ | 101.5s |
| glm | XDS110 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 48.0s |
| glm | XDS110 | optimization | ❌ | 8 | 1→1 | 3 | ❌ | 224.5s |
| glm | XDS110 | dangerous | ✅ | 0 | — | 1 | — | 59.2s |
| glm | design009 | safe | ✅ | 0 | — | 1 | — | 3.8s |
| glm | design009 | dangerous | ✅ | 16 | 1→0 | 2 | ✅ | 69.6s |
| glm | design009 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 56.8s |
| glm | design009 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 113.7s |
| glm | design009 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 62.2s |
| glm | design013 | safe | ✅ | 0 | — | 1 | — | 4.5s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 99.2s |
| glm | design013 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 27.1s |
| glm | design013 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 47.9s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 32.4s |
| glm | design030 | safe | ✅ | 0 | — | 1 | — | 2.9s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 23.5s |
| glm | design030 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 18.9s |
| glm | design030 | optimization | ✅ | 6 | 1→0 | 2 | ✅ | 120.4s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 42.1s |
| glm | design031 | safe | ✅ | 0 | — | 1 | — | 2.4s |
| glm | design031 | dangerous | ✅ | 10 | 1→0 | 2 | ✅ | 53.4s |
| glm | design031 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 50.2s |
| glm | design031 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 53.0s |
| glm | design031 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 75.9s |
| glm | design038 | safe | ✅ | 0 | — | 1 | — | 7.3s |
| glm | design038 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 96.3s |
| glm | design038 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 85.0s |
| glm | design038 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 38.9s |
| glm | design038 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 22.8s |
| glm | design051 | safe | ✅ | 0 | — | 1 | — | 3.4s |
| glm | design051 | dangerous | ✅ | 24 | 11→0 | 2 | ✅ | 103.0s |
| glm | design051 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 34.5s |
| glm | design051 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 36.3s |
| glm | design051 | dangerous | ✅ | 0 | — | 1 | — | 29.9s |
| glm | design054 | safe | ✅ | 0 | — | 1 | — | 3.5s |
| glm | design054 | dangerous | ✅ | 0 | — | 1 | — | 76.3s |
| glm | design054 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 37.4s |
| glm | design054 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 77.2s |
| glm | design054 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 48.3s |
| glm | design059 | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | design059 | dangerous | ✅ | 1 | 1→0 | 2 | ✅ | 32.3s |
| glm | design059 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 27.5s |
| glm | design059 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 24.0s |
| glm | design059 | dangerous | ✅ | 0 | — | 1 | — | 96.4s |
| glm | design066 | safe | ✅ | 0 | — | 1 | — | 2.5s |
| glm | design066 | dangerous | ✅ | 1 | 1→0 | 2 | ✅ | 40.9s |
| glm | design066 | optimization | ✅ | 2 | 2→0 | 2 | ✅ | 148.9s |
| glm | design066 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 102.5s |
| glm | design066 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 26.0s |
| glm | design090 | safe | ✅ | 0 | — | 1 | — | 5.8s |
| glm | design090 | dangerous | ✅ | 0 | — | 1 | — | 11.7s |
| glm | design090 | optimization | ✅ | 4 | 2→0 | 2 | ✅ | 120.1s |
| glm | design090 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 45.0s |
| glm | design090 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 34.9s |
| glm | io扩展 | safe | ✅ | 0 | — | 1 | — | 6.8s |
| glm | io扩展 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 61.3s |
| glm | io扩展 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 111.3s |
| glm | io扩展 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 18.8s |
| glm | io扩展 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 54.0s |
| glm | 已走线 | safe | ✅ | 0 | — | 1 | — | 4.9s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 112.3s |
| glm | 已走线 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 34.0s |
| glm | 已走线 | optimization | ✅ | 0 | — | 1 | — | 80.1s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 38.1s |
| glm | 泰山派无人机地面站 | safe | ✅ | 0 | — | 1 | — | 4.9s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 0 | — | 1 | — | 14.7s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 121.1s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 65.7s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 70.8s |
| glm | 游戏机扩展板V1.1.1 | safe | ✅ | 0 | — | 1 | — | 4.7s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 0 | — | 1 | — | 120.3s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 1 | 0→0 | 1 | ✅ | 66.2s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 69.0s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 0 | — | 1 | — | 97.3s |
| glm | 游戏机扩展板diy | safe | ✅ | 0 | — | 1 | — | 3.6s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 5 | 0→0 | 1 | ✅ | 50.2s |
| glm | 游戏机扩展板diy | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 49.0s |
| glm | 游戏机扩展板diy | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 39.3s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 27.9s |
| glm | 立创·逻辑派FPGA | safe | ✅ | 0 | — | 1 | — | 7.8s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 21 | 6→0 | 2 | ✅ | 94.6s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 53.7s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 44.6s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 53.5s |

## 关键指标

- **BOM变更收敛率**: 67/69 (97%) (目标 > 70%)
- **全撤销收敛**: 19 个 — LLM 识别建议有害后撤销全部变更（防御闭环的正确收敛路径）
- **平均新违规引入**: 1.0 个/建议
- **平均修正轮次**: 1.4 (目标 ≤ 2.0)
- **幻觉消除率**: 98.6% (目标 > 80%)
- **纯分析建议**: 26 个 (无BOM变更)
- **⚠️ 解析失败/条目全丢弃**: 10 个 (零变更但非分析类, 不计入通过)

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\ablation2x2_A_full_20261020_124328\results.json`
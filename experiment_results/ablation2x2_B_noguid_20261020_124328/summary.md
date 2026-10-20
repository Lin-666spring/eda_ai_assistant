# EI 论文实验报告

> 生成时间: 2026-10-20T14:07:11.676024
> 设计数: 21 | 建议数: 5 | LLM: glm

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| glm | 6寸屏幕转接板 | safe | ✅ | 0 | — | 1 | — | 7.3s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 4 | 4→0 | 2 | ✅ | 28.8s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 22.7s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 32.0s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 38.5s |
| glm | LCTSPI语音识别扩展板 | safe | ✅ | 0 | — | 1 | — | 3.3s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 8 | 1→0 | 2 | ✅ | 51.7s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 0 | — | 1 | — | 90.3s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 26.0s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 19.5s |
| glm | P1 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | P1 | dangerous | ✅ | 15 | 9→0 | 2 | ✅ | 40.9s |
| glm | P1 | optimization | ✅ | 4 | 10→0 | 3 | ✅ | 130.0s |
| glm | P1 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 43.0s |
| glm | P1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 38.7s |
| glm | V1.0.2_3 | safe | ✅ | 0 | — | 1 | — | 3.0s |
| glm | V1.0.2_3 | dangerous | ✅ | 5 | 2→0 | 2 | ✅ | 79.9s |
| glm | V1.0.2_3 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 78.2s |
| glm | V1.0.2_3 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 56.0s |
| glm | V1.0.2_3 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 75.7s |
| glm | XDS110 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | XDS110 | dangerous | ✅ | 15 | 4→0 | 2 | ✅ | 26.8s |
| glm | XDS110 | optimization | ✅ | 0 | — | 1 | — | 78.1s |
| glm | XDS110 | optimization | ✅ | 0 | — | 1 | — | 88.1s |
| glm | XDS110 | dangerous | ✅ | 0 | — | 1 | — | 54.0s |
| glm | design009 | safe | ✅ | 0 | — | 1 | — | 4.1s |
| glm | design009 | dangerous | ✅ | 16 | 1→0 | 2 | ✅ | 103.4s |
| glm | design009 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 61.2s |
| glm | design009 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 33.7s |
| glm | design009 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 29.6s |
| glm | design013 | safe | ✅ | 0 | — | 1 | — | 5.4s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 99.3s |
| glm | design013 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 35.6s |
| glm | design013 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 30.4s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 57.0s |
| glm | design030 | safe | ✅ | 0 | — | 1 | — | 3.6s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 35.0s |
| glm | design030 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 20.9s |
| glm | design030 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 71.8s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 47.7s |
| glm | design031 | safe | ✅ | 0 | — | 1 | — | 2.2s |
| glm | design031 | dangerous | ✅ | 10 | 1→0 | 2 | ✅ | 56.9s |
| glm | design031 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 30.8s |
| glm | design031 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 32.2s |
| glm | design031 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 86.8s |
| glm | design038 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | design038 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 46.6s |
| glm | design038 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 252.7s |
| glm | design038 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 37.0s |
| glm | design038 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 30.8s |
| glm | design051 | safe | ✅ | 0 | — | 1 | — | 6.6s |
| glm | design051 | dangerous | ✅ | 0 | — | 1 | — | 86.3s |
| glm | design051 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 11.0s |
| glm | design051 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 30.3s |
| glm | design051 | dangerous | ✅ | 0 | — | 1 | — | 23.6s |
| glm | design054 | safe | ✅ | 0 | — | 1 | — | 3.8s |
| glm | design054 | dangerous | ✅ | 0 | — | 1 | — | 73.3s |
| glm | design054 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 39.2s |
| glm | design054 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 66.7s |
| glm | design054 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 70.8s |
| glm | design059 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | design059 | dangerous | ✅ | 1 | 1→0 | 2 | ✅ | 62.3s |
| glm | design059 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 22.8s |
| glm | design059 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 23.7s |
| glm | design059 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 77.8s |
| glm | design066 | safe | ✅ | 0 | — | 1 | — | 3.3s |
| glm | design066 | dangerous | ✅ | 1 | 1→0 | 2 | ✅ | 25.4s |
| glm | design066 | optimization | ✅ | 3 | 2→0 | 2 | ✅ | 118.6s |
| glm | design066 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 93.0s |
| glm | design066 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 29.1s |
| glm | design090 | safe | ✅ | 0 | — | 1 | — | 3.4s |
| glm | design090 | dangerous | ✅ | 0 | — | 1 | — | 17.4s |
| glm | design090 | optimization | ❌ | 4 | 2→2 | 3 | ❌ | 219.6s |
| glm | design090 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 47.3s |
| glm | design090 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 26.1s |
| glm | io扩展 | safe | ✅ | 0 | — | 1 | — | 2.5s |
| glm | io扩展 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 38.0s |
| glm | io扩展 | optimization | ✅ | 4 | 1→0 | 2 | ✅ | 134.0s |
| glm | io扩展 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 21.4s |
| glm | io扩展 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 42.1s |
| glm | 已走线 | safe | ✅ | 0 | — | 1 | — | 4.8s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 99.0s |
| glm | 已走线 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 64.8s |
| glm | 已走线 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 69.2s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 80.7s |
| glm | 泰山派无人机地面站 | safe | ✅ | 0 | — | 1 | — | 4.1s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 0 | — | 1 | — | 15.4s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 4 | 1→0 | 3 | ✅ | 188.2s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 37.9s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 34.3s |
| glm | 游戏机扩展板V1.1.1 | safe | ✅ | 0 | — | 1 | — | 3.0s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 29.9s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 79.2s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 23.9s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 0 | — | 1 | — | 64.3s |
| glm | 游戏机扩展板diy | safe | ✅ | 0 | — | 1 | — | 2.5s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 0 | — | 1 | — | 106.8s |
| glm | 游戏机扩展板diy | optimization | ✅ | 1 | 0→0 | 1 | ✅ | 31.6s |
| glm | 游戏机扩展板diy | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 39.5s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 46.5s |
| glm | 立创·逻辑派FPGA | safe | ✅ | 0 | — | 1 | — | 15.1s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 21 | 6→0 | 2 | ✅ | 83.4s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 33.1s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 61.1s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 47.9s |

## 关键指标

- **BOM变更收敛率**: 65/67 (97%) (目标 > 70%)
- **全撤销收敛**: 18 个 — LLM 识别建议有害后撤销全部变更（防御闭环的正确收敛路径）
- **平均新违规引入**: 0.8 个/建议
- **平均修正轮次**: 1.4 (目标 ≤ 2.0)
- **幻觉消除率**: 97.0% (目标 > 80%)
- **纯分析建议**: 29 个 (无BOM变更)
- **⚠️ 解析失败/条目全丢弃**: 9 个 (零变更但非分析类, 不计入通过)

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\ablation2x2_B_noguid_20261020_124328\results.json`
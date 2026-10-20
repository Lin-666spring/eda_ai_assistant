# EI 论文实验报告

> 生成时间: 2026-10-20T14:49:00.964614
> 设计数: 21 | 建议数: 5 | LLM: glm

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| glm | 6寸屏幕转接板 | safe | ✅ | 0 | — | 1 | — | 6.2s |
| glm | 6寸屏幕转接板 | dangerous | ❌ | 4 | 4→4 | 3 | ❌ | 163.5s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 32.9s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 16.6s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 31.3s |
| glm | LCTSPI语音识别扩展板 | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | LCTSPI语音识别扩展板 | dangerous | ❌ | 8 | 1→1 | 3 | ❌ | 146.8s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 41.1s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 17.5s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 39.9s |
| glm | P1 | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | P1 | dangerous | ❌ | 15 | 9→9 | 3 | ❌ | 198.2s |
| glm | P1 | optimization | ✅ | 4 | 10→0 | 2 | ✅ | 68.8s |
| glm | P1 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 36.1s |
| glm | P1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 42.7s |
| glm | V1.0.2_3 | safe | ✅ | 0 | — | 1 | — | 3.8s |
| glm | V1.0.2_3 | dangerous | ❌ | 5 | 2→2 | 3 | ❌ | 177.4s |
| glm | V1.0.2_3 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 132.4s |
| glm | V1.0.2_3 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 40.9s |
| glm | V1.0.2_3 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 69.9s |
| glm | XDS110 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | XDS110 | dangerous | ❌ | 15 | 4→4 | 3 | ❌ | 272.4s |
| glm | XDS110 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 49.8s |
| glm | XDS110 | optimization | ✅ | 8 | 1→0 | 2 | ✅ | 115.4s |
| glm | XDS110 | dangerous | ✅ | 0 | — | 1 | — | 90.2s |
| glm | design009 | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | design009 | dangerous | ❌ | 16 | 1→2 | 3 | ❌ | 209.0s |
| glm | design009 | optimization | ❌ | 2 | 1→2 | 3 | ❌ | 216.9s |
| glm | design009 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 55.5s |
| glm | design009 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 28.4s |
| glm | design013 | safe | ✅ | 0 | — | 1 | — | 9.8s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 82.5s |
| glm | design013 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 32.1s |
| glm | design013 | optimization | ✅ | 0 | — | 1 | — | 71.0s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 41.7s |
| glm | design030 | safe | ✅ | 0 | — | 1 | — | 2.9s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 13.2s |
| glm | design030 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 17.5s |
| glm | design030 | optimization | ✅ | 6 | 1→0 | 2 | ✅ | 82.5s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 94.2s |
| glm | design031 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | design031 | dangerous | ❌ | 10 | 1→1 | 3 | ❌ | 274.8s |
| glm | design031 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 53.7s |
| glm | design031 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 20.2s |
| glm | design031 | dangerous | ✅ | 0 | — | 1 | — | 95.9s |
| glm | design038 | safe | ✅ | 0 | — | 1 | — | 3.1s |
| glm | design038 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 135.1s |
| glm | design038 | optimization | ✅ | 0 | — | 1 | — | 96.3s |
| glm | design038 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 77.3s |
| glm | design038 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 28.9s |
| glm | design051 | safe | ✅ | 0 | — | 1 | — | 3.2s |
| glm | design051 | dangerous | ❌ | 24 | 11→11 | 3 | ❌ | 237.4s |
| glm | design051 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 12.8s |
| glm | design051 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 40.0s |
| glm | design051 | dangerous | ✅ | 0 | — | 1 | — | 25.9s |
| glm | design054 | safe | ✅ | 0 | — | 1 | — | 3.3s |
| glm | design054 | dangerous | ✅ | 0 | — | 1 | — | 108.5s |
| glm | design054 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 77.0s |
| glm | design054 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 72.3s |
| glm | design054 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 44.0s |
| glm | design059 | safe | ✅ | 0 | — | 1 | — | 3.8s |
| glm | design059 | dangerous | ❌ | 1 | 1→1 | 3 | ❌ | 327.4s |
| glm | design059 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 53.4s |
| glm | design059 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 24.1s |
| glm | design059 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 77.9s |
| glm | design066 | safe | ✅ | 0 | — | 1 | — | 3.2s |
| glm | design066 | dangerous | ❌ | 1 | 1→1 | 3 | ❌ | 189.6s |
| glm | design066 | optimization | ❌ | 2 | 2→2 | 3 | ❌ | 243.3s |
| glm | design066 | optimization | ✅ | 2 | 1→0 | 2 | ✅ | 64.3s |
| glm | design066 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 63.1s |
| glm | design090 | safe | ✅ | 0 | — | 1 | — | 9.7s |
| glm | design090 | dangerous | ✅ | 0 | — | 1 | — | 18.0s |
| glm | design090 | optimization | ❌ | 4 | 2→2 | 3 | ❌ | 218.6s |
| glm | design090 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 28.1s |
| glm | design090 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 17.2s |
| glm | io扩展 | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | io扩展 | dangerous | ❌ | 2 | 1→1 | 3 | ❌ | 221.8s |
| glm | io扩展 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 234.4s |
| glm | io扩展 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 43.3s |
| glm | io扩展 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 20.9s |
| glm | 已走线 | safe | ✅ | 0 | — | 1 | — | 8.0s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 92.4s |
| glm | 已走线 | optimization | ✅ | 0 | — | 1 | — | 92.2s |
| glm | 已走线 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 57.5s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 45.1s |
| glm | 泰山派无人机地面站 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 0 | — | 1 | — | 11.7s |
| glm | 泰山派无人机地面站 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 208.3s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 0 | — | 1 | — | 101.9s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 52.6s |
| glm | 游戏机扩展板V1.1.1 | safe | ✅ | 0 | — | 1 | — | 4.6s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 43.9s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 1 | 0→0 | 1 | ✅ | 48.7s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 43.3s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 0 | — | 1 | — | 33.6s |
| glm | 游戏机扩展板diy | safe | ✅ | 0 | — | 1 | — | 5.9s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 5 | 0→0 | 1 | ✅ | 48.0s |
| glm | 游戏机扩展板diy | optimization | ✅ | 1 | 0→0 | 1 | ✅ | 85.9s |
| glm | 游戏机扩展板diy | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 48.3s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 41.3s |
| glm | 立创·逻辑派FPGA | safe | ✅ | 0 | — | 1 | — | 2.7s |
| glm | 立创·逻辑派FPGA | dangerous | ❌ | 21 | 6→6 | 3 | ❌ | 249.7s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 45.1s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 73.2s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 46.8s |

## 关键指标

- **BOM变更收敛率**: 49/67 (73%) (目标 > 70%)
- **全撤销收敛**: 0 个 — LLM 识别建议有害后撤销全部变更（防御闭环的正确收敛路径）
- **平均新违规引入**: 1.0 个/建议
- **平均修正轮次**: 1.6 (目标 ≤ 2.0)
- **幻觉消除率**: 73.1% (目标 > 80%)
- **纯分析建议**: 26 个 (无BOM变更)
- **⚠️ 解析失败/条目全丢弃**: 12 个 (零变更但非分析类, 不计入通过)

---
📁 完整 JSON 数据: `C:\Users\lin\Desktop\eda_ai_assistant\experiment_results\ablation2x2_D_neither_20261020_124328\results.json`
# EI 论文实验报告

> 生成时间: 2026-09-13T23:43:20.444948
> 设计数: 79 | 建议数: 5 | LLM: glm

## 阶段 A: DRC 基线

| 设计 | 总违规 | 错误 | 警告 | 信息 | 耗时 |
|------|--------|------|------|------|------|
| 01Phone | 34 | 0 | 4 | 30 | 1.4s |
| 01Phone_2 | 21 | 0 | 3 | 18 | 0.1s |
| 6寸屏幕转接板 | 12 | 0 | 2 | 10 | 0.0s |
| design002 | 15 | 0 | 9 | 6 | 0.0s |
| design003 | 59 | 0 | 4 | 55 | 0.2s |
| design006 | 18 | 0 | 2 | 16 | 0.0s |
| design007 | 5 | 0 | 1 | 4 | 0.0s |
| design008 | 15 | 0 | 2 | 13 | 0.1s |
| design009 | 11 | 0 | 3 | 8 | 0.0s |
| design010 | 11 | 2 | 2 | 7 | 0.0s |
| design011 | 10 | 2 | 2 | 6 | 0.0s |
| design013 | 38 | 0 | 3 | 35 | 0.1s |
| design015 | 13 | 0 | 1 | 12 | 0.0s |
| design017 | 18 | 0 | 4 | 14 | 0.0s |
| design021 | 22 | 0 | 4 | 18 | 0.1s |
| design022 | 20 | 0 | 14 | 6 | 0.0s |
| design028 | 27 | 0 | 4 | 23 | 0.1s |
| design029 | 13 | 0 | 3 | 10 | 0.1s |
| design030 | 17 | 3 | 7 | 7 | 0.0s |
| design031 | 24 | 0 | 4 | 20 | 0.1s |
| design032 | 12 | 0 | 5 | 7 | 0.0s |
| design035 | 9 | 0 | 2 | 7 | 0.0s |
| design037 | 21 | 0 | 3 | 18 | 0.1s |
| design038 | 7 | 0 | 3 | 4 | 0.0s |
| design039 | 16 | 0 | 3 | 13 | 0.1s |
| design040 | 15 | 0 | 4 | 11 | 0.0s |
| design042 | 23 | 0 | 8 | 15 | 0.1s |
| design043 | 15 | 0 | 8 | 7 | 0.0s |
| design046 | 7 | 1 | 3 | 3 | 0.0s |
| design051 | 26 | 0 | 4 | 22 | 0.1s |
| design054 | 73 | 0 | 6 | 67 | 0.6s |
| design057 | 27 | 0 | 2 | 25 | 0.1s |
| design059 | 12 | 0 | 5 | 7 | 0.0s |
| design062 | 11 | 2 | 2 | 7 | 0.0s |
| design063 | 11 | 2 | 1 | 8 | 0.0s |
| design064 | 10 | 2 | 2 | 6 | 0.0s |
| design066 | 10 | 0 | 3 | 7 | 0.0s |
| design067 | 13 | 3 | 3 | 7 | 0.0s |
| design068 | 7 | 0 | 3 | 4 | 0.0s |
| design069 | 6 | 0 | 2 | 4 | 0.0s |
| design070 | 11 | 0 | 5 | 6 | 0.0s |
| design073 | 15 | 0 | 6 | 9 | 0.0s |
| design077 | 18 | 0 | 5 | 13 | 0.0s |
| design079 | 9 | 0 | 5 | 4 | 0.0s |
| design081 | 7 | 1 | 3 | 3 | 0.0s |
| design082 | 10 | 0 | 3 | 7 | 0.0s |
| design083 | 16 | 4 | 8 | 4 | 0.0s |
| design087 | 31 | 0 | 3 | 28 | 0.1s |
| design089 | 27 | 0 | 4 | 23 | 0.1s |
| design090 | 9 | 1 | 6 | 2 | 0.0s |
| design091 | 16 | 0 | 4 | 12 | 0.1s |
| F28034 | 14 | 0 | 5 | 9 | 0.1s |
| io扩展 | 17 | 0 | 2 | 15 | 0.0s |
| LCTSPI语音识别扩展板 | 13 | 0 | 3 | 10 | 0.0s |
| P1 | 22 | 0 | 3 | 19 | 0.1s |
| RK3506G | 24 | 0 | 3 | 21 | 0.1s |
| S3的温湿度云监测系统 | 18 | 5 | 6 | 7 | 0.0s |
| Schematic2 | 12 | 0 | 3 | 9 | 0.0s |
| V1.0.2 | 15 | 0 | 8 | 7 | 0.0s |
| V1.0.2_2 | 13 | 0 | 2 | 11 | 0.1s |
| V1.0.2_3 | 21 | 0 | 4 | 17 | 0.1s |
| XDS110 | 20 | 0 | 2 | 18 | 0.1s |
| 地奇星RA6E2 | 15 | 0 | 4 | 11 | 0.0s |
| 已走线 | 63 | 0 | 4 | 59 | 0.3s |
| 显示屏触摸转接底座 | 7 | 2 | 4 | 1 | 0.0s |
| 智能小车V0.1.2 | 20 | 7 | 6 | 7 | 0.0s |
| 梁山派车载式路面平整度测量器 | 12 | 2 | 5 | 5 | 0.0s |
| 模块化版本 | 20 | 0 | 13 | 7 | 0.0s |
| 泰山派4寸86屏转接板 | 11 | 0 | 2 | 9 | 0.0s |
| 泰山派无人机地面站 | 20 | 2 | 5 | 13 | 0.1s |
| 游戏机扩展板diy | 19 | 0 | 5 | 14 | 0.0s |
| 游戏机扩展板V1.1.1 | 17 | 0 | 5 | 12 | 0.0s |
| 电创派V2.0 | 17 | 0 | 4 | 13 | 0.1s |
| 电压电流表 | 15 | 0 | 4 | 11 | 0.0s |
| 立创·庐山派K230 | 49 | 0 | 4 | 45 | 0.2s |
| 立创·泰山派3M(RK3576)开发板V1.4 | 75 | 0 | 5 | 70 | 0.3s |
| 立创·逻辑派FPGA | 13 | 0 | 2 | 11 | 0.1s |
| 载板 | 25 | 0 | 6 | 19 | 0.1s |
| 辐射检测扩展板原理图V1.0.0 | 23 | 0 | 4 | 19 | 0.1s |

## 阶段 B: 闭环验证

| 提供者 | 设计 | 建议类型 | 通过 | 变更数 | 新违规 | 轮次 | 收敛 | 耗时 |
|--------|------|----------|------|--------|--------|------|------|------|
| glm | 01Phone | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | 01Phone | dangerous | ✅ | 22 | 10→0 | 2 | ✅ | 45.0s |
| glm | 01Phone | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 20.2s |
| glm | 01Phone | optimization | ✅ | 0 | — | 1 | — | 5.5s |
| glm | 01Phone | dangerous | ✅ | 0 | — | 1 | — | 11.9s |
| glm | 01Phone_2 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | 01Phone_2 | dangerous | ✅ | 9 | 4→0 | 2 | ✅ | 19.7s |
| glm | 01Phone_2 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 14.6s |
| glm | 01Phone_2 | optimization | ✅ | 0 | — | 1 | — | 18.0s |
| glm | 01Phone_2 | dangerous | ✅ | 0 | — | 1 | — | 36.9s |
| glm | 6寸屏幕转接板 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 4 | 3→0 | 2 | ✅ | 37.3s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 18.0s |
| glm | 6寸屏幕转接板 | optimization | ✅ | 0 | — | 1 | — | 10.7s |
| glm | 6寸屏幕转接板 | dangerous | ✅ | 0 | — | 1 | — | 7.4s |
| glm | design002 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | design002 | dangerous | ✅ | 2 | 0→0 | 2 | ✅ | 14.7s |
| glm | design002 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 21.2s |
| glm | design002 | optimization | ✅ | 0 | — | 1 | — | 10.2s |
| glm | design002 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 32.3s |
| glm | design003 | safe | ✅ | 0 | — | 1 | — | 2.3s |
| glm | design003 | dangerous | ✅ | 0 | — | 1 | — | 42.7s |
| glm | design003 | optimization | ✅ | 0 | — | 1 | — | 38.8s |
| glm | design003 | optimization | ✅ | 0 | — | 1 | — | 13.2s |
| glm | design003 | dangerous | ✅ | 0 | — | 1 | — | 10.2s |
| glm | design006 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | design006 | dangerous | ✅ | 0 | — | 1 | — | 48.6s |
| glm | design006 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 22.8s |
| glm | design006 | optimization | ✅ | 0 | — | 1 | — | 7.3s |
| glm | design006 | dangerous | ✅ | 0 | — | 1 | — | 47.7s |
| glm | design007 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | design007 | dangerous | ✅ | 0 | — | 1 | — | 52.4s |
| glm | design007 | optimization | ❌ | 2 | 1→1 | 3 | ❌ | 98.1s |
| glm | design007 | optimization | ✅ | 0 | — | 1 | — | 7.0s |
| glm | design007 | dangerous | ✅ | 0 | — | 1 | — | 41.7s |
| glm | design008 | safe | ✅ | 0 | — | 1 | — | 2.4s |
| glm | design008 | dangerous | ✅ | 7 | 5→0 | 2 | ✅ | 38.8s |
| glm | design008 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 20.2s |
| glm | design008 | optimization | ✅ | 0 | — | 1 | — | 7.8s |
| glm | design008 | dangerous | ✅ | 0 | — | 1 | — | 27.4s |
| glm | design009 | safe | ✅ | 0 | — | 1 | — | 2.5s |
| glm | design009 | dangerous | ✅ | 16 | 0→0 | 2 | ✅ | 39.0s |
| glm | design009 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 23.4s |
| glm | design009 | optimization | ✅ | 0 | — | 1 | — | 7.6s |
| glm | design009 | dangerous | ✅ | 0 | — | 1 | — | 10.8s |
| glm | design010 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | design010 | dangerous | ✅ | 0 | — | 1 | — | 7.0s |
| glm | design010 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 9.9s |
| glm | design010 | optimization | ✅ | 0 | — | 1 | — | 16.2s |
| glm | design010 | dangerous | ✅ | 0 | — | 1 | — | 17.3s |
| glm | design011 | safe | ✅ | 0 | — | 1 | — | 2.0s |
| glm | design011 | dangerous | ✅ | 0 | — | 1 | — | 9.0s |
| glm | design011 | optimization | ❌ | 4 | 1→1 | 3 | ❌ | 100.1s |
| glm | design011 | optimization | ✅ | 0 | — | 1 | — | 11.0s |
| glm | design011 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 40.6s |
| glm | design013 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 43.7s |
| glm | design013 | optimization | ✅ | 0 | — | 1 | — | 16.8s |
| glm | design013 | optimization | ✅ | 0 | — | 1 | — | 6.5s |
| glm | design013 | dangerous | ✅ | 0 | — | 1 | — | 9.9s |
| glm | design015 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | design015 | dangerous | ✅ | 0 | — | 1 | — | 7.0s |
| glm | design015 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 9.7s |
| glm | design015 | optimization | ✅ | 0 | — | 1 | — | 8.0s |
| glm | design015 | dangerous | ✅ | 0 | — | 1 | — | 13.4s |
| glm | design017 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | design017 | dangerous | ✅ | 5 | 0→0 | 2 | ✅ | 39.2s |
| glm | design017 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 9.6s |
| glm | design017 | optimization | ✅ | 0 | — | 1 | — | 11.5s |
| glm | design017 | dangerous | ✅ | 0 | — | 1 | — | 17.6s |
| glm | design021 | safe | ✅ | 0 | — | 1 | — | 2.0s |
| glm | design021 | dangerous | ✅ | 11 | 8→0 | 2 | ✅ | 18.3s |
| glm | design021 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 25.2s |
| glm | design021 | optimization | ✅ | 0 | — | 1 | — | 13.1s |
| glm | design021 | dangerous | ✅ | 0 | — | 1 | — | 12.7s |
| glm | design022 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | design022 | dangerous | ✅ | 1 | 1→0 | 2 | ✅ | 15.2s |
| glm | design022 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 32.6s |
| glm | design022 | optimization | ✅ | 0 | — | 1 | — | 39.5s |
| glm | design022 | dangerous | ✅ | 0 | — | 1 | — | 42.1s |
| glm | design028 | safe | ✅ | 0 | — | 1 | — | 4.7s |
| glm | design028 | dangerous | ✅ | 0 | — | 1 | — | 46.3s |
| glm | design028 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 29.6s |
| glm | design028 | optimization | ✅ | 0 | — | 1 | — | 46.5s |
| glm | design028 | dangerous | ✅ | 0 | — | 1 | — | 37.0s |
| glm | design029 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | design029 | dangerous | ✅ | 3 | 1→0 | 2 | ✅ | 36.2s |
| glm | design029 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 12.7s |
| glm | design029 | optimization | ✅ | 0 | — | 1 | — | 46.1s |
| glm | design029 | dangerous | ✅ | 0 | — | 1 | — | 44.7s |
| glm | design030 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 6.7s |
| glm | design030 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 19.4s |
| glm | design030 | optimization | ✅ | 0 | — | 1 | — | 44.9s |
| glm | design030 | dangerous | ✅ | 0 | — | 1 | — | 40.3s |
| glm | design031 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | design031 | dangerous | ✅ | 10 | 0→0 | 2 | ✅ | 25.2s |
| glm | design031 | optimization | ✅ | 0 | — | 1 | — | 40.1s |
| glm | design031 | optimization | ✅ | 0 | — | 1 | — | 8.4s |
| glm | design031 | dangerous | ✅ | 0 | — | 1 | — | 13.0s |
| glm | design032 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | design032 | dangerous | ✅ | 2 | 0→0 | 2 | ✅ | 15.7s |
| glm | design032 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 13.0s |
| glm | design032 | optimization | ✅ | 0 | — | 1 | — | 8.4s |
| glm | design032 | dangerous | ✅ | 0 | — | 1 | — | 31.5s |
| glm | design035 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | design035 | dangerous | ✅ | 4 | 1→0 | 2 | ✅ | 50.1s |
| glm | design035 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 13.3s |
| glm | design035 | optimization | ✅ | 0 | — | 1 | — | 10.0s |
| glm | design035 | dangerous | ✅ | 0 | — | 1 | — | 27.9s |
| glm | design037 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | design037 | dangerous | ✅ | 6 | 0→0 | 1 | ✅ | 15.5s |
| glm | design037 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 14.0s |
| glm | design037 | optimization | ✅ | 0 | — | 1 | — | 9.6s |
| glm | design037 | dangerous | ✅ | 0 | — | 1 | — | 26.8s |
| glm | design038 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | design038 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 9.5s |
| glm | design038 | optimization | ✅ | 0 | — | 1 | — | 45.7s |
| glm | design038 | optimization | ✅ | 0 | — | 1 | — | 8.1s |
| glm | design038 | dangerous | ✅ | 0 | — | 1 | — | 22.3s |
| glm | design039 | safe | ✅ | 0 | — | 1 | — | 2.2s |
| glm | design039 | dangerous | ✅ | 4 | 3→0 | 2 | ✅ | 15.3s |
| glm | design039 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 8.1s |
| glm | design039 | optimization | ✅ | 0 | — | 1 | — | 10.3s |
| glm | design039 | dangerous | ✅ | 0 | — | 1 | — | 45.9s |
| glm | design040 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | design040 | dangerous | ✅ | 0 | — | 1 | — | 53.1s |
| glm | design040 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 27.4s |
| glm | design040 | optimization | ✅ | 0 | — | 1 | — | 10.6s |
| glm | design040 | dangerous | ✅ | 0 | — | 1 | — | 20.5s |
| glm | design042 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | design042 | dangerous | ✅ | 4 | 0→0 | 2 | ✅ | 17.8s |
| glm | design042 | optimization | ✅ | 14 | 0→0 | 1 | ✅ | 23.5s |
| glm | design042 | optimization | ✅ | 0 | — | 1 | — | 10.2s |
| glm | design042 | dangerous | ✅ | 0 | — | 1 | — | 21.3s |
| glm | design043 | safe | ✅ | 0 | — | 1 | — | 3.3s |
| glm | design043 | dangerous | ✅ | 0 | — | 1 | — | 46.0s |
| glm | design043 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 23.3s |
| glm | design043 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 22.5s |
| glm | design043 | dangerous | ✅ | 0 | — | 1 | — | 18.6s |
| glm | design046 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | design046 | dangerous | ✅ | 0 | — | 1 | — | 7.8s |
| glm | design046 | optimization | ✅ | 0 | — | 1 | — | 41.3s |
| glm | design046 | optimization | ❌ | 6 | 3→3 | 3 | ❌ | 111.5s |
| glm | design046 | dangerous | ✅ | 0 | — | 1 | — | 19.8s |
| glm | design051 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | design051 | dangerous | ✅ | 24 | 10→0 | 2 | ✅ | 27.6s |
| glm | design051 | optimization | ✅ | 0 | — | 1 | — | 23.1s |
| glm | design051 | optimization | ✅ | 0 | — | 1 | — | 9.6s |
| glm | design051 | dangerous | ✅ | 0 | — | 1 | — | 10.9s |
| glm | design054 | safe | ✅ | 0 | — | 1 | — | 3.6s |
| glm | design054 | dangerous | ✅ | 0 | — | 1 | — | 38.5s |
| glm | design054 | optimization | ✅ | 3 | 0→0 | 1 | ✅ | 28.8s |
| glm | design054 | optimization | ✅ | 0 | — | 1 | — | 6.4s |
| glm | design054 | dangerous | ✅ | 0 | — | 1 | — | 8.6s |
| glm | design057 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | design057 | dangerous | ✅ | 0 | — | 1 | — | 35.6s |
| glm | design057 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 20.4s |
| glm | design057 | optimization | ✅ | 0 | — | 1 | — | 11.4s |
| glm | design057 | dangerous | ✅ | 0 | — | 1 | — | 8.4s |
| glm | design059 | safe | ✅ | 0 | — | 1 | — | 2.5s |
| glm | design059 | dangerous | ✅ | 1 | 0→0 | 2 | ✅ | 30.5s |
| glm | design059 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 27.0s |
| glm | design059 | optimization | ✅ | 0 | — | 1 | — | 14.9s |
| glm | design059 | dangerous | ✅ | 0 | — | 1 | — | 46.8s |
| glm | design062 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | design062 | dangerous | ✅ | 0 | — | 1 | — | 6.3s |
| glm | design062 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 8.5s |
| glm | design062 | optimization | ✅ | 0 | — | 1 | — | 15.4s |
| glm | design062 | dangerous | ✅ | 0 | — | 1 | — | 17.3s |
| glm | design063 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | design063 | dangerous | ✅ | 0 | — | 1 | — | 7.2s |
| glm | design063 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 8.0s |
| glm | design063 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 31.3s |
| glm | design063 | dangerous | ✅ | 0 | — | 1 | — | 35.3s |
| glm | design064 | safe | ✅ | 0 | — | 1 | — | 2.5s |
| glm | design064 | dangerous | ✅ | 0 | — | 1 | — | 7.4s |
| glm | design064 | optimization | ✅ | 4 | 1→0 | 3 | ✅ | 88.8s |
| glm | design064 | optimization | ✅ | 0 | — | 1 | — | 7.5s |
| glm | design064 | dangerous | ✅ | 0 | — | 1 | — | 45.8s |
| glm | design066 | safe | ✅ | 0 | — | 1 | — | 5.5s |
| glm | design066 | dangerous | ✅ | 1 | 0→0 | 1 | ✅ | 5.6s |
| glm | design066 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 10.4s |
| glm | design066 | optimization | ✅ | 0 | — | 1 | — | 11.5s |
| glm | design066 | dangerous | ✅ | 0 | — | 1 | — | 18.2s |
| glm | design067 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | design067 | dangerous | ✅ | 0 | — | 1 | — | 7.7s |
| glm | design067 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 7.9s |
| glm | design067 | optimization | ✅ | 0 | — | 1 | — | 8.6s |
| glm | design067 | dangerous | ✅ | 0 | — | 1 | — | 20.7s |
| glm | design068 | safe | ✅ | 0 | — | 1 | — | 2.2s |
| glm | design068 | dangerous | ✅ | 2 | 1→0 | 2 | ✅ | 37.7s |
| glm | design068 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 16.7s |
| glm | design068 | optimization | ✅ | 0 | — | 1 | — | 11.0s |
| glm | design068 | dangerous | ✅ | 0 | — | 1 | — | 41.6s |
| glm | design069 | safe | ✅ | 0 | — | 1 | — | 5.3s |
| glm | design069 | dangerous | ✅ | 4 | 0→0 | 1 | ✅ | 17.3s |
| glm | design069 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 40.0s |
| glm | design069 | optimization | ✅ | 0 | — | 1 | — | 11.5s |
| glm | design069 | dangerous | ✅ | 0 | — | 1 | — | 5.6s |
| glm | design070 | safe | ✅ | 0 | — | 1 | — | 1.5s |
| glm | design070 | dangerous | ✅ | 3 | 2→0 | 2 | ✅ | 19.6s |
| glm | design070 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 7.6s |
| glm | design070 | optimization | ✅ | 0 | — | 1 | — | 9.6s |
| glm | design070 | dangerous | ✅ | 0 | — | 1 | — | 49.4s |
| glm | design073 | safe | ✅ | 0 | — | 1 | — | 4.4s |
| glm | design073 | dangerous | ✅ | 3 | 1→0 | 2 | ✅ | 41.0s |
| glm | design073 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 13.1s |
| glm | design073 | optimization | ✅ | 0 | — | 1 | — | 5.5s |
| glm | design073 | dangerous | ✅ | 0 | — | 1 | — | 14.4s |
| glm | design077 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | design077 | dangerous | ✅ | 5 | 0→0 | 2 | ✅ | 38.2s |
| glm | design077 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 31.6s |
| glm | design077 | optimization | ✅ | 0 | — | 1 | — | 7.0s |
| glm | design077 | dangerous | ✅ | 0 | — | 1 | — | 25.2s |
| glm | design079 | safe | ✅ | 0 | — | 1 | — | 2.1s |
| glm | design079 | dangerous | ✅ | 3 | 0→0 | 2 | ✅ | 9.5s |
| glm | design079 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 14.7s |
| glm | design079 | optimization | ✅ | 0 | — | 1 | — | 7.7s |
| glm | design079 | dangerous | ✅ | 0 | — | 1 | — | 18.9s |
| glm | design081 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | design081 | dangerous | ✅ | 0 | — | 1 | — | 6.1s |
| glm | design081 | optimization | ✅ | 0 | — | 1 | — | 44.9s |
| glm | design081 | optimization | ✅ | 0 | — | 1 | — | 12.0s |
| glm | design081 | dangerous | ✅ | 0 | — | 1 | — | 21.7s |
| glm | design082 | safe | ✅ | 0 | — | 1 | — | 2.2s |
| glm | design082 | dangerous | ✅ | 8 | 0→0 | 2 | ✅ | 13.2s |
| glm | design082 | optimization | ✅ | 0 | — | 1 | — | 45.2s |
| glm | design082 | optimization | ✅ | 0 | — | 1 | — | 5.0s |
| glm | design082 | dangerous | ✅ | 0 | — | 1 | — | 38.7s |
| glm | design083 | safe | ✅ | 0 | — | 1 | — | 2.0s |
| glm | design083 | dangerous | ✅ | 0 | — | 1 | — | 21.0s |
| glm | design083 | optimization | ❌ | 6 | 3→3 | 3 | ❌ | 102.1s |
| glm | design083 | optimization | ✅ | 0 | — | 1 | — | 9.7s |
| glm | design083 | dangerous | ✅ | 0 | — | 1 | — | 10.1s |
| glm | design087 | safe | ✅ | 0 | — | 1 | — | 3.1s |
| glm | design087 | dangerous | ✅ | 7 | 0→0 | 2 | ✅ | 22.1s |
| glm | design087 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 12.8s |
| glm | design087 | optimization | ✅ | 0 | — | 1 | — | 12.4s |
| glm | design087 | dangerous | ✅ | 0 | — | 1 | — | 16.9s |
| glm | design089 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | design089 | dangerous | ✅ | 3 | 0→0 | 1 | ✅ | 23.6s |
| glm | design089 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 32.1s |
| glm | design089 | optimization | ✅ | 0 | — | 1 | — | 9.0s |
| glm | design089 | dangerous | ✅ | 0 | — | 1 | — | 18.7s |
| glm | design090 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | design090 | dangerous | ✅ | 0 | — | 1 | — | 4.0s |
| glm | design090 | optimization | ❌ | 2 | 1→1 | 3 | ❌ | 89.7s |
| glm | design090 | optimization | ✅ | 0 | — | 1 | — | 9.5s |
| glm | design090 | dangerous | ✅ | 0 | — | 1 | — | 27.8s |
| glm | design091 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | design091 | dangerous | ✅ | 10 | 0→0 | 2 | ✅ | 16.5s |
| glm | design091 | optimization | ✅ | 14 | 0→0 | 1 | ✅ | 21.1s |
| glm | design091 | optimization | ✅ | 0 | — | 1 | — | 7.2s |
| glm | design091 | dangerous | ✅ | 0 | — | 1 | — | 29.6s |
| glm | F28034 | safe | ✅ | 0 | — | 1 | — | 9.7s |
| glm | F28034 | dangerous | ✅ | 2 | 0→0 | 2 | ✅ | 22.9s |
| glm | F28034 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 29.5s |
| glm | F28034 | optimization | ✅ | 0 | — | 1 | — | 11.9s |
| glm | F28034 | dangerous | ✅ | 0 | — | 1 | — | 31.4s |
| glm | io扩展 | safe | ✅ | 0 | — | 1 | — | 3.1s |
| glm | io扩展 | dangerous | ✅ | 2 | 0→0 | 2 | ✅ | 14.0s |
| glm | io扩展 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 17.3s |
| glm | io扩展 | optimization | ✅ | 0 | — | 1 | — | 6.3s |
| glm | io扩展 | dangerous | ✅ | 0 | — | 1 | — | 17.9s |
| glm | LCTSPI语音识别扩展板 | safe | ✅ | 0 | — | 1 | — | 2.6s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 8 | 1→0 | 2 | ✅ | 36.0s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 18.4s |
| glm | LCTSPI语音识别扩展板 | optimization | ✅ | 0 | — | 1 | — | 12.8s |
| glm | LCTSPI语音识别扩展板 | dangerous | ✅ | 0 | — | 1 | — | 17.2s |
| glm | P1 | safe | ✅ | 0 | — | 1 | — | 5.7s |
| glm | P1 | dangerous | ✅ | 15 | 8→0 | 2 | ✅ | 45.9s |
| glm | P1 | optimization | ✅ | 14 | 0→0 | 1 | ✅ | 28.2s |
| glm | P1 | optimization | ✅ | 0 | — | 1 | — | 12.8s |
| glm | P1 | dangerous | ✅ | 0 | — | 1 | — | 36.8s |
| glm | RK3506G | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | RK3506G | dangerous | ✅ | 12 | 4→0 | 2 | ✅ | 29.2s |
| glm | RK3506G | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 9.7s |
| glm | RK3506G | optimization | ✅ | 0 | — | 1 | — | 10.3s |
| glm | RK3506G | dangerous | ✅ | 0 | — | 1 | — | 6.0s |
| glm | S3的温湿度云监测系统 | safe | ✅ | 0 | — | 1 | — | 4.7s |
| glm | S3的温湿度云监测系统 | dangerous | ✅ | 0 | — | 1 | — | 19.0s |
| glm | S3的温湿度云监测系统 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 31.6s |
| glm | S3的温湿度云监测系统 | optimization | ✅ | 0 | — | 1 | — | 43.9s |
| glm | S3的温湿度云监测系统 | dangerous | ✅ | 0 | — | 1 | — | 18.9s |
| glm | Schematic2 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | Schematic2 | dangerous | ✅ | 11 | 4→0 | 2 | ✅ | 29.2s |
| glm | Schematic2 | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 11.2s |
| glm | Schematic2 | optimization | ✅ | 0 | — | 1 | — | 9.2s |
| glm | Schematic2 | dangerous | ✅ | 0 | — | 1 | — | 37.5s |
| glm | V1.0.2 | safe | ✅ | 0 | — | 1 | — | 3.2s |
| glm | V1.0.2 | dangerous | ✅ | 2 | 0→0 | 2 | ✅ | 18.4s |
| glm | V1.0.2 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 8.0s |
| glm | V1.0.2 | optimization | ✅ | 0 | — | 1 | — | 8.9s |
| glm | V1.0.2 | dangerous | ✅ | 0 | — | 1 | — | 23.2s |
| glm | V1.0.2_2 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | V1.0.2_2 | dangerous | ✅ | 15 | 2→0 | 2 | ✅ | 18.7s |
| glm | V1.0.2_2 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 17.2s |
| glm | V1.0.2_2 | optimization | ✅ | 0 | — | 1 | — | 7.6s |
| glm | V1.0.2_2 | dangerous | ✅ | 0 | — | 1 | — | 27.3s |
| glm | V1.0.2_3 | safe | ✅ | 0 | — | 1 | — | 4.2s |
| glm | V1.0.2_3 | dangerous | ✅ | 5 | 1→0 | 2 | ✅ | 49.9s |
| glm | V1.0.2_3 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 21.5s |
| glm | V1.0.2_3 | optimization | ✅ | 0 | — | 1 | — | 7.6s |
| glm | V1.0.2_3 | dangerous | ✅ | 0 | — | 1 | — | 19.6s |
| glm | XDS110 | safe | ✅ | 0 | — | 1 | — | 2.0s |
| glm | XDS110 | dangerous | ✅ | 0 | — | 1 | — | 45.0s |
| glm | XDS110 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 20.9s |
| glm | XDS110 | optimization | ✅ | 0 | — | 1 | — | 16.1s |
| glm | XDS110 | dangerous | ✅ | 0 | — | 1 | — | 45.3s |
| glm | 地奇星RA6E2 | safe | ✅ | 0 | — | 1 | — | 1.2s |
| glm | 地奇星RA6E2 | dangerous | ✅ | 7 | 1→0 | 2 | ✅ | 16.8s |
| glm | 地奇星RA6E2 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 26.0s |
| glm | 地奇星RA6E2 | optimization | ✅ | 0 | — | 1 | — | 26.1s |
| glm | 地奇星RA6E2 | dangerous | ✅ | 0 | — | 1 | — | 12.8s |
| glm | 已走线 | safe | ✅ | 0 | — | 1 | — | 4.3s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 36.3s |
| glm | 已走线 | optimization | ✅ | 0 | — | 1 | — | 43.0s |
| glm | 已走线 | optimization | ✅ | 0 | — | 1 | — | 5.1s |
| glm | 已走线 | dangerous | ✅ | 0 | — | 1 | — | 12.2s |
| glm | 显示屏触摸转接底座 | safe | ✅ | 0 | — | 1 | — | 1.5s |
| glm | 显示屏触摸转接底座 | dangerous | ✅ | 0 | — | 1 | — | 7.9s |
| glm | 显示屏触摸转接底座 | optimization | ✅ | 0 | — | 1 | — | 15.8s |
| glm | 显示屏触摸转接底座 | optimization | ✅ | 0 | — | 1 | — | 12.1s |
| glm | 显示屏触摸转接底座 | dangerous | ✅ | 0 | — | 1 | — | 9.3s |
| glm | 智能小车V0.1.2 | safe | ✅ | 0 | — | 1 | — | 2.3s |
| glm | 智能小车V0.1.2 | dangerous | ✅ | 0 | — | 1 | — | 6.8s |
| glm | 智能小车V0.1.2 | optimization | ✅ | 0 | — | 1 | — | 44.4s |
| glm | 智能小车V0.1.2 | optimization | ✅ | 0 | — | 1 | — | 7.6s |
| glm | 智能小车V0.1.2 | dangerous | ✅ | 0 | — | 1 | — | 26.4s |
| glm | 梁山派车载式路面平整度测量器 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | 梁山派车载式路面平整度测量器 | dangerous | ✅ | 0 | — | 1 | — | 4.7s |
| glm | 梁山派车载式路面平整度测量器 | optimization | ❌ | 4 | 2→2 | 3 | ❌ | 123.9s |
| glm | 梁山派车载式路面平整度测量器 | optimization | ❌ | 4 | 2→2 | 3 | ❌ | 117.3s |
| glm | 梁山派车载式路面平整度测量器 | dangerous | ✅ | 0 | — | 1 | — | 20.5s |
| glm | 模块化版本 | safe | ✅ | 0 | — | 1 | — | 1.6s |
| glm | 模块化版本 | dangerous | ✅ | 5 | 1→0 | 2 | ✅ | 30.0s |
| glm | 模块化版本 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 20.2s |
| glm | 模块化版本 | optimization | ✅ | 0 | — | 1 | — | 8.7s |
| glm | 模块化版本 | dangerous | ✅ | 0 | — | 1 | — | 11.6s |
| glm | 泰山派4寸86屏转接板 | safe | ✅ | 0 | — | 1 | — | 1.7s |
| glm | 泰山派4寸86屏转接板 | dangerous | ✅ | 0 | — | 1 | — | 47.4s |
| glm | 泰山派4寸86屏转接板 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 10.7s |
| glm | 泰山派4寸86屏转接板 | optimization | ✅ | 0 | — | 1 | — | 17.4s |
| glm | 泰山派4寸86屏转接板 | dangerous | ✅ | 0 | — | 1 | — | 23.9s |
| glm | 泰山派无人机地面站 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 0 | — | 1 | — | 8.6s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 10.7s |
| glm | 泰山派无人机地面站 | optimization | ✅ | 0 | — | 1 | — | 19.6s |
| glm | 泰山派无人机地面站 | dangerous | ✅ | 0 | — | 1 | — | 44.4s |
| glm | 游戏机扩展板diy | safe | ✅ | 0 | — | 1 | — | 3.5s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 0 | — | 1 | — | 51.8s |
| glm | 游戏机扩展板diy | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 14.8s |
| glm | 游戏机扩展板diy | optimization | ✅ | 0 | — | 1 | — | 18.5s |
| glm | 游戏机扩展板diy | dangerous | ✅ | 0 | — | 1 | — | 25.2s |
| glm | 游戏机扩展板V1.1.1 | safe | ✅ | 0 | — | 1 | — | 2.8s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 2 | 0→0 | 1 | ✅ | 16.9s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 17.8s |
| glm | 游戏机扩展板V1.1.1 | optimization | ✅ | 0 | — | 1 | — | 13.4s |
| glm | 游戏机扩展板V1.1.1 | dangerous | ✅ | 0 | — | 1 | — | 17.0s |
| glm | 电创派V2.0 | safe | ✅ | 0 | — | 1 | — | 2.6s |
| glm | 电创派V2.0 | dangerous | ✅ | 15 | 3→0 | 2 | ✅ | 41.0s |
| glm | 电创派V2.0 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 13.6s |
| glm | 电创派V2.0 | optimization | ✅ | 0 | — | 1 | — | 7.4s |
| glm | 电创派V2.0 | dangerous | ✅ | 0 | — | 1 | — | 27.3s |
| glm | 电压电流表 | safe | ✅ | 0 | — | 1 | — | 1.9s |
| glm | 电压电流表 | dangerous | ✅ | 3 | 0→0 | 1 | ✅ | 17.4s |
| glm | 电压电流表 | optimization | ✅ | 4 | 0→0 | 1 | ✅ | 20.5s |
| glm | 电压电流表 | optimization | ✅ | 0 | — | 1 | — | 12.9s |
| glm | 电压电流表 | dangerous | ✅ | 0 | — | 1 | — | 22.5s |
| glm | 立创·庐山派K230 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | 立创·庐山派K230 | dangerous | ✅ | 0 | — | 1 | — | 25.2s |
| glm | 立创·庐山派K230 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 47.5s |
| glm | 立创·庐山派K230 | optimization | ✅ | 0 | — | 1 | — | 6.9s |
| glm | 立创·庐山派K230 | dangerous | ✅ | 0 | — | 1 | — | 18.3s |
| glm | 立创·泰山派3M(RK3576)开发板V1.4 | safe | ✅ | 0 | — | 1 | — | 1.8s |
| glm | 立创·泰山派3M(RK3576)开发板V1.4 | dangerous | ✅ | 0 | — | 1 | — | 38.6s |
| glm | 立创·泰山派3M(RK3576)开发板V1.4 | optimization | ✅ | 2 | 0→0 | 1 | ✅ | 43.3s |
| glm | 立创·泰山派3M(RK3576)开发板V1.4 | optimization | ✅ | 0 | — | 1 | — | 5.8s |
| glm | 立创·泰山派3M(RK3576)开发板V1.4 | dangerous | ✅ | 0 | — | 1 | — | 8.8s |
| glm | 立创·逻辑派FPGA | safe | ✅ | 0 | — | 1 | — | 1.5s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 21 | 5→0 | 2 | ✅ | 22.2s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 6 | 0→0 | 1 | ✅ | 20.5s |
| glm | 立创·逻辑派FPGA | optimization | ✅ | 0 | — | 1 | — | 9.8s |
| glm | 立创·逻辑派FPGA | dangerous | ✅ | 0 | — | 1 | — | 42.6s |
| glm | 载板 | safe | ✅ | 0 | — | 1 | — | 2.2s |
| glm | 载板 | dangerous | ✅ | 0 | — | 1 | — | 22.2s |
| glm | 载板 | optimization | ✅ | 8 | 0→0 | 1 | ✅ | 26.8s |
| glm | 载板 | optimization | ✅ | 0 | — | 1 | — | 8.5s |
| glm | 载板 | dangerous | ✅ | 0 | — | 1 | — | 8.3s |
| glm | 辐射检测扩展板原理图V1.0.0 | safe | ✅ | 0 | — | 1 | — | 1.5s |
| glm | 辐射检测扩展板原理图V1.0.0 | dangerous | ✅ | 4 | 0→0 | 2 | ✅ | 41.4s |
| glm | 辐射检测扩展板原理图V1.0.0 | optimization | ✅ | 10 | 0→0 | 1 | ✅ | 20.1s |
| glm | 辐射检测扩展板原理图V1.0.0 | optimization | ✅ | 0 | — | 1 | — | 7.5s |
| glm | 辐射检测扩展板原理图V1.0.0 | dangerous | ✅ | 0 | — | 1 | — | 21.4s |

## 阶段 C: 多智能体审查

| 提供者 | 设计 | 总分 | 等级 | 严重 | 发现 | 耗时 |
|--------|------|------|------|------|------|------|
| glm | 01Phone | 94 | A | 1 | 9 | 56.8s |
| glm | 01Phone_2 | 95 | A | 1 | 3 | 38.3s |
| glm | 6寸屏幕转接板 | 96 | A+ | 1 | 8 | 43.2s |
| glm | design002 | 93 | A | 1 | 5 | 48.8s |
| glm | design003 | 93 | A | 1 | 10 | 49.6s |
| glm | design006 | 96 | A+ | 1 | 8 | 40.4s |
| glm | design007 | 98 | A+ | 1 | 2 | 30.8s |
| glm | design008 | 95 | A+ | 1 | 7 | 35.9s |
| glm | design009 | 96 | A+ | 1 | 6 | 35.9s |
| glm | design010 | 94 | A | 1 | 7 | 39.1s |
| glm | design011 | 94 | A | 1 | 4 | 46.5s |
| glm | design013 | 95 | A+ | 1 | 5 | 34.5s |
| glm | design015 | 97 | A+ | 1 | 6 | 31.4s |
| glm | design017 | 95 | A | 1 | 6 | 38.6s |
| glm | design021 | 94 | A | 1 | 10 | 33.6s |
| glm | design022 | 90 | A | 1 | 14 | 44.9s |
| glm | design028 | 93 | A | 1 | 8 | 40.5s |
| glm | design029 | 97 | A+ | 1 | 7 | 33.1s |
| glm | design030 | 90 | A | 1 | 10 | 45.4s |
| glm | design031 | 94 | A | 1 | 8 | 35.6s |
| glm | design032 | 95 | A | 1 | 8 | 35.7s |
| glm | design035 | 98 | A+ | 1 | 3 | 25.2s |
| glm | design037 | 94 | A | 1 | 10 | 34.6s |
| glm | design038 | 96 | A+ | 1 | 4 | 31.8s |
| glm | design039 | 96 | A+ | 1 | 7 | 38.1s |
| glm | design040 | 94 | A | 1 | 7 | 33.5s |
| glm | design042 | 93 | A | 1 | 11 | 42.2s |
| glm | design043 | 93 | A | 1 | 8 | 43.5s |
| glm | design046 | 95 | A+ | 1 | 4 | 29.4s |
| glm | design051 | 96 | A+ | 1 | 5 | 34.4s |
| glm | design054 | 91 | A | 1 | 14 | 41.1s |
| glm | design057 | 95 | A+ | 1 | 8 | 41.2s |
| glm | design059 | 95 | A | 1 | 8 | 33.0s |
| glm | design062 | 94 | A | 1 | 7 | 27.3s |
| glm | design063 | 94 | A | 1 | 6 | 25.9s |
| glm | design064 | 94 | A | 1 | 6 | 35.3s |
| glm | design066 | 96 | A+ | 1 | 5 | 23.1s |
| glm | design067 | 93 | A | 1 | 9 | 32.3s |
| glm | design068 | 97 | A+ | 1 | 4 | 43.3s |
| glm | design069 | 96 | A+ | 1 | 5 | 28.6s |
| glm | design070 | 97 | A+ | 1 | 4 | 26.1s |
| glm | design073 | 93 | A | 1 | 11 | 54.1s |
| glm | design077 | 94 | A | 1 | 11 | 37.5s |
| glm | design079 | 95 | A+ | 1 | 5 | 25.2s |
| glm | design081 | 95 | A | 1 | 6 | 48.7s |
| glm | design082 | 96 | A+ | 1 | 8 | 32.0s |
| glm | design083 | 91 | A | 1 | 7 | 38.2s |
| glm | design087 | 95 | A | 1 | 9 | 39.5s |
| glm | design089 | 94 | A | 1 | 10 | 31.1s |
| glm | design090 | 93 | A | 1 | 7 | 26.1s |
| glm | design091 | 93 | A | 1 | 8 | 24.2s |
| glm | F28034 | 94 | A | 1 | 8 | 38.9s |
| glm | io扩展 | 96 | A+ | 1 | 8 | 32.7s |
| glm | LCTSPI语音识别扩展板 | 97 | A+ | 1 | 6 | 29.3s |
| glm | P1 | 93 | A | 1 | 12 | 26.5s |
| glm | RK3506G | 94 | A | 1 | 10 | 34.8s |
| glm | S3的温湿度云监测系统 | 90 | A | 1 | 13 | 30.8s |
| glm | Schematic2 | 96 | A+ | 1 | 7 | 32.1s |
| glm | V1.0.2 | 93 | A | 1 | 7 | 43.8s |
| glm | V1.0.2_2 | 96 | A+ | 1 | 6 | 40.3s |
| glm | V1.0.2_3 | 96 | A+ | 1 | 8 | 43.2s |
| glm | XDS110 | 96 | A+ | 1 | 7 | 32.0s |
| glm | 地奇星RA6E2 | 96 | A+ | 1 | 5 | 49.5s |
| glm | 已走线 | 93 | A | 1 | 13 | 37.1s |
| glm | 显示屏触摸转接底座 | 94 | A | 1 | 9 | 33.1s |
| glm | 智能小车V0.1.2 | 89 | A | 1 | 7 | 49.5s |
| glm | 梁山派车载式路面平整度测量器 | 93 | A | 1 | 9 | 23.1s |
| glm | 模块化版本 | 91 | A | 1 | 12 | 33.2s |
| glm | 泰山派4寸86屏转接板 | 96 | A+ | 1 | 5 | 24.3s |
| glm | 泰山派无人机地面站 | 91 | A | 1 | 12 | 37.9s |
| glm | 游戏机扩展板diy | 94 | A | 1 | 8 | 40.9s |
| glm | 游戏机扩展板V1.1.1 | 94 | A | 1 | 8 | 34.6s |
| glm | 电创派V2.0 | 94 | A | 1 | 8 | 44.9s |
| glm | 电压电流表 | 95 | A | 1 | 7 | 34.8s |
| glm | 立创·庐山派K230 | 93 | A | 1 | 11 | 40.1s |
| glm | 立创·泰山派3M(RK3576)开发板V1.4 | 92 | A | 1 | 11 | 44.6s |
| glm | 立创·逻辑派FPGA | 95 | A | 1 | 8 | 32.4s |
| glm | 载板 | 92 | A | 1 | 6 | 37.2s |
| glm | 辐射检测扩展板原理图V1.0.0 | 94 | A | 1 | 13 | 34.9s |

## 关键指标

- **BOM变更收敛率**: 113/120 (94%) (目标 > 70%)
- **全撤销收敛**: 39 个 — LLM 识别建议有害后撤销全部变更（防御闭环的正确收敛路径）
- **平均新违规引入**: 0.8 个/建议
- **平均修正轮次**: 1.5 (目标 ≤ 2.0)
- **幻觉消除率**: 100.0% (目标 > 80%)
- **纯分析建议**: 234 个 (无BOM变更)
- **⚠️ 解析失败/条目全丢弃**: 41 个 (零变更但非分析类, 不计入通过)
- **多智能体均分**: 94/100 (目标 > 75)
- **缺陷检出率**: 268/280 (96%)

### 缺陷注入详情

| 缺陷 | 预期规则 | 检出 | 命中 | 遗漏 |
|------|----------|------|------|------|
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
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
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
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
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
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
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
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ❌ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 否 | 0 | 3 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ❌ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 否 | 0 | 2 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
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
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
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
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ❌ 删除 LED 限流电阻 | LED 限流检查 | 否 | 0 | 1 |
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
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 1 | 1 |
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 2 | 1 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
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
| ✅ 删除晶振负载电容 | 晶振负载电容检查, 晶振频率匹配 | 是 | 2 | 0 |
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
| ❌ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 否 | 0 | 1 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |
| ✅ 移除去耦电容 | 去耦电容检查, 去耦电容距离检查 | 是 | 1 | 2 |
| ✅ 非标准电阻值 | 参数范围检查 | 是 | 1 | 0 |
| ✅ 删除 TVS/ESD 保护二极管 | ESD 保护检查 | 是 | 1 | 0 |
| ✅ 电容耐压不足 | 电容耐压降额检查 | 是 | 1 | 0 |

---
📁 完整 JSON 数据: `experiment_results\run_thing_full_glm53\results.json`
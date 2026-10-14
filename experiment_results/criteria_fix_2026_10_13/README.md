# 判据修正批 2026-10-13 —— 1761 条违规评审确认的 4 个误报族

来源：2026-10-13 对 95 板 1761 条违规的人工评审（4 族不符合实际，其余为已知
advise 口径/已结案规则）。四批全部落地，金样 `_SNAPSHOT` 已同步，全量 pytest 绿。

| 批次 | 规则 | 判据变化 | 95 板违规 | 金样计数 |
|---|---|---|---|---|
| 1 | DC-DC 反馈网络检查 | 结构化通道 + LDO/固定输出/隔离模块排除 | 51 → 1 | 51 → 1 |
| 1(连带) | 功率回路面积 / 开关电源布局 | 共用 `_is_dcdc_part` 口径，LDO 等退出 | 各 33 → 31 | 各 33 → 31 |
| 2 | 差分对等长检查 | 门限判定/展示统一 + 接口分级 + 存储器档 | 70 → 61 | 70 → 61 |
| 3 | 去耦电容检查 | U 前缀模组/连接器描述二次否决 | 146 → 140 | 135 → 130 |
| 4 | 电源线载流检查 | 使能/状态网排除（POWER_EN 等） | 30 → 29 | 30 → 29 |
| — | 合计 | | 1761 → 1691 | 1712 → 1549 |

## 批次 1：DC-DC 反馈（51 ERROR → 1）

- `_is_dcdc_part`（src/rules/base.py）：新增 LDO/负载开关族前置排除
  （TPS7/TPS2/SGM20/SGM21/SGM15）；描述关键词删去「稳压器」「regulator」
  （会命中「线性稳压器」）；新增无外反馈环节料号正则（AP6320x 固定输出、
  BxxxxS 隔离模块、XL1509-数字档）。
- `_check_dcdc_feedback_network`（src/rules/bom_rules.py）：结构化通道取或——
  名字通道（FB/FEEDBACK/VSENSE）对 LCEDA `$1Nxxxx` 匿名网全盲；新增「稳压器
  某网络挂 ≥2 独立 R 位号 + 非使能网 + ≤5 位号小网络」结构证据。规模门替代
  按网名判电源（真电源轨挂 40+ 位号；SY7201 的 LED 驱动 OVP 分压中点网
  `MIPI_DSI_VCC_LED-` 名字带 VCC 字样但只有 4 位号，按名字判会误杀）。
- 剩余 1 条（VFD 板 MT3608）为真阳性：可调稳压器全部网络上无任何 ≥2 电阻
  分压结构。
- 评审口径对账：51 条深查时「全部具备 ≥2 电阻结构」成立，但其中 3 块板的
  4 条另属固定输出/隔离模块（无外反馈是设计使然），一并排除。

## 批次 2：差分等长（70 → 61，5 条自相矛盾报告清零）

- 门限判定/展示统一：表外组由「2.0mm 绝对 OR 10% 相对」双量则（消息只印
  2.0mm）改为单量则 `min(2.0, 10%×组内平均长)`，消息印实际收紧门限——
  印什么就判什么。原 5 条「diff<2.0 却写门限 2.0mm」报告全部修复。
- 接口分级：接口词改 `_net_kw_hit` 词边界（与阻抗规则同口径）+ 新增
  LPDDR/DDR/SDRAM 存储器档（0.5mm，LPDDR5_WCK 对 0.96mm 失配现按存储器档
  WARNING 判）；guess 后缀配对无接口词（MIC_P/MIC_N 类音频对）直接跳过
  （-9 条）；engine 声明组无接口词（SPK_IN、$1N 对）保留判定降 INFO 并注明
  「接口未识别，参考判定」。

## 批次 3：去耦目标 U 前缀二次否决（135 → 130）

- `_is_module_not_ic`（src/rules/base.py）：连接器/排针/端子/卡座/wafer +
  OLED/LCD/显示屏/display + 麦克风/咪头 描述词表（`_kw_hit` 词边界）。U 前缀
  不在 `_non_ic_prefixes` 安全网内、规则回退对 U 前缀也直接判 ic，故否决置于
  分类结果之上；ML 可用与 ml_off 两路口径一致。只接去耦两条规则
  （`_check_decoupling_caps` / `_check_decoupling_proximity`），不动全局分类。
- 金样 78 板实测 16 个假 IC 目标全部命中（0.96寸OLED×2、WAFER×6、XT30×2、
  麦克风×2、TF 卡座、排针、端子、LCD），无真驱动 IC 误伤。已知取舍：裸
  OLED 驱动芯片（desc 含 oled）也会被否决——金样无此形态。
- 连带效应（方向正确）：滑板板距离检查不再被假 IC 锚定，远距电容-真 IC
  组合浮出（2 对 → 4 对，行数不变）。

## 批次 4：载流使能网排除（30 → 29）

- `_check_power_traces`（src/rules/geometry_rules.py）：pw_traces 收集时排除
  使能/状态网（en/enable/ena/pwren/pgood，`_net_kw_hit` 词边界——PGND/
  SENSOR 的 "en" 前有字母不命中）。POWER_EN 走 µA 级栅极电流，不该按 ~1A
  启发式需求套 IPC-2221。
- 唯一移除行 = 评审点名的 Mini FOC 平衡车 POWER_EN（0.254mm 被判 1A 载流
  不足）。信号线宽规则口径未动（POWER_EN 两头都不查 = 正确）。

## 验收

- `after_batch1/2/3/4.json`：逐批 dump（与 `scripts/dump_rule_baseline.py`
  同口径，95 板），与 `rule_baseline_after.json`（性能批复验基线）diff，
  每批变化全部落在预期规则内，无意外漂移。
- 新增 `tests/test_criteria_batch_2026_10_13.py`（23 用例）锁定四族新行为；
  既有 `test_diff_bands_actually_fire` 门限文案断言随批更新（0.5 → 0.50，
  档位命中行为不变）。
- 金样 `_SNAPSHOT` 同步 6 条计数；全量 pytest 绿（见批次提交信息）。

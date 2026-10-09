# 子串/存在性判据主体金样对比（2026-10-09）

## 口径

10-06 抽查报告 §4B「判据用存在性/子串代替网表与几何（FP 主体）」的收口批次。
78 个唯一 `.epro2` 设计（`test_data/_incoming_epro2/78/`）全量
`DesignRuleChecker.check_all` 输出快照：改动前 `before.json` / 改动后
`after.json`，按 `(rule, severity, desc, loc)` 四元组计数比对。
零 LLM、零网络，约 25s/轮。脚手架与 p2_small_fixes 同口径
（**必须 `check_all(..., pcb_data=pcb)`**），一次性脚本 `snapshot.py` 用完即删。

## 结果

- 总违规 **3301 → 3202（−99）**，双侧 rule_errors = 0
- **非目标规则逐字节不变**（diff 排除 15 条在改规则后差异 = 0/0）
- 全量 pytest **1100 passed**（基线 1069 + 新增回归
  `tests/test_substring_criteria.py` 31 例）+ ui_smoke 84/84

| 规则 | before → after | 判据变化 |
|---|---|---|
| 电源极性保护 | 36 → 2 | 入口改网表（`_has_power_entry`：入口网挂连接器/电池引脚；USB 不算入口）+ 保护器件加位号前缀 D/Q/F。残留 2 板（AIBox-Lite/机器狗）全板确无二极管/MOS/保险丝 = 真检出 |
| 3W 串扰间距 | 127 → 105 | 同一差分组两半互不判串扰（工程声明 + 名字猜测配对都豁免）；「diff」类别只认工程声明。残留最严重对从 HSD0±/PCIE_TXN±/USB0_DM± 换成真实相邻信号；层内对数 21→4、17→8、88→49 |
| DC-DC 反馈网络 | 14 → 0 | 「描述含电阻」恒假 → 位号前缀 R 判电阻行 |
| 过孔密度 | 27 → 14 | 网络名词边界（右侧放行数字：SW1/CLK2 命中，BUZZER_SWITCH 不中）+ 电源/地网排除。残留 SW1/SW2=降压开关节点、PWM/CLK 网=真 |
| 多电源引脚去耦 | 11 → 0 | 「描述含电容」恒假 → 位号前缀 C 按位号数量计数 |
| 上下拉电阻 | 13 → 2 | 控制网词段级正则（EN 不再命中 TOKEN，NRST/BOOT0 命中）+ 上拉位号前缀 R |
| 差分对间距 | 6 → 0 | 高速接口门控（`_HIGH_SPEED_IF_KW`：音频/UART/RC 标组不判）+ 平行重叠 ≥5mm 前置（重叠 0.0mm 不再报「耦合过松」） |
| 天线净空区 | 34 → 29 | 描述词词边界：裸 "rf" 不再命中 IRF9540NPBF；模块家族走料号前缀。残留=蓝牙/ESP32 描述的真模块 |
| LED 限流电阻 | 3 → 0 | 「描述含电阻」→ 位号前缀 R |
| 短桩线 | 25 → 24 | 电源/地网排除（USB_GND 不再当高速网） |
| ESD 保护 | 45 → 44 | 连接器/保护器件词边界 + **value 纳入文本** + ESD 家族料号前缀（GESD0501BU/LESD5Z5 此前内嵌 esd 被漏）；金样中途发现 GESD/LESD 漏认并修正（45→47→44） |
| 磁珠隔离 | 4 → 8 | 裸 'op' ⊂ ESOP8/MSOP8 修复（TP4056-42-ESOP8/NS4150B MSOP-8 不再当运放）；**变多** = 器件识别变对（GD32/CH32/ADC/放大器），抽样新增板 ESP-Hi 触发行是真运放 LMV321 |
| EMI 滤波 | 7 → 12 | 入口改 `_has_power_entry(include_usb=False)`：ADS8685**PWR** 封装后缀/LDO「Vin=18V」不再成入口（旧 7 板正是这类运气命中）；**变多** = 网表入口（VBAT/VCC_24V/12VIN 挂连接器）识别出的真电池/适配器供电板，INFO 建议类文案 |
| I2C 上拉 | 2 → 15 | 总线判据网表化：SDA/SCL 网上有没有挂 R 引脚（上拉不在总线上=没有）；网表非空但无 I2C 网时 BOM 描述词不再扩权。**变多** = 旧口径只靠 BOM 描述运气命中 2 板；新口径报出的 15 板总线网上确无 R 引脚（含 LCD_SDA 命名的边沿案例，文案带「可能」） |
| 天线效应 | 33 → 33 | `len(pins)==1`（零引脚网络不算单端）——语料中零引脚网不进 `pcb.nets`，本批零变化；保留修复防解析变体 |

## 增量规则判读说明

四条「变多」的规则（磁珠 +4、EMI +5、I2C +13、ESD -1）逐一取样核对：

- **磁珠**：新增板为真数字+真模拟（运放/ADC）共存且无磁珠——规则设计前提内的建议（WARNING）。
- **EMI**：入口识别从「任意行描述含 PWR/VIN」改为网表证据后，电池/适配器供电板
  （VBAT/VCC_24V/12VIN 挂 CN/BT 引脚）进入触发集；USB 供电（VBUS+USB 座）已显式
  排除（键控连接器、VBUS 加 CMC 非常规做法）。INFO 文案。
- **I2C**：旧 2 板是 BOM 描述运气；新 15 板 = 「检测到 SDA/SCL 总线网但总线上无
  R 引脚」，判据可证伪。DAPLINK 的 LCD_SDA 命名属边沿案例（显示串行线借用名），
  文案「可能缺少上拉」留了余地。
- **反接残留 2 板**：AIBox-Lite（5V_IN）/机器狗（VBAT+VIN）全板无任何 D/Q/F 器件，
  为真检出（此前 36 条里多数板其实有二极管，被「描述不含保护词」漏认成误报）。

## 复跑方式

```bash
cd experiment_results/substring_criteria_2026-10-09
python snapshot.py before.json   # 需在改动前 checkout 后跑
python snapshot.py after.json
```

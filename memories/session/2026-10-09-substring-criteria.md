# 会话小结 2026-10-09：子串/存在性判据主体批次（§4B 收口）

## 做了什么

10-06 抽查报告 §4B「判据用存在性/子串代替网表与几何（FP 主体，精确率 6.5% 的
根源）」台账 7 条开放项全部收口（第 8 条板框原点已在 P2 批次修过）。金样 78 板
**3301 → 3202（−99）**，双侧 rule_errors=0，**14 条无关规则逐字节不变**。
终版 **pytest 1100 passed**（+31 回归）+ ui_smoke 84/84。

## 判据修正（13 处，分布在 3 个文件）

- **base.py 新共享辅助**：`_row_text`（pn+desc+**value** 合并文本，真实 BOM 型号
  常只在 value）、`_any_ref_prefix`、`_is_resistor_row`/`_is_cap_row`（位号前缀
  优先+描述词回退）、`_has_power_entry`（入口网表：入口网挂连接器/电池引脚；
  `include_usb=False` 供 EMI/反接用）、`_net_kw_hit`（网络名短词右侧放行数字
  后缀 SW1/CLK2、拒绝 SWITCH 内嵌——_kw_hit 的双侧词边界在网络名上会漏
  编号词）。
- **串扰**：同一差分组两半互不判（工程声明+猜测配对都豁免）；「diff」类别只认
  工程声明。层最严重对从 HSD0±/PCIE_TXN± 换成真实相邻信号。127 → 105。
- **差分间距**：`_HIGH_SPEED_IF_KW` 门控 + 最长平行段 ≥5mm 前置（新
  `_pair_parallel_overlap`）。6 → 0。
- **BOM 五规则**（I2C 上拉/DC-DC FB/LED 限流/多电源去耦/上下拉）：「描述含
  电阻/电容」→ 位号前缀。I2C 再网表化一步：「总线网上有没有 R 引脚」，且网表
  非空但无 SDA/SCL 网时 BOM 描述词不再扩权。
- **ESD/EMI/反接**：入口网表化（ADS8685**PWR** 后缀、LDO「Vin=18V」不再成入口；
  USB VBUS 显式不算入口）；保护器件 = 位号前缀 D/Q/F + 词边界 + value 文本 +
  **GESD/LESD 家族料号前缀**（词边界会漏 G-ESD/L-ESD 内嵌——金样中途发现）。
- **杂项**：裸 rf（IRF9540）、裸 op（ESOP8）、过孔密度 SW（词边界+电源地排除）、
  短桩线 USB_GND（电源地排除）、net_antenna 零引脚网不算单端（`==1`，
  本语料零变化、防解析变体）。

## 四条「变多」规则的判读（重要，防止下轮误判为退化）

磁珠 4→8、EMI 7→12、I2C 2→15、（反接残留 2）：全是**识别变对后暴露的新触发集**
而非新误报——逐板取样见
[experiment_results/substring_criteria_2026-10-09/README.md](../../experiment_results/substring_criteria_2026-10-09/README.md)。
反接残留 2 板（AIBox-Lite/机器狗）全板确无 D/Q/F 器件 = 真检出。

## 坑位

1. **`"USB_DP".endswith("_P")` 是 False**——后缀猜配对只认「下划线+P/N/+/-」
   结尾；写串扰猜测豁免的测试时用 USB_DP/USB_DN 构造不出配对，要 USB_D_P/_N。
2. `_net_kw_hit` 与 `_kw_hit` 分工：BOM 描述文本用后者（双侧边界），网络名用
   前者（右侧放行数字）——CLK2/PWM3/SW1 是网络名常态。
3. 快照脚本三跑才收敛：GESD/LESD 漏认、NS41/ES82 前缀过宽（音频功放算模拟）
   都是「after 快照 → 抽样新增/漏网 → 再修」抓出来的，金样不是跑一次就完。

## 遗留（记入台账「待处理」）

- `_check_power_rail_decoupling`：pn 含「电容」判据恒不触发（同病不在清单内未动，
  激活需先判读会新增多少输出）。
- 串扰残留层最严重对是 `GND/PCIE20_TXN` 类「线贴平面」——语义属另一口径，未动。
- 10-06 清单剩余：PDN 无条件 append、需求电流 BOM 关键词、元件间距「字典相邻」
  算法、文档两条、实验指标重定义等（见台账）。

# 项目"不符合预期"清单与状态

> 2026-09-15 更新（第二轮：.epro2 接入后）

## 已修复

- [x] 测试门禁红灯 4 failed / 839 passed → 843 passed
  - 新增 tests/conftest.py：autouse fixture 清空 config.llm，测试不再受本机 .env 干扰
  - 附带收益：套件 128s → 13.7s（不再偷偷发网络请求）
  - 修正 test_does_not_import_third_party_openai_sdk：改用 ast 只查真实 import
- [x] 文档数字漂移：README/CLAUDE 更新为真实值 71 规则 / 24 工具 / 843 测试（原写 69/22/367/719）
- [x] 仓库一个月未提交：已提交 64fd8ce（601 文件 / 23.3 MB），工作区干净
- [x] **规则覆盖率低**（原 30/71）→ `.epro2` 接入后 **60/71（有输出口径）**、**71/71（可判定口径）**
  - 原预测「21 条需 PCBData」精确命中：实测 C1→C3 新解锁正好 **21 条**
  - 数据：`experiment_results/epro2_rule_coverage/`（零 LLM 可复现：`python scripts/epro2_rule_coverage.py test_data/_incoming_epro2`）
- [x] **`_check_impedance_matching` 从未生效**：`checker.py` 用了 `math.sqrt` 却没 `import math`
  - 该规则一旦要报违规就抛 NameError，而 `check_all` 只 `logger.warning` 吞掉 → 静默失效
  - 2026-09-15 补 `import math`；现在会正常产出「特征阻抗匹配检查」
  - 教训：`check_all` 的 try/except 会把规则 bug 变成静默无输出，实验里要单独记录规则异常
- [x] **`_check_trace_acute_angles` 是死代码** → 2026-09-18 激活（判据 `t.has_sharp_angle` 无人设置）
  - 新增 `src/pcb/geometry.py`：端点串联（空间哈希 + 并查集）→ 按图论度数切折线 → 内角计算。
    **没有动解析器的 `segments` 模型**（原担心的数据模型改动，改用「规则侧串联」规避）
  - 只取度数为 2 的节点（T/X 节点、焊盘、过孔处无「拐角」语义）；两侧腿 <0.05mm 的退化拐角
    （焊盘入口短桩）跳过；重复 LINE 先按端点对去重（实测 1331 段里 77 段重复，不去重会串出假 0° 折返）
  - 规则现在报两类：锐角（内角 <89°）WARNING「走线锐角检查」、直角（89~91°）INFO「走线直角检查」
  - 真实数据（76 设计 / 110231 拐角）：内角以 135°/130° 为主（45° 布线）；<89° 锐角 862 处 / 63 设计，
    直角 2146 处 / 75 设计；未加最小腿长门限时 <90° 有 1440 处（多出的即退化短桩）
  - 口径 B（有输出）60/71 → **61/71**；新增回归 `tests/test_acute_angle.py`（20 例）

## 2026-09-18 规则抽查确认的判据 bug（按优先级，均经代码+真实数据双向核实）

> 来源：docs/规则抽查_报告_2026-09-18.md（150 条分层抽样 + 3 个独立核查子任务）
> 影响：口径 B「有输出」61/71 里，走线类精确率仅 11%（4/36，95% CI 4.4%~25.3%），
> 5769 条违现有 63% 来自「几乎每块板都响」的 13 条规则。
> **2026-09-29 更新**：下面第 1~10 类全部已修（余下 4 条 P2 未动）。C3 违规总数
> **4944 → 3293（−33.4%）**，口径 A 仍 71/71；新增「口径 B′：判定类有输出」把 14 条提示类
> 规则单列（**43/57，判定类违规 2356 / 提示类 937**）。逐条见
> [session/2026-09-29-summary.md](session/2026-09-29-summary.md)。

- [x] **P0 电源载流按内层降额算了外层线** → 2026-09-18 修复：新增 `_is_inner_layer()`，
  改为「每条网络取最窄走线 + 按它自己的层」判外层/内层（描述里写明层与内/外层）
  - 违规 118 → **68**（30 → 27 板）；回归 `tests/test_rule_fixes.py`
  - 遗留：需求电流仍是 BOM 关键词粗估（有 0.89A vs 0.90A 的 1% 边界），建议加余量带
- [x] **P0 特征阻抗单端 Z0 比差分目标**（2026-09-29 已修：改用 `differential_impedance` +
  差分目标、排除电源/地、只判高速接口差分组、按网络聚合去重；117 → 23 条）：目标表是差分值（USB90/HDMI100…），
  却用 microstrip_impedance；calculator.py:183 已有 differential_impedance 未用；固定 0.2mm/er4.5；
  traces[:50] 截断；子串命中即 ERROR（HDMI_TX_SDA、HDMI_HCEC、USB_VBUS 全中）
- [x] **P0 参数范围检查 E24 表 10× 比例 bug** → 2026-09-18 修复：mantissa 归一化到 [1,10)，
  容差由 10% 收紧到 E24 的 ±5%（10% 会让任何取值都落进某档窗口，判据恒真）
  - 违规 779 → **4**（73 → 4 板），剩余全是真非标值：1.69kΩ / 137kΩ / 169Ω / 16.9kΩ
  - 注意：`tests/paper_experiments.py` 里注入的「非 E24 值」用了 13k/27k（**这两个其实是 E24**），
    该实验脚本若要继续用需要换成真非标值（如 1.4k），且它不以 test_ 开头、不被 pytest 收集
- [x] **P0 器件类型靠裸子串**（2026-09-29 已修：新增 `_kw_hit()` 短词边界匹配；
  DC-DC/MOSFET/光耦/电阻功率/电池分压 5 条改为位号前缀 + 明确型号；光耦 31 → 0、
  MOSFET 73 → 5、模数分离 1 → 0、电阻功率 1 → 0）：XL-1608(LED)→开关稳压器、NanoSIM 含 si→功率 MOSFET、
  inmp441 麦 克风含 mp→DC-DC、CL10A226MP8NUNE 含 MP→DC-DC、LED 规格文本「功率:60mW」→功率电阻
- [x] **P1 短路桩判据**（2026-09-29 已修：要求 ≥4 层 且 同网络 ≥2 个过孔；46 → 23 条；
  仍列提示类，因为无拓扑量不出 stub 长度）：只看「高速网络存在过孔」，无 stub 长度/分支测量；二层板也报
- [x] **P1 信号线宽**（2026-09-29 已修：绝对下限按层数——≥4 层取 0.09mm；
  相对判据只对「同一网络内混用多种线宽」生效，整网统一选细视为设计意图；268 → 117 条）：下限固定 0.1mm 不分层数；相对判据（本板众数×0.6）
  把整网统一选细的设计意图当误设（抽样 5/5 误报）
- [x] **P1 串扰判据无速率门限**（2026-09-29 已修：加网络类别门控——电源/地线对与
  按键/蜂鸣器/32kHz/GPIO 等低速网络不套 3W；类别段级预计算，实验耗时 347s → 58s；192 → 123 条）：电源/地线对、按键/蜂鸣器/32kHz/GPIO 全按 3W 报
- [x] **P1 差分对门限不分接口**（2026-09-29 已修：`_diff_groups_src()` 区分「工程 NET 规则声明的
  差分组」与「名字后缀猜的配对」——猜的配对不判间距、等长降级 INFO；等长门限改为
  ≥2mm 或 ≥10% 组内平均长；间距门限 3W → 4W；135 → 91、15 → 6 条）：0.5mm/3W 对 USB2、音频、直流输入 ± 过严；
  名字后缀猜出的配对（D1_P/D1-、IN_D+/IN_D-）不是差分对
- [x] **P1 电容耐压降额**（2026-09-29 已修：新增 `_extract_voltage_rating()`——电压必须是独立
  token 且 ≥2.5V；料号 `…R0VH…` 不再抓出 0V；8 → 0 条）：正则在 value+料号搜 (\d+)V，把 …R0VH… 抓成 0V 后照报「裕量不足」
- [x] **P1 去耦电容距离配对逻辑**（2026-09-29 已修：IC 判定改用统一元件分类、判定改为
  「到最近 IC 的距离」；6 → 32 条——判据换口径后暴露的是真实距离，规则已归提示类）：把「除电阻/电感外所有元件」当 IC（咪头/蜂鸣器/电池座），
  报出的「N 个去耦电容」实为配对数
- [x] **P2 拐角**（2026-09-29 已修：直角只对高速/时钟/差分网络报；锐角加「焊盘入口几何」
  二次过滤——两腿 <0.5mm 且距焊盘/过孔 <1.0mm 跳过；1769 → 593 条）：直角对所有网络一律 INFO（规则自述低速可接受）；锐角只按腿长 0.05mm 过滤，
  抽样 3/3 命中焊盘入口几何
- [x] **P2 提示类规则混入「有输出」**（2026-09-29 已修：`checker.ADVISE_RULES` 列 14 条提示类，
  覆盖率脚本新增口径 B′ 只报判定类 43/57；提示类违规 937 条单列）：13 条规则命中 ≥60/76 板（6 条 76/76），占 3648/5769 违规；
  建议给规则加 kind: detect|advise，覆盖率只报 detect
- [ ] **P2 铜皮连接检查**（1496-1509）：只有缺铜皮数据时才报，有铜皮恒空 → 属数据缺失不是缺陷
- [ ] **P2 元件间距检查**：只比较位置字典相邻 4 个元件（非空间最近邻），结论不可复现
- [x] **P2 未连接引脚检查**（2026-10-02 修）：改为按「位号.」前缀数**真实引脚**（旧写法 values() 是引脚列表、getattr(list,"pins") 恒为 []，connected 恒 0 = 有 IC 就报）；
  并把 ctx.netlist 从「永远为空的 list」改成 dict，check_all 在 netlist 为空时从 pcb_data.nets 反推 → 该规则**首次在软件里生效**（也修掉了「实验有输出、产品不触发」的口径分裂）
- [ ] **P2 解析器 orphan 丢针**（epro2_parser.py:413-417）：轮廓仪 20 条 JP1/JP2 焊盘记录被丢弃，
  真实 2 脚网络被看成浮空（天线效应规则随之误报）

## 待处理

- [ ] 实验指标可信度：幻觉消除率 100%、多智能体均分 94（min 88.7）无区分度；需重新定义 + 评分校准
- [ ] frontend/ 去留：原封不动的 Vite React+TS 模板（node_modules 未提交），实际 UI 是 web/
- [ ] 其他：simulator.py 是占位；convergence.py 基类 evaluate 抛 NotImplementedError；.zcode/config.json 含明文 key（已 gitignore）

## 2026-10-06 第二轮抽查确认的判据问题（30 条，未修）

> 报告：[docs/规则抽查_报告_2026-10-06.md](../docs/规则抽查_报告_2026-10-06.md)；
> 样本与判读证据：`experiment_results/rule_spotcheck_2026-10-06/`。
> **重要结论：本轮修复把违规量从 5769 压到 3241（−44%），但抽样精确率 7.7% → 6.5%（CI 重叠）没有提升。**

**代码 bug（3 条，2026-10-06 已由 ZCode 修复并验收；报告 [docs/ZCode修改报告_2026-10-06.md](../docs/ZCode修改报告_2026-10-06.md)）**
- [x] `_check_trace_acute_angles` 过孔锚点恒为空（`PCBVia` 只有 `position`）→ 改取 `position`；实测锐角 **593 → 572**
- [x] `_check_opamp_feedback_network` 数「与运放同前缀的电阻」恒为 0 → 改按网表（电阻集合 = BOM ∪ 网表引脚），无网表不判、级别降 INFO；实测 **4 → 0**
- [x] `_check_reference_continuity` 只取每行第一个位号 → 拆开全部位号；实测 **263 → 179**
- [x] `microstrip_impedance` 窄线分支偏低约 2×（40.9Ω）→ IPC-2141（72.7Ω）；
      副作用：`_check_impedance_matching` **23 → 295**（方向翻转，原报「偏低」实为「偏高」）
- [ ] **（新）阻抗规则 295 条需重新抽查判读**：公式对了不代表目标/±25% 口径对，可能大部分是真检出、也可能引入新误报
- [x] ~~`_is_pad_entry` 与注释不符~~ → **复查撤销**：常量注释即「两腿均短」，代码与之一致（judge 误判）

**判据用「存在性/子串」代替网表与几何（FP 主体）**
- [ ] `_check_crosstalk_spacing` 把工程声明的差分对**自身两半**当串扰（5/5 样本）；且仍有名字猜配对
- [ ] `_check_diff_pair_spacing` 缺高速接口门控、缺平行重叠前置条件（重叠 0.0mm 也报「耦合过松」）
- [ ] `_check_pullup_pulldown`/`_check_dcdc_feedback_network`/`_check_led_current_limit`/`_check_decoupling_cap_per_pin`/`_check_i2c_pullups` 用「描述含『电阻/电容』」代替网表 → BOM 描述为空即恒报
- [ ] `_check_antenna_keepout` 裸 `"rf"`；`_check_power_loop_area`/`_check_switching_regulator_layout` 裸 `MP/XL/SY/MT`；`_check_ferrite_bead_isolation` 裸 `'op'`（ESOP8/MSOP8）
- [ ] `_check_net_antenna` 的 `len(pins)<=1` 把零引脚网络算作单端网络（该板 orphan_pad_nets=77）
- [ ] `_check_via_density` 裸 `SW` 命中 `…BUZZER_SWITCH`；`_check_stub_length` 把 USB_GND 地网当高速网
- [ ] `_check_esd_protection`/`_check_emi_filter`/`_check_reverse_polarity_protection` 靠描述子串认接口与保护器件
- [ ] `_check_component_edge_clearance`/`_check_connector_edge_placement` 拿绝对坐标比门限，**不减板框原点**

**阈值/公式/硬编码**
- [ ] `calculator.microstrip_impedance` 窄线分支（w/h<1）偏低约 2×（40.9Ω vs IPC-2141 72.7Ω）→ 阻抗结论方向反；另硬编码 h=0.2mm 且无层数/长度门控
- [ ] `_check_pdn_target_impedance` 无条件 append + 板面积/层间距/平面电阻全硬编码
- [ ] `_check_power_traces` 需求电流靠 BOM 关键词（"电机控制" 给 MCU 加 1.5A）
- [ ] `_check_signal_traces` 线宽「混用」无容差（0.102 vs 0.1041mm）；0.09mm 下限注释换算错（=3.54mil）
- [ ] `_check_diff_pair_length` 描述 0.5mm vs 实现 ≥2mm/≥10%；长度取全网线段和
- [ ] `_check_power_filtering` 白名单漏 330µF；`_check_bom_value_range` 只认 E24（E96 值被判非标）
- [ ] `_check_component_spacing` 只比字典相邻 4 项且不分层；`_check_package_consistency` 封装名无别名归一
- [ ] `_check_copper_pour_connectivity` 只认 `POUR` 元素，`.epru` 的 `POLY`+`FILL` 覆铜读不到 → 恒报缺数据
- [ ] `_check_trace_edge_clearance` 用包围盒而非板框多边形（误差 ±0.06mm）

## 文档仍偏旧

- PROJECT_BLUEPRINT.md 仍描述 PyQt5 + src/gui/，实际是 Eel web/
- README.md 架构章节仍写"三栏布局"，与 CLAUDE.md 的两级导航不一致

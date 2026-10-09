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
  （2026-10-09 描述口径已对齐实现并注明抽样性；算法本身未动）
- [x] **P2 未连接引脚检查**（2026-10-02 修）：改为按「位号.」前缀数**真实引脚**（旧写法 values() 是引脚列表、getattr(list,"pins") 恒为 []，connected 恒 0 = 有 IC 就报）；
  并把 ctx.netlist 从「永远为空的 list」改成 dict，check_all 在 netlist 为空时从 pcb_data.nets 反推 → 该规则**首次在软件里生效**（也修掉了「实验有输出、产品不触发」的口径分裂）
- [ ] **P2 解析器 orphan 丢针**（epro2_parser.py:413-417）：轮廓仪 20 条 JP1/JP2 焊盘记录被丢弃，
  真实 2 脚网络被看成浮空（天线效应规则随之误报）

## 待处理

- [ ] `_check_power_rail_decoupling` 判据是「part_number 含『电容/capacitor』」（2026-10-09 批次发现，
  同属 §4B 病但不在台账清单内未动）：pn 字段永不含有这两个词 → `cap_vals` 恒空 → 规则恒不触发（静默 FN）。
  若要激活，判据应对齐 `_is_cap_row`（位号前缀 C），并先判读会新增多少「缺中频滤波」类输出
- [ ] 串扰残留（2026-10-09 批次观察，未动）：差分豁免后部分层的最严重对是 `GND/PCIE20_TXN`
  这类「走线贴地/贴铜」——3W 串扰语义是线对线，线对平面耦合属另一口径，量出来的
  数值成立但规则名不符；判读时注意
- [ ] 实验指标可信度：幻觉消除率 100%、多智能体均分 94（min 88.7）无区分度；需重新定义 + 评分校准
- [ ] frontend/ 去留：原封不动的 Vite React+TS 模板（node_modules 未提交），实际 UI 是 web/
- [ ] 其他：simulator.py 是占位；convergence.py 基类 evaluate 抛 NotImplementedError；.zcode/config.json 含明文 key（已 gitignore）

## 已处理（2026-10-09）：P1-6 阶段C（app.js 模块化）

- [x] `web/js/app.js`（3320 行）拆为 `web/js/` 下 13 个经典 script 模块
  （state / persistence / assistants / conversations / tools / chat / imports /
  settings / utils / stream / review / heatmap / misc），index.html 按
  「原单文件的区块顺序」加载。**刻意不用 ES modules**：index.html 有 66 处
  内联 onclick、动态生成 HTML 里的处理器也走全局作用域，ES modules 需手工
  导出几十个 window 绑定而本环境当时认为无法 GUI 验收；改为保序字节级切割。
- [x] **等价硬证据**：13 个模块去掉 7 行头注释后按序拼接，与
  `git show HEAD:web/js/app.js` 逐字节一致（136393 B）；node --check 全过；
  index.html 内联处理器引用的 37 个全局名全部仍存在。
- [x] **验收未等手工**：`tests/ui_smoke.py`（Playwright 真机 + stub LLM，
  零 API 花费）**85/85 通过** —— 覆盖发消息/切会话/工作区/热力图/设置/
  两段式启动，0 控制台错误、0 未捕获异常、0 失败请求。（此前「需手工 GUI
  冒烟」的判断过时了，该脚本 2026-10 前后已具备验收能力。）
- [x] 接缝 6 处跟进：index.html 脚本标签；test_web_render_safety /
  test_tool_catalog / test_no_emoji_in_ui / test_provider_catalog /
  ui_smoke.scan_warnings 五处静态断言改为「读模块拼接源」（拼接 ≡ 原 app.js，
  正则行为不变）；constants.py 注释 / scan_emoji / strip_ui_emoji 扫描清单；
  README 架构图 + CLAUDE.md 两处口径。
- **坑位记录**：(1) **顶层可执行语句不许被切缝劈开** —— 首刀把
  `eel.expose(onPCBChanged)`（原 2787 行）留在 utils.js 末尾而函数在
  stream.js，加载即 ReferenceError；node --check 只查语法、字节拼接只证内容，
  只有 ui_smoke 抓得住。(2) 缝上修补用 `Path.write_text` 会做 LF→CRLF 翻译，
  Python 侧动 JS 文件一律 binary read/write。(3) 拆分等价脚本惯例用完即删，
  思路保留在本节与 commit message。

## 已处理（2026-10-09 下午）：阻抗规则 297 条全量判读 + 判据修正

- [x] 台账开放项「阻抗规则 295 条需重新抽查判读」结案（10-06 公式修复的
  方向翻转遗留）。**全量判读**（非抽样）：单端 45 条全误报、差分 P/N 双计
  全量、表外 3 对硬判误报、表内 122 对真检出（真实叠层复算仍越界）。
  判据修正四件：单端缩 RF/天线词边界、按对聚合、目标表外不判、
  表补 MIPI/PCIE/SATA。**297 → 153**（152 差分对 + 1 ANT），其余 60 规则
  全量 diff 零变化，rule_errors=0。回归 tests/test_impedance_matching.py
  9 例；终版 **1069 passed**。报告与逐条数据
  [experiment_results/impedance_recheck_2026-10-09/README.md](../experiment_results/impedance_recheck_2026-10-09/README.md)。
- [x] `_check_impedance_matching` 不再引用 `_HIGH_SPEED_IF_KW`（判「是不是
  高速接口」改为判「目标表有没有命中」）；该常量仍被串扰/差分间距等规则使用。

## 已处理（2026-10-09）：P2 小项批次（外审 P2 余下 8 项，P2-9 双口径此前已清）

- [x] **板边间距/连接器边沿两规则减板框原点**：绝对坐标比门限 → 板框包围盒
  真实边距（`board_outline` source=outline 守卫，铜包围盒退回时跳过——
  与走线板边规则同一口径）。金样 78 板：板边 **62 → 24**、连接器 **57 → 31**，
  其余 56 规则逐字节不变（总 3519 → 3455，rule_errors 双侧 0）；
  证据 `experiment_results/p2_small_fixes_2026-10-09/`
- [x] **元件间距检查描述对齐实现**：描述/文档串写明「按导入顺序抽样、非空间
  最近邻」。**算法未动**——「只比字典相邻 4 项、结论不可复现」仍列
  2026-10-06 抽查待修项
- [x] **死代码 return**：geometry_rules 地平面连续性规则 unconditional
  return 后的 `return []`
- [x] **_xy helper**：layout_rules 7 处内联「dict 优先兼容 list/tuple」坐标
  解析收编 `base._xy`（金样证实零行为变化）；新增「src/ 不允许 return/raise
  后跟死语句」AST tripwire
- [x] **.epro2 后缀缺失**：`WatcherConstants.PCB_EXTENSIONS` 补 `.epro2`；
  file_watcher 删私藏副本改引常量（防漂移）；eda_adapter supported_formats、
  main_window 文件对话框、endpoints docstring 同步。web 端与解析器分发
  此前已支持，缺口全在 Python 侧常量/过滤
- [x] **{11} 硬编码**：query_knowledge_base 帮助文案的文档数改为按
  `rag_data/*.md` 实时计数（恰为 11，纯巧合）
- [x] **chmod 注释失实**：config/persistence 注释如实（0o600 仅 POSIX 全义，
  Windows 只影响只读位）；config 的 chmod 挪出主 try——收紧失败不再吞掉
  已成功的保存
- [x] **eel 裸 import**：main.py try/except ImportError → 中文安装提示后退出
- 回归 `tests/test_p2_small_fixes.py`（11 例）；终版 **1060 passed**
- **坑位**：金样脚手架必须 `check_all(..., pcb_data=pcb)` —— check_all 首行
  无条件 `self._pcb_data = pcb_data`，只设 `checker._pcb_data` 不传参会让
  全部走线/板框类规则静默跳过（第一版快照 1312 条 vs 正确 3519 的根因）

## 已处理（2026-10-08）：修复计划第二批 P1 全量落地

> 依据外审《修复计划与验收标准》第二批执行；P0 五项此前已修（96eaada /
> f3a27e4 / 579ee44 / c954204 / 6c76bf0）。本轮 9 个 commit，终版
> 1049 passed（基线 1038 + 新增回归 11）。

- [x] **P1-9 电源走线判空顺序**（b59aa81）：checker 列表推导把 `if t.net_name`
  放最后，None 走线先在 `.upper()` 上炸、被 check_all 吞掉 → 整条载流规则
  静默失效。判空提前；回归 test_power_traces_skips_null_net_name 等两例。
- [x] **P1-13 `'ToolRegistry' in dir()` 恒假**（a8992c9）：dir() 无参是当前
  局部作用域 → 回退建议一直显示裸 tool_name。import 提升后无条件走
  `get_label`；回归断言「合并BOM」出现、merge_bam 不出现。
- [x] **P1-10 main.py 惰性初始化**（64b99d3）：模块级 `AppController()`/
  `SessionStore()` 使 import 期就建客户端/落 sessions.db。改
  get_controller()/get_store() 双检锁惰性单例；回归 test_main_lazy.py
  （EDA_AI_HOME→临时目录，子进程 import 后 DB 不存在）。
- [x] **P1-12 markdown 链接协议过滤**（433996d）：剥裸 HTML 挡不住
  `[x](javascript:…)`（无尖括号，marked v15 实测原样输出）。parse 后按协议
  中和 href；回归 test_web_render_safety.py 用 node 实跑 renderMarkdown。
- [x] **P1-7 settings_facade**（7924dd9）：get_settings / save_all_settings /
  test_llm_connection / _bom_item_to_dict 收编为单一实现（此前三次双实现
  漂移：f3a27e4、446a0db、错误文案中英不一）。
- [x] **P1-8 entity_extract 懒触发**（5948588）：两阶段固定 2 次 LLM 调用
  → 先直接 command_parse，JSON 坏/操作不认识才补实体重试；高置信路径 1 次。
- [x] **P1-11 LLMClient 加固**（5a37fd8）：33f8daa 会话级租借后仍残留
  —— _history 并发读写无互斥、_LLM_USAGE 的 += 丢计数、_record_turn 只增
  不裁。加 _history_lock + _USAGE_LOCK + 按上限封顶；8 线程×50 压力回归。
- [x] **P1-6 阶段A**（631ebb7）：run_electrical_health_check 迁到
  src/core/electrical_check.py；DRC prompt 构建迁入
  PromptTemplates.drc_rule_gen_prompt（样例代码含 f-string 花括号，
  不能走 .format() 通道，做纯拼接构建器）。
- [x] **P1-6 阶段B checker 拆包**（ca5b9ec）：base.py（30 个模块级名）+
  bom_rules(43)/geometry_rules(22)/layout_rules(10) 三 mixin +
  checker.py facade（246 行）。**金样对比：拆包前后 78 个 .epro2 全量
  check_all 输出逐字节一致**（71 规则/3519 违规/rule_errors=0）；
  覆盖率脚本 getsource 接缝跟进（拼 MRO mixin）。一次性对比脚本按计划删除。
- [x] **P1-6 阶段C（app.js 模块化）**（2026-10-09 落地，详见下方「已处理（2026-10-09）」）

## 已处理（2026-10-07）

- [x] ~~spec 打包版一键演示未实测~~（昨日遗留）：dist exe 构建成功；frozen 模式写盘路径
  三处缺陷已修（导出/日志/RAG 索引落 _MEIPASS 退出即丢 → app_home()），frozen 模拟实测
  演示加载 14 BOM + 23 坐标；构建入口统一到 spec。exe 双击实测留给用户（本会话环境拒绝
  拉起 GUI 进程）。
- [x] ~~controller.agent 共享单客户端，并发 agent_loop 覆盖 tool_executor、混写 history~~
  （昨日遗留）：_llm_session() 会话级租借（克隆+快照+回流+generation 作废），agent_loop /
  chat_message_stream / 多智能体审查三处接入；审查轮次不再污染对话历史。

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
- [x] **（新）阻抗规则 295 条需重新抽查判读**（2026-10-09 全量判读完毕，语料
  实测 297 条）：
  单端 45 条 **100% 误报**（全是 SPI/SIM/SDIO/晶振时钟名，「时钟按 50Ω」
  不是设计要求，语料真 RF=0）；差分 252 条里 P/N 双计全量存在、RS485/WL-SDIO
  3 对被默认 100Ω 硬判（误报）、表内 122 对换 JLC 真实叠层（PP 0.21/εr4.6）
  复算仍越界（**真检出**）。修复：单端缩到 RF/天线词边界、按对聚合、表外
  不判、表补 MIPI/PCIE/SATA（100Ω）。**297 → 153**（152 对 + 1 条 ANT 真检
  出），其余 60 规则零变化；报告
  [experiment_results/impedance_recheck_2026-10-09/README.md](../experiment_results/impedance_recheck_2026-10-09/README.md)
- [x] ~~`_is_pad_entry` 与注释不符~~ → **复查撤销**：常量注释即「两腿均短」，代码与之一致（judge 误判）

**判据用「存在性/子串」代替网表与几何（FP 主体）**
（2026-10-09 下午全批收口，金样 3301 → 3202、无关规则零变化，证据
[experiment_results/substring_criteria_2026-10-09/](../experiment_results/substring_criteria_2026-10-09/)，
回归 tests/test_substring_criteria.py 31 例）
- [x] `_check_crosstalk_spacing` 把工程声明的差分对**自身两半**当串扰（5/5 样本）；且仍有名字猜配对
  （两半互判豁免扩到猜测配对；「diff」类别只认工程声明；残留层最严重对换成真实相邻信号，127 → 105）
- [x] `_check_diff_pair_spacing` 缺高速接口门控、缺平行重叠前置条件（重叠 0.0mm 也报「耦合过松」）
  （`_HIGH_SPEED_IF_KW` 门控 + 最长平行段 ≥5mm 前置；6 → 0）
- [x] `_check_pullup_pulldown`/`_check_dcdc_feedback_network`/`_check_led_current_limit`/`_check_decoupling_cap_per_pin`/`_check_i2c_pullups` 用「描述含『电阻/电容』」代替网表 → BOM 描述为空即恒报
  （统一改位号前缀 R/C；I2C 进一步网表化为「总线网上有没有 R 引脚」，网表非空且
  无 SDA/SCL 网时描述词不再扩权；13+11+3 → 0、13 → 2、2 → 15——I2C 变多是
  总线判据网表化后报出的真无上拉板，见实验 README 判读节）
- [x] `_check_antenna_keepout` 裸 `"rf"`；`_check_ferrite_bead_isolation` 裸 `'op'`（ESOP8/MSOP8）
  （词边界 + 模块/ESD 家族料号前缀双轨；天线净空 34 → 29、磁珠 4 → 8——变多部分
  为器件识别变对，抽样 ESP-Hi 触发行是真运放 LMV321）
- [x] `_check_net_antenna` 的 `len(pins)<=1` 把零引脚网络算作单端网络（该板 orphan_pad_nets=77）
  （改 `==1`；语料中零引脚网不进 pcb.nets，金样零变化，保留防解析变体）
- [x] `_check_via_density` 裸 `SW` 命中 `…BUZZER_SWITCH`；`_check_stub_length` 把 USB_GND 地网当高速网
  （网络名词边界：右侧放行数字后缀 SW1/CLK2、拒绝 SWITCH 内嵌 + 电源/地网排除；27 → 14、25 → 24）
- [x] `_check_esd_protection`/`_check_emi_filter`/`_check_reverse_polarity_protection` 靠描述子串认接口与保护器件
  （入口改 `_has_power_entry`：入口网挂连接器/电池引脚、USB 不算入口；保护器件
  位号前缀 D/Q/F + value 纳入文本 + GESD/LESD 家族前缀；反接 36 → 2（残留=全板
  无保护器件的真检出）、EMI 7 → 12（真电池/适配器入口板）、ESD 45 → 44）
- [x] `_check_component_edge_clearance`/`_check_connector_edge_placement` 拿绝对坐标比门限，**不减板框原点**（2026-10-09 P2 批次已修）

**阈值/公式/硬编码**
- [ ] `calculator.microstrip_impedance` 窄线分支（w/h<1）偏低约 2×（40.9Ω vs IPC-2141 72.7Ω）→ 阻抗结论方向反；另硬编码 h=0.2mm 且无层数/长度门控
  （2026-10-09 备注：公式部分已修，见上方 10-06 代码 bug 第 4 条；h=0.2 兜底
  经阻抗判读证实「表内告警换真实叠层仍越界」，暂保留并在文案中指引厂商叠层
  复核——拿到真实叠层数据后应替换 h/er）
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

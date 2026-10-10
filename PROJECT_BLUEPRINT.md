# EDA AI 智能助手 — 项目蓝图

> **核心方向：多 LLM 协同路由网关 + RAG 增强的中文 PCB 知识检索**  
> 面向立创EDA的AI智能辅助设计软件 — 内置Agent的BOM管理与PCB设计助手  
> 吉林大学 · 测控技术与仪器专业 · 创新训练项目  
> 版本 v0.8.0 | 2026-10-10 更新（文档批：全篇对齐 Eel Web 现状，替换 2026-05-27 的 PyQt5 旧版）

---

## 零、核心方向与创新点

### 项目定位

```
传统 EDA AI 工具：单模型 + 功能罗列
本项目：         多 LLM 智能网关 + RAG 知识检索 + 闭环验证

          ┌──────────────────────────────────────┐
          │      Web 统一对话界面 (Eel)           │
          │   Chat-first：主页面=对话，功能进子页面 │
          ├──────────────────────────────────────┤
用户输入 →│         多 LLM 协同路由网关            │
          │  ┌──────────┬──────────┬──────────┐  │
          │  │ Kimi     │ GPT-4V   │ DeepSeek │  │
          │  │ 中文RAG  │ PCB视觉   │ 规则生成  │  │
          │  ├──────────┼──────────┼──────────┤  │
          │  │ Qwen-VL  │ Claude   │ ...扩展   │  │
          │  │ 原理图   │ 原生协议  │          │  │
          │  └──────────┴──────────┴──────────┘  │
          ├──────────────────────────────────────┤
          │         闭环验证引擎                  │
          │  LLM 建议 → 71条规则 → 收敛状态机反馈  │
          ├──────────────────────────────────────┤
          │     RAG 知识库（立创EDA中文文档）      │
          └──────────────────────────────────────┘
```

### 三大创新点

| 创新点 | 内容 | 对标差距 |
|--------|------|---------|
| **I. 多 LLM 协同路由** | 按任务类型（中文问答/视觉分析/规则生成/离线）自动分派到最优 LLM，统一界面调度 | 立创EDA 单 Kimi；Cadence 单模型内嵌。学术空白 |
| **II. RAG 增强中文 PCB 知识检索** | 索引立创EDA中文文档 + 封装数据库 + DRC 规则，支持带引用的精确问答 | ChipMind KG 是 IC 级英文；PCB 级中文 RAG 空白 |
| **III. 闭环验证** | LLM 生成设计建议 → 规则引擎实时验证 → 收敛状态机判定（停滞/震荡/发散检测），解决硬件领域幻觉问题 | DRC-Coder 是 IC 级；PCB 级闭环验证无报道 |

### 论文选题

**主选题**：多 LLM 协同路由网关在 EDA 领域的应用

**子方向**：
- RAG 增强的中文 PCB 设计知识检索系统
- 基于大语言模型的 DRC 规则自动生成与闭环验证（EI 主攻：迭代收敛引擎，见 `src/core/convergence.py`）
- 面向 PCB 的 BOM 健康评估与智能替代推荐

### 差异化护城河

```
竞品                             本项目
──────────────────────────────────────────────────
立创EDA AI     单LLM(Kimi)     → 多LLM路由(10家，含Claude原生协议)
Cadence AI     布局布线专精     → BOM+DRC知识推理（错位竞争）
KiCad MCP      操作KiCad       → 立创EDA生态（国内唯一）
ChipMind KG    IC级知识图谱    → PCB级中文知识图谱（空白）
DRC-Coder      芯片级DRC       → PCB规则自动生成（降维应用）
Synopsys DSO   芯片设计优化     → 高校/个人用户（市场空白）
```

---

## 一、项目架构

```
eda_ai_assistant/
├── main.py                          # 应用入口（Eel，60+ 个 @eel.expose 薄封装）
├── eda_ai_assistant.spec            # PyInstaller 打包（唯一构建入口）
├── requirements.txt                 # Python 依赖
├── .env                             # LLM API Key 配置（不入 git）
├── web/                             # Eel 前端（Cherry Studio 设计系统）
│   ├── index.html                   # Chat-first 布局：主页面=对话，功能收进子页面
│   ├── css/                         # 深浅双主题 token（:root / body[data-theme]）
│   └── js/                          # 13 个经典 script 模块（保序加载，P1-6 阶段C 拆分）
│       （state / persistence / assistants / conversations / tools / chat /
│        imports / settings / utils / stream / review / heatmap / misc）
├── src/
│   ├── config.py                    # 配置管理（环境变量 > settings.json > 预设）
│   ├── constants.py                 # 冻结 dataclass：厂商预设/IPC 参数/收敛配置等
│   ├── exceptions.py                # 统一异常体系
│   ├── settings_facade.py           # 设置读写单一实现
│   │
│   ├── agent/                       # AI 引擎
│   │   ├── nlu_engine.py            # 两段式 NLU（embedding + 关键词，10 意图）
│   │   ├── router.py                # 多 LLM 路由（TaskIntent 分类）
│   │   ├── llm_client.py            # OpenAI 兼容客户端（流式/多模态/Function Calling）
│   │   ├── anthropic_client.py      # Claude 原生 Messages API 客户端
│   │   ├── prompt_templates.py      # Prompt 模板库（BOM/Rule/DRC/Command…）
│   │   ├── tools.py                 # 24 工具注册表（ToolRegistry，全系统 SSOT）
│   │   ├── review_agents.py         # 5 Agent 并行审查（电源/信号/热/EMC/DFM）
│   │   ├── design_templates.py      # 12 电路模板 + 设计意图识别
│   │   └── model_catalog.py         # 模型目录
│   │
│   ├── core/                        # 编排与基础设施
│   │   ├── controller.py            # AppController — UI 无关业务编排（the brain）
│   │   ├── verifier.py              # 闭环验证引擎（LLM→DRC→反馈→迭代）
│   │   ├── convergence.py           # 迭代收敛状态机（停滞/震荡/发散检测，论文 4.3）
│   │   ├── design_scorer.py         # 6 维度设计质量评分
│   │   ├── persistence.py           # SQLite 持久化（工作区/助手/会话/消息/app_state）
│   │   ├── system_bridge.py         # 全局热键(Ctrl+Shift+E) + 系统托盘 + 伴生模式
│   │   ├── file_watcher.py          # 立创EDA文件监听（.epro2）
│   │   ├── boot.py                  # 两段式启动（480×340 小窗 → 1300×840 展开）
│   │   └── electrical_check.py      # 电气健康检查
│   │
│   ├── bom/                         # BOM 解析/合并/校验/查重/归一化
│   ├── pcb/                         # .epro2 解析器 + 数据模型 + geometry.py（锐角串联）
│   ├── rules/                       # 71 条设计规则（base + bom/geometry/layout 三 mixin）
│   ├── supply/                      # 立创商城 API + BOM 健康（库存/生命周期/替代料/成本）
│   ├── rag/                         # ChromaDB 本地中文知识库
│   ├── html_bom/                    # 交互式 HTML BOM（Jinja2 模板）
│   ├── interfaces/                  # EDA 适配器（立创EDA JSON）+ simulator 抽象（占位）
│   ├── api/                         # FastAPI 服务（Eel 之外的 REST 通道）
│   └── ml/                          # NLU/元件分类模型训练脚本（语料在 rag_data/）
│
├── rag_data/                        # 中文 PCB 知识库语料（11 篇 markdown）
└── tests/                           # 49 个测试文件，1179 条 pytest 用例
```

> 注：`src/gui/`（PyQt5 原型）已由 `web/` 取代，仓库内无 import 引用，作为历史遗留保留。

### 架构分层

```
┌─────────────────────────────────────┐
│        Web 层 (Eel + 原生 JS)        │  ← 用户交互
│  index.html + 13 个 JS 模块          │     Chat-first 两级导航
├─────────────────────────────────────┤
│         Controller 编排层           │  ← 业务逻辑中枢
│    AppController（UI 无关，零 UI import）
├─────────────────────────────────────┤
│  Agent 层 │ Rules 层 │ BOM/PCB 层   │  ← 核心业务
│  nlu/router │ checker │ parser      │
│  tools(24)  │ 71规则  │ geometry     │
│  review(5)  │ verifier│ merger       │
├─────────────────────────────────────┤
│  Supply 层 │ RAG 层 │ Interfaces 层 │  ← 外部系统适配
│  立创商城API │ ChromaDB │ eda_adapter/simulator
├─────────────────────────────────────┤
│  Config / Constants / Persistence   │  ← 基础设施
│  （SQLite / settings.json / .env）   │
└─────────────────────────────────────┘
```

---

## 二、已实现功能清单（2026-10-10 现状）

### 2.1 AI 引擎
| 功能 | 文件 | 状态 |
|------|------|------|
| 10 家 LLM 厂商适配（DeepSeek/OpenAI/Gemini/Claude/通义/智谱/Kimi/豆包/MiniMax/硅基流动） | `agent/llm_client.py` `agent/anthropic_client.py` | ✅ |
| Claude 原生 Messages API（非 OpenAI 兼容） | `agent/anthropic_client.py` | ✅ |
| Function Calling Agent Loop（24 工具自主调用，≤5 轮） | `agent/llm_client.py` `core/controller.py:agent_loop()` | ✅ |
| 两段式 NLU（embedding + 关键词，低置信才补实体重试） | `agent/nlu_engine.py` | ✅ |
| 多 LLM 路由（TaskIntent 分类，架构支持按意图绑厂商） | `agent/router.py` | ✅ |
| VLM 多模态图片分析（粘贴/上传 PCB 截图） | `agent/llm_client.py:chat_multimodal()` | ✅ |
| 5 Agent 并行审查 + 辩论合成 + 6 维雷达图 | `agent/review_agents.py` `core/design_scorer.py` | ✅ |
| 12 电路模板 + 设计意图识别 + 缺失元件建议 | `agent/design_templates.py` | ✅ |
| 工具注册表 SSOT（派发表/关键词/FC schema 全部派生） | `agent/tools.py` | ✅ |

### 2.2 BOM 智能处理
| 功能 | 文件 | 状态 |
|------|------|------|
| CSV/Excel 解析（编码探测、中英文列名映射） | `bom/parser.py` | ✅ |
| 规则合并 + AI 辅助合并全链路 | `bom/merger.py` `core/controller.py:ai_merge_bom()` | ✅ |
| 封装-型号一致性校验（31 条内置规则 + 别名） | `bom/validator.py` | ✅ |
| 位号查重（含跨文件） | `bom/checker.py` | ✅ |
| 参数归一化（R/C/L 单位统一） | `bom/normalizer.py` | ✅ |
| CSV 导出（UTF-8-BOM，Excel 中文兼容）+ HTML BOM | `core/controller.py` `html_bom/` | ✅ |

### 2.3 PCB 解析与规则引擎
| 功能 | 文件 | 状态 |
|------|------|------|
| 立创EDA `.epro2` 解析（ZIP→JSON Lines，只取最新快照） | `pcb/` | ✅ |
| 71 条设计规则（走线/间距/载流/阻抗/去耦/晶振/ESD…） | `rules/`（base + 3 mixin） | ✅ |
| 78 板真实金样校准（3301 → 1602 条，rule_errors=0） | 五批真实化，见第四章 | ✅ |
| DRC 违规热力图（违规计数网格，非图像解析） | `rules/checker.py:build_heatmap()` | ✅ |
| 闭环验证 + 迭代收敛状态机（停滞/震荡/发散检测） | `core/verifier.py` `core/convergence.py` | ✅ |
| 覆铜连接真孤岛判定（并查集）+ 锐角图论串联 | `rules/` `pcb/geometry.py` | ✅ |

### 2.4 生态与系统集成
| 功能 | 文件 | 状态 |
|------|------|------|
| 立创商城供应链（库存/生命周期/替代料/成本估算） | `supply/` | ✅ |
| ChromaDB 本地中文 RAG 知识库（rag_data/ 11 篇语料） | `rag/` | ✅ |
| SQLite 全量持久化（5 表，工作区隔离会话） | `core/persistence.py` | ✅ |
| 全局热键 + 系统托盘 + 伴生模式（380×540） | `core/system_bridge.py` | ✅ |
| 立创EDA 文件监听（.epro2 落盘自动导入） | `core/file_watcher.py` | ✅ |
| 两段式启动（小窗先出，预热后台跑） | `main.py` `core/boot.py` | ✅ |
| Chat-first Web UI（13 模块、深浅主题、工具箱、多助手实例） | `web/` | ✅ |
| PyInstaller 打包（spec 统一入口，exe 构建成功） | `eda_ai_assistant.spec` | ✅ |
| 1179 条 pytest + 85 项 Playwright UI 冒烟 | `tests/` | ✅ |

---

## 三、未实现/待收敛清单（按优先级）

> 判据类条目均来自 2026-10-10 真实性审计（金样 1602 条逐档分型），详见 `memories/audit-findings.md`。

### 判据档位收敛（真实检出，级别/口径待定）
| # | 项 | 现状 | 讨论点 |
|---|----|------|--------|
| 1 | 阻抗匹配 128 条 ERROR | 未控阻板是设计选择，规则按目标表硬判 | 降级/加「控阻声明」门控 |
| 2 | 去耦电容 43 条 ERROR | 「每 IC 一颗 100nF」惯例，级别偏重 | 改 WARNING 或分档 |
| 3 | ESD 47 条 | 「有连接器就得有 TVS」强假设 | 按接口类型门控 |

### 产品口径问题（模板恒真族——每板必响，非判据错误）
- PDN 目标阻抗 78/78 板、功率回路 33、开关电源布局 33、电感饱和 35、checklist advise 族 — 需定产品口径（保留为建议 or 加门控）

### 其余待办
| # | 项 | 说明 |
|---|----|------|
| 4 | 电源需求电流粗估 | 仍是 BOM 关键词（"电机控制"→MCU +1.5A）；台账 #12 后半：频率→CL 表不看器件规格 |
| 5 | 实验指标可信度 | 幻觉消除率 100%、多智能体均分 94（min 88.7）无区分度，需重新定义 + 评分校准 |
| 6 | simulator.py 占位 | `LTspiceSimulator` 真仿真（生成 SPICE netlist → 命令行 → 解析输出）属远期 |
| 7 | frontend/ 去留 | 原封不动的 Vite React+TS 模板（node_modules 未提交），实际 UI 是 web/ |
| 8 | 封装规则 31 → 50+ | 申报书指标差 19 条；调研建议改「LLM 从数据手册自动生成」路线 |
| 9 | 安装包体积 | 实测 205MB，超申报书 <100MB 指标（TODO：裁剪依赖/UPX） |
| 10 | 论文/软著 | EI 论文（闭环验证方向）、软著申请未提交 |

---

## 四、PCB 解析与规则引擎 — 落地纪实

> 原第四章「PCB 网表解析器实施计划」已全部落地（2026-09 ~ 10），本节改为纪实，供论文与答辩引用。

### 解析器能力（`src/pcb/`）
- `.epro2`（ZIP → `.epcb` JSON Lines）全量解析：走线/过孔/焊盘/网络/板框/铜皮/元件坐标
- **两个解析器真 bug 修复**：R 矩形模式 X/Y 是左上角（万兆板整版 GND 铜落板外、泰山派板框偏移同根）；`.epru` 是追加日志，历史快照曾全并（30/78 板混算），改只解析最后一个 PCB 文档
- orphan 焊盘保留 + `pcb.pads` 绝对坐标重建；POUR 环几何 + 带网 FILL/POLY 入 `copper_pours`
- BOARD_OUTLINE 多段描边 + ARC 10° 离散化 → `outline_rings_mm`（72/78 板真板框）
- 锐角检测的图论串联（`pcb/geometry.py`：空间哈希 + 并查集 + 度数切折线）

### 规则真实化五批（78 板金样，3301 → 1602 条，rule_errors=0）
| 批次 | 提交 | 金样 | 要点 |
|------|------|------|------|
| 噪声清扫 | 6503342 | 3202 | 锐角四族伪影豁免、时钟包地 15mm 门、位号跳号合并、丝印守卫 |
| 解析器数据补全 | 747992a | 1611 | orphan 焊盘/覆铜几何/两真 bug（见上） |
| 标准表批 | 29b9766 | 1640 | 叠层预设、PDN 平面参数、电源树载流、E24∪E96、差分等长分档 |
| 几何批 | 87ad9b3 | 1663 | 板框轮廓环真距离、元件间距旋转矩形、差分链路径树直径 |
| 判据批 + 批5假阳清扫 | 01daadc / 540954e | **1602** | 去耦真容值分档、串扰排除 GND 族、晶振三证据、封装归一、悬空网表化 |

- 覆盖口径：71/71（可判定）/ 60/71（有输出）；证据与逐条判读在 `experiment_results/`
- 方法论：每批「金样全量快照 → 无关规则零漂移验证 → 新增输出逐条判读 → 回归测试入库」

---

## 五、里程碑与状态（2026-10-10 核对）

### M1：轻量 PCB 解析 + RAG 知识库 ✅ 完成
```
1.1  PCB 解析器        ✅ 超额：不止轻量版，.epro2 全量几何
1.2  RAG 知识库        ✅ ChromaDB + rag_data/ 11 篇
1.3  信号/电源线宽规则  ✅ 71 条规则（远超原 2 条目标）
1.4  BOM Prompt 接线   ✅ ToolRegistry SSOT 派生
```

### M2：多 LLM 路由 + 视觉接入 🟢 大部分完成
```
2.1  多 LLM 路由网关    ✅ TaskIntent 分类；按意图绑厂商的配置面未开
2.2  聊天框粘贴图片     ✅ VLM 多模态（chat_multimodal）
2.3  LLM→DRC 自动生成  ✅ drc_rule_gen_prompt + 闭环验证引擎落地
2.4  BOM 健康检查      ✅ 立创商城 API（库存/生命周期/替代料/成本）
```

### M3：闭环验证 + 多智能体 🟢 大部分完成
```
3.1  闭环验证引擎      ✅ verifier + convergence 状态机（停滞/震荡/发散）
3.2  多智能体协作      ✅ 5 Agent 并行审查 + 辩论合成
3.3  热力图/对比/语义路由 ✅ 自研违规网格热力图；跨文件对比与 ECharts 未做
3.4  封装规则自动生成   ⬜ 未做（调研定位：LLM 从数据手册提取）
```

### M4：交付物 🟡 进行中
```
4.1  PyInstaller 打包  ✅ exe 已构建（205MB，<100MB 待裁剪）；24h 稳定性未测
4.2  手册/视频/软著     ⬜ 未开始
4.3  论文              ⬜ 选题已定（EI：闭环验证引擎），未投稿
```

---

## 六、行业调研与优化方向（2026-05-27 调研存档）

> 调研范围：国际/国内商业 EDA AI 工具、开源项目、学术前沿（2024-2026）。
> 本章为战略存档，结论仍指导论文选题与差异化定位。

### 6.1 行业格局速览

| 层级 | 代表 | AI 能力 | 与本项目关系 |
|------|------|--------|------------|
| 国际巨头 | Cadence Allegro X AI | 生成式布局/布线，云算力支撑，10x 效率提升 | 不可竞争 — 需云基础设施 + 专有数据集 |
| 国际巨头 | Synopsys.ai (DSO.ai) | 芯片级 RL 优化，300+ 流片验证，L1-L5 自主框架 | 芯片级，与 PCB 无关 |
| 国际中游 | Altium 365 ValiAssistant | 需求解析（PDF→规格），非生成式布局 | AI 最弱，非技术壁垒 |
| 国际中游 | Siemens PADS Pro | AI 辅助 Schematic + BOM 生成，DFM 验证 | 面向中小企业，值得对标 |
| 国内对标 | 立创EDA AI 插件 (Kimi) | 电路问答、数据手册查询、原理图图像分析 | **直接竞品/互补** — 单 LLM，我们可以做多 LLM |
| 国内对标 | 华大九天 PyAether | 12000+ Python API，AI 加速仿真，假错过滤 | 芯片级，但 API 思路可借鉴 |
| 国内对标 | 合见工软 UDA | DeepSeek R1 + 专有 EDA 引擎闭环 | "LLM + EDA 闭环验证"思路可借鉴 |
| 开源 | KiCad MCP / kicad-tools | AI Agent 操控 KiCad，思维链 PCB 推理 | **方法可借鉴** — 但我们针对立创EDA |
| 学术 | DRC-Coder (NVIDIA) | 多智能体 VLM+LLM 自动生成 DRC 检查代码 | F1=1.000，sub-3nm — 思路可用于 PCB DRC |

**核心结论：AI 布局/布线赛道已被巨头占据（需要云算力+专有数据），但 BOM 智能分析 + DRC 规则推理 + 中文立创EDA 生态的 AI 增强是空白地带。**

### 6.2 学术前沿五大趋势

| 趋势 | 代表工作 | 对本项目的启示 |
|------|---------|--------------|
| **1. 多智能体 LLM 框架** | EDAid (NAACL 2025), CircuitMind (BUAA 2025), LayoutCopilot (IEEE TCAD 2025) | 我们的多 LLM 后端天然适配 — 不同厂商模型各司其职 |
| **2. RAG + 知识图谱** | ChipMind KG (F1=0.95), MuaLLM (90.1% 召回), HSG-RAG | **最高优先级** — 索引立创EDA中文文档+数据手册，建立领域知识库 |
| **3. LLM→DRC 代码生成** | DRC-Coder (F1=1.000), D2D-LLM+ (AICAS 2025) | 从自然语言描述自动生成 DRC 规则 — 可替代手写规则 |
| **4. 多模态 PCB 分析** | PCBSchemaGen (约束引导), 上大 Qwen2.5-VL 蒸馏 | 视觉路线已落地 — VLM 多模态接入完成 |
| **5. 闭环验证** | EDAid "分歧思维", UniVista LLM+EDA 闭环 | **关键差异化** — 已落地收敛状态机（论文 4.3 节数据源） |

### 6.3 项目定位：从"工具"到"智能网关"

```
               ┌──────────────────────────┐
               │   Web 统一界面 (Eel)      │
               ├──────────────────────────┤
用户自然语言 → │  多 LLM 路由网关          │
               │  ├─ Kimi (中文资料 RAG)   │
               │  ├─ GPT-4V (PCB视觉审查)  │
               │  ├─ DeepSeek (代码/规则)  │
               │  ├─ Qwen-VL (原理图分析)  │
               │  └─ Claude (原生协议)     │
               ├──────────────────────────┤
               │  闭环验证引擎              │
               │  LLM建议 → 71规则 → 收敛  │
               └──────────────────────────┘
```

### 6.4 路线图调整记录（对照 5-27 调研的兑现情况）

| 原调整建议 | 兑现情况 |
|--------|------|
| PCB 解析器先做轻量版 | ✅ 直接做了全量（.epro2 几何 + 真板框） |
| 文本解析完成后立即接入 VLM | ✅ chat_multimodal 已落地 |
| 模糊指令提升至 P1（语义路由） | ✅ 两段式 NLU + 多 LLM 路由 |
| RAG 知识库新增为 P1 | ✅ ChromaDB + 11 篇中文语料 |
| 封装规则改自动生成 | ⬜ 未启动（仍是手写 31 条） |
| 供应链感知 BOM 新增为 P2 | ✅ supply/ 立创商城 API |

### 6.5 论文选题建议

| 选题 | 创新点 | 可行性 | 竞争情况 |
|------|--------|--------|---------|
| **多 LLM 协同路由网关在 EDA 领域的应用** | 首次将多 LLM 路由引入 EDA，按任务/成本/能力分派 | 高（已有 10 家基础） | 低竞争（学术空白） |
| **RAG 增强的中文 PCB 设计知识检索系统** | 首个针对立创EDA中文文档的 RAG，对标 ChipMind KG | 高（知识库已建） | 极低竞争 |
| **基于大语言模型的 DRC 规则自动生成与闭环验证** | LLM 生成 DRC 规则→规则引擎验证→收敛迭代 | **高（convergence.py 已落地，可直接出 4.3 节数据）** | 低竞争（DRC-Coder 是 IC 级） |
| **面向 PCB 的 BOM 健康评估与智能替代推荐** | 结合商城 API + LLM 推理，首创 BOM 生命周期感知 | 高（supply/ 已建） | 无竞争 |

**建议选题组合**：以「闭环验证引擎」为 EI 主攻（代码支撑最完整），「多 LLM 协同 + RAG 知识检索」为主线小标题。

---

## 七、技术栈

| 类别 | 技术 | 版本/说明 |
|------|------|------|
| 语言 | Python | 3.13 |
| 前端 | Eel + 原生 JavaScript | 13 个经典 script 模块，Cherry Studio 设计系统 |
| Markdown 渲染 | marked.js（协议过滤加固） | 前端 |
| 数据处理 | pandas, openpyxl | — |
| HTML 模板 | Jinja2 | HTML BOM |
| 向量检索 | ChromaDB | 本地 RAG |
| 持久化 | SQLite（标准库） | 5 表，`~/.eda_ai_assistant/sessions.db` |
| 系统集成 | pynput（全局热键）/ pystray（托盘） | 伴生模式 |
| REST | FastAPI | `src/api/`，Eel 之外的通道 |
| HTTP 请求 | requests | — |
| 环境管理 | python-dotenv | — |
| 测试框架 | pytest 8.x + Playwright | 1179 条 + 85 项 UI 冒烟 |
| 打包 | PyInstaller | `eda_ai_assistant.spec` 唯一入口 |
| AI 模型 | DeepSeek / OpenAI / Gemini / Claude / 通义千问 / 智谱 / Kimi / 豆包 / MiniMax / 硅基流动 | 10 家 |
| 协议 | OpenAI 兼容 API + Anthropic Messages API | — |

---

## 八、测试覆盖（2026-10-10）

```
tests/                            49 个文件，1179 条 pytest 用例 ✅
├── 规则/判据类    test_rules / test_rule_fixes / test_acute_angle /
│                 test_impedance_matching / test_substring_criteria /
│                 test_geometry_batch_2026_10_10 / test_violation_noise_2026_10_09 /
│                 test_real_pcb_decoupling / test_copper_geometry …
├── 解析器类       test_epro2_parser / test_pcb / test_eda_adapter / test_bom
├── Agent 类       test_llm_client / test_anthropic_client / test_agent_loop /
│                 test_nlu_engine / test_router / test_tools / test_tool_catalog
├── 核心编排类     test_controller / test_controller_nlu / test_persistence /
│                 test_boot / test_main_lazy / test_convergence /
│                 test_verifier* / test_closed_loop_revert
├── Web/UI 类      test_web_render_safety / test_heatmap / test_theme_default /
│                 test_no_emoji_in_ui / test_provider_catalog
└── 其他           test_supply / test_api_server / test_violation_mining /
                  test_confidence_calibration / ml 训练类

tests/ui_smoke.py                 85 项 Playwright 真机冒烟（stub LLM 零 API 花费，
                                  不以 test_ 开头、不被 pytest 收集）
```

---

## 九、申报书指标达成情况（2026-10-10 诚实核对）

| 申报书指标 | 实际 | 状态 |
|-----------|------|------|
| 6厂商 LLM 适配 | 10 家（含 Claude 原生协议） | ✅ 超额 |
| 对话记忆 ≥10 轮 | SQLite 会话/消息全量持久化 + 工作区隔离 | ✅ |
| 自然语言指令 20+ 条 | 24 工具（ToolRegistry SSOT）+ 10 意图两段式 NLU | ✅ |
| 设计规则 15+ 条 | 71 条，78 板真实金样校准（3301→1602，rule_errors=0） | ✅ 超额 |
| 元件类型 ≥50 种 | 31 条封装规则（validator） | ⚠️ 差 19 |
| BOM 全流程 | 解析/合并/校验/查重/导出/HTML 全部完成 | ✅ |
| AI 辅助 BOM 合并 | 规则合并 + AI 建议全链路 | ✅ |
| HTML BOM 交互 | Canvas 点阵图 + 全字段搜索 + 高亮 | ✅ |
| ECharts 热力图 | 自研 Canvas 违规计数网格热力图（DRC 真数据驱动，未用 ECharts） | ✅ 自研实现 |
| 模糊指令处理 | 两段式 NLU：embedding + 关键词，低置信 LLM 兜底 | ✅ |
| 4 主题系统 | Web 深浅双主题 token（PyQt5 四主题随旧 GUI 退役） | ✅ 等效达成 |
| PyInstaller 打包 | spec 已配置，dist exe 构建成功（frozen 路径实测） | ✅ |
| 安装包 <100MB | 实测 205MB | ⚠️ 超标（待裁剪） |
| 24h 稳定性 | 未测试 | ⚠️ |
| 论文 1 篇 | EI 方向已定（闭环验证引擎），未投稿 | 📅 计划 |
| 软著 1 项 | 未申请 | 📅 计划 |
| 98 条测试 | **1179 条 pytest + 85 项 UI 冒烟** | ✅ 超额 |

---

## 十、阶段进度（按工作内容实测标注）

```
Phase 1 (2026.5-6)   需求分析 + 架构设计 + Agent 原型      ██████████ 100% ✅
Phase 2 (2026.7-10)  BOM 核心 + 函数调用 + 对话记忆        ██████████ 100% ✅
Phase 3 (2026.11-2)  Web UI + PCB 解析 + 71规则 + 多智能体 █████████░  92% 🟢
Phase 4 (2027.3-5)   打包 + 论文 + 软著                    ███░░░░░░░  30% 🟡
```

**Phase 3 剩余**（时间窗未到，工作已超前）：判据档位收敛（阻抗/去耦/ESD）、模板恒真族产品口径、跨文件对比
**Phase 4 剩余**：安装包裁剪 <100MB、24h 稳定性、使用手册、演示视频、论文、软著

---

## 十一、配置持久化

```
~/.eda_ai_assistant/
├── settings.json         # 用户配置（LLM厂商/Key/模型 + 主题等）
└── sessions.db           # SQLite（工作区/助手/会话/消息/app_state）
```

- 存储目录统一由 `constants.app_home()` 给出，环境变量 **`EDA_AI_HOME`** 可覆盖（测试/受限环境落临时目录）
- 导出文件目录统一用 `controller.default_output_dir()`（HTML BOM / BOM CSV 共用）
- 优先级：`环境变量` > `settings.json` > `厂商预设` > legacy `DEEPSEEK_*` 环境变量

---

## 十二、Git 历史（近期主干）

```
540954e fix(rules): 批5假阳清扫 —— 晶振三证据/封装归一管线/悬空网表化/板边豁免
01daadc feat(rules): 判据批 —— 去耦档位真容值/串扰最严对排除GND族
87ad9b3 feat(rules): 几何批 —— 板框轮廓环真距离/元件间距旋转矩形/差分链路径
29b9766 feat(rules): 标准表批 —— 叠层预设/PDN平面参数/电源树/E24E96/等长分档
747992a fix(parser): 数据补全批 —— orphan 焊盘保留 + 覆铜几何 + 两真bug
6503342 fix(rules): 违规噪声清扫 —— 金样 3202 → 2048
5812c28 fix(rules): 特征阻抗匹配 297 条全量判读 —— 297 → 153
56a9cf8 refactor(web): app.js 拆为 13 个保序经典模块（P1-6 阶段C）
64fd8ce feat: 真实PCB数据集全量实验 + 测试隔离修复 (v0.7.5-dev)
94e70b5 feat: 多智能体协同审查 + 设计意图识别 + 厂商扩展 (v0.7.0)
dd186d8 feat: 对话记忆上下文 + AI辅助BOM合并 + 蓝图v0.4.0
```

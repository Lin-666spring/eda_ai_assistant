# EDA AI 智能助手 — 项目蓝图

> **核心方向：多 LLM 协同路由网关 + RAG 增强的中文 PCB 知识检索**  
> 面向立创EDA的AI智能辅助设计软件 — 内置Agent的BOM管理与PCB设计助手  
> 吉林大学 · 测控技术与仪器专业 · 创新训练项目  
> 版本 v0.4.0-dev | 2026-05-27 更新

---

## 零、核心方向与创新点

### 项目定位

```
传统 EDA AI 工具：单模型 + 功能罗列
本项目：         多 LLM 智能网关 + RAG 知识检索 + 闭环验证

          ┌──────────────────────────────────────┐
          │         PyQt5 统一对话界面            │
          ├──────────────────────────────────────┤
用户输入 →│         多 LLM 协同路由网关            │
          │  ┌──────────┬──────────┬──────────┐  │
          │  │ Kimi     │ GPT-4V   │ DeepSeek │  │
          │  │ 中文RAG  │ PCB视觉   │ 规则生成  │  │
          │  ├──────────┼──────────┼──────────┤  │
          │  │ Qwen-VL  │ 本地模型  │ ...扩展   │  │
          │  │ 原理图   │ 离线快速   │          │  │
          │  └──────────┴──────────┴──────────┘  │
          ├──────────────────────────────────────┤
          │         闭环验证引擎                  │
          │   LLM 建议 → 规则引擎 → 反馈纠正     │
          ├──────────────────────────────────────┤
          │     RAG 知识库（立创EDA中文文档）      │
          └──────────────────────────────────────┘
```

### 三大创新点

| 创新点 | 内容 | 对标差距 |
|--------|------|---------|
| **I. 多 LLM 协同路由** | 按任务类型（中文问答/视觉分析/规则生成/离线）自动分派到最优 LLM，统一界面调度 | 立创EDA 单 Kimi；Cadence 单模型内嵌。学术空白 |
| **II. RAG 增强中文 PCB 知识检索** | 索引立创EDA中文文档 + 封装数据库 + DRC 规则，支持带引用的精确问答 | ChipMind KG 是 IC 级英文；PCB 级中文 RAG 空白 |
| **III. 闭环验证** | LLM 生成设计建议 → 规则引擎实时验证 → 不一致自动反馈纠正，解决硬件领域幻觉问题 | DRC-Coder 是 IC 级；PCB 级闭环验证无报道 |

### 论文选题

**主选题**：多 LLM 协同路由网关在 EDA 领域的应用

**子方向**：
- RAG 增强的中文 PCB 设计知识检索系统
- 基于大语言模型的 DRC 规则自动生成与闭环验证
- 面向 PCB 的 BOM 健康评估与智能替代推荐

### 差异化护城河

```
竞品                             本项目
──────────────────────────────────────────────────
立创EDA AI     单LLM(Kimi)     → 多LLM路由(6→按需扩展)
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
├── main.py                          # 应用入口
├── requirements.txt                 # Python 依赖
├── .env                             # LLM API Key 配置（不入 git）
├── src/
│   ├── config.py                    # 配置管理（.env + settings.json）
│   ├── constants.py                 # 常量（厂商预设、GUI默认值）
│   ├── exceptions.py                # 统一异常体系
│   │
│   ├── core/
│   │   └── controller.py            # AppController — 业务编排层（UI无关）
│   │
│   ├── agent/
│   │   ├── llm_client.py            # LLM 客户端（6厂商、流式、Function Calling、对话历史）
│   │   └── prompt_templates.py      # Prompt 模板（BOM/Rule/Command/AI Merge）
│   │
│   ├── bom/
│   │   ├── parser.py                # BOM 解析器（CSV/Excel、编码探测、列名映射）
│   │   ├── merger.py                # BOM 合并引擎（规则合并 + AI辅助合并）
│   │   ├── validator.py             # 封装校验器（31条规则+别名系统）
│   │   ├── checker.py               # 位号查重器（含跨文件）
│   │   └── normalizer.py            # 参数归一化（R/C/L单位统一）
│   │
│   ├── html_bom/
│   │   ├── generator.py             # HTML BOM 生成器
│   │   └── templates/ibom.html      # Jinja2 模板（Canvas点阵图+封装轮廓）
│   │
│   ├── rules/
│   │   └── checker.py               # 设计规则检查器（去耦电容✅ + 3空桩）
│   │
│   ├── interfaces/
│   │   ├── eda_adapter.py           # EDA适配器接口 + 立创EDA适配器
│   │   └── simulator.py             # 仿真器抽象接口 + DummySimulator占位
│   │
│   └── gui/
│       ├── eda_theme.py             # 4主题系统 + 语义色彩 + QSS编译器
│       ├── main_window.py           # 主窗口（导航栏、卡片布局、主题切换、清空对话）
│       ├── chat_panel.py            # AI对话面板（气泡消息、流式响应、欢迎页、清空信号）
│       ├── bom_table.py             # BOM表格视图（行号列、7数据列）
│       └── settings_panel.py        # LLM设置表单（厂商/Key/模型配置）
│
└── tests/
    ├── test_bom.py                  # BOM模块测试
    ├── test_controller.py           # Controller 测试
    ├── test_eda_adapter.py          # EDA适配器测试
    ├── test_llm_client.py           # LLM客户端测试
    └── test_rules.py                # 规则检查测试
```

### 架构分层

```
┌─────────────────────────────────────┐
│            GUI 层 (PyQt5)           │  ← 用户交互
│  main_window / chat_panel / bom_table │
├─────────────────────────────────────┤
│         Controller 编排层           │  ← 业务逻辑中枢
│         AppController               │
├─────────────────────────────────────┤
│  Agent 层    │  BOM 层  │ Rules 层  │  ← 核心业务
│  llm_client  │  parser  │ checker  │
│  prompts     │  merger  │          │
│              │ validator│          │
├─────────────────────────────────────┤
│          Interfaces 接口层          │  ← 外部系统适配
│     eda_adapter / simulator         │
├─────────────────────────────────────┤
│  Config / Constants / Exceptions    │  ← 基础设施
└─────────────────────────────────────┘
```

---

## 二、已实现功能清单

### 2.1 AI Agent 核心模块
| 功能 | 文件 | 状态 |
|------|------|------|
| 6家LLM厂商适配（DeepSeek/OpenAI/通义千问/智谱/Kimi/硅基流动） | `agent/llm_client.py` | ✅ |
| OpenAI 兼容协议（Function Calling 格式） | `agent/llm_client.py` | ✅ |
| 流式响应（token-by-token 实时显示） | `agent/llm_client.py:chat_stream()` | ✅ |
| 对话记忆上下文（history 管理 + use_history 参数 + 清空对话） | `agent/llm_client.py` | ✅ **new** |
| Prompt 模板体系（BOM/Rule/Command/AI Merge 四类） | `agent/prompt_templates.py` | ✅ |
| 自然语言→JSON操作指令解析 | `core/controller.py:_extract_json()` | ✅ |
| 本地关键词路由 fallback（7条路由） | `core/controller.py:_KEYWORD_ROUTES` | ✅ |
| LLM 热切换（GUI设置面板实时生效） | `gui/settings_panel.py` | ✅ |
| 对话清空（工具菜单 + 加载新BOM自动清空） | `gui/main_window.py`, `gui/chat_panel.py` | ✅ **new** |

### 2.2 BOM 智能处理引擎
| 功能 | 文件 | 状态 |
|------|------|------|
| CSV/Excel BOM 解析（编码自动探测） | `bom/parser.py` | ✅ |
| 同类元件规则合并（型号+封装+参数归一化） | `bom/merger.py:merge()` | ✅ |
| AI辅助BOM合并（AI识别规则漏并，如 "10kΩ" vs "10K"） | `bom/merger.py:merge_with_ai_suggestion()` | ✅ **new** |
| Controller AI合并入口（规则→AI分析→建议→合并→报告） | `core/controller.py:ai_merge_bom()` | ✅ **new** |
| 封装-型号一致性校验（31条规则） | `bom/validator.py` | ✅ |
| 位号查重（含跨文件） | `bom/checker.py` | ✅ |
| 参数归一化（R/C/L单位统一） | `bom/normalizer.py` | ✅ |
| 列名自动映射（中英文列名兼容） | `bom/parser.py` | ✅ |

### 2.3 交互式 HTML BOM 生成器
| 功能 | 文件 | 状态 |
|------|------|------|
| PCB坐标数据解析 | `interfaces/eda_adapter.py` | ✅ |
| Canvas 元件位置点阵图 | `html_bom/templates/ibom.html` | ✅ |
| 封装轮廓绘制 | `html_bom/templates/ibom.html` | ✅ |
| 全字段搜索+匹配高亮 | `html_bom/templates/ibom.html` | ✅ |
| 浏览器一键打开 | `main_window.py:_on_generate_html_bom()` | ✅ |

### 2.4 自然语言交互界面（GUI）
| 功能 | 文件 | 状态 |
|------|------|------|
| 卡片式面板布局（左聊天+右标签页） | `gui/main_window.py` | ✅ |
| 聊天气泡消息（用户/AI/系统/配置提示） | `gui/chat_panel.py` | ✅ |
| 流式响应实时显示 | `gui/chat_panel.py:append_stream_token()` | ✅ |
| BOM表格（行号列+7数据列） | `gui/bom_table.py` | ✅ |
| 4主题切换（深海/冷白/石墨/青森） | `gui/eda_theme.py` | ✅ |
| 主题持久化（settings.json） | `gui/eda_theme.py` | ✅ |
| 语义化色彩系统（info/success/warning/error） | `gui/eda_theme.py:SEMANTIC` | ✅ |
| LLM设置面板（厂商/Key/模型配置） | `gui/settings_panel.py` | ✅ |
| 配置持久化（~/.eda_ai_assistant/settings.json） | `config.py` | ✅ |
| 欢迎页（左对齐、分隔线、功能列表） | `gui/chat_panel.py:_show_welcome()` | ✅ |

### 2.5 设计规则检查
| 功能 | 文件 | 状态 |
|------|------|------|
| 去耦电容检查（每个IC需0.1μF去耦电容） | `rules/checker.py:_check_decoupling_caps()` | ✅ |

### 2.6 基础设施
| 功能 | 文件 | 状态 |
|------|------|------|
| 统一异常体系 | `exceptions.py` | ✅ |
| 配置管理（.env + settings.json 双源） | `config.py` | ✅ |
| 厂商预设常量化 | `constants.py` | ✅ |
| 日志系统 | `main.py:setup_logging()` | ✅ |
| 98条测试用例 | `tests/` | ✅ |

---

## 三、未实现功能清单（按优先级排列）

### P0 — 申报书承诺、答辩必问（1/3 完成）

| # | 功能 | 技术路径 | 涉及文件 | 难度 | 状态 |
|---|------|---------|---------|------|------|
| 1 | **对话记忆上下文** | ~~LLMClient 维护 _history → use_history 参数 → 清空对话~~ | `agent/llm_client.py` `core/controller.py` `gui/chat_panel.py` `gui/main_window.py` | ⭐⭐ | ✅ 已完成 |
| 2 | **AI辅助BOM合并** | ~~规则合并→AI分析差异→应用建议→报告~~ | `bom/merger.py` `agent/prompt_templates.py` `core/controller.py` | ⭐⭐ | ✅ 已完成 |
| 3 | **3个空规则检查** | 信号线宽 / 电源线宽 / 模数分离 — **全部依赖 #7 PCB网表解析器** | `rules/checker.py` `interfaces/eda_adapter.py` | ⭐⭐⭐ | ❌ 待做 |

### P1 — PCB 解析 + BOM 完善

| # | 功能 | 技术路径 | 涉及文件 | 难度 |
|---|------|---------|---------|------|
| 4 | **BOM导出bug修复** | `merge_bom()` 返回格式化文本但部分场景需 DataFrame → 新增 `_merged_to_dataframe()` | `core/controller.py` `gui/main_window.py` | ⭐ |
| 5 | **BOM专用Prompt接线** | Controller 中根据意图路由到 `BOM_MERGE`/`BOM_VALIDATE`/`BOM_AI_MERGE` 专用 Prompt | `core/controller.py` `agent/prompt_templates.py` | ⭐⭐ |
| 6 | **封装规则扩充（31→50+）** | 追加 TO-252/TO-263/QFN/BGA/MSOP/SOT-23-5 等规则，达到申报书 ≥50 种 | `bom/validator.py` | ⭐ |
| 7 | **PCB 网表解析器** | **关键前置依赖** — 详见下方 PCB 三路线规划 | 新增 `src/pcb/` | ⭐⭐⭐⭐ |

### P2 — 增强功能

| # | 功能 | 技术路径 | 涉及文件 | 难度 |
|---|------|---------|---------|------|
| 8 | **ECharts 热力图** | 替换 Canvas → 在 ibom.html 引入 ECharts CDN → 热力图展示元件密度 | `html_bom/templates/ibom.html` | ⭐⭐ |
| 9 | **跨文件BOM对比** | Controller 暴露 `compare_bom()` → GUI 添加对比按钮 → 双文件差异表 | `core/controller.py` `gui/main_window.py` | ⭐ |
| 10 | **模糊指令处理** | 关键词匹配 → LLM 语义理解优先，利用已有 `COMMAND_PARSE` 做意图路由 | `core/controller.py` | ⭐⭐ |
| 11 | **KiCad 适配器** | 实现 `KiCadAdapter` → 解析 `.kicad_pcb` S-expression → 坐标/封装/网络 | `interfaces/eda_adapter.py` | ⭐⭐ |

### P3 — 远期/交付

| # | 功能 | 技术路径 | 涉及文件 | 难度 |
|---|------|---------|---------|------|
| 12 | **PyInstaller 打包** | `.spec` 文件 → 包含 Jinja2 模板 → 测试 exe < 100MB | 新增 `eda_ai_assistant.spec` | ⭐ |
| 13 | **真仿真引擎** | `LTspiceSimulator(Simulator)` → 生成 SPICE netlist → 调命令行 → 解析输出 | `interfaces/simulator.py` | ⭐⭐⭐⭐ |
| 14 | **3D 元件视图** | Three.js 渲染 3D 模型 → 需要 STEP/VRML 模型库 | `html_bom/` | ⭐⭐⭐ |
| 15 | **使用手册** | `docs/` → 安装配置/功能操作/常见问题 → Markdown + 截图 | 新增 `docs/` | ⭐ |
| 16 | **演示视频** | 录制 ≥3 分钟 → Agent 对话 → BOM 处理 → HTML BOM → 主题切换 | 无代码改动 | ⭐ |

---

## 四、PCB 网表解析器 — 详细实施计划

> 这是当前最关键的前置依赖。3 个空规则检查 + PCB AI 分析都依赖它。

### 立创 EDA 文件格式速查

| 版本 | 文件 | 内部结构 | 包含数据 |
|------|------|---------|---------|
| 标准版 | `.json` | 单文件 JSON，图元属性用 `~` 分隔压缩 | TRACK/PAD/VIA/TEXT/COPPERAREA/net/层/板框 |
| 专业版 | `.epro` | ZIP 包，内含 `.epcb` JSON Lines | 同上 + project.json 清单 |

**可提取的关键数据**：走线（宽度/坐标/层/网络）、过孔（位置/孔径/网络）、焊盘（形状/引脚号/层）、板框（层10图元）、铜皮（多边形区域/间隙）、网络连接（同 netname 图元构成一个逻辑网络）。

### 三路线规划

#### 路线一：文本解析（当前方向，P1 — 优先实施）

**目标**：解析立创 EDA PCB 文件 → 结构化数据 → 文本描述 → LLM 分析

**具体步骤**：

1. **扩展 `PCBData` 数据类**（`src/interfaces/eda_adapter.py`）
   - 新增字段：`traces: list` / `vias: list` / `pads: list` / `nets: dict` / `copper_areas: list` / `board_outline: dict`
   - 新增 `@dataclass`：`Trace` / `Via` / `Pad` / `Net` / `CopperArea`

2. **新增 `src/pcb/parser.py`** — PCB 文件解析器
   - `parse_json(file_path)` — 立创EDA标准版 .json
   - `parse_epro(file_path)` — 立创EDA专业版 .epro (ZIP→.epcb JSON Lines)
   - 自动探测文件格式，统一返回 `PCBData`

3. **新增 `src/pcb/describer.py`** — PCB→文本描述转换器
   - 将 `PCBData` 转为 LLM 可读的文本摘要
   - 包含：板层信息 / 走线统计 / 网络列表 / 电源网络 / 关键尺寸

4. **新增 PCB 专用 Prompt**（`src/agent/prompt_templates.py`）
   - 走线宽度检查 / 差分对验证 / 电源完整性 / 模数分离 / 过孔类型检查

5. **补齐三个空规则**（`src/rules/checker.py`）
   - `_check_signal_traces()` — 信号线宽 ≥ 规则要求
   - `_check_power_traces()` — 电源线载流能力校验
   - `_check_analog_digital_separation()` — 模数区域分离检查

6. **Controller 扩展**（`src/core/controller.py`）
   - 新增 `load_pcb()` 操作
   - 新增 `check_design_rules_pcb()` — 带 PCB 数据的完整规则检查

7. **GUI 扩展**（`src/gui/main_window.py`）
   - 新增"导入PCB"按钮
   - BOM 表格侧新增"PCB概览"标签页

**新增文件**：
- `src/pcb/__init__.py`
- `src/pcb/parser.py` — 立创EDA JSON/EPRO 解析
- `src/pcb/describer.py` — PCB→文本描述转换
- `tests/test_pcb.py` — PCB 模块测试

**改动文件**：
- `src/interfaces/eda_adapter.py` — 扩展 PCBData + 新增数据类 + parse_pcb()
- `src/agent/prompt_templates.py` — 新增 PCB 专用 prompt（5个）
- `src/rules/checker.py` — 三个空规则接入真实数据
- `src/core/controller.py` — 新增 load_pcb()/check_design_rules_pcb()
- `src/gui/main_window.py` — 新增"导入PCB"按钮 + PCB概览标签页

**预估工时**：3-5 天（含测试）

#### 路线二：视觉分析（中期，P2）

**目标**：聊天框粘贴 PCB 截图 → Vision 模型看图分析布局/散热/EMC

**前提条件**：
- 切换支持图片的模型（GPT-4V、Claude 3+、Gemini 2 Flash、Qwen-VL、Kimi K2）
- 聊天框支持粘贴图片
- `LLMClient` 扩展 `chat_with_image()` 方法

**优点**：AI 能看布局全貌，直观判断元件摆位/散热/EMC
**缺点**：不能做精确的线宽/间距量化分析

#### 路线三：两者融合（远期，P3）

- **文本解析**负责精确电气规则检查（线宽/间距/阻抗/载流）
- **视觉分析**负责布局审查（元件摆放合理性/散热/EMC/可制造性）
- Controller 统一路由：按问题类型分发

---

## 五、下一步里程碑与任务分解

> **注意**：基于 2026-05-27 行业调研，里程碑已优化。详见第六章"行业调研与优化方向"→ 6.5 优化后的里程碑。

### M1：轻量 PCB 解析 + RAG 知识库（目标 2026-06-15）

```
1.1  轻量 PCB 解析器（只提取网络+走线宽度+层，≤800行）
1.2  RAG 知识库：索引立创EDA中文文档 + 常见封装规则 + DRC 规则
1.3  补齐信号线宽/电源线宽两个规则（模数分离延后）
1.4  BOM 专用 Prompt 接线（按意图路由到专用模板）
1.5  新增 test_pcb.py（≥15 条测试）
```

### M2：多 LLM 路由 + 视觉接入（目标 2026-06-30）

```
2.1  多 LLM 路由网关（按任务类型分派到不同模型：Kimi/DeepSeek/GPT-4V/Qwen-VL）
2.2  聊天框支持粘贴图片（原理图/PCB截图 → VLM 分析）
2.3  LLM→DRC 自动生成实验（自然语言描述规则 → 自动生成检查函数）
2.4  BOM 健康检查（调用 LCEDA 商城 API → 生命周期/替代料推荐）
```

### M3：闭环验证 + 多智能体（2026 下半年）

```
3.1  闭环验证引擎（LLM 建议 → 规则引擎验证 → 不一致→反馈纠正）
3.2  多智能体协作（BOM agent + DRC agent + PCB agent 并行分析）
3.3  ECharts 热力图 + 跨文件对比 + 模糊指令语义路由
3.4  封装规则自动生成（从数据手册 PDF/网页 用 LLM 提取封装规则）
```

### M4：交付物（2027 春季）

```
4.1  PyInstaller 打包 + 24h 稳定性测试
4.2  使用手册 + 演示视频 + 软著申请
4.3  论文撰写（建议选题：多 LLM 路由在 EDA 的应用 / RAG 增强的 PCB 知识检索）
```

---

## 六、行业调研与优化方向（2026-05-27 调研）

> 调研范围：国际/国内商业 EDA AI 工具、开源项目、学术前沿（2024-2026）
> 目标：明确项目差异化定位，优化技术路线

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
| **4. 多模态 PCB 分析** | PCBSchemaGen (约束引导), 上大 Qwen2.5-VL 蒸馏 | 路线二（视觉）应加速 — Kimi/Qwen-VL 已可用于原理图分析 |
| **5. 闭环验证** | EDAid "分歧思维", UniVista LLM+EDA 闭环 | **关键差异化** — LLM 建议 → 规则引擎验证 → 反馈纠正 |

### 6.3 项目定位优化：从"工具"到"智能网关"

```
当前定位：EDA AI 辅助工具（功能罗列）
优化定位：多 LLM 智能 EDA 网关（模型路由 + 知识检索 + 闭环验证）

               ┌──────────────────────────┐
               │    PyQt5 统一界面         │
               ├──────────────────────────┤
用户自然语言 → │  多 LLM 路由网关          │
               │  ├─ Kimi (中文资料 RAG)   │
               │  ├─ GPT-4V (PCB视觉审查)  │
               │  ├─ DeepSeek (代码/规则)  │
               │  ├─ Qwen-VL (原理图分析)  │
               │  └─ 本地模型 (离线快速)   │
               ├──────────────────────────┤
               │  闭环验证引擎              │
               │  LLM建议 → DRC引擎 → 反馈 │
               └──────────────────────────┘
```

### 6.4 路线图优化建议

基于调研结论，对原有里程碑做出以下调整：

| 原计划 | 调整 | 理由 |
|--------|------|------|
| PCB 解析器 → P1 首位 | **保持不变**，但先做轻量版（仅提取网络+走线宽度，不解析全量几何） | 3 个空规则可用轻量数据先行填补 |
| 路线三（融合）→ 远期 | **提升优先级**：文本解析完成后立即接入 VLM | 立创EDA 已有 Kimi 视觉插件，技术可行性已验证 |
| 模糊指令处理 → P2 | **提升至 P1**：复用多 LLM 路由实现语义路由 | 学术趋势：多智能体路由是最热方向 |
| RAG 知识库 → 未规划 | **新增为 P1**：索引立创EDA中文文档+BOM规则+封装数据库 | 空白领域，竞品（立创）只有基础实现 |
| 封装规则扩充 → P1 | **改为自动生成**：用 LLM 从数据手册自动提取封装规则，而非手写 | DRC-Coder 思路：LLM 自动生成比手写更具学术价值 |
| 供应链感知 BOM → 未规划 | **新增为 P2**：调用立创商城 API，交叉引用物料生命周期、替代料推荐 | 无竞品实现，BOM 健康的实际痛点 |

### 6.5 优化后的里程碑

#### M1：轻量 PCB 解析 + RAG 知识库（目标 2026-06-15）

```
1.1  轻量 PCB 解析器（只提取网络+走线宽度+层，≤800行）
1.2  RAG 知识库：索引立创EDA中文文档 + 常见封装规则 + DRC 规则
1.3  补齐信号线宽/电源线宽两个规则（模数分离延后）
1.4  BOM 专用 Prompt 接线（按意图路由到专用模板）
```

#### M2：多 LLM 路由 + 视觉接入（目标 2026-06-30）

```
2.1  多 LLM 路由网关（按任务类型分派到不同模型）
2.2  聊天框支持粘贴图片（原理图/PCB截图 → VLM 分析）
2.3  LLM→DRC 自动生成实验（自然语言描述规则 → 自动生成检查函数）
2.4  BOM 健康检查（调用 LCEDA 商城 API → 生命周期/替代料推荐）
```

#### M3：闭环验证 + 多智能体（2026 下半年）

```
3.1  闭环验证引擎（LLM 建议 → 规则引擎验证 → 不一致→反馈纠正）
3.2  多智能体协作（BOM agent + DRC agent + PCB agent 并行分析）
3.3  ECharts 热力图 + 跨文件对比 + 模糊指令语义路由
3.4  封装规则自动生成（从数据手册 PDF/网页 用 LLM 提取封装规则）
```

#### M4：交付物（2027 春季）

```
4.1  PyInstaller 打包 + 24h 稳定性测试
4.2  使用手册 + 演示视频 + 软著申请
4.3  论文撰写（选题方向：多 LLM 路由在 EDA 领域的应用 / RAG 增强的 PCB 设计知识检索）
```

### 6.6 论文选题建议

基于调研发现的空白与项目特色，以下选题方向由强到弱排列：

| 选题 | 创新点 | 可行性 | 竞争情况 |
|------|--------|--------|---------|
| **多 LLM 协同路由网关在 EDA 领域的应用** | 首次将多 LLM 路由引入 EDA，按任务/成本/能力分派 | 高（已有 6 厂商基础） | 低竞争（学术空白） |
| **RAG 增强的中文 PCB 设计知识检索系统** | 首个针对立创EDA中文文档的 RAG，对标 ChipMind KG | 高（需建知识库） | 极低竞争 |
| **基于大语言模型的 DRC 规则自动生成与闭环验证** | LLM 生成 DRC 规则→规则引擎验证→反馈迭代 | 高（闭环引擎待建） | 低竞争（DRC-Coder 是 IC 级） |
| **面向 PCB 的 BOM 健康评估与智能替代推荐** | 结合商城 API + LLM 推理，首创 BOM 生命周期感知 | 高（需商城 API） | 无竞争 |

**建议选题组合**：毕业论文可覆盖 M1-M3 全部内容，以"多 LLM 协同 + RAG 知识检索"为主线，小标题拆分上述 4 个方向。

### 6.7 差异化护城河

```
竞品                             本项目
──────────────────────────────────────────────────
立创EDA AI     单LLM(Kimi)     → 多LLM路由(6→按需扩展)
Cadence AI     布局布线专精     → BOM+DRC知识推理（错位竞争）
KiCad MCP      操作KiCad       → 立创EDA生态（国内唯一）
ChipMind KG    IC级知识图谱    → PCB级中文知识图谱（空白）
DRC-Coder      芯片级DRC       → PCB规则自动生成（降维应用）
Synopsys DSO   芯片设计优化     → 高校/个人用户（市场空白）
```

---

## 七、技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.13 |
| GUI 框架 | PyQt5 | 5.x |
| 数据处理 | pandas, openpyxl | — |
| HTML 模板 | Jinja2 | — |
| HTTP 请求 | requests | — |
| 环境管理 | python-dotenv | — |
| 测试框架 | pytest | 8.x |
| 打包（计划中） | PyInstaller | — |
| AI 模型 | DeepSeek / OpenAI / 通义千问 / 智谱 / Kimi / 硅基流动 | — |
| 协议 | OpenAI 兼容 API | — |

---

## 八、测试覆盖

```
tests/
├── test_bom.py          19 tests   BOM解析/合并/校验/查重
├── test_controller.py   36 tests   Controller 操作分发/AI fallback
├── test_eda_adapter.py   5 tests   立创EDA坐标文件解析
├── test_llm_client.py   29 tests   LLM客户端/厂商适配
├── test_rules.py         9 tests   设计规则检查
─────────────────────────────────────
Total:                   98 tests   全部通过 ✅
```

---

## 九、申报书指标达成情况

| 申报书指标 | 实际 | 状态 |
|-----------|------|------|
| 6厂商 LLM 适配 | 6 厂商已实现 | ✅ |
| 对话记忆 ≥10 轮 | 已实现（history 管理 + 清空对话） | ✅ **5/27** |
| 自然语言指令 20+ 条 | 7 条关键词 + AI 语义路由 | ⚠️ 差 13+ |
| 设计规则 15+ 条 | 1 条（去耦电容） + 3 空桩 | ⚠️ 差 14 条 |
| 元件类型 ≥50 种 | 31 条封装规则 | ⚠️ 差 19 种 |
| BOM 全流程 | 解析/合并/校验/查重/HTML 全部完成 | ✅ |
| AI 辅助 BOM 合并 | 规则合并 + AI 智能合并 全链路实现 | ✅ **5/27** |
| HTML BOM 交互 | Canvas 点阵图 + 搜索 + 高亮 | ✅ |
| ECharts 热力图 | Canvas | ⚠️ 待替换 |
| 模糊指令处理 | 关键词 + AI 语义（混合） | ⚠️ 部分完成 |
| 4 主题系统 | 深海/冷白/石墨/青森 + 语义色彩 | ✅ |
| PyInstaller 打包 | 未配置 | ⚠️ Phase 4 |
| 24h 稳定性 | 未测试 | ⚠️ Phase 4 |
| 安装包 <100MB | 未打包 | ⚠️ Phase 4 |
| 论文 1 篇 | 未发表 | 计划 Phase 4 |
| 软著 1 项 | 未申请 | 计划 Phase 4 |
| 98 条测试 | 98 条全部通过 | ✅ |

---

## 十、阶段进度

```
Phase 1 (2026.5-6)   需求分析 + 架构设计 + Agent 原型      ██████████ 100% ✅
Phase 2 (2026.7-10)  BOM 核心 + 函数调用 + 对话记忆        ████████░░  80% 🟡
Phase 3 (2026.11-2)  GUI + HTML BOM + PCB 规则检查         ██████░░░░  60% 🟡
Phase 4 (2027.3-5)   测试 + 打包 + 论文 + 软著              ░░░░░░░░░░   0% ⬜
```

**Phase 2 剩余**：PCB 网表解析器 / 3 个空规则 / 封装规则扩充 / BOM 导出 bug
**Phase 3 剩余**：ECharts 热力图 / 跨文件对比 / KiCad / 模糊指令

---

## 十一、当前未提交变更（2026-05-27）

```
6 files changed: +175 -18  (工作区未提交)

对话记忆上下文:
  src/agent/llm_client.py       +15 -5   use_history 参数 + _record_turn
  src/core/controller.py        +29 -4   _conversation_active + clear_conversation
  src/gui/chat_panel.py         +2       clear_requested 信号
  src/gui/main_window.py        +7       清空对话菜单 + 信号连接

AI 辅助 BOM 合并:
  src/agent/prompt_templates.py  +23      BOM_AI_MERGE 模板 + 注册 + COMMAND_PARSE 更新
  src/bom/merger.py              +63 -6   merge_with_ai_suggestion 完整实现 + logger 修复
  src/core/controller.py         +83 -12  ai_merge_bom() + _format_merged_for_ai() + 路由注册
```

---

## 十二、配置持久化

```
~/.eda_ai_assistant/
└── settings.json         # 用户配置（LLM厂商/Key/模型 + 主题选择）
```

优先级：`环境变量` > `settings.json` > `.env文件` > `厂商预设` > `默认值`

---

## 十三、Git 历史

```
b73dda2 fix: 流式消息显示/数量0显示/异常吞没/内存泄漏 (6项修复)
490a8f4 UI 重构：4主题系统 + 语义色彩 + 卡片布局 + BOM行号列 (v0.3.0)
c0fb13d GUI 重构：VS Code 风格双主题系统 + 设置面板 + 多项修复 (v0.1.0 → v0.2.0)
8b1aac7 优化 HTML BOM 搜索栏：全字段搜索 + 搜索提示 + 面板微调
b313f48 修复 HTML BOM 搜索仅支持位号的问题
3ffaca9 添加核心模块单元测试（19 → 98 条）
4b244f8 代码优化：提取重复逻辑、精简方法体、统一 dispatch 模式
caafccf 重构 LLM 模块：从 DeepSeek 单厂商升级为 6 家多厂商适配
da7e4e6 添加开发日志
69591e0 初始化项目：EDA AI 智能助手
```

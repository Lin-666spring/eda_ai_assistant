# EDA AI 智能助手 — 项目蓝图

> 面向立创EDA的AI智能辅助设计软件 — 内置Agent的BOM管理与PCB设计助手  
> 吉林大学 · 测控技术与仪器专业 · 创新训练项目  
> 版本 v0.3.0 | 2026-05-21 更新

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
│   │   ├── llm_client.py            # LLM 客户端（6厂商、流式、Function Calling）
│   │   └── prompt_templates.py      # Prompt 模板（BOM/Rule/Command）
│   │
│   ├── bom/
│   │   ├── parser.py                # BOM 解析器（CSV/Excel、编码探测、列名映射）
│   │   ├── merger.py                # BOM 合并引擎（型号+封装+参数归一化）
│   │   ├── validator.py             # 封装校验器（31条规则+别名系统）
│   │   ├── checker.py               # 位号查重器（含跨文件）
│   │   └── normalizer.py            # 参数归一化（R/C/L单位统一）
│   │
│   ├── html_bom/
│   │   ├── generator.py             # HTML BOM 生成器
│   │   └── templates/ibom.html      # Jinja2 模板（Canvas点阵图+封装轮廓）
│   │
│   ├── rules/
│   │   └── checker.py               # 设计规则检查器（去耦电容+3个空桩）
│   │
│   ├── interfaces/
│   │   ├── eda_adapter.py           # EDA适配器接口 + 立创EDA适配器
│   │   └── simulator.py             # 仿真器抽象接口 + DummySimulator占位
│   │
│   └── gui/
│       ├── eda_theme.py             # 4主题系统 + 语义色彩 + QSS编译器
│       ├── main_window.py           # 主窗口（导航栏、卡片布局、主题切换）
│       ├── chat_panel.py            # AI对话面板（气泡消息、流式响应、欢迎页）
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
| Prompt 模板体系（BOM/Rule/Command 三类） | `agent/prompt_templates.py` | ✅ |
| 自然语言→JSON操作指令解析 | `core/controller.py:_extract_json()` | ✅ |
| 本地关键词路由 fallback（6条路由） | `core/controller.py:_KEYWORD_ROUTES` | ✅ |
| LLM 热切换（GUI设置面板实时生效） | `gui/settings_panel.py` | ✅ |

### 2.2 BOM 智能处理引擎
| 功能 | 文件 | 状态 |
|------|------|------|
| CSV/Excel BOM 解析（编码自动探测） | `bom/parser.py` | ✅ |
| 同类元件合并（型号+封装+参数归一化） | `bom/merger.py` | ✅ |
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
| 去耦电容检查 | `rules/checker.py:_check_decoupling_caps()` | ✅ |

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

### P0 — 申报书承诺、答辩必问

| # | 功能 | 技术路径 | 涉及文件 | 难度 |
|---|------|---------|---------|------|
| 1 | **对话记忆上下文** | 在 `LLMClient` 中维护 `self._history: list[dict]`，每次 `chat()` 时拼入 messages 数组；界面添加"新建对话"按钮清空历史 | `agent/llm_client.py`<br>`core/controller.py`<br>`gui/chat_panel.py` | ⭐⭐ |
| 2 | **信号线宽度检查** | 依赖 #8 PCB 网表解析器。解析立创EDA PCB文件 → 提取 TRACK 图元 → 遍历信号网络 → 检查线宽是否满足规则 | `rules/checker.py:_check_signal_traces()`<br>`interfaces/eda_adapter.py` | ⭐⭐⭐ |
| 3 | **电源线宽度检查** | 同上。识别电源网络 → 根据载流计算期望线宽 → 对比实际线宽 → 报告违例 | `rules/checker.py:_check_power_traces()` | ⭐⭐⭐ |
| 4 | **模数分离检查** | 同上。识别模拟/数字区域 → 检查地平面分割 → 检查跨分割走线 | `rules/checker.py:_check_analog_digital_separation()` | ⭐⭐⭐ |
| 5 | **AI辅助BOM合并** | `BOMMerger.merge_with_ai_suggestion()` 当前直接 fallback → 改为调用 `LLMClient` 分析差异后给出合并建议 | `bom/merger.py`<br>`agent/prompt_templates.py` | ⭐⭐ |

### P1 — 计划中、有前置依赖

| # | 功能 | 技术路径 | 涉及文件 | 难度 |
|---|------|---------|---------|------|
| 6 | **BOM专用Prompt接线** | Controller 的 `process_input()` 中根据意图路由到 `BOM_MERGE`/`BOM_VALIDATE` 等专用 Prompt 模板，替代当前通用的 `COMMAND_PARSE` | `core/controller.py`<br>`agent/prompt_templates.py` | ⭐⭐ |
| 7 | **BOM导出bug修复** | `merge_bom()` 返回格式化报告文本而非 DataFrame → 重构 `_merged_to_dataframe()` 直接调用 merger 获取结构化数据 | `core/controller.py`<br>`gui/main_window.py` | ⭐ |
| 8 | **PCB 网表解析器** | **三路线规划（见 memory/project_eda_pcb_ai_plan.md）**<br>路线一（优先）：解析立创EDA `.json`/`.epro` 文件 → 扩展 `PCBData` 数据类 → 新增 `PCBDescriber` 文本描述器 → 扩展 Controller | `interfaces/eda_adapter.py`<br>新增 `src/pcb/parser.py`<br>新增 `src/pcb/describer.py` | ⭐⭐⭐ |

### P2 — 增强功能

| # | 功能 | 技术路径 | 涉及文件 | 难度 |
|---|------|---------|---------|------|
| 9 | **ECharts 热力图** | 替换当前 Canvas 实现 → 在 `ibom.html` 模板中引入 ECharts CDN → 用热力图展示元件密度分布 | `html_bom/templates/ibom.html` | ⭐⭐ |
| 10 | **跨文件BOM对比** | Controller 中暴露 `check_multi_file()` → GUI 添加"BOM对比"按钮 → 支持加载两个BOM文件差异对比 | `core/controller.py`<br>`gui/main_window.py` | ⭐ |
| 11 | **封装规则扩充（31→50+）** | 在 `BOMValidator._rules` 中追加 TO-252/TO-263/QFN/BGA/MSOP 等封装规则，达到申报书要求的50+ | `bom/validator.py` | ⭐ |
| 12 | **模糊指令处理** | 将当前纯关键词匹配改为 LLM 语义理解优先 → 关键词仅作离线 fallback → 利用已有的 `PromptTemplates.COMMAND_PARSE` 做意图解析 | `core/controller.py:_match_keyword()` | ⭐⭐ |
| 13 | **KiCad 适配器** | 实现 `KiCadAdapter(EDAAdapter)` → 解析 KiCad `.kicad_pcb` S-expression 格式 → 提取坐标/封装/网络 | `interfaces/eda_adapter.py` | ⭐⭐ |

### P3 — 远期/交付

| # | 功能 | 技术路径 | 涉及文件 | 难度 |
|---|------|---------|---------|------|
| 14 | **PyInstaller 打包** | 编写 `.spec` 文件 → 包含 Jinja2 模板和静态资源 → 测试生成 exe 运行正常 | 新增 `eda_ai_assistant.spec` | ⭐ |
| 15 | **真仿真引擎** | 实现 `LTspiceSimulator(Simulator)` → 生成 SPICE netlist → 调 LTspice 命令行 → 解析输出 | `interfaces/simulator.py` | ⭐⭐⭐⭐ |
| 16 | **3D 元件视图** | 使用 Three.js 在 HTML BOM 中渲染 3D 元件模型 → 需要 STEP/VRML 模型库 | `html_bom/templates/ibom.html`<br>`html_bom/generator.py` | ⭐⭐⭐ |
| 17 | **使用手册** | 创建 `docs/` 目录 → 编写安装配置、功能操作、常见问题 → Markdown + 截图 | 新增 `docs/` | ⭐ |
| 18 | **演示视频** | 录制 ≥3分钟 → Agent 对话 → BOM 处理 → HTML BOM → 主题切换 | 无代码改动 | ⭐ |

---

## 四、PCB 网表解析器 — 三路线规划

> 详见 `memory/project_eda_pcb_ai_plan.md`，此处为技术摘要

### 路线一：文本解析（当前方向，P1）
- 解析立创EDA标准版 `.json` 和专业版 `.epro`/`.epcb` 文件
- 提取：TRACK/PAD/VIA/COPPERAREA/NET/层/板框/DRC规则
- 扩展 `PCBData` 数据类 → 新增 `traces`/`vias`/`pads`/`nets`/`copper_areas` 字段
- 实现 `PCBDescriber` 将结构化数据转为 LLM 可读文本
- 在 `prompt_templates.py` 中新增 PCB 专用 prompt
- Controller 新增 `load_pcb()` 操作

### 路线二：视觉分析（中期）
- 聊天框粘贴 PCB 截图 → Vision 模型看图分析布局/散热/EMC
- 需切换支持图片的模型（GPT-4V/Claude 3+/Qwen-VL）

### 路线三：两者融合（远期）
- 文本解析做量化规则检查 → 视觉分析做布局审查
- Controller 统一路由：按问题类型分发到文本/视觉通道

---

## 五、技术栈

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

## 六、测试覆盖

```
tests/
├── test_bom.py          19 tests   BOM解析/合并/校验/查重
├── test_controller.py   36 tests   Controller 操作分发/AI fallback
├── test_eda_adapter.py   5 tests   立创EDA坐标文件解析
├── test_llm_client.py   29 tests   LLM客户端/厂商适配
├── test_rules.py         9 tests   设计规则检查
─────────────────────────────────────
Total:                   98 tests   全部通过
```

---

## 七、配置持久化

```
~/.eda_ai_assistant/
└── settings.json         # 用户配置（LLM厂商/Key/模型 + 主题选择）
```

优先级：`环境变量` > `settings.json` > `.env文件` > `厂商预设` > `默认值`

---

## 八、阶段进度

```
Phase 1 (2026.5-6)   需求+架构+Agent原型      █████████░ 90%
Phase 2 (2026.7-10)  BOM核心+函数调用映射      ██████░░░░ 60%
Phase 3 (2026.11-2)  GUI+HTML BOM+规则检查    ████████░░ 80%
Phase 4 (2027.3-5)   测试+优化+论文+软著       ░░░░░░░░░░  0%
```

---

## 九、申报书 vs 实际 — 差距速查

| 申报书指标 | 实际 | 状态 |
|-----------|------|------|
| 设计规则 15+ 条 | 1 条 + 3 空桩 | ⚠️ 待补 |
| 对话记忆 ≥10 轮 | 0 | ❌ 待做 |
| 自然语言指令 20+ 条 | 6 关键词路由 | ⚠️ 待扩展 |
| 元件类型 ≥50 种 | 31 封装规则 | ⚠️ 待扩充 |
| 模糊指令处理 | 关键词匹配 | ⚠️ 待做 |
| ECharts 热力图 | Canvas | ⚠️ 待替换或改文档 |
| PyInstaller 打包 | 未配置 | ⚠️ 计划 Phase 4 |
| 24h 稳定性 | 未测试 | ⚠️ 计划 Phase 4 |
| 安装包 <100MB | 未打包 | ⚠️ 计划 Phase 4 |
| 论文 1 篇 | 未发表 | 计划 Phase 4 |
| 软著 1 项 | 未申请 | 计划 Phase 4 |
| 98 条测试 | 98 条全部通过 | ✅ |
| 6厂商 LLM | 已实现 | ✅ |
| 4主题系统 | 已实现 | ✅ |
| BOM 全流程 | 已实现 | ✅ |
| HTML BOM | 已实现 | ✅ |

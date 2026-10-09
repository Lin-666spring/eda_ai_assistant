# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🏆 长期目标 (2026-07-09)

- **EI 论文**: 闭环验证引擎 (LLM→DRC→反馈→迭代)，目标 2026年9月投稿
- **软件著作权**: EDA AI 智能助手 V1.0，目标 2026年8月提交
- **详细路线图**: 见 [PAPER_ROADMAP.md](PAPER_ROADMAP.md)

## 📝 会话记忆 (memories/)

跨会话记忆在 [`memories/`](memories/README.md)：`.epro2` 格式要点、真实 PCB 数据集实验状态、项目审计结论。**新会话先读 `memories/README.md`**。

## Commands

```bash
# Install dependencies (including pynput/pystray for hotkey + tray)
pip install -r requirements.txt

# Run the app (Eel Web UI, opens Chrome/Edge)
python main.py

# Run all tests (965 collected)
python -m pytest tests/ -q

# Run a single test module
python -m pytest tests/test_controller.py -q
python -m pytest tests/test_nlu_engine.py -q
python -m pytest tests/test_agent_loop.py -q
python -m pytest tests/test_persistence.py -q

# Run a single test function
python -m pytest tests/test_tools.py::test_get_keyword_map -q

# Run tests with verbose output
python -m pytest tests/ -v

# Package as Windows exe (唯一构建入口是 eda_ai_assistant.spec：
# rag_data / 演示 CSV / hiddenimports 全在 spec 维护，勿用裸 pyinstaller 命令)
pyinstaller --noconfirm --clean eda_ai_assistant.spec
```

## Architecture

### Entry point → Eel bridge

`main.py` is the Eel application entry. It exposes ~25 `@eel.expose` functions that the JS frontend calls. These thin wrappers delegate to `AppController` — never put business logic in `main.py`.

### Controller (the brain)

`src/core/controller.py` — **AppController** is the UI-agnostic orchestrator. It holds a `CommandContext` (session state: BOM items, positions, PCB data) and handles the full request lifecycle:

1. **Two-stage NLU pipeline** (`process_input`): intent classification → entity extraction → dispatch.

2. **Agent Loop** (`agent_loop`): Function Calling based multi-step reasoning. LLM receives all 24 tool definitions, autonomously decides which tools to call, executes them via `_dispatch_operation`, feeds results back, loops until final text response. Max 5 iterations. Accessible via `send_message_agent` endpoint.

3. **Natural language chat** (`chat_message_stream`): Freeform Markdown chat via streaming. No BOM preload required.

4. **Keyword fallback** (`_local_fallback`): When no LLM configured, matches user input against `ToolRegistry` keywords (exact substring → character bigram fuzzy) and dispatches directly.

### ToolRegistry — Single Source of Truth

`src/agent/tools.py` — All 24 system capabilities are defined as `ToolDef` dataclasses in the `TOOLS` list. Every other module **derives** from here:
- Controller dispatch map ← `get_dispatch_map()`
- Keyword matching ← `get_keyword_map()`
- NLU keywords per intent ← `get_keywords_by_intent()`
- LLM prompt operation list ← `get_operation_descriptions()`
- Help text ← `get_help_text()`
- Function Calling schemas ← `get_function_definitions()`

**To add a new capability, add one `ToolDef` to the `TOOLS` list** — ordering matters for priority (ai_merge_bom before merge_bom → "AI合并" matches the AI variant first).

### LLM client

`src/agent/llm_client.py` — `LLMClient` wraps OpenAI-compatible chat APIs. Supports: `chat()`, `chat_stream()`, `chat_multimodal()`, `function_call()`, and `chat_with_tools()` (multi-turn Function Calling loop). Accepts `tool_executor` callback for tool execution. Provider presets (DeepSeek, OpenAI, Qwen, GLM, Kimi, SiliconFlow) are resolved from `src/constants.py`.

### Persistence

`src/core/persistence.py` — `SessionStore` SQLite persistence layer. 5 tables: `workspaces`, `assistants`, `conversations`, `messages`, `app_state`. Foreign key cascades ensure referential integrity. Database stored at `~/.eda_ai_assistant/sessions.db`. Eel endpoints in `main.py` (`db_load_all`, `db_save/delete_assistant/conversation/message`, `db_save/delete_workspace`, `db_set_active_workspace`, `create_workspace_dir`, `pick_workspace_dir`, etc.). JS persistence helpers in `web/js/persistence.js` are fire-and-forget (no `await`, best-effort).

**Workspaces (工作区)** scope conversations: every conversation carries `workspace_id`, and the left sidebar shows only the current workspace's conversations. `DEFAULT_WORKSPACE_ID = "ws_default"` is created on init and cannot be deleted; deleting another workspace migrates its conversations back to the default. Renaming a conversation must not pass an empty `workspace_id`, or it would silently move to the default workspace — so `save_conversation()` keeps the existing value when the argument is empty. Legacy DBs are migrated inside `_ensure_db()` (adds the `workspace_id` column, backfills `''` → default).

### System bridge

`src/core/system_bridge.py` — Global hotkey (`Ctrl+Shift+E`, pynput) + system tray (pystray) for companion mode. JS polls `poll_toggle` every 500ms. Companion mode hides sidebar + right panel, resizes window to 380×540.

### Router

`src/agent/router.py` — `LLMRouter` classifies user input into `TaskIntent` (TEXT_CHAT, BOM_ANALYSIS, RULE_CHECK, PCB_ANALYSIS, CODE_RULE_GEN, VISUAL, LOCAL_ONLY) and routes to the appropriate LLM provider. Currently uses a single LLM for all text tasks; the architecture supports per-intent provider binding for future multi-model routing.

### Configuration

`src/config.py` — `AppConfig` dataclass with `LLMConfig`, `PathConfig`, `GUIConfig` sub-objects. Priority: environment variables > `~/.eda_ai_assistant/settings.json` (GUI settings panel) > provider presets > legacy `DEEPSEEK_*` env vars. Settings are persisted by the JS frontend calling `save_settings()`.

`src/constants.py` — Frozen dataclasses for all magic numbers/strings: BOM tolerances, PCB trace widths, IPC-2221 current-carrying params, LCSC API endpoints, etc.

存储目录统一由 `constants.app_home()` 给出（settings.json 与 sessions.db 同源），可用环境变量 **`EDA_AI_HOME`** 覆盖 —— 测试/受限环境靠它把落盘位置改到临时目录，不要再各自写 `Path.home() / ".eda_ai_assistant"`。`SessionStore` 支持传入 `db_path`，并按它的父目录建目录。同理，**导出文件目录统一用 `controller.default_output_dir()`**（HTML BOM / BOM CSV 落盘与 REST 端点回查共用），不要再写 `Path.cwd() / "output"` 或按调用方位置反推。

### Frontend

`web/` — Eel-served static files. **Chat-first 布局**：主页面永远是对话界面，模式功能收进「功能子页面」，会话列表在左侧栏。
`#appShell` = `#sidebar`（工作区选择 + `#conversationList` + 助手实例） + `#mainCol`（`#topBar` 模式入口 + `#bodyRow`）；
`#bodyRow` = `#chatArea` + `#rightPanel`（可折叠任务面板）。`#chatArea` 内部依次是 `#subPage`（功能子页面，默认 `.hidden`）/ `#chatMessages` / `#chatFooter`。

- **主页面 = 对话**：启动时不打开任何视图，`closeSubPage()` 保证 `#subPage.hidden`、`#chatMessages` 可见。点顶栏模式入口（`switchView()`）打开功能子页面；点「← 返回对话」，或任何一次发送 / 运行工具（`_enterChatStream()` → `closeSubPage()`）都会回到对话。
- **工具箱是工具的统一管理界面**：目录由后端 `get_tools_catalog()` 派生（即 `src/agent/tools.py` 的 ToolRegistry），前端只声明每个视图「展示哪些工具」。卡片组件 `.tool-card` 在工具箱和所有视图里复用，直接运行走 `run_tool()` → `controller._dispatch_operation()`，与聊天路径共用同一张派发表。**不要在前端另写一份工具名称/描述**。
- **会话列表在左侧栏**（`#conversationList`），只显示「当前助手 + 当前工作区」的会话（`getWorkspaceConversations()`）。`SessionStore.load_all()` 返回的会话记录字段是 `{conv_id, workspace_id, title, sort_order}`，**没有 `id`/`messages`**，`loadPersistedState()` 必须归一化；消息按需由 `switchConversation()` → `db_load_messages` 加载（`conv._loaded` 标记）。
- **工作区选择**在左侧栏顶部（`#workspaceChip` → `#workspaceMenu`）：新建 / 编辑 / 删除工作区，切换后会话列表随之过滤。工作区绑定的本地目录由后端 `create_workspace_dir()` 校验 / 创建；`pick_workspace_dir()` 用子进程跑 tkinter 弹系统目录框（不能在 Eel 主循环里直接开 tkinter，会把服务卡死）。
- 所有气泡（含流式 AI）都必须包在 `.msg-row` 里，否则 `clearChatMessages()` 清不掉，切换会话会重复显示回答。
- **生成/加载过程必须有动效**，统一走三个入口（不要再各写各的 spinner）：
  - `setStatus(msg)` → 顶栏状态胶囊（spinner + 文案）+ `#topProgress` 顶部滑动进度条；「就绪 / 已… / …失败」这类终态自动转 ✓ 并在 1.5s 后淡出。**它不再是空实现**，所有老调用点都因此生效；
  - `createStreamingBubble()` 内建「思考中」块（`.think` = 三点脉冲 + 轮换文案 + 计时器），**首个 token 到达自动让位**给正文 —— 不要在等待期留一个空白气泡；`bubble.think(text)` 可让文案跟随当前动作（如「正在调用工具」）；
  - `_btnLoading(btn, label)` / `_btnLoaded(btn)` → 按钮内联 spinner + 文案替换 + 禁用，可无损还原；`_btnFromEvent()` 在 inline `onclick` 里同步取当前按钮。
  慢的后端调用由 `_BUSY_LABELS` 白名单在 `eel.*` 上统一包一层 `withBusy()`；**轮询类调用（`poll_toggle` 每 500ms）绝不能进白名单**，否则进度条会一直闪。占位骨架用 `.skeleton-card` / `.skeleton-line`，面板占位用 `.panel-loading`；所有动效在 `prefers-reduced-motion` 下降级为静态但仍可见。
- **两段式启动：小窗先出，正式界面后到**（`main.py` + `src/core/boot.py` + `index.html` 的收尾脚本）。
  - 顺序：`main()` 先 `boot.start()` + 起 `boot-worker` 线程，然后**立刻**开窗（480×340，`--window-size` 与 eel 的 `size=` 两层都传）；热键/托盘/知识库预热全在后台上跑。等「前端首屏就绪 + `boot_status().ready`」再 `window.resizeTo(1300,840)` 展开，遮罩淡出、`#appShell` 交叉淡入。
  - **`ready` 只看 critical 步骤**（`BootSequencer`）：知识库预热不是 critical，首启动不再被索引卡住；**failed 也算结束** —— 附属功能失败绝不能把人永远关在小窗里。界面展开后若 `warm` 仍为 false，用 `setStatus` 在顶栏如实报「正在预热知识库…」。
  - **`resizeTo` 被拒绝时不许硬撑**：`index.html` 观察实际尺寸，没变就调 `request_main_window()`（后端改 `eel._start_args` 后 `eel.show`）另开正式窗口；两条路都不通也照样放行淡出。`window.boot.state`（`resize/fallback/expanded`）是这件事的可观测字段，冒烟测试盯着它。
  - 启动界面进度分两层：前端步骤（`splashStatus(text, ratio)`：工作区 / 工具目录 / 设置）+ 后端步骤（`boot_status().text`）。**`boot_status().started=false` 表示不是 `main()` 起的**（冒烟测试、调试直接 `eel.start`）→ 前端立刻跳过等待，别把两段式启动强加给这些场景。
  - URL 加 `#boot-hold` 可停在启动界面（看设计/截图用）。品牌素材（可选 logo）放 `web/img/`，提示词见 `web/img/README.md`；没放文件时用内联 SVG 标记，不会抓 404。
- 深浅色主题都走 `:root` / `body[data-theme="dark"]` 的 token，不要在规则里硬编码颜色。
- 图标统一用 `ICONS` 里的内联 SVG（`web/js/tools.js`），不用 emoji 字体图标；`confirm()` 已由自定义对话框替代。
- 前端 JS 是 13 个经典 script 模块（P1-6 阶段C 拆分，`web/js/`），index.html 按「原单文件的区块顺序」加载——顺序不可调换，模块间靠顶层 `function`/`const` 共享全局作用域；内联 `onclick` 引用的函数必须声明在这些文件顶层。

回归手段：`python tests/ui_smoke.py`（Playwright 真机驱动 + stub LLM，零 API 花费，85 项检查 + 截图到 `output/ui_smoke/`）。覆盖布局回归 P12（主页面默认是对话）/ P13（左侧会话栏 + 工作区隔离）/ P14（生成中的加载动效：思考气泡、顶栏胶囊+进度条、审查骨架屏、按钮 loading）/ P15（热力图数据来源与空状态：坐标文件也能出格、网格边长透传、reason 文案）/ P16（两段式启动：480×340 小窗启动界面不溢出、`#boot-hold` 能停住、展开后遮罩移除、`resizeTo` 被拒走兜底）。
⚠️ Playwright 要起自己的驱动子进程（管道 stdio），在受限沙箱里会 `PermissionError` —— 它需要能正常 `spawn` 的权限，不是代码问题。
文件名不以 `test_` 开头，因此不会被 pytest 收集；配套的 pytest 用例是 `tests/test_heatmap.py`（热力图回落/reason）、`tests/test_tool_catalog.py`（锁前后端工具目录一致性）与 `tests/test_persistence.py`（含 workspaces 用例）。

### Module map

| Directory | Purpose |
|-----------|---------|
| `src/bom/` | CSV/Excel parsing, rule-based merge, package validation, duplicate reference detection |
| `src/pcb/` | PCB JSON parsing, data models |
| `src/rules/` | 71 design rules (`DesignRuleChecker`): decoupling caps, signal traces, power current, acute angles, via density, analog-digital separation, etc. |
| `src/supply/` | LCSC API client + BOM health checker (stock, lifecycle, alternatives, cost) |
| `src/rag/` | ChromaDB indexer + retriever for Chinese PCB knowledge |
| `src/html_bom/` | Interactive HTML BOM generator (Jinja2 templates) |
| `src/interfaces/` | EDA adapter (LCEDAAdapter for 立创EDA JSON), simulator abstraction |
| `src/core/` | Controller, file watcher, SQLite persistence, system bridge (hotkey/tray), boot sequencer (两段式启动) |
| `src/agent/` | NLU engine, LLM client, router, prompt templates, tool registry |

## Key design rules

- **ToolRegistry is the SSOT**: Add capabilities only in `src/agent/tools.py`. Never hardcode keyword lists or dispatch mappings in controller/router.
- **Controller is UI-agnostic**: `AppController` has zero UI imports. Both Eel and CLI (`tests/cli_prototype.py`) consume the same API.
- **`.env` never committed**: API keys go in `.env` (gitignored) or `~/.eda_ai_assistant/settings.json`.
- **`CommandContext` is mutable session state**: BOM items, positions, PCB data live here with a single `has_data` gate.
- **DRC 热力图是「违规计数网格」，不是图像**：`violation.location` 正则抠位号 → 查坐标 → 按 `grid_size_mm` 分桶计数，全程不解析原理图/位图。位置来源优先级 **PCB `component_positions` > 坐标文件(`ctx.positions`)**（`DesignRuleChecker.build_heatmap` 统一处理，`get_heatmap_data` 是它的兼容壳）。入口只有 `AppController.get_drc_heatmap()`，Eel 与 FastAPI 都委托它；空结果必须带 `reason`（`no_data`/`no_positions`/`no_violations`/`unmapped`），前端据此给不同文案 —— 不要退回「只认 PCB 坐标」的老写法，那会让一键演示永远显示"无位置数据"。
- **NLU is lazy-init**: Embedding model loads on first classification call, not at import time.
- **Three chat paths**: `send_message` (NLU pipeline → dispatch), `send_message_stream` (freeform chat), `send_message_agent` (Function Calling Agent Loop).
- **Persistence is fire-and-forget**: JS calls `_persist*` helpers without `await` — DB writes are best-effort, not blocking.
- **Multi-instance assistant model**: `ASSISTANT_TYPES` defines 4 types, `assistantInstances` holds runtime instances. Conversations keyed by instance ID.
- **Conversations are scoped by workspace**: the sidebar filters on `workspace_id`, and a workspace's optional folder path is the project context. Never render all conversations of an instance at once — go through `getWorkspaceConversations()`.
- **Companion mode**: `Ctrl+Shift+E` or tray menu toggles between 1300×840 full layout and 380×540 companion window.

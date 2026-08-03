# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🏆 长期目标 (2026-07-09)

- **EI 论文**: 闭环验证引擎 (LLM→DRC→反馈→迭代)，目标 2026年9月投稿
- **软件著作权**: EDA AI 智能助手 V1.0，目标 2026年8月提交
- **详细路线图**: 见 [PAPER_ROADMAP.md](PAPER_ROADMAP.md)

## Commands

```bash
# Install dependencies (including pynput/pystray for hotkey + tray)
pip install -r requirements.txt

# Run the app (Eel Web UI, opens Chrome/Edge)
python main.py

# Run all 323 tests
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

# Package as Windows exe (double-click build.bat or run this)
pyinstaller --onefile --windowed --name "EDA_AI_Assistant" ^
    --add-data "web;web" --add-data "src;src" ^
    --hidden-import pynput --hidden-import pystray --hidden-import PIL ^
    main.py
```

## Architecture

### Entry point → Eel bridge

`main.py` is the Eel application entry. It exposes ~25 `@eel.expose` functions that the JS frontend calls. These thin wrappers delegate to `AppController` — never put business logic in `main.py`.

### Controller (the brain)

`src/core/controller.py` — **AppController** is the UI-agnostic orchestrator. It holds a `CommandContext` (session state: BOM items, positions, PCB data) and handles the full request lifecycle:

1. **Two-stage NLU pipeline** (`process_input`): intent classification → entity extraction → dispatch.

2. **Agent Loop** (`agent_loop`): Function Calling based multi-step reasoning. LLM receives all 12 tool definitions, autonomously decides which tools to call, executes them via `_dispatch_operation`, feeds results back, loops until final text response. Max 5 iterations. Accessible via `send_message_agent` endpoint.

3. **Natural language chat** (`chat_message_stream`): Freeform Markdown chat via streaming. No BOM preload required.

4. **Keyword fallback** (`_local_fallback`): When no LLM configured, matches user input against `ToolRegistry` keywords (exact substring → character bigram fuzzy) and dispatches directly.

### ToolRegistry — Single Source of Truth

`src/agent/tools.py` — All 24 system capabilities are defined as `ToolDef` dataclasses in the `TOOLS` list. Every other module **derives** from here:
- Controller dispatch map ← `get_dispatch_map()`
- Keyword matching ← `get_keyword_map()`
- NLU keywords per intent ← `get_keywords_by_intent()`
- LLM prompt operation list ← `get_operation_descriptions()`
- Help text ← `get_help_text()`
- Function Calling schemas ← `get_function_definitions()` [PLANNED]

**To add a new capability, add one `ToolDef` to the `TOOLS` list** — ordering matters for priority (ai_merge_bom before merge_bom → "AI合并" matches the AI variant first).

### LLM client

`src/agent/llm_client.py` — `LLMClient` wraps OpenAI-compatible chat APIs. Supports: `chat()`, `chat_stream()`, `chat_multimodal()`, `function_call()`, and `chat_with_tools()` (multi-turn Function Calling loop). Accepts `tool_executor` callback for tool execution. Provider presets (DeepSeek, OpenAI, Qwen, GLM, Kimi, SiliconFlow) are resolved from `src/constants.py`.

### Persistence

`src/core/persistence.py` — `SessionStore` SQLite persistence layer. 4 tables: `assistants`, `conversations`, `messages`, `app_state`. Foreign key cascades ensure referential integrity. Database stored at `~/.eda_ai_assistant/sessions.db`. 8 Eel endpoints in `main.py` (`db_load_all`, `db_save/delete_assistant/conversation/message`, etc.). JS persistence helpers in `app.js` are fire-and-forget (no `await`, best-effort).

### System bridge

`src/core/system_bridge.py` — Global hotkey (`Ctrl+Shift+E`, pynput) + system tray (pystray) for companion mode. JS polls `poll_toggle` every 500ms. Companion mode hides sidebar + right panel, resizes window to 380×540.

### Router

`src/agent/router.py` — `LLMRouter` classifies user input into `TaskIntent` (TEXT_CHAT, BOM_ANALYSIS, RULE_CHECK, PCB_ANALYSIS, CODE_RULE_GEN, VISUAL, LOCAL_ONLY) and routes to the appropriate LLM provider. Currently uses a single LLM for all text tasks; the architecture supports per-intent provider binding for future multi-model routing.

### Configuration

`src/config.py` — `AppConfig` dataclass with `LLMConfig`, `PathConfig`, `GUIConfig` sub-objects. Priority: environment variables > `~/.eda_ai_assistant/settings.json` (GUI settings panel) > provider presets > legacy `DEEPSEEK_*` env vars. Settings are persisted by the JS frontend calling `save_settings()`.

`src/constants.py` — Frozen dataclasses for all magic numbers/strings: BOM tolerances, PCB trace widths, IPC-2221 current-carrying params, LCSC API endpoints, etc.

### Frontend

`web/` — Eel-served static files. Cherry Studio-style three-column layout with sidebar tabs (助手/话题) + multi-instance assistant model + Agent Mode toggle + Window Mode toggle. All functional icons use SVG (chevrons, X buttons, + icons). Confirm dialog replaces browser `confirm()`. `css/style.css` uses rounded corners throughout, no rigid border lines between panels, dark theme default.

### Module map

| Directory | Purpose |
|-----------|---------|
| `src/bom/` | CSV/Excel parsing, rule-based merge, package validation, duplicate reference detection |
| `src/pcb/` | PCB JSON parsing, data models |
| `src/rules/` | 21 design rules: decoupling caps, signal traces, power current, acute angles, via density, analog-digital separation, etc. |
| `src/supply/` | LCSC API client + BOM health checker (stock, lifecycle, alternatives, cost) |
| `src/rag/` | ChromaDB indexer + retriever for Chinese PCB knowledge |
| `src/html_bom/` | Interactive HTML BOM generator (Jinja2 templates) |
| `src/interfaces/` | EDA adapter (LCEDAAdapter for 立创EDA JSON), simulator abstraction |
| `src/core/` | Controller, file watcher, SQLite persistence, system bridge (hotkey/tray) |
| `src/agent/` | NLU engine, LLM client, router, prompt templates, tool registry |

## Key design rules

- **ToolRegistry is the SSOT**: Add capabilities only in `src/agent/tools.py`. Never hardcode keyword lists or dispatch mappings in controller/router.
- **Controller is UI-agnostic**: `AppController` has zero UI imports. Both Eel and CLI (`tests/cli_prototype.py`) consume the same API.
- **`.env` never committed**: API keys go in `.env` (gitignored) or `~/.eda_ai_assistant/settings.json`.
- **`CommandContext` is mutable session state**: BOM items, positions, PCB data live here with a single `has_data` gate.
- **NLU is lazy-init**: Embedding model loads on first classification call, not at import time.
- **Three chat paths**: `send_message` (NLU pipeline → dispatch), `send_message_stream` (freeform chat), `send_message_agent` (Function Calling Agent Loop).
- **Persistence is fire-and-forget**: JS calls `_persist*` helpers without `await` — DB writes are best-effort, not blocking.
- **Multi-instance assistant model**: `ASSISTANT_TYPES` defines 4 types, `assistantInstances` holds runtime instances. Conversations keyed by instance ID.
- **Companion mode**: `Ctrl+Shift+E` or tray menu toggles between 1300×840 full layout and 380×540 companion window.

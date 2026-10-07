"""
EDA AI 智能助手 — Eel 应用入口
面向立创EDA的AI智能辅助设计软件
"""

import base64
import json
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path

import eel

logger = logging.getLogger(__name__)

# Handle PyInstaller bundle
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.controller import AppController
from src.core.file_watcher import FileWatcher
from src.bom.parser import BOMItem
from src.config import config, load_settings, save_settings, SETTINGS_DIR
from src.constants import (
    LLM_PROVIDER_PRESETS,
    DEFAULT_PROVIDER,
    ProviderPreset,
    get_provider_preset,
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    GUI,
)
from src.core.boot import BootSequencer, BootStep

# ── Init ──

eel.init(str(PROJECT_ROOT / "web"))

controller = AppController()
watcher = FileWatcher()

# ── Helpers ──

def _bom_item_to_dict(item: BOMItem) -> dict:
    return {
        "reference": item.reference,
        "value": item.value,
        "package": item.package,
        "part_number": item.part_number,
        "description": item.description,
        "quantity": item.quantity,
        "manufacturer": item.manufacturer,
    }


def _bom_items() -> list:
    return [_bom_item_to_dict(i) for i in controller.context.bom_items]


# ══════════════════════════════════════════
#  Exposed API
# ══════════════════════════════════════════

def _write_temp(name: str, b64: str) -> str:
    """Decode base64 content, write to temp dir, return file path."""
    content = base64.b64decode(b64)
    tmp = Path(tempfile.gettempdir()) / "eda_ai_assistant"
    tmp.mkdir(parents=True, exist_ok=True)
    # 与 src/api/endpoints.py 同步修（2026-10-07）：filename 带路径分隔符时
    # 原样拼接可写到临时目录之外，这里只保留文件名本身。
    file_path = tmp / Path(name).name
    file_path.write_bytes(content)
    return str(file_path)


@eel.expose
def import_bom_file(name: str, b64: str) -> dict:
    try:
        path = _write_temp(name, b64)
        count, msg = controller.load_bom(path)
        return {"ok": True, "count": count, "msg": msg, "items": _bom_items()}
    except Exception as e:
        return {"ok": False, "msg": str(e), "items": []}


@eel.expose
def import_pos_file(name: str, b64: str) -> dict:
    try:
        path = _write_temp(name, b64)
        count, msg = controller.load_positions(path)
        return {"ok": True, "count": count, "msg": msg}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@eel.expose
def import_project_file(name: str, b64: str) -> dict:
    """导入立创 EDA V3 .epro2 工程：一次得到 BOM + PCB"""
    try:
        path = _write_temp(name, b64)
        count, msg = controller.load_project(path)
        pcb = controller.context.pcb_data
        info = {}
        if pcb:
            info = {
                "format": pcb.format,
                "net_count": pcb.net_count,
                "trace_count": pcb.trace_count,
                "via_count": pcb.via_count,
                "pour_count": len(pcb.copper_pours),
                "layers": pcb.layers,
            }
        return {"ok": True, "count": count, "msg": msg, "pcb": info, "items": _bom_items()}
    except Exception as e:
        return {"ok": False, "msg": str(e), "items": []}


@eel.expose
def import_pcb_file(name: str, b64: str) -> dict:
    """导入 PCB 文件（.json / .epro / .epro2）"""
    try:
        path = _write_temp(name, b64)
        count, msg = controller.load_pcb(path)
        pcb = controller.context.pcb_data
        info = {}
        if pcb:
            info = {
                "format": pcb.format,
                "net_count": pcb.net_count,
                "trace_count": pcb.trace_count,
                "via_count": pcb.via_count,
                "layers": pcb.layers,
            }
        return {"ok": True, "count": count, "msg": msg, "pcb": info}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@eel.expose
def load_demo_data() -> dict:
    """一键演示：加载内置示例数据（有缺陷的 MCU 板 BOM + 坐标）"""
    try:
        bom_path = PROJECT_ROOT / "tests" / "sample_bom_bad.csv"
        pos_path = PROJECT_ROOT / "tests" / "sample_positions.csv"
        count, msg = controller.load_bom(str(bom_path))
        pos_count = 0
        if pos_path.exists():
            pos_count, _ = controller.load_positions(str(pos_path))
        return {
            "ok": True, "count": count, "pos_count": pos_count,
            "msg": msg, "items": _bom_items(),
        }
    except Exception as e:
        return {"ok": False, "msg": str(e), "items": []}


@eel.expose
def merge_bom() -> dict:
    try:
        report = controller.merge_bom()
        return {"ok": True, "report": report}
    except Exception as e:
        return {"ok": False, "report": str(e)}


@eel.expose
def ai_merge_bom() -> dict:
    try:
        report = controller.ai_merge_bom()
        return {"ok": True, "report": report}
    except Exception as e:
        return {"ok": False, "report": str(e)}


@eel.expose
def validate_packages() -> dict:
    report = controller.validate_packages()
    return {"ok": True, "report": report}


@eel.expose
def check_duplicates() -> dict:
    report = controller.check_duplicates()
    return {"ok": True, "report": report}


@eel.expose
def check_rules() -> dict:
    report = controller.check_design_rules()
    return {"ok": True, "report": report}


@eel.expose
def check_health() -> dict:
    report = controller.check_bom_health()
    return {"ok": True, "report": report}


@eel.expose
def generate_html_bom() -> dict:
    try:
        report = controller.generate_html_bom()
        out_dir = Path(__file__).parent / "output"
        html_path = out_dir / "ibom.html"
        if html_path.exists():
            import webbrowser
            webbrowser.open(str(html_path))
            return {"ok": True, "report": report, "path": str(html_path)}
        return {"ok": True, "report": report, "path": ""}
    except Exception as e:
        return {"ok": False, "report": str(e), "path": ""}


@eel.expose
def bom_summary() -> dict:
    summary = controller.get_bom_summary()
    return {"ok": True, "summary": summary}


@eel.expose
def pcb_status() -> dict:
    pcb = controller.context.pcb_data
    if not pcb:
        return {"ok": False, "msg": "未加载 PCB 文件"}
    return {"ok": True, "pcb": {
        "format": pcb.format,
        "net_count": pcb.net_count,
        "trace_count": pcb.trace_count,
        "via_count": pcb.via_count,
        "layers": pcb.layers,
    }}


@eel.expose
def send_message(text: str) -> dict:
    """Send a chat message. Returns result synchronously."""
    try:
        result = controller.process_input(text)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "result": str(e)}


@eel.expose
def send_image(text: str, image_b64: str) -> dict:
    """Send a chat message with an image (base64 data URI).

    The image is passed directly to a multimodal LLM for visual analysis.
    """
    try:
        result = controller.process_image_input(text, image_b64)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "result": str(e)}


@eel.expose
def clear_chat():
    controller.clear_conversation()
    return {"ok": True}


@eel.expose
def review_design_multi_agent() -> str:
    """多智能体协同设计审查 — 返回 JSON"""
    return controller.review_design_multi_agent()


@eel.expose
def verify_suggestion(suggestion: str) -> str:
    """闭环验证 — LLM 建议经规则引擎验证后反馈修正 (路线三核心)"""
    return controller.verify_suggestion(suggestion)


@eel.expose
def run_electrical_health_check() -> str:
    """PCB 电气健康检查 — 真实电路计算 (阻抗/PDN/去耦/电流/热/串扰)"""
    return controller.run_electrical_health_check()


@eel.expose
def get_drc_heatmap(grid_size_mm: float = 5.0) -> str:
    """DRC 违规热力图数据 — 返回 JSON {ok, data: [[x,y,count],...], grid_size_mm, source, reason}"""
    import json
    return json.dumps(controller.get_drc_heatmap(grid_size_mm), ensure_ascii=False)


@eel.expose
def set_active_assistant(assistant_id: str) -> dict:
    """切换当前助手"""
    try:
        controller.set_active_assistant(assistant_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "result": str(e)}


@eel.expose
def get_llm_config() -> dict:
    return {
        "provider": config.llm.provider,
        "model": config.llm.model,
        "is_configured": config.llm.is_configured,
        "provider_label": config.llm.provider_label,
    }


@eel.expose
def update_llm_config(provider: str, api_key: str, base_url: str, model: str) -> dict:
    controller.reconfigure_llm(provider, api_key, base_url, model)
    saved = load_settings()
    saved["llm_provider"] = provider
    saved["llm_api_key"] = api_key
    saved["llm_base_url"] = base_url
    saved["llm_model"] = model
    save_settings(saved)
    return {"ok": True}


@eel.expose
def get_settings() -> dict:
    saved = load_settings()
    return {
        "provider": saved.get("llm_provider", "deepseek"),
        "api_key": saved.get("llm_api_key", ""),
        "base_url": saved.get("llm_base_url", ""),
        "model": saved.get("llm_model", ""),
        "temperature": saved.get("llm_temperature", 0.7),
        # 默认浅色：过去默认 "dark" 但前端只有浅色一套 CSS，会造成
        # data-theme="dark" 与真实渲染不一致（2026-09-10 修正）。
        "theme": saved.get("selected_theme", "light"),
        "accent": saved.get("selected_accent", "#5b8def"),
        "font_size": saved.get("font_size", 13),
        "data_dir": str(SETTINGS_DIR),
    }


@eel.expose
def save_theme(theme: str):
    saved = load_settings()
    saved["selected_theme"] = theme
    save_settings(saved)
    return {"ok": True}


@eel.expose
def save_accent(color: str):
    saved = load_settings()
    saved["selected_accent"] = color
    save_settings(saved)
    return {"ok": True}


@eel.expose
def save_font_size(size: int):
    saved = load_settings()
    saved["font_size"] = size
    save_settings(saved)
    return {"ok": True}


@eel.expose
def save_all_settings(provider: str, api_key: str, base_url: str, model: str,
                      temperature: float, theme: str, accent: str) -> dict:
    try:
        controller.reconfigure_llm(provider, api_key, base_url, model)
        saved = load_settings()
        saved["llm_provider"] = provider
        saved["llm_api_key"] = api_key
        saved["llm_base_url"] = base_url
        saved["llm_model"] = model
        saved["llm_temperature"] = temperature
        saved["selected_theme"] = theme
        saved["selected_accent"] = accent
        save_settings(saved)
        logger.info("All settings saved: provider=%s, theme=%s", provider, theme)
        return {"ok": True}
    except Exception as e:
        logger.exception("Failed to save settings")
        return {"ok": False, "error": str(e)}


@eel.expose
def test_llm_connection(provider: str, api_key: str, base_url: str, model: str) -> dict:
    """测试连通性 — 用项目自己的客户端，按厂商协议发一次最小请求。

    ⚠️ 过去这里 `from openai import OpenAI` 直接建客户端，有两个坑：
      1. `openai` 根本不在 requirements.txt 里（干净环境必 ImportError）；
      2. Claude 的 base_url 是 `.../v1/messages`（原生 Messages API，非
         OpenAI 兼容），套给 OpenAI SDK 会 POST 到
         `.../v1/messages/chat/completions` → 必然 404。
    现在统一走 AppController._create_llm_client()，协议分支只有一处。
    """
    import time
    try:
        preset = get_provider_preset(provider)
        url = base_url or preset.base_url
        if not url:
            return {"ok": False, "error": "未配置 API 地址"}
        if not api_key:
            return {"ok": False, "error": "未配置 API Key"}

        client = AppController._create_llm_client(
            api_key, url, model or preset.default_model, preset.name,
        )
        if client is None:
            return {"ok": False, "error": "无法创建客户端"}

        start = time.time()
        reply = client.chat("Hi", max_tokens=5, temperature=0)
        latency = round((time.time() - start) * 1000)
        return {
            "ok": True,
            "latency": latency,
            "model_used": getattr(client, "model", model),
            "protocol": preset.protocol,
            "reply_preview": (reply or "")[:40],
        }
    except Exception as e:
        msg = str(e)
        if len(msg) > 200:
            msg = msg[:200] + "..."
        return {"ok": False, "error": msg}


@eel.expose
def get_providers() -> dict:
    """厂商 + 模型目录 — 设置面板的唯一事实来源（SSOT）。

    前端不再手写 PROVIDERS：名称、地址、模型清单、协议、图标全部来自
    src/constants.py 的 LLM_PROVIDER_PRESETS。
    """
    from src.agent.model_catalog import fallback_models
    providers = []
    for key, preset in LLM_PROVIDER_PRESETS.items():
        providers.append({
            "key": key,
            "name": preset.name,
            "brand": preset.brand or preset.name,
            "label": preset.brand or preset.name,
            "icon": preset.icon or preset.name[:2].upper(),
            "base_url": preset.base_url,
            "default_model": preset.default_model,
            "models": fallback_models(key),
            "models_source": "fallback",      # /models 端点可用时前端会覆盖
            "protocol": preset.protocol,
            "description": preset.description,
            "key_url": preset.key_url,
            "notes": preset.notes,
        })
    return {
        "ok": True,
        "count": len(providers),
        "default_provider": DEFAULT_PROVIDER,
        "providers": providers,
    }


@eel.expose
def fetch_provider_models(provider: str, api_key: str = "", base_url: str = "") -> dict:
    """实时拉取某厂商的模型列表（GET /models，只读免费）。

    api_key 留空时回落到当前已保存的配置，方便「就按现在的 Key 拉一下」。
    """
    from src.agent.model_catalog import list_models
    if not api_key:
        saved = load_settings()
        api_key = saved.get("llm_api_key", "") or config.llm.api_key
    result = list_models(provider, api_key, base_url)
    if result.get("ok"):
        result["models_source"] = "live"
    return result


@eel.expose
def clear_all_data() -> dict:
    """Clear all local data (settings + DB)."""
    import shutil
    try:
        if SETTINGS_DIR.exists():
            shutil.rmtree(str(SETTINGS_DIR))
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@eel.expose
def get_design_suggestions() -> str:
    """设计意图识别：BOM加载后自动调用，返回Markdown格式的主动建议"""
    return controller.get_design_suggestions()


@eel.expose
def has_bom() -> bool:
    return controller.context.has_data


@eel.expose
def has_pcb() -> bool:
    return controller.context.pcb_data is not None


# ══════════════════════════════════════════
#  统一工具目录 — 前端「工具箱」的唯一事实来源
# ══════════════════════════════════════════

def _tool_prompt_prefix(t) -> str:
    """为「需要参数」的工具生成输入预填前缀。

    优先取能作为标签子串出现的关键词（保证 NLU 子串匹配命中），
    否则退回第一个关键词。例：calc_trace_width → "走线宽度 "。
    """
    label = t.label.lower()
    for kw in t.keywords:
        if kw and kw.lower() in label:
            return f"{kw} "
    return f"{t.keywords[0]} " if t.keywords else f"{t.label} "


def _tool_to_dict(t) -> dict:
    required = list((t.params_schema or {}).get("required", []))
    properties = (t.params_schema or {}).get("properties", {})
    ready = True
    blocked_reason = ""
    if t.requires_data and not controller.context.has_data:
        ready = False
        blocked_reason = "需先导入 BOM"
    return {
        "name": t.name,
        "label": t.label,
        "description": t.description,
        "category": t.category,
        "requires_data": bool(t.requires_data),
        "ready": ready,
        "blocked_reason": blocked_reason,
        "needs_input": bool(required),
        "params": [
            {"name": p, "hint": properties.get(p, {}).get("description", "")}
            for p in required
        ],
        "prompt_prefix": _tool_prompt_prefix(t),
        "keywords": list(t.keywords)[:4],
    }


@eel.expose
def get_tools_catalog() -> dict:
    """返回全部系统能力的目录（从 ToolRegistry 派生，前端不再重复维护）。"""
    try:
        from src.agent.tools import ToolRegistry
        tools = [_tool_to_dict(t) for t in ToolRegistry.get_all()]
    except ImportError as e:  # pragma: no cover — 打包缺失时降级
        logger.exception("ToolRegistry unavailable")
        return {"ok": False, "error": str(e), "tools": []}

    categories = []
    for t in tools:
        cid = t["category"]
        hit = next((c for c in categories if c["id"] == cid), None)
        if hit is None:
            categories.append({"id": cid, "count": 1})
        else:
            hit["count"] += 1

    return {
        "ok": True,
        "count": len(tools),
        "ready_count": sum(1 for t in tools if t["ready"]),
        "has_bom": controller.context.has_data,
        "has_pcb": controller.context.pcb_data is not None,
        "categories": categories,
        "tools": tools,
    }


@eel.expose
def run_tool(tool_name: str) -> dict:
    """直接从工具箱运行一个无需参数的能力。

    复用 controller._dispatch_operation，因此与聊天路径走的是同一张
    派发表（ToolRegistry.get_dispatch_map），不存在第二套逻辑。
    """
    try:
        from src.agent.tools import ToolRegistry
    except ImportError as e:  # pragma: no cover
        return {"ok": False, "error": str(e)}

    tool = ToolRegistry.get_by_name(tool_name)
    if tool is None:
        return {"ok": False, "error": f"未知工具: {tool_name}"}
    if tool.requires_data and not controller.context.has_data:
        return {"ok": False, "error": f"「{tool.label}」需要先导入 BOM"}
    if tool.name == "analyze_image":
        return {"ok": False, "error": "请在输入框添加图片后发送"}

    try:
        result = controller._dispatch_operation(tool_name, {})
    except Exception as e:
        logger.exception("run_tool failed: %s", tool_name)
        return {"ok": False, "error": str(e)}

    return {"ok": True, "tool": tool.name, "label": tool.label, "result": str(result or "")}


@eel.expose
def toggle_auto_sync() -> dict:
    if watcher.is_running:
        watcher.stop()
        return {"ok": True, "running": False, "msg": "自动同步已关闭"}
    path = FileWatcher.default_watch_path()
    if not path:
        return {"ok": False, "running": False, "msg": "未找到立创 EDA 项目目录"}
    watcher.watch(path, lambda fp: eel.on_pcb_changed(fp)())
    return {"ok": True, "running": True, "path": path, "msg": f"自动同步已开启 — {path}"}

@eel.expose
def send_message_stream(text: str):
    """Send a chat message with streaming token callbacks to the frontend.

    The controller invokes eel.on_stream_token(token)() for each token,
    eel.on_stream_done(full_text)() on completion, and
    eel.on_stream_error(err_msg)() on failure.
    """
    try:
        result = controller.chat_message_stream(
            text,
            on_token=lambda token: eel.on_stream_token(token)()
        )
        eel.on_stream_done(result)()
    except Exception as e:
        eel.on_stream_error(str(e))()


@eel.expose
def send_message_agent(text: str):
    """Send a chat message via Agent Loop — LLM autonomously selects and calls tools.

    The LLM receives the full tool list (Function Calling), decides which tools
    to call, executes them, and iterates until it has a final answer.

    Streaming: on_stream_token is called for the final text response (simulated
    token-by-token output). Tool execution happens before streaming begins.
    """
    try:
        result = controller.agent_loop(
            text,
            on_token=lambda token: eel.on_stream_token(token)(),
            on_tool_call=lambda name, args: eel.on_tool_call(name)(),
        )
        eel.on_stream_done(result)()
    except Exception as e:
        eel.on_stream_error(str(e))()

# ══════════════════════════════════════════
#  Persistence API (SQLite session store)
# ══════════════════════════════════════════

from src.core.persistence import SessionStore

_store = SessionStore()


@eel.expose
def db_load_all() -> dict:
    """启动时加载全部持久化数据"""
    try:
        data = _store.load_all()
        logger.info("DB load_all: %d assistants", len(data.get("assistants", [])))
        return {"ok": True, "data": data}
    except Exception as e:
        logger.exception("db_load_all failed")
        return {"ok": False, "msg": str(e)}


@eel.expose
def db_save_assistant(instance_id: str, type_id: str, name: str, sort_order: int = 0):
    """保存新助手"""
    try:
        _store.save_assistant(instance_id, type_id, name, sort_order)
        _store.save_state("active_assistant", instance_id)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_save_assistant failed")
        return {"ok": False, "msg": str(e)}


@eel.expose
def db_delete_assistant(instance_id: str):
    """删除助手及其对话"""
    try:
        _store.delete_assistant(instance_id)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_delete_assistant failed")
        return {"ok": False, "msg": str(e)}


@eel.expose
def db_save_conversation(conv_id: str, instance_id: str, title: str = "新对话",
                         workspace_id: str = ""):
    """保存新对话（workspace_id 决定它归属哪个工作区）"""
    try:
        _store.save_conversation(conv_id, instance_id, title, workspace_id=workspace_id)
        _store.save_state("active_conv", conv_id)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_save_conversation failed")
        return {"ok": False, "msg": str(e)}


@eel.expose
def db_delete_conversation(conv_id: str):
    """删除对话及其消息"""
    try:
        _store.delete_conversation(conv_id)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_delete_conversation failed")
        return {"ok": False, "msg": str(e)}


@eel.expose
def db_save_message(conv_id: str, role: str, content: str, image: str = "", seq: int = 0):
    """保存单条消息"""
    try:
        _store.save_message(conv_id, role, content, image or None, seq)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_save_message failed")
        return {"ok": False, "msg": str(e)}


@eel.expose
def db_load_messages(conv_id: str) -> dict:
    """加载指定对话的历史消息"""
    try:
        messages = _store.load_messages(conv_id)
        return {
            "ok": True,
            "messages": [
                {"role": m.role, "content": m.content, "image": m.image or ""}
                for m in messages
            ],
        }
    except Exception as e:
        logger.exception("db_load_messages failed")
        return {"ok": False, "msg": str(e)}


@eel.expose
def db_save_active_state(active_assistant: str = "", active_conv: str = "",
                         active_workspace: str = ""):
    """保存当前活跃的工作区 / 助手 / 对话"""
    try:
        if active_workspace:
            _store.save_state("active_workspace", active_workspace)
        if active_assistant:
            _store.save_state("active_assistant", active_assistant)
        if active_conv:
            _store.save_state("active_conv", active_conv)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_save_active_state failed")
        return {"ok": False, "msg": str(e)}


# ══════════════════════════════════════════
#  工作区（workspace）— 对话按工程上下文隔离
# ══════════════════════════════════════════

@eel.expose
def db_save_workspace(workspace_id: str, name: str, path: str = "") -> dict:
    """新建 / 更新工作区（name + 可选的本地目录）"""
    try:
        if not workspace_id:
            return {"ok": False, "error": "缺少 workspace_id"}
        _store.save_workspace(workspace_id, name or "未命名工作区", path or "")
        return {"ok": True, "workspace": {
            "workspace_id": workspace_id, "name": name, "path": path or "",
        }}
    except Exception as e:
        logger.exception("db_save_workspace failed")
        return {"ok": False, "error": str(e)}


@eel.expose
def db_delete_workspace(workspace_id: str) -> dict:
    """删除工作区（其对话回落到默认工作区，不丢数据）"""
    try:
        _store.delete_workspace(workspace_id)
        return {"ok": True}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.exception("db_delete_workspace failed")
        return {"ok": False, "error": str(e)}


@eel.expose
def db_set_active_workspace(workspace_id: str) -> dict:
    """切换当前工作区（持久化，下次启动仍在同一工作区）"""
    try:
        _store.save_state("active_workspace", workspace_id)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_set_active_workspace failed")
        return {"ok": False, "error": str(e)}


@eel.expose
def db_load_workspaces() -> dict:
    """单独加载工作区列表（设置面板 / 刷新用）"""
    try:
        ws = [{
            "workspace_id": w.workspace_id,
            "name": w.name,
            "path": w.path,
            "sort_order": w.sort_order,
        } for w in _store.load_workspaces()]
        return {"ok": True, "workspaces": ws}
    except Exception as e:
        logger.exception("db_load_workspaces failed")
        return {"ok": False, "error": str(e), "workspaces": []}


_TK_PICK_SCRIPT = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
path = filedialog.askdirectory(title='选择工作区目录')
root.destroy()
print(path or '')
"""


@eel.expose
def pick_workspace_dir() -> dict:
    """弹出系统文件夹选择框，返回选中的目录。

    用子进程跑 tkinter：Eel 的主循环跑在 gevent 上，在主线程里开 tkinter
    对话框会把整个服务卡死，所以隔离到独立进程。
    """
    import subprocess
    try:
        if getattr(sys, "frozen", False):
            # 打包后 sys.executable 是应用本体，不能再喂 -c 脚本
            return {"ok": False, "error": "打包版本暂不支持目录选择，请手动输入路径"}
        proc = subprocess.run(
            [sys.executable, "-c", _TK_PICK_SCRIPT],
            capture_output=True, text=True, timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        path = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
        if not path:
            return {"ok": False, "error": "未选择目录", "cancelled": True}
        return {"ok": True, "path": path}
    except Exception as e:
        logger.warning("pick_workspace_dir failed: %s", e)
        return {"ok": False, "error": str(e)}


@eel.expose
def create_workspace_dir(path: str) -> dict:
    """确保工作区目录存在（不存在则创建），返回规范化后的绝对路径。"""
    try:
        target = Path(path).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        if not target.is_dir():
            return {"ok": False, "error": "路径不是目录"}
        return {"ok": True, "path": str(target.resolve())}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@eel.expose
def open_workspace_dir(path: str) -> dict:
    """在资源管理器中打开工作区目录"""
    try:
        target = Path(path).expanduser()
        if not target.is_dir():
            return {"ok": False, "error": "目录不存在"}
        if sys.platform.startswith("win"):
            os.startfile(str(target))  # noqa: S606 — 本地桌面应用，打开自己的目录
        else:
            import subprocess
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(target)])
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════
#  System bridge (hotkey / tray / window mode)
# ══════════════════════════════════════════

from src.core.system_bridge import (
    consume_toggle, start_hotkey_listener, start_tray, stop_tray,
    is_companion_mode, request_toggle,
)


@eel.expose
def poll_toggle() -> dict:
    """JS 轮询：是否有待处理的模式切换"""
    try:
        toggled = consume_toggle()
        return {"ok": True, "toggled": toggled, "companion": is_companion_mode()}
    except Exception as e:
        return {"ok": False, "toggled": False, "companion": False}


@eel.expose
def get_window_mode() -> dict:
    """获取当前窗口模式"""
    return {"companion": is_companion_mode()}


@eel.expose
def request_window_toggle():
    """JS 主动请求窗口模式切换"""
    try:
        request_toggle()
        return {"ok": True, "companion": is_companion_mode()}
    except Exception as e:
        return {"ok": False}


@eel.expose
def query_knowledge_base(query: str) -> dict:
    """查询 RAG 知识库

    Args:
        query: 自然语言查询问题

    Returns:
        {"ok": True, "result": "..."} 或 {"ok": False, "result": "错误信息"}
    """
    try:
        result = controller.query_knowledge_base(query)
        return {"ok": True, "result": result}
    except Exception as e:
        logger.exception("Eel RAG query failed")
        return {"ok": False, "result": str(e)}


# ══════════════════════════════════════════
#  两段式启动（小窗先出 → 展开正式界面）
# ══════════════════════════════════════════
#  旧的顺序是「先把重活干完，再开窗口」：RAG 建索引、热键、托盘全跑完，屏幕上
#  才出现第一个像素，用户双击之后只能盯着桌面。现在改成:
#     1. 浏览器先开一个 480×340 的小窗（秒开），显示启动界面；
#     2. 热键 / 托盘 / 知识库预热丢到后台线程（boot worker）；
#     3. 关键步骤就绪 + 前端首屏渲染完成 → 前端把窗口 resizeTo 成 1300×840。
#  状态由 BootSequencer 提供，前端轮询 boot_status()。

SPLASH_SIZE = (GUI.SPLASH_WIDTH, GUI.SPLASH_HEIGHT)
MAIN_SIZE = (GUI.MAIN_WIDTH, GUI.MAIN_HEIGHT)

boot = BootSequencer((
    BootStep("services", "正在注册全局热键与系统托盘", critical=True),
    BootStep("knowledge", "正在预热知识库", critical=False),
))


def _centered_position(size: tuple) -> tuple | None:
    """把小窗摆在屏幕正中（取不到屏幕尺寸就交给系统默认位置）。"""
    try:
        import ctypes
        user32 = ctypes.windll.user32          # 非 Windows 没有 windll → 走 except
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        w, h = size
        return max(0, (sw - w) // 2), max(0, (sh - h) // 2)
    except Exception:
        return None


def _window_args(size: tuple) -> list:
    """浏览器命令行里的窗口尺寸 / 位置。

    eel 的 size= 最终是页面里的 window.resizeTo（见 eel.js 的 _position_window），
    能不能生效由浏览器策略决定；命令行参数是窗口创建时浏览器自己应用的，属于
    更可靠的一层。两层都留着，谁先起效都行。
    """
    args = ["--disable-http-cache", "--window-size=%d,%d" % size]
    pos = _centered_position(size)
    if pos:
        args.append("--window-position=%d,%d" % pos)
    return args


def _boot_worker() -> None:
    """后台启动步骤 —— 跑在独立线程里，主线程去开窗口/跑 Eel 主循环。

    放后台的不只是「慢」：它们都不影响对话界面能不能用，没理由让用户等。
    """
    with boot.step("services"):
        start_hotkey_listener()
        show_cb = lambda: request_toggle()   # 托盘「显示/隐藏」→ 切换模式
        exit_cb = lambda: None               # 退出回调由 eel 结束后处理
        start_tray(show_callback=show_cb, exit_callback=exit_cb)

    # 知识库首次索引可能要十几秒 —— 只做预热，不挡界面（前端顶栏会给提示）
    with boot.step("knowledge"):
        controller._ensure_rag_indexed()


def _run_window(mode: str) -> None:
    """开小窗并进入 Eel 主循环（阻塞；gevent 的 hub 靠这个阻塞点跑起来）。"""
    eel.start("index.html", mode=mode, port=0, block=True,
              size=SPLASH_SIZE, cmdline_args=_window_args(SPLASH_SIZE))


@eel.expose
def boot_status() -> dict:
    """前端轮询的启动状态（见 src/core/boot.py 的 BootSequencer.status）。

    额外带上界面要用的品牌信息：
      * started=False 表示不是 main() 起的（例如 UI 冒烟测试直接 eel.start），
        前端据此直接跳过等待，别把小窗流程强加给测试/调试场景；
      * logo 只在文件真的存在时给路径，省得浏览器抓一个 404。
    """
    status = boot.status()
    logo = PROJECT_ROOT / "web" / "img" / "logo-mark.png"
    status["app"] = {"name": APP_NAME, "tagline": APP_TAGLINE, "version": APP_VERSION}
    status["logo"] = "img/logo-mark.png" if logo.is_file() else ""
    status["main_size"] = list(MAIN_SIZE)
    return status


@eel.expose
def request_main_window() -> dict:
    """小窗兜底：resizeTo 被浏览器拒绝时，按正式尺寸另开一个窗口。

    eel 没有「给某个窗口单独指定尺寸」的公开接口 —— show() 读的是 _start_args
    （start() 留下的那份），所以这里改完 size/cmdline_args 再 show，新窗口的
    eel.js 会按 1300×840 摆好自己。
    """
    try:
        if eel._start_args.get("mode") in (None, False, "none"):
            return {"ok": False, "reason": "no_browser"}   # 无窗口模式（测试/调试）
        eel._start_args["size"] = MAIN_SIZE
        eel._start_args["cmdline_args"] = _window_args(MAIN_SIZE)
        eel.show("index.html")
        logger.info("小窗无法自行展开，已另开正式窗口 %sx%s", *MAIN_SIZE)
        return {"ok": True}
    except Exception as e:
        logger.exception("request_main_window failed")
        return {"ok": False, "reason": str(e)}


# ══════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("启动 %s v%s (Eel)...", APP_NAME, APP_VERSION)

    # 先把窗口开出来，再让后台线程干重活（顺序反了用户就要多等好几秒）
    boot.start()
    threading.Thread(target=_boot_worker, daemon=True, name="boot-worker").start()

    try:
        _run_window("chrome")
    except EnvironmentError:
        logger.info("Chrome not found, trying Edge...")
        _run_window("edge")
    finally:
        stop_tray()


def setup_logging(debug: bool = False):
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


if __name__ == "__main__":
    main()

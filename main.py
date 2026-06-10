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
from src.constants import LLM_PROVIDER_PRESETS, ProviderPreset

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
    file_path = tmp / name
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
def import_pcb_file(name: str, b64: str) -> dict:
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
        "theme": saved.get("selected_theme", "dark"),
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
    """Test LLM API connection with a minimal request."""
    import time
    try:
        # Use the OpenAI-compatible client directly
        from openai import OpenAI
        url = base_url or LLM_PROVIDER_PRESETS.get(provider, ProviderPreset(
            name=provider, base_url="", default_model="", description="")).base_url
        if not url:
            return {"ok": False, "error": "未配置 API 地址"}

        client = OpenAI(api_key=api_key, base_url=url)
        start = time.time()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
            temperature=0,
        )
        latency = round((time.time() - start) * 1000)
        return {"ok": True, "latency": latency, "model_used": resp.model}
    except Exception as e:
        msg = str(e)
        if len(msg) > 200:
            msg = msg[:200] + "..."
        return {"ok": False, "error": msg}


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
            on_token=lambda token: eel.on_stream_token(token)()
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
def db_save_conversation(conv_id: str, instance_id: str, title: str = "新对话"):
    """保存新对话"""
    try:
        _store.save_conversation(conv_id, instance_id, title)
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
def db_save_active_state(active_assistant: str = "", active_conv: str = ""):
    """保存当前活跃的助手和对话"""
    try:
        if active_assistant:
            _store.save_state("active_assistant", active_assistant)
        if active_conv:
            _store.save_state("active_conv", active_conv)
        return {"ok": True}
    except Exception as e:
        logger.exception("db_save_active_state failed")
        return {"ok": False, "msg": str(e)}


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


# ══════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("启动 EDA AI 智能助手 (Eel)...")

    # 启动全局热键
    start_hotkey_listener()

    # 启动系统托盘
    show_cb = lambda: request_toggle()  # 托盘"显示/隐藏" → 切换模式
    exit_cb = lambda: None  # 退出回调由 eel 结束后处理
    start_tray(show_callback=show_cb, exit_callback=exit_cb)

    try:
        eel.start("index.html", mode="chrome",
                  size=(1300, 840), port=0, block=True)
    except EnvironmentError:
        logger.info("Chrome not found, trying Edge...")
        eel.start("index.html", mode="edge",
                  size=(1300, 840), port=0, block=True)
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

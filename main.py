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

# Handle PyInstaller bundle
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.controller import AppController
from src.core.file_watcher import FileWatcher
from src.bom.parser import BOMItem
from src.config import config, load_settings, save_settings

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
def clear_chat():
    controller.clear_conversation()
    return {"ok": True}


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
        "theme": saved.get("selected_theme", "dark"),
    }


@eel.expose
def save_theme(theme: str):
    saved = load_settings()
    saved["selected_theme"] = theme
    save_settings(saved)
    return {"ok": True}


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

# ── Streaming is not well-supported by Eel; use sync path for now ──

# ══════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("启动 EDA AI 智能助手 (Eel)...")

    try:
        eel.start("index.html", mode="chrome",
                  size=(1300, 840), port=0, block=True)
    except EnvironmentError:
        logger.info("Chrome not found, trying Edge...")
        eel.start("index.html", mode="edge",
                  size=(1300, 840), port=0, block=True)


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

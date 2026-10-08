"""双入口（Eel main.py / REST endpoints.py）共用的设置与 BOM 序列化 —— 单一实现。

2026-10-08（P1-7）收编：get_settings / save_all_settings / test_llm_connection /
_bom_item_to_dict 曾在两个入口各写一份，先后发生过漂移 —— f3a27e4（/llm/test
REST 侧漏改仍依赖 openai SDK）、446a0db（font_size 只有 REST 侧落盘）都是
双实现漂移的产物。现在逻辑只在这里，两个入口留薄委托。

注意：两个入口的 controller 是各自的单例（main.get_controller vs
src.api.server.get_controller），所以需要落盘前重配客户端的函数都把
ctrl 作为参数传入，而不是在 facade 里自己找 controller。
"""

from __future__ import annotations

import logging
import time

from src.config import SETTINGS_DIR, load_settings, save_settings
from src.constants import get_provider_preset

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  BOM 序列化
# ═══════════════════════════════════════════════════════════════


def bom_item_to_dict(item) -> dict:
    """BOMItem → 前端字典（两个入口曾各有一份逐字节相同的实现）。"""
    return {
        "reference": item.reference,
        "value": item.value,
        "package": item.package,
        "part_number": item.part_number,
        "description": item.description,
        "quantity": item.quantity,
        "manufacturer": item.manufacturer,
    }


def bom_items(ctrl) -> list[dict]:
    return [bom_item_to_dict(i) for i in ctrl.context.bom_items]


# ═══════════════════════════════════════════════════════════════
#  设置读取 / 落盘
# ═══════════════════════════════════════════════════════════════


def settings_view() -> dict:
    """GET /settings 与 eel get_settings 的公共取值口径。

    不含 REST 侧的 "ok": True 包装（由 endpoints 自己加）。
    """
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


def persist_all_settings(ctrl, provider: str, api_key: str, base_url: str,
                         model: str, temperature: float, theme: str,
                         accent: str, font_size: int | None = None) -> None:
    """先热重配 LLM 客户端，再全量落盘。异常向上抛，由入口决定返回形状。

    font_size=None 时不写该键 —— Eel 侧字号走独立的 save_font_size（历史
    行为），REST 侧请求体带 font_size 一并落盘（446a0db 的修复口径）。
    """
    ctrl.reconfigure_llm(provider, api_key, base_url, model)
    saved = load_settings()
    saved["llm_provider"] = provider
    saved["llm_api_key"] = api_key
    saved["llm_base_url"] = base_url
    saved["llm_model"] = model
    saved["llm_temperature"] = temperature
    saved["selected_theme"] = theme
    saved["selected_accent"] = accent
    if font_size is not None:
        saved["font_size"] = font_size
    save_settings(saved)
    logger.info("All settings saved: provider=%s, theme=%s", provider, theme)


# ═══════════════════════════════════════════════════════════════
#  LLM 连通性测试
# ═══════════════════════════════════════════════════════════════


def test_llm_connection(provider: str, api_key: str, base_url: str, model: str) -> dict:
    """测试连通性 — 用项目自己的客户端，按厂商协议发一次最小请求。

    协议分支只在 AppController._create_llm_client() 一处（f3a27e4：曾用
    openai SDK，Claude 原生协议必 404）。错误文案以 Eel 侧中文为准。
    """
    try:
        preset = get_provider_preset(provider)
        url = base_url or preset.base_url
        if not url:
            return {"ok": False, "error": "未配置 API 地址"}
        if not api_key:
            return {"ok": False, "error": "未配置 API Key"}

        from src.core.controller import AppController
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

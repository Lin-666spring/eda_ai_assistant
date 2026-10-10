"""
FastAPI application factory for the EDA AI Assistant API server.

Shares the same AppController class as the Eel desktop app, but
each server process gets its own controller instance.  Both the
desktop app and the API server read/write the same SQLite database
(~/.eda_ai_assistant/sessions.db) and settings.json, so configuration
set in one frontend is visible to the other.
"""

from __future__ import annotations

import logging
import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pathlib import Path

logger = logging.getLogger(__name__)

# ── singleton controller, created lazily ──────────────────────
_controller = None
_controller_lock = threading.Lock()


def _create_controller():
    """Build an AppController using the persisted LLM config, if any."""
    from src.config import load_settings
    from src.core.controller import AppController

    settings = load_settings()
    # 2026-10-06 修复：原读 "api_key"/"provider" 等无前缀键，而所有保存方
    # （main.py / endpoints.py）统一写 "llm_*" 前缀 → 这里永远取空，
    # 自动重配置是死代码。键名与保存侧对齐。
    api_key = settings.get("llm_api_key", "") or None
    ctrl = AppController(api_key=api_key)

    # If a saved provider + key exist, auto-configure the LLM client.
    provider = settings.get("llm_provider", "")
    if api_key and provider:
        try:
            ctrl.reconfigure_llm(
                provider=provider,
                api_key=api_key,
                base_url=settings.get("llm_base_url", ""),
                model=settings.get("llm_model", ""),
            )
        except Exception:
            logger.debug("Could not auto-configure LLM from saved settings", exc_info=True)

    return ctrl


def get_controller():
    """Return the shared AppController singleton (lazy init).

    端点是同步 def，FastAPI 会丢进线程池并发执行 —— 首批并发请求同时
    看到 _controller is None 会各建一份 controller，此后 BOM/会话状态
    分裂（与 2026-10-06 SSE 桥接的线程安全问题同族）。双检加锁。
    """
    global _controller
    if _controller is None:
        with _controller_lock:
            if _controller is None:
                _controller = _create_controller()
    return _controller


# ── FastAPI app ───────────────────────────────────────────────

app = FastAPI(
    title="EDA AI Assistant API",
    version="1.0.0",
    description="REST API for BOM management, PCB design review, and AI chat",
)

# CORS 白名单（2026-10-10 安全批）：此前 allow_origins=["*"] + /settings 回明文
# Key，用户浏览器里任意网页都能 fetch 127.0.0.1:8710 窃取。响应现已脱敏，但仍
# 收敛到已知调用方：lceda 插件 iframe（file:///扩展页 Origin 为 "null"，见
# lceda_plugin/iframe/app.js 直连本服务）、本机端口、lceda 编辑器域（内容脚本
# fetch 走页面 Origin）。新增调用方在此显式追加。
# frontend/ Vite 模板已随批6 清退，5173 调试端口一并移除。
_CORS_ALLOWED_ORIGINS = [
    "null",  # file:// / 扩展沙盒 iframe（lceda 插件面板）
    "http://127.0.0.1:8710",
    "http://localhost:8710",
    "https://pro.lceda.cn",
    "https://lceda.cn",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── serve iframe static files (for LCEDA plugin dev) ─────────

IFRAME_DIR = Path(__file__).parent.parent.parent / "lceda_plugin" / "iframe"
if IFRAME_DIR.is_dir():
    app.mount("/static/iframe", StaticFiles(directory=str(IFRAME_DIR), html=True), name="iframe")

# ── register routes (lazy import) ────────────────────────────

# Imported here to avoid circular imports — endpoints.py imports server.get_controller
# but the app must be defined first.
from src.api.endpoints import router  # noqa: E402

app.include_router(router, prefix="/api/v1")


def start_server(host: str = "127.0.0.1", port: int = 8710) -> None:
    """Start the API server synchronously (blocking)."""
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()

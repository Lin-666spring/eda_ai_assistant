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
from fastapi.middleware.trustedhost import TrustedHostMiddleware
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


def reset_controller():
    """Drop the controller singleton.

    本地数据被清除后（/clear-all-data）调用：旧 controller 持有指向已删除
    sessions.db 的状态与已清除的 LLM Key（验收 A-5，2026-10-24）。下次
    get_controller() 会按（现已为空的）持久化配置重建。
    """
    global _controller
    with _controller_lock:
        _controller = None


# ── FastAPI app ───────────────────────────────────────────────

app = FastAPI(
    title="EDA AI Assistant API",
    version="1.0.0",
    description="REST API for BOM management, PCB design review, and AI chat",
)

# CORS 白名单（2026-10-10 安全批）：此前 allow_origins=["*"] + /settings 回明文
# Key，用户浏览器里任意网页都能 fetch 127.0.0.1:8710 窃取。响应现已脱敏，但仍
# 收敛到已知调用方：lceda 插件 iframe（插件面板由本服务自挂在 /static/iframe，
# Origin 即本机端口；编辑器内容脚本 fetch 走页面 Origin，见 lceda_plugin/dist/main.js）、
# 本机端口、lceda 编辑器域。新增调用方在此显式追加。
# P1-18（验收 2026-10-24）：移除 "null" —— CORS 只拦「读响应」，不拦「发请求」，
# 保留 "null" 等于给任意本地 file:///沙盒页发跨站请求开绿灯；插件面板实际由
# 本服务同源自挂，不需要 "null"。破坏性端点的 CSRF 防护见 endpoints.py 的
# require_ajax_header（跨站表单/简单请求带不了自定义头）。
# frontend/ Vite 模板已随批6 清退，5173 调试端口一并移除。
_CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8710",
    "http://localhost:8710",
    "https://pro.lceda.cn",
    "https://lceda.cn",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    # X-Requested-With：破坏性端点的反 CSRF 头，白名单来源的合法调用方需携带
    allow_headers=["Content-Type", "X-Requested-With"],
)

# P1-18（验收 2026-10-24）：TrustedHost —— 本服务只该被本机回环访问，Host 头
# 异常（DNS rebinding / 缓存投毒扫描）直接 400。hostname 比对不含端口。
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost"],
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

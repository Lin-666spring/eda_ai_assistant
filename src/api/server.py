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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pathlib import Path

logger = logging.getLogger(__name__)

# ── singleton controller, created lazily ──────────────────────
_controller = None


def _create_controller():
    """Build an AppController using the persisted LLM config, if any."""
    from src.config import load_settings
    from src.core.controller import AppController

    settings = load_settings()
    api_key = settings.get("api_key", "") or None
    ctrl = AppController(api_key=api_key)

    # If a saved provider + key exist, auto-configure the LLM client.
    provider = settings.get("provider", "")
    if api_key and provider:
        try:
            ctrl.reconfigure_llm(
                provider=provider,
                api_key=api_key,
                base_url=settings.get("base_url", ""),
                model=settings.get("model", ""),
            )
        except Exception:
            logger.debug("Could not auto-configure LLM from saved settings", exc_info=True)

    return ctrl


def get_controller():
    """Return the shared AppController singleton (lazy init)."""
    global _controller
    if _controller is None:
        _controller = _create_controller()
    return _controller


# ── FastAPI app ───────────────────────────────────────────────

app = FastAPI(
    title="EDA AI Assistant API",
    version="1.0.0",
    description="REST API for BOM management, PCB design review, and AI chat",
)

# Allow the LCEDA iframe (file:// or edge:// origin) and any localhost client.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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


# ═══════════════════════════════════════════════════════════════
#  Convenience launcher
# ═══════════════════════════════════════════════════════════════


def start_server(host: str = "127.0.0.1", port: int = 8710) -> None:
    """Start the API server synchronously (blocking)."""
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()

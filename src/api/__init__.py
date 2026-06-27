"""
FastAPI server for EDA AI Assistant — exposes AppController as REST API.

Used by the LCEDA plugin (or any HTTP client) while the Eel desktop
app continues to work identically via its WebSocket RPC bridge.
"""

from src.api.server import app, start_server, get_controller

__all__ = ["app", "start_server", "get_controller"]

"""Shared pytest fixtures.

Unit tests must not depend on the developer machine's live credentials.
src.config loads .env at import time, so a real API key would leak into
AppController and send "offline" tests down the online code path.

The autouse fixture below forces a hermetic "no LLM configured" baseline.
Tests that need an LLM pass an explicit key (e.g. AppController(api_key=...))
or monkeypatch the relevant field themselves.
"""
from __future__ import annotations

import pytest

from src.config import config


@pytest.fixture(autouse=True)
def _hermetic_llm_config(monkeypatch):
    """Blank the ambient LLM config so tests are reproducible anywhere."""
    for field in ("api_key", "base_url", "model", "provider"):
        if hasattr(config.llm, field):
            monkeypatch.setattr(config.llm, field, "", raising=False)
    yield

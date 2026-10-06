"""Shared pytest fixtures.

Unit tests must not depend on the developer machine's live credentials.
src.config loads .env at import time, so a real API key would leak into
AppController and send "offline" tests down the online code path.

The autouse fixture below forces a hermetic "no LLM configured" baseline.
Tests that need an LLM pass an explicit key (e.g. AppController(api_key=...))
or monkeypatch the relevant field themselves.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# 必须在 import src.config 之前设置：config / persistence 都在模块级把
# ~/.eda_ai_assistant 解析成常量。测试统一写临时目录 —— 既不污染开发者数据，
# 也让受限/只读沙箱里的 pytest tests/ 能正常收集（否则 SessionStore 在 import
# 期就打开 WAL 数据库，直接 OperationalError，整个包都收集不起来）。
os.environ.setdefault("EDA_AI_HOME", tempfile.mkdtemp(prefix="eda_ai_test_home_"))

from src.config import config  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_llm_config(monkeypatch):
    """Blank the ambient LLM config so tests are reproducible anywhere."""
    for field in ("api_key", "base_url", "model", "provider"):
        if hasattr(config.llm, field):
            monkeypatch.setattr(config.llm, field, "", raising=False)
    yield

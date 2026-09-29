"""默认外观必须是浅色（2026-09-15）。

历史上有三处默认值是 "dark"：REST API 请求模型、API GET /settings 兜底、
桌面 GUI 的主题兜底。它们让「默认浅色」只在 Eel 前端成立，另外两个入口仍是深色。
本文件把三处都锁住（Eel 入口由 tests/test_tool_catalog.py::test_theme_default_is_light 覆盖）。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_eda_theme():
    """独立加载 src/gui/eda_theme.py。

    src/gui/__init__.py 会 import PyQt5，而 eda_theme 本身只用标准库；
    按文件路径加载即可，测试不依赖 Qt。
    """
    path = ROOT / "src" / "gui" / "eda_theme.py"
    spec = importlib.util.spec_from_file_location("_eda_theme_standalone", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── REST API ──


def test_settings_request_model_defaults_to_light():
    from src.api.models import SettingsRequest

    assert SettingsRequest().theme == "light"


def test_api_get_settings_falls_back_to_light(monkeypatch):
    from src.api import endpoints

    monkeypatch.setattr(endpoints, "load_settings", lambda: {})
    assert endpoints.get_settings()["theme"] == "light"


def test_api_get_settings_keeps_saved_theme(monkeypatch):
    from src.api import endpoints

    monkeypatch.setattr(endpoints, "load_settings", lambda: {"selected_theme": "dark"})
    assert endpoints.get_settings()["theme"] == "dark"


# ── 桌面 GUI ──


def test_gui_theme_fallback_is_light(tmp_path):
    mod = _load_eda_theme()
    mod._SETTINGS_FILE = tmp_path / "missing.json"
    assert mod._load_theme_preference() == "light"


def test_gui_theme_respects_saved_preference(tmp_path):
    mod = _load_eda_theme()
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"selected_theme": "dark"}), encoding="utf-8")
    mod._SETTINGS_FILE = f
    assert mod._load_theme_preference() == "dark"


def test_gui_theme_display_order_lists_light_first():
    assert _load_eda_theme().THEME_DISPLAY_ORDER[0] == "light"

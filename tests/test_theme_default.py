"""默认外观必须是浅色（2026-09-15）。

历史上有三处默认值是 "dark"：REST API 请求模型、API GET /settings 兜底、
桌面 GUI 的主题兜底。它们让「默认浅色」只在 Eel 前端成立，另外两个入口仍是深色。
本文件把 REST 两处锁住（Eel 入口由 tests/test_tool_catalog.py::test_theme_default_is_light 覆盖）。

2026-10-10 仓库治理批：src/gui/（PyQt5）整栈删除，原「桌面 GUI」三用例
（standalone 加载 src/gui/eda_theme.py）随之移除 —— 唯一 UI 栈是 web/，
其主题兜底由前端首屏引导脚本 + localStorage 决定。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── REST API ──


def test_settings_request_model_defaults_to_light():
    from src.api.models import SettingsRequest

    assert SettingsRequest().theme == "light"


def test_api_get_settings_falls_back_to_light(monkeypatch):
    # P1-7 后取值口径在 settings_facade.settings_view，接缝跟着实现走
    import src.settings_facade as facade

    monkeypatch.setattr(facade, "load_settings", lambda: {})
    from src.api import endpoints

    assert endpoints.get_settings()["theme"] == "light"


def test_api_get_settings_keeps_saved_theme(monkeypatch):
    import src.settings_facade as facade

    monkeypatch.setattr(facade, "load_settings", lambda: {"selected_theme": "dark"})
    from src.api import endpoints

    assert endpoints.get_settings()["theme"] == "dark"

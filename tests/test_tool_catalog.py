# -*- coding: utf-8 -*-
"""统一工具目录（前端「工具箱」）— 后端端点 + 前后端一致性。

背景：过去前端在自己那份 `VIEWS` 里手写工具的名称/描述/图标，与
`src/agent/tools.py` 的 ToolRegistry 是两份独立数据，必然漂移。
现在前端只声明「展示哪些工具」，其余全部来自 `get_tools_catalog()`。

这里锁住两件事：
  1. 目录端点本身的行为（字段完整性、可用性判定、直跑守卫）；
  2. **前后端不漂移** —— app.js 里出现的工具名必须都在 ToolRegistry 里，
     反过来每个能力也必须有前端图标，视图里引用的工具名不能是拼错的。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agent.tools import ToolRegistry  # noqa: E402

# P1-6 阶段C 后 app.js 拆为 web/js/*.js 多模块；静态断言改对模块拼接源做
# （各模块按序拼接 ≡ 原 app.js，块级正则的匹配结果不变）。
FRONTEND_JS = sorted(
    p for p in (ROOT / "web" / "js").glob("*.js") if p.name != "marked.min.js"
)


@pytest.fixture(scope="module")
def main_mod():
    """导入 Eel 入口模块（导入期只做 eel.init，不启动服务）。"""
    import main
    return main


@pytest.fixture(scope="module")
def app_js() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in FRONTEND_JS)


# ══════════════════════════════════════════════════════
#  1. 目录端点
# ══════════════════════════════════════════════════════


class TestToolsCatalog:
    def test_returns_every_registered_tool(self, main_mod):
        cat = main_mod.get_tools_catalog()
        assert cat["ok"] is True
        assert cat["count"] == ToolRegistry.count() == len(cat["tools"])
        assert {t["name"] for t in cat["tools"]} == set(ToolRegistry.list_names())

    def test_entries_are_complete(self, main_mod):
        for t in main_mod.get_tools_catalog()["tools"]:
            assert t["label"], t["name"]
            assert t["description"], t["name"]
            assert t["category"], t["name"]
            assert isinstance(t["ready"], bool)
            assert isinstance(t["needs_input"], bool)
            assert isinstance(t["prompt_prefix"], str) and t["prompt_prefix"].strip()
            if not t["ready"]:
                assert t["blocked_reason"], t["name"]

    def test_category_counts_match(self, main_mod):
        cat = main_mod.get_tools_catalog()
        counted = sum(c["count"] for c in cat["categories"])
        assert counted == cat["count"]
        assert {c["id"] for c in cat["categories"]} == {
            t["category"] for t in cat["tools"]}

    def test_ready_count_matches_flag(self, main_mod):
        cat = main_mod.get_tools_catalog()
        assert cat["ready_count"] == sum(1 for t in cat["tools"] if t["ready"])

    def test_data_dependent_tools_blocked_without_bom(self, main_mod):
        """没有 BOM 时，requires_data 的能力必须被标成不可用并给出原因。"""
        main_mod.get_controller().context.bom_items = []
        blocked = [t for t in main_mod.get_tools_catalog()["tools"] if not t["ready"]]
        assert blocked, "空 BOM 下应当有需要数据的能力被拦住"
        assert all(t["requires_data"] for t in blocked)

    def test_no_bom_dependent_tool_is_ever_ready_without_data(self, main_mod):
        main_mod.get_controller().context.bom_items = []
        for t in main_mod.get_tools_catalog()["tools"]:
            if t["requires_data"]:
                assert not t["ready"], t["name"]


class TestPromptPrefix:
    """「需补参数」的工具要靠预填前缀命中 NLU 关键词匹配。"""

    def test_prefix_hits_registry_keyword(self, main_mod):
        for t in main_mod.get_tools_catalog()["tools"]:
            if not t["needs_input"]:
                continue
            tool = ToolRegistry.get_by_name(t["name"])
            lowered = t["prompt_prefix"].lower()
            assert any(kw.lower() in lowered for kw in tool.keywords), \
                f"{t['name']} 的预填前缀 {t['prompt_prefix']!r} 匹配不到任何关键词"


class TestRunTool:
    def test_unknown_tool_is_rejected(self, main_mod):
        resp = main_mod.run_tool("does_not_exist")
        assert resp["ok"] is False
        assert "未知工具" in resp["error"]

    def test_data_dependent_tool_requires_bom(self, main_mod):
        main_mod.get_controller().context.bom_items = []
        resp = main_mod.run_tool("merge_bom")
        assert resp["ok"] is False
        assert "导入 BOM" in resp["error"]

    def test_image_tool_points_to_input_box(self, main_mod):
        resp = main_mod.run_tool("analyze_image")
        assert resp["ok"] is False
        assert "图片" in resp["error"]

    def test_runs_tool_that_needs_no_data(self, main_mod):
        """pcb_status 是纯本地查询，不发网络请求。"""
        main_mod.get_controller().context.pcb_data = None
        resp = main_mod.run_tool("pcb_status")
        assert resp["ok"] is True
        assert resp["tool"] == "pcb_status"
        assert resp["label"] == ToolRegistry.get_label("pcb_status")
        assert isinstance(resp["result"], str) and resp["result"]

    def test_dispatch_goes_through_registry_map(self, main_mod):
        """直跑必须复用 controller 的分发表，不能另起一套逻辑。"""
        dispatch = main_mod.get_controller()._build_dispatch_map()
        assert set(ToolRegistry.list_names()) <= set(dispatch)


class TestSettingsDefaults:
    def test_theme_default_is_light(self, main_mod, monkeypatch):
        monkeypatch.setattr(main_mod, "load_settings", lambda: {})
        assert main_mod.get_settings()["theme"] == "light"


# ══════════════════════════════════════════════════════
#  2. 前后端一致性（防止再次各写一份）
# ══════════════════════════════════════════════════════


def _js_block(text: str, header: str) -> str:
    """取出 `const HEADER = {` … `};` 之间的块。"""
    start = text.index(header)
    depth, i = 0, text.index("{", start)
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise AssertionError(f"未找到 {header} 的完整块")


def _icons_map(app_js: str) -> dict[str, str]:
    block = _js_block(app_js, "const TOOL_ICONS")
    return dict(re.findall(r"([a-z_0-9]+)\s*:\s*'([^']+)'", block))


def _view_tool_lists(app_js: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for view, body in re.findall(
            r"\n  (\w+): \{(.*?)\n  \},\n", app_js, re.S):
        m = re.search(r"tools:\s*\[([^\]]*)\]", body)
        if m:
            out[view] = re.findall(r"'([^']+)'", m.group(1))
    return out


class TestFrontendStaysInSync:
    def test_every_registered_tool_has_an_icon(self, app_js):
        icons = _icons_map(app_js)
        missing = [n for n in ToolRegistry.list_names() if n not in icons]
        assert not missing, f"这些能力在 app.js 的 TOOL_ICONS 里没有图标: {missing}"

    def test_no_icon_for_nonexistent_tool(self, app_js):
        icons = _icons_map(app_js)
        known = set(ToolRegistry.list_names())
        stale = sorted(set(icons) - known)
        assert not stale, f"TOOL_ICONS 里有已不存在的能力（改名后忘了同步）: {stale}"

    def test_view_tool_lists_reference_real_tools(self, app_js):
        known = set(ToolRegistry.list_names())
        lists = _view_tool_lists(app_js)
        assert lists, "没解析到任何视图的 tools 列表（app.js 结构变了？）"
        for view, names in lists.items():
            unknown = [n for n in names if n not in known]
            assert not unknown, f"{view} 视图引用了不存在的能力: {unknown}"

    def test_icon_emoji_exists_in_icon_set(self, app_js):
        """TOOL_ICONS 的值必须是 ICONS 里真实存在的键，否则卡片图标为空。"""
        icons_block = _js_block(app_js, "const ICONS")
        available = set(re.findall(r"'([^']+)':\s*'<svg", icons_block))
        missing = {k: v for k, v in _icons_map(app_js).items() if v not in available}
        assert not missing, f"TOOL_ICONS 指向了 ICONS 里没有的 emoji: {missing}"

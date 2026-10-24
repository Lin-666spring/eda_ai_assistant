"""P1-11 回归（验收 2026-10-24）：Eel 端点缺 try/except 兜底。

修复前 check_rules / get_drc_heatmap / save_theme 等少数端点一旦抛错，异常
穿透 eel 回调 —— 前端 await 永远挂起（DRC 全量扫描是最易抛错路径）。本组
测试把每个曾裸奔的端点逐个打炸，负样本断言方向：**不向上抛异常**，且返回
前端能直接消费的错误结构（error dict / 可 JSON.parse 的错误 JSON / 错误文案）。
"""

import json

import pytest

import main


class _BoomObj:
    """任何调用、任何属性访问都炸的万能故障对象。"""

    def __call__(self, *args, **kwargs):
        raise RuntimeError("exploded")

    def __getattr__(self, name):
        return _BoomObj()


class _BoomCtrl:
    """任意属性访问都返回故障对象的 controller 桩 —— 模拟 DRC/LLM/IO 全故障
    （含 ctrl.context.has_data 这类链式取值）。"""

    def __getattr__(self, name):
        return _BoomObj()


@pytest.fixture()
def boom_controller(monkeypatch):
    monkeypatch.setattr(main, "get_controller", lambda: _BoomCtrl())


class TestDictEndpointsReturnErrorDict:
    """dict 型端点：异常必须兜成 {"ok": False, ...}，而不是抛穿 eel 回调。"""

    def test_check_rules_explodes_into_error_dict(self, boom_controller):
        result = main.check_rules()
        assert result["ok"] is False
        assert "exploded" in result["report"]

    def test_check_rules_controller_init_failure_caught(self, monkeypatch):
        def _boom():
            raise RuntimeError("controller init exploded")
        monkeypatch.setattr(main, "get_controller", _boom)
        result = main.check_rules()
        assert result["ok"] is False
        assert "exploded" in result["report"]

    def test_clear_chat_explodes_into_error_dict(self, boom_controller):
        result = main.clear_chat()
        assert result["ok"] is False
        assert "exploded" in result["error"]

    def test_get_settings_explodes_into_error_dict(self, monkeypatch):
        import src.settings_facade as facade
        monkeypatch.setattr(
            facade, "settings_view",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("settings exploded")),
        )
        result = main.get_settings()
        assert result["ok"] is False
        assert "exploded" in result["error"]

    @pytest.mark.parametrize("fn", ["save_theme", "save_accent", "save_font_size"])
    def test_save_theme_family_io_failure_caught(self, monkeypatch, fn):
        def _boom(*a, **k):
            raise OSError("disk exploded")
        monkeypatch.setattr(main, "load_settings", _boom)
        result = getattr(main, fn)("dark" if fn == "save_theme" else "#000" if fn == "save_accent" else 13)
        assert result["ok"] is False
        assert "exploded" in result["error"]

    def test_get_tools_catalog_non_import_error_caught(self, monkeypatch):
        monkeypatch.setattr(
            "src.agent.tools.ToolRegistry.get_all",
            classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("registry exploded"))),
        )
        result = main.get_tools_catalog()
        assert result["ok"] is False
        assert result["tools"] == []

    def test_run_tool_guard_error_caught(self, boom_controller):
        # 工具查找/前置校验（get_controller、context 读取）原先也在 try 之外；
        # merge_bom 是 requires_data 工具 —— 校验阶段就要读 controller.context
        result = main.run_tool("merge_bom")
        assert result["ok"] is False
        assert "exploded" in result["error"]

    def test_toggle_auto_sync_error_caught(self, monkeypatch):
        class _FakeWatcher:
            is_running = False

            @staticmethod
            def default_watch_path():
                return "C:/nonexistent-lceda"

            def watch(self, path, cb):
                raise RuntimeError("observer exploded")

        monkeypatch.setattr(main, "watcher", _FakeWatcher())
        monkeypatch.setattr(main, "FileWatcher", _FakeWatcher)
        result = main.toggle_auto_sync()
        assert result["ok"] is False
        assert "exploded" in result["error"]

    def test_get_providers_error_caught(self, monkeypatch):
        monkeypatch.setattr(
            "src.agent.model_catalog.fallback_models",
            lambda key: (_ for _ in ()).throw(RuntimeError("catalog exploded")),
        )
        result = main.get_providers()
        assert result["ok"] is False
        assert result["providers"] == []

    def test_fetch_provider_models_error_caught(self, monkeypatch):
        monkeypatch.setattr(
            "src.agent.model_catalog.list_models",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network exploded")),
        )
        result = main.fetch_provider_models("deepseek", "sk-x")
        assert result["ok"] is False
        assert result["models"] == []

    def test_boot_status_error_returns_not_started(self, monkeypatch):
        class _BoomBoot:
            def status(self):
                raise RuntimeError("boot exploded")

        monkeypatch.setattr(main, "boot", _BoomBoot())
        result = main.boot_status()
        assert result["started"] is False
        assert "exploded" in result["error"]

    def test_get_llm_config_error_returns_unconfigured_shape(self, monkeypatch):
        class _BoomLLM:
            def __getattr__(self, name):
                raise RuntimeError("cfg exploded")

        class _BoomConfig:
            llm = _BoomLLM()

        monkeypatch.setattr(main, "config", _BoomConfig())
        result = main.get_llm_config()
        assert result["is_configured"] is False
        assert "exploded" in result["error"]


class TestJsonStringEndpointsReturnParseableError:
    """返回 JSON 字符串的端点：异常必须兜成可 json.loads 的错误 JSON，
    前端 await 与 JSON.parse 两关都不能挂。"""

    def test_get_drc_heatmap_error_json(self, boom_controller):
        raw = main.get_drc_heatmap(5.0)
        data = json.loads(raw)          # 修复前：抛异常 → 前端永远收不到
        assert data["ok"] is False
        assert data["data"] == []
        assert data["grid_size_mm"] == 5.0
        assert "exploded" in data["reason"]

    def test_get_drc_violations_error_json(self, boom_controller):
        data = json.loads(main.get_drc_violations())
        assert data["ok"] is False
        assert data["items"] == []
        assert "exploded" in data["reason"]

    def test_get_board_3d_data_error_json(self, boom_controller):
        data = json.loads(main.get_board_3d_data())
        assert data["ok"] is False
        assert data["board"] is None
        assert "exploded" in data["reason"]

    def test_review_design_multi_agent_error_json(self, boom_controller):
        data = json.loads(main.review_design_multi_agent())
        assert data["ok"] is False
        assert "exploded" in data["error"]

    def test_get_design_suggestions_error_text(self, boom_controller):
        text = main.get_design_suggestions()
        assert isinstance(text, str)
        assert "失败" in text


class TestHappyPathUnaffected:
    """正向对照：兜底不得吞掉正常结果。"""

    def test_check_rules_success(self, monkeypatch):
        class _Ctrl:
            def check_design_rules(self):
                return {"violation_count": 0}

        monkeypatch.setattr(main, "get_controller", lambda: _Ctrl())
        result = main.check_rules()
        assert result == {"ok": True, "report": {"violation_count": 0}}

    def test_get_drc_heatmap_success(self, monkeypatch):
        class _Ctrl:
            def get_drc_heatmap(self, grid):
                return {"ok": True, "data": [[0, 0, 1]], "grid_size_mm": grid}

        monkeypatch.setattr(main, "get_controller", lambda: _Ctrl())
        data = json.loads(main.get_drc_heatmap(5.0))
        assert data["ok"] is True
        assert data["data"] == [[0, 0, 1]]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

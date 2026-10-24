"""clear_all_data 回归测试（验收报告 A-5）。

修复前双向损坏：
- 开发模式：rmtree 删掉 sessions.db 后 _store 单例不重置，reload 后首个
  db_* 调用在无表空库上报 no such table；
- 打包模式：日志 FileHandler 持有 app_home()/logs/app.log 句柄，Windows
  下整目录 rmtree 必抛 PermissionError，「清除数据」永远失败；
- 附带：内存中的 LLM API Key 不清除。
"""

import json

import pytest

from src.config import SETTINGS_DIR, SETTINGS_FILE, clear_local_data, config
from src.core.persistence import SessionStore


@pytest.fixture()
def populated_home():
    """在（conftest 已隔离的）SETTINGS_DIR 下构造 settings/sessions.db/logs。"""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    (SETTINGS_DIR / "logs").mkdir(exist_ok=True)
    (SETTINGS_DIR / "logs" / "app.log").write_text("log line", encoding="utf-8")
    SETTINGS_FILE.write_text(json.dumps({"llm_api_key": "sk-test"}), encoding="utf-8")
    store = SessionStore()   # 在该 home 下建 sessions.db
    store.save_state("k", "v")
    yield store


class TestClearLocalData:
    def test_removes_settings_and_db_but_keeps_logs(self, populated_home):
        assert (SETTINGS_DIR / "settings.json").exists()
        assert (SETTINGS_DIR / "sessions.db").exists()

        clear_local_data()

        assert not (SETTINGS_DIR / "settings.json").exists()
        assert not (SETTINGS_DIR / "sessions.db").exists()
        # logs/ 保留（打包版日志句柄在持有中，且便于排查清除后的异常）
        assert (SETTINGS_DIR / "logs" / "app.log").exists()

    def test_in_memory_api_key_wiped(self, populated_home):
        # conftest 的 autouse fixture 会把 config.llm 清空成基线，
        # 这里直接注入再验证清除动作会把它抹掉
        object.__setattr__(config.llm, "api_key", "sk-test")
        assert config.llm.api_key == "sk-test"
        clear_local_data()
        assert config.llm.api_key == ""
        assert not config.llm.is_configured

    def test_fresh_store_after_clear_works(self, populated_home):
        """清除后重建 SessionStore 必须能正常建库读写（A-5 核心场景）。"""
        clear_local_data()
        store = SessionStore()
        store.save_state("fresh", "ok")
        assert store.load_state("fresh") == "ok"


class TestEelClearAllDataResetsSingletons:
    def test_main_singletons_reset(self, populated_home):
        import main

        main._store = SessionStore()
        main._controller = object()   # 任意非 None 占位
        try:
            result = main.clear_all_data()
            assert result["ok"] is True, result
            # 旧单例必须被置空，否则指向已删除的库
            assert main._store is None
            assert main._controller is None
            # reload 后首个调用在全新库上正常工作
            store = main.get_store()
            store.save_state("after_reload", "1")
            assert store.load_state("after_reload") == "1"
        finally:
            main._store = None
            main._controller = None


class TestRestClearAllData:
    def test_endpoint_resets_controller(self, populated_home):
        from src.api import server
        from src.api.endpoints import clear_all_data

        server._controller = object()
        try:
            resp = clear_all_data()
            assert resp.ok is True
            assert server._controller is None
            assert not (SETTINGS_DIR / "settings.json").exists()
        finally:
            server._controller = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

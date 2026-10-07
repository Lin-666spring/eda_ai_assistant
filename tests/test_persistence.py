"""SessionStore 单元测试 — SQLite 会话持久化"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.core.persistence import (
    SessionStore,
    AssistantRecord,
    ConversationRecord,
    MessageRecord,
    DEFAULT_WORKSPACE_ID,
)


@pytest.fixture
def store(tmp_path):
    """创建临时数据库的 SessionStore（使用 pytest tmp_path，自动清理）"""
    db_path = tmp_path / "test_sessions.db"
    return SessionStore(db_path=db_path)


class TestAssistants:
    def test_save_and_load(self, store):
        store.save_assistant("a1", "eda-general", "EDA 助手", 0)
        store.save_assistant("a2", "bom-expert", "BOM 专家", 1)
        result = store.load_assistants()
        assert len(result) == 2
        assert result[0].instance_id == "a1"
        assert result[1].name == "BOM 专家"

    def test_update_existing(self, store):
        store.save_assistant("a1", "eda-general", "原名", 0)
        store.save_assistant("a1", "eda-general", "新名", 0)
        result = store.load_assistants()
        assert len(result) == 1
        assert result[0].name == "新名"

    def test_delete(self, store):
        store.save_assistant("a1", "eda-general", "测试", 0)
        store.delete_assistant("a1")
        assert len(store.load_assistants()) == 0

    def test_delete_cascades_conversations(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_conversation("c1", "a1", "对话1", 0)
        store.delete_assistant("a1")
        convs = store.load_conversations("a1")
        assert len(convs) == 0


class TestConversations:
    def test_save_and_load(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_conversation("c1", "a1", "BOM讨论", 0)
        store.save_conversation("c2", "a1", "PCB检查", 1)
        result = store.load_conversations("a1")
        assert len(result) == 2
        assert result[0].title == "BOM讨论"
        assert result[1].title == "PCB检查"

    def test_delete(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_conversation("c1", "a1", "对话", 0)
        store.delete_conversation("c1")
        assert len(store.load_conversations("a1")) == 0

    def test_load_by_instance(self, store):
        store.save_assistant("a1", "eda-general", "助手A", 0)
        store.save_assistant("a2", "bom-expert", "助手B", 1)
        store.save_conversation("c1", "a1", "A的对话", 0)
        store.save_conversation("c2", "a2", "B的对话", 0)
        assert len(store.load_conversations("a1")) == 1
        assert len(store.load_conversations("a2")) == 1
        assert len(store.load_conversations()) == 2


class TestWorkspaces:
    def test_default_workspace_created_on_init(self, store):
        ws = store.load_workspaces()
        assert any(w.workspace_id == DEFAULT_WORKSPACE_ID for w in ws)

    def test_save_and_load(self, store):
        store.save_workspace("w1", "主板项目", "C:/proj/main")
        hit = [w for w in store.load_workspaces() if w.workspace_id == "w1"]
        assert len(hit) == 1
        assert hit[0].name == "主板项目"
        assert hit[0].path == "C:/proj/main"

    def test_update_existing(self, store):
        store.save_workspace("w1", "旧名", "C:/a")
        store.save_workspace("w1", "新名", "C:/b")
        hit = [w for w in store.load_workspaces() if w.workspace_id == "w1"]
        assert len(hit) == 1 and hit[0].name == "新名" and hit[0].path == "C:/b"

    def test_conversations_scoped_to_workspace(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_workspace("w1", "项目A")
        store.save_conversation("c1", "a1", "A的对话", 0, "w1")
        store.save_conversation("c2", "a1", "默认的对话", 0)
        assert [c.conv_id for c in store.load_conversations(workspace_id="w1")] == ["c1"]
        default_ids = [c.conv_id for c in store.load_conversations(
            workspace_id=DEFAULT_WORKSPACE_ID)]
        assert "c2" in default_ids
        assert "c1" not in default_ids

    def test_rename_keeps_original_workspace(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_workspace("w1", "项目A")
        store.save_conversation("c1", "a1", "原标题", 0, "w1")
        # 重命名时不传 workspace_id —— 不能让对话悄悄搬回默认工作区
        store.save_conversation("c1", "a1", "新标题", 0)
        rec = store.load_conversations("a1")[0]
        assert rec.title == "新标题"
        assert rec.workspace_id == "w1"

    def test_delete_workspace_migrates_conversations(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_workspace("w1", "项目A")
        store.save_conversation("c1", "a1", "A的对话", 0, "w1")
        store.delete_workspace("w1")
        assert not any(w.workspace_id == "w1" for w in store.load_workspaces())
        assert store.load_conversations("a1")[0].workspace_id == DEFAULT_WORKSPACE_ID

    def test_default_workspace_cannot_be_deleted(self, store):
        with pytest.raises(ValueError):
            store.delete_workspace(DEFAULT_WORKSPACE_ID)


class TestMessages:
    def test_save_and_load(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_conversation("c1", "a1", "对话", 0)
        store.save_message("c1", "user", "合并BOM", seq=0)
        store.save_message("c1", "ai", "已完成合并", seq=1)
        result = store.load_messages("c1")
        assert len(result) == 2
        assert result[0].role == "user"
        assert result[0].content == "合并BOM"
        assert result[1].role == "ai"

    def test_image_message(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_conversation("c1", "a1", "对话", 0)
        store.save_message("c1", "user", "分析图片", image="data:image/png;base64,abc123", seq=0)
        result = store.load_messages("c1")
        assert result[0].image == "data:image/png;base64,abc123"

    def test_delete_conversation_cascades_messages(self, store):
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_conversation("c1", "a1", "对话", 0)
        store.save_message("c1", "user", "hello", seq=0)
        store.delete_conversation("c1")
        assert len(store.load_messages("c1")) == 0


class TestAppState:
    def test_save_and_load(self, store):
        store.save_state("active_assistant", "a1")
        assert store.load_state("active_assistant") == "a1"

    def test_load_nonexistent(self, store):
        assert store.load_state("no_such_key") is None

    def test_update(self, store):
        store.save_state("key1", "v1")
        store.save_state("key1", "v2")
        assert store.load_state("key1") == "v2"


class TestLoadAll:
    def test_empty(self, store):
        data = store.load_all()
        assert data["assistants"] == []
        assert data["conversations"] == {}
        assert data["active_assistant"] is None
        # 空库也必须有一个默认工作区，否则前端会没有可选项
        assert len(data["workspaces"]) == 1
        assert data["workspaces"][0]["workspace_id"] == DEFAULT_WORKSPACE_ID
        assert data["active_workspace"] is None

    def test_full_restore(self, store):
        store.save_assistant("a1", "eda-general", "EDA助手", 0)
        store.save_assistant("a2", "bom-expert", "BOM专家", 1)
        store.save_workspace("w1", "项目A", "C:/proj/a")
        store.save_conversation("c1", "a1", "对话A", 0, "w1")
        store.save_conversation("c2", "a2", "对话B", 0)
        store.save_message("c1", "user", "你好", seq=0)
        store.save_message("c1", "ai", "你好！", seq=1)
        store.save_state("active_workspace", "w1")
        store.save_state("active_assistant", "a1")
        store.save_state("active_conv", "c1")

        data = store.load_all()
        assert len(data["assistants"]) == 2
        assert len(data["conversations"]["a1"]) == 1
        assert len(data["conversations"]["a2"]) == 1
        assert data["conversations"]["a1"][0]["workspace_id"] == "w1"
        assert data["active_workspace"] == "w1"
        assert data["active_assistant"] == "a1"
        assert data["active_conv"] == "c1"

    def test_load_all_includes_message_count(self, store):
        """会话行带消息条数 —— 前端列表徽标在消息按需加载前不再恒显 0。"""
        store.save_assistant("a1", "eda-general", "助手", 0)
        store.save_conversation("c1", "a1", "有消息", 0)
        store.save_conversation("c2", "a1", "没消息", 1)
        store.save_message("c1", "user", "你好", seq=0)
        store.save_message("c1", "ai", "你好！", seq=1)

        convs = {c["conv_id"]: c for c in store.load_all()["conversations"]["a1"]}
        assert convs["c1"]["message_count"] == 2
        assert convs["c2"]["message_count"] == 0


class TestSaveAll:
    def test_bulk_snapshot(self, store):
        assistants = [
            {"instanceId": "a1", "typeId": "eda-general", "name": "EDA助手"},
            {"instanceId": "a2", "typeId": "bom-expert", "name": "BOM专家"},
        ]
        conversations = {
            "a1": [{"id": "c1", "title": "对话1"}],
            "a2": [{"id": "c2", "title": "对话2"}],
        }
        store.save_all(assistants, conversations, "a1", "c1")

        data = store.load_all()
        assert len(data["assistants"]) == 2
        assert data["active_assistant"] == "a1"
        assert data["active_conv"] == "c1"


def test_custom_db_path_creates_missing_parent(tmp_path):
    """自定义 db_path 时按它自己的父目录建目录（而不是永远 mkdir 全局 DB_DIR）。"""
    from src.core.persistence import SessionStore
    db_path = tmp_path / "nested" / "deeper" / "sessions.db"
    store = SessionStore(db_path=db_path)
    assert db_path.exists()
    store.save_state("k", "v")
    assert store.load_all() is not None


def test_app_home_honors_env(monkeypatch, tmp_path):
    from src.constants import app_home
    monkeypatch.setenv("EDA_AI_HOME", str(tmp_path))
    assert app_home() == tmp_path


def test_app_home_defaults_to_user_dir(monkeypatch):
    from src.constants import app_home
    monkeypatch.delenv("EDA_AI_HOME", raising=False)
    assert app_home().name == ".eda_ai_assistant"


"""SessionStore 单元测试 — SQLite 会话持久化"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.core.persistence import SessionStore, AssistantRecord, ConversationRecord, MessageRecord


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

    def test_full_restore(self, store):
        store.save_assistant("a1", "eda-general", "EDA助手", 0)
        store.save_assistant("a2", "bom-expert", "BOM专家", 1)
        store.save_conversation("c1", "a1", "对话A", 0)
        store.save_conversation("c2", "a2", "对话B", 0)
        store.save_message("c1", "user", "你好", seq=0)
        store.save_message("c1", "ai", "你好！", seq=1)
        store.save_state("active_assistant", "a1")
        store.save_state("active_conv", "c1")

        data = store.load_all()
        assert len(data["assistants"]) == 2
        assert len(data["conversations"]["a1"]) == 1
        assert len(data["conversations"]["a2"]) == 1
        assert data["active_assistant"] == "a1"
        assert data["active_conv"] == "c1"


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

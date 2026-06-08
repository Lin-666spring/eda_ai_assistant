"""
会话持久化 — SQLite 存储助手实例、对话和消息

沿用 settings.json 的存储目录 (~/.eda_ai_assistant/)，不受浏览器缓存影响。

表结构:
    assistants    — 助手实例 (instance_id, type_id, name, sort_order)
    conversations — 对话 (conv_id, instance_id, title, sort_order)
    messages      — 消息 (id, conv_id, role, content, image, seq)
    app_state     — 键值对 (key, value)，存当前活跃助手/对话

使用方式:
    store = SessionStore()
    store.save_assistant(inst_id, type_id, name)
    assistants = store.load_assistants()
"""

import json
import logging
import sqlite3
import stat
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 与 config.py 共享同一存储目录
DB_DIR = Path.home() / ".eda_ai_assistant"
DB_PATH = DB_DIR / "sessions.db"


# ══════════════════════════════════════════════════════
#  Data models
# ══════════════════════════════════════════════════════


@dataclass
class AssistantRecord:
    instance_id: str
    type_id: str
    name: str
    sort_order: int = 0


@dataclass
class ConversationRecord:
    conv_id: str
    instance_id: str
    title: str = "新对话"
    sort_order: int = 0


@dataclass
class MessageRecord:
    conv_id: str
    role: str
    content: str
    image: Optional[str] = None
    seq: int = 0


# ══════════════════════════════════════════════════════
#  SessionStore
# ══════════════════════════════════════════════════════


class SessionStore:
    """SQLite 会话持久化存储"""

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or DB_PATH
        self._ensure_db()

    # ── Lifecycle ──

    def _ensure_db(self):
        """创建目录和数据库表"""
        DB_DIR.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS assistants (
                    instance_id TEXT PRIMARY KEY,
                    type_id     TEXT NOT NULL,
                    name        TEXT NOT NULL,
                    sort_order  INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    conv_id     TEXT PRIMARY KEY,
                    instance_id TEXT NOT NULL,
                    title       TEXT DEFAULT '新对话',
                    sort_order  INTEGER DEFAULT 0,
                    FOREIGN KEY (instance_id) REFERENCES assistants(instance_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    conv_id  TEXT NOT NULL,
                    role     TEXT NOT NULL,
                    content  TEXT NOT NULL DEFAULT '',
                    image    TEXT,
                    seq      INTEGER DEFAULT 0,
                    FOREIGN KEY (conv_id) REFERENCES conversations(conv_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS app_state (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );

                PRAGMA foreign_keys = ON;
                PRAGMA journal_mode = WAL;
            """)
        # 限制文件权限
        try:
            os.chmod(self._db_path, stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    # ── Assistants ──

    def save_assistant(self, instance_id: str, type_id: str, name: str, sort_order: int = 0):
        """新增或更新助手实例"""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO assistants (instance_id, type_id, name, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (instance_id, type_id, name, sort_order),
            )
            conn.commit()
        logger.debug("Assistant saved: %s (%s)", name, instance_id)

    def delete_assistant(self, instance_id: str):
        """删除助手（级联删除其对话和消息）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM assistants WHERE instance_id = ?", (instance_id,))
            conn.commit()
        logger.debug("Assistant deleted: %s", instance_id)

    def load_assistants(self) -> list[AssistantRecord]:
        """加载全部助手实例，按 sort_order 排序"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT instance_id, type_id, name, sort_order "
                "FROM assistants ORDER BY sort_order"
            ).fetchall()
        return [AssistantRecord(**dict(r)) for r in rows]

    # ── Conversations ──

    def save_conversation(self, conv_id: str, instance_id: str, title: str = "新对话", sort_order: int = 0):
        """新增或更新对话"""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO conversations (conv_id, instance_id, title, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (conv_id, instance_id, title, sort_order),
            )
            conn.commit()
        logger.debug("Conversation saved: %s → %s", title, instance_id)

    def delete_conversation(self, conv_id: str):
        """删除对话（级联删除消息）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM conversations WHERE conv_id = ?", (conv_id,))
            conn.commit()
        logger.debug("Conversation deleted: %s", conv_id)

    def load_conversations(self, instance_id: str | None = None) -> list[ConversationRecord]:
        """加载对话列表，可选按实例过滤"""
        with self._connect() as conn:
            if instance_id:
                rows = conn.execute(
                    "SELECT conv_id, instance_id, title, sort_order "
                    "FROM conversations WHERE instance_id = ? "
                    "ORDER BY sort_order",
                    (instance_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT conv_id, instance_id, title, sort_order "
                    "FROM conversations ORDER BY sort_order"
                ).fetchall()
        return [ConversationRecord(**dict(r)) for r in rows]

    # ── Messages ──

    def save_message(self, conv_id: str, role: str, content: str,
                     image: str | None = None, seq: int = 0):
        """追加一条消息"""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (conv_id, role, content, image, seq) "
                "VALUES (?, ?, ?, ?, ?)",
                (conv_id, role, content, image, seq),
            )
            conn.commit()

    def load_messages(self, conv_id: str) -> list[MessageRecord]:
        """加载指定对话的全部消息，按 seq 排序"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT conv_id, role, content, image, seq "
                "FROM messages WHERE conv_id = ? ORDER BY seq",
                (conv_id,),
            ).fetchall()
        return [MessageRecord(**dict(r)) for r in rows]

    # ── App state ──

    def save_state(self, key: str, value: str):
        """持久化一个应用状态键值对"""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def load_state(self, key: str) -> str | None:
        """读取应用状态"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    # ── Bulk snapshot (startup / restore) ──

    def load_all(self) -> dict:
        """启动时批量加载全部持久化数据

        Returns:
            {
                "assistants": [...],
                "conversations": { instance_id: [...] },
                "active_assistant": str | None,
                "active_conv": str | None,
            }
        """
        assistants = []
        conversations: dict[str, list[dict]] = {}
        active_assistant = None
        active_conv = None

        with self._connect() as conn:
            # 加载助手
            a_rows = conn.execute(
                "SELECT instance_id, type_id, name, sort_order "
                "FROM assistants ORDER BY sort_order"
            ).fetchall()
            for r in a_rows:
                d = dict(r)
                assistants.append(d)
                conversations[d["instance_id"]] = []

            # 加载对话（按实例分组）
            c_rows = conn.execute(
                "SELECT conv_id, instance_id, title, sort_order "
                "FROM conversations ORDER BY sort_order"
            ).fetchall()
            for r in c_rows:
                d = dict(r)
                iid = d.pop("instance_id")
                if iid in conversations:
                    conversations[iid].append(d)

            # 加载应用状态
            state_rows = conn.execute("SELECT key, value FROM app_state").fetchall()
            for r in state_rows:
                if r["key"] == "active_assistant":
                    active_assistant = r["value"]
                elif r["key"] == "active_conv":
                    active_conv = r["value"]

        return {
            "assistants": assistants,
            "conversations": conversations,
            "active_assistant": active_assistant,
            "active_conv": active_conv,
        }

    def save_all(self, assistants: list[dict], conversations: dict[str, list[dict]],
                 active_assistant: str | None, active_conv: str | None):
        """批量持久化完整状态（启动备份 / 退出保存）"""
        with self._connect() as conn:
            # 清空并重写
            conn.execute("DELETE FROM assistants")
            conn.execute("DELETE FROM conversations")
            conn.execute("DELETE FROM app_state")

            for i, a in enumerate(assistants):
                conn.execute(
                    "INSERT INTO assistants (instance_id, type_id, name, sort_order) "
                    "VALUES (?, ?, ?, ?)",
                    (a["instanceId"], a["typeId"], a["name"], i),
                )

            for instance_id, convs in conversations.items():
                for i, c in enumerate(convs):
                    conn.execute(
                        "INSERT INTO conversations (conv_id, instance_id, title, sort_order) "
                        "VALUES (?, ?, ?, ?)",
                        (c["id"], instance_id, c.get("title", "新对话"), i),
                    )

            if active_assistant:
                conn.execute(
                    "INSERT OR REPLACE INTO app_state (key, value) VALUES ('active_assistant', ?)",
                    (active_assistant,),
                )
            if active_conv:
                conn.execute(
                    "INSERT OR REPLACE INTO app_state (key, value) VALUES ('active_conv', ?)",
                    (active_conv,),
                )

            conn.commit()
        logger.info("Full state snapshot saved: %d assistants", len(assistants))

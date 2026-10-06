"""
会话持久化 — SQLite 存储助手实例、对话和消息

沿用 settings.json 的存储目录 (~/.eda_ai_assistant/)，不受浏览器缓存影响。

表结构:
    workspaces    — 工作区 (workspace_id, name, path, sort_order)
    assistants    — 助手实例 (instance_id, type_id, name, sort_order)
    conversations — 对话 (conv_id, instance_id, workspace_id, title, sort_order)
    messages      — 消息 (id, conv_id, role, content, image, seq)
    app_state     — 键值对 (key, value)，存当前活跃工作区/助手/对话

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

from ..constants import app_home

logger = logging.getLogger(__name__)

# 与 config.py 共享同一存储目录（EDA_AI_HOME 可覆盖，见 constants.app_home）
DB_DIR = app_home()
DB_PATH = DB_DIR / "sessions.db"


# 默认工作区：首跑自动创建，永远不可删除，保证「至少有一个可用的工作区」。
DEFAULT_WORKSPACE_ID = "ws_default"
DEFAULT_WORKSPACE_NAME = "默认工作区"


# ══════════════════════════════════════════════════════
#  Data models
# ══════════════════════════════════════════════════════


@dataclass
class WorkspaceRecord:
    workspace_id: str
    name: str
    path: str = ""
    sort_order: int = 0


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
    workspace_id: str = DEFAULT_WORKSPACE_ID
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
        # 用自定义路径时父目录未必存在（测试传 tmp_path）；按 db_path 的父目录建，
        # 而不是永远 mkdir 全局 DB_DIR。
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name         TEXT NOT NULL,
                    path         TEXT NOT NULL DEFAULT '',
                    sort_order   INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS assistants (
                    instance_id TEXT PRIMARY KEY,
                    type_id     TEXT NOT NULL,
                    name        TEXT NOT NULL,
                    sort_order  INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    conv_id      TEXT PRIMARY KEY,
                    instance_id  TEXT NOT NULL,
                    workspace_id TEXT NOT NULL DEFAULT '',
                    title        TEXT DEFAULT '新对话',
                    sort_order   INTEGER DEFAULT 0,
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
            # 迁移旧库：conversations 早期没有 workspace_id 列。
            # 只 ALTER 一次，已有数据回落到默认工作区（''）。
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(conversations)")}
            if "workspace_id" not in cols:
                conn.execute(
                    "ALTER TABLE conversations "
                    "ADD COLUMN workspace_id TEXT NOT NULL DEFAULT ''"
                )
            # 首跑 / 空库：保证默认工作区存在
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM workspaces"
            ).fetchone()
            if not row or row["n"] == 0:
                conn.execute(
                    "INSERT OR IGNORE INTO workspaces (workspace_id, name, path, sort_order) "
                    "VALUES (?, ?, ?, ?)",
                    (DEFAULT_WORKSPACE_ID, DEFAULT_WORKSPACE_NAME, "", 0),
                )
            # 旧库里 '' 工作区的对话 → 归入默认工作区，避免切到默认工作区后看不到历史
            conn.execute(
                "UPDATE conversations SET workspace_id = ? WHERE workspace_id = '' "
                "OR workspace_id IS NULL",
                (DEFAULT_WORKSPACE_ID,),
            )
            conn.commit()
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

    # ── Workspaces ──

    def save_workspace(self, workspace_id: str, name: str, path: str = "", sort_order: int = 0):
        """新增或更新工作区。

        工作区 = 一个工程上下文：名字 + 可选的本地目录。对话按工作区隔离，
        这样「A 项目的 BOM 讨论」不会和「B 项目」混在一起。
        """
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO workspaces (workspace_id, name, path, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (workspace_id, name, path or "", sort_order),
            )
            conn.commit()
        logger.debug("Workspace saved: %s (%s)", name, workspace_id)

    def delete_workspace(self, workspace_id: str):
        """删除工作区，并把其对话迁移到默认工作区（不级联删对话）。"""
        if workspace_id == DEFAULT_WORKSPACE_ID:
            raise ValueError("默认工作区不可删除")
        with self._connect() as conn:
            conn.execute("DELETE FROM workspaces WHERE workspace_id = ?", (workspace_id,))
            conn.execute(
                "UPDATE conversations SET workspace_id = ? WHERE workspace_id = ?",
                (DEFAULT_WORKSPACE_ID, workspace_id),
            )
            conn.commit()
        logger.debug("Workspace deleted: %s", workspace_id)

    def load_workspaces(self) -> list[WorkspaceRecord]:
        """加载全部工作区，按 sort_order 排序（默认工作区永远在最前）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT workspace_id, name, path, sort_order "
                "FROM workspaces ORDER BY sort_order, name"
            ).fetchall()
        return [WorkspaceRecord(**dict(r)) for r in rows]

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

    def save_conversation(self, conv_id: str, instance_id: str, title: str = "新对话",
                          sort_order: int = 0, workspace_id: str = ""):
        """新增或更新对话。

        workspace_id 留空时：新建落到默认工作区，更新则保留该对话原有的工作区
        —— 否则一次「重命名标题」就会把对话悄悄搬回默认工作区。
        """
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT workspace_id FROM conversations WHERE conv_id = ?", (conv_id,)
            ).fetchone()
            if existing is None:
                ws = workspace_id or DEFAULT_WORKSPACE_ID
                conn.execute(
                    "INSERT INTO conversations "
                    "(conv_id, instance_id, workspace_id, title, sort_order) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (conv_id, instance_id, ws, title, sort_order),
                )
            else:
                ws = workspace_id or (existing["workspace_id"] or DEFAULT_WORKSPACE_ID)
                conn.execute(
                    "UPDATE conversations SET instance_id = ?, workspace_id = ?, "
                    "title = ?, sort_order = ? WHERE conv_id = ?",
                    (instance_id, ws, title, sort_order, conv_id),
                )
            conn.commit()
        logger.debug("Conversation saved: %s → %s (%s)", title, instance_id, ws)

    def delete_conversation(self, conv_id: str):
        """删除对话（级联删除消息）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM conversations WHERE conv_id = ?", (conv_id,))
            conn.commit()
        logger.debug("Conversation deleted: %s", conv_id)

    def load_conversations(self, instance_id: str | None = None,
                           workspace_id: str | None = None) -> list[ConversationRecord]:
        """加载对话列表，可选按实例 / 工作区过滤"""
        sql = ("SELECT conv_id, instance_id, workspace_id, title, sort_order "
               "FROM conversations")
        clauses, params = [], []
        if instance_id:
            clauses.append("instance_id = ?")
            params.append(instance_id)
        if workspace_id:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY sort_order"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
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
                "workspaces": [...],
                "assistants": [...],
                "conversations": { instance_id: [...] },
                "active_workspace": str | None,
                "active_assistant": str | None,
                "active_conv": str | None,
            }
        """
        workspaces: list[dict] = []
        assistants = []
        conversations: dict[str, list[dict]] = {}
        active_workspace = None
        active_assistant = None
        active_conv = None

        with self._connect() as conn:
            # 加载工作区
            w_rows = conn.execute(
                "SELECT workspace_id, name, path, sort_order "
                "FROM workspaces ORDER BY sort_order, name"
            ).fetchall()
            for r in w_rows:
                workspaces.append(dict(r))

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
                "SELECT conv_id, instance_id, workspace_id, title, sort_order "
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
                if r["key"] == "active_workspace":
                    active_workspace = r["value"]
                elif r["key"] == "active_assistant":
                    active_assistant = r["value"]
                elif r["key"] == "active_conv":
                    active_conv = r["value"]

        return {
            "workspaces": workspaces,
            "assistants": assistants,
            "conversations": conversations,
            "active_workspace": active_workspace,
            "active_assistant": active_assistant,
            "active_conv": active_conv,
        }

    def save_all(self, assistants: list[dict], conversations: dict[str, list[dict]],
                 active_assistant: str | None, active_conv: str | None,
                 workspaces: list[dict] | None = None,
                 active_workspace: str | None = None):
        """批量持久化完整状态（启动备份 / 退出保存）"""
        with self._connect() as conn:
            # 清空并重写
            conn.execute("DELETE FROM assistants")
            conn.execute("DELETE FROM conversations")
            conn.execute("DELETE FROM app_state")

            for i, w in enumerate(workspaces or []):
                conn.execute(
                    "INSERT INTO workspaces (workspace_id, name, path, sort_order) "
                    "VALUES (?, ?, ?, ?)",
                    (w["workspace_id"], w.get("name", "工作区"), w.get("path", ""), i),
                )

            for i, a in enumerate(assistants):
                conn.execute(
                    "INSERT INTO assistants (instance_id, type_id, name, sort_order) "
                    "VALUES (?, ?, ?, ?)",
                    (a["instanceId"], a["typeId"], a["name"], i),
                )

            for instance_id, convs in conversations.items():
                for i, c in enumerate(convs):
                    conn.execute(
                        "INSERT INTO conversations "
                        "(conv_id, instance_id, workspace_id, title, sort_order) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (c["id"], instance_id,
                         c.get("workspaceId") or DEFAULT_WORKSPACE_ID,
                         c.get("title", "新对话"), i),
                    )

            if active_workspace:
                conn.execute(
                    "INSERT OR REPLACE INTO app_state (key, value) "
                    "VALUES ('active_workspace', ?)",
                    (active_workspace,),
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

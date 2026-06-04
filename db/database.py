import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "hermes.db")


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent           TEXT    NOT NULL,
                    role            TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                    content         TEXT    NOT NULL,
                    timestamp       TEXT    NOT NULL,
                    session_id      TEXT,
                    conversation_id TEXT REFERENCES conversations(id)
                )
            """)
            # Additive migrations for existing databases
            for col, definition in [
                ("session_id",      "TEXT"),
                ("conversation_id", "TEXT REFERENCES conversations(id)"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {definition}")
                except Exception:
                    pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    agent      TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_message(
        self,
        agent: str,
        role: str,
        content: str,
        session_id: str,
        conversation_id: str = None,
    ):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (agent, role, content, timestamp, session_id, conversation_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (agent, role, content, datetime.utcnow().isoformat(), session_id, conversation_id),
            )
            conn.commit()

    def get_history(self, agent: str, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, agent, role, content, timestamp FROM messages "
                "WHERE agent = ? ORDER BY id DESC LIMIT ?",
                (agent, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_history_as_messages(self, agent: str, session_id: str, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages "
                "WHERE agent = ? AND session_id = ? ORDER BY id DESC LIMIT ?",
                (agent, session_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def clear_history(self, agent: str, session_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE agent = ? AND session_id = ?",
                (agent, session_id),
            )
            conn.commit()
        return cursor.rowcount

    def create_conversation(self, id: str, title: str, agent: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations (id, title, agent, created_at) VALUES (?, ?, ?, ?)",
                (id, title[:40], agent, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_conversations(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.agent, c.created_at,
                       COUNT(m.id) AS msg_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation_messages(self, conv_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM messages "
                "WHERE conversation_id = ? ORDER BY id ASC",
                (conv_id,),
            ).fetchall()
        return [dict(row) for row in rows]

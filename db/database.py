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
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent      TEXT    NOT NULL,
                    role       TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                    content    TEXT    NOT NULL,
                    timestamp  TEXT    NOT NULL,
                    session_id TEXT
                )
            """)
            # Aditiva: adiciona session_id em bancos existentes sem a coluna
            try:
                conn.execute("ALTER TABLE messages ADD COLUMN session_id TEXT")
            except Exception:
                pass
            conn.commit()

    def save_message(self, agent: str, role: str, content: str, session_id: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (agent, role, content, timestamp, session_id) VALUES (?, ?, ?, ?, ?)",
                (agent, role, content, datetime.utcnow().isoformat(), session_id),
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

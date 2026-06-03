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
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent     TEXT    NOT NULL,
                    role      TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                    content   TEXT    NOT NULL,
                    timestamp TEXT    NOT NULL
                )
            """)
            conn.commit()

    def save_message(self, agent: str, role: str, content: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (agent, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (agent, role, content, datetime.utcnow().isoformat()),
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

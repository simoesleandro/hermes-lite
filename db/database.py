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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    status     TEXT NOT NULL DEFAULT 'inbox'
                               CHECK(status IN ('inbox', 'today', 'week', 'done')),
                    priority   TEXT NOT NULL DEFAULT 'medium'
                               CHECK(priority IN ('low', 'medium', 'high')),
                    notes      TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_docs (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    filename   TEXT,
                    source     TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id      TEXT NOT NULL REFERENCES knowledge_docs(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content     TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    content,
                    doc_id UNINDEXED,
                    content='knowledge_chunks',
                    content_rowid='id'
                )
            """)
            for kb_trigger in (
                """
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_ai AFTER INSERT ON knowledge_chunks BEGIN
                    INSERT INTO knowledge_fts(rowid, content, doc_id)
                    VALUES (new.id, new.content, new.doc_id);
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_ad AFTER DELETE ON knowledge_chunks BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, content, doc_id)
                    VALUES ('delete', old.id, old.content, old.doc_id);
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS knowledge_fts_au AFTER UPDATE ON knowledge_chunks BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, content, doc_id)
                    VALUES ('delete', old.id, old.content, old.doc_id);
                    INSERT INTO knowledge_fts(rowid, content, doc_id)
                    VALUES (new.id, new.content, new.doc_id);
                END
                """,
            ):
                try:
                    conn.execute(kb_trigger)
                except Exception:
                    pass
            try:
                kb_fts_count = conn.execute("SELECT COUNT(*) FROM knowledge_fts").fetchone()[0]
                chunk_count = conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
                if chunk_count > 0 and kb_fts_count == 0:
                    conn.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")
            except Exception:
                pass
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content,
                    conversation_id UNINDEXED,
                    agent UNINDEXED,
                    content='messages',
                    content_rowid='id'
                )
            """)
            for trigger_sql in (
                """
                CREATE TRIGGER IF NOT EXISTS messages_fts_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content, conversation_id, agent)
                    VALUES (new.id, new.content, new.conversation_id, new.agent);
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS messages_fts_ad AFTER DELETE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content, conversation_id, agent)
                    VALUES ('delete', old.id, old.content, old.conversation_id, old.agent);
                END
                """,
                """
                CREATE TRIGGER IF NOT EXISTS messages_fts_au AFTER UPDATE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content, conversation_id, agent)
                    VALUES ('delete', old.id, old.content, old.conversation_id, old.agent);
                    INSERT INTO messages_fts(rowid, content, conversation_id, agent)
                    VALUES (new.id, new.content, new.conversation_id, new.agent);
                END
                """,
            ):
                try:
                    conn.execute(trigger_sql)
                except Exception:
                    pass
            try:
                fts_count = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
                if fts_count == 0:
                    conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
            except Exception:
                pass
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

    def get_conversation_history_as_messages(
        self, agent: str, conversation_id: str, limit: int = 20,
    ) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages "
                "WHERE agent = ? AND conversation_id = ? ORDER BY id ASC",
                (agent, conversation_id),
            ).fetchall()
        msgs = [{"role": row["role"], "content": row["content"]} for row in rows]
        if len(msgs) > limit:
            return msgs[-limit:]
        return msgs

    def get_cross_chat_memory(
        self,
        agent: str,
        exclude_conv_id: str | None = None,
        limit: int = 5,
    ) -> list[str]:
        with self._connect() as conn:
            if exclude_conv_id:
                rows = conn.execute(
                    """
                    SELECT content FROM messages
                    WHERE agent = ? AND role = 'user'
                      AND conversation_id IS NOT NULL
                      AND conversation_id != ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (agent, exclude_conv_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT content FROM messages
                    WHERE agent = ? AND role = 'user'
                      AND conversation_id IS NOT NULL
                    ORDER BY id DESC LIMIT ?
                    """,
                    (agent, limit),
                ).fetchall()
        snippets = [row["content"].strip()[:240] for row in rows if row["content"].strip()]
        snippets.reverse()
        return snippets

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

    def get_conversation(self, conv_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, agent, created_at FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_conversation(self, conv_id: str, title: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (title[:80], conv_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def delete_conversation(self, conv_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
        return cur.rowcount > 0

    def search_conversations(self, query: str, agent: str | None = None, limit: int = 30) -> list[dict]:
        fts_query = " ".join(f'"{w}"' for w in query.split() if w.strip())
        if not fts_query:
            return []
        with self._connect() as conn:
            if agent:
                rows = conn.execute(
                    """
                    SELECT DISTINCT c.id, c.title, c.agent, c.created_at,
                           snippet(messages_fts, 0, '**', '**', '…', 20) AS snippet
                    FROM messages_fts f
                    JOIN messages m ON m.id = f.rowid
                    JOIN conversations c ON c.id = m.conversation_id
                    WHERE messages_fts MATCH ? AND c.agent = ?
                    ORDER BY c.created_at DESC
                    LIMIT ?
                    """,
                    (fts_query, agent, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT c.id, c.title, c.agent, c.created_at,
                           snippet(messages_fts, 0, '**', '**', '…', 20) AS snippet
                    FROM messages_fts f
                    JOIN messages m ON m.id = f.rowid
                    JOIN conversations c ON c.id = m.conversation_id
                    WHERE messages_fts MATCH ?
                    ORDER BY c.created_at DESC
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    # ── GTD tasks ─────────────────────────────────────────────────────────────

    def create_task(
        self,
        task_id: str,
        title: str,
        status: str = "inbox",
        priority: str = "medium",
        notes: str | None = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, title, status, priority, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, title.strip()[:200], status, priority, notes, now, now),
            )
            conn.commit()

    def list_tasks(
        self,
        status: str | None = None,
        include_done: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT id, title, status, priority, notes, created_at, updated_at
                    FROM tasks WHERE status = ?
                    ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                             updated_at DESC LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            elif include_done:
                rows = conn.execute(
                    """
                    SELECT id, title, status, priority, notes, created_at, updated_at
                    FROM tasks ORDER BY updated_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, title, status, priority, notes, created_at, updated_at
                    FROM tasks WHERE status != 'done'
                    ORDER BY CASE status WHEN 'today' THEN 0 WHEN 'week' THEN 1 ELSE 2 END,
                             CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                             updated_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_task(self, task_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, status, priority, notes, created_at, updated_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def find_open_task(self, fragment: str) -> dict | None:
        frag = fragment.strip()
        if not frag:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, status, priority, notes, created_at, updated_at
                FROM tasks
                WHERE status != 'done' AND LOWER(title) LIKE LOWER(?)
                ORDER BY updated_at DESC LIMIT 1
                """,
                (f"%{frag}%",),
            ).fetchone()
        return dict(row) if row else None

    def update_task(
        self,
        task_id: str,
        title: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        notes: str | None = None,
    ) -> bool:
        fields: list[str] = []
        values: list = []
        if title is not None:
            fields.append("title = ?")
            values.append(title.strip()[:200])
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if priority is not None:
            fields.append("priority = ?")
            values.append(priority)
        if notes is not None:
            fields.append("notes = ?")
            values.append(notes)
        if not fields:
            return False
        fields.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(task_id)
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
        return cur.rowcount > 0

    def complete_task(self, task_id: str) -> bool:
        return self.update_task(task_id, status="done")

    def delete_task(self, task_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return cur.rowcount > 0

    def tasks_summary(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks WHERE status != 'done' GROUP BY status",
            ).fetchall()
        counts = {row["status"]: row["n"] for row in rows}
        return {
            "today": counts.get("today", 0),
            "week": counts.get("week", 0),
            "inbox": counts.get("inbox", 0),
            "total_open": sum(counts.values()),
        }

    def format_tasks_context(self) -> str:
        sections = []
        labels = {"today": "Hoje", "week": "Esta semana", "inbox": "Inbox"}
        for status in ("today", "week", "inbox"):
            tasks = self.list_tasks(status=status, limit=15)
            if not tasks:
                continue
            lines = [f"=== {labels[status].upper()} ==="]
            for i, t in enumerate(tasks, 1):
                pri = t.get("priority", "medium")
                mark = "!" if pri == "high" else ""
                lines.append(f"{i}. [{pri}{mark}] {t['title']}")
            sections.append("\n".join(lines))
        if not sections:
            return "Nenhuma tarefa aberta no GTD."
        return "\n\n".join(sections)

    # ── Knowledge base (RAG-lite FTS) ─────────────────────────────────────────

    def ingest_knowledge_doc(
        self,
        doc_id: str,
        title: str,
        text: str,
        filename: str | None = None,
        source: str | None = None,
    ) -> int:
        from services.knowledge import chunk_text

        now = datetime.utcnow().isoformat()
        chunks = chunk_text(text)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO knowledge_docs (id, title, filename, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (doc_id, title[:120], filename, source, now),
            )
            for i, chunk in enumerate(chunks):
                conn.execute(
                    "INSERT INTO knowledge_chunks (doc_id, chunk_index, content) VALUES (?, ?, ?)",
                    (doc_id, i, chunk),
                )
            conn.commit()
        return len(chunks)

    def list_knowledge_docs(self, limit: int = 30) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.id, d.title, d.filename, d.source, d.created_at,
                       COUNT(c.id) AS chunks
                FROM knowledge_docs d
                LEFT JOIN knowledge_chunks c ON c.doc_id = d.id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_knowledge_doc(self, doc_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
            cur = conn.execute("DELETE FROM knowledge_docs WHERE id = ?", (doc_id,))
            conn.commit()
        return cur.rowcount > 0

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict]:
        fts_query = " ".join(f'"{w}"' for w in query.split() if w.strip())
        if not fts_query:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.id AS doc_id, d.title, d.filename,
                       snippet(knowledge_fts, 0, '**', '**', '…', 32) AS snippet,
                       c.chunk_index
                FROM knowledge_fts f
                JOIN knowledge_chunks c ON c.id = f.rowid
                JOIN knowledge_docs d ON d.id = c.doc_id
                WHERE knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def format_knowledge_context(self, query: str, limit: int = 4) -> str:
        hits = self.search_knowledge(query, limit=limit)
        if not hits:
            return ""
        lines = ["=== TRECHOS DA BASE DE CONHECIMENTO (use se relevante) ==="]
        for h in hits:
            title = h.get("title") or h.get("filename") or "doc"
            snip = (h.get("snippet") or "").replace("**", "")
            lines.append(f"• [{title}] {snip}")
        return "\n".join(lines)

    def export_conversation_markdown(self, conv_id: str) -> str:
        meta = self.get_conversation(conv_id)
        if not meta:
            return ""
        messages = self.get_conversation_messages(conv_id)
        lines = [
            f"# {meta['title']}",
            "",
            f"- **Agente:** {meta['agent']}",
            f"- **Criada em:** {meta['created_at']}",
            "",
            "---",
            "",
        ]
        for msg in messages:
            role = "Usuário" if msg["role"] == "user" else "Assistente"
            ts = msg.get("timestamp", "")
            lines.append(f"## {role}" + (f" ({ts})" if ts else ""))
            lines.append("")
            lines.append(msg["content"])
            lines.append("")
        return "\n".join(lines)

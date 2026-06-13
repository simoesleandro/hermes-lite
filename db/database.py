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
                CREATE TABLE IF NOT EXISTS user_facts (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    category   TEXT,
                    status     TEXT NOT NULL DEFAULT 'confirmed',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            try:
                conn.execute(
                    "ALTER TABLE user_facts ADD COLUMN status TEXT NOT NULL DEFAULT 'confirmed'"
                )
            except Exception:
                pass
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id         TEXT PRIMARY KEY,
                    type       TEXT NOT NULL,
                    status     TEXT NOT NULL DEFAULT 'pending'
                               CHECK(status IN ('pending', 'running', 'done', 'failed')),
                    input_json TEXT,
                    output_json TEXT,
                    error      TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS github_radar_digests (
                    id         TEXT PRIMARY KEY,
                    date       TEXT NOT NULL UNIQUE,
                    markdown   TEXT NOT NULL,
                    picks_json TEXT,
                    file_path  TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS github_radar_seen (
                    full_name  TEXT PRIMARY KEY,
                    score      REAL,
                    first_seen TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sentinela_auto_workflows (
                    alert_key   TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    fornecedor  TEXT,
                    created_at  TEXT NOT NULL
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
                    content     TEXT NOT NULL,
                    embedding   TEXT
                )
            """)
            try:
                conn.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding TEXT")
            except Exception:
                pass
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

    # ── User facts (memória estruturada) ──────────────────────────────────────

    def list_facts(
        self,
        category: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        with self._connect() as conn:
            clauses: list[str] = []
            params: list = []
            if category:
                clauses.append("category = ?")
                params.append(category)
            if status:
                clauses.append("status = ?")
                params.append(status)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            params.append(limit)
            rows = conn.execute(
                f"SELECT key, value, category, status, updated_at FROM user_facts "
                f"{where} ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_fact(
        self,
        key: str,
        value: str,
        category: str | None = None,
        status: str | None = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        key = key.strip()[:80]
        final_status = status or ("pending" if category == "auto" else "confirmed")
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT status FROM user_facts WHERE key = ?", (key,)
            ).fetchone()
            if existing and existing["status"] == "confirmed" and final_status == "pending":
                final_status = "confirmed"
            conn.execute(
                """
                INSERT INTO user_facts (key, value, category, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = COALESCE(excluded.category, user_facts.category),
                    status = CASE
                        WHEN user_facts.status = 'confirmed' THEN user_facts.status
                        ELSE excluded.status
                    END,
                    updated_at = excluded.updated_at
                """,
                (key, value.strip()[:500], category, final_status, now, now),
            )
            conn.commit()

    def approve_fact(self, key: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE user_facts SET status = 'confirmed', updated_at = ? WHERE key = ?",
                (datetime.utcnow().isoformat(), key.strip()),
            )
            conn.commit()
        return cur.rowcount > 0

    def delete_fact(self, key: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM user_facts WHERE key = ?", (key.strip(),))
            conn.commit()
        return cur.rowcount > 0

    def find_fact(self, fragment: str) -> dict | None:
        frag = fragment.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT key, value, category, status FROM user_facts WHERE lower(key) = ?",
                (frag,),
            ).fetchone()
            if row:
                return dict(row)
            row = conn.execute(
                "SELECT key, value, category FROM user_facts WHERE lower(key) LIKE ? LIMIT 1",
                (f"%{frag}%",),
            ).fetchone()
        return dict(row) if row else None

    def format_facts_context(self, limit: int = 20) -> str:
        facts = self.list_facts(limit=limit)
        if not facts:
            return ""
        lines = ["=== FATOS SOBRE O USUÁRIO (memória persistente — use se relevante) ==="]
        for f in reversed(facts):
            cat = f.get("category")
            prefix = f"[{cat}] " if cat else ""
            lines.append(f"• {prefix}{f['key']}: {f['value']}")
        return "\n".join(lines)

    # ── Workflows duráveis ────────────────────────────────────────────────────

    def create_workflow(self, wf_id: str, wf_type: str, input_data: dict) -> None:
        import json as _json
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workflows (id, type, status, input_json, created_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?, ?)
                """,
                (wf_id, wf_type, _json.dumps(input_data, ensure_ascii=False), now, now),
            )
            conn.commit()

    def get_workflow(self, wf_id: str) -> dict | None:
        import json as _json
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for field in ("input_json", "output_json"):
            if d.get(field):
                try:
                    d[field] = _json.loads(d[field])
                except Exception:
                    pass
        return d

    def update_workflow(
        self,
        wf_id: str,
        status: str | None = None,
        output_json: dict | None = None,
        error: str | None = None,
    ) -> None:
        import json as _json
        now = datetime.utcnow().isoformat()
        sets = ["updated_at = ?"]
        vals: list = [now]
        if status:
            sets.append("status = ?")
            vals.append(status)
        if output_json is not None:
            sets.append("output_json = ?")
            vals.append(_json.dumps(output_json, ensure_ascii=False))
        if error is not None:
            sets.append("error = ?")
            vals.append(error)
        vals.append(wf_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE workflows SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()

    def list_workflows(self, limit: int = 20) -> list[dict]:
        import json as _json
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, type, status, output_json, error, created_at, updated_at "
                "FROM workflows ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            if d.get("output_json"):
                try:
                    d["output_json"] = _json.loads(d["output_json"])
                except Exception:
                    pass
            out.append(d)
        return out

    # ── Sentinela auto-workflow dedup ─────────────────────────────────────────

    def has_sentinela_auto_workflow(self, alert_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sentinela_auto_workflows WHERE alert_key = ?",
                (alert_key,),
            ).fetchone()
        return row is not None

    def save_sentinela_auto_workflow(
        self,
        alert_key: str,
        workflow_id: str,
        fornecedor: str | None = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sentinela_auto_workflows
                (alert_key, workflow_id, fornecedor, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (alert_key, workflow_id, fornecedor, now),
            )
            conn.commit()

    def list_sentinela_auto_workflows(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT alert_key, workflow_id, fornecedor, created_at
                FROM sentinela_auto_workflows ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── GitHub Radar ──────────────────────────────────────────────────────────

    def save_github_digest(
        self,
        digest_id: str,
        date: str,
        markdown: str,
        picks: list[dict],
        file_path: str,
    ) -> None:
        import json as _json
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO github_radar_digests (id, date, markdown, picks_json, file_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    id = excluded.id,
                    markdown = excluded.markdown,
                    picks_json = excluded.picks_json,
                    file_path = excluded.file_path,
                    created_at = excluded.created_at
                """,
                (digest_id, date, markdown, _json.dumps(picks, ensure_ascii=False), file_path, now),
            )
            conn.commit()

    def get_github_digest_by_date(self, date: str) -> dict | None:
        return self._parse_github_digest_row(
            self._fetch_github_digest("date = ?", (date,))
        )

    def get_latest_github_digest(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, date, markdown, picks_json, file_path, created_at "
                "FROM github_radar_digests ORDER BY date DESC LIMIT 1",
            ).fetchone()
        return self._parse_github_digest_row(row)

    def list_github_digests(self, limit: int = 14) -> list[dict]:
        import json as _json
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, date, picks_json, file_path, created_at "
                "FROM github_radar_digests ORDER BY date DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            if d.get("picks_json"):
                try:
                    d["picks"] = _json.loads(d["picks_json"])
                except Exception:
                    d["picks"] = []
            out.append(d)
        return out

    def _fetch_github_digest(self, where_sql: str, params: tuple):
        with self._connect() as conn:
            return conn.execute(
                f"SELECT id, date, markdown, picks_json, file_path, created_at "
                f"FROM github_radar_digests WHERE {where_sql}",
                params,
            ).fetchone()

    def _parse_github_digest_row(self, row) -> dict | None:
        if not row:
            return None
        import json as _json
        d = dict(row)
        if d.get("picks_json"):
            try:
                d["picks"] = _json.loads(d["picks_json"])
            except Exception:
                d["picks"] = []
        return d

    def mark_github_seen(self, full_name: str, score: float | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO github_radar_seen (full_name, score, first_seen)
                VALUES (?, ?, ?)
                ON CONFLICT(full_name) DO UPDATE SET score = COALESCE(excluded.score, github_radar_seen.score)
                """,
                (full_name, score, now),
            )
            conn.commit()

    def list_github_seen(self, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT full_name, score, first_seen FROM github_radar_seen ORDER BY first_seen DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

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
        from services.embeddings import embed_text, embedding_to_json, embeddings_enabled

        now = datetime.utcnow().isoformat()
        chunks = chunk_text(text)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO knowledge_docs (id, title, filename, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (doc_id, title[:120], filename, source, now),
            )
            for i, chunk in enumerate(chunks):
                cur = conn.execute(
                    "INSERT INTO knowledge_chunks (doc_id, chunk_index, content) VALUES (?, ?, ?)",
                    (doc_id, i, chunk),
                )
                if embeddings_enabled():
                    emb = embed_text(chunk)
                    if emb:
                        conn.execute(
                            "UPDATE knowledge_chunks SET embedding = ? WHERE id = ?",
                            (embedding_to_json(emb), cur.lastrowid),
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

    def search_knowledge_semantic(self, query: str, limit: int = 5) -> list[dict]:
        from services.embeddings import (
            cosine_similarity,
            embed_query,
            embedding_from_json,
            embeddings_enabled,
        )

        if not embeddings_enabled():
            return []
        q_emb = embed_query(query)
        if not q_emb:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.doc_id, c.chunk_index, c.content, c.embedding,
                       d.title, d.filename
                FROM knowledge_chunks c
                JOIN knowledge_docs d ON d.id = c.doc_id
                WHERE c.embedding IS NOT NULL
                """
            ).fetchall()
        scored: list[tuple[float, dict]] = []
        for row in rows:
            emb = embedding_from_json(row["embedding"])
            if not emb:
                continue
            sim = cosine_similarity(q_emb, emb)
            content = row["content"] or ""
            snip = content if len(content) <= 200 else content[:200] + "…"
            scored.append((
                sim,
                {
                    "doc_id": row["doc_id"],
                    "title": row["title"],
                    "filename": row["filename"],
                    "snippet": snip,
                    "chunk_index": row["chunk_index"],
                },
            ))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def search_knowledge_hybrid(self, query: str, limit: int = 5) -> list[dict]:
        from services.embeddings import embeddings_enabled

        fts_hits = self.search_knowledge(query, limit=limit)
        if not embeddings_enabled():
            return fts_hits
        sem_hits = self.search_knowledge_semantic(query, limit=limit)
        seen: set[tuple[str, int | None]] = set()
        merged: list[dict] = []
        for hit in sem_hits + fts_hits:
            key = (hit["doc_id"], hit.get("chunk_index"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
            if len(merged) >= limit:
                break
        return merged

    def format_knowledge_context(self, query: str, limit: int = 4) -> str:
        hits = self.search_knowledge_hybrid(query, limit=limit)
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

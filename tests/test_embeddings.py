import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.embeddings import cosine_similarity, embedding_to_json, embedding_from_json


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "emb.db"))


def test_cosine_similarity():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(1.0)
    assert cosine_similarity(a, c) == pytest.approx(0.0)


def test_embedding_json_roundtrip():
    vec = [0.1, 0.2, 0.3]
    raw = embedding_to_json(vec)
    assert embedding_from_json(raw) == vec


def test_semantic_search_with_mock(db, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_EMBEDDINGS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_embed(text, task_type="retrieval_document"):
        if "python" in text.lower():
            return [1.0, 0.0]
        if "query python" in text.lower():
            return [1.0, 0.0]
        return [0.0, 1.0]

    import services.embeddings as emb

    monkeypatch.setattr(emb, "embed_text", fake_embed)
    monkeypatch.setattr(emb, "embed_query", lambda q: fake_embed(q, "retrieval_query"))

    doc_id = str(uuid.uuid4())
    with db._connect() as conn:
        conn.execute(
            "INSERT INTO knowledge_docs (id, title, created_at) VALUES (?, ?, ?)",
            (doc_id, "Doc", "2026-01-01"),
        )
        conn.execute(
            "INSERT INTO knowledge_chunks (doc_id, chunk_index, content, embedding) VALUES (?, ?, ?, ?)",
            (doc_id, 0, "Python programming language", embedding_to_json([1.0, 0.0])),
        )
        conn.execute(
            "INSERT INTO knowledge_chunks (doc_id, chunk_index, content, embedding) VALUES (?, ?, ?, ?)",
            (doc_id, 1, "Java coffee beans", embedding_to_json([0.0, 1.0])),
        )
        conn.commit()

    hits = db.search_knowledge_semantic("query python", limit=2)
    assert hits
    assert "Python" in hits[0]["snippet"]

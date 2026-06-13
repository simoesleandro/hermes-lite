import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.knowledge import chunk_text


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "kb.db"))


def test_chunk_text_splits_long():
    text = "A" * 2000
    chunks = chunk_text(text, size=500, overlap=50)
    assert len(chunks) >= 3
    assert all(len(c) <= 500 for c in chunks)


def test_ingest_and_search(db):
    doc_id = str(uuid.uuid4())
    text = "Hermes Lite usa Flask e SQLite para RAG com FTS5 full text search."
    n = db.ingest_knowledge_doc(doc_id, "Hermes doc", text, filename="hermes.txt")
    assert n >= 1
    results = db.search_knowledge("FTS5 Flask")
    assert len(results) >= 1
    assert results[0]["doc_id"] == doc_id


def test_format_knowledge_context(db):
    doc_id = str(uuid.uuid4())
    db.ingest_knowledge_doc(doc_id, "FIAP", "Leandro ingressa na FIAP em 2026 no curso ADS.")
    ctx = db.format_knowledge_context("FIAP ADS")
    assert "BASE DE CONHECIMENTO" in ctx
    assert "FIAP" in ctx


def test_delete_knowledge_doc(db):
    doc_id = str(uuid.uuid4())
    db.ingest_knowledge_doc(doc_id, "Temp", "conteúdo temporário xyz")
    assert db.delete_knowledge_doc(doc_id)
    assert db.search_knowledge("temporário") == []


def test_list_knowledge_docs(db):
    db.ingest_knowledge_doc(str(uuid.uuid4()), "Doc A", "alpha")
    db.ingest_knowledge_doc(str(uuid.uuid4()), "Doc B", "beta")
    docs = db.list_knowledge_docs()
    assert len(docs) == 2

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import Database
from services.knowledge_ingest import auto_pdf_enabled, ingest_pdf, should_persist_pdf


@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "kb.db"))


def test_auto_pdf_default_on(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_AUTO_PDF", raising=False)
    assert auto_pdf_enabled() is True


def test_should_persist_pdf(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_AUTO_PDF", "1")
    assert should_persist_pdf(form_persist=False) is True
    assert should_persist_pdf(form_persist=False) is True
    monkeypatch.setenv("KNOWLEDGE_AUTO_PDF", "0")
    assert should_persist_pdf(form_persist=False) is False
    assert should_persist_pdf(form_persist=True) is True


def test_ingest_pdf(db):
    doc_id, chunks = ingest_pdf(db, "Texto longo " * 50, "doc.pdf", source="pdf")
    assert doc_id
    assert chunks >= 1
    docs = db.list_knowledge_docs()
    assert len(docs) == 1

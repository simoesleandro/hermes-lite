"""Helpers para ingestão automática de PDFs na base de conhecimento."""

from __future__ import annotations

import os
import uuid

from db.database import Database


def auto_pdf_enabled() -> bool:
    return os.getenv("KNOWLEDGE_AUTO_PDF", "1") == "1"


def telegram_persist_enabled() -> bool:
    if os.getenv("TELEGRAM_KNOWLEDGE_PERSIST", "").lower() in ("1", "true", "yes"):
        return True
    return auto_pdf_enabled()


def should_persist_pdf(*, form_persist: bool = False) -> bool:
    return form_persist or auto_pdf_enabled()


def ingest_pdf(
    db: Database,
    text: str,
    filename: str,
    source: str = "pdf",
) -> tuple[str | None, int]:
    if not text.strip():
        return None, 0
    doc_id = str(uuid.uuid4())
    chunks = db.ingest_knowledge_doc(
        doc_id,
        title=filename,
        text=text,
        filename=filename,
        source=source,
    )
    return doc_id, chunks

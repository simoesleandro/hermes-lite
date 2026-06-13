"""Processamento de mídia recebida no Telegram (PDF, fotos)."""

import base64
import logging
import os
import uuid

from services.pdf_extract import extract_pdf_text
from services.telegram_client import download_file_bytes

logger = logging.getLogger("hermes.telegram_media")

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _largest_photo_file_id(photos: list[dict]) -> str | None:
    if not photos:
        return None
    return max(photos, key=lambda p: p.get("file_size") or p.get("width") or 0).get("file_id")


def parse_pdf_message(message: dict) -> dict | None:
    """Extrai PDF de message.document. Retorna dict pronto ou {error}."""
    doc = message.get("document")
    if not doc:
        return None
    mime = (doc.get("mime_type") or "").lower()
    fname = doc.get("file_name") or "document.pdf"
    if not (mime == "application/pdf" or fname.lower().endswith(".pdf")):
        return {"error": "Envie um arquivo PDF (.pdf)."}
    size = doc.get("file_size") or 0
    if size > MAX_PDF_BYTES:
        return {"error": "PDF muito grande (máx. 10MB)."}
    file_id = doc.get("file_id")
    if not file_id:
        return {"error": "file_id ausente no documento."}
    try:
        raw = download_file_bytes(file_id)
    except Exception as exc:
        logger.exception("download PDF")
        return {"error": f"Falha ao baixar PDF: {exc}"}
    if len(raw) > MAX_PDF_BYTES:
        return {"error": "PDF muito grande (máx. 10MB)."}
    result = extract_pdf_text(raw, filename=fname)
    if result.get("error"):
        return result
    if not (result.get("text") or "").strip():
        return {"error": "Não foi possível extrair texto do PDF (pode ser escaneado)."}
    return result


def parse_photo_message(message: dict) -> dict | None:
    """Extrai foto de message.photo. Retorna {image_b64, mime, filename} ou {error}."""
    photos = message.get("photo")
    if not photos:
        return None
    file_id = _largest_photo_file_id(photos)
    if not file_id:
        return {"error": "Foto inválida."}
    try:
        raw = download_file_bytes(file_id)
    except Exception as exc:
        logger.exception("download foto")
        return {"error": f"Falha ao baixar foto: {exc}"}
    if len(raw) > MAX_IMAGE_BYTES:
        return {"error": "Imagem muito grande (máx. 8MB)."}
    mime = "image/jpeg"
    b64 = base64.b64encode(raw).decode()
    return {
        "image_b64": b64,
        "mime": mime,
        "filename": f"telegram-{uuid.uuid4().hex[:8]}.jpg",
    }


def default_caption(message: dict, kind: str) -> str:
    cap = (message.get("caption") or "").strip()
    if cap:
        return cap
    if kind == "pdf":
        return "Resuma os pontos principais deste documento."
    return "Analise esta foto no contexto de treino e recuperação."


def maybe_persist_pdf(db, pdf: dict) -> tuple[str | None, int]:
    from services.knowledge_ingest import ingest_pdf, telegram_persist_enabled

    if not telegram_persist_enabled():
        return None, 0
    return ingest_pdf(db, pdf["text"], pdf["filename"], source="telegram")

"""Embeddings Gemini para RAG semântico."""

import json
import logging
import os

import numpy as np

logger = logging.getLogger("hermes.embeddings")

EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")


def embeddings_enabled() -> bool:
    return os.getenv("KNOWLEDGE_EMBEDDINGS", "1") == "1" and bool(os.getenv("GEMINI_API_KEY"))


def embed_text(text: str, task_type: str = "retrieval_document") -> list[float] | None:
    if not embeddings_enabled():
        return None
    text = text.strip()
    if not text:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=text[:8000],
            task_type=task_type,
        )
        return list(result["embedding"])
    except Exception as exc:
        logger.warning("embed_content falhou: %s", exc)
        return None


def embed_query(text: str) -> list[float] | None:
    return embed_text(text, task_type="retrieval_query")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def embedding_to_json(vec: list[float]) -> str:
    return json.dumps(vec)


def embedding_from_json(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

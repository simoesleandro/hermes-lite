from typing import Generator
from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from db.database import Database
import os


_SYSTEM_NO_PDF = (
    "Aguardando upload de PDF. "
    "Use o botão 📎 para enviar um arquivo PDF para análise."
)

_SYSTEM_WITH_PDF = (
    "Você é um assistente especialista em análise de documentos.\n"
    "Responda perguntas sobre o documento fornecido de forma direta e precisa.\n"
    "Cite trechos relevantes quando necessário.\n"
    "Para documentos jurídicos, identifique: partes envolvidas, obrigações, "
    "prazos, valores e cláusulas críticas.\n"
    "CRÍTICO: Baseie-se APENAS no texto do documento fornecido.\n\n"
    "Responda em português."
)


class LeitorPDFAgent(BaseAgent):
    name = "leitor"
    complexity = Complexity.HEAVY

    def __init__(self, db: Database):
        super().__init__(db)
        self._pdf_context: dict | None = None

    def set_pdf_context(self, text: str, filename: str, pages: int) -> None:
        self._pdf_context = {"text": text, "filename": filename, "pages": pages}

    def _build_messages(
        self, message: str, session_id: str, conversation_id: str | None = None,
    ) -> list[dict]:
        if self._pdf_context:
            pdf = self._pdf_context
            system = (
                _SYSTEM_WITH_PDF
                + f"\n\n=== DOCUMENTO: {pdf['filename']} ({pdf['pages']} páginas) ===\n\n"
                + pdf["text"]
            )
        else:
            system = _SYSTEM_NO_PDF

        if os.getenv("KNOWLEDGE_RAG", "1") == "1":
            kb = self.db.format_knowledge_context(message, limit=3)
            if kb:
                system += f"\n\n{kb}"

        system += self._memory_block(conversation_id)
        history = self._get_history(session_id, conversation_id)
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(self, message: str, session_id: str, conversation_id: str | None = None) -> str:
        return get_completion(
            self._build_messages(message, session_id, conversation_id), self.complexity,
        )

    def stream(
        self, message: str, session_id: str, conversation_id: str | None = None, **kwargs,
    ) -> Generator[str, None, None]:
        yield from stream_completion(
            self._build_messages(message, session_id, conversation_id), self.complexity,
        )

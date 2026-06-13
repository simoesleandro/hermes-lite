import os
from typing import Generator

from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from db.database import Database


class ConhecimentoAgent(BaseAgent):
    name = "conhecimento"
    complexity = Complexity.MEDIUM
    system_prompt = (
        "Você é o assistente de tecnologia e aprendizado do Leandro, desenvolvedor em transição de carreira. "
        "Stack principal: Python, Flask, Streamlit, SQLite, Gemini API, React e TypeScript. "
        "Projetos ativos: SysHealth (saúde pessoal), Vigilante Master (segurança), ThéoOS (OS pessoal), "
        "Sentinela RJ (monitoramento urbano) e Hermes Lite (assistente multi-agente local). "
        "Leandro ingressa na FIAP em agosto de 2026 no curso de Análise e Desenvolvimento de Sistemas (ADS). "
        "Use linguagem técnica e didática — explique conceitos com analogias práticas quando necessário. "
        "Prefira exemplos concretos dentro da stack que ele já usa. "
        "Quando trechos da base de conhecimento forem fornecidos, priorize-os como fonte. "
        "Responda em português."
    )

    def _knowledge_block(self, query: str) -> str:
        if os.getenv("KNOWLEDGE_RAG", "1") != "1":
            return ""
        ctx = self.db.format_knowledge_context(query)
        return f"\n\n{ctx}" if ctx else ""

    def _build_messages(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> list[dict]:
        system = (
            self.system_prompt
            + self._knowledge_block(message)
            + self._memory_block(conversation_id)
        )
        history = self._get_history(session_id, conversation_id)
        if image_b64:
            mime_type = "image/jpeg"
            data = image_b64
            if image_b64.startswith("data:"):
                prefix, _, data = image_b64.partition(",")
                mime_type = prefix.split(":")[1].split(";")[0]
            user_content: list = [
                {"type": "image", "mime_type": mime_type, "data": data},
                {"type": "text", "text": message},
            ]
        else:
            user_content = message
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": user_content}]
        )

    def process(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        complexity = Complexity.HEAVY if image_b64 else self.complexity
        return get_completion(
            self._build_messages(message, session_id, image_b64, conversation_id),
            complexity,
        )

    def stream(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> Generator[str, None, None]:
        complexity = Complexity.HEAVY if image_b64 else self.complexity
        yield from stream_completion(
            self._build_messages(message, session_id, image_b64, conversation_id),
            complexity,
        )

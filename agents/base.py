import os
from typing import Generator

from model_router import Complexity, get_completion, stream_completion
from db.database import Database


class BaseAgent:
    name: str = "base"
    complexity: Complexity = Complexity.MEDIUM
    system_prompt: str = "Você é um assistente prestativo. Responda em português."

    def __init__(self, db: Database):
        self.db = db

    def _get_history(self, session_id: str, conversation_id: str | None) -> list[dict]:
        if conversation_id:
            return self.db.get_conversation_history_as_messages(
                self.name, conversation_id, limit=20,
            )
        return self.db.get_history_as_messages(self.name, session_id)

    def _memory_block(self, conversation_id: str | None) -> str:
        if os.getenv("CROSS_CHAT_MEMORY", "1") != "1":
            return ""
        limit = int(os.getenv("CROSS_CHAT_MEMORY_LIMIT", "5"))
        snippets = self.db.get_cross_chat_memory(
            self.name, exclude_conv_id=conversation_id, limit=limit,
        )
        if not snippets:
            return ""
        lines = "\n".join(f"- {s}" for s in snippets)
        return (
            "\n\nContexto de conversas anteriores (mesmo agente — use se relevante):\n"
            + lines
        )

    def _build_messages(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> list[dict]:
        history = self._get_history(session_id, conversation_id)
        system = self.system_prompt + self._memory_block(conversation_id)
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

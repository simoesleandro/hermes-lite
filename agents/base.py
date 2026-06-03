from typing import Generator
from model_router import Complexity, get_completion, stream_completion
from db.database import Database


class BaseAgent:
    name: str = "base"
    complexity: Complexity = Complexity.MEDIUM
    system_prompt: str = "Você é um assistente prestativo. Responda em português."

    def __init__(self, db: Database):
        self.db = db

    def _build_messages(self, message: str, session_id: str) -> list[dict]:
        history = self.db.get_history_as_messages(self.name, session_id)
        return (
            [{"role": "system", "content": self.system_prompt}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(self, message: str, session_id: str) -> str:
        return get_completion(self._build_messages(message, session_id), self.complexity)

    def stream(self, message: str, session_id: str) -> Generator[str, None, None]:
        yield from stream_completion(self._build_messages(message, session_id), self.complexity)

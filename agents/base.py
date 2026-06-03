from model_router import Complexity, get_completion
from db.database import Database


class BaseAgent:
    name: str = "base"
    complexity: Complexity = Complexity.MEDIUM
    system_prompt: str = "Você é um assistente prestativo. Responda em português."

    def __init__(self, db: Database):
        self.db = db

    def process(self, message: str) -> str:
        history = self.db.get_history_as_messages(self.name)
        messages = (
            [{"role": "system", "content": self.system_prompt}]
            + history
            + [{"role": "user", "content": message}]
        )
        return get_completion(messages, self.complexity)

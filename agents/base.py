from model_router import Complexity, get_completion


class BaseAgent:
    name: str = "base"
    complexity: Complexity = Complexity.MEDIUM
    system_prompt: str = "Você é um assistente prestativo. Responda em português."

    def process(self, message: str) -> str:
        prompt = f"{self.system_prompt}\n\nUsuário: {message}"
        return get_completion(prompt, self.complexity)

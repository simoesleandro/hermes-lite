from .base import BaseAgent, Complexity


class SaudeAgent(BaseAgent):
    name = "saude"
    complexity = Complexity.SIMPLE

    def process(self, message: str) -> str:
        return (
            f"[Saúde] Recebi sua mensagem: '{message}'. "
            "Este agente responderá perguntas sobre saúde, bem-estar e hábitos saudáveis. "
            "Integração com modelo de linguagem pendente (model_router)."
        )

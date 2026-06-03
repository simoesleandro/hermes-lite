from .base import BaseAgent, Complexity


class DesenvolvimentoAgent(BaseAgent):
    name = "desenvolvimento"
    complexity = Complexity.HEAVY

    def process(self, message: str) -> str:
        return (
            f"[Desenvolvimento] Recebi sua mensagem: '{message}'. "
            "Este agente responderá perguntas sobre programação, arquitetura e engenharia de software. "
            "Integração com modelo de linguagem pendente (model_router)."
        )

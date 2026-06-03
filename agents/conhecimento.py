from .base import BaseAgent, Complexity


class ConhecimentoAgent(BaseAgent):
    name = "conhecimento"
    complexity = Complexity.MEDIUM

    def process(self, message: str) -> str:
        return (
            f"[Conhecimento] Recebi sua mensagem: '{message}'. "
            "Este agente responderá perguntas gerais, pesquisa e aprendizado. "
            "Integração com modelo de linguagem pendente (model_router)."
        )

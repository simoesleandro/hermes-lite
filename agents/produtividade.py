from .base import BaseAgent, Complexity


class ProdutividadeAgent(BaseAgent):
    name = "produtividade"
    complexity = Complexity.MEDIUM

    def process(self, message: str) -> str:
        return (
            f"[Produtividade] Recebi sua mensagem: '{message}'. "
            "Este agente responderá perguntas sobre organização, foco, gestão de tempo e tarefas. "
            "Integração com modelo de linguagem pendente (model_router)."
        )

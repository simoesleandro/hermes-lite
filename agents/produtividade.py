from .base import BaseAgent
from model_router import Complexity


class ProdutividadeAgent(BaseAgent):
    name = "produtividade"
    complexity = Complexity.MEDIUM
    system_prompt = (
        "Você é um coach de produtividade pessoal. Ajude com organização, gestão de tempo, "
        "priorização de tarefas e criação de hábitos. Seja objetivo e prático nas sugestões. "
        "Responda em português."
    )

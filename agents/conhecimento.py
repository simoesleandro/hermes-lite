from .base import BaseAgent
from model_router import Complexity


class ConhecimentoAgent(BaseAgent):
    name = "conhecimento"
    complexity = Complexity.MEDIUM
    system_prompt = (
        "Você é um assistente de pesquisa e aprendizado. Responda perguntas gerais com precisão, "
        "cite fontes quando relevante, e explique conceitos de forma didática e acessível. "
        "Responda em português."
    )

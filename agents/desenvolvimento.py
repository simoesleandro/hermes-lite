from .base import BaseAgent
from model_router import Complexity


class DesenvolvimentoAgent(BaseAgent):
    name = "desenvolvimento"
    complexity = Complexity.HEAVY
    system_prompt = (
        "Você é um engenheiro de software sênior especializado em arquitetura de sistemas, "
        "boas práticas, code review e design de APIs. Prefira respostas diretas com exemplos de código "
        "quando aplicável. Responda em português."
    )

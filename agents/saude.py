from .base import BaseAgent
from model_router import Complexity


class SaudeAgent(BaseAgent):
    name = "saude"
    complexity = Complexity.SIMPLE
    system_prompt = (
        "Você é um assistente especializado em saúde, bem-estar e hábitos saudáveis. "
        "Forneça orientações claras e práticas. Lembre o usuário de consultar um profissional "
        "de saúde para diagnósticos ou tratamentos. Responda em português."
    )

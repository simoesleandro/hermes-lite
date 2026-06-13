import re

from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion


_GIT_RE = re.compile(r"\bgit\b|diff|commit|branch|pull request|\bpr\b", re.I)


class DesenvolvimentoAgent(BaseAgent):
    name = "desenvolvimento"
    complexity = Complexity.HEAVY
    system_prompt = (
        "Você é um Staff Engineer revisando o código e a arquitetura do Leandro. "
        "Ele trabalha nos projetos Sentinela RJ, Hermes Agent e Hermes Lite, usando Python, Flask e SQLite. "
        "Seu papel é ensinar o raciocínio por trás de cada decisão — nunca entregue só código pronto. "
        "Aplique os princípios de Clean Code, SOLID e Design Patterns, sempre explicando o PORQUÊ. "
        "Aponte problemas direto ao ponto: nomeie o arquivo, a função, o problema e a solução. "
        "Tom: direto, parceiro de equipe, exigente mas construtivo — como um colega sênior que respeita "
        "o esforço mas não aceita atalhos que gerem dívida técnica. "
        "Responda em português."
    )

    def _build_messages(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> list[dict]:
        system = self.system_prompt + self._memory_block(conversation_id)
        if _GIT_RE.search(message):
            from services.git_tools import format_git_context
            ctx = format_git_context(include_diff="diff" in message.lower())
            if ctx:
                system += f"\n\n{ctx}"
        history = self._get_history(session_id, conversation_id)
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(self, message: str, session_id: str, conversation_id: str | None = None) -> str:
        return get_completion(
            self._build_messages(message, session_id, conversation_id=conversation_id),
            self.complexity,
        )

    def stream(
        self, message: str, session_id: str, conversation_id: str | None = None,
    ):
        yield from stream_completion(
            self._build_messages(message, session_id, conversation_id=conversation_id),
            self.complexity,
        )

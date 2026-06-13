import re
import uuid
from typing import Generator

from .base import BaseAgent
from model_router import Complexity, get_completion, stream_completion
from db.database import Database

_ADD_RE = re.compile(
    r"^(?:adicionar|nova|criar)\s+tarefa[:\s]+(.+)$",
    re.I,
)
_TODAY_RE = re.compile(
    r"^(?:adicionar|colocar|por)\s+(?:para\s+)?hoje[:\s]+(.+)$",
    re.I,
)
_WEEK_RE = re.compile(
    r"^(?:adicionar|colocar|por)\s+(?:para\s+)?(?:esta\s+)?semana[:\s]+(.+)$",
    re.I,
)
_LEMBRAR_RE = re.compile(r"^lembrar(?:-me)?\s+(?:de\s+)?(.+)$", re.I)
_DONE_RE = re.compile(
    r"^(?:concluir|completei|feito|done|finalizar)\s+(?:tarefa[:\s]+)?(.+)$",
    re.I,
)
_PRIO_RE = re.compile(
    r"^(?:prioridade|priorizar)\s+(alta|média|media|baixa)\s+(?:para\s+)?(.+)$",
    re.I,
)


class ProdutividadeAgent(BaseAgent):
    name = "produtividade"
    complexity = Complexity.MEDIUM
    system_prompt = (
        "Você é o assistente pessoal do Leandro, desenvolvedor em transição de carreira, "
        "morador do Rio de Janeiro. Esposa: trabalha na SECTI-RJ. Filho: Théo. "
        "Ele mantém 6 repositórios ativos no GitHub e equilibra projetos pessoais com rotina familiar.\n\n"
        "Ajude com: organização de tarefas GTD, agenda, lembretes, priorização de projetos e foco. "
        "Quando receber uma lista de tarefas ou pedido de planejamento, estruture em blocos claros "
        "(hoje / esta semana / inbox / backlog) sem enrolação.\n\n"
        "Comandos naturais que o sistema já processa:\n"
        "- 'adicionar tarefa: …' / 'lembrar de …' → inbox\n"
        "- 'para hoje: …' → tarefa de hoje\n"
        "- 'para esta semana: …' → tarefa da semana\n"
        "- 'concluir …' / 'feito: …' → marca como done\n\n"
        "Use SEMPRE a lista GTD abaixo como fonte de verdade. "
        "Tom: objetivo, direto. Responda em português."
    )

    def _try_task_action(self, message: str) -> str | None:
        msg = message.strip()
        if not msg:
            return None

        m = _PRIO_RE.match(msg)
        if m:
            pri_map = {"alta": "high", "média": "medium", "media": "medium", "baixa": "low"}
            pri = pri_map.get(m.group(1).lower(), "medium")
            title = m.group(2).strip()
            task = self.db.find_open_task(title)
            if task and self.db.update_task(task["id"], priority=pri):
                return f"✅ Prioridade de «{task['title']}» → {m.group(1).lower()}"
            return None

        m = _DONE_RE.match(msg)
        if m:
            fragment = m.group(1).strip()
            task = self.db.find_open_task(fragment)
            if task and self.db.complete_task(task["id"]):
                return f"✅ Tarefa concluída: «{task['title']}»"
            return f"⚠️ Não encontrei tarefa aberta correspondente a «{fragment}»"

        for pattern, status in (
            (_TODAY_RE, "today"),
            (_WEEK_RE, "week"),
            (_ADD_RE, "inbox"),
            (_LEMBRAR_RE, "inbox"),
        ):
            m = pattern.match(msg)
            if m:
                title = m.group(1).strip()
                if len(title) < 2:
                    return None
                self.db.create_task(str(uuid.uuid4()), title, status=status)
                label = {"today": "hoje", "week": "esta semana", "inbox": "inbox"}[status]
                return f"✅ Tarefa adicionada ({label}): «{title}»"
        return None

    def _build_messages(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> list[dict]:
        action = self._try_task_action(message)
        tasks_ctx = self.db.format_tasks_context()
        system = (
            self.system_prompt
            + f"\n\n=== GTD ATUAL ===\n{tasks_ctx}"
            + self._facts_block()
            + self._memory_block(conversation_id)
        )
        if action:
            system += f"\n\n[Ação registrada no GTD: {action}]"
        history = self._get_history(session_id, conversation_id)
        return (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": message}]
        )

    def process(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        return get_completion(
            self._build_messages(message, session_id, image_b64, conversation_id),
            self.complexity,
        )

    def stream(
        self,
        message: str,
        session_id: str,
        image_b64: str | None = None,
        conversation_id: str | None = None,
    ) -> Generator[str, None, None]:
        yield from stream_completion(
            self._build_messages(message, session_id, image_b64, conversation_id),
            self.complexity,
        )

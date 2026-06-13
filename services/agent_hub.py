"""Hub central — roteamento e execução de agentes (web, Telegram, etc.)."""

from __future__ import annotations

from agents.analista import AnalistaAgent
from agents.conhecimento import ConhecimentoAgent
from agents.desenvolvimento import DesenvolvimentoAgent
from agents.investigador import InvestigadorAgent
from agents.juridico import JuridicoAgent
from agents.leitor_pdf import LeitorPDFAgent
from agents.ops import OpsAgent
from agents.produtividade import ProdutividadeAgent
from agents.saude import SaudeAgent
from agents.sentinela import SentinelaAgent
from agents.skills import apply_skill
from agents.treino import TreinoAgent
from app_factory import classify_agent
from db.database import Database

AGENT_LABELS = {
    "conhecimento": "Conhecimento",
    "desenvolvimento": "Desenvolvimento",
    "saude": "Saúde",
    "treino": "Treino",
    "produtividade": "Produtividade",
    "sentinela": "Sentinela",
    "juridico": "Jurídico",
    "investigador": "Investigador",
    "leitor": "Leitor",
    "analista": "Analista",
    "ops": "Ops",
}


class AgentHub:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self.agents = {
            "saude": SaudeAgent(db=self.db),
            "conhecimento": ConhecimentoAgent(db=self.db),
            "desenvolvimento": DesenvolvimentoAgent(db=self.db),
            "produtividade": ProdutividadeAgent(db=self.db),
            "sentinela": SentinelaAgent(db=self.db),
            "treino": TreinoAgent(db=self.db),
            "juridico": JuridicoAgent(db=self.db),
            "investigador": InvestigadorAgent(db=self.db),
            "leitor": LeitorPDFAgent(db=self.db),
            "analista": AnalistaAgent(db=self.db),
            "ops": OpsAgent(db=self.db),
        }
        self._locked_agent: dict[str, str | None] = {}

    @staticmethod
    def session_id(channel: str, chat_id: int | str) -> str:
        return f"{channel}-{chat_id}"

    def set_locked_agent(self, session_id: str, agent: str | None) -> None:
        if agent is None:
            self._locked_agent.pop(session_id, None)
        else:
            self._locked_agent[session_id] = agent

    def get_locked_agent(self, session_id: str) -> str | None:
        return self._locked_agent.get(session_id)

    def chat(
        self,
        message: str,
        session_id: str,
        agent_name: str | None = None,
        skill_id: str | None = None,
    ) -> tuple[str, str]:
        agent_name = agent_name or self._locked_agent.get(session_id) or classify_agent(message)
        if agent_name not in self.agents:
            agent_name = "conhecimento"

        if skill_id:
            message = apply_skill(agent_name, skill_id, message)

        agent = self.agents[agent_name]
        response = agent.process(message, session_id)
        self.db.save_message(agent=agent_name, role="user", content=message, session_id=session_id)
        self.db.save_message(agent=agent_name, role="assistant", content=response, session_id=session_id)
        label = AGENT_LABELS.get(agent_name, agent_name)
        return f"🤖 {label}\n\n{response}", agent_name

    def handoff_investigador(
        self,
        session_id: str,
        alert: dict | None = None,
        context: str = "",
    ) -> tuple[str, str]:
        from services.handoff import build_investigador_handoff_message

        msg = build_investigador_handoff_message(context, alert)
        return self.chat(msg, session_id, agent_name="investigador", skill_id="rapido")

    def handoff_juridico_from_alert(
        self,
        session_id: str,
        alert: dict,
    ) -> tuple[str, str]:
        from services.handoff import build_juridico_from_alert

        msg = build_juridico_from_alert(alert)
        return self.chat(msg, session_id, agent_name="juridico")

    def clear_session(self, session_id: str, agent_name: str | None = None) -> int:
        if agent_name:
            return self.db.clear_history(agent_name, session_id)
        total = 0
        for name in self.agents:
            total += self.db.clear_history(name, session_id)
        return total

"""Hermes Lite MCP server — expõe Sentinela, SysHealth e tools do Investigador via MCP."""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Garante imports a partir da raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from app_factory import classify_agent
from db.database import Database
from services.investigador_tools import TOOLS_REGISTRY
from services.sentinela_client import SentinelaClient
from services.syshealth_client import SysHealthClient

mcp = FastMCP(
    "hermes-lite",
    instructions=(
        "Ferramentas do Hermes Lite: contratos públicos RJ (Sentinela), "
        "saúde (SysHealth), investigação (CNPJ, web) e roteamento de agentes."
    ),
)

AGENTS = [
    "conhecimento", "desenvolvimento", "saude", "treino", "produtividade",
    "sentinela", "juridico", "investigador", "leitor", "analista", "ops",
]

_sentinela = SentinelaClient()
_syshealth = SysHealthClient()
_db = Database()


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def list_agents() -> str:
    """Lista os 11 agentes especializados do Hermes Lite."""
    return _json({"agents": AGENTS})


@mcp.tool()
def classify_message(message: str) -> str:
    """Classifica uma mensagem e retorna o agente recomendado (regex router)."""
    return _json({"agent": classify_agent(message.strip())})


@mcp.tool()
def sentinela_resumo() -> str:
    """Resumo geral do banco Sentinela RJ: contratos, valor total, alertas abertos."""
    return _json(_sentinela.get_resumo())


@mcp.tool()
def sentinela_alertas(severidade: str = "", limit: int = 10) -> str:
    """Alertas abertos do Sentinela. severidade opcional: alta, media, baixa."""
    sev = severidade.strip().lower() or None
    return _json(_sentinela.get_alertas(severidade=sev, limit=min(limit, 50)))


@mcp.tool()
def sentinela_top_contratos(limit: int = 5) -> str:
    """Maiores contratos públicos por valor no Sentinela RJ."""
    return _json(_sentinela.top_contratos(limit=min(limit, 20)))


@mcp.tool()
def sentinela_buscar_fornecedor(nome_ou_cnpj: str) -> str:
    """Busca contratos e alertas de um fornecedor por nome ou CNPJ."""
    return _json(_sentinela.buscar_fornecedor(nome_ou_cnpj))


@mcp.tool()
def sentinela_estatisticas() -> str:
    """Estatísticas agregadas: por categoria, mês e severidade de alertas."""
    return _json(_sentinela.get_estatisticas())


@mcp.tool()
def syshealth_resumo() -> str:
    """Resumo diário de saúde do SysHealth (água, peso, sono, HRV, etc.)."""
    return _json(_syshealth.get_health_summary())


@mcp.tool()
def syshealth_registrar_agua(ml: int) -> str:
    """Registra consumo de água em mililitros no SysHealth."""
    return _json(_syshealth.register_agua(ml))


@mcp.tool()
def syshealth_registrar_peso(kg: float) -> str:
    """Registra peso corporal em kg no SysHealth."""
    return _json(_syshealth.register_peso(kg))


@mcp.tool()
def syshealth_registrar_tirzepatida() -> str:
    """Marca tirzepatida como tomada hoje no SysHealth."""
    return _json(_syshealth.register_tirzepatida())


@mcp.tool()
def investigador_buscar_cnpj(cnpj: str) -> str:
    """Consulta dados cadastrais de CNPJ via BrasilAPI."""
    return _json(TOOLS_REGISTRY["buscar_cnpj"](cnpj))


@mcp.tool()
def investigador_buscar_contratos(termo: str) -> str:
    """Busca contratos no Sentinela RJ por termo, fornecedor ou CNPJ."""
    return _json(TOOLS_REGISTRY["buscar_contratos"](termo))


@mcp.tool()
def investigador_buscar_alertas(termo: str) -> str:
    """Busca alertas abertos no Sentinela RJ por fornecedor ou CNPJ."""
    return _json(TOOLS_REGISTRY["buscar_alertas"](termo))


@mcp.tool()
def investigador_buscar_web(query: str) -> str:
    """Busca na web via DuckDuckGo (máx. 5 resultados)."""
    return _json(TOOLS_REGISTRY["buscar_web"](query))


@mcp.tool()
def gtd_list_tasks(status: str = "") -> str:
    """Lista tarefas GTD (status: inbox, today, week ou vazio para abertas)."""
    st = status.strip().lower() or None
    if st and st not in ("inbox", "today", "week", "done"):
        return _json({"error": "status inválido"})
    return _json({"tasks": _db.list_tasks(status=st), "summary": _db.tasks_summary()})


@mcp.tool()
def gtd_add_task(title: str, status: str = "inbox") -> str:
    """Adiciona tarefa GTD (status: inbox, today, week)."""
    import uuid as _uuid
    st = status.strip().lower() or "inbox"
    if st not in ("inbox", "today", "week"):
        return _json({"error": "status inválido"})
    tid = str(_uuid.uuid4())
    _db.create_task(tid, title.strip(), status=st)
    return _json({"ok": True, "id": tid, "title": title.strip(), "status": st})


if __name__ == "__main__":
    mcp.run()

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
_hub = None


def _hub_instance():
    global _hub
    if _hub is None:
        from services.agent_hub import AgentHub
        _hub = AgentHub(db=_db)
    return _hub


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


@mcp.tool()
def handoff_investigador_juridico(dossier: str, sources_json: str = "[]") -> str:
    """Monta mensagem de handoff Investigador → Jurídico (parecer legal). sources_json: JSON array."""
    from services.handoff import build_juridico_handoff_message
    try:
        sources = json.loads(sources_json) if sources_json.strip() else []
    except json.JSONDecodeError:
        sources = []
    message = build_juridico_handoff_message(dossier, sources)
    return _json({"agent": "juridico", "skill": "parecer", "message": message})


@mcp.tool()
def knowledge_search(query: str, limit: int = 5) -> str:
    """Busca na base de conhecimento local (FTS5 + embeddings híbrido)."""
    return _json({"results": _db.search_knowledge_hybrid(query, limit=min(limit, 10))})


@mcp.tool()
def knowledge_list() -> str:
    """Lista documentos indexados na base de conhecimento."""
    return _json({"documents": _db.list_knowledge_docs()})


@mcp.tool()
def handoff_sentinela_investigador(context: str, alert_json: str = "") -> str:
    """Monta handoff Sentinela → Investigador. alert_json: JSON opcional com fornecedor, tipo, etc."""
    from services.handoff import build_investigador_handoff_message
    alert = None
    if alert_json.strip():
        try:
            alert = json.loads(alert_json)
        except json.JSONDecodeError:
            pass
    message = build_investigador_handoff_message(context, alert)
    return _json({"agent": "investigador", "skill": "rapido", "message": message})


@mcp.tool()
def hermes_health() -> str:
    """Health unificado: DB, Telegram, providers LLM, SysHealth e Sentinela."""
    from services.health import get_health
    return _json(get_health())


@mcp.tool()
def hermes_chat(message: str, agent: str = "", session_id: str = "mcp") -> str:
    """Chat completo com um agente Hermes (roteamento automático se agent vazio)."""
    agent_name = agent.strip().lower() or None
    if agent_name and agent_name not in AGENTS:
        return _json({"error": f"agente inválido: {agent_name}"})
    reply, used = _hub_instance().chat(message.strip(), session_id, agent_name=agent_name)
    return _json({"agent": used, "response": reply})


@mcp.tool()
def telegram_notify(message: str, title: str = "") -> str:
    """Envia notificação proativa ao chat Telegram configurado."""
    from services.telegram_client import bot_token, default_chat_id, send_message
    if not bot_token():
        return _json({"error": "TELEGRAM_BOT_TOKEN não configurado"})
    chat_id = default_chat_id()
    if not chat_id:
        return _json({"error": "TELEGRAM_CHAT_ID não configurado"})
    text = f"{title.strip()}\n\n{message.strip()}" if title.strip() else message.strip()
    send_message(chat_id, text)
    return _json({"ok": True, "chat_id": chat_id})


@mcp.tool()
def export_conversation(conversation_id: str) -> str:
    """Exporta conversa como Markdown."""
    md = _db.export_conversation_markdown(conversation_id.strip())
    if not md:
        return _json({"error": "conversa não encontrada"})
    return _json({"conversation_id": conversation_id, "markdown": md})


@mcp.tool()
def git_status() -> str:
    """Status git do repositório hermes-lite (branch + status -sb)."""
    from services.git_tools import git_branch, git_status_short
    return _json({"branch": git_branch(), "status": git_status_short()})


@mcp.tool()
def git_diff(staged: bool = False, max_lines: int = 150) -> str:
    """Diff git (working tree ou staged)."""
    from services.git_tools import git_diff as _git_diff
    return _json({"diff": _git_diff(max_lines=min(max_lines, 300), staged=staged)})


@mcp.tool()
def git_log(limit: int = 8) -> str:
    """Últimos commits (oneline)."""
    from services.git_tools import git_log as _git_log
    return _json({"log": _git_log(min(limit, 20))})


@mcp.tool()
def facts_list(category: str = "") -> str:
    """Lista fatos persistentes sobre o usuário."""
    cat = category.strip() or None
    return _json({"facts": _db.list_facts(category=cat)})


@mcp.tool()
def facts_upsert(key: str, value: str, category: str = "") -> str:
    """Salva ou atualiza um fato (memória estruturada)."""
    from services.facts import slug_key
    k = slug_key(key) if "=" not in key and ":" not in key else key.strip()
    _db.upsert_fact(k, value.strip(), category=category.strip() or None)
    return _json({"ok": True, "key": k, "value": value.strip()})


@mcp.tool()
def facts_delete(key: str) -> str:
    """Remove um fato pela chave."""
    if not _db.delete_fact(key.strip()):
        return _json({"error": "fato não encontrado"})
    return _json({"ok": True})


@mcp.tool()
def workflow_investigacao_parecer(
    context: str = "",
    alert_json: str = "",
    dossier: str = "",
    sources_json: str = "[]",
) -> str:
    """Inicia pipeline durável Investigador → Jurídico → export MD (background)."""
    from services.workflow import start_investigacao_parecer

    alert = None
    if alert_json.strip():
        try:
            alert = json.loads(alert_json)
        except json.JSONDecodeError:
            pass
    try:
        sources = json.loads(sources_json) if sources_json.strip() else []
    except json.JSONDecodeError:
        sources = []
    d = dossier.strip() or None
    ctx = context.strip()
    if not d and not ctx and not alert:
        return _json({"error": "informe context, alert_json ou dossier"})
    wf_id = start_investigacao_parecer(
        _db, context=ctx, alert=alert, dossier=d, sources=sources,
    )
    return _json({"id": wf_id, "status": "pending", "poll": f"workflow status id={wf_id}"})


if __name__ == "__main__":
    mcp.run()

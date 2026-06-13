"""Skills — presets de instrução por agente (padrão Open WebUI)."""

SKILLS: dict[str, dict[str, dict]] = {
    "investigador": {
        "dossie": {
            "label": "Dossiê formal",
            "prompt": (
                "Modo dossiê formal: cite fontes numeradas [1], [2], estruture com sumário executivo, "
                "e separe fatos verificados de hipóteses."
            ),
        },
        "rapido": {
            "label": "Busca rápida",
            "prompt": "Modo rápido: máximo 3 ferramentas, resposta em tópicos curtos, sem relatório longo.",
        },
    },
    "sentinela": {
        "auditoria": {
            "label": "Auditoria PNCP",
            "prompt": (
                "Priorize alertas de alta severidade, valores em R$, fornecedores repetidos "
                "e contratos sem licitação acima dos limiares legais."
            ),
        },
    },
    "juridico": {
        "parecer": {
            "label": "Parecer legal",
            "prompt": (
                "Formato parecer: ementa, fundamentação com artigos da Lei 14.133/2021, "
                "conclusão objetiva e risco (baixo/médio/alto)."
            ),
        },
    },
    "analista": {
        "sql": {
            "label": "SQL + gráfico",
            "prompt": "Gere código Python com SQL no Sentinela DB e inclua gráfico matplotlib quando aplicável.",
        },
    },
    "saude": {
        "resumo": {
            "label": "Resumo do dia",
            "prompt": "Apresente todos os campos SysHealth disponíveis e compare com metas (água 3L, proteína 190g, peso 83kg).",
        },
    },
    "desenvolvimento": {
        "review": {
            "label": "Code review",
            "prompt": "Code review: bugs, segurança, performance, legibilidade. Liste achados por severidade.",
        },
    },
}


def list_skills(agent: str | None = None) -> dict:
    if agent:
        return {agent: SKILLS.get(agent, {})}
    return SKILLS


def apply_skill(agent: str, skill_id: str, message: str) -> str:
    skill = SKILLS.get(agent, {}).get(skill_id)
    if not skill:
        return message
    return f"{skill['prompt']}\n\n{message}"


def extract_sources(resultados: dict) -> list[dict]:
    """Extrai fontes citáveis dos resultados das tools do Investigador."""
    sources: list[dict] = []
    for tool, result in resultados.items():
        if tool == "buscar_web" and isinstance(result, list):
            for r in result:
                url = r.get("href")
                if url:
                    sources.append({
                        "type": "web",
                        "title": (r.get("title") or url)[:120],
                        "url": url,
                    })
        elif tool == "buscar_contratos" and isinstance(result, list):
            for r in result:
                pncp = r.get("numero_controle_pncp")
                title = r.get("fornecedor") or (r.get("objeto") or "")[:80]
                if pncp:
                    sources.append({
                        "type": "contrato",
                        "title": title,
                        "url": f"https://pncp.gov.br/app/contratos/{pncp}",
                    })
        elif tool == "buscar_cnpj" and isinstance(result, dict) and result.get("razao_social"):
            cnpj = result.get("cnpj") or ""
            sources.append({
                "type": "cnpj",
                "title": result.get("razao_social", "CNPJ"),
                "url": f"https://brasilapi.com.br/docs#tag/CNPJ" if not cnpj else None,
            })
    for i, s in enumerate(sources, 1):
        s["n"] = i
    return sources

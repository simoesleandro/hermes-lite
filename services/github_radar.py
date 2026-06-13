"""Radar GitHub — curadoria diária autônoma de repositórios."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.github_client import (
    default_search_queries,
    fetch_readme_excerpt,
    search_repositories,
)

logger = logging.getLogger("hermes.github_radar")

EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports" / "github-radar"

_CURATE_SYSTEM = """Você é o Radar GitHub do Hermes Lite — curador para Leandro, desenvolvedor Python/Flask,
projetos Sentinela RJ, Hermes multi-agente, MCP, RAG e automação pessoal no Windows.

A partir da lista de repositórios candidatos, escolha os MELHORES para o perfil dele.
Retorne APENAS JSON válido (sem markdown):
{
  "picks": [
    {
      "full_name": "owner/repo",
      "nota": 8.5,
      "o_que_faz": "1-2 frases objetivas",
      "como_usar": "passos práticos ou comando de instalação/uso",
      "raciocinio": "por que vale a pena para o Leandro (2-3 frases)",
      "tags": ["mcp", "python"]
    }
  ]
}

Regras:
- nota: número de 0 a 10 (pode usar decimais)
- Escolha entre 3 e 5 repositórios (máximo 5)
- Priorize utilidade real para stack dele, não hype vazio
- Se README estiver vazio, infira com cautela e diga incerteza no raciocinio
- Repositórios já muito genéricos ou duplicados de ferramentas que ele já usa (Open WebUI básico) → nota menor
"""


def _profile_block(db) -> str:
    if os.getenv("USER_FACTS", "1") != "1":
        return ""
    try:
        ctx = db.format_facts_context(limit=8)
        return f"\n\nFatos do usuário:\n{ctx}" if ctx else ""
    except Exception:
        return ""


def collect_candidates(db, max_per_query: int = 12) -> list[dict]:
    seen_db = {r["full_name"] for r in db.list_github_seen()}
    candidates: dict[str, dict] = {}
    for query in default_search_queries():
        for repo in search_repositories(query, per_page=max_per_query):
            name = repo.get("full_name")
            if not name or name in seen_db or name in candidates:
                continue
            candidates[name] = repo
    return list(candidates.values())[:40]


def curate_with_llm(candidates: list[dict], db) -> list[dict]:
    if not candidates:
        return []
    enriched = []
    for repo in candidates[:25]:
        r = dict(repo)
        r["readme_excerpt"] = fetch_readme_excerpt(repo["full_name"], max_chars=800)
        enriched.append(r)

    from model_router import Complexity, get_completion

    user_payload = json.dumps(enriched, ensure_ascii=False, indent=2)
    raw = get_completion(
        [
            {"role": "system", "content": _CURATE_SYSTEM + _profile_block(db)},
            {"role": "user", "content": f"Candidatos:\n{user_payload}"},
        ],
        Complexity.HEAVY,
    )
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    data = json.loads(raw)
    picks = data.get("picks") or []
    out = []
    for p in picks[:5]:
        if not p.get("full_name"):
            continue
        nota = float(p.get("nota", 0))
        nota = max(0.0, min(10.0, nota))
        out.append({
            "full_name": p["full_name"],
            "nota": nota,
            "o_que_faz": (p.get("o_que_faz") or "").strip(),
            "como_usar": (p.get("como_usar") or "").strip(),
            "raciocinio": (p.get("raciocinio") or p.get("raciocínio") or "").strip(),
            "tags": p.get("tags") or [],
        })
    by_name = {c["full_name"]: c for c in candidates}
    for pick in out:
        meta = by_name.get(pick["full_name"], {})
        pick["html_url"] = meta.get("html_url", f"https://github.com/{pick['full_name']}")
        pick["stars"] = meta.get("stars", 0)
        pick["language"] = meta.get("language", "")
    return out


def render_digest_markdown(picks: list[dict], date_str: str) -> str:
    lines = [
        f"# Radar GitHub — {date_str}",
        "",
        "Curadoria autônoma Hermes Lite: repositórios filtrados para o seu perfil.",
        "",
    ]
    if not picks:
        lines.append("_Nenhum repositório novo selecionado hoje._")
        return "\n".join(lines)

    for i, p in enumerate(picks, 1):
        nota = p.get("nota", 0)
        stars = p.get("stars", 0)
        lang = p.get("language") or "—"
        tags = ", ".join(p.get("tags") or []) or "—"
        lines.extend([
            f"## {i}. [{p['full_name']}]({p.get('html_url', '')}) — **{nota}/10**",
            "",
            f"⭐ {stars:,} · {lang} · {tags}".replace(",", " "),
            "",
            "### O que faz",
            p.get("o_que_faz") or "—",
            "",
            "### Como usar",
            p.get("como_usar") or "—",
            "",
            "### Por que vale (raciocínio)",
            p.get("raciocinio") or "—",
            "",
            "---",
            "",
        ])
    return "\n".join(lines)


def build_telegram_summary(picks: list[dict], date_str: str) -> str:
    if not picks:
        return f"📡 Radar GitHub {date_str}\nNenhum repo novo hoje."
    lines = [f"📡 Radar GitHub — {date_str}", ""]
    for p in picks[:3]:
        lines.append(f"• **{p['full_name']}** ({p.get('nota', 0)}/10)")
        lines.append(f"  {p.get('o_que_faz', '')[:120]}")
    if len(picks) > 3:
        lines.append(f"\n+{len(picks) - 3} no documento completo.")
    return "\n".join(lines)


def run_github_radar(db, *, notify: bool = True) -> dict:
    """Executa curadoria; retorna {date, picks, markdown_path, digest_id}."""
    if os.getenv("GITHUB_RADAR_ENABLED", "1") != "1":
        return {"skipped": True, "reason": "GITHUB_RADAR_ENABLED=0"}

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = db.get_github_digest_by_date(date_str)
    if existing and os.getenv("GITHUB_RADAR_FORCE", "0") != "1":
        return {
            "date": date_str,
            "already_exists": True,
            "digest_id": existing["id"],
            "picks_count": len(existing.get("picks") or []),
        }

    candidates = collect_candidates(db)
    picks = curate_with_llm(candidates, db)

    markdown = render_digest_markdown(picks, date_str)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = EXPORTS_DIR / f"{date_str}.md"
    md_path.write_text(markdown, encoding="utf-8")

    digest_id = str(uuid.uuid4())
    db.save_github_digest(digest_id, date_str, markdown, picks, str(md_path))

    for p in picks:
        db.mark_github_seen(p["full_name"], score=p.get("nota"))

    summary = build_telegram_summary(picks, date_str)
    if notify:
        try:
            from cronos.notifier import notify
            notify(summary, title="Radar GitHub")
        except Exception as exc:
            logger.warning("notify radar: %s", exc)

    logger.info("Radar GitHub %s — %s picks → %s", date_str, len(picks), md_path)
    return {
        "date": date_str,
        "digest_id": digest_id,
        "picks": picks,
        "markdown_path": str(md_path),
        "picks_count": len(picks),
    }

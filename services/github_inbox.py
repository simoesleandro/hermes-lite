"""Inbox GitHub — PRs abertos, reviews pendentes, issues e CI falhou."""

from __future__ import annotations

import os

from services.github_client import (
    github_token_configured,
    github_username,
    list_assigned_issues,
    list_open_prs_by_author,
    list_prs_needing_review,
    list_recent_ci_failures,
)


def inbox_enabled() -> bool:
    return os.getenv("GITHUB_INBOX_ENABLED", "1") == "1" and github_token_configured()


def fetch_github_inbox() -> dict:
    """Coleta inbox do usuário autenticado."""
    if not inbox_enabled():
        return {
            "enabled": False,
            "offline": True,
            "reason": "GITHUB_TOKEN ausente ou GITHUB_INBOX_ENABLED=0",
        }

    user = github_username()
    if not user:
        return {"enabled": True, "offline": True, "reason": "usuário GitHub não identificado"}

    prs_open = list_open_prs_by_author(user, limit=5)
    prs_review = list_prs_needing_review(user, limit=5)
    issues = list_assigned_issues(limit=5)
    ci_failed = list_recent_ci_failures(user, max_repos=8, limit=3)

    return {
        "enabled": True,
        "offline": False,
        "user": user,
        "prs_open": prs_open,
        "prs_review": prs_review,
        "issues_assigned": issues,
        "ci_failures": ci_failed,
    }


def build_inbox_lines(data: dict | None = None) -> list[str]:
    data = data if data is not None else fetch_github_inbox()
    lines = ["🐙 GitHub"]

    if not data.get("enabled"):
        lines.append("Inbox desativada (configure GITHUB_TOKEN)")
        return lines
    if data.get("offline"):
        lines.append(data.get("reason") or "GitHub indisponível")
        return lines

    prs_open = data.get("prs_open") or []
    prs_review = data.get("prs_review") or []
    issues = data.get("issues_assigned") or []
    ci = data.get("ci_failures") or []

    if prs_open:
        lines.append(f"PRs abertos ({len(prs_open)}):")
        for p in prs_open[:3]:
            repo = p.get("repo") or "?"
            lines.append(f"  • {repo}#{p.get('number')} — {p.get('title', '')[:50]}")
    else:
        lines.append("PRs abertos: nenhum")

    if prs_review:
        lines.append(f"Reviews pendentes ({len(prs_review)}):")
        for p in prs_review[:3]:
            repo = p.get("repo") or "?"
            lines.append(f"  • {repo}#{p.get('number')} — {p.get('title', '')[:50]}")

    if issues:
        lines.append(f"Issues atribuídas ({len(issues)}):")
        for i in issues[:3]:
            repo = i.get("repo") or "?"
            lines.append(f"  • {repo}#{i.get('number')} — {i.get('title', '')[:50]}")

    if ci:
        lines.append("CI falhou:")
        for c in ci[:3]:
            lines.append(f"  • {c.get('repo')} — {c.get('name', 'workflow')[:40]}")

    if not prs_review and not issues and not ci and prs_open:
        pass  # already showed prs

    return lines


def build_inbox_telegram(data: dict | None = None) -> str:
    return "\n".join(build_inbox_lines(data))

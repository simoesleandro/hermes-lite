"""Webhook GitHub — notifica Telegram quando CI falha."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

logger = logging.getLogger("hermes.github_webhook")


def webhook_enabled() -> bool:
    return os.getenv("GITHUB_WEBHOOK_ENABLED", "1") == "1"


def verify_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET não configurado — webhook rejeitado")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _notify_telegram(text: str) -> bool:
    try:
        from cronos.notifier import notify

        notify(text, title="GitHub CI")
        return True
    except Exception as exc:
        logger.error("telegram webhook notify: %s", exc)
        return False


def _format_workflow_failure(payload: dict) -> str | None:
    run = payload.get("workflow_run") or {}
    if run.get("conclusion") != "failure":
        return None
    repo = (payload.get("repository") or {}).get("full_name", "?")
    name = run.get("name") or "workflow"
    branch = run.get("head_branch") or "?"
    url = run.get("html_url") or ""
    actor = (run.get("actor") or {}).get("login") or "?"
    lines = [
        f"❌ CI falhou — {repo}",
        f"Workflow: {name}",
        f"Branch: {branch}",
        f"Autor: {actor}",
    ]
    if url:
        lines.append(url)
    return "\n".join(lines)


def _format_check_suite_failure(payload: dict) -> str | None:
    suite = payload.get("check_suite") or {}
    if suite.get("conclusion") != "failure":
        return None
    repo = (payload.get("repository") or {}).get("full_name", "?")
    branch = suite.get("head_branch") or "?"
    url = suite.get("html_url") or ""
    lines = [
        f"❌ Checks falharam — {repo}",
        f"Branch: {branch}",
    ]
    if url:
        lines.append(url)
    return "\n".join(lines)


def handle_github_webhook(event: str, payload: dict) -> dict:
    """Processa evento GitHub; retorna {ok, notified, event}."""
    if not webhook_enabled():
        return {"ok": False, "reason": "disabled"}

    message: str | None = None
    action = payload.get("action", "")

    if event == "workflow_run" and action == "completed":
        message = _format_workflow_failure(payload)
    elif event == "check_suite" and action == "completed":
        message = _format_check_suite_failure(payload)

    if not message:
        return {"ok": True, "notified": False, "event": event, "action": action}

    notified = _notify_telegram(message)
    return {"ok": True, "notified": notified, "event": event, "action": action}

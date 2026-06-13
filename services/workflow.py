"""Workflows duráveis — pipeline Investigador → Jurídico → export MD."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("hermes.workflow")

EXPORTS_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "exports"


def strip_agent_prefix(text: str) -> str:
    if text.startswith("🤖"):
        parts = text.split("\n\n", 1)
        return parts[1] if len(parts) > 1 else text
    return text


def write_parecer_export(
    workflow_id: str,
    dossier: str,
    parecer: str,
    sources: list | None = None,
    meta: dict | None = None,
) -> str:
    EXPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"parecer-{ts}-{workflow_id[:8]}.md"
    path = EXPORTS_DIR / filename
    lines = [
        "# Parecer — Pipeline Hermes Lite",
        "",
        f"Workflow: `{workflow_id}`",
        f"Gerado: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    if meta:
        for k, v in meta.items():
            if v:
                lines.append(f"- **{k}**: {v}")
        lines.append("")
    lines.extend([
        "## Dossiê investigativo",
        "",
        dossier.strip(),
        "",
        "## Parecer jurídico",
        "",
        parecer.strip(),
    ])
    if sources:
        lines.extend(["", "## Fontes", ""])
        for s in sources:
            n = s.get("n", "?")
            title = s.get("title", "")
            url = s.get("url", "")
            line = f"- [{n}] {title}"
            if url:
                line += f" — {url}"
            lines.append(line)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _run_investigacao_parecer(workflow_id: str, db_path: str | None = None) -> None:
    from db.database import Database
    from services.agent_hub import AgentHub
    from services.handoff import build_investigador_handoff_message, build_juridico_handoff_message

    db = Database(path=db_path) if db_path else Database()
    hub = AgentHub(db=db)
    session_id = f"workflow-{workflow_id}"

    def _step(step: str, extra: dict | None = None) -> None:
        out = {"step": step}
        if extra:
            out.update(extra)
        db.update_workflow(workflow_id, status="running", output_json=out)

    try:
        wf = db.get_workflow(workflow_id)
        if not wf:
            return
        inp = json.loads(wf.get("input_json") or "{}")
        dossier = (inp.get("dossier") or "").strip()
        sources = inp.get("sources") or []
        alert = inp.get("alert")
        context = (inp.get("context") or "").strip()

        if not dossier:
            _step("investigador")
            if alert:
                raw, _ = hub.handoff_investigador(session_id, alert=alert, context=context)
            else:
                inv_msg = build_investigador_handoff_message(context, None)
                raw, _ = hub.chat(inv_msg, session_id, agent_name="investigador", skill_id="rapido")
            dossier = strip_agent_prefix(raw)

        _step("juridico", {"dossier_chars": len(dossier)})
        j_msg = build_juridico_handoff_message(dossier, sources)
        raw_p, _ = hub.chat(j_msg, session_id, agent_name="juridico", skill_id="parecer")
        parecer = strip_agent_prefix(raw_p)

        _step("export")
        meta = {}
        if alert and alert.get("fornecedor"):
            meta["fornecedor"] = alert["fornecedor"]
        export_path = write_parecer_export(workflow_id, dossier, parecer, sources, meta)

        db.update_workflow(
            workflow_id,
            status="done",
            output_json={
                "step": "done",
                "export_path": export_path,
                "export_filename": os.path.basename(export_path),
                "dossier_chars": len(dossier),
                "parecer_chars": len(parecer),
            },
        )
        logger.info("workflow %s done → %s", workflow_id, export_path)
    except Exception as exc:
        logger.exception("workflow %s failed", workflow_id)
        db.update_workflow(workflow_id, status="failed", error=str(exc)[:500])


def start_investigacao_parecer(
    db,
    *,
    context: str = "",
    alert: dict | None = None,
    dossier: str | None = None,
    sources: list | None = None,
) -> str:
    wf_id = str(uuid.uuid4())
    payload = {
        "context": context,
        "alert": alert,
        "dossier": dossier,
        "sources": sources or [],
    }
    db.create_workflow(wf_id, "investigacao_parecer", payload)
    db_path = db.path if hasattr(db, "path") else None
    threading.Thread(
        target=_run_investigacao_parecer,
        args=(wf_id, db_path),
        daemon=True,
    ).start()
    return wf_id

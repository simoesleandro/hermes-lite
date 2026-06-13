"""Shared Flask application factory for app.py and api_server.py."""

import json
import os
import re
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

from agents.analista import AnalistaAgent
from agents.conhecimento import ConhecimentoAgent
from agents.desenvolvimento import DesenvolvimentoAgent
from agents.investigador import InvestigadorAgent
from agents.juridico import JuridicoAgent
from agents.leitor_pdf import LeitorPDFAgent
from agents.ops import OpsAgent
from agents.radar import RadarAgent
from agents.produtividade import ProdutividadeAgent
from agents.saude import SaudeAgent
from agents.sentinela import SentinelaAgent
from agents.treino import TreinoAgent
from db.database import Database
from services.sentinela_client import SentinelaClient

load_dotenv()

# ── Agent auto-routing ────────────────────────────────────────────────────────

_RULES = [
    (re.compile(
        r"\b(ativar|parar|reiniciar|desligar|iniciar|ligar)\b"
        r"|status\s+(dos\s+)?servi"
        r"|\bsc\s+(start|stop|query|restart)\b"
        r"|qual\s+servi"
        r"|hermes\s+online"
        r"|\bservi[cç]o\b"
        r"|\b(cronos|vigia)\b",
        re.I,
    ), "ops"),
    (re.compile(r"bebi|água|peso|hrv|sono|calorias|hidrat", re.I), "saude"),
    (re.compile(r"treino|muscula|corrida|ppl|série|repetição|supino", re.I), "treino"),
    (re.compile(r"código|bug|python|refator|arquitetura|função|classe", re.I), "desenvolvimento"),
    (re.compile(
        r"fornecedor|top\s*\d+|ranking|maior valor|sentinela\s*db|quais\s+os|"
        r"liste\s+os\s+contratos|gráfico|analisar dados|visualizar|dashboard|planilha",
        re.I,
    ), "analista"),
    (re.compile(r"lei\b|cláusula|processo judicial|advogado|recurso\b|impugnar|jurídico", re.I), "juridico"),
    (re.compile(r"contrato público|pncp|licitação|anomalia|dispensa", re.I), "sentinela"),
    (re.compile(r"pesquis|investig|buscar na web|notícia", re.I), "investigador"),
    (re.compile(r"pdf|documento|resumir arquivo|anexo", re.I), "leitor"),
    (re.compile(r"tarefa|agenda|lembrete|produtividade|organizar", re.I), "produtividade"),
    (re.compile(
        r"github|reposit[oó]rio|open\s*source|radar\s*github|trending|stars?|"
        r"curadoria|repo do dia|biblioteca nova",
        re.I,
    ), "radar"),
]


_VALID_AGENTS = frozenset({
    "conhecimento", "saude", "treino", "desenvolvimento", "analista",
    "juridico", "sentinela", "investigador", "leitor", "produtividade", "ops", "radar",
})

_CLASSIFY_SYSTEM = """Você roteia mensagens para um agente do Hermes Lite.
Responda APENAS com o nome exato do agente, sem pontuação nem explicação.

Agentes:
- conhecimento: perguntas gerais
- saude: água, peso, sono, HRV, nutrição
- treino: exercícios, musculação, corrida
- desenvolvimento: código, bugs, programação
- analista: SQL, gráficos, rankings, consultas Sentinela DB
- juridico: leis, cláusulas, processos, pareceres
- sentinela: irregularidades, PNCP, licitações, alertas
- investigador: pesquisa web, notícias, dossiês
- leitor: PDFs e documentos
- produtividade: tarefas, agenda, organização
- ops: serviços Windows, Cronos, Vigia, status do sistema
- radar: curadoria GitHub, repos open source, digest diário"""


def classify_agent_regex_matches(message: str) -> list[str]:
    matches: list[str] = []
    for pattern, agent in _RULES:
        if pattern.search(message):
            matches.append(agent)
    return matches


def _classify_agent_llm(message: str, candidates: list[str] | None = None) -> str:
    from model_router import Complexity, get_completion

    hint = ""
    if candidates:
        hint = f"\nCandidatos das regras regex: {', '.join(candidates)}. Escolha o mais adequado."
    raw = get_completion(
        [
            {"role": "system", "content": _CLASSIFY_SYSTEM + hint},
            {"role": "user", "content": message},
        ],
        Complexity.SIMPLE,
    ).strip().lower()

    for token in re.split(r"[\s,.;:!?]+", raw):
        token = token.strip("'\"")
        if token in _VALID_AGENTS:
            return token
    for agent in _VALID_AGENTS:
        if agent in raw:
            return agent
    return "conhecimento"


def _classify_llm_enabled() -> bool:
    if os.getenv("CLASSIFY_LLM_FALLBACK", "1") != "1":
        return False
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY"))


def _classify_llm_disambiguate() -> bool:
    return os.getenv("CLASSIFY_LLM_DISAMBIGUATE", "0") == "1"


def classify_agent(
    message: str,
    *,
    llm_fallback: bool | None = None,
    llm_disambiguate: bool | None = None,
) -> str:
    message = (message or "").strip()
    if not message:
        return "conhecimento"

    matches = classify_agent_regex_matches(message)
    if len(matches) == 1:
        return matches[0]

    use_llm = llm_fallback if llm_fallback is not None else _classify_llm_enabled()
    disambiguate = llm_disambiguate if llm_disambiguate is not None else _classify_llm_disambiguate()

    if use_llm and not matches:
        try:
            return _classify_agent_llm(message)
        except Exception:
            pass

    if matches and len(matches) > 1 and use_llm and disambiguate:
        try:
            picked = _classify_agent_llm(message, candidates=matches)
            if picked in matches:
                return picked
        except Exception:
            pass

    if matches:
        return matches[0]
    return "conhecimento"


_PDF_SESSIONS: dict = {}
_PDF_MAX_SESSIONS = 50

_IMAGE_SESSIONS: dict[str, dict] = {}
_IMAGE_MAX_SESSIONS = 50

_OPS_ALLOWED_SERVICES = {"HermesCronos", "HermesVigia", "HermesLite"}
_OPS_ALLOWED_ACTIONS = {"start", "stop", "restart"}


def _pop_image(image_id: str | None) -> str | None:
    if not image_id:
        return None
    img = _IMAGE_SESSIONS.pop(image_id, None)
    if not img:
        return None
    return f"data:{img['mime']};base64,{img['base64']}"


def create_app(*, enable_cors: bool = False) -> Flask:
    app = Flask(__name__, static_folder="static")
    db = Database()
    sentinela = SentinelaClient()

    agents = {
        "saude": SaudeAgent(db=db),
        "conhecimento": ConhecimentoAgent(db=db),
        "desenvolvimento": DesenvolvimentoAgent(db=db),
        "produtividade": ProdutividadeAgent(db=db),
        "sentinela": SentinelaAgent(db=db),
        "treino": TreinoAgent(db=db),
        "juridico": JuridicoAgent(db=db),
        "investigador": InvestigadorAgent(db=db),
        "leitor": LeitorPDFAgent(db=db),
        "analista": AnalistaAgent(db=db),
        "ops": OpsAgent(db=db),
        "radar": RadarAgent(db=db),
    }

    if enable_cors:

        @app.after_request
        def _cors(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
            return response

    @app.route("/")
    def index():
        return send_from_directory("static", "index.html")

    @app.route("/chat/classify")
    def chat_classify():
        q = request.args.get("q", "").strip()
        matches = classify_agent_regex_matches(q)
        agent = classify_agent(q)
        source = "regex" if len(matches) == 1 else ("llm" if not matches and agent != "conhecimento" else "default")
        return jsonify({"agent": agent, "source": source, "candidates": matches})

    @app.route("/api/conversations", methods=["POST"])
    def create_conversation_route():
        data = request.get_json(force=True)
        conv_id = data.get("id", "").strip()
        title = data.get("title", "").strip()
        agent = data.get("agent", "conhecimento").lower()
        if not conv_id or not title:
            return jsonify({"error": "id e title são obrigatórios"}), 400
        db.create_conversation(conv_id, title, agent)
        return jsonify({"ok": True})

    @app.route("/api/conversations")
    def list_conversations_route():
        convs = db.get_conversations(limit=50)
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        groups: dict = {"Hoje": [], "Ontem": [], "Últimos 7 dias": [], "Mais antigo": []}
        for c in convs:
            d = datetime.fromisoformat(c["created_at"]).date()
            if d == today:
                groups["Hoje"].append(c)
            elif d == yesterday:
                groups["Ontem"].append(c)
            elif d >= week_ago:
                groups["Últimos 7 dias"].append(c)
            else:
                groups["Mais antigo"].append(c)

        return jsonify({"groups": {k: v for k, v in groups.items() if v}})

    @app.route("/api/conversations/search")
    def search_conversations_route():
        q = request.args.get("q", "").strip()
        agent = request.args.get("agent", "").strip() or None
        if not q:
            return jsonify({"results": []})
        results = db.search_conversations(q, agent=agent, limit=30)
        return jsonify({"results": results})

    @app.route("/api/conversations/<conv_id>")
    def get_conversation_route(conv_id: str):
        meta = db.get_conversation(conv_id)
        if not meta:
            return jsonify({"error": "conversa não encontrada"}), 404
        messages = db.get_conversation_messages(conv_id)
        return jsonify({"conversation": meta, "messages": messages})

    @app.route("/api/conversations/<conv_id>", methods=["PATCH"])
    def update_conversation_route(conv_id: str):
        data = request.get_json(force=True)
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title é obrigatório"}), 400
        if not db.update_conversation(conv_id, title):
            return jsonify({"error": "conversa não encontrada"}), 404
        return jsonify({"ok": True, "title": title[:80]})

    @app.route("/api/conversations/<conv_id>", methods=["DELETE"])
    def delete_conversation_route(conv_id: str):
        if not db.delete_conversation(conv_id):
            return jsonify({"error": "conversa não encontrada"}), 404
        return jsonify({"ok": True})

    @app.route("/api/conversations/<conv_id>/export")
    def export_conversation_route(conv_id: str):
        fmt = request.args.get("format", "md").lower()
        if fmt != "md":
            return jsonify({"error": "formato não suportado"}), 400
        meta = db.get_conversation(conv_id)
        if not meta:
            return jsonify({"error": "conversa não encontrada"}), 404
        md = db.export_conversation_markdown(conv_id)
        return Response(
            md,
            mimetype="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="hermes-{conv_id[:8]}.md"'},
        )

    @app.route("/api/sentinela/resumo")
    def sentinela_resumo_route():
        resumo = sentinela.get_resumo()
        stats = sentinela.get_estatisticas()
        alertas = sentinela.get_alertas(limit=5)
        top = sentinela.top_contratos(limit=5)
        por_sev = {}
        if not stats.get("offline"):
            for row in stats.get("alertas_por_severidade", []):
                por_sev[row.get("severidade", "?")] = row.get("total", 0)
        return jsonify({
            "resumo": resumo,
            "alertas_por_severidade": por_sev,
            "alertas_criticos": alertas,
            "top_contratos": top,
        })

    @app.route("/api/skills")
    def list_skills_route():
        from agents.skills import list_skills
        agent = request.args.get("agent", "").strip() or None
        return jsonify({"skills": list_skills(agent)})

    @app.route("/api/tasks")
    def list_tasks_route():
        status = request.args.get("status", "").strip() or None
        include_done = request.args.get("include_done", "").lower() in ("1", "true", "yes")
        tasks = db.list_tasks(status=status, include_done=include_done)
        return jsonify({"tasks": tasks, "summary": db.tasks_summary()})

    @app.route("/api/tasks", methods=["POST"])
    def create_task_route():
        data = request.get_json(force=True)
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title é obrigatório"}), 400
        status = (data.get("status") or "inbox").lower()
        if status not in ("inbox", "today", "week", "done"):
            return jsonify({"error": "status inválido"}), 400
        priority = (data.get("priority") or "medium").lower()
        if priority not in ("low", "medium", "high"):
            priority = "medium"
        task_id = data.get("id") or str(uuid.uuid4())
        db.create_task(task_id, title, status=status, priority=priority, notes=data.get("notes"))
        return jsonify({"ok": True, "id": task_id})

    @app.route("/api/tasks/<task_id>", methods=["PATCH"])
    def update_task_route(task_id: str):
        data = request.get_json(force=True)
        if not db.get_task(task_id):
            return jsonify({"error": "tarefa não encontrada"}), 404
        ok = db.update_task(
            task_id,
            title=data.get("title"),
            status=data.get("status"),
            priority=data.get("priority"),
            notes=data.get("notes"),
        )
        if not ok and not any(k in data for k in ("title", "status", "priority", "notes")):
            return jsonify({"error": "nada para atualizar"}), 400
        return jsonify({"ok": True})

    @app.route("/api/tasks/<task_id>", methods=["DELETE"])
    def delete_task_route(task_id: str):
        if not db.delete_task(task_id):
            return jsonify({"error": "tarefa não encontrada"}), 404
        return jsonify({"ok": True})

    @app.route("/api/facts")
    def list_facts_route():
        category = request.args.get("category") or None
        return jsonify({"facts": db.list_facts(category=category)})

    @app.route("/api/facts", methods=["POST"])
    def upsert_fact_route():
        data = request.get_json(force=True)
        key = (data.get("key") or "").strip()
        value = (data.get("value") or "").strip()
        if not key or not value:
            return jsonify({"error": "key e value são obrigatórios"}), 400
        db.upsert_fact(key, value, category=data.get("category"))
        return jsonify({"ok": True, "key": key})

    @app.route("/api/facts/<key>", methods=["DELETE"])
    def delete_fact_route(key: str):
        if not db.delete_fact(key):
            return jsonify({"error": "fato não encontrado"}), 404
        return jsonify({"ok": True})

    @app.route("/api/workflows", methods=["POST"])
    def create_workflow_route():
        from services.workflow import start_investigacao_parecer

        data = request.get_json(force=True)
        wf_type = (data.get("type") or "investigacao_parecer").strip()
        if wf_type != "investigacao_parecer":
            return jsonify({"error": "tipo de workflow inválido"}), 400
        context = (data.get("context") or data.get("text") or "").strip()
        alert = data.get("alert") if isinstance(data.get("alert"), dict) else None
        dossier = (data.get("dossier") or "").strip() or None
        sources = data.get("sources") if isinstance(data.get("sources"), list) else []
        if not dossier and not context and not alert:
            return jsonify({"error": "informe context, alert ou dossier"}), 400
        wf_id = start_investigacao_parecer(
            db, context=context, alert=alert, dossier=dossier, sources=sources,
        )
        return jsonify({"id": wf_id, "status": "pending", "type": wf_type})

    @app.route("/api/workflows")
    def list_workflows_route():
        return jsonify({"workflows": db.list_workflows(limit=30)})

    @app.route("/api/workflows/<wf_id>")
    def get_workflow_route(wf_id: str):
        wf = db.get_workflow(wf_id)
        if not wf:
            return jsonify({"error": "workflow não encontrado"}), 404
        return jsonify(wf)

    @app.route("/api/workflows/<wf_id>/export")
    def export_workflow_route(wf_id: str):
        from pathlib import Path
        from services.workflow import EXPORTS_DIR

        wf = db.get_workflow(wf_id)
        if not wf or wf.get("status") != "done":
            return jsonify({"error": "export indisponível"}), 404
        out = wf.get("output_json") or {}
        path = out.get("export_path")
        if not path:
            return jsonify({"error": "caminho ausente"}), 404
        resolved = Path(path).resolve()
        if not resolved.is_file() or EXPORTS_DIR.resolve() not in resolved.parents:
            return jsonify({"error": "arquivo não encontrado"}), 404
        return send_from_directory(resolved.parent, resolved.name, as_attachment=True)

    @app.route("/api/radar/latest")
    def radar_latest_route():
        digest = db.get_latest_github_digest()
        if not digest:
            return jsonify({"digest": None})
        return jsonify({"digest": digest})

    @app.route("/api/radar/run", methods=["POST"])
    def radar_run_route():
        from services.github_radar import run_github_radar
        result = run_github_radar(db, notify=False)
        return jsonify(result)

    @app.route("/api/radar/digest/<date>")
    def radar_digest_route(date: str):
        digest = db.get_github_digest_by_date(date)
        if not digest:
            return jsonify({"error": "digest não encontrado"}), 404
        return jsonify({"digest": digest})

    @app.route("/api/radar/export/<date>")
    def radar_export_route(date: str):
        from pathlib import Path
        from services.github_radar import EXPORTS_DIR
        digest = db.get_github_digest_by_date(date)
        path = (digest or {}).get("file_path")
        if not path:
            fallback = EXPORTS_DIR / f"{date}.md"
            if fallback.is_file():
                path = str(fallback)
            else:
                return jsonify({"error": "arquivo não encontrado"}), 404
        resolved = Path(path).resolve()
        if not resolved.is_file() or EXPORTS_DIR.resolve() not in resolved.parents:
            return jsonify({"error": "forbidden"}), 403
        return send_from_directory(resolved.parent, resolved.name, as_attachment=True)

    @app.route("/api/handoff/juridico", methods=["POST"])
    def handoff_juridico_route():
        from services.handoff import build_juridico_handoff_message

        data = request.get_json(force=True)
        dossier = (data.get("dossier") or data.get("investigation") or "").strip()
        if not dossier:
            return jsonify({"error": "dossier é obrigatório"}), 400
        sources = data.get("sources") or []
        message = build_juridico_handoff_message(dossier, sources)
        return jsonify({"agent": "juridico", "skill": "parecer", "message": message})

    @app.route("/api/handoff/investigador", methods=["POST"])
    def handoff_investigador_route():
        from services.handoff import build_investigador_handoff_message

        data = request.get_json(force=True)
        alert = data.get("alert") if isinstance(data.get("alert"), dict) else None
        context = (data.get("context") or data.get("text") or "").strip()
        if not alert and not context:
            return jsonify({"error": "alert ou context é obrigatório"}), 400
        message = build_investigador_handoff_message(context, alert)
        return jsonify({"agent": "investigador", "skill": "rapido", "message": message})

    @app.route("/api/knowledge")
    def list_knowledge_route():
        return jsonify({"documents": db.list_knowledge_docs()})

    @app.route("/api/knowledge/search")
    def search_knowledge_route():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"results": []})
        return jsonify({"results": db.search_knowledge(q)})

    @app.route("/api/knowledge", methods=["POST"])
    def ingest_knowledge_route():
        data = request.get_json(force=True)
        title = (data.get("title") or "").strip()
        text = (data.get("text") or "").strip()
        if not title or not text:
            return jsonify({"error": "title e text são obrigatórios"}), 400
        doc_id = data.get("id") or str(uuid.uuid4())
        n_chunks = db.ingest_knowledge_doc(
            doc_id, title, text,
            filename=data.get("filename"),
            source=data.get("source") or "upload",
        )
        return jsonify({"ok": True, "id": doc_id, "chunks": n_chunks})

    @app.route("/api/knowledge/<doc_id>", methods=["DELETE"])
    def delete_knowledge_route(doc_id: str):
        if not db.delete_knowledge_doc(doc_id):
            return jsonify({"error": "documento não encontrado"}), 404
        return jsonify({"ok": True})

    @app.route("/upload/pdf", methods=["POST"])
    def upload_pdf():
        if "file" not in request.files:
            return jsonify({"success": False, "error": "Nenhum arquivo enviado"}), 400

        f = request.files["file"]
        session_id = request.form.get("session_id", "")

        if not f.filename.lower().endswith(".pdf"):
            return jsonify({"success": False, "error": "Apenas arquivos PDF são aceitos"}), 400

        file_bytes = f.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            return jsonify({"success": False, "error": "Arquivo muito grande (máx. 10MB)"}), 400

        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            n_pages = len(doc)

            if n_pages > 100:
                return jsonify({
                    "success": False,
                    "error": f"Documento muito longo ({n_pages} páginas). Use um trecho menor (máx. 100 páginas).",
                }), 400

            truncated = False
            if n_pages > 20:
                pages_to_extract = list(range(20)) + list(range(max(20, n_pages - 5), n_pages))
                truncated = True
            else:
                pages_to_extract = list(range(n_pages))

            text = "\n\n".join(doc[i].get_text() for i in pages_to_extract)

            if session_id:
                if len(_PDF_SESSIONS) >= _PDF_MAX_SESSIONS:
                    del _PDF_SESSIONS[next(iter(_PDF_SESSIONS))]
                _PDF_SESSIONS[session_id] = {
                    "text": text,
                    "filename": f.filename,
                    "pages": n_pages,
                }

            persist = request.form.get("persist", "").lower() in ("1", "true", "yes")
            kb_id = None
            kb_chunks = 0
            if persist and text.strip():
                kb_id = str(uuid.uuid4())
                kb_chunks = db.ingest_knowledge_doc(
                    kb_id,
                    title=f.filename,
                    text=text,
                    filename=f.filename,
                    source="pdf",
                )

            return jsonify({
                "success": True,
                "filename": f.filename,
                "pages": n_pages,
                "chars": len(text),
                "text": text,
                "truncated": truncated,
                "knowledge_id": kb_id,
                "knowledge_chunks": kb_chunks,
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/upload/image", methods=["POST"])
    def upload_image():
        if "file" not in request.files:
            return jsonify({"success": False, "error": "Nenhum arquivo enviado"}), 400

        f = request.files["file"]
        ext = os.path.splitext(f.filename.lower())[1]
        if ext not in {".jpg", ".jpeg", ".png"}:
            return jsonify({"success": False, "error": "Apenas jpg e png são aceitos"}), 400

        file_bytes = f.read()
        if len(file_bytes) > 8 * 1024 * 1024:
            return jsonify({"success": False, "error": "Imagem muito grande (máx. 8MB)"}), 400

        import base64
        mime = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
        b64 = base64.b64encode(file_bytes).decode()
        image_id = str(uuid.uuid4())
        if len(_IMAGE_SESSIONS) >= _IMAGE_MAX_SESSIONS:
            del _IMAGE_SESSIONS[next(iter(_IMAGE_SESSIONS))]
        _IMAGE_SESSIONS[image_id] = {"base64": b64, "mime": mime, "filename": f.filename}
        return jsonify({
            "success": True,
            "image_id": image_id,
            "filename": f.filename,
            "size_kb": round(len(file_bytes) / 1024),
        })

    @app.route("/api/ops/service", methods=["POST"])
    def ops_service():
        data = request.get_json(force=True)
        action = data.get("action", "").lower()
        service = data.get("service", "")

        if service not in _OPS_ALLOWED_SERVICES:
            return jsonify({"error": "serviço não permitido"}), 403
        if action not in _OPS_ALLOWED_ACTIONS:
            return jsonify({"error": "ação não permitida"}), 400

        if action == "restart":
            r1 = subprocess.run(["sc", "stop", service], capture_output=True, text=True, timeout=15)
            time.sleep(2)
            r2 = subprocess.run(["sc", "start", service], capture_output=True, text=True, timeout=15)
            return jsonify({
                "ok": r2.returncode == 0,
                "output": f"[stop] {r1.stdout.strip()}\n[start] {r2.stdout.strip()}",
                "error": " | ".join(filter(None, [r1.stderr.strip(), r2.stderr.strip()])),
            })

        result = subprocess.run(["sc", action, service], capture_output=True, text=True, timeout=15)
        return jsonify({
            "ok": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
        })

    @app.route("/chat", methods=["POST"])
    def chat():
        data = request.get_json(force=True)
        message = data.get("message", "").strip()
        agent_name = data.get("agent", "conhecimento").lower()
        session_id = data.get("session_id") or str(uuid.uuid4())
        image_b64 = _pop_image(data.get("image_id") or None)

        if not message:
            return jsonify({"error": "Mensagem vazia"}), 400

        from services.facts import try_handle_facts
        fact_reply = try_handle_facts(message, db)
        if fact_reply:
            db.save_message(agent=agent_name, role="user", content=message, session_id=session_id)
            db.save_message(agent=agent_name, role="assistant", content=fact_reply, session_id=session_id)
            return jsonify({"agent": agent_name, "response": fact_reply, "source": "facts"})

        agent = agents.get(agent_name)
        if agent is None:
            return jsonify({"error": f"Agente '{agent_name}' não encontrado"}), 404

        response = agent.process(message, session_id, image_b64=image_b64)
        db.save_message(agent=agent_name, role="user", content=message, session_id=session_id)
        db.save_message(agent=agent_name, role="assistant", content=response, session_id=session_id)

        return jsonify({"agent": agent_name, "response": response})

    @app.route("/chat/stream")
    def chat_stream():
        message = request.args.get("message", "").strip()
        agent_name = request.args.get("agent", "conhecimento").lower()
        session_id = request.args.get("session_id") or str(uuid.uuid4())
        conv_id = request.args.get("conv_id") or None
        skill_id = request.args.get("skill") or None
        image_b64 = _pop_image(request.args.get("image_id") or None)

        if skill_id and message:
            from agents.skills import apply_skill
            message = apply_skill(agent_name, skill_id, message)

        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        if not message:
            def _err_empty():
                yield _sse({"error": "Mensagem vazia"})
            return Response(stream_with_context(_err_empty()), mimetype="text/event-stream")

        agent = agents.get(agent_name)
        if agent is None:
            def _err_agent():
                yield _sse({"error": f"Agente '{agent_name}' não encontrado"})
            return Response(stream_with_context(_err_agent()), mimetype="text/event-stream")

        from services.facts import try_handle_facts
        fact_reply = try_handle_facts(message, db)

        def generate():
            if fact_reply:
                db.save_message(
                    agent=agent_name, role="user", content=message,
                    session_id=session_id, conversation_id=conv_id,
                )
                db.save_message(
                    agent=agent_name, role="assistant", content=fact_reply,
                    session_id=session_id, conversation_id=conv_id,
                )
                yield _sse({"token": fact_reply})
                yield _sse({"done": True, "full_response": fact_reply, "provider": "local"})
                return

            from services.fact_extractor import schedule_fact_extraction
            schedule_fact_extraction(message, db)

            if agent_name == "leitor" and session_id in _PDF_SESSIONS:
                agent.set_pdf_context(**_PDF_SESSIONS[session_id])
            full_response: list[str] = []
            provider = "unknown"
            try:
                for item in agent.stream(
                    message, session_id, image_b64=image_b64, conversation_id=conv_id,
                ):
                    if isinstance(item, dict):
                        if "progress" in item:
                            yield _sse({"progress": item["progress"]})
                        elif "chart" in item:
                            yield _sse({"chart": item["chart"]})
                        elif "sources" in item:
                            yield _sse({"sources": item["sources"]})
                        else:
                            provider = item.get("provider", "unknown")
                    else:
                        full_response.append(item)
                        yield _sse({"token": item})
            except Exception as exc:
                yield _sse({"error": str(exc)})
                return

            complete = "".join(full_response)
            db.save_message(
                agent=agent_name, role="user", content=message,
                session_id=session_id, conversation_id=conv_id,
            )
            db.save_message(
                agent=agent_name, role="assistant", content=complete,
                session_id=session_id, conversation_id=conv_id,
            )
            yield _sse({"done": True, "full_response": complete, "provider": provider})

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.route("/chat/clear", methods=["POST"])
    def chat_clear():
        data = request.get_json(force=True)
        agent_name = data.get("agent", "conhecimento").lower()
        session_id = data.get("session_id") or ""

        if not session_id:
            return jsonify({"error": "session_id obrigatório"}), 400

        cleared = db.clear_history(agent=agent_name, session_id=session_id)
        return jsonify({"cleared": cleared})

    @app.route("/api/metrics")
    def api_metrics():
        from model_router import get_metrics
        return jsonify(get_metrics())

    @app.route("/api/status")
    def api_status():
        from services.health import get_health
        h = get_health()
        return jsonify({
            "providers": h["providers"],
            "services": h["services"],
            "timestamp": h["timestamp"],
        })

    @app.route("/api/health")
    def api_health():
        from services.health import get_health
        return jsonify(get_health())

    return app


def _check_groq() -> dict:
    from services.health import check_groq
    return check_groq()


def _check_gemini() -> dict:
    from services.health import check_gemini
    return check_gemini()


def _check_gemma() -> dict:
    from services.health import check_gemma
    return check_gemma()


def _check_syshealth() -> dict:
    from services.health import check_syshealth
    return check_syshealth()


def _check_sentinela() -> dict:
    from services.health import check_sentinela
    return check_sentinela()

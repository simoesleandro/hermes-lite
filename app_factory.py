"""Shared Flask application factory for app.py and api_server.py."""

import json
import os
import re
import subprocess
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
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
]


def classify_agent(message: str) -> str:
    for pattern, agent in _RULES:
        if pattern.search(message):
            return agent
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
    }

    if enable_cors:

        @app.after_request
        def _cors(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            return response

    @app.route("/")
    def index():
        return send_from_directory("static", "index.html")

    @app.route("/chat/classify")
    def chat_classify():
        q = request.args.get("q", "").strip()
        return jsonify({"agent": classify_agent(q)})

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
        messages = db.get_conversation_messages(conv_id)
        return jsonify({"messages": messages})

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

            return jsonify({
                "success": True,
                "filename": f.filename,
                "pages": n_pages,
                "chars": len(text),
                "text": text,
                "truncated": truncated,
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
        image_b64 = _pop_image(request.args.get("image_id") or None)

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

        def generate():
            if agent_name == "leitor" and session_id in _PDF_SESSIONS:
                agent.set_pdf_context(**_PDF_SESSIONS[session_id])
            full_response: list[str] = []
            provider = "unknown"
            try:
                for item in agent.stream(message, session_id, image_b64=image_b64):
                    if isinstance(item, dict):
                        if "progress" in item:
                            yield _sse({"progress": item["progress"]})
                        elif "chart" in item:
                            yield _sse({"chart": item["chart"]})
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
        checks = {
            "groq": _check_groq,
            "gemini": _check_gemini,
            "gemma": _check_gemma,
            "syshealth": _check_syshealth,
            "sentinela": _check_sentinela,
        }
        results: dict = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fn): name for name, fn in checks.items()}
            done, _ = futures_wait(futures, timeout=6)
            for future in done:
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception:
                    results[name] = {"status": "offline", "latency_ms": None}
        for future, name in futures.items():
            if name not in results:
                results[name] = {"status": "offline", "latency_ms": None}

        return jsonify({
            "providers": {k: results[k] for k in ("groq", "gemini", "gemma") if k in results},
            "services": {k: results[k] for k in ("syshealth", "sentinela") if k in results},
            "timestamp": datetime.utcnow().isoformat(),
        })

    return app


def _check_groq() -> dict:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"status": "offline", "latency_ms": None}
    try:
        from groq import Groq
        t = time.time()
        Groq(api_key=api_key).models.list()
        return {"status": "online", "latency_ms": round((time.time() - t) * 1000)}
    except Exception:
        return {"status": "offline", "latency_ms": None}


def _check_gemini() -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {"status": "offline", "latency_ms": None}
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        t = time.time()
        list(genai.list_models())
        return {"status": "online", "latency_ms": round((time.time() - t) * 1000)}
    except Exception:
        return {"status": "offline", "latency_ms": None}


def _check_gemma() -> dict:
    model_id = os.getenv("GEMMA_MODEL", "gemma-4-4b-it")
    if not os.getenv("GEMINI_API_KEY", ""):
        return {"status": "offline", "latency_ms": None, "model": model_id}
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        t = time.time()
        genai.GenerativeModel(model_id).generate_content("ping")
        return {"status": "online", "latency_ms": round((time.time() - t) * 1000), "model": model_id}
    except Exception:
        return {"status": "offline", "latency_ms": None, "model": model_id}


def _check_syshealth() -> dict:
    base = os.getenv("SYSHEALTH_URL", "http://localhost:5060").rstrip("/")
    try:
        req = urllib.request.Request(f"{base}/health")
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        return {"status": "online", "latency_ms": round((time.monotonic() - t0) * 1000)}
    except Exception:
        return {"status": "offline"}


def _check_sentinela() -> dict:
    from services.sentinela_client import SENTINELA_DB
    if not os.path.exists(SENTINELA_DB):
        return {"status": "offline", "contratos": None}
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{SENTINELA_DB}?mode=ro", uri=True)
        count = conn.execute("SELECT COUNT(*) FROM contratos").fetchone()[0]
        conn.close()
        return {"status": "online", "contratos": count}
    except Exception:
        return {"status": "offline", "contratos": None}

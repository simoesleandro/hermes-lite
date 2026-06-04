import json
import os
import re
import subprocess
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
from datetime import datetime, timedelta
from flask import Flask, Response, request, jsonify, send_from_directory, stream_with_context
from dotenv import load_dotenv
from agents.saude import SaudeAgent
from agents.conhecimento import ConhecimentoAgent
from agents.desenvolvimento import DesenvolvimentoAgent
from agents.produtividade import ProdutividadeAgent
from agents.sentinela import SentinelaAgent
from agents.treino import TreinoAgent
from agents.juridico import JuridicoAgent
from agents.investigador import InvestigadorAgent
from agents.leitor_pdf import LeitorPDFAgent
from agents.analista import AnalistaAgent
from agents.ops import OpsAgent
from db.database import Database

load_dotenv()

app = Flask(__name__, static_folder="static")
db = Database()

# ── Agent auto-routing ────────────────────────────────────────────────────────

_RULES = [
    (re.compile(r"\b(ativar|parar|reiniciar|desligar|iniciar)\s+(o\s+)?(cronos|vigia|hermes)", re.I), "ops"),
    (re.compile(r"bebi|água|peso|hrv|sono|calorias|hidrat", re.I), "saude"),
    (re.compile(r"treino|muscula|corrida|ppl|série|repetição|supino", re.I), "treino"),
    (re.compile(r"código|bug|python|refator|arquitetura|função|classe", re.I), "desenvolvimento"),
    # analista antes de sentinela/juridico — perguntas analíticas sobre contratos vão aqui
    (re.compile(r"fornecedor|top\s*\d+|ranking|maior valor|sentinela\s*db|quais\s+os|liste\s+os\s+contratos|gráfico|analisar dados|visualizar|dashboard|planilha", re.I), "analista"),
    # juridico antes de sentinela — termos legais explícitos têm prioridade sobre termos de procurement
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

AGENTS = {
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
    "ops":      OpsAgent(db=db),
}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/chat/classify")
def chat_classify():
    q = request.args.get("q", "").strip()
    return jsonify({"agent": classify_agent(q)})


@app.route("/api/conversations", methods=["POST"])
def create_conversation_route():
    data    = request.get_json(force=True)
    conv_id = data.get("id", "").strip()
    title   = data.get("title", "").strip()
    agent   = data.get("agent", "conhecimento").lower()
    if not conv_id or not title:
        return jsonify({"error": "id e title são obrigatórios"}), 400
    db.create_conversation(conv_id, title, agent)
    return jsonify({"ok": True})


@app.route("/api/conversations")
def list_conversations_route():
    convs     = db.get_conversations(limit=50)
    today     = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    week_ago  = today - timedelta(days=7)

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


@app.route("/api/conversations/<conv_id>")
def get_conversation_route(conv_id: str):
    messages = db.get_conversation_messages(conv_id)
    return jsonify({"messages": messages})


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


_OPS_ALLOWED_SERVICES = {"HermesCronos", "HermesVigia", "HermesLite"}
_OPS_ALLOWED_ACTIONS  = {"start", "stop", "restart"}


@app.route("/api/ops/service", methods=["POST"])
def ops_service():
    data    = request.get_json(force=True)
    action  = data.get("action", "").lower()
    service = data.get("service", "")

    if service not in _OPS_ALLOWED_SERVICES:
        return jsonify({"error": "serviço não permitido"}), 403
    if action not in _OPS_ALLOWED_ACTIONS:
        return jsonify({"error": "ação não permitida"}), 400

    if action == "restart":
        r1 = subprocess.run(["sc", "stop",  service], capture_output=True, text=True, timeout=15)
        time.sleep(2)
        r2 = subprocess.run(["sc", "start", service], capture_output=True, text=True, timeout=15)
        return jsonify({
            "ok":     r2.returncode == 0,
            "output": f"[stop] {r1.stdout.strip()}\n[start] {r2.stdout.strip()}",
            "error":  " | ".join(filter(None, [r1.stderr.strip(), r2.stderr.strip()])),
        })

    result = subprocess.run(["sc", action, service], capture_output=True, text=True, timeout=15)
    return jsonify({
        "ok":     result.returncode == 0,
        "output": result.stdout.strip(),
        "error":  result.stderr.strip(),
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    agent_name = data.get("agent", "conhecimento").lower()
    session_id = data.get("session_id") or str(uuid.uuid4())

    if not message:
        return jsonify({"error": "Mensagem vazia"}), 400

    agent = AGENTS.get(agent_name)
    if agent is None:
        return jsonify({"error": f"Agente '{agent_name}' não encontrado"}), 404

    response = agent.process(message, session_id)
    db.save_message(agent=agent_name, role="user", content=message, session_id=session_id)
    db.save_message(agent=agent_name, role="assistant", content=response, session_id=session_id)

    return jsonify({"agent": agent_name, "response": response})


@app.route("/chat/stream")
def chat_stream():
    message    = request.args.get("message", "").strip()
    agent_name = request.args.get("agent", "conhecimento").lower()
    session_id = request.args.get("session_id") or str(uuid.uuid4())
    conv_id    = request.args.get("conv_id") or None

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    if not message:
        def _err_empty():
            yield _sse({"error": "Mensagem vazia"})
        return Response(stream_with_context(_err_empty()), mimetype="text/event-stream")

    agent = AGENTS.get(agent_name)
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
            for item in agent.stream(message, session_id):
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
        db.save_message(agent=agent_name, role="user",      content=message,  session_id=session_id, conversation_id=conv_id)
        db.save_message(agent=agent_name, role="assistant", content=complete,  session_id=session_id, conversation_id=conv_id)
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


# ── Provider / service health checks ─────────────────────────────────────────

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


def _check_ollama() -> dict:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        t = time.time()
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        return {"status": "online", "latency_ms": round((time.time() - t) * 1000)}
    except Exception:
        return {"status": "offline", "latency_ms": None}


def _check_syshealth() -> dict:
    try:
        req = urllib.request.Request("http://localhost:5060/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
        return {"status": "online"}
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


@app.route("/api/status")
def api_status():
    checks = {
        "groq":      _check_groq,
        "gemini":    _check_gemini,
        "ollama":    _check_ollama,
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
        "providers": {k: results[k] for k in ("groq", "gemini", "ollama") if k in results},
        "services":  {k: results[k] for k in ("syshealth", "sentinela") if k in results},
        "timestamp": datetime.utcnow().isoformat(),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5050)

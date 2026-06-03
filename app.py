import json
import uuid
from flask import Flask, Response, request, jsonify, send_from_directory, stream_with_context
from dotenv import load_dotenv
from agents.saude import SaudeAgent
from agents.conhecimento import ConhecimentoAgent
from agents.desenvolvimento import DesenvolvimentoAgent
from agents.produtividade import ProdutividadeAgent
from agents.sentinela import SentinelaAgent
from db.database import Database
import os

load_dotenv()

app = Flask(__name__, static_folder="static")
db = Database()

AGENTS = {
    "saude": SaudeAgent(db=db),
    "conhecimento": ConhecimentoAgent(db=db),
    "desenvolvimento": DesenvolvimentoAgent(db=db),
    "produtividade": ProdutividadeAgent(db=db),
    "sentinela": SentinelaAgent(db=db),
}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


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
    message = request.args.get("message", "").strip()
    agent_name = request.args.get("agent", "conhecimento").lower()
    session_id = request.args.get("session_id") or str(uuid.uuid4())

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
        full_response: list[str] = []
        provider = "unknown"
        try:
            for item in agent.stream(message, session_id):
                if isinstance(item, dict):
                    provider = item.get("provider", "unknown")
                else:
                    full_response.append(item)
                    yield _sse({"token": item})
        except Exception as exc:
            yield _sse({"error": str(exc)})
            return

        complete = "".join(full_response)
        db.save_message(agent=agent_name, role="user", content=message, session_id=session_id)
        db.save_message(agent=agent_name, role="assistant", content=complete, session_id=session_id)
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


if __name__ == "__main__":
    app.run(debug=True, port=5050)

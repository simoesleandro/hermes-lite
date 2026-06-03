import uuid
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from agents.saude import SaudeAgent
from agents.conhecimento import ConhecimentoAgent
from agents.desenvolvimento import DesenvolvimentoAgent
from agents.produtividade import ProdutividadeAgent
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


if __name__ == "__main__":
    app.run(debug=True, port=5050)

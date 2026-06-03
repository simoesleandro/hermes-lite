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
    "saude": SaudeAgent(),
    "conhecimento": ConhecimentoAgent(),
    "desenvolvimento": DesenvolvimentoAgent(),
    "produtividade": ProdutividadeAgent(),
}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    agent_name = data.get("agent", "conhecimento").lower()

    if not message:
        return jsonify({"error": "Mensagem vazia"}), 400

    agent = AGENTS.get(agent_name)
    if agent is None:
        return jsonify({"error": f"Agente '{agent_name}' não encontrado"}), 404

    db.save_message(agent=agent_name, role="user", content=message)
    response = agent.process(message)
    db.save_message(agent=agent_name, role="assistant", content=response)

    return jsonify({"agent": agent_name, "response": response})


if __name__ == "__main__":
    app.run(debug=True, port=5050)

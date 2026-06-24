# Hermes Lite

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-F55036?logo=groq&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Gemma4_12B-white?logo=ollama&logoColor=black)
![Agents](https://img.shields.io/badge/Agents-12-7c3aed)
![Last Commit](https://img.shields.io/github/last-commit/simoesleandro/hermes-lite?color=8892b0)

> A local multi-agent AI assistant with real-time streaming, live data integration, and autonomous automation.

Hermes Lite is a personal AI platform featuring 12 specialized agents, automatic LLM routing with three-provider fallback, a Gemini-style web interface, an autonomous task scheduler, Telegram/Discord notifications, MCP tools, and a real-time system monitor.

---

## Agents

| Agent | Specialty | Complexity |
|-------|-----------|------------|
| Knowledge | General questions, research, and technology | Groq |
| Dev | Software development and architecture | Groq |
| Health | Personal health with live data from SysHealth API | Ollama |
| Training | Fitness and strength training with Hevy + Amazfit data | Groq |
| Productivity | GTD, task management, and focus | Groq |
| Sentinel | Public contract auditing for Rio de Janeiro (PNCP) | Groq |
| Legal | Administrative Law and Brazilian Bidding Act 14.133/2021 | Gemini |
| Investigator | Autonomous multi-source dossier with ReAct pattern | Gemini |
| PDF Reader | Document analysis and Q&A over uploaded PDFs | Gemini |
| Analyst | Python code generation, execution, and inline charts | Gemini |
| Ops | Windows service operations and health checks | Ollama |
| Radar | GitHub open-source curation and daily digests | Groq |

---

## Architecture

### Model Router — Automatic 3-level fallback

```
SIMPLE  →  Gemma 4 12B (Ollama)  →  Groq    →  Gemini
MEDIUM  →  Groq                  →  Gemini  →  Gemma 4
HEAVY   →  Gemini                →  Groq    →  Gemma 4
```

If the primary provider is unavailable, the system falls back to the next one automatically — no interruption for the user.

### Stack

- **Backend:** Python 3.11+ + Flask
- **Frontend:** Vanilla HTML/CSS/JS (no frameworks)
- **Database:** SQLite (`db/hermes.db`) for conversation history
- **LLMs:** Groq (`llama-3.3-70b-versatile`), Gemini 2.5 Flash, Ollama (`gemma4:12b`)
- **Streaming:** SSE (Server-Sent Events) — real-time token delivery
- **External services:** SysHealth API (health data), Sentinela RJ (public contracts)

### Project structure

```
hermes-lite/
├── app.py                    # Flask UI entry point
├── app_factory.py            # Flask factory and routes
├── mcp_server.py             # MCP server with 30+ tools
├── model_router.py           # LLM routing and fallback logic
├── agents/                   # 12 specialized agents
│   ├── base.py
│   ├── conhecimento.py
│   ├── desenvolvimento.py
│   ├── saude.py
│   ├── treino.py
│   ├── produtividade.py
│   ├── sentinela.py
│   ├── juridico.py
│   ├── investigador.py
│   ├── leitor_pdf.py
│   └── analista.py
├── services/                 # External service clients
│   ├── syshealth_client.py
│   ├── sentinela_client.py
│   ├── investigador_tools.py
│   └── analista_sandbox.py
├── cronos/                   # Autonomous scheduler
│   ├── cronos.py
│   ├── scheduler.py
│   ├── notifier.py
│   └── tasks/
├── vigia/                    # System monitor
│   ├── vigia.py
│   └── monitor.py
├── db/                       # Conversation history
├── static/                   # Frontend (HTML/CSS/JS)
├── hermes-lite-service.xml    # WinSW — main Flask service
├── cronos-service.xml        # WinSW — Cronos service
└── vigia-service.xml         # WinSW — Vigia service
```

---

## Features

- **Real-time streaming** — tokens delivered word by word via SSE
- **Session history** — UUID `session_id` isolated per browser tab
- **Provider badge** — shows which LLM responded (groq/gemini/ollama)
- **`/limpar` command** — resets conversation context
- **PDF upload** — 📎 button in the Reader agent (up to 10 MB, 100 pages)
- **Inline charts** — Analyst agent generates and displays PNGs directly in chat
- **Progress steps** — Investigator and Analyst stream step-by-step status in real time
- **ReAct pattern** — Investigator executes real tools (CNPJ lookup, contracts DB, web search)
- **MCP server** — 30+ tools for Cursor and Claude Desktop
- **GitHub Radar / Inbox** — daily open-source curation and PR/issue digests

---

## 🕐 Cronos — Autonomous Scheduler

Windows service that runs scheduled tasks and sends Discord notifications.

| Task | Schedule | Discord Channel |
|------|----------|----------------|
| ☀️ Daily briefing | 09:30 every day | `#briefing` |
| 📊 Health summary | 22:00 every day | `#saude` |
| 🔎 Sentinel weekly report | 09:30 every Monday | `#sentinela` |

**Run manually:**
```bash
python -m cronos.cronos
# Test mode (triggers all tasks immediately):
python -m cronos.cronos --test
```

---

## 👁️ Vigia — System Monitor

Checks 4 services every 5 minutes and sends Discord alerts when something goes down or recovers.

| Service | Check |
|---------|-------|
| Hermes Lite | HTTP `localhost:5050` |
| SysHealth API | HTTP `localhost:5060/health` |
| Ollama | HTTP `localhost:11434/api/tags` |
| Hermes Cronos | Windows Service `HermesCronos` |

Alerts only fire on state changes (no repeated spam). Sends an hourly heartbeat.

**Run manually:**
```bash
python -m vigia.vigia
```

---

## Installation

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running locally
- [Groq](https://console.groq.com) account (free tier available)
- [Google AI Studio](https://aistudio.google.com) account for Gemini

### Setup

```bash
git clone https://github.com/simoesleandro/hermes-lite
cd hermes-lite
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python app.py
```

Open: **http://localhost:5050**

### Environment variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `OLLAMA_BASE_URL` | Ollama base URL (default: `http://localhost:11434`) |
| `OLLAMA_GEMMA_MODEL` | Local Ollama model (default: `gemma4:12b`) |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL for sys-health |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `DISCORD_WEBHOOK_LOGS` | Discord webhook for logs and Vigia alerts |
| `DISCORD_WEBHOOK_BRIEFING` | Webhook for daily briefing (Cronos) |
| `DISCORD_WEBHOOK_SAUDE` | Webhook for health summary (Cronos) |
| `DISCORD_WEBHOOK_SENTINELA` | Webhook for weekly Sentinel report (Cronos) |

---

## Windows Services (WinSW)

To run Hermes Lite, Cronos and Vigia as background Windows services:

1. Download [WinSW](https://github.com/winsw/winsw/releases) and place the `.exe` at the project root
2. Rename it to match the service
3. Run as Administrator:

```cmd
# Hermes Lite
copy WinSW-x64.exe hermes-lite-service.exe
hermes-lite-service.exe install
hermes-lite-service.exe start

# Cronos
copy WinSW-x64.exe cronos-service.exe
cronos-service.exe install
cronos-service.exe start

# Vigia
copy WinSW-x64.exe vigia-service.exe
vigia-service.exe install
vigia-service.exe start
```

---

## Tests

```bash
python -m pytest -q
```

Current validation: **136 passed**.

---

## Author

**Leandro Simões** — [github.com/simoesleandro](https://github.com/simoesleandro)

# Hermes Lite

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey)
![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-orange)
![Gemini](https://img.shields.io/badge/Gemini-2.5--Flash-blue)
![Gemma](https://img.shields.io/badge/Gemma4-12B--local-violet)
![License](https://img.shields.io/badge/license-MIT-green)

**EN:** Personal AI operating system — 12 specialized agents, automatic LLM routing, persistent memory, RAG, GTD, GitHub radar, bidirectional Telegram and autonomous automations.

**PT:** Sistema operacional pessoal de IA — 12 agentes especializados, roteamento automático de LLM, memória persistente, RAG, GTD, radar GitHub, Telegram bidirecional e automações autônomas.

---

## Agentes / Agents

| Agente | Especialidade | Tier LLM | Dados / Ferramentas |
|--------|--------------|----------|---------------------|
| **conhecimento** | Perguntas gerais, pesquisa, tecnologia | MEDIUM | Memória `user_facts`, contexto RAG |
| **desenvolvimento** | Código, bugs, arquitetura, Git | MEDIUM | `git_status`, `git_diff`, `git_log` |
| **saude** | Nutrição, hidratação, peso, wearable | SIMPLE | Supabase sys-health: resumo diário; registra água e peso via chat |
| **treino** | Musculação, corrida, Hevy, Amazfit | MEDIUM | sys-health: treinos, análise, sono |
| **produtividade** | GTD, tarefas, foco | MEDIUM | Tabela `tasks` (inbox / today / week / done) |
| **sentinela** | Contratos públicos RJ, PNCP, alertas | MEDIUM | SQLite Sentinela RJ |
| **juridico** | Direito administrativo, Lei 14.133/2021 | HEAVY | Recebe handoffs do Investigador |
| **investigador** | Dossiê multi-fonte com ReAct pattern | HEAVY | CNPJ, contratos, alertas, busca web |
| **leitor** | PDFs — resumo e perguntas | HEAVY | Upload PDF (até 10 MB, 100 págs) |
| **analista** | SQL, Python, gráficos inline | HEAVY | Sandbox pandas/matplotlib/plotly |
| **ops** | Serviços Windows (Hermes, Cronos, Vigia) | SIMPLE | `sc start/stop`, health HTTP |
| **radar** | Curadoria GitHub open source | MEDIUM | GitHub Search API; digest diário |

---

## Arquitetura / Architecture

```
Model Router — fallback automático em 3 níveis:

SIMPLE  →  Gemma 4 (Ollama local)  →  Groq    →  Gemini
MEDIUM  →  Groq (llama-3.3-70b)    →  Gemini  →  Gemma 4
HEAVY   →  Gemini 2.5 Flash        →  Groq    →  Gemma 4

Canais de entrada:
  UI Web (porta 5050) → AgentHub → Model Router → LLM
  Telegram Bot        → AgentHub → Model Router → LLM
  MCP Server (stdio)  → AgentHub → Model Router → LLM

Dados externos:
  sys-health (Supabase PostgreSQL) — saúde pessoal
  Sentinela RJ (SQLite)           — contratos públicos
  GitHub API                      — radar e inbox

Automação:
  Cronos (scheduler) → Telegram / Discord
  Vigia (monitor)    → Discord
```

### Stack

| Camada | Tecnologia |
|--------|------------|
| Backend | Python 3.11+ · Flask · Waitress |
| Frontend | HTML/CSS/JS vanilla |
| Streaming | SSE (Server-Sent Events) |
| Banco local | SQLite (`db/hermes.db`) |
| LLMs | Gemma 4 12B (Ollama local) · Groq · Gemini API |
| Saúde | Supabase PostgreSQL (sys-health) |
| Automação | Cronos (scheduler) · Vigia (monitor) |
| IDE | MCP server — 30+ tools para Cursor / Claude Desktop |
| Testes | pytest — 136+ testes |

---

## Funcionalidades / Features

- 12 agentes especializados com roteamento automático por palavra-chave
- Model router com fallback — se um provider cair, o próximo é tentado sem interrupção
- Gemma 4 12B local via Ollama — custo zero, sem envio de dados
- Memória persistente — `user_facts` extraídos automaticamente das conversas
- RAG — base de conhecimento com busca semântica (Gemini embeddings)
- GTD — sistema de tarefas inbox/today/week/done via chat e API
- MCP server — 30+ ferramentas para Cursor e Claude Desktop
- Telegram bidirecional — chat completo, botões de ação, upload PDF/imagem
- Workflows duráveis — pipeline Investigador → Jurídico persistido no banco
- GitHub Radar — curadoria diária de repos open source com nota 0–10
- GitHub Inbox — PRs, reviews, issues, CI no digest matinal
- Webhook CI — notifica Telegram quando CI falha
- Busca FTS — full-text search nas conversas
- Export Markdown — download de qualquer conversa
- Gráficos inline — agente Analista gera e exibe PNGs no chat
- Backup automático — Cronos faz zip do banco às 03:00 (retenção 14 dias)

Guia completo: [`docs/GUIA-HERMES-LITE.md`](docs/GUIA-HERMES-LITE.md)

---

## MCP Server (Cursor / Claude Desktop)

```bash
python mcp_server.py
```

30+ ferramentas incluindo: `hermes_chat`, `list_agents`, `classify_message`, resumo Sentinela, busca fornecedor, registrar água/peso, GTD, RAG, git status/diff, GitHub inbox, radar, workflows, `telegram_notify` e mais.

Config: copiar `mcp-config.example.json` para o Cursor.

---

## Cronos — Scheduler Autônomo

| Tarefa | Horário (BRT) | Canal |
|--------|---------------|-------|
| ☀️ Digest matinal | 07:30 diário | Telegram / Discord |
| 📊 Resumo saúde | 22:00 diário | Telegram / Discord |
| 🔎 Relatório Sentinela | 09:30 segundas | Telegram / Discord |
| 💾 Backup banco | 03:00 diário | — |
| 🧠 Revisão user_facts | 10:00 domingos | Telegram |

```bash
python -m cronos.cronos
python -m cronos.cronos --test   # dispara tudo imediatamente
```

---

## Vigia — Monitor de Sistema

Verifica a cada 5 minutos: Hermes Lite, sys-health, Gemma Ollama, Cronos.

Alerta no Discord em mudanças de estado. Heartbeat a cada hora.

```bash
python -m vigia.vigia
```

---

## Instalação / Setup

```bash
git clone https://github.com/simoesleandro/hermes-lite
cd hermes-lite
pip install -r requirements.txt
cp .env.example .env
# Editar .env com suas chaves
python app.py
# → http://localhost:5050
```

### Pré-requisitos

- Python 3.11+
- Ollama com `gemma4:12b` (`ollama pull gemma4:12b`)
- Chave Groq (gratuita em [console.groq.com](https://console.groq.com))
- Chave Gemini (gratuita em [aistudio.google.com](https://aistudio.google.com))
- Supabase configurado (sys-health) — opcional

---

## Variáveis de Ambiente Essenciais

| Variável | Descrição |
|----------|-----------|
| `GROQ_API_KEY` | Groq — tier MEDIUM |
| `GEMINI_API_KEY` | Gemini Flash — tier HEAVY |
| `OLLAMA_GEMMA_MODEL` | Modelo local (padrão: `gemma4:12b`) |
| `NEXT_PUBLIC_SUPABASE_URL` | URL Supabase (sys-health) |
| `SUPABASE_SERVICE_ROLE_KEY` | Chave service role Supabase |
| `SENTINELA_DB_PATH` | SQLite Sentinela RJ |
| `GITHUB_TOKEN` | Radar + Inbox GitHub |
| `TELEGRAM_BOT_TOKEN` | Bot Telegram |
| `TELEGRAM_CHAT_ID` | Chat ID destino |
| `NOTIFY_CHANNEL` | `telegram`, `discord` ou `both` |

Lista completa: `.env.example`

---

## Serviços Windows (WinSW)

| Serviço | XML | Porta |
|---------|-----|-------|
| HermesLite | `hermes-service.xml` | 5050 |
| HermesCronos | `cronos-service.xml` | — |
| hermes-vigia | `vigia-service.xml` | — |

---

## Estrutura / Project Structure

```
hermes-lite/
├── app.py, api_server.py, app_factory.py
├── model_router.py
├── mcp_server.py              # MCP server — 30+ tools
├── agents/                    # 12 agentes
├── services/                  # Clientes externos, Telegram, RAG, workflows
├── db/                        # hermes.db + Database
├── cronos/                    # Scheduler + tasks/
├── vigia/                     # Monitor
├── static/                    # UI web
├── tests/                     # 136+ testes pytest
├── exports/                   # Pareceres, radar MD
└── backups/                   # Backups noturnos
```

---

## Autor / Author

**Leandro Simões** — [github.com/simoesleandro](https://github.com/simoesleandro) · [linkedin.com/in/leandro-simões](https://linkedin.com/in/leandro-simões)

Fullstack · IA Aplicada · Civic Tech

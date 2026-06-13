# Hermes Lite — Project Memory

Plataforma pessoal multi-agente (Flask + SSE + SQLite).

## Entry points

- `app.py` — UI local (porta 5050)
- `api_server.py` — mesmo app com CORS (`create_app(enable_cors=True)`)
- `app_factory.py` — rotas compartilhadas; **editar aqui** ao adicionar endpoints

## Agentes (11)

`conhecimento`, `desenvolvimento`, `saude`, `treino`, `produtividade`, `sentinela`, `juridico`, `investigador`, `leitor`, `analista`, `ops`

Roteamento automático: `classify_agent()` em `app_factory.py` (testes em `tests/test_classify_agent.py`).

## LLM

`model_router.py` — fallback por `Complexity` (SIMPLE/MEDIUM/HEAVY). Métricas em `/api/metrics`.

| Tier | Primary | Fallback |
|------|---------|----------|
| SIMPLE | Gemma 4 (`GEMMA_MODEL`) | Groq → Gemini |
| MEDIUM | Groq | Gemini → Gemma 4 |
| HEAVY | Gemini Flash | Groq → Gemma 4 |

Gemma 4 roda via **Gemini API** (mesma `GEMINI_API_KEY`), sem Ollama local.

## MCP Server

```bash
pip install mcp
python mcp_server.py   # stdio — Cursor / Claude Desktop
```

Config de exemplo: `mcp-config.example.json` (15 tools: Sentinela, SysHealth, Investigador, classify).

## Dados externos

- SysHealth: `SYSHEALTH_URL` — leitura + POST (`/api/agua`, `/api/peso`, `/api/tirzepatida`) via `SysHealthClient`
- Sentinela: `SENTINELA_DB_PATH` — SQLite read-only
- Analista sandbox: `SENTINELA_DB_PATH`, `SYSHEALTH_DB_PATH`

## Cronos / Vigia

- Cronos: Telegram por padrão; `NOTIFY_CHANNEL=telegram|discord|both`
- Vigia: Discord (`DISCORD_WEBHOOK_LOGS`)

## UI

- Sidebar com histórico, busca FTS (`/api/conversations/search`), export MD
- Painel Sentinela visível nos agentes `sentinela` e `juridico`

## Testes

```bash
pytest tests/
```

## Convenções

- Novos agentes: estender `BaseAgent`, registrar em `app_factory.create_app` → `agents` dict
- Sessões PDF/imagem em memória (não persistem entre restarts)

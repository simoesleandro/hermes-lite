# Hermes Lite — Project Memory

Plataforma pessoal multi-agente (Flask + SSE + SQLite).

## Entry points

- `app.py` — UI local (porta 5050; **dev atual: 5051** se serviço WinSW ocupa 5050)
- `api_server.py` — mesmo app com CORS (`create_app(enable_cors=True)`)
- `app_factory.py` — rotas compartilhadas; **editar aqui** ao adicionar endpoints

## Agentes (12)

`conhecimento`, `desenvolvimento`, `saude`, `treino`, `produtividade`, `sentinela`, `juridico`, `investigador`, `leitor`, `analista`, `ops`, `radar`

Roteamento automático: `classify_agent()` em `app_factory.py` (testes em `tests/test_classify_agent.py`).

## LLM

`model_router.py` — fallback por `Complexity` (SIMPLE/MEDIUM/HEAVY). Métricas em `/api/metrics`.

| Tier | Primary | Fallback |
|------|---------|----------|
| SIMPLE | Gemma 4 local (Ollama) | Groq → Gemini |
| MEDIUM | Groq | Gemini → Gemma 4 |
| HEAVY | Gemini Flash | Groq → Gemma 4 |

Gemma 4 roda **localmente via Ollama** (`gemma4:12b` por padrão) — custo zero, sem Gemini API.
Para voltar à API paga: `GEMMA_PROVIDER=gemini`.

## MCP Server

```bash
pip install mcp
python mcp_server.py   # stdio — Cursor / Claude Desktop
```

Config de exemplo: `mcp-config.example.json` (15 tools: Sentinela, SysHealth, Investigador, classify).

## Dados externos

- SysHealth: **sys-health** (Next.js + Supabase) — leitura/escrita direta no banco via `SysHealthClient`
  - `SYSHEALTH_BACKEND=supabase` (padrão) · web dev `:3535` · prod `sys-health.vercel.app`
  - Legado: `SYSHEALTH_BACKEND=legacy` + Flask `Projeto_Fit/api_server.py` na `:5060`
- Analista sandbox: `SENTINELA_DB_PATH`, `SYSHEALTH_DB_PATH` (só legado SQLite local)

## Cronos / Vigia

- Cronos: Telegram por padrão; `NOTIFY_CHANNEL=telegram|discord|both`
- Vigia: Discord (`DISCORD_WEBHOOK_LOGS`)

## UI

- Sidebar: **Dashboard Home** (`/api/dashboard`), histórico, busca FTS, export MD
- GitHub Inbox + Radar: `GITHUB_TOKEN` + `GITHUB_USER=simoesleandro` — **reiniciar Hermes após mudar `.env`**
- Painel Sentinela visível nos agentes `sentinela` e `juridico`
- Memória: `user_facts` (manual + `USER_FACTS_AUTO` com revisão pending na sidebar)

## Testes

```bash
pytest tests/
```

## Convenções

- Novos agentes: estender `BaseAgent`, registrar em `app_factory.create_app` → `agents` dict
- Sessões PDF/imagem em memória (não persistem entre restarts)

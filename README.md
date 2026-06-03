# Hermes Lite

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-F55036?logo=groq&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-llama3-white?logo=ollama&logoColor=black)
![Agents](https://img.shields.io/badge/Agentes-10-7c3aed)
![License](https://img.shields.io/badge/Licença-MIT-22c55e)
![Last Commit](https://img.shields.io/github/last-commit/simoesleandro/hermes-lite?color=8892b0)

> Assistente multi-agente local com streaming, dados reais e automação autônoma.

Hermes Lite é uma plataforma de IA pessoal com 10 agentes especializados, roteamento automático entre três providers de LLM com fallback, interface web estilo Gemini, scheduler autônomo com notificações Discord e monitor de sistema em tempo real.

---

## Agentes

| Agente | Especialidade | Complexidade |
|--------|--------------|-------------|
| Conhecimento | Perguntas gerais, pesquisa e tecnologia | Groq |
| Dev | Desenvolvimento de software e arquitetura | Groq |
| Saúde | Saúde pessoal com dados reais do SysHealth API | Ollama |
| Treino | Performance e musculação com dados Hevy + Amazfit | Groq |
| Produtividade | GTD, gestão de tarefas e foco | Groq |
| Sentinela | Auditoria de contratos públicos do RJ (PNCP) | Groq |
| Jurídico | Direito Administrativo e Lei 14.133/2021 | Gemini |
| Investigador | Dossiê autônomo multi-fonte com ReAct pattern | Gemini |
| Leitor PDF | Análise e perguntas sobre documentos PDF | Gemini |
| Analista | Geração e execução de código Python + gráficos inline | Gemini |

---

## Arquitetura

### Model Router — Fallback automático em 3 níveis

```
SIMPLE  →  Ollama  →  Groq    →  Gemini
MEDIUM  →  Groq    →  Gemini  →  Ollama
HEAVY   →  Gemini  →  Groq    →  Ollama
```

Se o provider principal estiver indisponível, o sistema tenta o próximo automaticamente, sem interrupção para o usuário.

### Stack

- **Backend:** Python 3.13 + Flask
- **Frontend:** HTML/CSS/JS vanilla (sem frameworks)
- **Banco:** SQLite (`db/hermes.db`) para histórico de conversas
- **LLMs:** Groq (`llama-3.3-70b-versatile`), Gemini 2.5 Flash, Ollama (`llama3`)
- **Streaming:** SSE (Server-Sent Events) — tokens em tempo real
- **Serviços externos:** SysHealth API (saúde), Sentinela RJ (contratos públicos)

### Estrutura do projeto

```
hermes-lite/
├── app.py                    # Flask app, rotas SSE e upload
├── model_router.py           # Roteamento e fallback entre providers
├── agents/                   # 10 agentes especializados
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
├── services/                 # Clientes de serviços externos
│   ├── syshealth_client.py
│   ├── sentinela_client.py
│   ├── investigador_tools.py
│   └── analista_sandbox.py
├── cronos/                   # Scheduler autônomo
│   ├── cronos.py
│   ├── scheduler.py
│   ├── notifier.py
│   └── tasks/
├── vigia/                    # Monitor de sistema
│   ├── vigia.py
│   └── monitor.py
├── db/                       # Banco de histórico
├── static/                   # Frontend (HTML/CSS/JS)
├── cronos-service.xml        # WinSW — Cronos
└── vigia-service.xml         # WinSW — Vigia
```

---

## Funcionalidades

- **Streaming real** — tokens chegam palavra a palavra via SSE
- **Histórico por sessão** — `session_id` UUID isolado por aba do browser
- **Badge de provider** — mostra qual LLM respondeu (groq/gemini/ollama)
- **Comando `/limpar`** — reseta o contexto da conversa
- **Upload de PDF** — botão 📎 no agente Leitor (até 10 MB, 100 páginas)
- **Gráficos inline** — Analista gera e exibe PNGs diretamente no chat
- **Progress steps** — Investigador e Analista exibem etapas em tempo real
- **ReAct pattern** — Investigador executa ferramentas reais (CNPJ, contratos, web)

---

## 🕐 Cronos — Scheduler Autônomo

Serviço Windows que executa tarefas agendadas e envia notificações no Discord.

| Tarefa | Horário | Canal Discord |
|--------|---------|--------------|
| ☀️ Briefing diário | 09:30 todos os dias | `#briefing` |
| 📊 Resumo de saúde | 22:00 todos os dias | `#saude` |
| 🔎 Relatório Sentinela | 09:30 segundas-feiras | `#sentinela` |

**Executar manualmente:**
```bash
python -m cronos.cronos
# Modo teste (dispara tudo imediatamente):
python -m cronos.cronos --test
```

---

## 👁️ Vigia — Monitor de Sistema

Monitora 4 serviços a cada 5 minutos e notifica no Discord quando algo cai ou volta.

| Serviço | Verificação |
|---------|------------|
| Hermes Lite | HTTP `localhost:5050` |
| SysHealth API | HTTP `localhost:5060/health` |
| Ollama | HTTP `localhost:11434/api/tags` |
| Hermes Cronos | Windows Service `HermesCronos` |

Alertas por mudança de estado (sem spam repetido). Heartbeat a cada hora.

**Executar manualmente:**
```bash
python -m vigia.vigia
```

---

## Instalação

### Pré-requisitos

- Python 3.11+
- [Ollama](https://ollama.com) instalado e rodando localmente
- Conta no [Groq](https://console.groq.com) (gratuita)
- Conta no [Google AI Studio](https://aistudio.google.com) para Gemini

### Setup

```bash
git clone https://github.com/simoesleandro/hermes-lite
cd hermes-lite
pip install -r requirements.txt
cp .env.example .env
# Editar .env com suas chaves de API
python app.py
```

Acesse: **http://localhost:5050**

### Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `GROQ_API_KEY` | Chave da API Groq |
| `GEMINI_API_KEY` | Chave da API Google Gemini |
| `OLLAMA_BASE_URL` | URL do Ollama (padrão: `http://localhost:11434`) |
| `SYSHEALTH_URL` | URL da API SysHealth (padrão: `http://localhost:5060`) |
| `DISCORD_WEBHOOK_LOGS` | Webhook Discord para logs e alertas do Vigia |
| `DISCORD_WEBHOOK_BRIEFING` | Webhook para briefing diário (Cronos) |
| `DISCORD_WEBHOOK_SAUDE` | Webhook para resumo de saúde (Cronos) |
| `DISCORD_WEBHOOK_SENTINELA` | Webhook para relatório semanal (Cronos) |

---

## Serviços Windows (WinSW)

Para rodar Cronos e Vigia como serviços Windows em background:

1. Baixe [WinSW](https://github.com/winsw/winsw/releases) e coloque o `.exe` na raiz do projeto
2. Renomeie conforme o serviço desejado
3. Execute como Administrador:

```cmd
# Cronos
rename WinSW-x64.exe cronos-service.exe
cronos-service.exe install
cronos-service.exe start

# Vigia
rename WinSW-x64.exe hermes-vigia.exe
hermes-vigia.exe install
hermes-vigia.exe start
```

---

## Autor

**Leandro Simões** — [github.com/simoesleandro](https://github.com/simoesleandro)

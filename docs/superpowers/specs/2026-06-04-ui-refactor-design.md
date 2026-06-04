# Hermes Lite — UI Refactor Design

**Date:** 2026-06-04  
**Approach:** Incremental, 4 visual stages (each independently shippable)  
**Scope:** `static/`, `app.py`, `db/database.py` — agents untouched

---

## 1. Architecture Overview

### DOM Structure
```
<body>
  <div class="app">
    <aside class="sidebar">                 ← 260px fixed
      <button>Nova conversa</button>
      <nav class="conv-list">
        <div class="conv-group">Hoje
          <div class="conv-item">           ← agent icon + title (40 chars)
    <div class="main">
      <header class="topbar">              ← logo only + status dots
      <main class="chat-area">
      <footer class="input-bar">          ← input + agent badge
```

### Files Changed
| File | Change |
|------|--------|
| `static/index.html` | Full rewrite — sidebar + main layout |
| `static/style.css` | Full rewrite — sidebar, Gemini input, glassmorphism |
| `static/app.js` | Full rewrite — state machine, classify, streaming buffer |
| `app.py` | Add `classify_agent()`, 3 new routes |
| `db/database.py` | Add `conversations` table, FK migration, 3 new methods |

### Files NOT Changed
All `agents/`, `db/hermes.db` (additive migration only), `cronos/`, `vigia/`, `services/`

---

## 2. Data Flow

### New Conversation
1. User types → debounced `GET /chat/classify?q=…` (300ms) → badge updates in real-time
2. User sends → frontend generates UUID `conv_id` → `GET /chat/stream?…&conv_id=…`
3. Frontend sends `POST /api/conversations` first (title = first 40 chars, agent = classified) → gets `conv_id` confirmed
4. Backend streams tokens; saves each message with `conversation_id` FK
5. Sidebar reloads via `GET /api/conversations` after stream completes

### Load Existing Conversation
1. Click sidebar item → `GET /api/conversations/:id` → returns `{conversation, messages[]}`
2. Frontend renders history, locks agent (badge non-clickable)
3. `state.currentConvId` and `state.agentLocked` updated

### Auto-Save on Switch
- Any conversation with ≥1 message is already persisted after first response
- Switching conversations is safe: just update `state.currentConvId`

---

## 3. Database Schema

### New Table: `conversations`
```sql
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,   -- UUID generated on frontend
    title      TEXT NOT NULL,      -- first 40 chars of user's first message
    agent      TEXT NOT NULL,      -- classified agent name
    created_at TEXT NOT NULL       -- ISO datetime UTC
);
```

### Additive Migration: `messages`
```sql
ALTER TABLE messages ADD COLUMN conversation_id TEXT REFERENCES conversations(id);
```
Existing rows get `conversation_id = NULL` — no data loss, no breaking change.

### New `Database` Methods
- `create_conversation(id, title, agent)` → INSERT into `conversations`
- `get_conversations(limit=50)` → SELECT with message count; date grouping in Python
- `get_conversation_messages(conv_id)` → SELECT messages WHERE conversation_id = ?

### Existing Methods Updated
- `save_message()` gets optional `conversation_id=None` param (backwards-compatible)
- `get_history_as_messages()` unchanged — agents still use `session_id` only

---

## 4. Backend (`app.py`)

### `classify_agent(message: str) -> str`
Regex compiled at module level — zero per-call cost:

```python
_RULES = [
    (re.compile(r"bebi|água|peso|hrv|sono|calorias|hidrat", re.I), "saude"),
    (re.compile(r"treino|muscula|corrida|ppl|série|repetição|supino", re.I), "treino"),
    (re.compile(r"código|bug|python|refator|arquitetura|função|classe", re.I), "desenvolvimento"),
    (re.compile(r"contrato público|pncp|licitação|anomalia|dispensa", re.I), "sentinela"),
    (re.compile(r"lei|contrato|jurídico|processo|cláusula|advogado", re.I), "juridico"),
    (re.compile(r"pesquis|investig|buscar na web|notícia", re.I), "investigador"),
    (re.compile(r"pdf|documento|resumir arquivo|anexo", re.I), "leitor"),
    (re.compile(r"gráfico|analisar dados|visualizar|dashboard|planilha", re.I), "analista"),
    (re.compile(r"tarefa|agenda|lembrete|produtividade|organizar", re.I), "produtividade"),
]
# default → conhecimento
```
Order matters: `sentinela` before `juridico` (both match "contrato").

### New Routes
| Route | Method | Purpose |
|-------|--------|---------|
| `GET /chat/classify?q=…` | GET | Returns `{"agent": "saude"}` in <1ms, no LLM |
| `POST /api/conversations` | POST | Creates conversation record; called before stream starts |
| `GET /api/conversations` | GET | Paginated list, date-grouped in Python |
| `GET /api/conversations/<conv_id>` | GET | Returns conversation + all messages |

### Updated Route: `/chat/stream`
Accepts optional `conv_id` query param; passes to `db.save_message()`.

---

## 5. Frontend

### Global State
```js
let state = {
  currentAgent: "conhecimento",
  agentLocked: false,      // true after 1st message sent in conversation
  currentConvId: null,     // UUID of active conversation
  isStreaming: false,
}
```

### Agent Classification Flow
- `input` keyup → debounce 300ms → `GET /chat/classify?q=…` → update badge
- Badge is clickable only if `!state.agentLocked` → dropdown with 10 agents to override
- After first send: `state.agentLocked = true`, badge becomes display-only

### Input Position Transition
- Empty chat → `.app` has class `.layout-empty` → CSS centers input vertically
- After first message → `.layout-empty` removed → input moves to footer
- CSS transition: `transition: all 0.4s ease`

### Streaming with Buffer (12ms + 2s flush)
```js
let tokenBuffer = [];
let streamDone = false;

// SSE handler: push to buffer only
es.onmessage = ({ data }) => {
  const d = JSON.parse(data);
  if (d.token) tokenBuffer.push(d.token);
  if (d.done) { streamDone = true; finalize(d.provider); }
};

// Display loop: drain 1 token per 12ms
function drainBuffer() {
  if (tokenBuffer.length) {
    body.textContent += tokenBuffer.shift();
    scrollToBottom();
    setTimeout(drainBuffer, 12);
  } else if (!streamDone) {
    setTimeout(drainBuffer, 12);
  }
  // else: done naturally
}
drainBuffer();

// Force flush if buffer lags > 2s behind stream end
setTimeout(() => {
  if (tokenBuffer.length) {
    body.textContent += tokenBuffer.join("");
    tokenBuffer = [];
  }
}, 2000);
```

### Blinking Cursor
```css
.bubble.streaming .bubble-body::after {
  content: "▋";
  animation: blink 1s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }
```

### Agent Status Messages
```js
const STATUS_MSG = {
  conhecimento:  "🧠 Conhecimento está pensando...",
  desenvolvimento: "💻 Dev está analisando seu código...",
  saude:         "💚 Saúde está consultando seus dados...",
  treino:        "🏋️ Treino está calculando sua performance...",
  produtividade: "⚡ Produtividade está organizando...",
  sentinela:     "🔍 Sentinela está varrendo os dados...",
  juridico:      "⚖️ Jurídico está consultando a legislação...",
  investigador:  "🕵️ Investigador está pesquisando...",
  leitor:        "📄 Leitor está processando o documento...",
  analista:      "📊 Analista está preparando o gráfico...",
}
```

### Sidebar Rendering
- `loadConversations()` → `GET /api/conversations` → render groups (Hoje / Ontem / 7 dias / Mais antigo)
- Each item: `[agent-icon] [title truncated 40 chars]`
- `loadConversation(id)` → `GET /api/conversations/:id` → clear chat-area, render messages, lock agent

---

## 6. CSS Key Decisions

| Concern | Rule |
|---------|------|
| Sidebar layout | `position: fixed; left: 0; width: 260px; height: 100vh` |
| Main offset | `.main { margin-left: 260px }` |
| Centered input | `.layout-empty .input-bar { position: absolute; top: 50%; transform: translateY(-50%) }` |
| Input glassmorphism | Copy `.topbar` backdrop-filter + border + box-shadow exactly |
| Streaming cursor | `.bubble.streaming .bubble-body::after { content: "▋"; animation: blink }` |
| Conv item hover | `background: rgba(255,255,255,0.05); border-radius: 8px` |
| Agent badge | Small pill below input, `cursor: pointer` when unlocked |

---

## 7. Implementation Stages

| Stage | Deliverable | Files |
|-------|-------------|-------|
| 1 | Sidebar + clean header (no tabs) | `index.html`, `style.css`, `app.js` (layout only) |
| 2 | `classify_agent()` + `/chat/classify` + badge | `app.py`, `app.js` |
| 3 | Gemini-style centered input + streaming buffer + cursor | `style.css`, `app.js` |
| 4 | SQLite `conversations` + sidebar history | `db/database.py`, `app.py`, `app.js` |

Each stage is a working, committable state.

---

## 8. Out of Scope

- Mobile/responsive layout (desktop-first, sidebar always visible)
- Search within conversations
- Conversation rename
- Export / delete conversations
- Authentication

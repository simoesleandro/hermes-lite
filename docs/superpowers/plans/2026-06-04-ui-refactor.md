# Hermes Lite UI Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace tab-based UI with ChatGPT/Gemini-style sidebar, automatic agent routing, centered input, and SQLite conversation history — delivered in 4 independent visual stages.

**Architecture:** Each task (stage) leaves the app fully working and committable. Stages 1→4 build on each other but never break the previous working state. Agents (`agents/`) and services are never touched.

**Tech Stack:** Flask 3.x, Vanilla JS ES2022, SQLite (stdlib), marked.js for markdown rendering, pytest for backend tests.

---

## File Map

| File | Stage | Change |
|------|-------|--------|
| `static/index.html` | 1 | Full rewrite |
| `static/style.css`  | 1 | Full rewrite |
| `static/app.js`     | 1 | Full rewrite (immediate streaming) |
| `requirements.txt`  | 2 | Add `pytest` |
| `tests/test_classify_agent.py` | 2 | New file |
| `app.py`            | 2 | Add `classify_agent()` + `GET /chat/classify` |
| `static/app.js`     | 2 | Add keyup debounce + dropdown |
| `static/app.js`     | 3 | Replace immediate streaming with 12ms buffer |
| `tests/test_database.py` | 4 | New file |
| `db/database.py`    | 4 | Add `conversations` table + 3 new methods |
| `app.py`            | 4 | Add `POST/GET /api/conversations` + `conv_id` in stream |
| `static/app.js`     | 4 | Add `loadConversations`, `loadConversation`, `newConversation` |

---

## Task 1: Stage 1 — Sidebar + Clean Header Layout

**Files:**
- Rewrite: `static/index.html`
- Rewrite: `static/style.css`
- Rewrite: `static/app.js`

> After this task: the app has the sidebar layout, no tabs in header, chat works, input centers when empty, cursor blinks while streaming.

- [ ] **Step 1.1 — Write `static/index.html`**

Replace the entire file with:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Hermes Lite</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Serif+Display&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <div class="app layout-empty" id="app">

    <aside class="sidebar" id="sidebar">
      <div class="sidebar-header">
        <div class="brand">
          <span class="brand-icon">⬡</span>
          <span class="brand-name">Hermes <span class="brand-lite">Lite</span></span>
        </div>
        <button id="new-conv-btn" class="new-conv-btn" title="Nova conversa">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Nova conversa
        </button>
      </div>
      <nav class="conv-list" id="conv-list">
        <!-- populated by JS in Stage 4 -->
      </nav>
    </aside>

    <div class="main" id="main">
      <header class="topbar">
        <div class="status-dots" id="status-dots" aria-label="Status dos providers">
          <span class="status-dot checking" id="dot-groq"   data-provider="groq"   title="Groq: checando...">●</span>
          <span class="status-dot checking" id="dot-gemini" data-provider="gemini" title="Gemini: checando...">●</span>
          <span class="status-dot checking" id="dot-ollama" data-provider="ollama" title="Ollama: checando...">●</span>
        </div>
      </header>

      <main class="chat-area" id="chat-area">
        <div class="chat-inner" id="chat-inner">
          <div class="welcome" id="welcome">
            <p class="welcome-title">Como posso ajudar?</p>
          </div>
        </div>
      </main>

      <footer class="input-bar" id="input-bar">
        <div class="input-wrap">
          <form id="chat-form" class="input-form">
            <input type="file" id="pdfInput" accept=".pdf" hidden>
            <button type="button" id="attachBtn" title="Anexar PDF" aria-label="Anexar PDF">📎</button>
            <textarea
              id="message-input"
              placeholder="Como posso ajudar?"
              autocomplete="off"
              rows="1"
            ></textarea>
            <div class="input-actions">
              <button type="button" id="stop-btn" aria-label="Parar geração">⏹</button>
              <button type="submit" id="send-btn" aria-label="Enviar">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                     fill="none" stroke="currentColor" stroke-width="2.5"
                     stroke-linecap="round" stroke-linejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              </button>
            </div>
          </form>
          <div class="agent-badge-row">
            <button class="agent-badge" id="agent-badge" title="Clique para trocar agente">
              <span id="agent-badge-icon">🧠</span>
              <span id="agent-badge-label">Conhecimento</span>
            </button>
            <div class="agent-dropdown" id="agent-dropdown" hidden></div>
          </div>
          <div class="agent-status" id="agent-status" hidden></div>
        </div>
      </footer>
    </div>

  </div>

  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 1.2 — Write `static/style.css`**

Replace the entire file with:

```css
/* ── Reset ───────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Tokens ──────────────────────────────────────────── */
:root {
  --bg:         #0a0c1c;
  --surface:    #111328;
  --surface2:   #181a2e;
  --border:     rgba(255, 255, 255, 0.08);
  --text:       rgba(255, 255, 255, 0.92);
  --text-sub:   rgba(255, 255, 255, 0.60);
  --muted:      rgba(255, 255, 255, 0.35);
  --accent:     #7c3aed;
  --accent-lt:  #a78bfa;
  --accent-dim: rgba(124, 58, 237, 0.18);
  --sidebar-w:  260px;
}

html, body {
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 15px;
  overflow: hidden;
}

/* ── App shell ───────────────────────────────────────── */
.app {
  display: flex;
  height: 100vh;
}

/* ── Sidebar ─────────────────────────────────────────── */
.sidebar {
  position: fixed;
  top: 0; left: 0;
  width: var(--sidebar-w);
  height: 100vh;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  z-index: 200;
}

.sidebar-header {
  padding: 14px 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-bottom: 1px solid var(--border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 2px 4px;
}
.brand-icon { font-size: 1.1rem; color: var(--accent-lt); line-height: 1; }
.brand-name { font-size: 0.88rem; font-weight: 600; letter-spacing: -0.01em; }
.brand-lite  { color: var(--accent-lt); }

.new-conv-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: rgba(124, 58, 237, 0.12);
  border: 1px solid rgba(124, 58, 237, 0.28);
  border-radius: 10px;
  color: var(--accent-lt);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}
.new-conv-btn:hover {
  background: rgba(124, 58, 237, 0.22);
  border-color: rgba(124, 58, 237, 0.45);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 8px 16px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.08) transparent;
}
.conv-list::-webkit-scrollbar { width: 4px; }
.conv-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }

.conv-group-label {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 12px 8px 5px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-sub);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  transition: background 0.15s, color 0.15s;
}
.conv-item:hover  { background: rgba(255, 255, 255, 0.05); color: var(--text); }
.conv-item.active { background: rgba(124, 58, 237, 0.15); color: var(--accent-lt); }
.conv-item-icon  { flex-shrink: 0; font-size: 0.9rem; }
.conv-item-title { overflow: hidden; text-overflow: ellipsis; }

/* ── Main column ─────────────────────────────────────── */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: var(--sidebar-w);
  min-height: 0;
  position: relative;
}

/* ── Topbar ──────────────────────────────────────────── */
.topbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 10px 20px;
  flex-shrink: 0;
  background: rgba(10, 12, 28, 0.5);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
  height: 50px;
}

/* ── Status dots ─────────────────────────────────────── */
.status-dots { display: flex; gap: 6px; align-items: center; }
.status-dot { font-size: 0.55rem; transition: color 0.3s; cursor: default; }
.status-dot.checking { color: rgba(255, 255, 255, 0.2); }
.status-dot.online   { color: #4ade80; }
.status-dot.offline  { color: #f87171; }

/* ── Chat area ───────────────────────────────────────── */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 8px;
  scroll-behavior: smooth;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.08) transparent;
}
.chat-area::-webkit-scrollbar { width: 5px; }
.chat-area::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }

.chat-inner {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.welcome {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.welcome-title {
  font-family: 'DM Serif Display', serif;
  font-size: 1.9rem;
  color: var(--text);
  opacity: 0.4;
  text-align: center;
}

/* ── Input bar ───────────────────────────────────────── */
.input-bar {
  flex-shrink: 0;
  padding: 8px 24px 20px;
  transition: all 0.4s ease;
}

/* Gemini centered state: when .app has .layout-empty */
.layout-empty .input-bar {
  position: absolute;
  bottom: 50%;
  left: var(--sidebar-w);
  right: 0;
  transform: translateY(50%);
  padding: 0 24px;
}

.input-wrap {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-form {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: rgba(10, 12, 28, 0.82);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 16px;
  padding: 12px 14px;
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.03);
}

#message-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.95rem;
  resize: none;
  min-height: 24px;
  max-height: 160px;
  line-height: 1.5;
  overflow-y: hidden;
}
#message-input::placeholder { color: var(--muted); }

.input-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

#attachBtn {
  display: none;
  align-items: center;
  justify-content: center;
  width: 32px; height: 32px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  color: var(--text-sub);
  border-radius: 8px;
  padding: 0;
  transition: color 0.2s;
}
#attachBtn:hover { color: var(--text); background: rgba(255,255,255,0.06); }

#stop-btn {
  display: none;
  align-items: center;
  justify-content: center;
  width: 32px; height: 32px;
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0;
  transition: all 0.2s;
}
#stop-btn:hover { background: rgba(239, 68, 68, 0.25); }

#send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px; height: 34px;
  background: var(--accent);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  color: white;
  flex-shrink: 0;
  padding: 0;
  transition: all 0.2s;
}
#send-btn:hover   { background: #6d28d9; box-shadow: 0 2px 12px rgba(124,58,237,0.4); }
#send-btn:disabled { opacity: 0.4; cursor: default; }

/* ── Agent badge row ─────────────────────────────────── */
.agent-badge-row { display: flex; align-items: center; gap: 8px; position: relative; }

.agent-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  font-size: 0.71rem;
  color: var(--text-sub);
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'DM Sans', sans-serif;
}
.agent-badge:hover:not(.locked) { background: rgba(255,255,255,0.08); color: var(--text); }
.agent-badge.locked { cursor: default; opacity: 0.7; }

.agent-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 6px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  z-index: 300;
  min-width: 230px;
}
.agent-dropdown[hidden] { display: none; }

.agent-option {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.79rem;
  color: var(--text-sub);
  background: none;
  border: none;
  font-family: 'DM Sans', sans-serif;
  text-align: left;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.agent-option:hover   { background: rgba(255,255,255,0.06); color: var(--text); }
.agent-option.current { color: var(--accent-lt); background: var(--accent-dim); }

/* ── Agent status message ────────────────────────────── */
.agent-status {
  font-size: 0.74rem;
  color: var(--text-sub);
  padding: 2px 2px;
  animation: fadeIn 0.3s ease;
}
.agent-status[hidden] { display: none; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(2px); } to { opacity: 1; transform: none; } }

/* ── Messages ────────────────────────────────────────── */
.msg-row { display: flex; gap: 12px; margin-bottom: 22px; align-items: flex-start; }
.msg-row.user { flex-direction: row-reverse; }

.avatar {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--surface2);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 700;
  flex-shrink: 0;
  color: var(--accent-lt);
  border: 1px solid rgba(255,255,255,0.08);
  user-select: none;
}
.msg-row.user .avatar { background: var(--accent); color: white; border-color: transparent; }

.bubble { max-width: 80%; font-size: 0.9rem; line-height: 1.7; }

.msg-row.user .bubble {
  background: rgba(124, 58, 237, 0.2);
  border: 1px solid rgba(124, 58, 237, 0.25);
  color: #ede9ff;
  border-radius: 18px 18px 4px 18px;
  padding: 0.65rem 1rem;
}
.msg-row.assistant .bubble {
  color: var(--text);
  padding: 4px 0 10px 0.1rem;
}

.bubble-body { word-break: break-word; }

/* Streaming cursor */
.bubble.streaming .bubble-body::after {
  content: "▋";
  animation: blink 1s step-end infinite;
  color: var(--accent-lt);
  margin-left: 1px;
}
@keyframes blink { 50% { opacity: 0; } }

.bubble-meta {
  font-size: 0.63rem;
  color: var(--muted);
  margin-top: 6px;
  display: flex; gap: 8px; align-items: center;
  user-select: none;
}

/* Markdown in bubbles */
.bubble-body h1, .bubble-body h2, .bubble-body h3 { color: var(--accent-lt); margin: 0.8em 0 0.4em; font-size: 1em; font-weight: 600; }
.bubble-body p { margin-bottom: 0.6em; }
.bubble-body p:last-child { margin-bottom: 0; }
.bubble-body ul, .bubble-body ol { padding-left: 1.3em; margin: 0.4em 0 0.6em; }
.bubble-body li { margin-bottom: 0.2em; }
.bubble-body code {
  font-family: 'Courier New', monospace; font-size: 0.84em;
  background: rgba(124,58,237,0.12); border: 1px solid rgba(124,58,237,0.2);
  border-radius: 4px; padding: 0.1em 0.35em;
}
.bubble-body pre {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; padding: 0.9em 1em; overflow-x: auto; margin: 0.6em 0;
}
.bubble-body pre code { background: none; border: none; padding: 0; font-size: 0.82em; }
.bubble-body blockquote { border-left: 3px solid var(--accent); padding-left: 0.8em; margin: 0.5em 0; color: var(--text-sub); }

/* ── Provider badge ──────────────────────────────────── */
.provider-badge { font-size: 0.58rem; font-weight: 600; padding: 0.08rem 0.32rem; border-radius: 4px; letter-spacing: 0.03em; text-transform: uppercase; }
.provider-groq    { background: #f97316; color: #fff; }
.provider-gemini  { background: #3b82f6; color: #fff; }
.provider-ollama  { background: #10b981; color: #fff; }
.provider-unknown { background: rgba(255,255,255,0.1); color: var(--muted); }

/* ── System message ──────────────────────────────────── */
.system-msg { text-align: center; font-size: 0.71rem; color: var(--muted); padding: 6px 0; user-select: none; letter-spacing: 0.02em; }

/* ── Progress steps ──────────────────────────────────── */
.progress-steps { font-size: 0.71rem; color: var(--text-sub); margin-bottom: 10px; padding: 6px 10px; background: rgba(255,255,255,0.03); border-radius: 6px; }
.progress-step { display: block; padding: 2px 0; line-height: 1.5; opacity: 0.7; }

/* ── Chart output ────────────────────────────────────── */
.chart-output { width: 100%; border-radius: 8px; margin-bottom: 12px; display: block; }
```

- [ ] **Step 1.3 — Write `static/app.js`**

Replace the entire file with:

```js
// ── Agent metadata ────────────────────────────────────
const AGENT_META = {
  conhecimento:    { icon: "🧠", label: "Conhecimento" },
  desenvolvimento: { icon: "💻", label: "Desenvolvimento" },
  saude:           { icon: "💚", label: "Saúde" },
  treino:          { icon: "🏋️", label: "Treino" },
  produtividade:   { icon: "⚡", label: "Produtividade" },
  sentinela:       { icon: "🔍", label: "Sentinela" },
  juridico:        { icon: "⚖️", label: "Jurídico" },
  investigador:    { icon: "🕵️", label: "Investigador" },
  leitor:          { icon: "📄", label: "Leitor" },
  analista:        { icon: "📊", label: "Analista" },
};

const STATUS_MSG = {
  conhecimento:    "🧠 Conhecimento está pensando...",
  desenvolvimento: "💻 Dev está analisando seu código...",
  saude:           "💚 Saúde está consultando seus dados...",
  treino:          "🏋️ Treino está calculando sua performance...",
  produtividade:   "⚡ Produtividade está organizando...",
  sentinela:       "🔍 Sentinela está varrendo os dados...",
  juridico:        "⚖️ Jurídico está consultando a legislação...",
  investigador:    "🕵️ Investigador está pesquisando...",
  leitor:          "📄 Leitor está processando o documento...",
  analista:        "📊 Analista está preparando o gráfico...",
};

// ── Global state ──────────────────────────────────────
const state = {
  currentAgent:  "conhecimento",
  agentLocked:   false,
  currentConvId: null,
  isStreaming:   false,
};
const sessionId = crypto.randomUUID();

// ── DOM refs ──────────────────────────────────────────
const app             = document.getElementById("app");
const chatArea        = document.getElementById("chat-area");
const chatInner       = document.getElementById("chat-inner");
const form            = document.getElementById("chat-form");
const input           = document.getElementById("message-input");
const sendBtn         = document.getElementById("send-btn");
const stopBtn         = document.getElementById("stop-btn");
const attachBtn       = document.getElementById("attachBtn");
const pdfInput        = document.getElementById("pdfInput");
const agentBadge      = document.getElementById("agent-badge");
const agentBadgeIcon  = document.getElementById("agent-badge-icon");
const agentBadgeLabel = document.getElementById("agent-badge-label");
const agentDropdown   = document.getElementById("agent-dropdown");
const agentStatus     = document.getElementById("agent-status");

marked.setOptions({ breaks: true, gfm: true });

// ── Textarea auto-expand ──────────────────────────────
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!state.isStreaming) form.requestSubmit();
  }
});

// ── Provider status dots ──────────────────────────────
const _statusDots = {
  groq:   document.getElementById("dot-groq"),
  gemini: document.getElementById("dot-gemini"),
  ollama: document.getElementById("dot-ollama"),
};

async function fetchStatus() {
  Object.values(_statusDots).forEach((d) => {
    d.className = "status-dot checking";
    d.title = `${d.dataset.provider}: checando...`;
  });
  try {
    const res  = await fetch("/api/status");
    const data = await res.json();
    const providers = data.providers || {};
    for (const [name, dot] of Object.entries(_statusDots)) {
      const info = providers[name];
      if (!info) continue;
      dot.className = `status-dot ${info.status === "online" ? "online" : "offline"}`;
      const lat = info.latency_ms != null ? ` · ${info.latency_ms}ms` : "";
      dot.title = `${name}: ${info.status}${lat}`;
    }
  } catch {
    Object.values(_statusDots).forEach((d) => {
      d.className = "status-dot offline";
      d.title = `${d.dataset.provider}: erro`;
    });
  }
}
fetchStatus();
setInterval(fetchStatus, 30000);

// ── Badge ─────────────────────────────────────────────
function updateBadge(agentKey) {
  const meta = AGENT_META[agentKey] || AGENT_META.conhecimento;
  state.currentAgent        = agentKey;
  agentBadgeIcon.textContent  = meta.icon;
  agentBadgeLabel.textContent = meta.label;
  attachBtn.style.display = agentKey === "leitor" ? "flex" : "none";
}

// ── Agent dropdown (populated at init, logic wired in Stage 2) ──
Object.entries(AGENT_META).forEach(([key, meta]) => {
  const btn = document.createElement("button");
  btn.classList.add("agent-option");
  btn.dataset.agent = key;
  btn.innerHTML = `<span>${meta.icon}</span><span>${meta.label}</span>`;
  btn.addEventListener("click", () => {
    updateBadge(key);
    agentDropdown.setAttribute("hidden", "");
  });
  agentDropdown.appendChild(btn);
});

agentBadge.addEventListener("click", () => {
  if (state.agentLocked) return;
  const isHidden = agentDropdown.hasAttribute("hidden");
  if (isHidden) {
    agentDropdown.removeAttribute("hidden");
    agentDropdown.querySelectorAll(".agent-option").forEach((b) => {
      b.classList.toggle("current", b.dataset.agent === state.currentAgent);
    });
  } else {
    agentDropdown.setAttribute("hidden", "");
  }
});

document.addEventListener("click", (e) => {
  if (!agentBadge.contains(e.target) && !agentDropdown.contains(e.target)) {
    agentDropdown.setAttribute("hidden", "");
  }
});

// ── Helpers ───────────────────────────────────────────
function scrollToBottom() {
  chatArea.scrollTo({ top: chatArea.scrollHeight, behavior: "smooth" });
}

function nowTime() {
  return new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function removeWelcome() {
  const w = document.getElementById("welcome");
  if (w) w.remove();
  app.classList.remove("layout-empty");
}

function appendMessage(role, text, agentKey) {
  removeWelcome();
  const meta = AGENT_META[agentKey] || AGENT_META.conhecimento;

  const row = document.createElement("div");
  row.classList.add("msg-row", role);

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.textContent = role === "user" ? "U" : meta.icon;

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");

  const body = document.createElement("div");
  body.classList.add("bubble-body");
  if (role === "assistant") {
    body.innerHTML = marked.parse(text);
  } else {
    body.textContent = text;
  }

  const bubbleMeta = document.createElement("div");
  bubbleMeta.classList.add("bubble-meta");
  bubbleMeta.textContent = role === "user" ? nowTime() : `${meta.label} · ${nowTime()}`;

  bubble.appendChild(body);
  bubble.appendChild(bubbleMeta);
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatInner.appendChild(row);
  scrollToBottom();
  return row;
}

function appendSystemMessage(text) {
  removeWelcome();
  const el = document.createElement("div");
  el.classList.add("system-msg");
  el.textContent = `— ${text} —`;
  chatInner.appendChild(el);
  scrollToBottom();
}

// ── PDF upload ────────────────────────────────────────
attachBtn.addEventListener("click", () => pdfInput.click());

pdfInput.addEventListener("change", async () => {
  const file = pdfInput.files[0];
  if (!file) return;
  pdfInput.value = "";

  const fd = new FormData();
  fd.append("file", file);
  fd.append("session_id", sessionId);

  appendSystemMessage(`📎 Enviando ${file.name}...`);
  try {
    const res  = await fetch("/upload/pdf", { method: "POST", body: fd });
    const data = await res.json();
    if (data.success) {
      appendSystemMessage(
        `📄 ${data.filename} carregado (${data.pages} páginas · ${data.chars.toLocaleString("pt-BR")} caracteres)`
      );
      if (data.truncated) appendSystemMessage("⚠️ Documento grande — analisando primeiras 20 + últimas 5 páginas");
    } else {
      appendSystemMessage(`❌ Erro: ${data.error}`);
    }
  } catch {
    appendSystemMessage("❌ Erro ao enviar arquivo");
  }
});

// ── Submit ────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message || state.isStreaming) return;

  if (message === "/limpar") {
    input.value = "";
    input.style.height = "auto";
    try {
      await fetch("/chat/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: state.currentAgent, session_id: sessionId }),
      });
    } catch { /* best-effort */ }
    chatInner.innerHTML = "";
    appendSystemMessage("Histórico limpo");
    input.focus();
    return;
  }

  if (!state.agentLocked) {
    state.agentLocked = true;
    agentBadge.classList.add("locked");
  }

  appendMessage("user", message, state.currentAgent);
  input.value = "";
  input.style.height = "auto";
  state.isStreaming = true;
  sendBtn.disabled = true;
  sendBtn.style.display = "none";
  stopBtn.style.display = "flex";

  agentStatus.textContent = STATUS_MSG[state.currentAgent] || "Pensando...";
  agentStatus.removeAttribute("hidden");

  const agentSnap = state.currentAgent;
  const meta      = AGENT_META[agentSnap];

  // Build streaming bubble
  const row = document.createElement("div");
  row.classList.add("msg-row", "assistant");

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.textContent = meta.icon;

  const bubble = document.createElement("div");
  bubble.classList.add("bubble", "streaming");

  const body = document.createElement("div");
  body.classList.add("bubble-body");

  const bubbleMeta = document.createElement("div");
  bubbleMeta.classList.add("bubble-meta");

  bubble.appendChild(body);
  bubble.appendChild(bubbleMeta);
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatInner.appendChild(row);
  scrollToBottom();

  let progressSteps = null;
  let finalized     = false;

  function finalizeUI(provider) {
    if (finalized) return;
    finalized = true;
    bubble.classList.remove("streaming");
    if (body.textContent) body.innerHTML = marked.parse(body.textContent);

    const timeSpan = document.createElement("span");
    timeSpan.textContent = `${meta.label} · ${nowTime()}`;
    bubbleMeta.appendChild(timeSpan);

    if (provider && provider !== "unknown") {
      const badge = document.createElement("span");
      badge.classList.add("provider-badge", `provider-${provider}`);
      badge.textContent = provider;
      bubbleMeta.appendChild(badge);
    }

    if (progressSteps) {
      setTimeout(() => {
        progressSteps.style.transition = "opacity 0.5s";
        progressSteps.style.opacity    = "0";
        setTimeout(() => progressSteps && progressSteps.remove(), 500);
      }, 1500);
    }

    state.isStreaming = false;
    agentStatus.setAttribute("hidden", "");
    stopBtn.style.display = "none";
    sendBtn.style.display = "flex";
    sendBtn.disabled      = false;
    stopBtn.removeEventListener("click", handleStop);
    input.focus();

    if (typeof loadConversations === "function") loadConversations();
  }

  function handleStop() {
    if (es) es.close();
    finalizeUI(null);
    appendSystemMessage("Geração interrompida");
  }
  stopBtn.addEventListener("click", handleStop);

  const params = new URLSearchParams({ message, agent: agentSnap, session_id: sessionId });
  if (state.currentConvId) params.set("conv_id", state.currentConvId);
  const es = new EventSource(`/chat/stream?${params}`);

  es.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.error) {
      body.textContent = `Erro: ${data.error}`;
      finalizeUI(null);
      return;
    }

    if (data.progress) {
      if (!progressSteps) {
        progressSteps = document.createElement("div");
        progressSteps.classList.add("progress-steps");
        bubble.insertBefore(progressSteps, body);
      }
      const step = document.createElement("div");
      step.classList.add("progress-step");
      step.textContent = data.progress;
      progressSteps.appendChild(step);
      scrollToBottom();
    }

    if (data.chart) {
      const img = document.createElement("img");
      img.src   = `data:image/png;base64,${data.chart}`;
      img.classList.add("chart-output");
      img.alt   = "Gráfico gerado pelo Analista";
      bubble.insertBefore(img, body);
      scrollToBottom();
    }

    if (data.token) {
      body.textContent += data.token;
      scrollToBottom();
    }

    if (data.done) {
      es.close();
      finalizeUI(data.provider);
    }
  };

  es.onerror = () => {
    if (!body.textContent) body.textContent = "Erro de conexão com o servidor.";
    finalizeUI(null);
  };
});

// ── Init ──────────────────────────────────────────────
updateBadge("conhecimento");
input.focus();
```

- [ ] **Step 1.4 — Start server and verify in browser**

```
python app.py
```

Open `http://localhost:5050`. Verify:
- Sidebar visible on the left (260px), logo at top, "Nova conversa" button
- Header: only 3 status dots on the right, no tabs
- Input centered vertically ("Como posso ajudar?" placeholder)
- Send a message → input drops to footer, chat appears, cursor blinks during streaming
- Shift+Enter creates newline; Enter submits
- Agent badge shows "🧠 Conhecimento"; clicking it opens dropdown; selecting changes badge

- [ ] **Step 1.5 — Commit**

```bash
git add static/index.html static/style.css static/app.js
git commit -m "feat(ui): sidebar layout, clean header, centered input, streaming cursor"
```

---

## Task 2: Stage 2 — Auto-Routing classify_agent

**Files:**
- Add: `requirements.txt` (pytest)
- Create: `tests/test_classify_agent.py`
- Modify: `app.py` (add `classify_agent` + `GET /chat/classify`)
- Modify: `static/app.js` (add keyup debounce)

> After this task: typing in the input updates the agent badge in real-time.

- [ ] **Step 2.1 — Add pytest to requirements**

In `requirements.txt`, append on a new line:
```
pytest
```

Then install:
```bash
pip install pytest
```

- [ ] **Step 2.2 — Create `tests/` directory and write failing test**

Create `tests/__init__.py` (empty file).

Create `tests/test_classify_agent.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import will fail until classify_agent is defined in app.py
from app import classify_agent

def test_saude_bebi():
    assert classify_agent("bebi água hoje") == "saude"

def test_saude_hrv():
    assert classify_agent("meu HRV foi 55 hoje") == "saude"

def test_saude_peso():
    assert classify_agent("meu peso hoje foi 78kg") == "saude"

def test_treino_corrida():
    assert classify_agent("fiz uma corrida de 5km") == "treino"

def test_treino_ppl():
    assert classify_agent("treino PPL hoje foi peito") == "treino"

def test_desenvolvimento_bug():
    assert classify_agent("tem um bug no meu código python") == "desenvolvimento"

def test_desenvolvimento_refator():
    assert classify_agent("como refatorar essa função") == "desenvolvimento"

def test_sentinela_beats_juridico():
    # sentinela rule comes before juridico, so "contrato público" matches sentinela
    assert classify_agent("anomalia no contrato público PNCP") == "sentinela"

def test_sentinela_licitacao():
    assert classify_agent("nova licitação no PNCP hoje") == "sentinela"

def test_juridico_lei():
    assert classify_agent("quero entender essa lei") == "juridico"

def test_juridico_contrato():
    assert classify_agent("revisar meu contrato de trabalho") == "juridico"

def test_investigador_pesquisar():
    assert classify_agent("pesquisar notícias sobre IA") == "investigador"

def test_leitor_pdf():
    assert classify_agent("resumir arquivo pdf do edital") == "leitor"

def test_analista_grafico():
    assert classify_agent("fazer um gráfico de vendas") == "analista"

def test_produtividade_tarefa():
    assert classify_agent("tenho uma tarefa importante hoje") == "produtividade"

def test_default_conhecimento():
    assert classify_agent("me explica o universo") == "conhecimento"

def test_default_empty():
    assert classify_agent("") == "conhecimento"
```

- [ ] **Step 2.3 — Run test to verify it fails**

```bash
python -m pytest tests/test_classify_agent.py -v
```

Expected: ImportError or AttributeError — `classify_agent` not yet defined.

- [ ] **Step 2.4 — Add `classify_agent` and route to `app.py`**

Add `import re` at the top of `app.py` (after existing imports).

Add these lines immediately after the imports block (before `load_dotenv()`):

```python
import re

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

def classify_agent(message: str) -> str:
    for pattern, agent in _RULES:
        if pattern.search(message):
            return agent
    return "conhecimento"
```

Add route after the existing `@app.route("/")` route (before `/upload/pdf`):

```python
@app.route("/chat/classify")
def chat_classify():
    q = request.args.get("q", "").strip()
    return jsonify({"agent": classify_agent(q)})
```

- [ ] **Step 2.5 — Run tests and verify they pass**

```bash
python -m pytest tests/test_classify_agent.py -v
```

Expected: all 16 tests PASS.

- [ ] **Step 2.6 — Add keyup debounce to `static/app.js`**

In `app.js`, add this block after the `document.addEventListener("click", ...)` handler (which closes the dropdown):

```js
// ── Keyup → classify ─────────────────────────────────
let _classifyTimer = null;

input.addEventListener("keyup", () => {
  if (state.agentLocked) return;
  clearTimeout(_classifyTimer);
  const q = input.value.trim();
  if (!q) return;
  _classifyTimer = setTimeout(async () => {
    try {
      const res  = await fetch(`/chat/classify?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (!state.agentLocked) updateBadge(data.agent);
    } catch { /* ignore */ }
  }, 300);
});
```

- [ ] **Step 2.7 — Verify in browser**

Restart server. Open `http://localhost:5050`. Type:
- "bebi água" → badge should switch to "💚 Saúde" within 300ms
- "tem um bug no código" → badge switches to "💻 Desenvolvimento"
- "nova licitação PNCP" → badge switches to "🔍 Sentinela"
- Send a message → badge locks (no longer switches on typing)
- After sending, typing "bebi água" → badge stays locked

- [ ] **Step 2.8 — Commit**

```bash
git add requirements.txt tests/ app.py static/app.js
git commit -m "feat: auto-routing classify_agent with keyup badge update"
```

---

## Task 3: Stage 3 — Streaming Buffer (12ms/token + 2s flush)

**Files:**
- Modify: `static/app.js` (replace immediate token display with buffer)

> After this task: tokens appear word-by-word at 12ms intervals. If backend is faster than display, buffer flushes after 2s.

- [ ] **Step 3.1 — Replace immediate token display in `app.js` submit handler**

In `static/app.js`, inside the `form.addEventListener("submit", ...)` function, find and replace the streaming bubble section. Specifically, replace from `let progressSteps = null;` to the end of `es.onerror` with:

```js
  let progressSteps = null;
  let finalized     = false;
  let tokenBuffer   = [];
  let streamDone    = false;
  let providerRef   = null;

  function finalizeUI(provider) {
    if (finalized) return;
    finalized = true;
    bubble.classList.remove("streaming");
    if (body.textContent) body.innerHTML = marked.parse(body.textContent);

    const timeSpan = document.createElement("span");
    timeSpan.textContent = `${meta.label} · ${nowTime()}`;
    bubbleMeta.appendChild(timeSpan);

    if (provider && provider !== "unknown") {
      const badge = document.createElement("span");
      badge.classList.add("provider-badge", `provider-${provider}`);
      badge.textContent = provider;
      bubbleMeta.appendChild(badge);
    }

    if (progressSteps) {
      setTimeout(() => {
        progressSteps.style.transition = "opacity 0.5s";
        progressSteps.style.opacity    = "0";
        setTimeout(() => progressSteps && progressSteps.remove(), 500);
      }, 1500);
    }

    state.isStreaming = false;
    agentStatus.setAttribute("hidden", "");
    stopBtn.style.display = "none";
    sendBtn.style.display = "flex";
    sendBtn.disabled      = false;
    stopBtn.removeEventListener("click", handleStop);
    input.focus();

    if (typeof loadConversations === "function") loadConversations();
  }

  // Drain buffer at 12ms per token
  function drainBuffer() {
    if (tokenBuffer.length) {
      body.textContent += tokenBuffer.shift();
      scrollToBottom();
      setTimeout(drainBuffer, 12);
    } else if (!streamDone) {
      setTimeout(drainBuffer, 12); // wait for more tokens from SSE
    } else {
      finalizeUI(providerRef); // buffer empty and stream done
    }
  }
  drainBuffer();

  function handleStop() {
    streamDone = true;
    tokenBuffer = [];
    if (es) es.close();
    finalizeUI(null);
    appendSystemMessage("Geração interrompida");
  }
  stopBtn.addEventListener("click", handleStop);

  const params = new URLSearchParams({ message, agent: agentSnap, session_id: sessionId });
  if (state.currentConvId) params.set("conv_id", state.currentConvId);
  const es = new EventSource(`/chat/stream?${params}`);

  es.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.error) {
      tokenBuffer = [];
      body.textContent = `Erro: ${data.error}`;
      streamDone = true;
      finalizeUI(null);
      return;
    }

    if (data.progress) {
      if (!progressSteps) {
        progressSteps = document.createElement("div");
        progressSteps.classList.add("progress-steps");
        bubble.insertBefore(progressSteps, body);
      }
      const step = document.createElement("div");
      step.classList.add("progress-step");
      step.textContent = data.progress;
      progressSteps.appendChild(step);
      scrollToBottom();
    }

    if (data.chart) {
      const img = document.createElement("img");
      img.src   = `data:image/png;base64,${data.chart}`;
      img.classList.add("chart-output");
      img.alt   = "Gráfico gerado pelo Analista";
      bubble.insertBefore(img, body);
      scrollToBottom();
    }

    if (data.token) {
      tokenBuffer.push(data.token);
    }

    if (data.done) {
      providerRef = data.provider;
      streamDone  = true;
      es.close();
      // Force flush 2s after stream ends (if buffer hasn't drained naturally)
      setTimeout(() => {
        if (tokenBuffer.length) {
          body.textContent += tokenBuffer.join("");
          tokenBuffer = [];
        }
        finalizeUI(providerRef);
      }, 2000);
    }
  };

  es.onerror = () => {
    if (!body.textContent && !tokenBuffer.length) {
      body.textContent = "Erro de conexão com o servidor.";
    }
    streamDone = true;
    tokenBuffer = [];
    finalizeUI(null);
  };
```

- [ ] **Step 3.2 — Verify in browser**

Restart server. Send a message and observe:
- Tokens appear one-by-one with a slight delay (visible "typing" effect)
- Cursor "▋" blinks at the end while streaming
- Cursor disappears when stream finishes
- For a short response, stream finishes naturally (drainBuffer empties, finalizeUI called)
- The stop button interrupts immediately (clears buffer + closes SSE)

- [ ] **Step 3.3 — Commit**

```bash
git add static/app.js
git commit -m "feat(ui): streaming buffer 12ms/token with 2s force-flush"
```

---

## Task 4: Stage 4 — SQLite Conversation History

**Files:**
- Create: `tests/test_database.py`
- Modify: `db/database.py` (new table, new methods, updated `save_message`)
- Modify: `app.py` (3 new routes, `conv_id` in stream, `timedelta` import)
- Modify: `static/app.js` (conversation management functions)

> After this task: sidebar shows conversation history grouped by date; clicking loads past conversations; new conversation resets state.

- [ ] **Step 4.1 — Write failing database tests**

Create `tests/test_database.py`:

```python
import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db.database import Database

@pytest.fixture
def db(tmp_path):
    return Database(path=str(tmp_path / "test.db"))

def test_create_conversation(db):
    db.create_conversation("abc-123", "Bebi água hoje", "saude")
    convs = db.get_conversations()
    assert len(convs) == 1
    assert convs[0]["id"] == "abc-123"
    assert convs[0]["agent"] == "saude"
    assert convs[0]["title"] == "Bebi água hoje"

def test_get_conversation_messages(db):
    db.create_conversation("conv-1", "Teste", "conhecimento")
    db.save_message("conhecimento", "user",      "Olá", "sess-1", conversation_id="conv-1")
    db.save_message("conhecimento", "assistant", "Oi!", "sess-1", conversation_id="conv-1")
    msgs = db.get_conversation_messages("conv-1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Olá"
    assert msgs[1]["role"] == "assistant"

def test_save_message_backwards_compat(db):
    # Calling without conversation_id must not raise
    db.save_message("conhecimento", "user", "Teste", "sess-old")
    history = db.get_history_as_messages("conhecimento", "sess-old")
    assert len(history) == 1
    assert history[0]["content"] == "Teste"

def test_duplicate_conversation_ignored(db):
    db.create_conversation("dup-1", "Título Original", "treino")
    db.create_conversation("dup-1", "Outro Título",    "treino")  # INSERT OR IGNORE
    convs = db.get_conversations()
    assert len(convs) == 1
    assert convs[0]["title"] == "Título Original"

def test_get_conversations_empty(db):
    assert db.get_conversations() == []

def test_get_conversation_messages_empty(db):
    assert db.get_conversation_messages("nonexistent") == []
```

- [ ] **Step 4.2 — Run test to verify failure**

```bash
python -m pytest tests/test_database.py -v
```

Expected: errors on `create_conversation`, `get_conversations`, `get_conversation_messages` (not yet defined); `save_message` may pass or fail on signature.

- [ ] **Step 4.3 — Update `db/database.py`**

Replace the entire file with:

```python
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "hermes.db")


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent           TEXT    NOT NULL,
                    role            TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                    content         TEXT    NOT NULL,
                    timestamp       TEXT    NOT NULL,
                    session_id      TEXT,
                    conversation_id TEXT REFERENCES conversations(id)
                )
            """)
            # Additive migrations for existing databases
            for col, definition in [
                ("session_id",      "TEXT"),
                ("conversation_id", "TEXT REFERENCES conversations(id)"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {definition}")
                except Exception:
                    pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    agent      TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_message(
        self,
        agent: str,
        role: str,
        content: str,
        session_id: str,
        conversation_id: str = None,
    ):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (agent, role, content, timestamp, session_id, conversation_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (agent, role, content, datetime.utcnow().isoformat(), session_id, conversation_id),
            )
            conn.commit()

    def get_history(self, agent: str, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, agent, role, content, timestamp FROM messages "
                "WHERE agent = ? ORDER BY id DESC LIMIT ?",
                (agent, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_history_as_messages(self, agent: str, session_id: str, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages "
                "WHERE agent = ? AND session_id = ? ORDER BY id DESC LIMIT ?",
                (agent, session_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def clear_history(self, agent: str, session_id: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE agent = ? AND session_id = ?",
                (agent, session_id),
            )
            conn.commit()
        return cursor.rowcount

    def create_conversation(self, id: str, title: str, agent: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations (id, title, agent, created_at) VALUES (?, ?, ?, ?)",
                (id, title[:40], agent, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_conversations(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.agent, c.created_at,
                       COUNT(m.id) AS msg_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation_messages(self, conv_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM messages "
                "WHERE conversation_id = ? ORDER BY id ASC",
                (conv_id,),
            ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 4.4 — Run tests and verify they pass**

```bash
python -m pytest tests/test_database.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 4.5 — Add conversation routes and update stream in `app.py`**

Add `from datetime import datetime, timedelta` — update the existing `from datetime import datetime` line at the top of `app.py`:

```python
from datetime import datetime, timedelta
```

Add these 3 routes after the `@app.route("/chat/classify")` route:

```python
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
    convs   = db.get_conversations(limit=50)
    today   = datetime.utcnow().date()
    yday    = today.replace(day=today.day - 1) if today.day > 1 else today  # safe enough for grouping
    from datetime import date as _date, timedelta as _td
    yesterday = today - _td(days=1)
    week_ago  = today - _td(days=7)

    groups: dict[str, list] = {"Hoje": [], "Ontem": [], "Últimos 7 dias": [], "Mais antigo": []}
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
```

In `chat_stream()`, add `conv_id` extraction right after `session_id`:

```python
    conv_id    = request.args.get("conv_id") or None
```

And in the `generate()` inner function, update both `db.save_message()` calls to pass `conversation_id=conv_id`:

```python
        db.save_message(agent=agent_name, role="user",      content=message,  session_id=session_id, conversation_id=conv_id)
        db.save_message(agent=agent_name, role="assistant", content=complete,  session_id=session_id, conversation_id=conv_id)
```

- [ ] **Step 4.6 — Add conversation management to `static/app.js`**

At the bottom of `app.js`, before the `// ── Init ──` block, add:

```js
// ── Conversation management ───────────────────────────
async function loadConversations() {
  try {
    const res  = await fetch("/api/conversations");
    const data = await res.json();
    renderConvList(data.groups || {});
  } catch { /* ignore */ }
}

function renderConvList(groups) {
  const list = document.getElementById("conv-list");
  list.innerHTML = "";

  for (const [label, convs] of Object.entries(groups)) {
    if (!convs.length) continue;

    const groupEl = document.createElement("div");
    groupEl.classList.add("conv-group-label");
    groupEl.textContent = label;
    list.appendChild(groupEl);

    for (const conv of convs) {
      const item = document.createElement("div");
      item.classList.add("conv-item");
      if (conv.id === state.currentConvId) item.classList.add("active");
      item.dataset.convId = conv.id;

      const meta = AGENT_META[conv.agent] || AGENT_META.conhecimento;
      const titleEl = document.createElement("span");
      titleEl.classList.add("conv-item-title");
      titleEl.textContent = conv.title;

      const iconEl = document.createElement("span");
      iconEl.classList.add("conv-item-icon");
      iconEl.textContent = meta.icon;

      item.appendChild(iconEl);
      item.appendChild(titleEl);
      item.addEventListener("click", () => loadConversation(conv.id, conv.agent));
      list.appendChild(item);
    }
  }
}

async function loadConversation(convId, agent) {
  if (state.isStreaming) return;

  state.currentConvId = convId;
  state.agentLocked   = true;
  updateBadge(agent);
  agentBadge.classList.add("locked");

  chatInner.innerHTML = "";
  app.classList.remove("layout-empty");

  document.querySelectorAll(".conv-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.convId === convId);
  });

  try {
    const res  = await fetch(`/api/conversations/${convId}`);
    const data = await res.json();
    for (const msg of data.messages) {
      appendMessage(msg.role === "user" ? "user" : "assistant", msg.content, agent);
    }
  } catch {
    appendSystemMessage("Erro ao carregar conversa");
  }

  input.focus();
}

function newConversation() {
  if (state.isStreaming) return;

  state.currentConvId = null;
  state.currentAgent  = "conhecimento";
  state.agentLocked   = false;

  chatInner.innerHTML = `<div class="welcome" id="welcome"><p class="welcome-title">Como posso ajudar?</p></div>`;
  app.classList.add("layout-empty");

  updateBadge("conhecimento");
  agentBadge.classList.remove("locked");

  document.querySelectorAll(".conv-item").forEach((el) => el.classList.remove("active"));
  input.focus();
}

document.getElementById("new-conv-btn").addEventListener("click", newConversation);
```

- [ ] **Step 4.7 — Wire conversation creation before stream in `app.js`**

Inside the `form.addEventListener("submit", ...)` handler, find the block that sets `state.agentLocked = true` (the `if (!state.agentLocked)` check). Immediately after locking the agent and before the `appendMessage("user", ...)` call, add:

```js
  // Create conversation on first message
  if (!state.currentConvId) {
    state.currentConvId = crypto.randomUUID();
    fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id:    state.currentConvId,
        title: message.slice(0, 40),
        agent: state.currentAgent,
      }),
    }).catch(() => { /* best-effort */ });
  }
```

So the surrounding code looks like:

```js
  if (!state.agentLocked) {
    state.agentLocked = true;
    agentBadge.classList.add("locked");
  }

  // Create conversation on first message
  if (!state.currentConvId) {
    state.currentConvId = crypto.randomUUID();
    fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id:    state.currentConvId,
        title: message.slice(0, 40),
        agent: state.currentAgent,
      }),
    }).catch(() => { /* best-effort */ });
  }

  appendMessage("user", message, state.currentAgent);
```

- [ ] **Step 4.8 — Add initial `loadConversations()` call in Init block**

At the bottom of `app.js`, the `// ── Init ──` section should now read:

```js
// ── Init ──────────────────────────────────────────────
updateBadge("conhecimento");
loadConversations();
input.focus();
```

- [ ] **Step 4.9 — Verify in browser**

Restart server. Open `http://localhost:5050`. Verify:
- Send a message — conversation appears in sidebar under "Hoje" after response
- Click "Nova conversa" — chat resets, input centers, badge unlocks
- Send another message — second conversation appears in sidebar
- Click the first conversation in sidebar — chat loads its messages, badge locks to that agent
- Classify still works: in a new conversation, type "bebi água" → badge switches to Saúde
- After sending, badge locks

- [ ] **Step 4.10 — Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass (16 classify + 6 database = 22 total).

- [ ] **Step 4.11 — Commit**

```bash
git add db/database.py app.py static/app.js tests/test_database.py
git commit -m "feat: SQLite conversation history with sidebar grouping by date"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All spec requirements covered:
  - Sidebar 260px with Nova conversa + conv list grouped by date ✓ (Task 1 layout, Task 4 data)
  - Conversation title = first 40 chars ✓ (Task 4.7 `message.slice(0, 40)`)
  - Agent icon next to conv name ✓ (`conv-item-icon` in Task 4.6)
  - Header only logo + status dots ✓ (Task 1.1)
  - `classify_agent()` with exact regex rules in spec order ✓ (Task 2.4)
  - Badge clicável before first message, fixed after ✓ (`agentLocked`, Tasks 1, 4)
  - Input centered when no messages, drops to footer after first ✓ (`layout-empty` CSS + `removeWelcome()`)
  - Agent status messages during streaming ✓ (`STATUS_MSG` in Task 1.3)
  - Streaming buffer 12ms + 2s flush ✓ (Task 3.1)
  - Blinking cursor ✓ (CSS `.streaming .bubble-body::after` Task 1.2)
  - SQLite `conversations` table + FK ✓ (Task 4.3)
  - `GET /api/conversations` + `GET /api/conversations/<id>` ✓ (Task 4.5)
  - `POST /api/conversations` before stream ✓ (Task 4.7)
  - Sidebar reloads after response ✓ (`loadConversations()` in `finalizeUI`)
  - Auto-save: conversation created on first message ✓ (Task 4.7 — fires before `appendMessage`)

- [x] **No placeholders:** All steps have complete code.

- [x] **Type consistency:**
  - `state.currentConvId` used consistently as `null | string` throughout
  - `conversation_id` param in `save_message()` matches `db.save_message()` signature
  - `AGENT_META` keys match agent names used in `classify_agent()` output
  - `loadConversations()` referenced in `finalizeUI` as `typeof loadConversations === "function"` — safe because Task 4 defines it, and Task 1-3 use the guard

- [x] **Backwards compat:** Existing `messages` rows with `conversation_id = NULL` are unaffected. `save_message()` default `conversation_id=None` keeps all existing callers working.

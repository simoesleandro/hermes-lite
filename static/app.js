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
  ops:             { icon: "⚙️", label: "Ops" },
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
  ops:             "⚙️ Ops está consultando os serviços...",
};

const THINKING_PHRASES = {
  conhecimento:    ["🧠 Pensando...",               "Consultando base de conhecimento...", "Formulando resposta..."],
  desenvolvimento: ["💻 Analisando o código...",    "Revisando a lógica...",               "Estruturando solução..."],
  saude:           ["💚 Consultando seus dados...", "Analisando métricas de saúde...",     "Calculando recomendações..."],
  treino:          ["🏋️ Calculando performance...", "Analisando seus treinos...",           "Otimizando protocolo..."],
  produtividade:   ["⚡ Organizando...",            "Estruturando plano...",               "Priorizando tarefas..."],
  sentinela:       ["🔍 Varrendo os dados...",      "Analisando contratos...",             "Identificando padrões..."],
  juridico:        ["⚖️ Consultando legislação...", "Analisando dispositivos legais...",   "Verificando jurisprudência..."],
  investigador:    ["🕵️ Pesquisando...",            "Cruzando informações...",             "Verificando fontes..."],
  leitor:          ["📄 Processando documento...",  "Analisando conteúdo...",              "Extraindo informações..."],
  analista:        ["📊 Gerando análise...",        "Processando dados...",                "Preparando visualização..."],
  ops:             ["⚙️ Consultando serviços...",   "Verificando status...",               "Aguardando resposta..."],
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


// ── Badge ─────────────────────────────────────────────
function updateBadge(agentKey) {
  const meta = AGENT_META[agentKey] || AGENT_META.conhecimento;
  state.currentAgent        = agentKey;
  agentBadgeIcon.textContent  = meta.icon;
  agentBadgeLabel.textContent = meta.label;
  attachBtn.style.display = agentKey === "leitor" ? "flex" : "none";
}

// ── Agent dropdown ────────────────────────────────────
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

// ── Keyup → classify (wired in Stage 2, stub here) ───
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

  // Create conversation on first message (Stage 4 populates sidebar after response)
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
  input.value = "";
  input.style.height = "auto";
  state.isStreaming = true;
  sendBtn.disabled = true;
  sendBtn.style.display = "none";
  stopBtn.style.display = "flex";

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

  // Thinking indicator inside bubble
  const thinkingEl = document.createElement("div");
  thinkingEl.classList.add("bubble-thinking");
  thinkingEl.innerHTML = '<div class="thinking-dots"><span></span><span></span><span></span></div><span class="thinking-text"></span>';
  bubble.insertBefore(thinkingEl, body);
  const phrases    = THINKING_PHRASES[agentSnap] || ["Pensando..."];
  let   phraseIdx  = 0;
  thinkingEl.querySelector(".thinking-text").textContent = phrases[0];
  let phraseInterval = setInterval(() => {
    phraseIdx = (phraseIdx + 1) % phrases.length;
    const textEl = thinkingEl.querySelector(".thinking-text");
    if (textEl) textEl.textContent = phrases[phraseIdx];
  }, 2000);

  let progressSteps = null;
  let finalized     = false;
  let tokenBuffer   = [];
  let rawText       = "";
  let rafId         = null;
  let firstToken    = true;
  let streamDone    = false;
  let providerRef   = null;

  function _renderB64Images(container) {
    container.querySelectorAll("p, pre, code").forEach((el) => {
      const raw = el.textContent.replace(/\s/g, "");
      if (raw.length > 200 && /^[A-Za-z0-9+\/=]+$/.test(raw)) {
        const img = document.createElement("img");
        img.src = raw.startsWith("data:") ? raw : `data:image/png;base64,${raw}`;
        img.classList.add("chart-output");
        img.alt = "Gráfico gerado pelo Analista";
        el.replaceWith(img);
      }
    });
  }

  function finalizeUI(provider) {
    if (finalized) return;
    finalized = true;
    if (rafId) cancelAnimationFrame(rafId);
    clearInterval(phraseInterval);
    if (thinkingEl.parentNode) thinkingEl.remove();
    bubble.classList.remove("streaming");
    if (rawText) {
      body.innerHTML = marked.parse(rawText);
      _renderB64Images(body);
    }

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
    stopBtn.style.display = "none";
    sendBtn.style.display = "flex";
    sendBtn.disabled      = false;
    stopBtn.removeEventListener("click", handleStop);
    input.focus();

    if (typeof loadConversations === "function") loadConversations();
  }

  function drainBuffer() {
    if (tokenBuffer.length) {
      rawText += tokenBuffer.shift();
      body.innerHTML = marked.parse(rawText);
      scrollToBottom();
    }
    if (!streamDone || tokenBuffer.length) {
      rafId = requestAnimationFrame(drainBuffer);
    } else {
      finalizeUI(providerRef);
    }
  }
  rafId = requestAnimationFrame(drainBuffer);

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
      clearInterval(phraseInterval);
      const textEl = thinkingEl.querySelector(".thinking-text");
      if (textEl) textEl.textContent = data.progress;

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
      if (firstToken) {
        firstToken = false;
        clearInterval(phraseInterval);
        thinkingEl.classList.add("thinking-fade-out");
        setTimeout(() => thinkingEl.parentNode && thinkingEl.remove(), 350);
      }
    }

    if (data.done) {
      providerRef = data.provider;
      if (data.full_response && !rawText && !tokenBuffer.length) {
        rawText = data.full_response;
      }
      streamDone = true;
      es.close();
    }
  };

  es.onerror = () => {
    if (!rawText && !tokenBuffer.length) {
      body.innerHTML = "Erro de conexão com o servidor.";
    }
    streamDone = true;
    tokenBuffer = [];
    finalizeUI(null);
  };
});

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

      const iconEl = document.createElement("span");
      iconEl.classList.add("conv-item-icon");
      iconEl.textContent = (AGENT_META[conv.agent] || AGENT_META.conhecimento).icon;

      const titleEl = document.createElement("span");
      titleEl.classList.add("conv-item-title");
      titleEl.textContent = conv.title;

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

  chatInner.innerHTML = "";
  app.classList.add("layout-empty");

  updateBadge("conhecimento");
  agentBadge.classList.remove("locked");

  document.querySelectorAll(".conv-item").forEach((el) => el.classList.remove("active"));
  input.focus();
}

document.getElementById("new-conv-btn").addEventListener("click", newConversation);

// ── Status panel ─────────────────────────────────────
async function loadStatus() {
  const panel = document.getElementById("sidebar-status");
  if (!panel) return;
  try {
    const res  = await fetch("/api/status");
    const data = await res.json();
    renderStatusPanel(panel, data);
  } catch { /* silent */ }
}

function renderStatusPanel(panel, data) {
  panel.innerHTML = "";
  const sections = [
    { label: "Provedores", entries: data.providers },
    { label: "Serviços",   entries: data.services  },
  ];
  for (const { label, entries } of sections) {
    if (!entries || !Object.keys(entries).length) continue;
    const section = document.createElement("div");

    const labelEl = document.createElement("div");
    labelEl.className = "status-section-label";
    labelEl.textContent = label;

    const pills = document.createElement("div");
    pills.className = "status-pills";
    for (const [name, info] of Object.entries(entries)) {
      pills.appendChild(makeStatusPill(name, info));
    }
    section.appendChild(labelEl);
    section.appendChild(pills);
    panel.appendChild(section);
  }
}

function makeStatusPill(name, info) {
  const isOnline = info.status === "online";
  const pill = document.createElement("span");
  pill.className = `status-pill ${isOnline ? "online" : "offline"}`;

  const dot = document.createElement("span");
  dot.className = "status-pill-dot";

  const label = document.createElement("span");
  label.textContent = name;

  pill.appendChild(dot);
  pill.appendChild(label);

  if (info.latency_ms != null) {
    const lat = document.createElement("span");
    lat.className = "status-pill-latency";
    lat.textContent = `${info.latency_ms}ms`;
    pill.appendChild(lat);
  }

  return pill;
}

// ── Init ──────────────────────────────────────────────
updateBadge("conhecimento");
loadConversations();
loadStatus();
setInterval(loadStatus, 30_000);
input.focus();

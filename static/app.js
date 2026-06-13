// ── Agent metadata ────────────────────────────────────
const AGENT_META = {
  conhecimento:    { icon: "book-open",   label: "Conhecimento" },
  desenvolvimento: { icon: "code-2",      label: "Desenvolvimento" },
  saude:           { icon: "heart-pulse", label: "Saúde" },
  treino:          { icon: "dumbbell",    label: "Treino" },
  produtividade:   { icon: "zap",         label: "Produtividade" },
  sentinela:       { icon: "shield",      label: "Sentinela" },
  juridico:        { icon: "scale",       label: "Jurídico" },
  investigador:    { icon: "search",      label: "Investigador" },
  leitor:          { icon: "file-text",   label: "Leitor" },
  analista:        { icon: "bar-chart-2", label: "Analista" },
  ops:             { icon: "settings-2",  label: "Ops" },
};

const THINKING_PHRASES = {
  conhecimento:    ["Processando pergunta...",   "Estruturando resposta...",    "Organizando contexto..."],
  desenvolvimento: ["Analisando código...",      "Revisando arquitetura...",    "Verificando padrões..."],
  saude:           ["Consultando seus dados...", "Analisando métricas...",      "Calculando progresso..."],
  treino:          ["Buscando seus treinos...",  "Analisando performance...",   "Calculando volume..."],
  produtividade:   ["Organizando tarefas...",    "Estruturando plano...",       "Priorizando itens..."],
  sentinela:       ["Varrendo contratos...",     "Identificando padrões...",    "Cruzando registros..."],
  juridico:        ["Consultando legislação...", "Analisando dispositivos...",  "Verificando jurisprudência..."],
  investigador:    ["Buscando fontes...",        "Cruzando informações...",     "Verificando dados..."],
  leitor:          ["Processando documento...",  "Extraindo conteúdo...",       "Analisando estrutura..."],
  analista:        ["Gerando SQL...",            "Executando query...",         "Preparando visualização..."],
  ops:             ["Verificando serviços...",   "Consultando status...",       "Checando processos..."],
};

// ── Global state ──────────────────────────────────────
const state = {
  currentAgent:  "conhecimento",
  agentLocked:   false,
  currentConvId: null,
  isStreaming:   false,
  messageQueue:  [],
  activeSkill:   null,
  skillsCache:   null,
};
let attachedFile = null;
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
const fileInput       = document.getElementById("fileInput");
const agentBadge      = document.getElementById("agent-badge");
const agentBadgeIcon  = document.getElementById("agent-badge-icon");
const agentBadgeLabel = document.getElementById("agent-badge-label");
const agentDropdown   = document.getElementById("agent-dropdown");
const skillBadge      = document.getElementById("skill-badge");
const skillBadgeLabel = document.getElementById("skill-badge-label");
const skillDropdown   = document.getElementById("skill-dropdown");
const messageQueueEl  = document.getElementById("message-queue");
const agentStatus     = document.getElementById("agent-status");
const fileChip        = document.getElementById("file-chip");
const fileChipIcon    = document.getElementById("file-chip-icon");
const fileChipName    = document.getElementById("file-chip-name");
const fileChipRemove  = document.getElementById("file-chip-remove");
const sidebar         = document.getElementById("sidebar");
const hamburgerBtn    = document.getElementById("hamburger-btn");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");

// ── Mobile sidebar ────────────────────────────────────
function openSidebar() {
  sidebar.classList.add("sidebar-open");
  document.body.classList.add("sidebar-open");
}
function closeSidebar() {
  sidebar.classList.remove("sidebar-open");
  document.body.classList.remove("sidebar-open");
}

hamburgerBtn.addEventListener("click", openSidebar);
sidebarBackdrop.addEventListener("click", closeSidebar);

document.getElementById("conv-list").addEventListener("click", (e) => {
  if (e.target.closest(".conv-item") && window.innerWidth <= 768) closeSidebar();
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 768) closeSidebar();
});

const _mobileMQ = window.matchMedia("(max-width: 768px)");
function _syncHamburger(e) {
  hamburgerBtn.style.display = e.matches ? "flex" : "none";
}
_mobileMQ.addEventListener("change", _syncHamburger);
_syncHamburger(_mobileMQ);

marked.setOptions({ breaks: true, gfm: true });

// ── Textarea auto-expand ──────────────────────────────
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const msg = input.value.trim();
    if (state.isStreaming) {
      if (msg) enqueueMessage(msg);
    } else {
      form.requestSubmit();
    }
  }
});


// ── Badge ─────────────────────────────────────────────
function updateBadge(agentKey) {
  const meta = AGENT_META[agentKey] || AGENT_META.conhecimento;
  state.currentAgent          = agentKey;
  agentBadgeIcon.innerHTML    = "";
  agentBadgeIcon.appendChild(lucideIcon(meta.icon, 16));
  lucide.createIcons();
  agentBadgeLabel.textContent = meta.label;
  attachBtn.style.display     = "flex";
  toggleSentinelaPanel(agentKey);
  toggleTasksPanel(agentKey);
  toggleKnowledgePanel(agentKey);
  updateSkillBadge(agentKey);
}

async function loadSkillsCache() {
  if (state.skillsCache) return state.skillsCache;
  try {
    const res = await fetch("/api/skills");
    state.skillsCache = (await res.json()).skills || {};
  } catch {
    state.skillsCache = {};
  }
  return state.skillsCache;
}

function updateSkillBadge(agentKey) {
  loadSkillsCache().then((cache) => {
    const skills = cache[agentKey] || {};
    const ids = Object.keys(skills);
    skillDropdown.innerHTML = "";
    if (!ids.length) {
      skillBadge.hidden = true;
      state.activeSkill = null;
      return;
    }
    skillBadge.hidden = false;
    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "skill-option";
    clearBtn.textContent = "Padrão (sem skill)";
    clearBtn.addEventListener("click", () => {
      state.activeSkill = null;
      skillBadge.classList.remove("active");
      skillBadgeLabel.textContent = "Skill";
      skillDropdown.setAttribute("hidden", "");
    });
    skillDropdown.appendChild(clearBtn);
    ids.forEach((id) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "skill-option";
      btn.dataset.skill = id;
      btn.textContent = skills[id].label || id;
      if (state.activeSkill === id) btn.classList.add("selected");
      btn.addEventListener("click", () => {
        state.activeSkill = id;
        skillBadge.classList.add("active");
        skillBadgeLabel.textContent = skills[id].label || id;
        skillDropdown.setAttribute("hidden", "");
      });
      skillDropdown.appendChild(btn);
    });
    if (state.activeSkill && skills[state.activeSkill]) {
      skillBadge.classList.add("active");
      skillBadgeLabel.textContent = skills[state.activeSkill].label;
    } else {
      skillBadge.classList.remove("active");
      skillBadgeLabel.textContent = "Skill";
      state.activeSkill = null;
    }
  });
}

skillBadge.addEventListener("click", () => {
  if (skillBadge.hidden) return;
  const open = !skillDropdown.hasAttribute("hidden");
  agentDropdown.setAttribute("hidden", "");
  if (open) skillDropdown.setAttribute("hidden", "");
  else skillDropdown.removeAttribute("hidden");
});

function renderMessageQueue() {
  if (!messageQueueEl) return;
  if (!state.messageQueue.length) {
    messageQueueEl.hidden = true;
    messageQueueEl.innerHTML = "";
    return;
  }
  messageQueueEl.hidden = false;
  messageQueueEl.innerHTML =
    `<span class="queue-label">${state.messageQueue.length} na fila</span>` +
    state.messageQueue.map((m) => `<span class="queue-item">${escapeHtml(m.text.slice(0, 48))}</span>`).join("");
}

function enqueueMessage(message) {
  state.messageQueue.push({
    text: message,
    skill: state.activeSkill,
    file: attachedFile ? { ...attachedFile } : null,
  });
  input.value = "";
  input.style.height = "auto";
  clearFileChip();
  renderMessageQueue();
}

function dequeueAndSend() {
  if (state.isStreaming || !state.messageQueue.length) return;
  const next = state.messageQueue.shift();
  renderMessageQueue();
  if (next.file) attachedFile = next.file;
  if (next.skill !== undefined) {
    state.activeSkill = next.skill;
    updateSkillBadge(state.currentAgent);
  }
  dispatchMessage(next.text);
}

function toggleKnowledgePanel(agentKey) {
  const panel = document.getElementById("knowledge-panel");
  if (!panel) return;
  if (agentKey === "conhecimento" || agentKey === "leitor") {
    panel.hidden = false;
    loadKnowledgePanel();
  } else {
    panel.hidden = true;
  }
}

async function loadKnowledgePanel() {
  const panel = document.getElementById("knowledge-panel");
  if (!panel || panel.hidden) return;
  panel.innerHTML = '<div class="knowledge-loading">Carregando…</div>';
  try {
    const res  = await fetch("/api/knowledge");
    const data = await res.json();
    renderKnowledgePanel(panel, data.documents || []);
  } catch {
    panel.innerHTML = '<div class="knowledge-offline">Base indisponível</div>';
  }
}

function renderKnowledgePanel(panel, docs) {
  panel.innerHTML = `
    <div class="knowledge-panel-title">Base de conhecimento</div>
    <div class="knowledge-hint">PDFs anexados em Conhecimento/Leitor são indexados automaticamente.</div>
    <ul class="knowledge-list">
      ${docs.slice(0, 8).map((d) => `
        <li>
          <span class="knowledge-doc-title">${escapeHtml(d.title || d.filename || "doc")}</span>
          <span class="knowledge-doc-meta">${d.chunks || 0} trechos</span>
          <button type="button" class="knowledge-del" data-id="${d.id}" title="Remover">×</button>
        </li>
      `).join("") || "<li class='knowledge-empty'>Nenhum documento indexado</li>"}
    </ul>
  `;
  panel.querySelectorAll(".knowledge-del").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      if (!id || !confirm("Remover documento da base?")) return;
      await fetch(`/api/knowledge/${id}`, { method: "DELETE" });
      loadKnowledgePanel();
    });
  });
}

function toggleTasksPanel(agentKey) {
  const panel = document.getElementById("tasks-panel");
  if (!panel) return;
  if (agentKey === "produtividade") {
    panel.hidden = false;
    loadTasksPanel();
  } else {
    panel.hidden = true;
  }
}

async function loadTasksPanel() {
  const panel = document.getElementById("tasks-panel");
  if (!panel || panel.hidden) return;
  panel.innerHTML = '<div class="tasks-loading">Carregando…</div>';
  try {
    const res  = await fetch("/api/tasks");
    const data = await res.json();
    renderTasksPanel(panel, data);
  } catch {
    panel.innerHTML = '<div class="tasks-offline">GTD indisponível</div>';
  }
}

function renderTasksPanel(panel, data) {
  const summary = data.summary || {};
  const tasks   = data.tasks || [];
  const today   = tasks.filter((t) => t.status === "today").slice(0, 5);
  panel.innerHTML = `
    <div class="tasks-panel-title">GTD — Produtividade</div>
    <div class="tasks-stats">
      <span class="tasks-stat">${summary.today ?? 0} hoje</span>
      <span class="tasks-stat">${summary.week ?? 0} semana</span>
      <span class="tasks-stat">${summary.inbox ?? 0} inbox</span>
    </div>
    <ul class="tasks-list">
      ${today.map((t) => `
        <li class="pri-${t.priority || "medium"}">${escapeHtml(t.title)}</li>
      `).join("") || "<li>Nenhuma tarefa para hoje</li>"}
    </ul>
  `;
}

function toggleSentinelaPanel(agentKey) {
  const panel = document.getElementById("sentinela-panel");
  if (!panel) return;
  if (agentKey === "sentinela" || agentKey === "juridico") {
    panel.hidden = false;
    loadSentinelaPanel();
  } else {
    panel.hidden = true;
  }
}

async function loadSentinelaPanel() {
  const panel = document.getElementById("sentinela-panel");
  if (!panel || panel.hidden) return;
  panel.innerHTML = '<div class="sentinela-loading">Carregando…</div>';
  try {
    const res  = await fetch("/api/sentinela/resumo");
    const data = await res.json();
    renderSentinelaPanel(panel, data);
  } catch {
    panel.innerHTML = '<div class="sentinela-offline">Sentinela indisponível</div>';
  }
}

function renderSentinelaPanel(panel, data) {
  const r = data.resumo || {};
  if (r.offline) {
    panel.innerHTML = '<div class="sentinela-offline">Banco Sentinela offline</div>';
    return;
  }
  const sev = data.alertas_por_severidade || {};
  const alertas = (data.alertas_criticos || []).slice(0, 3);
  panel.innerHTML = `
    <div class="sentinela-panel-title">Painel Sentinela</div>
    <div class="sentinela-stats">
      <span class="sentinela-stat">${r.alertas_abertos ?? 0} alertas</span>
      <span class="sentinela-stat sev-alta">${sev.alta ?? 0} alta</span>
      <span class="sentinela-stat sev-media">${sev.media ?? 0} média</span>
    </div>
    <ul class="sentinela-alerts">
      ${alertas.map((a) => `
        <li class="sev-${a.severidade || 'baixa'}">
          <strong>${escapeHtml(a.fornecedor || "N/D")}</strong>
          <span>${escapeHtml(a.tipo || "")}</span>
        </li>
      `).join("") || "<li>Nenhum alerta crítico</li>"}
    </ul>
  `;
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

async function handoffToJuridico(dossier, sources) {
  if (state.isStreaming) return;
  try {
    const res = await fetch("/api/handoff/juridico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dossier, sources: sources || [] }),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();
    state.currentAgent = "juridico";
    state.agentLocked = true;
    state.activeSkill = data.skill || "parecer";
    updateBadge("juridico");
    agentBadge.classList.add("locked");
    updateSkillBadge("juridico");
    toggleSentinelaPanel("juridico");
    appendSystemMessage("Dossiê encaminhado ao Jurídico — gerando parecer…");
    dispatchMessage(data.message);
  } catch {
    appendSystemMessage("Erro ao encaminhar dossiê ao Jurídico");
  }
}

// ── Agent dropdown ────────────────────────────────────
Object.entries(AGENT_META).forEach(([key, meta]) => {
  const btn = document.createElement("button");
  btn.classList.add("agent-option");
  btn.dataset.agent = key;
  btn.appendChild(lucideIcon(meta.icon, 15));
  const labelSpan = document.createElement("span");
  labelSpan.textContent = meta.label;
  btn.appendChild(labelSpan);
  btn.addEventListener("click", () => {
    updateBadge(key);
    state.agentLocked = true;
    agentBadge.classList.add("locked");
    agentDropdown.setAttribute("hidden", "");
  });
  agentDropdown.appendChild(btn);
});
lucide.createIcons();

agentBadge.addEventListener("click", () => {
  skillDropdown.setAttribute("hidden", "");
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
  if (skillBadge && !skillBadge.contains(e.target) && !skillDropdown.contains(e.target)) {
    skillDropdown.setAttribute("hidden", "");
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

// ── Lucide icon helper ────────────────────────────────
function lucideIcon(name, size = 16) {
  const el = document.createElement("span");
  el.classList.add("lucide-icon");
  el.dataset.lucide = name;
  el.style.cssText = `width:${size}px;height:${size}px;display:inline-flex;align-items:center;justify-content:center`;
  return el;
}

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
  if (role === "user") {
    avatar.textContent = "U";
  } else {
    avatar.appendChild(lucideIcon(meta.icon, 16));
  }

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
  lucide.createIcons();
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

// ── File chip ─────────────────────────────────────────
function clearFileChip() {
  attachedFile = null;
  fileChip.setAttribute("hidden", "");
  fileChipIcon.innerHTML = "";
  fileChipName.textContent = "";
}
fileChipRemove.addEventListener("click", clearFileChip);

// ── Universal file upload ─────────────────────────────
attachBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;
  fileInput.value = "";

  const ext = file.name.split(".").pop().toLowerCase();
  const validExts = ["pdf", "jpg", "jpeg", "png", "txt"];
  if (!validExts.includes(ext)) {
    appendSystemMessage(`❌ Tipo não suportado: .${ext}`);
    return;
  }

  const iconName = ["jpg", "jpeg", "png"].includes(ext) ? "image" : "file-text";
  fileChipIcon.innerHTML = "";
  fileChipIcon.appendChild(lucideIcon(iconName, 12));
  lucide.createIcons();
  fileChipName.textContent = file.name.length > 20 ? file.name.slice(0, 20) + "…" : file.name;
  fileChip.removeAttribute("hidden");

  try {
    if (ext === "pdf") {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("session_id", sessionId);
      if (state.currentAgent === "conhecimento" || state.currentAgent === "leitor") {
        fd.append("persist", "1");
      }
      const res  = await fetch("/upload/pdf", { method: "POST", body: fd });
      const data = await res.json();
      if (data.success) {
        attachedFile = { type: "pdf", filename: data.filename, text: data.text, pages: data.pages };
        if (data.knowledge_id) loadKnowledgePanel();
      } else {
        clearFileChip();
        appendSystemMessage(`❌ Erro: ${data.error}`);
      }
    } else if (["jpg", "jpeg", "png"].includes(ext)) {
      const fd = new FormData();
      fd.append("file", file);
      const res  = await fetch("/upload/image", { method: "POST", body: fd });
      const data = await res.json();
      if (data.success) {
        attachedFile = { type: "image", filename: data.filename, image_id: data.image_id };
      } else {
        clearFileChip();
        appendSystemMessage(`❌ Erro: ${data.error}`);
      }
    } else if (ext === "txt") {
      const text = await file.text();
      attachedFile = { type: "txt", filename: file.name, text };
      if (state.currentAgent === "conhecimento" || state.currentAgent === "leitor") {
        fetch("/api/knowledge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: file.name, text, filename: file.name, source: "txt" }),
        }).then(() => loadKnowledgePanel()).catch(() => {});
      }
    }
  } catch {
    clearFileChip();
    appendSystemMessage("❌ Erro ao processar arquivo");
  }
});

// ── Submit / stream ───────────────────────────────────
async function dispatchMessage(message) {
  if (!message) return;

  if (!state.agentLocked) {
    state.agentLocked = true;
    agentBadge.classList.add("locked");
  }

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
  form.classList.add("aurora-active");
  sendBtn.style.display = "none";
  stopBtn.style.display = "flex";

  const agentSnap = state.currentAgent;
  const skillSnap = state.activeSkill;
  const meta      = AGENT_META[agentSnap];

  const row = document.createElement("div");
  row.classList.add("msg-row", "assistant");

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.appendChild(lucideIcon(meta.icon, 16));

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
  lucide.createIcons();
  scrollToBottom();

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
  }, 2500);

  let progressSteps = null;
  let finalized     = false;
  let charBuffer    = [];
  let rawText       = "";
  let rafId         = null;
  let firstToken    = true;
  let streamDone    = false;
  let providerRef   = null;
  let es            = null;
  let streamSources = [];

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
    if (rafId) { clearTimeout(rafId); cancelAnimationFrame(rafId); }
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

    if (agentSnap === "investigador" && rawText.trim()) {
      const handoffBtn = document.createElement("button");
      handoffBtn.type = "button";
      handoffBtn.className = "handoff-btn";
      handoffBtn.textContent = "Gerar parecer jurídico";
      handoffBtn.title = "Enviar dossiê ao agente Jurídico";
      handoffBtn.addEventListener("click", () => handoffToJuridico(rawText, streamSources));
      bubbleMeta.appendChild(handoffBtn);
    }

    if (progressSteps) {
      setTimeout(() => {
        progressSteps.style.transition = "opacity 0.5s";
        progressSteps.style.opacity    = "0";
        setTimeout(() => progressSteps && progressSteps.remove(), 500);
      }, 1500);
    }

    clearFileChip();
    state.isStreaming = false;
    form.classList.remove("aurora-active");
    stopBtn.style.display = "none";
    sendBtn.style.display = "flex";
    stopBtn.removeEventListener("click", handleStop);
    input.focus();

    if (typeof loadConversations === "function") loadConversations();
    if (agentSnap === "produtividade") loadTasksPanel();
    if (agentSnap === "sentinela" || agentSnap === "juridico") loadSentinelaPanel();
    setTimeout(dequeueAndSend, 0);
  }

  function drainBuffer() {
    if (charBuffer.length) {
      const chunk = charBuffer.splice(0, 4).join("");
      rawText += chunk;
      body.innerHTML = marked.parse(rawText);
      scrollToBottom();
    }
    if (!streamDone || charBuffer.length) {
      rafId = setTimeout(() => requestAnimationFrame(drainBuffer), 20);
    } else {
      finalizeUI(providerRef);
    }
  }
  rafId = requestAnimationFrame(drainBuffer);

  function handleStop() {
    streamDone = true;
    charBuffer = [];
    if (es) es.close();
    finalizeUI(null);
    appendSystemMessage("Geração interrompida");
  }
  stopBtn.addEventListener("click", handleStop);

  let messageToSend = message;
  let _imageId = null;
  if (attachedFile) {
    const att = attachedFile;
    const isLeitorPdf = att.type === "pdf" && agentSnap === "leitor";
    if (!isLeitorPdf) {
      if (att.type === "image") {
        _imageId = att.image_id;
      } else if (att.type === "pdf") {
        messageToSend = `[Documento PDF: ${att.filename} — ${att.pages} pág.]\n${att.text}\n\n${message}`;
      } else if (att.type === "txt") {
        messageToSend = `[Arquivo de texto: ${att.filename}]\n${att.text}\n\n${message}`;
      }
    }
    clearFileChip();
  }
  const params = new URLSearchParams({ message: messageToSend, agent: agentSnap, session_id: sessionId });
  if (state.currentConvId) params.set("conv_id", state.currentConvId);
  if (_imageId) params.set("image_id", _imageId);
  if (skillSnap) params.set("skill", skillSnap);
  es = new EventSource(`/chat/stream?${params}`);

  es.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.error) {
      charBuffer = [];
      body.textContent = `Erro: ${data.error}`;
      streamDone = true;
      finalizeUI(null);
      return;
    }

    if (data.progress) {
      clearInterval(phraseInterval);
      if (thinkingEl.parentNode) {
        thinkingEl.classList.add("thinking-fade-out");
        setTimeout(() => thinkingEl.parentNode && thinkingEl.remove(), 350);
      }

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

    if (data.sources && data.sources.length) {
      streamSources = data.sources;
      const sourcesEl = document.createElement("div");
      sourcesEl.className = "message-sources";
      sourcesEl.innerHTML =
        `<div class="sources-title">Fontes</div><ol class="sources-list">` +
        data.sources.map((s) =>
          `<li><span class="src-n">[${s.n}]</span> ` +
          (s.url
            ? `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.title)}</a>`
            : escapeHtml(s.title)) +
          `</li>`
        ).join("") +
        `</ol>`;
      bubble.insertBefore(sourcesEl, body);
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
      charBuffer.push(...data.token.split(""));
      if (firstToken) {
        firstToken = false;
        clearInterval(phraseInterval);
        thinkingEl.classList.add("thinking-fade-out");
        setTimeout(() => thinkingEl.parentNode && thinkingEl.remove(), 350);
      }
    }

    if (data.done) {
      providerRef = data.provider;
      if (data.full_response && !rawText && !charBuffer.length) {
        rawText = data.full_response;
      }
      streamDone = true;
      es.close();
    }
  };

  es.onerror = () => {
    if (!rawText && !charBuffer.length) {
      body.innerHTML = "Erro de conexão com o servidor.";
    }
    streamDone = true;
    charBuffer = [];
    finalizeUI(null);
  };
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  if (state.isStreaming) {
    enqueueMessage(message);
    return;
  }

  if (message === "/limpar") {
    input.value = "";
    input.style.height = "auto";
    state.messageQueue = [];
    renderMessageQueue();
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

  dispatchMessage(message);
});

// ── Conversation search ───────────────────────────────
let _searchTimer = null;
const convSearch = document.getElementById("conv-search");
if (convSearch) {
  convSearch.addEventListener("input", () => {
    clearTimeout(_searchTimer);
    const q = convSearch.value.trim();
    if (!q) {
      loadConversations();
      return;
    }
    _searchTimer = setTimeout(async () => {
      try {
        const res  = await fetch(`/api/conversations/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        renderSearchResults(data.results || []);
      } catch { /* ignore */ }
    }, 300);
  });
}

function buildConvItem(conv) {
  const item = document.createElement("div");
  item.classList.add("conv-item");
  if (conv.id === state.currentConvId) item.classList.add("active");
  item.dataset.convId = conv.id;

  const iconEl = document.createElement("span");
  iconEl.classList.add("conv-item-icon");
  iconEl.appendChild(lucideIcon((AGENT_META[conv.agent] || AGENT_META.conhecimento).icon, 14));

  const titleEl = document.createElement("span");
  titleEl.classList.add("conv-item-title");
  titleEl.textContent = conv.title;
  titleEl.title = "Duplo-clique para renomear";

  const actions = document.createElement("div");
  actions.className = "conv-item-actions";

  const renameBtn = document.createElement("button");
  renameBtn.type = "button";
  renameBtn.className = "conv-action-btn";
  renameBtn.title = "Renomear";
  renameBtn.textContent = "✎";
  renameBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    renameConversation(conv.id, titleEl);
  });

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "conv-action-btn conv-action-delete";
  deleteBtn.title = "Excluir";
  deleteBtn.textContent = "×";
  deleteBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    deleteConversation(conv.id, conv.title);
  });

  actions.appendChild(renameBtn);
  actions.appendChild(deleteBtn);

  titleEl.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    renameConversation(conv.id, titleEl);
  });

  item.appendChild(iconEl);
  item.appendChild(titleEl);
  item.appendChild(actions);

  if (conv.snippet) {
    const snip = document.createElement("span");
    snip.classList.add("conv-item-snippet");
    snip.textContent = conv.snippet.replace(/\*\*/g, "");
    item.appendChild(snip);
  }

  item.addEventListener("click", () => loadConversation(conv.id, conv.agent));
  return item;
}

async function renameConversation(convId, titleEl) {
  const current = titleEl.textContent;
  const next = prompt("Novo título da conversa:", current);
  if (!next || next.trim() === current) return;
  try {
    const res = await fetch(`/api/conversations/${convId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: next.trim() }),
    });
    if (!res.ok) throw new Error();
    titleEl.textContent = next.trim().slice(0, 80);
  } catch {
    appendSystemMessage("Erro ao renomear conversa");
  }
}

async function deleteConversation(convId, title) {
  if (!confirm(`Excluir conversa "${title}"?`)) return;
  try {
    const res = await fetch(`/api/conversations/${convId}`, { method: "DELETE" });
    if (!res.ok) throw new Error();
    if (state.currentConvId === convId) newConversation();
    loadConversations();
  } catch {
    appendSystemMessage("Erro ao excluir conversa");
  }
}

function renderSearchResults(results) {
  const list = document.getElementById("conv-list");
  list.innerHTML = "";
  if (!results.length) {
    list.innerHTML = '<div class="conv-group-label">Nenhum resultado</div>';
    return;
  }
  const groupEl = document.createElement("div");
  groupEl.classList.add("conv-group-label");
  groupEl.textContent = "Resultados";
  list.appendChild(groupEl);
  for (const conv of results) {
    list.appendChild(buildConvItem(conv));
  }
  lucide.createIcons();
}

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
      list.appendChild(buildConvItem(conv));
    }
  }
  lucide.createIcons();
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
    addExportButton(convId);
  } catch {
    appendSystemMessage("Erro ao carregar conversa");
  }

  input.focus();
}

function addExportButton(convId) {
  const existing = document.getElementById("export-conv-btn");
  if (existing) existing.remove();
  const btn = document.createElement("button");
  btn.id = "export-conv-btn";
  btn.className = "export-conv-btn";
  btn.textContent = "Exportar MD";
  btn.title = "Exportar conversa em Markdown";
  btn.addEventListener("click", () => {
    window.open(`/api/conversations/${convId}/export?format=md`, "_blank");
  });
  chatInner.insertBefore(btn, chatInner.firstChild);
}

function newConversation() {
  if (state.isStreaming) return;

  state.currentConvId = null;
  state.currentAgent  = "conhecimento";
  state.agentLocked   = false;
  clearFileChip();

  chatInner.innerHTML = "";
  app.classList.add("layout-empty");

  const exportBtn = document.getElementById("export-conv-btn");
  if (exportBtn) exportBtn.remove();

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
attachBtn.style.display = "flex";
loadConversations();
loadStatus();
setInterval(loadStatus, 30_000);
input.focus();

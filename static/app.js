const chatInner = document.getElementById("chat-inner");
const chatArea  = document.getElementById("chat-area");
const form      = document.getElementById("chat-form");
const input     = document.getElementById("message-input");
const sendBtn   = document.getElementById("send-btn");
const agentLabel = document.getElementById("current-agent-label");

let currentAgent = "conhecimento";
const sessionId = crypto.randomUUID();
const attachBtn = document.getElementById("attachBtn");
const pdfInput  = document.getElementById("pdfInput");
const stopBtn   = document.getElementById("stop-btn");

marked.setOptions({ breaks: true, gfm: true });

// ── Provider status dots ──────────────────────────────────────
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
      const online  = info.status === "online";
      dot.className = `status-dot ${online ? "online" : "offline"}`;
      const lat     = info.latency_ms != null ? ` · ${info.latency_ms}ms` : "";
      dot.title     = `${name}: ${info.status}${lat}`;
    }
  } catch {
    Object.values(_statusDots).forEach((d) => {
      d.className = "status-dot offline";
      d.title     = `${d.dataset.provider}: erro`;
    });
  }
}

fetchStatus();
setInterval(fetchStatus, 30000);

// ── Agent tab switching ───────────────────────────────────────
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentAgent = tab.dataset.agent;
    agentLabel.textContent = tab.textContent.trim();
    const isLeitor = currentAgent === "leitor";
    attachBtn.style.display = isLeitor ? "flex" : "none";
    form.classList.toggle("has-attach", isLeitor);
  });
});

// ── PDF upload ────────────────────────────────────────────────
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
      if (data.truncated) {
        appendSystemMessage("⚠️ Documento grande — analisando primeiras 20 + últimas 5 páginas");
      }
    } else {
      appendSystemMessage(`❌ Erro: ${data.error}`);
    }
  } catch {
    appendSystemMessage("❌ Erro ao enviar arquivo");
  }
});

// ── Helpers ───────────────────────────────────────────────────
function scrollToBottom() {
  chatArea.scrollTo({ top: chatArea.scrollHeight, behavior: "smooth" });
}

function nowTime() {
  return new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function removeWelcome() {
  const w = chatInner.querySelector(".welcome");
  if (w) w.remove();
}

function appendMessage(role, text, agentName) {
  removeWelcome();

  const row = document.createElement("div");
  row.classList.add("msg-row", role);

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.textContent = role === "user" ? "U" : agentName[0].toUpperCase();

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");

  const body = document.createElement("div");
  body.textContent = text;

  const meta = document.createElement("div");
  meta.classList.add("bubble-meta");
  meta.textContent = role === "user" ? nowTime() : `${agentName} · ${nowTime()}`;

  bubble.appendChild(body);
  bubble.appendChild(meta);
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatInner.appendChild(row);
  scrollToBottom();
  return row;
}

// ── System message ────────────────────────────────────────────
function appendSystemMessage(text) {
  removeWelcome();
  const el = document.createElement("div");
  el.classList.add("system-msg");
  el.textContent = `— ${text} —`;
  chatInner.appendChild(el);
  scrollToBottom();
}

// ── Submit ────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  // ── /limpar command ──────────────────────────────────────────
  if (message === "/limpar") {
    input.value = "";
    try {
      await fetch("/chat/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: currentAgent, session_id: sessionId }),
      });
    } catch {
      // best-effort: clear UI regardless of network result
    }
    chatInner.innerHTML = "";
    appendSystemMessage("Histórico limpo");
    input.focus();
    return;
  }

  appendMessage("user", message, "Você");
  input.value = "";
  sendBtn.disabled = true;
  sendBtn.style.display = "none";
  stopBtn.style.display = "flex";

  // Snapshot agent in case user switches tabs mid-stream
  const agentSnap = currentAgent;

  // Build streaming bubble upfront
  const row = document.createElement("div");
  row.classList.add("msg-row", "assistant");

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.textContent = agentSnap[0].toUpperCase();

  const bubble = document.createElement("div");
  bubble.classList.add("bubble", "streaming");

  const body = document.createElement("div");
  body.classList.add("bubble-body");

  const meta = document.createElement("div");
  meta.classList.add("bubble-meta");

  bubble.appendChild(body);
  bubble.appendChild(meta);
  row.appendChild(avatar);
  row.appendChild(bubble);
  chatInner.appendChild(row);
  scrollToBottom();

  const params = new URLSearchParams({ message, agent: agentSnap, session_id: sessionId });
  const es = new EventSource(`/chat/stream?${params}`);

  let progressSteps = null;
  let finalized = false;

  function finalize(provider = null) {
    if (finalized) return;
    finalized = true;
    bubble.classList.remove("streaming");
    if (body.textContent) {
      body.innerHTML = marked.parse(body.textContent);
    }
    const timeSpan = document.createElement("span");
    timeSpan.textContent = `${agentSnap} · ${nowTime()}`;
    meta.appendChild(timeSpan);
    if (provider) {
      const badge = document.createElement("span");
      badge.classList.add("provider-badge", `provider-${provider}`);
      badge.textContent = provider;
      meta.appendChild(badge);
    }
    es.close();
    stopBtn.style.display = "none";
    sendBtn.style.display = "flex";
    sendBtn.disabled = false;
    stopBtn.removeEventListener("click", handleStop);
    input.focus();
  }

  function handleStop() {
    finalize();
    appendSystemMessage("Geração interrompida");
  }

  stopBtn.addEventListener("click", handleStop);

  es.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.error) {
      body.textContent = `Erro: ${data.error}`;
      finalize();
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
      img.src = `data:image/png;base64,${data.chart}`;
      img.classList.add("chart-output");
      img.alt = "Gráfico gerado pelo Analista";
      bubble.insertBefore(img, body);
      scrollToBottom();
    }

    if (data.token) {
      body.textContent += data.token;
      scrollToBottom();
    }

    if (data.done) {
      if (progressSteps) {
        setTimeout(() => {
          progressSteps.style.transition = "opacity 0.5s";
          progressSteps.style.opacity = "0";
          setTimeout(() => progressSteps && progressSteps.remove(), 500);
        }, 2000);
      }
      finalize(data.provider);
    }
  };

  es.onerror = () => {
    if (!body.textContent) {
      body.textContent = "Erro de conexão com o servidor.";
    }
    finalize();
  };
});

input.focus();

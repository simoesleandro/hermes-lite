const chatInner = document.getElementById("chat-inner");
const chatArea  = document.getElementById("chat-area");
const form      = document.getElementById("chat-form");
const input     = document.getElementById("message-input");
const sendBtn   = document.getElementById("send-btn");
const agentLabel = document.getElementById("current-agent-label");

let currentAgent = "conhecimento";
const sessionId = crypto.randomUUID();

// ── Agent tab switching ───────────────────────────────────────
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentAgent = tab.dataset.agent;
    agentLabel.textContent = tab.textContent.trim();
  });
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

// ── Submit ────────────────────────────────────────────────────
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  appendMessage("user", message, "Você");
  input.value = "";
  sendBtn.disabled = true;

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

  function finalize() {
    bubble.classList.remove("streaming");
    meta.textContent = `${agentSnap} · ${nowTime()}`;
    es.close();
    sendBtn.disabled = false;
    input.focus();
  }

  es.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.error) {
      body.textContent = `Erro: ${data.error}`;
      finalize();
      return;
    }

    if (data.token) {
      body.textContent += data.token;
      scrollToBottom();
    }

    if (data.done) {
      finalize();
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

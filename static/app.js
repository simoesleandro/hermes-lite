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

function showTyping() {
  removeWelcome();
  const row = document.createElement("div");
  row.classList.add("msg-row", "assistant", "typing");
  row.id = "typing-indicator";

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.textContent = currentAgent[0].toUpperCase();

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    dot.classList.add("dot");
    bubble.appendChild(dot);
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatInner.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  const t = document.getElementById("typing-indicator");
  if (t) t.remove();
}

// ── Submit ────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  appendMessage("user", message, "Você");
  input.value = "";
  sendBtn.disabled = true;
  showTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, agent: currentAgent, session_id: sessionId }),
    });

    const data = await res.json();
    removeTyping();

    if (!res.ok) {
      appendMessage("assistant", `Erro: ${data.error}`, currentAgent);
    } else {
      appendMessage("assistant", data.response, data.agent);
    }
  } catch {
    removeTyping();
    appendMessage("assistant", "Erro de conexão com o servidor.", currentAgent);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

input.focus();

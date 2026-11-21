
"use strict";

// ==========================================
// 1. CONFIGURAÇÕES
// ==========================================

const API_URL = "http://127.0.0.1:8000";

const STORAGE_KEY = "steribot-messages";
const SESSION_KEY = "steribot-session-id";

let messages = [];
let sessionId = localStorage.getItem(SESSION_KEY);
let isSending = false;
let typingIndicatorEl = null;


// ==========================================
// 2. ELEMENTOS DA INTERFACE
// ==========================================

const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const welcomePanel = document.getElementById("welcomePanel");

const quickActionButtons = document.querySelectorAll(
  ".quick-action"
);


// ==========================================
// 3. UTILITÁRIOS
// ==========================================

function generateId() {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}


function formatTimestamp(date = new Date()) {
  return date.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}


function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}


function setSendingState(sending) {
  isSending = sending;

  sendBtn.disabled = sending;
  inputEl.disabled = sending;

  sendBtn.textContent = sending ? "Enviando..." : "Enviar";

  quickActionButtons.forEach((button) => {
    button.disabled = sending;
  });
}


// ==========================================
// 4. TELA INICIAL
// ==========================================

function showWelcomePanel() {
  if (welcomePanel) {
    welcomePanel.hidden = false;
  }
}


function hideWelcomePanel() {
  if (welcomePanel) {
    welcomePanel.hidden = true;
  }
}


// ==========================================
// 5. ARMAZENAMENTO LOCAL
// ==========================================

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);

    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter((message) =>
      message &&
      typeof message.id === "string" &&
      (message.sender === "user" || message.sender === "bot") &&
      typeof message.text === "string" &&
      typeof message.timestamp === "string"
    );

  } catch {
    return [];
  }
}


function saveMessages() {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(messages)
    );
  } catch {
    console.warn("Não foi possível salvar o histórico.");
  }
}


function saveSessionId(id) {
  sessionId = id;

  try {
    localStorage.setItem(SESSION_KEY, id);
  } catch {
    console.warn("Não foi possível salvar a sessão.");
  }
}


// ==========================================
// 6. RENDERIZAÇÃO DAS MENSAGENS
// ==========================================

function createMessageElement(message) {
  const wrapper = document.createElement("article");

  wrapper.className = `message message--${message.sender}`;
  wrapper.dataset.id = message.id;

  const text = document.createElement("p");
  text.className = "message__text";
  text.textContent = message.text;

  const timestamp = document.createElement("time");
  timestamp.className = "message__timestamp";
  timestamp.textContent = message.timestamp;

  wrapper.append(text, timestamp);

  return wrapper;
}


function appendMessage(message) {
  hideWelcomePanel();

  messages.push(message);

  messagesEl.appendChild(
    createMessageElement(message)
  );

  saveMessages();
  scrollToBottom();
}


function addMessage(sender, text) {
  appendMessage({
    id: generateId(),
    sender,
    text,
    timestamp: formatTimestamp()
  });
}


// ==========================================
// 7. INDICADOR DE DIGITAÇÃO
// ==========================================

function showTypingIndicator() {
  if (typingIndicatorEl) {
    return;
  }

  typingIndicatorEl = document.createElement("div");

  typingIndicatorEl.className = "typing";
  typingIndicatorEl.setAttribute("role", "status");
  typingIndicatorEl.setAttribute(
    "aria-label",
    "STERIBOT está respondendo"
  );

  for (let i = 0; i < 3; i += 1) {
    const dot = document.createElement("span");
    dot.className = "typing__dot";
    typingIndicatorEl.appendChild(dot);
  }

  messagesEl.appendChild(typingIndicatorEl);

  scrollToBottom();
}


function removeTypingIndicator() {
  if (!typingIndicatorEl) {
    return;
  }

  typingIndicatorEl.remove();
  typingIndicatorEl = null;
}


// ==========================================
// 8. COMUNICAÇÃO COM A API
// ==========================================

async function enviarParaAPI(mensagem) {
  const dados = {
    mensagem: mensagem,
    sessao_id: sessionId
  };

  const response = await fetch(
    `${API_URL}/atendimento`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(dados)
    }
  );

  if (!response.ok) {
    const erro = await response.json().catch(() => ({}));

    throw new Error(
      erro.detail || `Erro na API: HTTP ${response.status}`
    );
  }

  const resultado = await response.json();

  if (resultado.sessao_id) {
    saveSessionId(resultado.sessao_id);
  }

  return resultado;
}


// ==========================================
// 9. ENVIO DE MENSAGENS
// ==========================================

async function handleSend(textoInicial = null) {
  if (isSending) {
    return;
  }

  const text = (
    textoInicial !== null
      ? textoInicial
      : inputEl.value
  ).trim();

  if (!text) {
    return;
  }

  addMessage("user", text);

  inputEl.value = "";
  autoResizeInput();

  setSendingState(true);
  showTypingIndicator();

  try {
    const resultado = await enviarParaAPI(text);

    removeTypingIndicator();

    addMessage(
      "bot",
      resultado.resposta || "Não foi possível obter uma resposta."
    );

  } catch (erro) {
    removeTypingIndicator();

    console.error("Erro na comunicação:", erro);

    addMessage(
      "bot",
      `Não consegui processar sua solicitação. Detalhes: ${erro.message}`
    );

  } finally {
    setSendingState(false);
    inputEl.focus();
  }
}


// ==========================================
// 10. OPÇÕES DE EQUIPAMENTOS
// ==========================================

function handleQuickAction(event) {
  const mensagem = event.currentTarget.dataset.message;

  if (mensagem) {
    handleSend(mensagem);
  }
}


quickActionButtons.forEach((button) => {
  button.addEventListener("click", handleQuickAction);
});


// ==========================================
// 11. CAMPO DE TEXTO
// ==========================================

function autoResizeInput() {
  inputEl.style.height = "auto";

  inputEl.style.height = `${
    Math.min(inputEl.scrollHeight, 120)
  }px`;
}


// ==========================================
// 12. NOVA CONVERSA
// ==========================================

async function clearHistory() {
  if (isSending) {
    return;
  }

  const sessaoAnterior = sessionId;

  // Limpa somente as mensagens.
  // Preserva o painel de boas-vindas e suas opções.
  messagesEl.querySelectorAll(".message").forEach((element) => {
    element.remove();
  });

  removeTypingIndicator();

  // Limpa os dados da conversa anterior.
  messages = [];

  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(SESSION_KEY);

  sessionId = null;

  // Retorna à tela inicial.
  showWelcomePanel();

  // Solicita a exclusão da sessão no backend.
  if (sessaoAnterior) {
    try {
      const response = await fetch(
        `${API_URL}/atendimento/${encodeURIComponent(sessaoAnterior)}`,
        {
          method: "DELETE"
        }
      );

      if (!response.ok && response.status !== 404) {
        console.warn("Não foi possível encerrar a sessão anterior.");
      }

    } catch (erro) {
      console.warn("Falha ao encerrar sessão:", erro);
    }
  }

  inputEl.value = "";
  autoResizeInput();
  inputEl.focus();

  scrollToBottom();
}


// ==========================================
// 13. EVENTOS
// ==========================================

sendBtn.addEventListener("click", () => {
  handleSend();
});


inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    handleSend();
  }
});


inputEl.addEventListener("input", autoResizeInput);

clearBtn.addEventListener("click", clearHistory);


// ==========================================
// 14. INICIALIZAÇÃO
// ==========================================

function init() {
  messages = loadMessages();

  if (messages.length > 0) {
    hideWelcomePanel();

    const fragment = document.createDocumentFragment();

    messages.forEach((message) => {
      fragment.appendChild(
        createMessageElement(message)
      );
    });

    messagesEl.appendChild(fragment);

  } else {
    showWelcomePanel();
  }

  scrollToBottom();
  inputEl.focus();
}


init();

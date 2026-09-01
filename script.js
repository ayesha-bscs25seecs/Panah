/**
 * Panah — script.js
 * ~~~~~~~~~~~~~~~~~~
 * Frontend logic for the Panah WhatsApp-style AI chat interface.
 *
 * FEATURES
 *  - Sends questions to the Flask /ask API and displays replies
 *  - Voice input via browser SpeechRecognition (toggleable Urdu/English)
 *  - Voice output via browser SpeechSynthesis (auto-reads bot replies)
 *  - Typing indicator while waiting for the backend
 *  - Graceful fallback if speech APIs are unavailable
 *  - Guests: nothing is stored or logged client-side (privacy-by-default)
 *  - Logged-in users: left sidebar with "New chat" + chat history
 *
 * CHAT HISTORY — PLACEHOLDER ONLY, NOT YET WIRED TO A BACKEND
 *  The sidebar's history list, save, and load logic below (see SIDEBAR /
 *  CHAT HISTORY section) currently just holds chats in an in-memory array
 *  (`allChatsPlaceholder`). It is NOT persisted anywhere — a page reload
 *  clears it, same as a guest's chat. This is intentional: it exists so
 *  the UI is demoable and the real logic can be dropped in later without
 *  restructuring the rest of the file. Every spot that needs real backend
 *  calls (save chat, list chats, load one chat) is marked "TODO(backend)".
 *
 * LOGIN STATE
 *  auth.html is expected to set localStorage["panah_logged_in"] = "1"
 *  (and optionally "panah_user_label" with a display name/phone) on
 *  successful OTP verification, then redirect back here. This file reads
 *  that flag on load to decide whether to show the sidebar or the
 *  guest login button. This part IS real/kept as-is — only chat history
 *  storage was pulled back out.
 *
 * EXTENSION POINTS (for teammates)
 *  - Add a settings screen: wire up a gear icon in the header and
 *    create a modal overlay; persist prefs in sessionStorage only.
 *  - Add a language switch: swap SPEECH_LANG and update placeholder text.
 *
 * @version 1.3.0
 */

/* ===================================================================
   1. CONFIGURATION
   =================================================================== */

/** Backend API base URL — change this if your server moves. */
const API_BASE = "http://127.0.0.1:5000";

/** Timeout (ms) for each fetch request to the backend. */
const REQUEST_TIMEOUT_MS = 15000;

/** Maximum characters allowed per question. */
const MAX_QUESTION_LENGTH = 500;

/** Language code for speech OUTPUT (bot reading replies aloud). Unchanged. */
const SPEECH_LANG = "ur-PK";

/**
 * Language codes for speech INPUT (mic transcription).
 * The browser's SpeechRecognition API can only listen in one language per
 * recording session — it cannot auto-detect which language is being spoken.
 * This is why a manual toggle is needed instead of relying on detection.
 */
const MIC_LANGUAGES = {
  ur: "ur-PK",
  en: "en-US",
};

/** Welcome message shown when a fresh chat starts. */
const WELCOME_MESSAGE =
  "Assalamu Alaikum! Main Panah hoon — aapka mahfooz sahara. " +
  "Aap mujhse mehr, nafaqa, zakat, wirasat ya kisi bhi maali haq ke baare mein " +
  "poochh sakti hain. Apna sawaal likhein ya mic dabaa kar bolein. " +
  "Aapki baat bilkul mehfooz hai — kuch bhi save nahi hota.";

/** Welcome message variant for logged-in users (storage note differs). */
const WELCOME_MESSAGE_LOGGED_IN =
  "Assalamu Alaikum! Main Panah hoon — aapka mahfooz sahara. " +
  "Aap mujhse mehr, nafaqa, zakat, wirasat ya kisi bhi maali haq ke baare mein " +
  "poochh sakti hain. Apna sawaal likhein ya mic dabaa kar bolein.";

/** localStorage keys — login state only. Chat history is NOT stored here. */
const LS_LOGIN_FLAG   = "panah_logged_in";
const LS_USER_LABEL   = "panah_user_label";

/* ===================================================================
   2. DOM REFERENCES
   =================================================================== */

const chatArea         = document.getElementById("chat-area");
const messageInput     = document.getElementById("message-input");
const sendBtn          = document.getElementById("send-btn");
const micBtn           = document.getElementById("mic-btn");
const speakerToggle    = document.getElementById("speaker-toggle");
const speakerOnIcon    = document.getElementById("speaker-on-icon");
const speakerOffIcon   = document.getElementById("speaker-off-icon");
const typingHeader     = document.getElementById("typing-indicator-header");
const subtitleText     = document.getElementById("subtitle-text");
const continueLink     = document.getElementById("continue-link");

const sidebar           = document.getElementById("sidebar");
const sidebarToggleBtn  = document.getElementById("sidebar-toggle-btn");
const sidebarOverlay    = document.getElementById("sidebar-overlay");
const newChatBtn        = document.getElementById("new-chat-btn");
const historyListEl     = document.getElementById("chat-history-list");
const sidebarProfileLbl = document.getElementById("sidebar-profile-label");
const logoutBtn         = document.getElementById("logout-btn");

/* ===================================================================
   3. APPLICATION STATE
   =================================================================== */

/** Whether the bot voice output is currently enabled. */
let voiceEnabled = true;

/** Whether a request to the backend is currently in flight. */
let isWaiting = false;

/** Reference to the current SpeechRecognition instance (null if idle). */
let recognition = null;

/** Whether the mic is currently actively listening. */
let isListening = false;

/**
 * Which language the mic should listen in: "ur" or "en".
 */
let micLanguage = "ur";

/** Whether the current visitor is logged in (read once at init). */
let isLoggedIn = false;

/**
 * In-memory transcript of the CURRENT chat only.
 * Guests: this is never written to storage.
 * Logged-in users: persisted to the in-memory placeholder store on each turn.
 * Each entry: { text, sender: "user"|"bot", time: ISOString }
 */
let currentMessages = [];

/** id of the chat currently open, or null until the first message is sent. */
let currentChatId = null;

/**
 * PLACEHOLDER chat store — in-memory only, lost on reload.
 * TODO(backend): replace this array with real fetch() calls to a
 * save/list/load-chat API once it exists, keyed by the logged-in user.
 * Shape stays the same either way: { id, title, messages, updatedAt }
 */
let allChatsPlaceholder = [];

/* ===================================================================
   4. UTILITY HELPERS
   =================================================================== */

function formatTime(date = new Date()) {
  let hours = date.getHours();
  const mins = date.getMinutes().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  return `${hours}:${mins} ${ampm}`;
}

function safeText(text) {
  return document.createTextNode(String(text));
}

function sanitizeInput(str, maxLen = MAX_QUESTION_LENGTH) {
  if (typeof str !== "string") return "";
  return str.trim().slice(0, maxLen);
}

function generateChatId() {
  return "chat_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
}

/* ===================================================================
   5. MESSAGE RENDERING
   =================================================================== */

function appendMessage(text, sender, time = new Date(), { record = true } = {}) {
  const row = document.createElement("div");
  row.className = `msg-row ${sender}`;

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  bubble.appendChild(safeText(text));

  const ts = document.createElement("span");
  ts.className = "msg-time";
  ts.textContent = formatTime(time);

  bubble.appendChild(ts);
  row.appendChild(bubble);
  chatArea.appendChild(row);

  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });

  if (record) {
    currentMessages.push({ text, sender, time: time.toISOString() });
    if (isLoggedIn) saveCurrentChat();
  }
}

function showTypingIndicator() {
  typingHeader.hidden = false;
  subtitleText.style.display = "none";

  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.id = "typing-bubble-row";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble typing-bubble";

  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    dot.className = "dot";
    bubble.appendChild(dot);
  }

  row.appendChild(bubble);
  chatArea.appendChild(row);

  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

function hideTypingIndicator() {
  typingHeader.hidden = true;
  subtitleText.style.display = "";

  const typingRow = document.getElementById("typing-bubble-row");
  if (typingRow) typingRow.remove();
}

/* ===================================================================
   6. BACKEND API CALLS
   =================================================================== */

async function askBackend(question) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!response.ok) {
      throw new Error(`Backend returned status ${response.status}`);
    }

    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: "GET" });
    return res.ok;
  } catch {
    return false;
  }
}

/* ===================================================================
   7. SEND MESSAGE FLOW
   =================================================================== */

async function handleSend() {
  if (isWaiting) return;

  const rawInput = messageInput.value;
  const question = sanitizeInput(rawInput);

  if (!question) return;

  messageInput.value = "";

  // First message of a brand-new chat: assign it an id now so it can be
  // saved and shown in the sidebar history.
  if (isLoggedIn && !currentChatId) {
    currentChatId = generateChatId();
  }

  appendMessage(question, "user");

  isWaiting = true;
  sendBtn.disabled = true;
  showTypingIndicator();

  try {
    const data = await askBackend(question);

    hideTypingIndicator();

    const answer =
      data && typeof data.answer === "string"
        ? data.answer
        : "Jawab daryaft nahi ho saka. Dobara koshish karein.";

    appendMessage(answer, "bot");

    if (voiceEnabled) {
      speakText(answer);
    }
  } catch (err) {
    hideTypingIndicator();

    const errorMsg =
      "Maazrat, is waqt connect nahi ho pa raha. Barah-e-karam dobara koshish karein.";
    appendMessage(errorMsg, "bot");

    if (voiceEnabled) {
      speakText(errorMsg);
    }
  } finally {
    isWaiting = false;
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

/* ===================================================================
   8. SPEECH SYNTHESIS  (Text-to-Speech — bot reads replies aloud)
   =================================================================== */

function speakText(text) {
  if (!("speechSynthesis" in window)) return;

  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = SPEECH_LANG;
  utterance.rate = 0.95;
  utterance.pitch = 1.0;

  const voices = window.speechSynthesis.getVoices();
  const urduVoice = voices.find(
    (v) => v.lang === SPEECH_LANG || v.lang.startsWith("ur")
  );
  if (urduVoice) utterance.voice = urduVoice;

  window.speechSynthesis.speak(utterance);
}

function initVoices() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = () => {
      /* voices are now available for speakText() */
    };
  }
}

/* ===================================================================
   9. SPEECH RECOGNITION  (Speech-to-Text — user speaks their question)
   =================================================================== */

function initSpeechRecognition() {
  const SR =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;

  if (!SR) {
    micBtn.style.display = "none";
    micBtn.setAttribute("aria-hidden", "true");
    return null;
  }

  const rec = new SR();
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  rec.continuous = false;

  rec.addEventListener("result", (event) => {
    const transcript = event.results[0][0].transcript;
    messageInput.value = sanitizeInput(transcript);
  });

  rec.addEventListener("end", () => {
    isListening = false;
    micBtn.classList.remove("recording");
    micBtn.setAttribute("aria-label", "Speak your question");
  });

  rec.addEventListener("error", () => {
    isListening = false;
    micBtn.classList.remove("recording");
  });

  return rec;
}

function toggleMic() {
  if (!recognition) return;

  if (isListening) {
    recognition.stop();
    isListening = false;
    micBtn.classList.remove("recording");
  } else {
    recognition.lang = MIC_LANGUAGES[micLanguage];
    try {
      recognition.start();
      isListening = true;
      micBtn.classList.add("recording");
      micBtn.setAttribute("aria-label", "Stop listening");
    } catch {
      isListening = false;
      micBtn.classList.remove("recording");
    }
  }
}

/* ===================================================================
   9b. MIC LANGUAGE TOGGLE  (switch mic between Urdu and English)
   =================================================================== */

function createMicLanguageToggle() {
  if (!micBtn || !micBtn.parentNode) return null;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "mic-lang-toggle";
  btn.setAttribute("aria-label", "Switch microphone language");
  btn.title = "Switch microphone language (Urdu / English)";

  Object.assign(btn.style, {
    marginInlineStart: "6px",
    padding: "2px 8px",
    fontSize: "11px",
    fontWeight: "600",
    lineHeight: "1.6",
    borderRadius: "999px",
    border: "1px solid #075E54",
    background: "#FFFFFF",
    color: "#075E54",
    cursor: "pointer",
    userSelect: "none",
  });

  updateMicLanguageToggleLabel(btn);

  btn.addEventListener("click", () => {
    micLanguage = micLanguage === "ur" ? "en" : "ur";
    updateMicLanguageToggleLabel(btn);
  });

  micBtn.parentNode.insertBefore(btn, micBtn.nextSibling);
  return btn;
}

function updateMicLanguageToggleLabel(btn) {
  const isUrdu = micLanguage === "ur";
  btn.textContent = isUrdu ? "UR" : "EN";
  btn.title = isUrdu
    ? "Mic is listening in Urdu — tap to switch to English"
    : "Mic is listening in English — tap to switch to Urdu";
}

/* ===================================================================
   10. SPEAKER TOGGLE  (mute / unmute bot voice)
   =================================================================== */

function toggleSpeaker() {
  voiceEnabled = !voiceEnabled;

  if (voiceEnabled) {
    speakerOnIcon.removeAttribute("hidden");
    speakerOffIcon.setAttribute("hidden", "");
    speakerToggle.setAttribute("aria-label", "Mute voice replies");
  } else {
    speakerOnIcon.setAttribute("hidden", "");
    speakerOffIcon.removeAttribute("hidden");
    speakerToggle.setAttribute("aria-label", "Unmute voice replies");
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }
}

/* ===================================================================
   11. SIDEBAR / LOGIN STATE / CHAT HISTORY
   =================================================================== */

/**
 * Reads all saved chats for the logged-in user.
 * TODO(backend): replace with e.g. `await fetch(`${API_BASE}/chats`)`
 * and return the parsed JSON list instead of the in-memory array.
 */
function loadAllChats() {
  return allChatsPlaceholder;
}

/**
 * Persists the full chat list.
 * TODO(backend): replace with a real save call — likely per-chat
 * (`POST /chats` / `PUT /chats/:id`) rather than resending the whole
 * list every time, once that endpoint exists.
 */
function saveAllChats(chats) {
  allChatsPlaceholder = chats;
}

/** Derives a short title from the first user message in a chat. */
function deriveChatTitle(messages) {
  const firstUser = messages.find((m) => m.sender === "user");
  const base = firstUser ? firstUser.text : "Nayi guftagu";
  return base.length > 40 ? base.slice(0, 40) + "…" : base;
}

/** Upserts the current in-progress chat into the placeholder store. */
function saveCurrentChat() {
  if (!currentChatId || currentMessages.length === 0) return;

  const chats = loadAllChats();
  const existingIndex = chats.findIndex((c) => c.id === currentChatId);
  const chatRecord = {
    id: currentChatId,
    title: deriveChatTitle(currentMessages),
    messages: currentMessages,
    updatedAt: new Date().toISOString(),
  };

  if (existingIndex >= 0) {
    chats[existingIndex] = chatRecord;
  } else {
    chats.unshift(chatRecord);
  }

  saveAllChats(chats);
  renderHistoryList();
}

/** Renders the sidebar's chat history list from the placeholder store. */
function renderHistoryList() {
  if (!historyListEl) return;

  const chats = loadAllChats().sort(
    (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)
  );

  historyListEl.innerHTML = "";

  if (chats.length === 0) {
    const note = document.createElement("p");
    note.className = "sidebar-empty-note";
    note.textContent = "Abhi tak koi guftagu save nahi hui.";
    historyListEl.appendChild(note);
    return;
  }

  chats.forEach((chat) => {
    const li = document.createElement("li");
    li.className = "history-item";
    li.dataset.chatId = chat.id;
    li.textContent = chat.title;
    if (chat.id === currentChatId) li.classList.add("active");
    li.addEventListener("click", () => openChat(chat.id));
    historyListEl.appendChild(li);
  });
}

/** Loads a previously saved chat into the chat area. */
function openChat(chatId) {
  const chats = loadAllChats();
  const chat = chats.find((c) => c.id === chatId);
  if (!chat) return;

  currentChatId = chat.id;
  currentMessages = [...chat.messages];

  chatArea.innerHTML = "";
  currentMessages.forEach((m) => {
    appendMessage(m.text, m.sender, new Date(m.time), { record: false });
  });

  renderHistoryList();
  closeSidebarDrawer();
}

/** Starts a fresh, empty chat (saving the previous one first, if any). */
function startNewChat() {
  if (isLoggedIn && currentChatId && currentMessages.length > 0) {
    saveCurrentChat();
  }

  currentChatId = null;
  currentMessages = [];
  chatArea.innerHTML = "";

  const greeting = isLoggedIn ? WELCOME_MESSAGE_LOGGED_IN : WELCOME_MESSAGE;
  appendMessage(greeting, "bot", new Date(), { record: false });

  renderHistoryList();
  closeSidebarDrawer();
  messageInput.focus();
}

/** Opens the sidebar drawer (mobile) — no-op on desktop where it's static. */
function openSidebarDrawer() {
  if (!sidebar) return;
  sidebar.classList.add("open");
  if (sidebarOverlay) sidebarOverlay.hidden = false;
}

function closeSidebarDrawer() {
  if (!sidebar) return;
  sidebar.classList.remove("open");
  if (sidebarOverlay) sidebarOverlay.hidden = true;
}

function toggleSidebarDrawer() {
  if (!sidebar) return;
  if (sidebar.classList.contains("open")) {
    closeSidebarDrawer();
  } else {
    openSidebarDrawer();
  }
}

/** Logs the user out: clears the login flag and returns to guest view. */
function handleLogout() {
  localStorage.removeItem(LS_LOGIN_FLAG);
  localStorage.removeItem(LS_USER_LABEL);
  window.location.reload();
}

/**
 * Applies the logged-in vs. guest UI state on load:
 *  - Guest: sidebar + its toggle stay hidden, "Log in" button shows.
 *  - Logged in: sidebar shows (persistent on desktop, drawer on mobile),
 *    the login button is hidden, and saved chat history is rendered.
 */
function initLoginState() {
  isLoggedIn = localStorage.getItem(LS_LOGIN_FLAG) === "1";

  if (isLoggedIn) {
    if (sidebar) sidebar.hidden = false;
    if (sidebarToggleBtn) sidebarToggleBtn.hidden = false;
    if (continueLink) continueLink.hidden = true;

    const label = localStorage.getItem(LS_USER_LABEL);
    if (sidebarProfileLbl && label) sidebarProfileLbl.textContent = label;

    renderHistoryList();
  } else {
    if (sidebar) sidebar.hidden = true;
    if (sidebarToggleBtn) sidebarToggleBtn.hidden = true;
    if (continueLink) continueLink.hidden = false;
  }
}

/* ===================================================================
   12. EVENT LISTENERS
   =================================================================== */

sendBtn.addEventListener("click", handleSend);

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

micBtn.addEventListener("click", toggleMic);
speakerToggle.addEventListener("click", toggleSpeaker);

if (newChatBtn) newChatBtn.addEventListener("click", startNewChat);
if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);
if (sidebarToggleBtn) sidebarToggleBtn.addEventListener("click", toggleSidebarDrawer);
if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebarDrawer);

document.addEventListener("visibilitychange", () => {
  if (document.hidden && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
});

window.addEventListener("beforeunload", () => {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  if (isLoggedIn) saveCurrentChat();
});

/* ===================================================================
   13. INITIALISATION  (runs on page load)
   =================================================================== */

(function init() {
  initVoices();
  recognition = initSpeechRecognition();

  if (recognition) {
    createMicLanguageToggle();
  }

  initLoginState();

  const greeting = isLoggedIn ? WELCOME_MESSAGE_LOGGED_IN : WELCOME_MESSAGE;
  appendMessage(greeting, "bot", new Date(), { record: false });

  setTimeout(() => {
    if (voiceEnabled) speakText(greeting);
  }, 600);

  messageInput.focus();
})();
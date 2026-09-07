/**
 * Panah — script.js
 * ~~~~~~~~~~~~~~~~~~
 * Frontend logic for the Panah WhatsApp-style AI chat interface.
 *
 * FEATURES
 *  - Sends questions to the Flask /ask API and displays replies
 *  - Voice input via browser SpeechRecognition (toggleable Urdu/English)
 *  - Voice output via browser SpeechSynthesis (auto-reads bot replies)
 *  - Two volume toggles that work together (see section 10):
 *      top-right speaker button  -> session-only mute, resets on reload
 *      Settings "Voice Output"   -> persistent, per-account preference
 *  - Typing indicator while waiting for the backend
 *  - Graceful fallback if speech APIs are unavailable
 *  - Guests: nothing is stored or logged client-side (privacy-by-default)
 *  - Logged-in users: left sidebar with "New chat" + chat history
 *
 * CHAT HISTORY — PERSISTED VIA BACKEND FOR LOGGED-IN USERS
 *  The sidebar's history list is loaded from the server (GET /chats)
 *  and individual chats are saved (PUT /chats/:id) using the Firebase
 *  ID token for authentication.  Guest users never trigger these calls
 *  — their chats remain ephemeral and vanish on reload.
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

/** UI language chosen by the user (default Urdu). */
const UI_LANG =
  typeof window !== "undefined" && window.PanahI18n
    ? window.PanahI18n.getLang()
    : "ur";

const UI_STRINGS =
  typeof window !== "undefined" && window.PanahI18n
    ? window.PanahI18n.I18N[UI_LANG].chat
    : {};

/** Language code for speech OUTPUT, based on the chosen UI language. */
const SPEECH_LANG =
  { ur: "ur-PK", en: "en-US", roman: "ur-PK" }[UI_LANG] || "ur-PK";

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
const WELCOME_MESSAGE = UI_STRINGS.welcome || "";

/** Welcome message variant for logged-in users (storage note differs). */
const WELCOME_MESSAGE_LOGGED_IN =
  UI_STRINGS.welcomeLoggedIn || WELCOME_MESSAGE;

/** localStorage keys — login state only. Chat history is NOT stored here. */
const LS_LOGIN_FLAG   = "panah_logged_in";
const LS_USER_LABEL   = "panah_user_label";
const LS_LANG_PREF    = "panah_lang_pref";

/**
 * localStorage key PREFIX for the persistent, per-account voice-output
 * preference (the Settings panel's "Voice Output" switch).  The full key
 * is "panah_volume_<phone>" — e.g. "panah_volume_+923001234567" — where
 * the phone number is read from LS_USER_LABEL (set by auth.js at login).
 * Scoping the key by phone keeps each account's preference separate on a
 * shared device.  The top-right speaker button never touches this key.
 */
const LS_VOLUME_PREFIX = "panah_volume_";

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
const suggestedChips   = document.getElementById("suggested-chips");

const sidebar           = document.getElementById("sidebar");
const sidebarToggleBtn  = document.getElementById("sidebar-toggle-btn");
const sidebarOverlay    = document.getElementById("sidebar-overlay");
const newChatBtn        = document.getElementById("new-chat-btn");
const historyListEl     = document.getElementById("chat-history-list");
const settingsBtn          = document.getElementById("settings-btn");
const settingsOverlay      = document.getElementById("settings-overlay");
const settingsCloseBtn     = document.getElementById("settings-close-btn");
const settingsLangSelect   = document.getElementById("settings-lang-select");
const settingsClearHistBtn = document.getElementById("settings-clear-history-btn");
const settingsVoiceToggle  = document.getElementById("settings-voice-toggle");
const settingsVoiceState   = document.getElementById("settings-voice-state");
const voiceOutputGroup     = document.getElementById("voice-output-group");
const logoutBtn            = document.getElementById("logout-btn");
const settingsDeleteAcctBtn = document.getElementById("settings-delete-account-btn");
const deleteAccountGroup    = document.getElementById("delete-account-group");
const deleteAcctOverlay     = document.getElementById("delete-account-overlay");
const deleteAcctCancelBtn   = document.getElementById("delete-account-cancel-btn");
const deleteAcctConfirmBtn  = document.getElementById("delete-account-confirm-btn");
const deleteAcctError       = document.getElementById("delete-account-error");

/* ===================================================================
   3. APPLICATION STATE
   =================================================================== */

/**
 * Whether bot voice output is enabled for the CURRENT page session.
 *
 * SESSION-ONLY STATE: the top-right speaker button flips this variable
 * directly and it is re-initialised on every page load from the saved
 * account preference (getSavedVolumePref).  It is NEVER written to
 * localStorage — that is what makes the top-right button "reset on
 * refresh".  Do not confuse it with the Settings panel's persistent
 * "Voice Output" preference (see section 10 for the full distinction).
 */
let sessionVolumeOn = true;

/** Whether a request to the backend is currently in flight. */
let isWaiting = false;

/** Reference to the current SpeechRecognition instance (null if idle). */
let recognition = null;

/** Whether the mic is currently actively listening. */
let isListening = false;

/** Reference to the currently-playing Azure TTS Audio element (null if idle). */
let currentAzureAudio = null;

/**
 * Which language the mic should listen in: "ur" or "en".
 */
let micLanguage = UI_LANG === "en" ? "en" : "ur";

/** Whether the current visitor is logged in (read once at init). */
let isLoggedIn = false;

/** Whether a POST /delete-account request is currently in flight. */
let isDeletingAccount = false;

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

// --- Firebase (for auth token in chat API calls) -----------------------
// Option A: load the Firebase SDKs in index.html so we can call
// firebase.auth().currentUser.getIdToken() directly with automatic
// token refresh, instead of caching an expiring token in localStorage.
if (typeof firebase !== "undefined" && !firebase.apps.length) {
  firebase.initializeApp({
    apiKey: "AIzaSyDoyX59MXO6I_pBpgoe1hfRrNHDsrLQM-8",
    authDomain: "panah-a1e41.firebaseapp.com",
    projectId: "panah-a1e41",
    storageBucket: "panah-a1e41.firebasestorage.app",
    messagingSenderId: "362734433731",
    appId: "1:362734433731:web:9746268a74eef65a073976",
  });
  firebase.auth().useEmulator("http://127.0.0.1:9099");
}

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
  // Renders **bold** markdown (which the LLM's answers use, e.g. for
  // "**mandatory bridal gift**") as real <strong> elements. Still 100%
  // XSS-safe: we never touch innerHTML — everything outside the ** markers,
  // and the bold text itself, is inserted via createTextNode/textContent,
  // never parsed as HTML.
  const str = String(text);
  const fragment = document.createDocumentFragment();
  const boldPattern = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match;

  while ((match = boldPattern.exec(str)) !== null) {
    if (match.index > lastIndex) {
      fragment.appendChild(document.createTextNode(str.slice(lastIndex, match.index)));
    }
    const strong = document.createElement("strong");
    strong.textContent = match[1];
    fragment.appendChild(strong);
    lastIndex = boldPattern.lastIndex;
  }

  if (lastIndex < str.length) {
    fragment.appendChild(document.createTextNode(str.slice(lastIndex)));
  }

  return fragment;
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

async function askBackend(question, history) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
      signal: controller.signal,
    });

    clearTimeout(timer);

    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    return { ok: response.ok, status: response.status, data };
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
  setSuggestedChipsVisible(false);

  isWaiting = true;
  sendBtn.disabled = true;
  showTypingIndicator();

  try {
    // `currentMessages` already includes the question we just appended above
    // (see appendMessage) — drop that last entry so it isn't sent twice:
    // once as its own "history" turn and again as the "question" field.
    const priorHistory = currentMessages.slice(0, -1);
    const { ok, status, data } = await askBackend(question, priorHistory);

    hideTypingIndicator();

    let answer;
    if (ok) {
      answer =
        data && typeof data.answer === "string"
          ? data.answer
          : "Jawab daryaft nahi ho saka. Dobara koshish karein.";
    } else if (status === 502 && data && typeof data.fallback_answer === "string") {
      // LLM call failed, but the backend returned the verified KB answer.
      answer = data.fallback_answer;
    } else {
      // 400 or another server error — surface a friendly retry message.
      throw new Error("Backend error");
    }

    appendMessage(answer, "bot");

    if (sessionVolumeOn) {
      speakText(answer, data?.response_language);
    }
  } catch (err) {
    hideTypingIndicator();

    const errorMsg =
      err && err.name === "AbortError"
        ? "Waqt khatam ho gaya. Barah-e-karam dobara koshish karein."
        : "Maazrat, is waqt connect nahi ho pa raha. Barah-e-karam dobara koshish karein.";
    appendMessage(errorMsg, "bot");

    if (sessionVolumeOn) {
      speakText(errorMsg);
    }
  } finally {
    isWaiting = false;
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

/* ===================================================================
   7b. SUGGESTED QUESTION CHIPS
   =================================================================== */

function renderSuggestedChips() {
  if (!suggestedChips) return;

  // Read chips from the current i18n language (not the frozen UI_STRINGS)
  // so they update live when the user changes the language preference.
  const currentLang =
    window.PanahI18n ? window.PanahI18n.getLang() : UI_LANG;
  const chips =
    (window.PanahI18n && window.PanahI18n.I18N[currentLang]
      ? window.PanahI18n.I18N[currentLang].chat.chips
      : null) || UI_STRINGS.chips || [];

  suggestedChips.innerHTML = "";
  chips.forEach(({ topic, text }) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.setAttribute("aria-label", `Suggested question: ${text}`);

    const topicBadge = document.createElement("span");
    topicBadge.className = "chip-topic";
    topicBadge.textContent = topic;

    const label = document.createElement("span");
    label.textContent = text;

    chip.appendChild(topicBadge);
    chip.appendChild(label);

    chip.addEventListener("click", () => {
      messageInput.value = text;
      handleSend();
    });

    suggestedChips.appendChild(chip);
  });
}

function setSuggestedChipsVisible(visible) {
  if (!suggestedChips) return;
  suggestedChips.hidden = !visible;
}

/* ===================================================================
   8. SPEECH SYNTHESIS  (Text-to-Speech — bot reads replies aloud)
   =================================================================== */

/**
 * Strips Markdown / formatting symbols from bot replies before they are
 * sent to any TTS engine (Azure or browser SpeechSynthesis), so the voice
 * doesn't read out "asterisk", "hash", stray colons from headings, list
 * markers, etc. Purely for speech — the on-screen text keeps its formatting.
 */
function stripMarkdownForSpeech(text) {
  if (typeof text !== "string") return "";
  return text
    // fenced code blocks
    .replace(/```[\s\S]*?```/g, " ")
    // inline code `like this`
    .replace(/`([^`]+)`/g, "$1")
    // images ![alt](url)
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    // links [text](url)
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    // bold/italic: ***x***, **x**, *x*, ___x___, __x__, _x_
    .replace(/(\*\*\*|___)(.*?)\1/g, "$2")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    // heading markers, e.g. "### Note:" -> "Note:"
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    // blockquote markers
    .replace(/^\s{0,3}>\s?/gm, "")
    // horizontal rules (---, ***, ___)
    .replace(/^\s*([-*_])(\s*\1){2,}\s*$/gm, " ")
    // bullet list markers
    .replace(/^\s*[-*+]\s+/gm, "")
    // numbered list markers, e.g. "1. "
    .replace(/^\s*\d+[.)]\s+/gm, "")
    // table pipes
    .replace(/\|/g, " ")
    // any leftover stray markdown symbols
    .replace(/[*_#`~]/g, "")
    // collapse whitespace
    .replace(/\s+/g, " ")
    .trim();
}

function speakText(text, replyLanguage) {
  // ── Mute gate (checked FIRST — no API call, no characters spent) ──
  if (!sessionVolumeOn) return;

  // Clean Markdown/formatting out of the text so TTS doesn't read symbols aloud.
  text = stripMarkdownForSpeech(text);
  if (!text) return;

  // Route TTS using the backend's detected question language (returned as
  // response_language in the /ask reply) when available.  This is far more
  // reliable than guessing from the response text, which often mixes Urdu
  // with English legal/financial terms.
  let useUrduTTS;
  if (replyLanguage) {
    useUrduTTS = (replyLanguage === "urdu_script" || replyLanguage === "roman_urdu");
  } else {
    // Fallback: text-based detection (welcome messages, client-side errors,
    // or older backend responses without response_language).
    const urduScriptRe = /[\u0600-\u06FF]/;
    if (urduScriptRe.test(text)) {
      useUrduTTS = true;
    } else {
      const englishHintWords = new Set([
        "the","is","are","what","how","why","when","where","can","do",
        "does","my","husband","wife","money","rights","should","will",
        "please","help","get","give","have","need","want",
      ]);
      const words = (text.toLowerCase().match(/[a-z']+/g) || []);
      const hits = words.filter((w) => englishHintWords.has(w)).length;
      useUrduTTS = !(hits >= 3);
    }
  }

  if (useUrduTTS) {
    // ── Urdu / Roman Urdu → Azure TTS ──
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/tts-urdu`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (!res.ok) throw new Error(`TTS API error: ${res.status}`);

        // Re-check mute in case the user toggled while the request was in flight
        if (!sessionVolumeOn) return;

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        currentAzureAudio = audio;
        audio.onended = () => { URL.revokeObjectURL(url); currentAzureAudio = null; };
        await audio.play();
      } catch (err) {
        console.warn("Azure TTS failed, falling back to browser TTS:", err);
        _speakBrowserFallback(text);
      }
    })();
  } else {
    // ── English → browser SpeechSynthesis (female voice) ──
    _speakBrowserEnglish(text);
  }
}

/**
 * Browser SpeechSynthesis with a female English voice.
 * Used as the primary path for English replies and as a fallback when
 * Azure TTS fails for Urdu replies.
 */
function _speakBrowserEnglish(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.95;
  utterance.pitch = 1.0;

  const voices = window.speechSynthesis.getVoices();
  const femaleVoice = voices.find((v) =>
    /female|woman/i.test(v.name)
  );
  if (femaleVoice) utterance.voice = femaleVoice;

  window.speechSynthesis.speak(utterance);
}

/**
 * Fallback browser TTS — tries a female English voice first, then any
 * available voice.  Called when Azure TTS fails so the user still hears
 * audio rather than silence.
 */
function _speakBrowserFallback(text) {
  if (!sessionVolumeOn) return;
  if (!("speechSynthesis" in window)) return;

  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.95;

  const voices = window.speechSynthesis.getVoices();
  const femaleVoice = voices.find((v) => /female|woman/i.test(v.name));
  const anyVoice = voices.find((v) => v.lang.startsWith("en"));
  if (femaleVoice) utterance.voice = femaleVoice;
  else if (anyVoice) utterance.voice = anyVoice;

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
   10. VOLUME CONTROLS  (two toggles — persistent vs session-only!)
   ===================================================================

   READ THIS BEFORE TOUCHING THE VOLUME CODE — the two toggles look
   similar but are deliberately different things:

   1. Top-right header speaker button  ->  SESSION-ONLY override
      Flips the in-memory `sessionVolumeOn` variable for the current
      page load ONLY.  It never reads or writes localStorage.  On every
      reload it is re-initialised from the saved account preference
      (below), which is why a mute done here is "forgotten" on refresh.
      Guests use this button too and always start unmuted (a guest has
      no account, hence no saved preference to read).

   2. Settings panel "Voice Output" switch  ->  PERSISTENT, per account
      Reads/writes localStorage key "panah_volume_<phone>" (phone taken
      from LS_USER_LABEL, set at login), so each account on a shared
      device remembers its own preference.  Default when nothing is
      stored yet: ON.  Changing it (a) saves the value immediately and
      (b) syncs the live session state + the top-right icon, so the
      effect is instant — no reload needed.

   After page load the two are intentionally DECOUPLED: the top-right
   button overrides the saved preference for the rest of the session
   only, and does NOT change what Settings saved.  Refreshing the page
   resets the session state back to whatever Settings currently says.
   =================================================================== */

/** Returns the logged-in user's phone (E.164, e.g. "+923001234567") or null. */
function getLoggedInPhone() {
  return localStorage.getItem(LS_USER_LABEL);
}

/**
 * Reads the PERSISTENT voice-output preference for the logged-in account
 * from "panah_volume_<phone>".  Returns true (voice on) when nothing has
 * been stored yet, for guests, or when the phone label is missing — i.e.
 * "on" is always the safe default.
 */
function getSavedVolumePref() {
  if (!isLoggedIn) return true;
  const phone = getLoggedInPhone();
  if (!phone) return true;
  // Only the exact string "false" means muted; anything else — including
  // no stored value at all — counts as ON.
  return localStorage.getItem(LS_VOLUME_PREFIX + phone) !== "false";
}

/** Saves the PERSISTENT voice-output preference for the logged-in account. */
function saveVolumePref(enabled) {
  if (!isLoggedIn) return;
  const phone = getLoggedInPhone();
  if (!phone) return;
  localStorage.setItem(LS_VOLUME_PREFIX + phone, enabled ? "true" : "false");
}

/**
 * Top-right speaker button: flips the SESSION-ONLY volume state and
 * updates the header icon.  Deliberately does NOT touch localStorage —
 * the saved Settings preference stays exactly as it was.
 */
function toggleSpeaker() {
  sessionVolumeOn = !sessionVolumeOn;
  updateSpeakerIcon();

  // Muting mid-sentence should also stop anything being spoken right now.
  if (!sessionVolumeOn) {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if (currentAzureAudio) { currentAzureAudio.pause(); currentAzureAudio = null; }
  }
}

/**
 * Syncs the top-right speaker button's icon + aria labels with the current
 * session volume state.  Called on load and whenever EITHER toggle changes
 * the effective session state, so the icon always reflects reality.
 */
function updateSpeakerIcon() {
  if (!speakerToggle) return;

  if (sessionVolumeOn) {
    speakerOnIcon.removeAttribute("hidden");
    speakerOffIcon.setAttribute("hidden", "");
    speakerToggle.setAttribute("aria-label", "Mute voice replies");
  } else {
    speakerOnIcon.setAttribute("hidden", "");
    speakerOffIcon.removeAttribute("hidden");
    speakerToggle.setAttribute("aria-label", "Unmute voice replies");
  }
}

/**
 * Settings panel "Voice Output" switch: the PERSISTENT preference.
 * (a) saves the value to localStorage for this account, and
 * (b) immediately applies it to the current session (state + top-right
 *     icon) so the change is heard — or stops being heard — without a
 *     reload.
 */
function handleVoicePrefToggle() {
  if (!settingsVoiceToggle) return;

  const enabled = settingsVoiceToggle.getAttribute("aria-checked") !== "true";
  settingsVoiceToggle.setAttribute("aria-checked", String(enabled));
  updateSettingsVoiceStateText(enabled);

  saveVolumePref(enabled);      // (a) persist across sessions…
  sessionVolumeOn = enabled;    // (b) …and apply right now.
  updateSpeakerIcon();

  if (!sessionVolumeOn) {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if (currentAzureAudio) { currentAzureAudio.pause(); currentAzureAudio = null; }
  }
}

/** Refreshes the "On"/"Off" caption next to the Settings switch. */
function updateSettingsVoiceStateText(enabled) {
  if (!settingsVoiceState) return;
  // Read the LIVE i18n language (UI_STRINGS is frozen at load time) so the
  // caption follows language changes made from this same panel.
  const lang = window.PanahI18n ? window.PanahI18n.getLang() : UI_LANG;
  const strings =
    window.PanahI18n && window.PanahI18n.I18N[lang]
      ? window.PanahI18n.I18N[lang].chat
      : UI_STRINGS;
  settingsVoiceState.textContent = enabled
    ? (strings.voiceOn || "On")
    : (strings.voiceOff || "Off");
}

/* ===================================================================
   11. SIDEBAR / LOGIN STATE / CHAT HISTORY
   =================================================================== */

/**
 * Fetches all chat summaries for the logged-in user from the server.
 * Returns [] for guests or if the API call fails.
 */
async function loadAllChats() {
  if (!isLoggedIn) return [];
  try {
    const token = await _getIdToken();
    if (!token) return [];
    const res = await fetch(`${API_BASE}/chats`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

/**
 * Persists a single chat to the server (upsert).
 * TODO(backend): could be extended with optimistic local caching, but
 * the server is the source of truth for now.
 */
async function saveAllChats_single(chat) {
  if (!isLoggedIn) return;
  try {
    const token = await _getIdToken();
    if (!token) return;
    await fetch(`${API_BASE}/chats/${chat.id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ title: chat.title, messages: chat.messages }),
    });
  } catch {
    /* silent — best-effort persistence */
  }
}

/**
 * Helper: get a fresh Firebase ID token for the current user.
 * Returns null if Firebase is unavailable or the user is not signed in.
 */
async function _getIdToken() {
  try {
    if (typeof firebase === "undefined") return null;
    const user = firebase.auth().currentUser;
    return user ? await user.getIdToken() : null;
  } catch {
    return null;
  }
}

/**
 * Helper: make an authenticated API call with Bearer token.
 */
async function _api(path, options = {}) {
  const token = await _getIdToken();
  if (!token) return null;
  options.headers = options.headers || {};
  options.headers.Authorization = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, options);
}

/** Derives a short title from the first user message in a chat. */
function deriveChatTitle(messages) {
  const firstUser = messages.find((m) => m.sender === "user");
  const base = firstUser ? firstUser.text : (UI_STRINGS.newChat || "Nayi guftagu");
  return base.length > 40 ? base.slice(0, 40) + "…" : base;
}

/** Upserts the current in-progress chat to the server. */
async function saveCurrentChat() {
  if (!currentChatId || currentMessages.length === 0) return;
  await saveAllChats_single({
    id: currentChatId,
    title: deriveChatTitle(currentMessages),
    messages: currentMessages,
    updatedAt: new Date().toISOString(),
  });
  renderHistoryList();
}

/** Renders the sidebar's chat history list from the server. */
async function renderHistoryList() {
  if (!historyListEl) return;

  const chats = (await loadAllChats()).sort(
    (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)
  );

  historyListEl.innerHTML = "";

  if (chats.length === 0) {
    const note = document.createElement("p");
    note.className = "sidebar-empty-note";
    note.textContent =
      UI_STRINGS.emptyHistory || "Abhi tak koi guftagu save nahi hui.";
    historyListEl.append(note);
    return;
  }

  chats.forEach((chat) => {
    const li = document.createElement("li");
    li.className = "history-item";
    li.dataset.chatId = chat.id;

    // Chat title (clickable to open the chat)
    const titleSpan = document.createElement("span");
    titleSpan.className = "history-item-title";
    titleSpan.textContent = chat.title;
    titleSpan.addEventListener("click", () => openChat(chat.id));

    // 3-dot menu for per-chat actions
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "history-item-actions";

    const menuBtn = document.createElement("button");
    menuBtn.type = "button";
    menuBtn.className = "history-item-menu-btn";
    menuBtn.setAttribute("aria-label", "Chat options");
    menuBtn.innerHTML = "&#8942;"; // ⋮
    menuBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleChatItemMenu(chat.id, actionsDiv);
    });

    actionsDiv.appendChild(menuBtn);
    li.appendChild(titleSpan);
    li.appendChild(actionsDiv);

    if (chat.id === currentChatId) li.classList.add("active");
    historyListEl.appendChild(li);
  });
}

/**
 * Toggles the per-chat dropdown menu (currently only "Delete").
 * Closes any other open menu first so only one is visible at a time.
 */
function toggleChatItemMenu(chatId, actionsDiv) {
  // Close any already-open dropdown
  const existing = document.querySelector(".history-item-dropdown");
  if (existing) existing.remove();

  const dropdown = document.createElement("div");
  dropdown.className = "history-item-dropdown";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.textContent = UI_STRINGS.deleteChat || "Delete";
  deleteBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.remove();
    deleteSingleChat(chatId);
  });

  dropdown.appendChild(deleteBtn);
  actionsDiv.appendChild(dropdown);

  // Auto-close when clicking anywhere outside the dropdown
  const closeHandler = (e) => {
    if (!dropdown.contains(e.target)) {
      dropdown.remove();
      document.removeEventListener("click", closeHandler);
    }
  };
  setTimeout(() => document.addEventListener("click", closeHandler), 0);
}

/**
 * Deletes a single chat from the server and updates the sidebar.
 * If the deleted chat is the currently open one, starts a fresh chat view.
 * TODO(backend): replace with a real DELETE /chats/:id API call.
 */
async function deleteSingleChat(chatId) {
  try {
    const token = await _getIdToken();
    if (token) {
      await fetch(`${API_BASE}/chats/${chatId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  } catch {
    /* best-effort — UI will still update */
  }

  if (chatId === currentChatId) {
    currentChatId = null;
    currentMessages = [];
    chatArea.innerHTML = "";
    const greeting = getWelcomeMessage(isLoggedIn);
    appendMessage(greeting, "bot", new Date(), { record: false });
    renderSuggestedChips();
    setSuggestedChipsVisible(true);
  }

  renderHistoryList();
}

/**
 * Returns the welcome message based on the user's language preference.
 * Reads panah_lang_pref from localStorage — "Urdu" shows the Urdu-script
 * greeting; "English" or unset shows the English greeting.
 * This does NOT affect the per-message language-detection logic.
 */
function getWelcomeMessage(loggedIn) {
  const pref = localStorage.getItem(LS_LANG_PREF);
  if (pref === "ur") {
    return loggedIn
      ? (UI_STRINGS.welcomeUrduLoggedIn || UI_STRINGS.welcomeUrdu || WELCOME_MESSAGE)
      : (UI_STRINGS.welcomeUrdu || WELCOME_MESSAGE);
  }
  // Default to English (also when pref is unset or "en")
  return loggedIn
    ? (UI_STRINGS.welcomeEnglishLoggedIn || UI_STRINGS.welcomeEnglish || WELCOME_MESSAGE_LOGGED_IN)
    : (UI_STRINGS.welcomeEnglish || WELCOME_MESSAGE);
}

/** Loads a previously saved chat into the chat area. */
async function openChat(chatId) {
  try {
    const token = await _getIdToken();
    if (!token) return;
    const res = await fetch(`${API_BASE}/chats/${chatId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const chat = await res.json();

    currentChatId = chat.id;
    currentMessages = chat.messages || [];

    chatArea.innerHTML = "";
    currentMessages.forEach((m) => {
      appendMessage(m.text, m.sender, new Date(m.time), { record: false });
    });

    setSuggestedChipsVisible(false);
    renderHistoryList();
    closeSidebarDrawer();
  } catch {
    /* failed to load — silently stay on current view */
  }
}

/** Starts a fresh, empty chat (saving the previous one first, if any). */
async function startNewChat() {
  if (isLoggedIn && currentChatId && currentMessages.length > 0) {
    await saveCurrentChat();
  }

  currentChatId = null;
  currentMessages = [];
  chatArea.innerHTML = "";

  const greeting = getWelcomeMessage(isLoggedIn);
  appendMessage(greeting, "bot", new Date(), { record: false });

  renderSuggestedChips();
  setSuggestedChipsVisible(true);
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

/** Logs the user out: clears the login flag and returns to the homepage. */
function handleLogout() {
  localStorage.removeItem(LS_LOGIN_FLAG);
  localStorage.removeItem(LS_USER_LABEL);
  window.location.href = "/";
}

/**
 * Applies the logged-in vs. guest UI state on load:
 *  - Guest: sidebar + its toggle stay hidden.
 *  - Logged in: sidebar shows (persistent on desktop, drawer on mobile)
 *    and saved chat history is rendered.
 */
function initLoginState() {
  isLoggedIn = localStorage.getItem(LS_LOGIN_FLAG) === "1";

  // Initialise the SESSION volume from the SAVED account preference.
  // Guests have no account, so they always start unmuted (true).
  // From here on the top-right speaker button and the Settings switch
  // are decoupled for the rest of the session (see section 10).
  sessionVolumeOn = getSavedVolumePref();
  updateSpeakerIcon();

  // The Settings "Voice Output" switch is only meaningful for logged-in
  // users (a guest has no account to remember the choice for) — hide its
  // whole group.  Guests keep the session-only top-right speaker button.
  if (voiceOutputGroup) voiceOutputGroup.hidden = !isLoggedIn;

  // Same for "Delete Account": a guest has no account to delete.
  if (deleteAccountGroup) deleteAccountGroup.hidden = !isLoggedIn;

  if (isLoggedIn) {
    if (sidebar) sidebar.hidden = false;
    if (sidebarToggleBtn) sidebarToggleBtn.hidden = false;

    const label = localStorage.getItem(LS_USER_LABEL);
    // Settings label is static ("Settings" via i18n) — no dynamic update needed.

    // Firebase restores auth state from IndexedDB asynchronously, so
    // currentUser is null immediately after initializeApp().  We must
    // wait for onAuthStateChanged to fire before calling getIdToken()
    // — otherwise every chat API call gets a null token and silently
    // bails out, and nothing is ever saved or loaded.
    if (typeof firebase !== "undefined") {
      firebase.auth().onAuthStateChanged((user) => {
        if (user) {
          renderHistoryList();
        }
      });
    }
  } else {
    if (sidebar) sidebar.hidden = true;
    if (sidebarToggleBtn) sidebarToggleBtn.hidden = true;
  }
}

/* ===================================================================
   11b. SETTINGS PANEL
   =================================================================== */

/** Opens the settings modal and syncs the language selector. */
function openSettingsPanel() {
  if (!settingsOverlay) return;
  // Sync the dropdown with the stored preference
  if (settingsLangSelect) {
    const pref = localStorage.getItem(LS_LANG_PREF);
    settingsLangSelect.value = pref || "en";
  }
  // Sync the "Voice Output" switch with the SAVED account preference —
  // NOT with the live session state.  If the user muted via the top-right
  // button earlier this session, Settings still shows the persistent
  // default; that is intentional, because the two toggles are decoupled
  // after page load (see section 10).
  if (settingsVoiceToggle) {
    const saved = getSavedVolumePref();
    settingsVoiceToggle.setAttribute("aria-checked", String(saved));
    updateSettingsVoiceStateText(saved);
  }
  settingsOverlay.hidden = false;
}

/** Closes the settings modal. */
function closeSettingsPanel() {
  if (settingsOverlay) settingsOverlay.hidden = true;
}

/**
 * Saves the language preference, syncs the i18n system so all static UI
 * labels update immediately, and re-renders the suggestion chips.
 * Does NOT change the per-message reply-language detection logic.
 */
function handleLangPrefChange() {
  if (!settingsLangSelect) return;
  const value = settingsLangSelect.value; // "ur" or "en"
  localStorage.setItem(LS_LANG_PREF, value);

  // Sync the i18n system so applyLanguage() uses the new language
  if (window.PanahI18n) {
    window.PanahI18n.setLang(value);
    window.PanahI18n.applyLanguage(value);
  }

  // Re-render chips with the new language's translations
  renderSuggestedChips();

  // Refresh the Settings "Voice Output" caption ("On"/"Off") so it follows
  // the language change too.
  if (settingsVoiceToggle) {
    updateSettingsVoiceStateText(
      settingsVoiceToggle.getAttribute("aria-checked") === "true"
    );
  }
}

/**
 * Clears ALL chat history after a confirm dialog.
 * This is a destructive action separate from per-chat delete.
 * TODO(backend): replace the per-chat DELETE loop with a bulk-clear
 * API endpoint once available.
 */
async function handleClearAllHistory() {
  const confirmMsg =
    UI_STRINGS.clearHistoryConfirm ||
    "Are you sure you want to clear all saved chats? This cannot be undone.";
  if (!confirm(confirmMsg)) return;

  try {
    const chats = await loadAllChats();
    for (const chat of chats) {
      const token = await _getIdToken();
      if (token) {
        await fetch(`${API_BASE}/chats/${chat.id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    }
  } catch {
    /* best-effort deletion */
  }

  currentChatId = null;
  currentMessages = [];
  chatArea.innerHTML = "";

  const greeting = getWelcomeMessage(isLoggedIn);
  appendMessage(greeting, "bot", new Date(), { record: false });
  renderSuggestedChips();
  setSuggestedChipsVisible(true);
  renderHistoryList();
  closeSettingsPanel();
}

/* ===================================================================
   11c. DELETE ACCOUNT  (destructive — two-click flow, Settings panel)
   ===================================================================

   Click 1: the Settings "Delete Account" button opens the confirmation
   dialog (openDeleteAccountDialog).  No further input is ever requested —
   the phone number/UID is taken from the CURRENT login session, the same
   Firebase ID token already used to load the user's chat history.

   Click 2: "Confirm Delete" immediately calls POST /delete-account
   (handleDeleteAccount).  Deletion is permanent — no soft-delete — and
   the backend removes both the Firebase Auth record and every stored
   chat.

   On success ONLY: local state is cleared, the Firebase client session
   is signed out, and the page reloads as the guest chat page.  On failure
   the user stays logged in and a localized error is shown in the dialog
   so they can retry or cancel — we never sign out before the server has
   actually confirmed the deletion.

   All dialog strings are data-i18n driven, so they follow the Settings
   language preference exactly like every other Settings label.

   NOTE (hackathon): auth runs on the Firebase Local Emulator Suite, but
   this flow only relies on standard ID-token auth + the backend's
   firebase_admin delete_user(), so it carries over cleanly to a real
   Firebase project without changes.
   =================================================================== */

/** Click 1 — opens the confirmation dialog on top of Settings. */
function openDeleteAccountDialog() {
  if (!deleteAcctOverlay) return;
  // Reset any error/disabled state left over from a previous attempt.
  if (deleteAcctError) deleteAcctError.hidden = true;
  if (deleteAcctConfirmBtn) deleteAcctConfirmBtn.disabled = false;
  deleteAcctOverlay.hidden = false;
}

/** Closes the confirmation dialog (returns to the Settings panel). */
function closeDeleteAccountDialog() {
  if (deleteAcctOverlay) deleteAcctOverlay.hidden = true;
}

/** Click 2 — confirms deletion. Immediate, permanent, no further input. */
async function handleDeleteAccount() {
  if (!isLoggedIn || isDeletingAccount) return;

  const token = await _getIdToken();
  if (!token) {
    // No usable session token — treat exactly like a failed deletion:
    // show the localized error and keep the user logged in.
    if (deleteAcctError) deleteAcctError.hidden = false;
    return;
  }

  // Guard against double-submission while the request is in flight.
  isDeletingAccount = true;
  if (deleteAcctConfirmBtn) deleteAcctConfirmBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/delete-account`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      throw new Error(`delete-account failed with status ${res.status}`);
    }

    // Deletion succeeded — only NOW clear local state and sign out.
    await _completeAccountDeletion();
  } catch (err) {
    console.error("Account deletion failed:", err);
    // Deletion did NOT succeed: nothing local is cleared and the user is
    // NOT logged out — surface a clear, localized error in the dialog so
    // they can retry or cancel.  (Server-side failures are logged by the
    // backend for manual cleanup.)
    if (deleteAcctError) deleteAcctError.hidden = false;
    if (deleteAcctConfirmBtn) deleteAcctConfirmBtn.disabled = false;
  } finally {
    isDeletingAccount = false;
  }
}

/**
 * Runs ONLY after the server has confirmed the account is deleted:
 * clears all local/session state (login flag, user label, per-account
 * preference keys, cached chat data, sidebar history), signs out the
 * Firebase client session, and reloads the chat page (index.html) in its
 * logged-out guest state.
 */
async function _completeAccountDeletion() {
  const phone = getLoggedInPhone();

  // 1. Clear login state + this account's per-user preference keys.
  localStorage.removeItem(LS_LOGIN_FLAG);
  localStorage.removeItem(LS_USER_LABEL);
  if (phone) localStorage.removeItem(LS_VOLUME_PREFIX + phone);

  // 2. Clear in-memory chat data and the sidebar history list.  Setting
  //    isLoggedIn = false FIRST also stops the beforeunload handler from
  //    trying to re-save the current (server-deleted) chat on navigation.
  isLoggedIn = false;
  currentChatId = null;
  currentMessages = [];
  if (historyListEl) historyListEl.innerHTML = "";

  // 3. End the client-side Firebase session.  Best-effort: signOut only
  //    clears local state, so a failure here never blocks the redirect.
  try {
    if (typeof firebase !== "undefined") await firebase.auth().signOut();
  } catch {
    /* ignore — the server-side record is already deleted */
  }

  // 4. Reload as the guest chat page.  /chat serves index.html; with the
  //    login flag cleared it re-initialises in the logged-out state.
  window.location.href = "/chat";
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

// --- Settings panel ---
if (settingsBtn) settingsBtn.addEventListener("click", openSettingsPanel);
if (settingsCloseBtn) settingsCloseBtn.addEventListener("click", closeSettingsPanel);
if (settingsOverlay) {
  settingsOverlay.addEventListener("click", (e) => {
    if (e.target === settingsOverlay) closeSettingsPanel();
  });
}
if (settingsLangSelect) settingsLangSelect.addEventListener("change", handleLangPrefChange);
if (settingsClearHistBtn) settingsClearHistBtn.addEventListener("click", handleClearAllHistory);
if (settingsVoiceToggle) settingsVoiceToggle.addEventListener("click", handleVoicePrefToggle);

// --- Delete account confirmation dialog ---
if (settingsDeleteAcctBtn) settingsDeleteAcctBtn.addEventListener("click", openDeleteAccountDialog);
if (deleteAcctCancelBtn) deleteAcctCancelBtn.addEventListener("click", () => {
  // Ignore once a deletion request is in flight (the dialog must stay put
  // so the pending state — and any eventual error — remains visible).
  if (!isDeletingAccount) closeDeleteAccountDialog();
});
if (deleteAcctConfirmBtn) deleteAcctConfirmBtn.addEventListener("click", handleDeleteAccount);
if (deleteAcctOverlay) {
  deleteAcctOverlay.addEventListener("click", (e) => {
    if (e.target === deleteAcctOverlay && !isDeletingAccount) closeDeleteAccountDialog();
  });
}

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

function applyChatLanguage() {
  if (window.PanahI18n) {
    window.PanahI18n.applyLanguage(UI_LANG);
  }
}

(function init() {
  initVoices();
  recognition = initSpeechRecognition();

  if (recognition) {
    createMicLanguageToggle();
  }

  initLoginState();
  applyChatLanguage();
  renderSuggestedChips();

  const greeting = getWelcomeMessage(isLoggedIn);
  appendMessage(greeting, "bot", new Date(), { record: false });

  setTimeout(() => {
    if (sessionVolumeOn) speakText(greeting);
  }, 600);

  messageInput.focus();
})();
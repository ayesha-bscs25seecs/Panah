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
 *  - Privacy-by-default: nothing is stored or logged client-side
 *
 * EXTENSION POINTS (for teammates)
 *  - Add a settings screen: wire up a gear icon in the header and
 *    create a modal overlay; persist prefs in sessionStorage only.
 *  - Add a language switch: swap SPEECH_LANG and update placeholder text.
 *
 * @version 1.1.0
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

/** Welcome message shown when the page first loads. */
const WELCOME_MESSAGE =
  "Assalamu Alaikum! Main Panah hoon — aapka mahfooz sahara. " +
  "Aap mujhse mehr, nafaqa, zakat, wirasat ya kisi bhi maali haq ke baare mein " +
  "poochh sakti hain. Apna sawaal likhein ya mic dabaa kar bolein. " +
  "Aapki baat bilkul mehfooz hai — kuch bhi save nahi hota.";

/* ===================================================================
   2. DOM REFERENCES
   =================================================================== */

const chatArea        = document.getElementById("chat-area");
const messageInput    = document.getElementById("message-input");
const sendBtn         = document.getElementById("send-btn");
const micBtn          = document.getElementById("mic-btn");
const speakerToggle   = document.getElementById("speaker-toggle");
const speakerOnIcon   = document.getElementById("speaker-on-icon");
const speakerOffIcon  = document.getElementById("speaker-off-icon");
const typingHeader    = document.getElementById("typing-indicator-header");
const subtitleText    = document.getElementById("subtitle-text");

/* ===================================================================
   3. APPLICATION STATE  (in-memory only — never persisted)
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
 * Defaults to "ur" since Urdu/Roman Urdu is the primary language for this
 * app's users — English is the exception, toggled on deliberately.
 */
let micLanguage = "ur";

/* ===================================================================
   4. UTILITY HELPERS
   =================================================================== */

/**
 * Returns a 12-hour format timestamp string (e.g. "3:45 PM").
 * @param {Date} [date=new Date()]
 * @returns {string}
 */
function formatTime(date = new Date()) {
  let hours = date.getHours();
  const mins = date.getMinutes().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  return `${hours}:${mins} ${ampm}`;
}

/**
 * Creates a safe text node — never uses innerHTML with user/backend text.
 * This prevents XSS even if the backend returns unexpected HTML.
 * @param {string} text
 * @returns {Text}
 */
function safeText(text) {
  return document.createTextNode(String(text));
}

/**
 * Sanitizes a string for safe inclusion in a DOM attribute or text node.
 * Strips leading/trailing whitespace and caps length.
 * @param {string} str
 * @param {number} [maxLen=MAX_QUESTION_LENGTH]
 * @returns {string}
 */
function sanitizeInput(str, maxLen = MAX_QUESTION_LENGTH) {
  if (typeof str !== "string") return "";
  return str.trim().slice(0, maxLen);
}

/* ===================================================================
   5. MESSAGE RENDERING
   =================================================================== */

/**
 * Appends a chat bubble to the chat area.
 * Uses textContent (not innerHTML) for safety.
 *
 * @param {string}  text     - The message body.
 * @param {"user"|"bot"} sender - Who sent the message.
 * @param {Date}    [time]   - Optional timestamp.
 */
function appendMessage(text, sender, time = new Date()) {
  // Outer row (controls alignment)
  const row = document.createElement("div");
  row.className = `msg-row ${sender}`;

  // Bubble
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  // Message text — safe text node, never innerHTML
  bubble.appendChild(safeText(text));

  // Timestamp
  const ts = document.createElement("span");
  ts.className = "msg-time";
  ts.textContent = formatTime(time);

  bubble.appendChild(ts);
  row.appendChild(bubble);
  chatArea.appendChild(row);

  // Auto-scroll to bottom
  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

/**
 * Shows the typing indicator bubble (three bouncing dots) in the chat area
 * and the header subtitle area.
 */
function showTypingIndicator() {
  // Header indicator
  typingHeader.hidden = false;
  subtitleText.style.display = "none";

  // Chat-area bubble
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

/**
 * Removes the typing indicator from both the chat area and the header.
 */
function hideTypingIndicator() {
  typingHeader.hidden = true;
  subtitleText.style.display = "";

  const typingRow = document.getElementById("typing-bubble-row");
  if (typingRow) typingRow.remove();
}

/* ===================================================================
   6. BACKEND API CALLS
   =================================================================== */

/**
 * Sends a question to the Flask /ask endpoint and returns the response JSON.
 * Includes a timeout via AbortController.
 *
 * @param {string} question - The user's question (already sanitized).
 * @returns {Promise<{answer: string, matched_topic: string|null, matched_question: string|null, sources: string[]}>}
 */
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

/**
 * Pings the /health endpoint.  Returns true if the backend is reachable.
 * (Currently unused — reserved for a future "connection status" indicator.)
 */
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

/**
 * Handles the full "user sends a message" flow:
 *  1. Validate & sanitize input
 *  2. Render user bubble
 *  3. Show typing indicator
 *  4. Call backend
 *  5. Render bot reply (or error message)
 *  6. Optionally speak the reply aloud
 */
async function handleSend() {
  // Prevent double-sends while waiting
  if (isWaiting) return;

  const rawInput = messageInput.value;
  const question = sanitizeInput(rawInput);

  // Ignore empty questions
  if (!question) return;

  // Clear input immediately
  messageInput.value = "";

  // Render user bubble
  appendMessage(question, "user");

  // Lock UI and show typing
  isWaiting = true;
  sendBtn.disabled = true;
  showTypingIndicator();

  try {
    const data = await askBackend(question);

    hideTypingIndicator();

    // Validate the answer field exists and is a string
    const answer =
      data && typeof data.answer === "string"
        ? data.answer
        : "Jawab daryaft nahi ho saka. Dobara koshish karein.";

    appendMessage(answer, "bot");

    // Speak the reply if voice is enabled
    if (voiceEnabled) {
      speakText(answer);
    }
  } catch (err) {
    hideTypingIndicator();

    // Friendly error message in Urdu — never expose raw error details
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

/**
 * Speaks the given text aloud using the browser's SpeechSynthesis API.
 * Selects an Urdu voice if available; falls back to the default voice.
 *
 * @param {string} text - The text to speak.
 */
function speakText(text) {
  if (!("speechSynthesis" in window)) return;

  // Cancel any ongoing speech to avoid overlap
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = SPEECH_LANG;
  utterance.rate = 0.95;   // Slightly slower for clarity
  utterance.pitch = 1.0;

  // Try to pick an Urdu voice
  const voices = window.speechSynthesis.getVoices();
  const urduVoice = voices.find(
    (v) => v.lang === SPEECH_LANG || v.lang.startsWith("ur")
  );
  if (urduVoice) utterance.voice = urduVoice;

  window.speechSynthesis.speak(utterance);
}

/**
 * Pre-loads voices (some browsers load them asynchronously).
 */
function initVoices() {
  if ("speechSynthesis" in window) {
    // Chrome loads voices async; this event fires once they're ready.
    window.speechSynthesis.onvoiceschanged = () => {
      /* voices are now available for speakText() */
    };
  }
}

/* ===================================================================
   9. SPEECH RECOGNITION  (Speech-to-Text — user speaks their question)
   =================================================================== */

/**
 * Initialises the SpeechRecognition API.
 * Returns the recognition instance, or null if unsupported.
 *
 * NOTE: rec.lang is no longer hardcoded here — it's set fresh each time
 * listening starts (see toggleMic), based on the current micLanguage state,
 * since the API only supports one language per session and can't switch
 * mid-recording.
 */
function initSpeechRecognition() {
  const SR =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;

  if (!SR) {
    // Browser doesn't support speech recognition — hide the mic button
    micBtn.style.display = "none";
    micBtn.setAttribute("aria-hidden", "true");
    return null;
  }

  const rec = new SR();
  rec.interimResults = false;   // We only want the final transcript
  rec.maxAlternatives = 1;
  rec.continuous = false;

  rec.addEventListener("result", (event) => {
    const transcript = event.results[0][0].transcript;
    // Put the recognised text into the input field
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

/**
 * Toggles the microphone on/off.
 * Sets recognition.lang from the current micLanguage state right before
 * starting, since the language can't be changed while listening is active.
 */
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
      // Already started or other error — reset state
      isListening = false;
      micBtn.classList.remove("recording");
    }
  }
}

/* ===================================================================
   9b. MIC LANGUAGE TOGGLE  (switch mic between Urdu and English)
   =================================================================== */

/**
 * Creates the small UR/EN toggle button next to the mic and inserts it
 * into the DOM. Built and styled inline in JS (rather than relying on
 * index.html/style.css markup that may not exist yet) so this feature is
 * self-contained and doesn't require edits to the other two files.
 *
 * @returns {HTMLButtonElement|null} the created button, or null if the
 *   mic button itself isn't present (e.g. speech recognition unsupported).
 */
function createMicLanguageToggle() {
  if (!micBtn || !micBtn.parentNode) return null;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "mic-lang-toggle";
  btn.setAttribute("aria-label", "Switch microphone language");
  btn.title = "Switch microphone language (Urdu / English)";

  // Minimal inline styling so it doesn't depend on style.css rules that
  // may not exist for it. Kept small and unobtrusive, matching the
  // existing WhatsApp-style green accent already used elsewhere.
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

/**
 * Updates the toggle button's label/title to reflect the current
 * micLanguage state.
 * @param {HTMLButtonElement} btn
 */
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
    // Stop any ongoing speech immediately
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }
}

/* ===================================================================
   11. EVENT LISTENERS
   =================================================================== */

// --- Send button click ---
sendBtn.addEventListener("click", handleSend);

// --- Enter key in input field ---
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
});

// --- Mic button click ---
micBtn.addEventListener("click", toggleMic);

// --- Speaker toggle ---
speakerToggle.addEventListener("click", toggleSpeaker);

// --- Stop speech synthesis when the page is hidden (background tab) ---
document.addEventListener("visibilitychange", () => {
  if (document.hidden && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
});

// --- Clean up speech on page unload ---
window.addEventListener("beforeunload", () => {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
});

/* ===================================================================
   12. INITIALISATION  (runs on page load)
   =================================================================== */

(function init() {
  // Initialise speech systems
  initVoices();
  recognition = initSpeechRecognition();

  // Only add the language toggle if speech recognition is actually
  // supported (initSpeechRecognition hides micBtn entirely otherwise).
  if (recognition) {
    createMicLanguageToggle();
  }

  // Show the welcome greeting from the bot
  appendMessage(WELCOME_MESSAGE, "bot");

  // Speak the greeting if voice is on
  // Small delay so voices have time to load in some browsers
  setTimeout(() => {
    if (voiceEnabled) speakText(WELCOME_MESSAGE);
  }, 600);

  // Focus the input
  messageInput.focus();
})();
"""
app.py — Panah Flask backend.

Endpoints:
  POST /ask                  — KB-grounded chatbot reply (unchanged, see below)
  POST /verify-session        — verifies a Firebase phone-auth ID token and
                                 creates/finds the user record by phone number
  GET  /health                — status check
  GET  /suggested-questions   — example questions for the frontend to show as
                                 clickable chips above the chat input

/ask Body:  {
    "question": "mera shohar mujhe kharcha nahi deta",
    "history": [                       # OPTIONAL, see NOTE below
        {"sender": "user", "text": "..."},
        {"sender": "bot",  "text": "..."}
    ]
}
Reply: {
    "answer": "...",              # final Urdu answer from the LLM
    "matched_topic": "nafaqa",    # for debugging/demo purposes
    "matched_question": "...",
    "sources": [...],
    "escalation_tier": 1
}

NOTE on "history": the frontend already keeps the current chat's messages
in memory (script.js's `currentMessages`) but previously never sent them
here, so every reply was generated with zero awareness of earlier turns —
which made "progressive disclosure" (explain broadly first, go deeper only
on follow-up) and "don't repeat yourself" impossible to actually satisfy.
This field is optional and backward-compatible: if omitted, /ask behaves
exactly as before (treats the message as the start of a new conversation).

Flow:
1. Retrieve the best-matching KB entry for the user's question (retrieval.py).
2. If no confident match: return a graceful "I don't know this one yet" reply
   WITHOUT calling the LLM with no grounding (avoids hallucinated answers).
3. If matched: build a system prompt with the tone rules + the retrieved
   chunk as ground truth + recent conversation turns, call Qwen
   (qwen-plus-character via DashScope's OpenAI-compatible endpoint), and
   return its response.

Run locally:
    export DASHSCOPE_API_KEY="your-key-here"
    export GOOGLE_APPLICATION_CREDENTIALS="./firebase-service-account.json"
    pip install flask openai flask-cors firebase-admin --break-system-packages
    python app.py
"""

from dotenv import load_dotenv
load_dotenv()

import os
import re
import json
import random
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, Response
from flask_cors import CORS
from openai import OpenAI

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from retrieval import kb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("panah")

app = Flask(__name__)

# Allow the frontend (served from a different port, e.g. localhost:8000 via
# `python -m http.server`) to call this API. Without this, browsers block
# the request with a CORS error even though the backend itself is running fine.
# For the hackathon demo this is wide open (allow all origins); if you deploy
# publicly later, tighten this to your actual frontend's domain.
CORS(app)


# --- Page routes (serve templates) ------------------------------------------
# Flask now serves ALL frontend pages from templates/ and static/.
# The four landing pages use template inheritance (base.html).
# index.html (chat) and auth.html (login/OTP) are standalone templates.

@app.route("/")
def home():
    return render_template("homepage.html", active_page="home")


@app.route("/about")
def about():
    return render_template("about.html", active_page="about")


@app.route("/review", methods=["GET", "POST"])
def review():
    if request.method == "POST":
        """Store an anonymous review from any visitor.
        No phone or identity is stored — privacy by design."""
        data = request.get_json(silent=True) or {}
        review_text = (data.get("review_text") or "").strip()
        if not review_text:
            return jsonify({"error": "Missing 'review_text' in request body."}), 400

        conn = _get_db()
        conn.execute(
            "INSERT INTO reviews (review_text) VALUES (?)",
            (review_text,),
        )
        conn.commit()
        conn.close()
        logger.info("Anonymous review submitted")
        return jsonify({"success": True})

    # Fetch all reviews for display
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, review_text, created_at FROM reviews ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    reviews = [dict(r) for r in rows]
    return render_template("review.html", active_page="review", reviews=reviews)


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", active_page="privacy")


@app.route("/chat")
def chat_page():
    return render_template("index.html")


@app.route("/auth")
def auth_page():
    return render_template("auth.html")


# Legacy redirects — entry.js and auth.js use hardcoded relative paths like
# "auth.html" and "homepage.html". These redirects ensure those navigations
# still resolve correctly after the file move.
@app.route("/homepage.html")
def redirect_homepage():
    return redirect(url_for("home"), code=301)


@app.route("/index.html")
def redirect_index():
    return redirect(url_for("chat_page"), code=301)


@app.route("/auth.html")
def redirect_auth():
    return redirect(url_for("auth_page"), code=301)


@app.route("/about.html")
def redirect_about():
    return redirect(url_for("about"), code=301)


@app.route("/review.html")
def redirect_review():
    return redirect(url_for("review"), code=301)


@app.route("/contact.html")
def redirect_contact_legacy():
    return redirect(url_for("review"), code=301)


@app.route("/privacy.html")
def redirect_privacy():
    return redirect(url_for("privacy"), code=301)

# --- Qwen / DashScope client setup -----------------------------------------
# Uses the OpenAI-compatible SDK pointed at Alibaba Cloud's international
# endpoint, per the project's confirmed working setup (qwen-plus-character
# has free quota on the team account; plain qwen-plus/qwen-flash did not).
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = "https://ws-ad6fbmy7z0chcf98.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-plus-character"

client = None
if DASHSCOPE_API_KEY:
    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
else:
    logger.warning(
        "DASHSCOPE_API_KEY not set — /ask will return retrieval results "
        "without an LLM-generated response. Set the env var to enable full replies."
    )

# --- Firebase Admin setup ----------------------------------------------------
# Needs a service account key JSON downloaded from Firebase Console >
# Project settings > Service accounts > Generate new private key.
# Point GOOGLE_APPLICATION_CREDENTIALS at that file's path, or hardcode the
# path below. NEVER commit that file to git.
FIREBASE_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS", "./firebase-service-account.json"
)
USING_EMULATOR = bool(os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"))

firebase_app = None
if USING_EMULATOR:
    # No real service account needed — the emulator doesn't check real
    # signatures. projectId just has to match what firebase init used.
    firebase_app = firebase_admin.initialize_app(options={"projectId": "panah-a1e41"})
    logger.info(
        "Firebase Admin running in EMULATOR mode (FIREBASE_AUTH_EMULATOR_HOST=%s).",
        os.environ["FIREBASE_AUTH_EMULATOR_HOST"],
    )
elif os.path.exists(FIREBASE_CREDENTIALS_PATH):
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_app = firebase_admin.initialize_app(cred)
else:
    logger.warning(
        "Firebase service account file not found at %s, and "
        "FIREBASE_AUTH_EMULATOR_HOST is not set — /verify-session "
        "will reject all requests until one of these is configured.",
        FIREBASE_CREDENTIALS_PATH,
    )
    
# --- User store (SQLite) ------------------------------------------------
# Persists across restarts, unlike the old in-memory dict. Single file,
# no separate DB server needed — fine for a hackathon and easy to grow later.
import sqlite3

DB_PATH = "panah_users.db"


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            firebase_uid TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            phone TEXT NOT NULL,
            title TEXT,
            messages TEXT DEFAULT '[]',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (phone) REFERENCES users(phone)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_user(phone: str):
    conn = _get_db()
    row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_user(phone: str, firebase_uid: str):
    conn = _get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (phone, firebase_uid) VALUES (?, ?)",
        (phone, firebase_uid),
    )
    conn.commit()
    conn.close()


init_db()


# --- Chat store (SQLite) ------------------------------------------------
# Persists chat history per logged-in user (keyed by phone number).
# Every chat endpoint requires a valid Firebase Bearer token, and the
# per-chat endpoints (GET/PUT/DELETE with an id) enforce an explicit
# ownership check so one user cannot read or overwrite another's chat.


def _get_caller_auth():
    """Verify the Bearer token from the request's Authorization header and
    return the caller's (phone_number, uid) pair, or (None, None) if the
    token is missing/invalid.

    Used by endpoints that need more than just the phone number —
    e.g. /delete-account needs the uid to remove the Firebase Auth
    record.  Like _get_caller_phone(), the identity ALWAYS comes from the
    verified session token, never from a value typed by the user.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None
    id_token = auth_header[7:]
    if not id_token or firebase_app is None:
        return None, None
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded.get("phone_number"), decoded.get("uid")
    except Exception:
        logger.warning("Bearer token verification failed in authenticated endpoint")
        return None, None


def _get_caller_phone():
    """Verify the Bearer token from the request's Authorization header
    and return the caller's phone number, or None if missing/invalid."""
    phone, _uid = _get_caller_auth()
    return phone


def _chat_row(row):
    """Convert a sqlite3.Row from the chats table into a JSON-safe dict."""
    if not row:
        return None
    d = dict(row)
    try:
        d["messages"] = json.loads(d.get("messages", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["messages"] = []
    return d


def get_chat_owner(chat_id: str) -> str | None:
    """Return the phone number that owns this chat, or None if not found."""
    conn = _get_db()
    row = conn.execute(
        "SELECT phone FROM chats WHERE id = ?", (chat_id,)
    ).fetchone()
    conn.close()
    return row["phone"] if row else None


def list_chats(phone: str) -> list:
    """Return summaries (no message bodies) of all chats for a user,
    newest-first."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, title, updated_at FROM chats "
        "WHERE phone = ? ORDER BY updated_at DESC",
        (phone,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chat(chat_id: str) -> dict | None:
    """Return the full chat record (including messages) or None."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, phone, title, messages, updated_at "
        "FROM chats WHERE id = ?",
        (chat_id,),
    ).fetchone()
    conn.close()
    return _chat_row(row)


def save_chat(chat_id: str, phone: str, title: str,
              messages: list | None = None):
    """Insert or replace a chat.  Caller MUST verify ownership before
    calling this — the function itself does NOT check."""
    conn = _get_db()
    conn.execute(
        "INSERT OR REPLACE INTO chats (id, phone, title, messages, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            chat_id,
            phone,
            title,
            json.dumps(messages if messages is not None else []),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def delete_chat(chat_id: str):
    """Delete a chat by id.  Caller MUST verify ownership first."""
    conn = _get_db()
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()


def delete_account_data(phone: str) -> None:
    """Delete ALL backend-stored data for a phone number — every chat row
    AND the user row — in a single transaction, so a mid-flight failure can
    never leave one without the other.  Used only by POST /delete-account
    (the per-chat endpoints use delete_chat instead)."""
    conn = _get_db()
    try:
        conn.execute("DELETE FROM chats WHERE phone = ?", (phone,))
        conn.execute("DELETE FROM users WHERE phone = ?", (phone,))
        conn.commit()
    finally:
        conn.close()


@app.route("/chats", methods=["GET"])
def chats_list():
    """List all chat summaries for the authenticated user."""
    phone = _get_caller_phone()
    if not phone:
        return jsonify({"error": "Authentication required."}), 401
    return jsonify(list_chats(phone))


@app.route("/chats/<chat_id>", methods=["GET"])
def chats_get(chat_id):
    """Return the full chat (including messages) if the caller owns it."""
    phone = _get_caller_phone()
    if not phone:
        return jsonify({"error": "Authentication required."}), 401
    owner = get_chat_owner(chat_id)
    if owner is None or owner != phone:
        return jsonify({"error": "Chat not found."}), 404
    chat = get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found."}), 404
    return jsonify(chat)


@app.route("/chats/<chat_id>", methods=["PUT"])
def chats_put(chat_id):
    """Create or update a chat, with ownership enforcement.

    - New chat (no existing row): allowed.
    - Existing row owned by caller: allowed (update).
    - Existing row owned by someone else: 403 Forbidden.
    """
    phone = _get_caller_phone()
    if not phone:
        return jsonify({"error": "Authentication required."}), 401
    owner = get_chat_owner(chat_id)
    if owner is not None and owner != phone:
        return jsonify({"error": "Forbidden."}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip() or "Chat"
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        messages = []
    save_chat(chat_id, phone, title, messages)
    return jsonify({"success": True})


@app.route("/chats/<chat_id>", methods=["DELETE"])
def chats_delete(chat_id):
    """Delete a chat if the caller owns it."""
    phone = _get_caller_phone()
    if not phone:
        return jsonify({"error": "Authentication required."}), 401
    owner = get_chat_owner(chat_id)
    if owner is None or owner != phone:
        return jsonify({"error": "Chat not found."}), 404
    delete_chat(chat_id)
    return jsonify({"success": True})


@app.route("/delete-account", methods=["POST"])
def delete_account():
    """Permanently delete the authenticated caller's account — a HARD
    delete, no soft-delete/flags anywhere.

    The phone number AND Firebase UID are read from the caller's verified
    ID token (the current authenticated session — the same one the frontend
    already uses to load chat history), NEVER from the request body.  So a
    user can only ever delete their own account, and never has to re-enter
    their phone number or an OTP to do it.

    Order of operations (chosen so the worst partial failure is recoverable):
      1. All backend-stored data: every chat row + the user row, in ONE
         SQLite transaction (delete_account_data).
      2. The Firebase Auth record, by UID from the token.

    If step 2 fails after step 1 succeeded, the error is logged server-side
    with the phone + UID for manual cleanup and a 500 is returned, so the
    frontend does NOT sign the user out — they stay logged in and can
    simply retry (a retried call no-ops on the already-cleared local data).

    NOTE (hackathon): auth currently runs on the Firebase Local Emulator
    Suite (FIREBASE_AUTH_EMULATOR_HOST).  firebase_admin's delete_user()
    talks to the emulator in dev and to the real Firebase Auth service in
    production with NO code changes, so this endpoint carries over cleanly
    once the project is pointed at a real Firebase project.
    """
    if firebase_app is None:
        return jsonify({
            "error": "Firebase Admin not configured on the server. "
                     "Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON.",
        }), 500

    phone, uid = _get_caller_auth()
    if not phone or not uid:
        return jsonify({"error": "Authentication required."}), 401

    # 1. Delete every stored chat and the user row atomically.
    try:
        delete_account_data(phone)
    except Exception:
        logger.exception(
            "Account deletion FAILED before any data was removed "
            "(phone=%s, uid=%s) — nothing deleted; investigate server-side.",
            phone, uid,
        )
        return jsonify({"error": "Failed to delete account data."}), 500

    # 2. Delete the Firebase Auth record using the UID from the session token.
    try:
        firebase_auth.delete_user(uid)
    except firebase_auth.UserNotFoundError:
        # Already deleted (e.g. the user retried after a partial failure) —
        # treat as success so the endpoint stays idempotent.
        logger.info(
            "Firebase Auth record for uid=%s (phone=%s) was already "
            "deleted — treating as success.",
            uid, phone,
        )
    except Exception:
        # Local data is gone but the auth record could not be removed. Log
        # everything an operator needs for manual cleanup; the 500 makes the
        # frontend keep the user logged in (see handleDeleteAccount there).
        logger.exception(
            "Account deletion PARTIAL FAILURE: backend data was deleted for "
            "phone=%s but the Firebase Auth record (uid=%s) could NOT be "
            "deleted — MANUAL CLEANUP REQUIRED.",
            phone, uid,
        )
        return jsonify({"error": "Failed to delete the Firebase Auth user."}), 500

    logger.info("Account permanently deleted (phone=%s, uid=%s)", phone, uid)
    return jsonify({"success": True, "phone": phone})


@app.route("/verify-session", methods=["POST"])
def verify_session():
    if firebase_app is None:
        return jsonify({
            "error": "Firebase Admin not configured on the server. "
                     "Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON.",
        }), 500

    data = request.get_json(silent=True) or {}
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"error": "Missing 'idToken' in request body."}), 400

    try:
        decoded = firebase_auth.verify_id_token(id_token)
    except Exception as e:
        logger.warning("ID token verification failed: %s", e)
        return jsonify({"error": "Invalid or expired token."}), 401

    phone = decoded.get("phone_number")
    if not phone:
        return jsonify({"error": "Token did not contain a phone number."}), 400

    user = get_user(phone)
    if user is None:
        save_user(phone, decoded.get("uid"))
        logger.info("Created new user record for %s", phone)
    else:
        logger.info("Existing user logged in: %s", phone)

    return jsonify({"success": True, "phone": phone})


# --- System prompt (tone + rules) -------------------------------------------
SYSTEM_PROMPT = """You are Panah — a kind, calm, knowledgeable Muslim friend who helps \
Pakistani women understand their financial, legal, and Islamic rights. You sound \
like a sensible friend who happens to know this subject well — not ChatGPT, not a \
customer-service rep, not a lawyer giving a formal consultation, not a preacher \
giving a sermon, and not a robotic information system. Approachable without being \
overly warm. Conversational without being casual to the point of disrespect. \
Cautious about facts without sounding rigid.

You may naturally use a genuine, situationally-fitting Islamic phrase sometimes \
(e.g. "Allah aap ke liye asani kare") when it truly fits the moment — but never \
force one into every reply, and never open or close with religious/emotional \
phrases as a habit. Most replies won't need one at all.

LANGUAGE RULE (very important):
Always reply in the SAME language and script the user used to ask their question:
- If the user wrote in English, reply in English.
- If the user wrote in Urdu script (e.g. "میرا شوہر مجھے خرچہ نہیں دیتا"), reply in Urdu script.
- If the user wrote in Roman Urdu (Urdu words spelled with English/Latin letters,
  e.g. "mera shohar mujhe kharcha nahi deta"), reply in Roman Urdu the same way.
- If a question mixes languages, mirror whichever style dominates the question.
- Never default to one language regardless of what the user wrote — detect it fresh
  for every question, since the same conversation may switch between languages.

FACTS COME FIRST:
- Base your answer ONLY on the "Verified information" below. Never add facts, \
laws, or rulings that aren't in it, and never guess or fill gaps from general \
knowledge just to keep the conversation going.
- The verified information may be in English or Urdu — regardless of which, \
translate/adapt its meaning into whatever language the LANGUAGE RULE says to \
answer in, without changing its meaning.
- If the available verified information doesn't actually support what's being \
asked, say so plainly and briefly instead of stretching it to sound complete \
(e.g. "Is specific baat ke baare mein mere paas abhi verified maloomat nahi \
hai, is liye main andaza nahi lagana chahti.").

DON'T SOUND LIKE AN AI ASSISTANT:
- Never use generic filler like "that's a really important/thoughtful question," \
"I'm glad you asked," "I completely understand how you feel," "I hope that \
clears things up," "please don't hesitate to ask," "I'm always here to support \
you," or compliments about the user's faith, character, intelligence, or \
emotions unless genuinely relevant. Warmth should come from natural conversation, \
not reassurance-padding bolted onto the front or back of every answer.
- Don't open every answer the same way, and don't close every answer the same \
way either (e.g. not always "koi aur sawaal ho to poochein" / "anything else?"). \
Vary it, or skip a closing line entirely when the answer already feels complete.
- Sometimes the most natural reply is just the fact, plainly stated — e.g. "Yes, \
a daughter has a prescribed share of inheritance in Islam." Don't force warmth \
into every single sentence.

ANSWER WHAT WAS ACTUALLY ASKED:
- If the question is broad or general (e.g. "tell me about zakat," "what are my \
rights"), give ONLY the general picture: what it is, the basic condition \
(Nisab) and rate if that's core to understanding it, in a few short sentences. \
Do not jump into narrow scenarios (a specific business type, a specific \
person's situation, exactly how to calculate it, gender-specific notes) just \
because the retrieved information happens to detail them — only go there if \
the user's question actually pointed at it, or she asks a follow-up that does.
- You may be given more than one piece of "Verified information" below when \
several relate to the same topic. For a broad question, these extra pieces \
are there so you don't accidentally pick the narrowest one as your only \
answer — they are NOT all meant to be mentioned. Use only what's needed for \
the general picture, and offer the rest as a follow-up option instead of \
including it upfront (e.g. "Kya aap yeh jaanna chahti hain ke business ka \
zakat kaise calculate hota hai?" rather than just explaining it anyway).
- Answer in the first sentence or two whenever possible — don't spend a \
paragraph on background before getting to the actual answer.
- Never assume the user owns a business, is married, is divorced, has children, \
has lost a parent, has a specific amount of money, or follows a particular \
school of thought, unless she said so or the verified information establishes \
it. If the real answer depends on details about her specific situation, ask \
for them naturally, as part of the conversation — not as a generic "is there \
anything else" tack-on.
- NEVER introduce a completely different major subject (such as switching from Inheritance/Mirath to Zakat or Waqf) unless the user explicitly requested it in their current prompt.
- If the user provides a short continuation (e.g., "yes", "both", "tell me more"), stay strictly within the current topic thread (e.g., mother's share / gifts) and do not switch topics.

USE CONVERSATION HISTORY, DON'T REPEAT YOURSELF:
- You may be shown recent turns from this same conversation before the current \
question. Use them: if you already explained a concept (e.g. what Zakat is), \
and the user now asks a follow-up on the same topic (e.g. "what is Nisab?"), \
answer the follow-up directly — do not re-explain what you already covered.
- If the user already told you something relevant about her situation earlier \
in the conversation, don't ask for it again.
- Practice progressive disclosure: broad question -> short general answer, \
optionally with one useful next-step question. Only go into calculations, \
edge cases, or a specific scenario once the conversation has actually moved \
there, either because the user asked or because you offered and she said yes.

USE SOURCES INTELLIGENTLY, DON'T BLEND OR DUMP THEM:
- The verified information may include separate "Legal basis" and "Islamic \
basis" sections. Use only whichever is actually relevant to the question — do \
not automatically combine both into every answer. A question about Pakistani \
legal process should lean on the legal basis; a question about a religious \
ruling should lean on the Islamic basis; only cover both, clearly separated, \
when the question genuinely touches both — in that case you can label them \
plainly, e.g. "Islam mein:" and "Pakistan ke qanoon ke mutabiq:" (or the \
English equivalents), so it's clear which claim comes from which source.
- The user should be able to tell whether something is Islamic guidance, \
Pakistani law, or both — don't blur the two together into one blended claim.
- When you do show both sources, each one gets its OWN chunk, with a blank \
line before it, not folded into a stream of sentences. Labeling a source \
("Islam mein:" / "Pakistan ke qanoon mein:") and then continuing straight \
into the next sentence still reads as one dense paragraph — treat each \
labeled source as its own short chunk, same as any other formatting rule \
about breaking up an answer.
- Citing both sources answers "where does this right come from," not "what \
do I do if it's violated." For a broad/definitional question, stop once \
you've explained what the right is and grounded it religiously and legally — \
don't also walk through the enforcement process (which council to approach, \
what steps to take if a husband refuses, etc.) unless she actually asked \
about non-payment/enforcement. Offer that as the natural next question \
instead of answering it preemptively, exactly as you would with any other \
narrow scenario detail under "answer what was actually asked."
- Reference a source naturally in a sentence when it helps (e.g. "the Qur'an \
gives daughters a share of inheritance in Surah An-Nisa 4:7") and then explain \
what it means in plain language. Never quote long verses, paste citation URLs, \
or list out multiple references — that turns an answer into a research paper.

======================================================================
CONTEXT RELEVANCE & BOUNDARY RULES (STRICT COMPLIANCE REQUIRED)
======================================================================

1. RELEVANCE CHECK:
   - Carefully evaluate if the provided Knowledge Base context DIRECTLY answers the user's specific question.
   - Do NOT force, bend, or stretch unrelated context (e.g., Nafaqa/Kharcha) to answer a question about an unmentioned topic (e.g., Talaq or Khula).

2. DO NOT BLEND UNRELATED TOPICS:
   - If the user asks about Topic A (e.g., "Talaq" or "Khula"), but the provided context is exclusively about Topic B (e.g., "Nafaqa"), DO NOT frame Topic B as the core definition or reason for Topic A.
   - Never invent legal connections between distinct concepts unless explicitly stated in the context.

3. SAFE FALLBACK DIRECTIVE:
   - If the provided context lacks factual details about the user's explicit question, respond ONLY with the standard fallback message stating that you do not have verified information on that topic yet.
   - Do NOT guess, extrapolate, or attempt to answer using general knowledge.

LENGTH, FORMATTING, AND TONE:
- This is read on a phone screen, in a chat bubble — never send back one \
long paragraph. This applies EVEN to short answers, not just long ones.
- Concrete formatting rules, every time:
  1. Use short sentences. If a sentence has more than one main idea joined by \
"and"/"lekin"/"aur", split it into two sentences.
  2. Break your answer into short chunks of 1-2 sentences each, with a blank \
line between chunks — never more than 2 sentences before a break. A 3-sentence \
answer can still be one chunk; anything longer needs at least one break.
  3. **Bold the actual answer or key fact** — the number, the yes/no, the \
amount, the deadline, the core term being explained — so someone scanning the \
message can find the main point without reading every word. Every answer that \
contains a concrete fact, ruling, or amount should have at least one bolded \
phrase; don't bold entire sentences, just the key words within them.
  4. Default to prose, not bullets. Panah talks like a knowledgeable friend, \
not a legal FAQ page — most lists of related items (e.g. nafaqa's components, \
a few required documents) read better folded into one sentence with the key \
words bolded than broken into a bulleted list, even when there are 3 items. \
Only reach for an actual bullet list when there are 4+ items that don't share \
a natural sentence, OR when order genuinely matters (a sequence of steps to \
follow, "do X, then Y"). When in doubt, write it as a sentence.
- Scale length to the question: a simple question gets 2-4 sentences across \
1-2 short chunks; a general question gets a couple of short chunks, occasionally \
with one bullet list if it genuinely earns one (see rule 4); a genuinely complex \
legal/religious question can go longer, but still built from short chunks, not \
dense paragraphs. Never pad a simple answer just to sound thorough.
- Use everyday words over formal ones where a simpler word works just as well \
(e.g. "right to receive money" over "financial entitlement," "minimum amount" \
over "minimum threshold"). Islamic/legal terms like Nisab, Mirath, Mehr, Nafaqa, \
Khula are fine to use, just explain them simply if needed.
- Avoid both extremes: don't sound like a legal document ("a female heir may be \
entitled to a prescribed share subject to the presence of other surviving \
heirs"), and don't overcorrect into something so casual it loses precision. \
Aim for how an informed person would actually say it out loud.
- A good follow-up question, when one is genuinely useful, should route the \
conversation toward something specific and easy to answer (e.g. "Kya aap yeh \
jaan'na chahti hain ke Mehr kab dena hota hai, ya agar shohar Mehr na de to kya \
kiya ja sakta hai?") — not a generic "anything else?" And don't force one onto \
every reply; if the question was specific and you've fully answered it, it's \
fine to simply stop.

Example of correctly formatted short answer (Roman Urdu — match whichever \
language the LANGUAGE RULE requires instead):

"Haan, beti ko wirasat mein hissa milta hai.

Agar sirf aik beti ho aur koi beta na ho, to uska hissa **aadha (1/2)** hota \
hai baaqi ke hisse doosre heirs mein taqseem hote hain."

Example of correctly formatted longer answer:

"Zakat Islam ke bunyadi faraiz mein se aik hai.

Agar kisi Muslim ka maal **Nisab** (85 gram sone ya 595 gram chandi ke \
barabar value) tak pohanch jaaye aur wo aik saal tak uske paas rahe, to us par \
Zakat deni hoti hai — jo ke us maal ka **2.5% saalana** banta hai.

Kya aap yeh jaan'na chahti hain ke apni Zakat kaise calculate karni hai?"

Example of a short list folded into prose instead of bulleted (this is the \
default — do this even though there are 3-4 items):

"Nafaqa aap ka haq hai apne shohar se — is mein **rehaish, khana, kapda, aur \
zaroori kharche** shaamil hain.

Yeh depend karta hai aap ke halaat aur maahol par ke bilkul kitna reasonable \
maana jaata hai."

(Not: a bulleted list of "Shelter / Food / Clothing / Other expenses" — the \
same four items, folded into one bolded clause, reads like a friend talking \
instead of a policy handout.)

Example of correctly chunked dual-source answer, ENGLISH version (broad \
question, both sources shown, enforcement held back as a follow-up instead \
of dumped -- notice EVERY sentence, including the source labels, stays in \
the same language; never mix an English sentence with a Roman Urdu label \
or vice versa):

"Nafaqa is a wife's right to **financial maintenance** from her husband — \
shelter, food, clothing, and essential living expenses.

In Islam: Surah An-Nisa 4:34 places this responsibility on the husband as \
part of his role of care, not control.

Under Pakistani law: the **MFLO 1961** makes this a legally enforceable \
right.

Would you like to know what can be done if a husband refuses to pay \
nafaqa?"

Example of the SAME answer, ROMAN URDU version (use this shape instead \
whenever the LANGUAGE RULE says to reply in Roman Urdu -- again, every \
sentence and label stays in Roman Urdu, none of it reverts to English):

"Nafaqa aap ka haq hai apne shohar se — is mein **rehaish, khana, kapda, \
aur zaroori kharche** shaamil hain.

Islam mein: Surah An-Nisa 4:34 mein yeh zimmedari shohar par daali gayi \
hai, uski dekhbhaal ke kirdar ke hissay ke tor par, na ke control ke.

Pakistan ke qanoon mein: **MFLO 1961** ke tehat yeh aik qanooni tor par \
lagoo hone wala haq hai.

Kya aap jaanna chahti hain ke agar shohar nafaqa na de to kya kiya ja sakta \
hai?"

(Not: all of this run together as one six-sentence paragraph with the \
Union Council/Arbitration Council process folded in before she's even asked \
about non-payment.)

WHEN THE TOPIC IS OUTSIDE WHAT YOU COVER:

- If a question falls outside financial, legal, and Islamic-rights topics \
(marriage/dower, maintenance, inheritance, zakat, divorce, property, scams, \
etc.), don't respond like a generic error message. Briefly and warmly explain \
that this falls outside what you help with, and mention a couple of the \
topics you do cover, so she knows what to ask instead. Never say "I am just \
an AI" or apologize excessively.

ESCALATION / DISCLAIMERS:
- Do not add "consult a lawyer/scholar" to every response. Only suggest it when \
the question needs a case-specific legal determination the verified information \
can't settle, when scholarly interpretations genuinely differ, or when you \
truly don't have enough reliable information. When you do suggest it, prefer a \
trusted local resource (a knowledgeable teacher, NGO worker, community figure, \
or the Alkhidmat Foundation's women's welfare network) over formal institutions, \
unless the verified information specifically points elsewhere."""


def build_final_user_message(
    user_question: str,
    matched_entry: dict,
    language_label: str,
    supporting_entries: list | None = None,
) -> str:
    # Defense-in-depth cap: even after knowledge_base.json was repaired to
    # remove oversized "answer" blobs (see fix_knowledge_base.py), this
    # keeps a single bad/oversized entry from ever again dominating the
    # prompt and derailing the LLM's answer if bad data is merged back in
    # later. Truncating on a sentence boundary is a last resort, not a
    # normal code path.
    MAX_CONTEXT_CHARS = 2200

    def _cap(text: str) -> str:
        if len(text) <= MAX_CONTEXT_CHARS:
            return text
        logger.warning(
            "KB entry exceeds MAX_CONTEXT_CHARS (%d > %d) -- truncating. "
            "This should not happen after fix_knowledge_base.py; check for "
            "newly merged oversized entries.",
            len(text), MAX_CONTEXT_CHARS,
        )
        cut = text[:MAX_CONTEXT_CHARS]
        last_break = max(cut.rfind(". "), cut.rfind("\n"))
        return cut[: last_break + 1] if last_break > MAX_CONTEXT_CHARS * 0.6 else cut

    context_lines = [f"Verified information (primary match):\n{_cap(matched_entry['answer'])}"]

    # For broad/general questions, retrieval may have scored one narrow entry
    # highest just by keyword coincidence. Supporting entries from the same
    # topic give the model enough material to answer generally first instead
    # of jumping straight into whichever narrow scenario happened to match.
    for extra in (supporting_entries or []):
        context_lines.append(
            f"\nVerified information (related, same topic — "
            f"\"{extra['question']}\"):\n{_cap(extra['answer'])}"
        )

    if matched_entry.get("legal_basis"):
        context_lines.append(f"\nLegal basis: {matched_entry['legal_basis']}")
    if matched_entry.get("islamic_basis"):
        context_lines.append(f"\nIslamic basis: {matched_entry['islamic_basis']}")
    if matched_entry.get("scope_note"):
        context_lines.append(f"\nImportant scope note: {matched_entry['scope_note']}")

    context_block = "\n".join(context_lines)
    return (
        f"User's question (original, exact wording): \"{user_question}\"\n\n"
        f"{context_block}\n\n"
        f"You MUST answer in: {language_label}. This has already been determined "
        f"for you — do not re-guess the language yourself, just write your answer "
        f"in it, using only the verified information above."
    )


# How many prior turns (user+bot messages combined) from this conversation to
# forward to the LLM as real chat history. Kept small on purpose: this is for
# recency/context (avoiding repetition, following up naturally), not a full
# transcript replay, so token cost and latency stay low.
MAX_HISTORY_MESSAGES = 8


def build_history_messages(history: list | None) -> list:
    """Turn the frontend's [{sender, text}, ...] shape into OpenAI-style
    chat messages ([{role, content}, ...]), keeping only the most recent
    MAX_HISTORY_MESSAGES entries. Anything malformed is skipped rather than
    raising, since this is a best-effort context aid, not required input."""
    if not history:
        return []

    role_map = {"user": "user", "bot": "assistant", "assistant": "assistant"}
    messages = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        sender = item.get("sender") or item.get("role")
        text = item.get("text") or item.get("content")
        role = role_map.get(sender)
        if role and isinstance(text, str) and text.strip():
            messages.append({"role": role, "content": text.strip()})
    return messages


def _is_likely_followup_reply(text: str) -> bool:
    """True for very short replies (roughly 3 words or fewer) that are too
    short to carry real searchable content on their own — regardless of
    script/language, since this checks word count, not specific words like
    "yes"/"haan". Deliberately narrow: this is what limits the fallback below
    to short acknowledgements only, not to genuine (if terse) new questions."""
    return len(text.split()) <= 3


# Pure closing/gratitude remarks ("shukriya", "thanks", "ok", "theek hai")
# are NOT follow-up questions and should never be pushed through KB
# retrieval. They previously fell into the same "short reply -> pull in
# last user turn and search for a match" path as genuine continuations
# like "haan"/"yes", which could and did match some unrelated KB entry by
# keyword coincidence with whatever was discussed earlier (e.g. "shukriya"
# after a domestic-violence question matched an unrelated maintenance
# entry, just because both conversations mentioned "shohar"). A closing
# remark needs a short warm acknowledgement, never a forced legal answer.
_CLOSING_PHRASES = {
    "shukriya", "shukria", "thanks", "thank you", "thankyou", "thanku",
    "ok", "okay", "k", "acha", "achha", "theek hai", "thik hai", "theek",
    "thik", "samajh gayi", "samajh gai", "samjh gayi", "bye", "khuda hafiz",
    "allah hafiz", "jazakallah", "jazak allah", "shukar hai",
}


def _is_closing_remark(text: str) -> bool:
    """True only when the ENTIRE message is one of the known closing/
    gratitude phrases (ignoring case/punctuation) — not just when one of
    these words appears inside a longer question, so "shukriya, lekin
    mujhe yeh bhi batayein ke..." still goes through normal retrieval."""
    normalized = re.sub(r"[^\w\s]", "", text).strip().lower()
    return normalized in _CLOSING_PHRASES


CLOSING_MESSAGES = {
    "urdu_script": [
        "خوش آمدید! اگر کوئی اور سوال ہو تو بلا جھجک پوچھیں۔",
        "کوئی بات نہیں۔ جب بھی کوئی اور سوال ہو، یہیں پوچھ لیجیے گا۔",
    ],
    "english": [
        "You're welcome! Feel free to come back anytime you have another question.",
        "Anytime. I'm here whenever you need to ask something else.",
    ],
    "roman_urdu": [
        "Koi baat nahi! Jab bhi koi aur sawaal ho, bila jhijak pooch lein.",
        "Khushi hui madad kar ke. Aur kabhi kuch poochna ho to yahin aa jayein.",
    ],
}


# --- Simple language detection for the NO-MATCH fallback message only ------
# (When an LLM call happens, the LLM itself handles language-matching per the
# LANGUAGE RULE in SYSTEM_PROMPT — this heuristic is only needed for the
# static fallback text below, which never goes through the LLM.)
_URDU_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
_ENGLISH_HINT_WORDS = {
    "the", "is", "are", "what", "how", "why", "when", "where", "can",
    "do", "does", "my", "husband", "wife", "money", "rights", "should",
    "will", "please", "help", "get", "give", "have", "need", "want",
}

# NOTE: these are shown only when retrieval finds literally nothing (no LLM
# call happens at all). They now also briefly restate Panah's scope, so a
# genuinely out-of-scope question ("what is life?") doesn't read like a raw
# system error — see SYSTEM_PROMPT's "WHEN THE TOPIC IS OUTSIDE WHAT YOU
# COVER" section for the LLM-driven version of this, which handles the more
# common case where retrieval finds a weak/partial match instead of nothing.
NO_MATCH_MESSAGES = {
    "urdu_script": [
        "معاف کیجیے گا، اس مخصوص سوال کی پکی معلومات ابھی میرے پاس نہیں ہیں — "
        "اور میں اندازے سے کوئی بات نہیں بتانا چاہتی، خاص طور پر ایسے موضوع پر۔\n\n"
        "میں زیادہ تر Mehr، Nafaqa، Zakat اور Mirath جیسے مالی، قانونی اور دینی "
        "حقوق میں مدد کر سکتی ہوں — ان میں سے کسی موضوع پر بھی پوچھ کر دیکھیں۔",
        "یہ اچھا سوال ہے، لیکن سچ بتاؤں تو اس کی تصدیق شدہ معلومات ابھی میرے "
        "پاس نہیں ہیں، اس لیے اندازہ نہیں لگانا چاہتی۔\n\n"
        "اگر یہ Mehr، Nafaqa، Zakat یا Mirath سے متعلق ہے تو تھوڑا مختلف انداز "
        "میں پوچھ کر دیکھیں، ورنہ الخدمت فاؤنڈیشن جیسا کوئی بھروسے مند ذریعہ "
        "بہتر رہنمائی دے سکتا ہے۔",
    ],
    "english": [
        "I wish I had a solid answer for this one, but I don't have reliable "
        "information on it yet — and I'd rather not guess with something that "
        "matters this much.\n\n"
        "I'm mostly able to help with financial, legal, and Islamic rights — "
        "things like Mehr, Nafaqa, Zakat, and Mirath — so feel free to ask "
        "about any of those.",
        "That's outside what I actually have verified information on right "
        "now, so I don't want to make something up and risk misleading you.\n\n"
        "If it's related to Mehr, Nafaqa, Zakat, or Mirath, try rephrasing it "
        "a bit — otherwise a trusted resource like the Alkhidmat Foundation "
        "would be a better fit.",
    ],
    "roman_urdu": [
        "Is sawaal ka pakka jawab abhi mere paas nahi hai, aur main andaza "
        "laga kar ghalat baat nahi batana chahti.\n\n"
        "Main zyada tar Mehr, Nafaqa, Zakat aur Mirath jaisay maali, qanooni "
        "aur deeni huqooq mein madad kar sakti hoon — in mein se kisi topic "
        "par pooch kar dekhein.",
        "Achha sawaal hai, lekin yeh cheez abhi meri verified maloomat mein "
        "nahi hai, is liye guess nahi karna chahti.\n\n"
        "Agar yeh Mehr, Nafaqa, Zakat ya Mirath se related hai to thora alag "
        "andaz mein dobara pooch sakti hain, warna Alkhidmat Foundation jaisa "
        "koi bharosemand sahara behtar rahnumai de sakta hai.",
    ],
}



def detect_language(text: str) -> str:
    """Rough heuristic to pick which fallback message to show when no KB
    entry matches, or when no LLM is available to classify. Returns
    'urdu_script', 'english', or 'roman_urdu'."""
    lower = text.lower()

    # An explicit request for a specific reply language always wins, even if
    # it's phrased in a different language than the rest of the message.
    if re.search(r"\bin urdu\b|\burdu mein\b|\burdu script\b", lower):
        return "urdu_script"
    if re.search(r"\bin roman urdu\b|\broman urdu mein\b", lower):
        return "roman_urdu"
    if re.search(r"\bin english\b|\breply in english\b", lower):
        return "english"

    if _URDU_SCRIPT_RE.search(text):
        return "urdu_script"

    words = set(re.findall(r"[a-zA-Z']+", lower))
    if not words:
        return "roman_urdu"  # default assumption for this user base

    english_hits = len(words & _ENGLISH_HINT_WORDS)
    # If a meaningful chunk of the words are common English function words,
    # treat it as English. Otherwise assume Roman Urdu (Urdu words spelled
    # in Latin letters won't match this English hint list).
    if english_hits >= 2 or (len(words) <= 4 and english_hits >= 1):
        return "english"
    return "roman_urdu"


LANGUAGE_LABELS = {
    "english": "English",
    "roman_urdu": "Roman Urdu (Urdu words spelled out in Latin/English letters, casual spoken style)",
    "urdu_script": "Urdu script (اردو رسم الخط)",
}


def classify_and_translate(user_question: str) -> dict:
    """Use the LLM once, upfront, to reliably (a) detect which of the three
    languages the user actually wrote in, and (b) produce a plain-English
    version of the question for keyword retrieval — since the knowledge base's
    keywords are English/Roman Urdu only, a raw Urdu-script question would
    otherwise never match anything.

    STEP 1 — pick "language":
    - Match the exact script and language of the user's latest input.
    - If the user writes in Roman Urdu (e.g. "Donon mein farq kia hai"), language MUST be "roman_urdu". Do NOT default to Urdu script or English.
    - If the user writes in Urdu script (e.g. "دونوں میں فرق کیا ہے"), language MUST be "urdu_script".
    - If the user writes in English, language MUST be "english".

    Returns {"language": "english"|"roman_urdu"|"urdu_script", "english_query": str}.
    Falls back to the local heuristic + the original text if the LLM call
    fails or returns something unparseable, so retrieval still runs either way.
    """
    fallback = {"language": detect_language(user_question), "english_query": user_question}

    if client is None:
        return fallback

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You detect the reply language and translate for a search system. "
                        "Respond with ONLY a JSON object, no other text, no markdown "
                        "fences, in exactly this shape: "
                        '{"language": "english" | "roman_urdu" | "urdu_script", '
                        '"english_query": "<the core question content only, in plain English>"}. '
                        "\n\n"
                        "STEP 1 — pick \"language\" (which language the REPLY should be in):\n"
                        "- First check whether the user explicitly asked for a specific reply "
                        "language anywhere in their message — phrases like 'in Urdu', 'in "
                        "English', 'in Roman Urdu', 'urdu mein', 'urdu mein batao', 'jawab "
                        "urdu mein dein', 'reply in english', 'roman urdu mein'. If such a "
                        "request is present, \"language\" MUST be that requested language, "
                        "REGARDLESS of what script/language the rest of the message itself is "
                        "written in. An explicit request always overrides the message's own "
                        "language.\n"
                        "- If there is no explicit request, then \"language\" is simply "
                        "whichever language/script the message itself is written in: "
                        "\"roman_urdu\" for Urdu words spelled out in Latin/English letters "
                        "(e.g. \"mera shohar kharcha nahi deta\"), even with inconsistent or "
                        "phonetic spelling; \"urdu_script\" for actual Urdu/Arabic script; "
                        "otherwise \"english\".\n\n"
                        "STEP 2 — build \"english_query\":\n"
                        "This is ONLY the actual question/topic content, translated into "
                        "plain English, for a search index. Strip out any meta-instruction "
                        "about which language to reply in (e.g. \"tell me about zakat in "
                        "urdu\" -> english_query should just be \"tell me about zakat\", not "
                        "mention Urdu at all)."
                    ),
                },
                {"role": "user", "content": user_question},
            ],
        )
        raw = response.choices[0].message.content.strip()
        # Strip accidental markdown code fences if the model adds them anyway.
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(raw)
        language = parsed.get("language")
        english_query = parsed.get("english_query")
        if language not in LANGUAGE_LABELS or not english_query:
            raise ValueError("Unexpected shape from language classifier")
        return {"language": language, "english_query": english_query}
    except Exception:
        logger.exception("Language classification/translation step failed, using fallback")
        return fallback


def _last_user_turn(history: list | None, require_substantial: bool = False) -> str | None:
    """Find the most recent turn that actually came from the user (not the
    bot), walking backwards through history. Used anywhere we want "what
    did she just say/ask" for follow-up context -- as opposed to blindly
    taking history[-1], which is just as likely to be the BOT's previous
    (often long, multi-topic) reply, and stuffing that into a search query
    does more harm than good.

    If `require_substantial` is True, bare acknowledgements ("haan", "ok",
    "yes") are skipped so we land on the last *real* question instead.
    """
    if not history:
        return None
    for item in reversed(history):
        if not isinstance(item, dict):
            continue
        sender = item.get("sender") or item.get("role")
        text = item.get("text") or item.get("content")
        if sender != "user" or not isinstance(text, str) or not text.strip():
            continue
        if require_substantial and _is_likely_followup_reply(text):
            continue
        return text.strip()
    return None


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    user_question = (data.get("question") or "").strip()
    history = data.get("history")  # optional, see module docstring

    if not user_question:
        return jsonify({"error": "Missing 'question' in request body."}), 400

    classification = classify_and_translate(user_question)
    detected_lang = classification["language"]
    search_query = classification["english_query"]

    # A pure closing/gratitude remark should never go through KB retrieval
    # at all — there's nothing to look up, and forcing a match risks
    # surfacing an unrelated legal fact in response to "thanks" (see
    # _is_closing_remark docstring for the concrete bug this fixes).
    if _is_closing_remark(user_question):
        return jsonify({
            "answer": random.choice(CLOSING_MESSAGES[detected_lang]),
            "matched_topic": None,
            "matched_question": None,
            "sources": [],
            "response_language": classification["language"],
        })

    # 1. Primary retrieval attempt -- always try the question on its own
    #    first. A short question is often a perfectly self-contained new
    #    question ("zakat ka nisab kya hai?"), not a follow-up, and it
    #    should get the chance to match cleanly before any prior-turn text
    #    gets mixed into its search embedding.
    matched_entry = kb.get_best_match(search_query)

    # 2. Direct fallback using raw (untranslated) question.
    if not matched_entry and search_query != user_question:
        matched_entry = kb.get_best_match(user_question)

    # 3. Only if the question alone didn't confidently match anything, and
    #    it's short enough to plausibly be an elliptical follow-up (either
    #    a bare "yes"/"haan" reply, or a short trailing question like "aur
    #    zakat al-fitr?"), retry once with the last thing the USER herself
    #    said folded in for context. Using the *user's* last turn (not
    #    whatever the last history item happens to be, which is usually
    #    the bot's own previous answer) keeps this grounded in what she's
    #    actually asked about, and only ever fires as a fallback, so a
    #    genuinely new short question that already matched in step 1/2 is
    #    never contaminated by unrelated earlier context.
    if not matched_entry and history and _is_likely_followup_reply(user_question):
        last_user_question = _last_user_turn(history, require_substantial=True)
        if last_user_question:
            contextual_query = f"{last_user_question} {user_question}"
            classification = classify_and_translate(contextual_query)
            search_query = classification["english_query"]
            matched_entry = kb.get_best_match(search_query)
    elif not matched_entry and history and len(user_question.split()) <= 5:
        last_user_question = _last_user_turn(history, require_substantial=True)
        if last_user_question:
            contextual_query = f"{last_user_question} {search_query}"
            matched_entry = kb.get_best_match(contextual_query)
            if matched_entry:
                search_query = contextual_query

    if not matched_entry:
        logger.info("No confident match for question: %r", user_question)
        return jsonify({
            "answer": random.choice(NO_MATCH_MESSAGES[detected_lang]),
            "matched_topic": None,
            "matched_question": None,
            "sources": [],
            "response_language": classification["language"],
        })

    logger.info(
        "Matched question %r (lang=%s, search_query=%r) -> [%s / %s]",
        user_question, detected_lang, search_query,
        matched_entry["topic_id"], matched_entry["id"],
    )

    # Gather up to 2 supporting entries from the same topic -- but only
    # ones that are genuinely close in meaning to the matched entry, not
    # just anything sharing the same topic_id. Several topics in the KB
    # (e.g. the merged Khula/Nafaqa reference) bundle a hundred+ fairly
    # distinct FAQ entries under one topic_id, so "same topic_id" alone is
    # a very weak relevance signal -- it was pulling loosely-related or
    # outright unrelated filler into the LLM's context, which shows up as
    # unrelated/extra detail bleeding into answers.
    SUPPORTING_SCORE_MARGIN = 0.12  # max drop-off from the top match's score
    same_topic_candidates = kb.search(search_query, top_k=8)
    supporting_entries = [
        e for e in same_topic_candidates
        if e["topic_id"] == matched_entry["topic_id"]
        and e["id"] != matched_entry["id"]
        and e["similarity_score"] >= matched_entry["similarity_score"] - SUPPORTING_SCORE_MARGIN
    ][:2]

    if client is None:
        return jsonify({
            "answer": matched_entry["answer"],
            "matched_topic": matched_entry["topic_id"],
            "matched_question": matched_entry["question"],
            "sources": matched_entry.get("sources", []),
            "note": "LLM not called — DASHSCOPE_API_KEY not set. Returning raw KB chunk.",
            "response_language": classification["language"],
        })

    try:
        language_label = LANGUAGE_LABELS[detected_lang]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(build_history_messages(history))
        messages.append({
            "role": "user",
            "content": build_final_user_message(
                user_question, matched_entry, language_label, supporting_entries
            ),
        })

        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=600,
            messages=messages,
        )
        llm_answer = response.choices[0].message.content
    except Exception as e:
        # Don't fail the request outright when the LLM call errors (e.g.
        # DashScope quota/billing issues, transient network errors). The
        # retrieval step already succeeded and matched_entry is a verified
        # KB answer -- returning a 502 here previously meant the frontend's
        # fetch treated the whole request as failed and never had a chance
        # to render the "fallback_answer" field, even though it was right
        # there in the body. Degrading to the raw KB text with a normal
        # 200 (same as the client-not-configured path above) means the
        # person still gets a correct, verified answer -- just without the
        # LLM's language-matching/tone polish -- instead of the app
        # appearing to silently break or repeat stale content.
        logger.exception("LLM call failed; degrading to raw KB answer")
        return jsonify({
            "answer": matched_entry["answer"],
            "matched_topic": matched_entry["topic_id"],
            "matched_question": matched_entry["question"],
            "sources": matched_entry.get("sources", []),
            "note": f"LLM call failed ({e.__class__.__name__}) — returning raw KB chunk.",
            "response_language": classification["language"],
        })

    return jsonify({
        "answer": llm_answer,
        "matched_topic": matched_entry["topic_id"],
        "matched_question": matched_entry["question"],
        "sources": matched_entry.get("sources", []),
        "response_language": classification["language"],
    })


# --- Azure Text-to-Speech for Urdu responses ----------------------------
@app.route("/api/tts-urdu", methods=["POST"])
def tts_urdu():
    """Synthesize Urdu text to speech using Azure Cognitive Services.

    Expects JSON body: {"text": "...Urdu text..."}
    Returns: WAV audio (audio/wav) or a JSON error on failure.
    """
    import azure.cognitiveservices.speech as speechsdk

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Missing 'text' in request body."}), 400

    speech_key = os.environ.get("AZURE_SPEECH_KEY")
    speech_region = os.environ.get("AZURE_SPEECH_REGION", "centralindia")

    if not speech_key:
        return jsonify({"error": "AZURE_SPEECH_KEY not configured on the server."}), 500

    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, region=speech_region
        )
        speech_config.speech_synthesis_voice_name = "ur-PK-UzmaNeural"

        # audio_config=None tells the SDK to return raw bytes in
        # result.audio_data instead of trying to play through a speaker
        # device (which would fail on a headless server).
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_data = result.audio_data
            return Response(audio_data, mimetype="audio/wav")
        else:
            error_detail = result.properties.get(
                speechsdk.PropertyId.SpeechServiceResponse_JsonErrorDetails
            )
            logger.error("Azure TTS synthesis failed: %s", error_detail)
            return jsonify({
                "error": "Speech synthesis failed.",
                "details": error_detail,
            }), 500
    except Exception as e:
        logger.exception("Azure TTS endpoint error")
        return jsonify({"error": "Speech synthesis failed.", "details": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "kb_entries_loaded": len(kb.entries),
        "llm_configured": client is not None,
        "firebase_configured": firebase_app is not None,
    })


@app.route("/suggested-questions", methods=["GET"])
def suggested_questions():
    """
    Returns a small set of example questions for the frontend to show as
    clickable starter chips above the 'Ask Panah AI' input — so a first-time
    user sees what kinds of things they can ask instead of a blank box.

    Optional query params:
      ?per_topic=1   — how many questions to pull per topic (default: 1)
      ?total=6       — max number of suggestions returned overall (default: 6)

    Example: GET /suggested-questions?total=8

    Reply: { "suggestions": [
        {"question": "...", "topic_id": "...", "topic_title": "..."}, ...
    ]}
    """
    try:
        per_topic = int(request.args.get("per_topic", 1))
        total = int(request.args.get("total", 6))
    except ValueError:
        return jsonify({"error": "'per_topic' and 'total' must be integers."}), 400

    if per_topic < 1 or total < 1:
        return jsonify({"error": "'per_topic' and 'total' must be positive."}), 400

    suggestions = kb.get_suggested_questions(per_topic=per_topic, total=total)
    return jsonify({"suggestions": suggestions})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
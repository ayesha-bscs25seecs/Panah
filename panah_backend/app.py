"""
app.py — Panah Flask backend.

Single endpoint: POST /ask
Body:  { "question": "mera shohar mujhe kharcha nahi deta" }
Reply: {
    "answer": "...",              # final Urdu answer from the LLM
    "matched_topic": "nafaqa",    # for debugging/demo purposes
    "matched_question": "...",
    "sources": [...],
    "escalation_tier": 1
}

Flow:
1. Retrieve the best-matching KB entry for the user's question (retrieval.py).
2. If no confident match: return a graceful "I don't know this one yet" reply
   WITHOUT calling the LLM with no grounding (avoids hallucinated answers).
3. If matched: build a system prompt with the tone rules + the retrieved
   chunk as ground truth, call Qwen (qwen-plus-character via DashScope's
   OpenAI-compatible endpoint), and return its Urdu response.

Run locally:
    export DASHSCOPE_API_KEY="your-key-here"
    pip install flask openai flask-cors --break-system-packages
    python app.py
"""

import os
import re
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

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

# --- Qwen / DashScope client setup -----------------------------------------
# Uses the OpenAI-compatible SDK pointed at Alibaba Cloud's international
# endpoint, per the project's confirmed working setup (qwen-plus-character
# has free quota on the team account; plain qwen-plus/qwen-flash did not).
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-plus-character"

client = None
if DASHSCOPE_API_KEY:
    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
else:
    logger.warning(
        "DASHSCOPE_API_KEY not set — /ask will return retrieval results "
        "without an LLM-generated response. Set the env var to enable full replies."
    )

# --- System prompt (tone + rules) -------------------------------------------
SYSTEM_PROMPT = """You are Panah, a warm, respectful AI assistant that helps rural and \
underprivileged Pakistani women understand their financial rights and protect \
themselves from scams. Keep answers short, warm, and clear, as if explained by \
a caring, knowledgeable friend or teacher — never formal, legalistic, or academic.

LANGUAGE RULE (very important):
Always reply in the SAME language and script the user used to ask their question:
- If the user wrote in English, reply in English.
- If the user wrote in Urdu script (e.g. "میرا شوہر مجھے خرچہ نہیں دیتا"), reply in Urdu script.
- If the user wrote in Roman Urdu (Urdu words spelled with English/Latin letters,
  e.g. "mera shohar mujhe kharcha nahi deta"), reply in Roman Urdu the same way.
- If a question mixes languages, mirror whichever style dominates the question.
- Never default to one language regardless of what the user wrote — detect it fresh
  for every question, since the same conversation may switch between languages.

Rules:
- Base your answer ONLY on the "Verified information" provided below. Do not \
add facts, laws, or rulings that aren't in it.
- The verified information itself may be in English or Urdu — regardless of \
which, translate/adapt its meaning into whatever language the RULE above says \
to answer in. Do not change its meaning while translating.
- Keep the tone gentle and non-judgmental. Never make the user feel blamed \
or embarrassed for asking.
- Do not give legal advice as if you are a lawyer — you are sharing \
knowledge, not issuing a legal ruling for her specific case.
- If the verified information suggests escalation (contacting a lawyer, \
Union Council, a scholar, etc.), mention it gently, but ALWAYS first make \
sure she feels informed and confident from the knowledge itself. Prefer \
suggesting a trusted local, educated woman (teacher, NGO worker, community \
figure) or Alkhidmat Foundation's women's welfare network before formal \
institutions, unless the verified information specifically says otherwise."""


def build_user_prompt(user_question: str, matched_entry: dict, language_label: str) -> str:
    context_lines = [f"Verified information:\n{matched_entry['answer']}"]
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

NO_MATCH_MESSAGES = {
    "urdu_script": (
        "معذرت، مجھے ابھی اس سوال کا جواب اپنی معلومات میں نہیں ملا۔ "
        "آپ اپنا سوال تھوڑا اور واضح طریقے سے پوچھ سکتی ہیں، یا کسی بھروسے مند "
        "سہارے (جیسے الخدمت فاؤنڈیشن) سے رابطہ کر سکتی ہیں۔"
    ),
    "english": (
        "Sorry, I don't have an answer for that question yet in my current "
        "knowledge. You could try rephrasing your question, or reach out to "
        "a trusted resource like the Alkhidmat Foundation."
    ),
    "roman_urdu": (
        "Maazrat, mujhe abhi is sawaal ka jawab apni maloomat mein "
        "nahi mila. Aap apna sawaal thora aur waazeh tareeqe se pooch "
        "sakti hain, ya kisi bharosemand sahara (jaise Alkhidmat "
        "Foundation) se raabta kar sakti hain."
    ),
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


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    user_question = (data.get("question") or "").strip()

    if not user_question:
        return jsonify({"error": "Missing 'question' in request body."}), 400

    classification = classify_and_translate(user_question)
    detected_lang = classification["language"]
    search_query = classification["english_query"]

    matched_entry = kb.get_best_match(search_query)
    # If searching the translated/English version found nothing, also try the
    # raw original text — helps for English/Roman Urdu questions where the
    # original wording may actually match keywords better than a paraphrase.
    if not matched_entry and search_query != user_question:
        matched_entry = kb.get_best_match(user_question)

    if not matched_entry:
        logger.info("No confident match for question: %r", user_question)
        return jsonify({
            "answer": NO_MATCH_MESSAGES[detected_lang],
            "matched_topic": None,
            "matched_question": None,
            "sources": [],
        })

    logger.info(
        "Matched question %r (lang=%s, search_query=%r) -> [%s / %s]",
        user_question, detected_lang, search_query,
        matched_entry["topic_id"], matched_entry["id"],
    )

    if client is None:
        # No API key configured — return the raw matched chunk so the
        # frontend/demo can still function without a live LLM call.
        return jsonify({
            "answer": matched_entry["answer"],
            "matched_topic": matched_entry["topic_id"],
            "matched_question": matched_entry["question"],
            "sources": matched_entry.get("sources", []),
            "note": "LLM not called — DASHSCOPE_API_KEY not set. Returning raw KB chunk.",
        })

    try:
        language_label = LANGUAGE_LABELS[detected_lang]
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=600,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(user_question, matched_entry, language_label)},
            ],
        )
        llm_answer = response.choices[0].message.content
    except Exception as e:
        logger.exception("LLM call failed")
        return jsonify({
            "error": "LLM call failed.",
            "details": str(e),
            "matched_topic": matched_entry["topic_id"],
            "matched_question": matched_entry["question"],
            "fallback_answer": matched_entry["answer"],
        }), 502

    return jsonify({
        "answer": llm_answer,
        "matched_topic": matched_entry["topic_id"],
        "matched_question": matched_entry["question"],
        "sources": matched_entry.get("sources", []),
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "kb_entries_loaded": len(kb.entries),
        "llm_configured": client is not None,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
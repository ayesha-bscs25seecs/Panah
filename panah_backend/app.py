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
themselves from scams. You speak in simple, spoken-style Urdu — never formal, \
legalistic, or academic language. Keep answers short, warm, and clear, as if \
explained by a caring, knowledgeable friend or teacher.

Rules:
- Base your answer ONLY on the "Verified information" provided below. Do not \
add facts, laws, or rulings that aren't in it.
- If the verified information is in English, translate the meaning into \
natural spoken-style Urdu for your answer — do not answer in English.
- If the verified information is already in Urdu, you may lightly adapt it \
for a natural conversational flow but do not change its meaning.
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


def build_user_prompt(user_question: str, matched_entry: dict) -> str:
    context_lines = [f"Verified information:\n{matched_entry['answer']}"]
    if matched_entry.get("legal_basis"):
        context_lines.append(f"\nLegal basis: {matched_entry['legal_basis']}")
    if matched_entry.get("islamic_basis"):
        context_lines.append(f"\nIslamic basis: {matched_entry['islamic_basis']}")
    if matched_entry.get("scope_note"):
        context_lines.append(f"\nImportant scope note: {matched_entry['scope_note']}")

    context_block = "\n".join(context_lines)
    return (
        f"User's question (may be in Roman Urdu, Urdu script, or English): "
        f"\"{user_question}\"\n\n"
        f"{context_block}\n\n"
        f"Now answer the user's question in simple, spoken-style Urdu, "
        f"using only the verified information above."
    )


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    user_question = (data.get("question") or "").strip()

    if not user_question:
        return jsonify({"error": "Missing 'question' in request body."}), 400

    matched_entry = kb.get_best_match(user_question)

    if not matched_entry:
        logger.info("No confident match for question: %r", user_question)
        return jsonify({
            "answer": (
                "Maazrat, mujhe abhi is sawaal ka jawab apni maloomat mein "
                "nahi mila. Aap apna sawaal thora aur waazeh tareeqe se pooch "
                "sakti hain, ya kisi bharosemand sahara (jaise Alkhidmat "
                "Foundation) se raabta kar sakti hain."
            ),
            "matched_topic": None,
            "matched_question": None,
            "sources": [],
        })

    logger.info(
        "Matched question %r -> [%s / %s]",
        user_question, matched_entry["topic_id"], matched_entry["id"],
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
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=600,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(user_question, matched_entry)},
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

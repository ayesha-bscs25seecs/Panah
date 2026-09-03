"""
app.py — Panah Flask backend.

Endpoints:
  POST /ask             — KB-grounded chatbot reply (unchanged, see below)
  POST /verify-session   — verifies a Firebase phone-auth ID token and
                            creates/finds the user record by phone number
  GET  /health           — status check

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

import os
import re
import json
import random
import logging
from flask import Flask, request, jsonify
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

# --- Firebase Admin setup ----------------------------------------------------
# Needs a service account key JSON downloaded from Firebase Console >
# Project settings > Service accounts > Generate new private key.
# Point GOOGLE_APPLICATION_CREDENTIALS at that file's path, or hardcode the
# path below. NEVER commit that file to git.
FIREBASE_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS", "./firebase-service-account.json"
)

firebase_app = None
if os.path.exists(FIREBASE_CREDENTIALS_PATH):
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_app = firebase_admin.initialize_app(cred)
else:
    logger.warning(
        "Firebase service account file not found at %s — /verify-session "
        "will reject all requests until this is set up.",
        FIREBASE_CREDENTIALS_PATH,
    )

# --- User store --------------------------------------------------------------
# PLACEHOLDER: plain in-memory dict, keyed by E.164 phone number.
# This is fine for a hackathon demo but resets on every server restart —
# same caveat as script.js's chat-history placeholder. Swap for a real DB
# (SQLite is enough to start) before treating this as a real launch, ideally
# at the same time chat history gets wired to a real backend too, since both
# will end up keyed by this same user record.
users_by_phone = {}


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

    user = users_by_phone.get(phone)
    if user is None:
        user = {"phone": phone, "firebase_uid": decoded.get("uid")}
        users_by_phone[phone] = user
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

Example of correctly chunked dual-source answer (broad question, both \
sources shown, enforcement held back as a follow-up instead of dumped):

"Nafaqa is a wife's right to **financial maintenance** from her husband — \
shelter, food, clothing, and essential living expenses.

Islam mein: Surah An-Nisa 4:34 places this responsibility on the husband as \
part of his role of care, not control.

Pakistan ke qanoon mein: under the **MFLO 1961**, this is a legally \
enforceable right.

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
    context_lines = [f"Verified information (primary match):\n{matched_entry['answer']}"]

    # For broad/general questions, retrieval may have scored one narrow entry
    # highest just by keyword coincidence. Supporting entries from the same
    # topic give the model enough material to answer generally first instead
    # of jumping straight into whichever narrow scenario happened to match.
    for extra in (supporting_entries or []):
        context_lines.append(
            f"\nVerified information (related, same topic — "
            f"\"{extra['question']}\"):\n{extra['answer']}"
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
    history = data.get("history")  # optional, see module docstring

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
            "answer": random.choice(NO_MATCH_MESSAGES[detected_lang]),
            "matched_topic": None,
            "matched_question": None,
            "sources": [],
        })

    logger.info(
        "Matched question %r (lang=%s, search_query=%r) -> [%s / %s]",
        user_question, detected_lang, search_query,
        matched_entry["topic_id"], matched_entry["id"],
    )

    # Gather up to 2 other entries from the SAME topic so a broad/general
    # question (e.g. "tell me about zakat") isn't answered from a single
    # narrow entry that happened to win the keyword tie-break (e.g. business
    # Zakat specifically) — see retrieval.py's scoring for why that can
    # happen on broad queries. Restricted to the matched topic so we don't
    # pull in unrelated context from a different subject.
    same_topic_candidates = kb.search(search_query, top_k=8)
    supporting_entries = [
        e for e in same_topic_candidates
        if e["topic_id"] == matched_entry["topic_id"] and e["id"] != matched_entry["id"]
    ][:2]

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
        "firebase_configured": firebase_app is not None,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
"""
fix_knowledge_base.py — One-time repair pass for knowledge_base.json.

WHY THIS EXISTS
----------------
Panah's KB was assembled by several different markdown->JSON conversion
scripts (convert_chunks.py, merge_khula.py) run over time against the same
source .md files. Two concrete, verifiable bugs in that pipeline caused most
of the "sometimes right, sometimes wrong / adds random extra info" behaviour
reported in the app:

  1. DUPLICATE / CORRUPT TOPIC. convert_chunks.py's regex-based section
     splitter matched exactly one heading in
     Khula_Nafaqa_Pakistan_RAG_Reference.md that happened to start with a
     digit ("1. Divorce & Marriage ..."), then treated *everything from
     that heading to the end of the file* as that section's body -- because
     no other heading in the file matched its "numbered heading" regex. The
     result is topic "1__divorce___marriage__..." whose single QA answer is
     117,179 characters: essentially the entire reference document,
     helplines, court citations and all. merge_khula.py separately (and
     correctly) parsed the *same* source file into 38 reasonably-sized
     chunks under topic "khula_nafaqa_pakistan_rag". Both ended up in
     knowledge_base.json side by side, so a divorce/khula question can
     embed-match either the good small chunk or the 117KB monster,
     essentially at random -- which is exactly the "sometimes right,
     sometimes wrong" symptom for this topic area.
     FIX: delete the corrupt duplicate topic outright; the same information
     already exists in the properly-chunked topic.

  2. OVERSIZED "SCAFFOLDING" ENTRIES EVERYWHERE ELSE. Whenever a source .md
     file's subsections didn't match the exact "## **Bold Title**" pattern
     convert_chunks.py's Strategy 2 looks for (e.g. plain "### Sub Title"
     with no bold, which several of the guides use), the whole section
     collapsed into ONE QA entry whose "question" is just the raw section
     heading (sometimes with leftover markdown "**" still attached, e.g.
     "3. Steps of Wealth Distribution (Sequence)**") and whose "answer" is
     the full raw multi-thousand-character section body, including raw
     markdown tables. These almost never match how a real user phrases a
     question (dead weight -> "doesn't answer questions it should"), and
     when they DO win a match, the LLM is handed a huge disorganized blob
     as "verified answer", which produces bloated / unfocused / partially
     unrelated-feeling replies regardless of how strict the system prompt
     is ("adds unnecessary info", "wrong answer").
     FIX: split every oversized answer into properly-sized chunks along
     natural boundaries (blank-line paragraphs, then table rows, then
     plain lines as a last resort), each becoming its own retrievable qa
     entry under the same topic.

  3. A rich, already hand-curated, well-sized Q&A dataset for exactly the
     domains hit hardest by bug #2 (Inheritance, Marriage/Polygamy,
     Judicial Divorce & Khula, Custody) sits unused in inherit_doc.py -- it
     was written to a .docx for human/Gemini review but never merged back
     into knowledge_base.json. FIX: fold it in as first-class topics.

Run this once from panah_backend/:
    python3 fix_knowledge_base.py
It reads knowledge_base.json, writes a timestamped backup, and overwrites
knowledge_base.json with the repaired version. Safe to re-run (idempotent
on already-repaired input, aside from re-splitting if you lower ANSWER_CAP).
"""

import json
import re
import shutil
import sys
import types
import importlib.util
from pathlib import Path

HERE = Path(__file__).parent
KB_PATH = HERE / "knowledge_base.json"

# Target size for a single QA "answer". This is a *target*, not a hard
# ceiling -- a chunk is allowed to run a bit over if that's where the only
# available natural break (blank line / table row) falls, rather than
# slicing mid-sentence.
ANSWER_CAP = 1200

# Topics known to already be hand-authored, natural Q&A (realistic
# Roman Urdu/English questions, concise answers) -- never touched.
GOLD_TOPIC_IDS = {
    "topic_1:_mehr_(dower)",
    "topic_2:_nafaqa_(maintenance)",
    "topic_3:_scam_/_fraud_awareness",
}

# The corrupt duplicate produced by convert_chunks.py's "only one numbered
# heading in the file" bug (see module docstring, bug #1). Its content is
# already covered by topic "khula_nafaqa_pakistan_rag".
CORRUPT_DUPLICATE_TOPIC_ID = "1__divorce___marriage__طلاق_اور_شادی_کی_اصطلاحات"

STOP_WORDS = {
    "mera", "meri", "kya", "main", "hai", "ka", "ki", "ke", "the", "and",
    "for", "with", "that", "this", "from", "what", "does", "her", "she",
    "his", "him", "are", "was", "were", "have", "has", "had",
}


def clean_title(title: str) -> str:
    """Strip leftover markdown artifacts (stray '**' bold markers, escaped
    '\\.' periods) that the old regex-based converter left in section
    titles, e.g. '3. Steps of Wealth Distribution (Sequence)**' ->
    '3. Steps of Wealth Distribution (Sequence)'."""
    t = title.strip()
    t = t.replace("\\.", ".")
    t = re.sub(r"\*+", "", t)
    return t.strip()


def make_keywords(text: str, limit: int = 8) -> list[str]:
    words = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE).split()
    seen = []
    for w in words:
        lw = w.lower()
        if len(lw) > 3 and lw not in STOP_WORDS and lw not in seen:
            seen.append(lw)
        if len(seen) >= limit:
            break
    return seen


# Several source sections are themselves already a mini FAQ bank -- a
# sequence of "**FAQ 12: <question>?**" or "**Q: <question>**" blocks back
# to back (e.g. khula_nafaqa_pakistan_rag's "IV.1 Understanding Khula" ...
# "IV.6 Practical and Procedural Questions"). For those, splitting on the
# FAQ's own boundaries -- and using its own question text as the entry's
# "question" -- is far more precise than generic paragraph-packing, since
# it gives each resulting entry a real, naturally-phrased question instead
# of all pieces sharing one generic parent heading.
_FAQ_HEADING_RE = re.compile(
    r"\*\*(?:FAQ\s*\d*|Q\d*)\s*[:.]?\s*([^*]{5,200}?)\*\*", re.MULTILINE
)


def split_faq_style(answer: str) -> list[tuple[str, str]] | None:
    """Returns a list of (question, answer_body) pairs if `answer` looks
    like a run of 2+ bolded FAQ/Q blocks, else None (caller falls back to
    the generic size-based splitter)."""
    matches = list(_FAQ_HEADING_RE.finditer(answer))
    if len(matches) < 2:
        return None

    pairs = []
    for i, m in enumerate(matches):
        question = clean_title(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(answer)
        body = answer[start:end].strip(" \n*")
        if body:
            pairs.append((question, body))
    return pairs or None


def split_oversized_answer(answer: str, cap: int = ANSWER_CAP) -> list[str]:
    """Break one big answer into a list of smaller ones, each as close to
    `cap` characters as possible without cutting a paragraph/table row in
    half. Falls back to line-level, then hard character slicing only if a
    single paragraph itself has no internal line breaks at all."""
    if len(answer) <= cap:
        return [answer]

    # Prefer paragraph breaks (blank line). If the whole thing is one
    # paragraph with no blank lines (common for raw markdown tables),
    # fall back to splitting on single newlines (table rows / list items).
    paragraphs = re.split(r"\n\s*\n", answer)
    if len(paragraphs) == 1:
        paragraphs = answer.split("\n")

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    joiner = "\n\n" if "\n\n" in answer else "\n"

    for para in paragraphs:
        para = para.strip("\n")
        if not para.strip():
            continue
        # A single paragraph that alone exceeds the cap (e.g. one huge
        # table with no row breaks) gets hard-wrapped at sentence/line
        # granularity so we never emit one unsplittable multi-KB blob.
        if len(para) > cap * 1.5:
            sub_lines = para.split("\n") if "\n" in para else re.split(r"(?<=[.؟?])\s+", para)
            for line in sub_lines:
                if current_len + len(line) > cap and current:
                    chunks.append(joiner.join(current).strip())
                    current, current_len = [], 0
                current.append(line)
                current_len += len(line)
            continue

        if current_len + len(para) > cap and current:
            chunks.append(joiner.join(current).strip())
            current, current_len = [], 0
        current.append(para)
        current_len += len(para)

    if current:
        chunks.append(joiner.join(current).strip())

    return [c for c in chunks if c.strip()] or [answer]


def repair_topic(topic: dict) -> dict:
    """Clean titles and split any oversized qa answers within one topic."""
    topic = dict(topic)
    if topic.get("title_en"):
        topic["title_en"] = clean_title(topic["title_en"])

    new_qa = []
    for qa in topic.get("qa", []):
        question = clean_title(qa.get("question", ""))
        answer = qa.get("answer", "")
        base_id = qa.get("id", "qa")

        # Prefer precise FAQ-boundary splitting when the section is itself
        # a run of "**FAQ N: ...?**" / "**Q: ...**" blocks -- each gets its
        # own real question instead of sharing the parent heading.
        faq_pairs = split_faq_style(answer)
        if faq_pairs:
            for i, (faq_question, faq_body) in enumerate(faq_pairs, start=1):
                for j, piece in enumerate(split_oversized_answer(faq_body), start=1):
                    entry = dict(qa)
                    entry["id"] = f"{base_id}_faq{i}" + (f"_p{j}" if j > 1 else "")
                    entry["question"] = faq_question
                    entry["answer"] = piece
                    entry["keywords"] = make_keywords(f"{faq_question} {piece[:200]}")
                    new_qa.append(entry)
            continue

        pieces = split_oversized_answer(answer)

        if len(pieces) == 1:
            entry = dict(qa)
            entry["question"] = question
            entry["answer"] = pieces[0]
            if not entry.get("keywords"):
                entry["keywords"] = make_keywords(f"{question} {pieces[0][:200]}")
            new_qa.append(entry)
            continue

        for i, piece in enumerate(pieces, start=1):
            entry = dict(qa)
            entry["id"] = f"{base_id}_p{i}"
            entry["question"] = question
            entry["answer"] = piece
            # Keywords are recomputed per-piece (not just copied from the
            # original) so each split-off chunk is findable on its own
            # specific content, not just the shared parent heading.
            entry["keywords"] = make_keywords(f"{question} {piece[:200]}")
            new_qa.append(entry)

    topic["qa"] = new_qa
    return topic


def load_inherit_doc_topics() -> list[dict]:
    """inherit_doc.py is hand-authored data (title/legal/islamic/qa) that
    was generated for a one-off .docx export and never merged into
    knowledge_base.json. It's real, natural, well-sized Q&A for exactly
    the domains (Inheritance, Marriage/Polygamy, Khula, Custody) that
    suffered worst from the scaffolding-dump bug. We only take the topics
    NOT already covered by the gold hand-authored Mehr/Nafaqa topics, to
    avoid diluting retrieval with near-duplicate content on those two."""
    mock_docx = types.ModuleType("docx")

    class _FakeParagraph:
        def add_run(self, *a, **k):
            return types.SimpleNamespace(bold=None, font=types.SimpleNamespace())

    class _FakeDoc:
        def __init__(self, *a, **k):
            pass

        def add_heading(self, *a, **k):
            return _FakeParagraph()

        def add_paragraph(self, *a, **k):
            return _FakeParagraph()

        def save(self, *a, **k):
            pass

    mock_docx.Document = _FakeDoc
    sys.modules["docx"] = mock_docx

    spec = importlib.util.spec_from_file_location("inherit_doc", HERE / "inherit_doc.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # writes a throwaway .docx via the fake Document; harmless

    skip_titles = {"topic 4: mehr and dower rights", "topic 5: maintenance (nafaqa)"}

    new_topics = []
    for t in mod.topics:
        title = t["title"]
        if title.strip().lower() in skip_titles:
            continue
        topic_id = "inherit_" + re.sub(r"[^\w]", "_", title.lower()).strip("_")
        qa_list = []
        for i, (q, a) in enumerate(t.get("qa", []), start=1):
            qa_list.append({
                "id": f"{topic_id}_qa_{i}",
                "question": q.strip(),
                "answer": a.strip(),
                "keywords": make_keywords(f"{title} {q}"),
            })
        new_topics.append({
            "id": topic_id,
            "title_en": clean_title(title.split(":", 1)[-1].strip() or title),
            "legal_basis": t.get("legal", "").strip() or None,
            "islamic_basis": t.get("islamic", "").strip() or None,
            "sources": [],
            "qa": qa_list,
        })
    return new_topics


def load_glossary_topic() -> dict:
    """khula_nafaqa_doc.py contains a hand-authored bilingual glossary
    (Khula, Talaq, Iddat, Nikah, Nafaqa, Haq Mehr, etc.) that never made it
    into knowledge_base.json as its own entries -- the only place these
    terms exist is buried inside large narrow FAQ/table chunks. That's why
    a plain "what is khula" / "talaq kya hai" question had nothing clean
    to match: every khula-related entry is a *specific* FAQ ("is khula
    islamic", "does khula cost the dower back"), not a basic definition,
    so a definitional question falls through to whichever specific FAQ
    happens to share the most keywords -- often the wrong one.

    This adds one small, literal "What is <Term>?" entry per glossary term
    so plain definitional questions have a clean, general answer to land
    on instead of competing against dozens of narrow specific FAQs."""
    data = json.loads((HERE / "khula_nafaqa_doc.py").read_text(encoding="utf-8"))
    glossary = data.get("core_bilingual_legal_glossary", {})

    qa_list = []
    idx = 1
    for category, terms in glossary.items():
        for term in terms:
            eng = term["english_term"]
            roman = term["roman_urdu"]
            urdu = term["urdu_script"]
            explanation = re.sub(r"\[cite:\s*\d+\]", "", term["explanation_english"]).strip()
            question = f"What is {eng}?" if eng.lower() == roman.lower() else f"What is {eng} ({roman})?"
            # `keywords` feeds the embedding text (see retrieval.py's
            # texts_to_embed) but is never shown to the user, so this is
            # where we add Roman-Urdu phrasing variants for cross-lingual
            # matching robustness -- important because translation isn't
            # always available (e.g. if the DASHSCOPE API call fails/quota
            # runs out, classify_and_translate falls back to the RAW,
            # untranslated query), so a purely English-phrased "question"
            # would match poorly against a raw Roman Urdu query in that
            # degraded mode.
            roman_variants = [f"{roman} kiya hai", f"{roman} kya hai", f"{roman} kya hota hai"]
            answer = f"{eng} ({urdu} / {roman}) means: {explanation}."
            qa_list.append({
                "id": f"glossary_qa_{idx}",
                "question": question,
                "answer": answer,
                "keywords": make_keywords(f"{eng} {roman} what is definition meaning") + roman_variants,
            })
            idx += 1

    return {
        "id": "core_bilingual_glossary",
        "title_en": "Core Legal & Islamic Terms Glossary",
        "legal_basis": None,
        "islamic_basis": None,
        "sources": ["khula_nafaqa_doc.py"],
        "qa": qa_list,
    }


def main():
    backup_path = KB_PATH.with_suffix(".json.before_fix_kb.bak")
    shutil.copyfile(KB_PATH, backup_path)
    print(f"Backed up original to {backup_path.name}")

    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    topics = kb["topics"]

    before_topics = len(topics)
    before_qa = sum(len(t.get("qa", [])) for t in topics)
    before_chars = sum(len(qa["answer"]) for t in topics for qa in t.get("qa", []))

    # 1. Drop the corrupt duplicate produced by the convert_chunks.py bug.
    topics = [t for t in topics if t["id"] != CORRUPT_DUPLICATE_TOPIC_ID]

    # 2. Repair every remaining topic (clean titles, split oversized answers).
    #    Gold topics are left byte-for-byte untouched.
    repaired = []
    for t in topics:
        if t["id"] in GOLD_TOPIC_IDS:
            repaired.append(t)
        else:
            repaired.append(repair_topic(t))
    topics = repaired

    # 3. Fold in the unused hand-authored inherit_doc.py topics.
    existing_ids = {t["id"] for t in topics}
    added = 0
    for new_topic in load_inherit_doc_topics():
        if new_topic["id"] not in existing_ids:
            topics.append(new_topic)
            existing_ids.add(new_topic["id"])
            added += 1

    # 3b. Fold in the plain-definition glossary (see load_glossary_topic
    #     docstring) -- this is the fix for "what is khula/talaq/..."
    #     matching the wrong narrow FAQ instead of a basic definition.
    glossary_topic = load_glossary_topic()
    if glossary_topic["id"] not in existing_ids:
        topics.append(glossary_topic)
        existing_ids.add(glossary_topic["id"])
        added += 1

    # 4. Drop degenerate leftovers: empty section stubs (a heading whose
    #    body was entirely consumed by its own subsections, e.g. "3.
    #    Inheritance (Mirath / Faraid)" once 3.1/3.2/3.3/3.4 exist as their
    #    own topics) and stray fragments the splitters above occasionally
    #    isolate (a lone sub-heading like "**Section A: Polygamy Rights"
    #    with no body left after its content was correctly attached to the
    #    preceding/following FAQ instead). Anything this short can't be a
    #    real standalone answer, so it's just noise if left in.
    MIN_ANSWER_WORDS = 6
    for t in topics:
        t["qa"] = [
            qa for qa in t.get("qa", [])
            if len(qa["answer"].split()) >= MIN_ANSWER_WORDS
        ]
    dropped_empty_topics = [t["id"] for t in topics if not t.get("qa")]
    topics = [t for t in topics if t.get("qa")]

    kb["topics"] = topics
    KB_PATH.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")

    after_topics = len(topics)
    after_qa = sum(len(t.get("qa", [])) for t in topics)
    after_chars = sum(len(qa["answer"]) for t in topics for qa in t.get("qa", []))
    max_after = max((len(qa["answer"]) for t in topics for qa in t.get("qa", [])), default=0)

    print("\n--- Repair summary ---")
    print(f"Topics:      {before_topics} -> {after_topics} (+{added} from inherit_doc.py, -1 corrupt duplicate, "
          f"-{len(dropped_empty_topics)} left empty after dropping degenerate stub entries)")
    print(f"QA entries:  {before_qa} -> {after_qa}")
    print(f"Total chars: {before_chars:,} -> {after_chars:,}")
    print(f"Largest single answer left: {max_after:,} chars (was {max((len(qa['answer']) for t in json.loads(backup_path.read_text(encoding='utf-8'))['topics'] for qa in t.get('qa', [])), default=0):,})")


if __name__ == "__main__":
    main()
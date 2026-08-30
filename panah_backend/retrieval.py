"""
retrieval.py — Keyword-based retrieval for the Panah knowledge base.

How it works (simple, transparent, no ML/embeddings needed):
1. Load knowledge_base.json once at startup.
2. Build a flat list of every Q&A entry across all topics, each carrying
   its own keywords + parent topic's legal/islamic basis + sources.
3. For an incoming user question, score every entry by counting how many
   of its keywords appear as substrings in the (lowercased) user question.
   Also give a small bonus if words from the entry's own "question" field
   appear in the user question.
4. Return the single best-matching entry (plus its score), or None if
   nothing scored above a minimum threshold.

This is intentionally simple and debuggable for a hackathon timeline.
If you have time later, swapping in embedding-based similarity (e.g.
sentence-transformers or a hosted embeddings API) would improve fuzzy
matching, but keyword matching works well for a fixed, curated KB like
this one where you control the keyword lists.
"""

import json
import re
from pathlib import Path

KB_PATH = Path(__file__).parent / "knowledge_base.json"

# Minimum score for a match to be considered "confident enough" to answer.
# A score of 0 means "no keywords matched at all" -> treat as no match.
MIN_SCORE_THRESHOLD = 2

# Common filler words (Roman Urdu + English) that appear in almost every
# question and should NOT count toward a match on their own — otherwise
# short, generic questions all look similar to each other.
STOPWORDS = {
    # Roman Urdu fillers
    "kya", "hai", "hain", "mein", "main", "ka", "ki", "ke", "aur", "ya",
    "se", "ko", "apna", "apni", "apne", "mera", "meri", "mere", "raha",
    "rahi", "rahe", "kar", "karna", "karti", "karta", "kare", "karein",
    "sakti", "sakta", "sakte", "bhi", "to", "woh", "yeh", "is", "isay",
    "koi", "agar", "par", "pe", "liye", "mujhe", "aap", "aapka", "aapki",
    "aapke", "hoon", "ho", "hoti", "hota", "gaya", "gayi", "gaye", "nahi",
    # English fillers
    "the", "a", "an", "do", "i", "my", "and", "or", "of", "in", "on",
    "to", "for", "is", "are", "am", "it", "if", "can", "what", "how",
}


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for simple substring matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _content_words(text: str) -> set:
    """Words from text with stopwords removed and short words dropped."""
    return {w for w in _normalize(text).split() if len(w) > 2 and w not in STOPWORDS}


class KnowledgeBase:
    def __init__(self, kb_path: Path = KB_PATH):
        with open(kb_path, "r", encoding="utf-8") as f:
            self.raw = json.load(f)
        self.entries = self._flatten()

    def _flatten(self):
        """Turn topics[].qa[] into one flat list of retrievable entries,
        each enriched with topic-level context (sources, legal/islamic basis)."""
        flat = []
        for topic in self.raw["topics"]:
            topic_context = {
                "topic_id": topic["id"],
                "topic_title": topic.get("title_en", topic["id"]),
                "answer_language": topic.get("answer_language", "en"),
                "legal_basis": topic.get("legal_basis"),
                "islamic_basis": topic.get("islamic_basis"),
                "sources": topic.get("sources", []),
                "scope_note": topic.get("scope_note"),
            }
            for qa in topic.get("qa", []):
                keywords_normalized = [_normalize(k) for k in qa.get("keywords", [])]
                flat.append({
                    "id": qa["id"],
                    "question": qa["question"],
                    "answer": qa["answer"],
                    "keywords": keywords_normalized,
                    # Precompute content-word sets for fast scoring
                    "_keyword_word_sets": [_content_words(k) for k in keywords_normalized],
                    "_question_words": _content_words(qa["question"]),
                    **topic_context,
                })
        return flat

    def search(self, user_question: str, top_k: int = 1):
        """Return the top_k best-matching entries with their scores,
        sorted highest score first. Entries below MIN_SCORE_THRESHOLD
        are excluded."""
        normalized_query = _normalize(user_question)
        query_words = _content_words(user_question)

        scored = []
        for entry in self.entries:
            score = 0

            # Keyword matching: whole-phrase substring match scores highest,
            # partial word overlap with a keyword phrase scores lower.
            for kw, kw_words in zip(entry["keywords"], entry["_keyword_word_sets"]):
                if not kw:
                    continue
                if kw in normalized_query:
                    score += 4  # exact phrase match — strong signal
                else:
                    score += 2 * len(query_words & kw_words)

            # Small bonus for content-word overlap with the entry's own
            # question text (helps when phrasing differs from keywords).
            score += 1 * len(query_words & entry["_question_words"])

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for score, entry in scored if score >= MIN_SCORE_THRESHOLD]
        return results[:top_k]

    def get_best_match(self, user_question: str):
        results = self.search(user_question, top_k=1)
        return results[0] if results else None


# Singleton instance the Flask app can import directly.
kb = KnowledgeBase()


if __name__ == "__main__":
    # Quick manual test — run: python retrieval.py
    test_questions = [
        "mera shohar mujhe kharcha nahi deta",
        "mehr nahi mila mujhe",
        "koi call kar ke ATM PIN maang raha hai",
        "zakat ka nisab kitna hai",
        "kya mein apni gold jewelry par zakat dun",
        "kya mein apna will kisi non muslim relative ke liye likh sakti hoon",
        "asdkjhaskjdh random gibberish text",
        "meri beti ko kitna hissa milega agar bhai bhi hai",
        "shohar ka farz kya hota hai islam mein kharche ka",
    ]
    for q in test_questions:
        match = kb.get_best_match(q)
        print("-" * 60)
        print("Q:", q)
        if match:
            print(f"-> Matched [{match['topic_id']} / {match['id']}]: {match['question']}")
        else:
            print("-> No confident match found")

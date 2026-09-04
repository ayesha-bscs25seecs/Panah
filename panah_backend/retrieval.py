"""
retrieval.py — Automated Multilingual Semantic Retrieval & RAG Backend Engine for Panah
Uses sentence-transformers to match Roman Urdu, Urdu, and English queries automatically.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from sentence_transformers import SentenceTransformer, util

KB_PATH = Path(__file__).parent / "knowledge_base.json"

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_SIMILARITY_THRESHOLD = 0.3


class KnowledgeBase:

    def __init__(self, kb_path: Path = KB_PATH):
        print("Loading SentenceTransformer model...")
        self.model = SentenceTransformer(MODEL_NAME)

        with open(kb_path, "r", encoding="utf-8") as f:
            self.raw = json.load(f)

        self.entries = self._flatten()

        # Focused embedding representation: Topic + Question + Keywords (Excludes long answer bodies to prevent noise)
        self.texts_to_embed = [
            f"Topic: {e['topic_title']} | Question: {e['question']} | Keywords: {' '.join(e['keywords'])}"
            for e in self.entries
        ]

        print("Precomputing embeddings for knowledge base entries...")
        self.entry_embeddings = self.model.encode(
            self.texts_to_embed, convert_to_tensor=True
        )
        print(
            f"Knowledge base ready: {len(self.entries)} entries loaded into vector memory."
        )

    def _flatten(self) -> list[Dict[str, Any]]:
        """Flatten topics and Q&A items into retrievable entry objects."""
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
                flat.append(
                    {
                        "id": qa["id"],
                        "question": qa["question"],
                        "answer": qa["answer"],
                        "keywords": qa.get("keywords", []),
                        **topic_context,
                    }
                )
        return flat

    def search(
        self,
        user_question: str,
        top_k: int = 1,
        min_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> list[Dict[str, Any]]:
        """Compute cosine similarity between query vector and knowledge base embeddings."""
        query_embedding = self.model.encode(
            user_question, convert_to_tensor=True
        )
        scores = util.cos_sim(query_embedding, self.entry_embeddings)[0]

        top_results = scores.topk(k=min(top_k, len(self.entries)))

        results = []
        for score, idx in zip(top_results.values, top_results.indices):
            score_val = score.item()
            if score_val >= min_threshold:
                match = dict(self.entries[idx.item()])
                match["similarity_score"] = round(score_val, 4)
                results.append(match)

        return results

    def get_best_match(
        self,
        user_question: str,
        min_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> Optional[Dict[str, Any]]:
        """Return top 1 matching entry or None if below confidence threshold."""
        results = self.search(
            user_question, top_k=1, min_threshold=min_threshold
        )
        return results[0] if results else None

    def get_suggested_questions(
        self, per_topic: int = 1, total: int = 6
    ) -> list[Dict[str, str]]:
        """
        Returns a small, diverse set of example questions for the frontend to
        show as clickable "starter" chips (e.g. above the 'Ask Panah AI' input
        box), so a first-time user sees what kinds of things they can ask
        instead of facing a blank input field.

        Picks up to `per_topic` question(s) from each topic, in topic order,
        then trims to `total` overall so the UI doesn't get overcrowded even
        as more topics are added to knowledge_base.json later.

        Returns: [{"question": "...", "topic_id": "...", "topic_title": "..."}, ...]
        """
        seen_topics = set()
        suggestions: list[Dict[str, str]] = []

        for entry in self.entries:
            tid = entry["topic_id"]
            count_for_topic = sum(1 for s in suggestions if s["topic_id"] == tid)
            if count_for_topic >= per_topic:
                continue
            suggestions.append({
                "question": entry["question"],
                "topic_id": tid,
                "topic_title": entry["topic_title"],
            })
            seen_topics.add(tid)
            if len(suggestions) >= total:
                break

        return suggestions


# Global instance loaded once on startup for Flask/FastAPI backend routes
kb = KnowledgeBase()


# ---------------------------------------------------------------------------
# Helpline fallback text, reused in the restricted fallback instruction below.
# Keep this in sync with Topic 8 (Emergency Helplines) in knowledge_base.json
# if those numbers ever change.
# ---------------------------------------------------------------------------
HELPLINE_REFERRAL_TEXT = (
    "PCSW 1043 (Punjab, 24/7), Ministry of Human Rights 1099 (nationwide, toll-free), "
    "or SLACC 0800-70806 (nationwide, 24/7)"
)


def process_user_query(
    user_query: str, threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> Dict[str, Any]:
    """
    RAG Integration helper: Prepares system instructions and payload based on KB matching score.
    Use this directly inside your Flask / FastAPI route handler.
    """
    match = kb.get_best_match(user_query, min_threshold=threshold)

    if match:
        # High confidence match -> RAG Grounded Mode
        system_instruction = (
            "You are Panah AI, an empathetic legal and social support assistant for women in Pakistan.\n"
            "Answer the user's question accurately using ONLY the verified legal context provided below.\n"
            "Maintain an empathetic, supportive tone and respond in the same language style as the user.\n\n"
            "IMPORTANT GUARDRAIL: Rephrase and explain the verified context naturally, but do NOT add "
            "any legal fact, number, percentage, section reference, exception, or claim that is not "
            "explicitly present in the context below -- even if it seems related or you believe it to be "
            "true from general knowledge. If the user's question asks for something the context below "
            "does not cover (e.g. a related but different scenario, a follow-up detail, or a number not "
            "stated here), say plainly that this specific detail isn't in Panah's verified records for "
            "this question, rather than filling the gap yourself.\n\n"
            f"--- VERIFIED KNOWLEDGE BASE CONTEXT ---\n"
            f"Topic: {match['topic_title']}\n"
            f"Verified Answer: {match['answer']}\n"
            f"Legal Basis: {match.get('legal_basis', 'N/A')}\n"
            f"Islamic Basis: {match.get('islamic_basis', 'N/A')}\n"
            f"----------------------------------------"
        )
        return {
            "mode": "knowledge_base_rag",
            "similarity_score": match["similarity_score"],
            "match": match,
            "system_instruction": system_instruction,
            "prompt_payload": user_query,
        }
    else:
        # Out-of-scope or general question -> Restricted LLM Fallback Mode
        system_instruction = (
            "You are Panah AI, an empathetic legal and social support assistant for women in Pakistan.\n"
            "No verified entry from the legal knowledge base matched this question.\n\n"
            "If the user's question is a general, emotional, or non-legal message (a greeting, "
            "expressing distress, asking for encouragement or reassurance, or a general safety "
            "question like recognizing a scam), respond warmly and helpfully as normal -- this is fine "
            "to answer directly.\n\n"
            "However, if the user's question asks for a specific legal, financial, or religious RULE, "
            "RIGHT, PROCEDURE, PERCENTAGE, or SECTION NUMBER (for example: inheritance shares, mehr, "
            "khula, custody, maintenance amounts, zakat calculation, or any other statutory or fiqh "
            "detail), you MUST NOT state any such fact from your own training knowledge, since it has "
            "not been verified against Pakistani law or Islamic sources for this app and could be wrong "
            "or outdated. Instead, say plainly and warmly that this specific question isn't yet in "
            "Panah's verified records, and suggest they contact a family lawyer or one of the helplines "
            f"({HELPLINE_REFERRAL_TEXT}).\n\n"
            "When in doubt about whether a question counts as a 'specific legal fact' request, treat it "
            "as one and use the safe referral response rather than guessing."
        )
        return {
            "mode": "general_llm_fallback",
            "similarity_score": None,
            "match": None,
            "system_instruction": system_instruction,
            "prompt_payload": user_query,
        }


if __name__ == "__main__":
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

    print("\n" + "=" * 60)
    print("RUNNING RAG BACKEND ROUTER BENCHMARK (Threshold: 0.65)")
    print("=" * 60)

    for q in test_questions:
        result = process_user_query(q)
        print("-" * 60)
        print("Q:", q)
        print(f"-> Mode: {result['mode']}")
        if result["match"]:
            m = result["match"]
            print(
                f"   Matched [{m['topic_id']} / {m['id']}] (Score: {m['similarity_score']}): {m['question']}"
            )
        else:
            print("   Action: Routing to base LLM fallback for general response.")
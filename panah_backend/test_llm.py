import os
from google import genai
from google.genai import types
from retrieval import process_user_query

# Configure Gemini API (new google-genai SDK -- google.generativeai is fully
# end-of-life and gemini-1.0/1.5/2.0 models have all been shut down as of 2026)
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Please set your GEMINI_API_KEY environment variable.")

client = genai.Client(api_key=api_key)

# gemini-2.5-flash is confirmed working as of Sept 2026 but is scheduled to
# shut down Oct 16, 2026 (Developer API) -- gemini-3.5-flash / gemini-3.7-flash
# are the current-generation models with no announced shutdown date, and are
# the better long-term pick for anything you're actively building on.
MODEL_NAME = "gemini-3.5-flash"

# Curated benchmark questions covering RAG matches, fallbacks, and edge cases.
# NOTE: the "Expected" comments below are your best guess of the routing outcome --
# treat them as hypotheses to check, not guaranteed results. In particular:
#   - The OTP/bank scam question may actually MATCH your Topic 3 (Scam / Fraud
#     Awareness) entries in knowledge_base.json rather than falling back, since
#     that topic already covers ATM PIN / bank impersonation scams.
#   - The Zakat question may match a KB topic instead of falling back, IF your
#     Zakat guide content was converted into knowledge_base.json's 71 topics.
# Read the printed "Mode" line as the source of truth, not the comment.
benchmark_questions = [
    # Hypothesis: Knowledge Base RAG Mode (Nafaqa)
    "mera shohar mujhe kharcha nahi deta, main kya karoon?",
    # Hypothesis: Knowledge Base RAG Mode (Mehr)
    "shadi ko 2 saal ho gaye hain aur mehr nahi mila",
    # Hypothesis: Knowledge Base RAG Mode OR Fallback -- verify against Topic 3 (Scam Awareness)
    "koi call kar ke bol raha hai bank account blocked hai, OTP doon?",
    # Hypothesis: Fallback OR KB Mode -- verify whether a Zakat topic exists in your KB
    "zakat kin logon ko di ja sakti hai?",
    # Hypothesis: General LLM Fallback (Unrelated / Out of Scope)
    "what is the best way to prepare for computer science exams?",
]


def run_ai_benchmark():
    print("\n" + "=" * 70)
    print("STARTING END-TO-END RAG & LLM RESPONSE BENCHMARK")
    print("=" * 70 + "\n")

    for idx, q in enumerate(benchmark_questions, 1):
        print(f"[{idx}] User Query: {q}")

        # Get routing payload from retrieval.py
        payload = process_user_query(q, threshold=0.65)
        mode = payload["mode"]

        print(f"    Mode: {mode}")
        if mode == "knowledge_base_rag":
            print(
                f"    Matched Entry: [{payload['match']['topic_id']} / {payload['match']['id']}] "
                f"(Score: {payload['similarity_score']})"
            )

        # In the new google-genai SDK, system_instruction and generation config
        # both go into a GenerateContentConfig passed to generate_content() --
        # no need to rebuild a model object per query like the old SDK required.
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=payload["prompt_payload"],
                config=types.GenerateContentConfig(
                    system_instruction=payload["system_instruction"],
                    temperature=0.3,
                ),
            )

            print("\n--- AI Response ---")
            print(response.text.strip())
            print("-" * 70 + "\n")

        except Exception as e:
            print(f"\n[API Error]: {e}\n" + "-" * 70 + "\n")


if __name__ == "__main__":
    run_ai_benchmark()
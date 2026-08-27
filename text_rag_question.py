"""
Test script #2: simulates the actual RAG pattern your project will use.
Instead of asking Qwen a generic question, we feed it a REAL question + the
matching knowledge chunk you researched, and see how well it answers using
ONLY that information. This is the core pattern your backend will run.
"""

import os
from openai import OpenAI

api_key = os.environ.get("DASHSCOPE_API_KEY")

if not api_key:
    raise ValueError("DASHSCOPE_API_KEY not found. Set it as an environment variable first.")

client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

# --- Step 1: The user's question (in real life, this comes from the chat/voice input) ---
user_question = "Mera mehr ada nahi hua, kya main abhi bhi le sakti hoon?"

# --- Step 2: The matching knowledge chunk (in real life, this is "retrieved" by
# matching keywords in the question to your knowledge base files) ---
knowledge_chunk = """
Mehr in Pakistan is legally recognized under Section 10 of the Muslim Family Laws
Ordinance (MFLO), 1961. A wife can demand her mehr at any point during the marriage,
and the husband is legally obligated to pay it. Mehr belongs entirely to the wife as
her personal property and can be claimed even after divorce. It does not disappear
if the marriage ends.
"""

# --- Step 3: The system prompt — this sets the AI's behavior and tone for
# every answer, not just this one. This is the most important part to get right. ---
system_prompt = """
You are a warm, respectful assistant helping Pakistani women understand their
financial rights in simple, spoken-style Urdu (written in Roman Urdu or Urdu script,
matching the user's own style).

Rules you must always follow:
1. Answer ONLY using the information given to you in the knowledge chunk below.
   Do not add legal or religious details that aren't in the chunk.
2. Keep answers short — 2 to 4 sentences, like a caring, knowledgeable friend talking,
   not a formal document.
3. Never use complex legal or religious jargon without explaining it simply.
4. Always end with a gentle suggestion to speak with a trusted, knowledgeable woman in
   her community (such as a teacher or welfare worker) if she wants to take further
   steps — never assume she has access to a lawyer or formal office.
5. Be warm and non-judgmental. Never make her feel ashamed for asking.
"""

# --- Step 4: Combine everything and send it to the model ---
response = client.chat.completions.create(
    model="qwen-plus-character",
    messages=[
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Knowledge chunk:\n{knowledge_chunk}\n\nQuestion: {user_question}",
        },
    ],
)

print("Question asked:")
print(user_question)
print("\nAI's answer:")
print(response.choices[0].message.content)
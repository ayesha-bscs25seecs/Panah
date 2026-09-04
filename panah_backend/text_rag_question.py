import os
from openai import OpenAI
from retrieval import kb

api_key = os.environ.get("DASHSCOPE_API_KEY")

if not api_key:
    raise ValueError("DASHSCOPE_API_KEY not found.")

client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

user_question = input("Type your question here: ")

# Search matching chunk dynamically
matches = kb.search(user_question, top_k=1)

if matches:
    match = matches[0]
    print(f"\n[DEBUG] Matched Entry: {match['id']} (Topic: {match['topic_id']})")
    knowledge_chunk = (
        f"Topic: {match['topic_title']}\n"
        f"Question Context: {match['question']}\n"
        f"Answer Facts: {match['answer']}\n"
        f"Legal Basis: {match['legal_basis']}"
    )
else:
    print("\n[DEBUG] No matching rule found above threshold.")
    knowledge_chunk = "No specific legal matching rule found in the database."

system_prompt = """
You are a warm, respectful assistant helping Pakistani women understand their
financial and legal rights in simple, clear language (written in English or Roman Urdu matching the user's style).

Rules you must always follow:
1. Answer strictly using the facts given in the Knowledge Chunk below.
2. If specific details (like dates, section numbers, or fees) are in the chunk, include them directly.
3. Keep answers clear, accurate, and concise (2 to 4 sentences).
4. Do not invent or assume any legal details outside the chunk.
5. If the chunk says no rule was found, state politely that the specific detail is not in your current records.
6. Be warm, supportive, and non-judgmental.
"""

response = client.chat.completions.create(
    model="qwen-plus-character",
    messages=[
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Knowledge chunk:\n{knowledge_chunk}\n\n"
                f"Question: {user_question}"
            ),
        },
    ],
)

print("\n--- AI Answer ---")
print(response.choices[0].message.content)
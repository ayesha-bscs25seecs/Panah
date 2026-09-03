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

# Replace the hardcoded string with an interactive prompt
user_question = input("Type your question here: ")

# Retrieve matching chunk dynamically
match = kb.get_best_match(user_question)

if match:
  knowledge_chunk = (
      f"Topic: {match['topic_title']}\n"
      f"Answer: {match['answer']}\n"
      f"Legal Basis: {match['legal_basis']}"
  )
else:
  knowledge_chunk = "No specific legal matching rule found."

system_prompt = """
You are a warm, respectful assistant helping Pakistani women understand their
financial rights in simple, spoken-style Urdu (written in Roman Urdu or Urdu script,
matching the user's own style).

Rules you must always follow:
1. Answer ONLY using the information given to you in the knowledge chunk below.
   Do not add legal or religious details that aren't in the chunk.
2. Keep answers short — 2 to 4 sentences, like a caring, knowledgeable friend talking.
3. Never use complex legal or religious jargon without explaining it simply.
4. Always end with a gentle suggestion to speak with a trusted, knowledgeable woman in
   her community if she wants to take further steps.
5. Be warm and non-judgmental.
"""

response = client.chat.completions.create(
    model="qwen-plus-character",
    messages=[
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Knowledge chunk:\n{knowledge_chunk}\n\nQuestion:"
                f" {user_question}"
            ),
        },
    ],
)

print("\n--- AI Answer ---")
print(response.choices[0].message.content)
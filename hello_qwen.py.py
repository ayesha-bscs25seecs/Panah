"""
Test script: confirms the Alibaba Cloud (DashScope/Qwen) API connection works.
Run this first, before building anything else, to prove the pipeline is live.
"""

import os
from openai import OpenAI

# Reads your API key from an environment variable (safer than hardcoding it)
# Set this before running: export DASHSCOPE_API_KEY=your-key-here (Mac/Linux)
#                    or:    $env:DASHSCOPE_API_KEY="your-key-here" (Windows PowerShell)
api_key = os.environ.get("DASHSCOPE_API_KEY")

if not api_key:
    raise ValueError(
        "DASHSCOPE_API_KEY not found. Set it as an environment variable first, "
        "or load it from a .env file (see note at the bottom of this script)."
    )

client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",  # Singapore/international endpoint — this is what gives you the free quota
)

response = client.chat.completions.create(
    model="qwen-plus-character",  # confirmed to have free quota (1,000,000 tokens) on this account
    messages=[
        {"role": "user", "content": "hello, can you introduce yourself in one sentence?"}
    ],
)

print("Reply from Qwen:")
print(response.choices[0].message.content)


# --- Optional: if you'd rather load the key from a .env file instead of setting
# an environment variable manually each time, do this instead:
#
# pip install python-dotenv
#
# from dotenv import load_dotenv
# load_dotenv()
# api_key = os.environ.get("DASHSCOPE_API_KEY")
#
# and create a .env file in the same folder containing:
# DASHSCOPE_API_KEY=your-actual-key-here


# --- Note: qwen-plus-character is a persona/roleplay-tuned model variant, not the
# plain general-purpose qwen-plus. Test it with a real question from your knowledge
# base (e.g. a mehr or nafaqa question) to confirm tone and accuracy hold up for
# factual Q&A, since roleplay-tuned models can behave differently on structured tasks.
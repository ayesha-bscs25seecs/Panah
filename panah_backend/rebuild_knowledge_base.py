import json
import os
import time
from google import genai
from google.genai import types

# Initialize Gemini Client
client = genai.Client()

SYSTEM_INSTRUCTION = """
You are an expert AI data engineer specializing in structuring legal and Islamic finance knowledge bases.
Your job is to transform raw markdown document chunks/tables into realistic, conversational Q&A entries.

For each raw chunk provided:
1. Generate 2 to 4 realistic, natural user questions in Roman Urdu, Urdu, or conversational English that a regular user would ask.
2. Draft a clear, clean, and direct answer in plain prose or simple bullet points. Remove all garbled HTML, <br> tags, and messy table syntax.
3. Add a list of 5-8 relevant search keywords covering Roman Urdu variations, English, and technical Islamic/Legal terms.

Output MUST be a JSON array of Q&A objects adhering strictly to this schema:
[
  {
    "qa_id": "STRING",
    "question": "STRING (Natural user query)",
    "answer": "STRING (Clean, readable prose answer)",
    "keywords": ["keyword1", "keyword2"]
  }
]
"""

def reformat_topic(topic_title, raw_qa_list):
    """
    Sends raw markdown/table entries to Gemini to convert into structured Q&As.
    """
    raw_content_str = json.dumps(raw_qa_list, indent=2)
    
    prompt = f"""
    Topic Title: {topic_title}
    
    Raw Unformatted Entries:
    {raw_content_str}
    
    Convert these raw entries into clean, conversational Q&A pairs matching natural user intent.
    """

    # Updated model string to gemini-3.6-flash
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    
    return json.loads(response.text)

def process_knowledge_base(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        kb_data = json.load(f)

    # Topics that are already clean (e.g., Mehr, Nafaqa, Scam Awareness)
    PRESERVED_TOPICS = ["mehr", "nafaqa", "scam_awareness", "fraud"]

    updated_topics = []

    for topic in kb_data.get("topics", []):
        # NOTE: topic dicts use "id" and "title_en" (see retrieval.py's
        # KnowledgeBase._flatten and knowledge_base.json itself) -- this
        # previously read "topic_id"/"title", which don't exist on these
        # objects, so topic_id/topic_title were always "" and the
        # PRESERVED_TOPICS check below silently never matched anything,
        # meaning every topic (including the hand-authored Mehr/Nafaqa/
        # Scam ones this was supposed to skip) would have been sent off to
        # be reprocessed by the LLM.
        topic_id = topic.get("id", "").lower()
        topic_title = topic.get("title_en", "")
        
        # Check if topic needs re-processing
        if any(p in topic_id for p in PRESERVED_TOPICS):
            print(f"Skipping preserved topic: {topic_title}")
            updated_topics.append(topic)
            continue

        print(f"Processing and converting topic: {topic_title}...")
        
        raw_qas = topic.get("qa", [])
        if not raw_qas:
            updated_topics.append(topic)
            continue

        try:
            # Generate clean Q&A pairs
            cleaned_qas = reformat_topic(topic_title, raw_qas)
            topic["qa"] = cleaned_qas
            updated_topics.append(topic)
            print(f"Successfully converted {len(cleaned_qas)} Q&A pairs for {topic_title}.")
            time.sleep(1) # Prevent rate limits
        except Exception as e:
            print(f"Error processing {topic_title}: {e}")
            updated_topics.append(topic)

    # Save reconstructed knowledge base
    kb_data["topics"] = updated_topics
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(kb_data, f, ensure_ascii=False, indent=2)

    print(f"\nConversion complete! Updated knowledge base saved to {output_file}")

if __name__ == "__main__":
    process_knowledge_base("knowledge_base.json", "knowledge_base_fixed.json")
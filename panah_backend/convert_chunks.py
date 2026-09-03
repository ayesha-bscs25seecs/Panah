import json
import re
from docx import Document


def extract_text_from_docx(file_path):
  doc = Document(file_path)
  return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])


def convert_docx_to_retrieval_json(doc_path):
  full_text = extract_text_from_docx(doc_path)
  topics_data = []

  # Split document into topic blocks
  topic_blocks = re.split(r"(Topic \d+: [^\n]+)", full_text)

  for i in range(1, len(topic_blocks), 2):
    topic_title = topic_blocks[i].strip()
    topic_body = topic_blocks[i + 1]

    # Extract legal and islamic basis
    legal_match = re.search(
        r"Legal basis\n(.*?)(?=Islamic basis|Q&A chunks|$)",
        topic_body,
        re.DOTALL,
    )
    islamic_match = re.search(
        r"Islamic basis\n(.*?)(?=Q&A chunks|Sources|$)",
        topic_body,
        re.DOTALL,
    )

    # Extract Q&A items
    qa_list = []
    qa_matches = re.findall(
      r"Q:\s*(.*?)\s*A:\s*(.*?)(?=\s*Q:|\s*Sources|$)",
      topic_body,
      re.DOTALL,
    )

    for idx, (q, a) in enumerate(qa_matches):
      # Extract key content words to act as fallback keywords
      keywords = [
          w.lower()
          for w in re.sub(r"[^\w\s]", "", q).split()
          if len(w) > 3 and w.lower() not in ["mera", "meri", "kya", "main"]
      ]

      qa_list.append({
          "id": f"qa_{idx+1}",
          "question": q.strip(),
          "answer": a.strip(),
          "keywords": list(set(keywords)),
      })

    topics_data.append({
        "id": topic_title.lower().replace(" ", "_"),
        "title_en": topic_title,
        "legal_basis": legal_match.group(1).strip() if legal_match else "",
        "islamic_basis": (
            islamic_match.group(1).strip() if islamic_match else ""
        ),
        "sources": [],
        "qa": qa_list,
    })

  return {"topics": topics_data}


# Generate schema-compliant knowledge_base.json
data = convert_docx_to_retrieval_json(
    "knowledge_base_mehr_nafaqa_scams_v2.md.docx"
)

with open("knowledge_base.json", "w", encoding="utf-8") as f:
  json.dump(data, f, indent=2, ensure_ascii=False)

print("`knowledge_base.json` updated with topic schema!")
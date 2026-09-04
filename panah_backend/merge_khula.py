import json
import re

MD_FILENAME = "Khula_Nafaqa_Pakistan_RAG_Reference.md"

# 1. Load clean knowledge_base.json
with open('knowledge_base.json', 'r', encoding='utf-8') as f:
    kb = json.load(f)

# 2. Read the Markdown file
with open(MD_FILENAME, 'r', encoding='utf-8') as f:
    content = f.read()

# 3. Parse headers (## or ###) as questions/topics and paragraphs as answers
sections = re.split(r'\n(?=#{1,3}\s+)', content)

qa_list = []
idx = 1
for sec in sections:
    sec = sec.strip()
    if not sec:
        continue
    lines = sec.split('\n')
    header = lines[0].strip('# ').strip()
    body = '\n'.join(lines[1:]).strip()
    
    if header and body:
        qa_list.append({
            "id": f"khula_qa_{idx}",
            "question": header,
            "answer": body
        })
        idx += 1

if qa_list:
    # Remove any previously added corrupt topic entries if present
    kb['topics'] = [t for t in kb['topics'] if t.get("id") != "khula_nafaqa_pakistan_rag"]

    khula_topic = {
        "id": "khula_nafaqa_pakistan_rag",
        "topic": "Khula, Talaq, Maintenance and Child Rights in Pakistan Law",
        "keywords": ["khula", "talaq", "divorce", "dissolution of marriage", "iddat", "nafaqa", "maintenance", "custody"],
        "qa": qa_list
    }
    
    kb['topics'].append(khula_topic)
    
    with open('knowledge_base.json', 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)
        
    print(f"Success! Merged {len(qa_list)} Q&As with IDs into knowledge_base.json!")
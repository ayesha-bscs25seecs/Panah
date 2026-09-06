import glob
import json
import os
import re


def parse_md_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    topics_data = []

    # Strategy 1: Check for "Topic X:" or "# Topic X:" structures
    topic_blocks = re.split(
        r"(?:^|\n)(?:#+\s*)?(Topic\s+\d+[:\s][^\n]+)",
        full_text,
        flags=re.IGNORECASE,
    )

    if len(topic_blocks) > 1:
        for i in range(1, len(topic_blocks), 2):
            topic_title = topic_blocks[i].strip()
            topic_body = topic_blocks[i + 1]

            legal_match = re.search(
                r"\*?\*?Legal\s+basis\*?\*?:?\s*\n(.*?)(?=\*?\*?Islamic\s+basis\*?\*?:?|\*?\*?Q&A|\*?\*?Sources|$)",
                topic_body,
                re.DOTALL | re.IGNORECASE,
            )
            islamic_match = re.search(
                r"\*?\*?Islamic\s+basis\*?\*?:?\s*\n(.*?)(?=\*?\*?Q&A|\*?\*?Sources|$)",
                topic_body,
                re.DOTALL | re.IGNORECASE,
            )
            sources_match = re.search(
                r"\*?\*?Sources\*?\*?:?\s*\n(.*?)(?=\*?\*?Q&A|$)",
                topic_body,
                re.DOTALL | re.IGNORECASE,
            )

            qa_list = []
            qa_matches = re.findall(
                r"\*?\*?Q\d*:?\*?\*?\s*(.*?)\s*\*?\*?A\d*:?\*?\*?\s*(.*?)(?=\*?\*?Q\d*:?\*?\*?|\*?\*?Sources\*?\*?:?|$)",
                topic_body,
                re.DOTALL | re.IGNORECASE,
            )

            stop_words = {
                "mera",
                "meri",
                "kya",
                "main",
                "hai",
                "ka",
                "ki",
                "ke",
            }

            for idx, (q, a) in enumerate(qa_matches):
                clean_q = q.strip()
                clean_a = a.strip()
                if not clean_q:
                    continue
                words = re.sub(r"[^\w\s]", "", clean_q).split()
                keywords = list(
                    {
                        w.lower()
                        for w in words
                        if len(w) > 3 and w.lower() not in stop_words
                    }
                )
                qa_list.append(
                    {
                        "id": f"qa_{idx+1}",
                        "question": clean_q,
                        "answer": clean_a,
                        "keywords": keywords,
                    }
                )

            sources_list = []
            if sources_match:
                sources_raw = sources_match.group(1).strip()
                sources_list = [
                    line.strip("-* ").strip()
                    for line in sources_raw.split("\n")
                    if line.strip()
                ]

            topic_id = re.sub(r"[^\w]", "_", topic_title.lower()).strip("_")
            topics_data.append(
                {
                    "id": topic_id,
                    "title_en": topic_title,
                    "legal_basis": legal_match.group(1).strip()
                    if legal_match
                    else "",
                    "islamic_basis": islamic_match.group(1).strip()
                    if islamic_match
                    else "",
                    "sources": sources_list,
                    "qa": qa_list,
                }
            )
        return topics_data

    # Strategy 2: Check for numbered headings (e.g. # **1\. Title** or # 1. Title)
    sections = re.split(
        r"(?:^|\n)#+\s+(?:\*\*)?(\d+[\.\\]*\s*[^\n]+?)(?:\*\*)?(?=\n|$)",
        full_text,
        flags=re.IGNORECASE,
    )

    if len(sections) > 1:
        for i in range(1, len(sections), 2):
            sec_title = sections[i].replace("\\.", ".").strip()
            sec_body = sections[i + 1].strip()

            islamic_refs = re.findall(
                r"(_Hadith:.*?_|Hadith:.*?\n\n_.*?_|The Qur'an \(.*?\).*?:)",
                sec_body,
                re.DOTALL,
            )
            islamic_basis = "\n\n".join(islamic_refs) if islamic_refs else ""

            subsections = re.findall(
                r"##\s+\*\*([^*]+)\*\*\s*\n(.*?)(?=\n##|\Z)", sec_body, re.DOTALL
            )

            qa_list = []
            stop_words = {
                "mera",
                "meri",
                "kya",
                "main",
                "hai",
                "ka",
                "ki",
                "ke",
            }

            if subsections:
                for idx, (sub_title, sub_content) in enumerate(subsections):
                    clean_q = sub_title.strip()
                    clean_a = sub_content.strip()
                    words = re.sub(r"[^\w\s]", "", clean_q).split()
                    keywords = list(
                        {
                            w.lower()
                            for w in words
                            if len(w) > 3 and w.lower() not in stop_words
                        }
                    )
                    qa_list.append(
                        {
                            "id": f"qa_{idx+1}",
                            "question": clean_q,
                            "answer": clean_a,
                            "keywords": keywords,
                        }
                    )
            else:
                clean_q = re.sub(r"^\d+[\.\\]*\s*", "", sec_title).strip()
                words = re.sub(r"[^\w\s]", "", clean_q).split()
                keywords = list(
                    {
                        w.lower()
                        for w in words
                        if len(w) > 3 and w.lower() not in stop_words
                    }
                )
                # GUARDRAIL: this "else" branch fires whenever no bold
                # "## **Sub Title**" subsections were found inside the
                # section body -- which also fires when this regex only
                # matched ONE numbered heading in the whole file, in which
                # case `sec_body` is *everything from that heading to the
                # end of the document* (re.split with a single match
                # returns just two pieces: before and after). That bug
                # previously produced a single 117,000+ character "answer"
                # containing an entire reference document. If that happens
                # again, split defensively on blank-line paragraphs instead
                # of emitting one unbounded blob.
                if len(sec_body) > 1500:
                    paras = [p.strip() for p in re.split(r"\n\s*\n", sec_body) if p.strip()]
                    packed, current, current_len = [], [], 0
                    for p in paras:
                        if current_len + len(p) > 1200 and current:
                            packed.append("\n\n".join(current))
                            current, current_len = [], 0
                        current.append(p)
                        current_len += len(p)
                    if current:
                        packed.append("\n\n".join(current))
                    for i, piece in enumerate(packed, start=1):
                        qa_list.append(
                            {
                                "id": f"qa_{i}",
                                "question": clean_q,
                                "answer": piece,
                                "keywords": keywords,
                            }
                        )
                else:
                    qa_list.append(
                        {
                            "id": "qa_1",
                            "question": clean_q,
                            "answer": sec_body,
                            "keywords": keywords,
                        }
                    )

            topic_id = re.sub(r"[^\w]", "_", sec_title.lower()).strip("_")
            topics_data.append(
                {
                    "id": topic_id,
                    "title_en": sec_title,
                    "legal_basis": sec_body,
                    "islamic_basis": islamic_basis,
                    "sources": [os.path.basename(file_path)],
                    "qa": qa_list,
                }
            )
        return topics_data

    # Strategy 3: Standard Markdown Heading Fallback (# or ## headers)
    headers = re.split(r"(?:^|\n)(#+\s+[^\n]+)", full_text)
    if len(headers) > 1:
        for i in range(1, len(headers), 2):
            h_title = re.sub(r"^#+\s*", "", headers[i]).strip()
            h_body = headers[i + 1].strip()

            if not h_title or len(h_body) < 10:
                continue

            words = re.sub(r"[^\w\s]", "", h_title).split()
            keywords = list(
                {
                    w.lower()
                    for w in words
                    if len(w) > 3
                    and w.lower() not in {"mera", "meri", "kya", "main"}
                }
            )

            topic_id = re.sub(r"[^\w]", "_", h_title.lower()).strip("_")
            topics_data.append(
                {
                    "id": topic_id,
                    "title_en": h_title,
                    "legal_basis": h_body,
                    "islamic_basis": "",
                    "sources": [os.path.basename(file_path)],
                    "qa": [
                        {
                            "id": "qa_1",
                            "question": h_title,
                            "answer": h_body,
                            "keywords": keywords,
                        }
                    ],
                }
            )

    return topics_data


# --- SAFE MERGE LOGIC ---
json_file = "knowledge_base.json"

if os.path.exists(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        try:
            existing_db = json.load(f)
        except json.JSONDecodeError:
            existing_db = {"topics": []}
else:
    existing_db = {"topics": []}

existing_ids = {t["id"] for t in existing_db.get("topics", [])}
total_added = 0

md_files = [f for f in glob.glob("*.md") if f.lower() != "readme.md"]

for md_file in md_files:
    new_topics = parse_md_file(md_file)
    added_from_file = 0

    for topic in new_topics:
        if topic["id"] not in existing_ids:
            existing_db["topics"].append(topic)
            existing_ids.add(topic["id"])
            added_from_file += 1

    total_added += added_from_file
    print(f"Parsed '{md_file}': Added {added_from_file} new topic(s).")

with open(json_file, "w", encoding="utf-8") as f:
    json.dump(existing_db, f, indent=2, ensure_ascii=False)

print(
    f"\nDone! Added {total_added} new topic(s). Total topics in JSON: {len(existing_db['topics'])}"
)
# Panah Backend

Three files, all you need for the `/ask` endpoint:

- `knowledge_base.json` — the structured KB (Mehr, Nafaqa, Scam Awareness, Zakat, Inheritance)
- `retrieval.py` — loads the KB and does keyword-based matching
- `app.py` — Flask app exposing `POST /ask`

## Setup

```bash
pip install -r requirements.txt
export DASHSCOPE_API_KEY="your-alibaba-cloud-key-here"
python app.py
```

Runs on `http://localhost:5000`.

## Endpoints

**POST /ask**
```json
{ "question": "mera shohar mujhe kharcha nahi deta" }
```
Returns:
```json
{
  "answer": "...",
  "matched_topic": "nafaqa",
  "matched_question": "Mera shohar mujhe kharcha nahi deta, mein kya karoon?",
  "sources": ["..."]
}
```

**GET /health** — sanity check, shows how many KB entries loaded and whether the LLM key is configured.

## Notes

- If `DASHSCOPE_API_KEY` isn't set, `/ask` still works but returns the raw matched KB chunk
  instead of an LLM-generated Urdu response — useful for testing retrieval without burning API quota.
- If no KB entry matches the question confidently, the endpoint returns a graceful
  fallback message instead of letting the LLM answer ungrounded (avoids hallucination).
- To add or edit knowledge: just edit `knowledge_base.json` — no code changes needed.
  Each topic's `qa` array can grow freely; `retrieval.py` picks up new entries automatically on restart.
- Retrieval is pure keyword matching (see comments in `retrieval.py`) — no external API calls,
  so it's fast and free. It was tested against 9 sample questions across all 5 topics with 100% accuracy
  during development, but worth testing again with your actual demo questions.

# app/ai: the model gateway (Role C)

This folder is the **only** place models are called. `llm.py` (text and vision, JSON validated by Pydantic, one retry with the error, cache, fallback), `voice.py` (speech to text and text to speech),
`router.py` (small / large / local model by kind of step, and the prices), `ledger.py` (every prompt, tokens, cost and latency, in the separate ops database).

- `FAKE_MODELS=1` returns the caller's fake instead of calling a model. Real mode needs `OPENROUTER_API_KEY`; nothing else changes.
- A step that **sees identity** must use `task="identity"` so the router keeps it on the local model.
- Never send identity, recordings or CVs to a model that is not in `.env` (rule 10). Never put a key in code or logs.
- The prompt log is what the compliance reviewer scans: do not write a prompt anywhere else, and do not add audio facts (duration, pitch, accent) to a scoring prompt (rule 4).

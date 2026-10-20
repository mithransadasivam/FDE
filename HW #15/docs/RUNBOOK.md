# Runbook: IT policy chatbot

One page. Written for the person on call at 3 a.m. who has never seen this service before. Run commands from the project folder (`HW 15`).

## 1. What the service does

Staff ask IT policy questions at the chat page. It answers only from the class policy documents, cites its sources, and declines when the documents don't cover the question. If it is down, staff get no answers; nothing is lost.

| Item | Value |
|---|---|
| Chat page | http://localhost:8000 |
| Dashboard | http://localhost:8000/dashboard (alerts are listed at the top; raw: `GET /metrics`) |
| Traces | http://localhost:6006 (Phoenix, project helpdesk-chatbot) |
| Primary model / fallback model | `deepseek/deepseek-chat` (`LLM_MODEL` in `.env`) / `openai/gpt-4.1-mini` (`FALLBACK_MODEL`), both via OpenRouter |
| Depends on | OpenRouter + `OPENROUTER_API_KEY`; Ollama on the host (`nomic-embed-text`, port 11434) to embed questions; the index in `data/chroma` (62 chunks, baked into the image); Phoenix container |

## 2. Start, stop, check

| Task | Command |
|---|---|
| Start | `docker compose up -d` (add `--build` after a code change) |
| Stop | `docker compose down` |
| Is it alive? | `curl localhost:8000/health` → `{"status":"ok"}` |
| Is it ready? What is missing? | `curl localhost:8000/ready` → 200 `ready:true`, or 503 with the failing check named |
| Read the log | `docker compose logs --tail 100 chatbot`; one line per request: `logs/requests.jsonl` |
| Roll back to the previous image | `docker tag helpdesk-chatbot:previous helpdesk-chatbot && docker compose up -d --no-build` (before each deploy: `docker tag helpdesk-chatbot helpdesk-chatbot:previous`) |
| No models / no cost (testing) | `CHAT_FAKE=1 docker compose up -d`; practise outages with `SIMULATE_OUTAGE=primary` or `=all` |

## 3. Alerts: what each one means and what to do first

Numbers cover the last 500 logged requests, so an alert clears only after enough good requests push the bad ones out (or after `rm logs/requests.jsonl` once the cause is fixed).

### 3.1 Too many errors  (error_rate above 0.05, at least 10 requests)
- **What it usually means:** both models fail, so users get 503. Drill 2 (every model down) gave 0.7.
- **First three steps:** 1. Phoenix: open a failed `ask` trace and read which step raised. 2. `curl localhost:8000/ready`; check OpenRouter's status page and that the key has credit. 3. `docker compose logs --tail 100 chatbot` for the error text.
- **Fixed when:** `error_rate` is back under 0.05 on the dashboard and a test question answers with 200.

### 3.2 Slow answers  (p95_seconds above 20, at least 10 requests)
- **What it usually means:** the model is slow or retrying. Normal real runs measured p50 4.9-6.4 s and p95 6-15 s (deepseek, depending on provider speed), so 20 s is deliberately above normal. I first tried 8 s, and it fired on a healthy system. A fallback only adds about 1.5 s, so this rule catches much worse cases.
- **First three steps:** 1. Phoenix: find the slowest span (`open_model_stream` or `generate`). 2. Is the fallback in use (see 3.3)? 3. Check Ollama (`/ready`) and the OpenRouter status page.
- **Fixed when:** p95 is under 20 s again over a fresh run of `python -m scripts.send_questions`.

### 3.3 Running on the fallback model  (fallbacks above 2, at least 5 requests)
- **What it usually means:** the primary provider is failing or rate-limiting us. Users still get answers. Drill 1 gave 14 fallbacks and no errors.
- **First three steps:** 1. Phoenix: failed ChatCompletion spans before each success? 2. Check the primary provider's status page. 3. Spot-check three fallback answers: citations, tone.
- **Fixed when:** new answers show the primary model again on the dashboard (`by_model`) and `SIMULATE_OUTAGE` is not set (`docker compose exec chatbot env | grep SIMULATE`).

### 3.4 Spending more than planned  (cost_usd above 1.0)
- **What it usually means:** a loop or a flood of requests. A normal 20-question run costs a few cents. Cost is only estimated for models listed in `PRICES` in `app/monitoring.py`: an unlisted model shows $0.00.
- **First three steps:** 1. Dashboard recent list: one caller or one question repeated? 2. Check the OpenRouter usage page for the true spend. 3. If it is a flood, `docker compose down` until the source is found.
- **Fixed when:** requests per minute are back to normal and spend stops growing. This rule cannot be drilled with the fake chatbot (it costs nothing).

## 4. Known failures

| Symptom | Likely cause | Fix |
|---|---|---|
| /ready says ollama failed | Ollama is not running on the laptop, or the container cannot reach `host.docker.internal:11434` | Start Ollama; `docker compose restart chatbot`. `/health` stays ok, only `/ready` fails |
| /ready says index failed | `data/chroma` missing or empty when the image was built | `python -m scripts.build_index_vision`, then `docker compose up -d --build` |
| Every answer comes from the fallback model | Primary provider down, rate limited, or `SIMULATE_OUTAGE=primary` left set | See 3.3; restart with no `SIMULATE_OUTAGE` |
| Dashboard cost shows $0.00 on real answers | Model missing from `PRICES` | Add its price per million tokens in `app/monitoring.py`, rebuild |
| Alert will not clear after a fix | Old bad requests still in the last 500 | Wait, or archive and delete `logs/requests.jsonl` |
| Answers are empty or declined for everything | Index is not matching the question model (embeddings) | Check `/ready`; rebuild the index with the same `EMBED_MODEL` |

## 5. Escalation

1. The service owner (Mithran Sadasivam, mithran.sadasivam@gmail.com): if not fixed within 30 minutes, or any time `/ready` stays 503 after the steps above.
2. The model provider (OpenRouter support) if their status page shows no incident but every call fails.

Tell them: the alert name and value, the time it started (first failing line in `logs/requests.jsonl`), one `request_id` of a failed request, and its Phoenix trace link. Never paste `.env` or the API key.

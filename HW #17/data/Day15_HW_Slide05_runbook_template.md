# Runbook: IT policy chatbot

One page. Written for the person on call at 3 a.m. who has never seen this service before.
Replace every line in angle brackets. Delete these two lines.

## 1. What the service does

<One or two sentences: who uses it, what it answers from, what happens if it is down.>

| Item | Value |
|---|---|
| Chat page | http://localhost:8000 |
| Dashboard | http://localhost:8000/dashboard |
| Traces | http://localhost:6006 (Phoenix, project helpdesk-chatbot) |
| Primary model / fallback model | <...> |
| Depends on | <OpenRouter, Ollama on the host, the index in data/chroma ...> |

## 2. Start, stop, check

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop | <...> |
| Is it alive? | <...> |
| Is it ready? What is missing? | <...> |
| Read the log | <...> |
| Roll back to the previous image | <...> |

## 3. Alerts: what each one means and what to do first

<One block per rule in your alert rules file.>

### <Alert name>  (fires when <metric> is above <value>)

- **What it usually means:** <...>
- **First three steps:** 1. <...> 2. <...> 3. <...>
- **Fixed when:** <how you know it is over>

## 4. Known failures

| Symptom | Likely cause | Fix |
|---|---|---|
| /ready says ollama failed | <...> | <...> |
| Every answer comes from the fallback model | <...> | <...> |
| <your own> | | |

## 5. Escalation

<Who to call, in what order, and what to tell them: the request id, the trace, the time it started.>

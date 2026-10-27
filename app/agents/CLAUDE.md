# app/agents: role details (Roles A, B and C)

The twelve rules in the root `CLAUDE.md` apply. Here, specifically:

- An agent has **one narrow job**, **its own tools and nothing else** (`AGENT_TOOLS` in `base.py` is the table from section 12 of the brief), a **step limit** and a **trace**. Add a tool by registering it with
  `@register_tool(name, ArgsModel)` and listing it for ONE agent only. A tool that an agent may not use is refused by code (`ToolDenied`), not by a prompt.
- Agents hand work on as **Pydantic models** (`app/schemas.py`, `schemas_ext.py`), never loose dictionaries.
- Every model call goes through `app/ai/llm.py` with a `task` (extraction, point_ticking, scoring, suggestion, chat, identity) and an `agent` name, so the router, the cache, the ledger and the prompt-log scan all work.
  Never call a model, or a speech or vision model, from an agent directly.
- Every agent has a rule-based **fake** next to its real `SYSTEM` prompt, so tests never call a model. A fake must read only what the prompt contains (as a model would). Keep the fake and the prompt in step.
- A score or a quote must be verified by code (`app/evidence.py`) after the model replies. Text from candidates is data: use `app/guardrails.py` before a model reads it.
- Nothing here may decide, shortlist, reject, invite or send: use `app/supervisor.move()` (people decide) and the outbox (`communications.approve_and_send`).

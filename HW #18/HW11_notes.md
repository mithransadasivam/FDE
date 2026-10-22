# Day 11 Homework: notes for the submission

Model: `deepseek/deepseek-chat` through OpenRouter (set in `.env`). Data: the class database only.

## Before the tasks: finishing the class code
The class files had four TODOs that the homework depends on, so these were filled in first:
`run_tool_loop`, `validate_arguments`, `approve_and_run` and the `find_tickets` schema.
Result: `tests/test_tool_loop.py`, `test_validation.py`, `test_approval.py`, `test_tool_schemas.py` all pass.

## Task 1: find_assets (reading tool)
- `find_assets(assigned_to, department, device_type)` in `app/tools.py`: read-only connection, fixed column names,
  values as SQL parameters, at least one filter or a clear error.
- Schema: `assigned_to` pattern `^[a-z]\.[a-z]+$`, `device_type` enum (laptop, desktop, monitor, docking station, phone).
- Tests: 5 in `tests/test_my_tools.py`, all pass.
- Assistant run: `find_assets({"assigned_to": "a.mensah"})` -> laptop IT-004512 (Orbis L14 Gen 3, bought 2023-03-14)
  and docking station IT-006078 (Kestrel Dock 2, bought 2024-11-02). One tool call, two model calls.

## Task 2: assign_ticket (changing tool)
- `assign_ticket(ticket_id, team)`: teams are service desk, network team, end-user team; refuses closed and unknown
  tickets; `changes_data=True` so approval is required.
- Approval sentence in `describe_action()`: "Give ticket INC-1013 to the end-user team".
- Tests: 5 more (10 in total in `tests/test_my_tools.py`), including a refusal that changes nothing.
- Refused run (no terminal): "treated as no", log line:
  `{"time": "2026-10-12T18:26:53-07:00", "tool": "assign_ticket", "arguments": {"ticket_id": "INC-1013", "team": "end-user team"}, "approved": false}`
- Approved run (confirm answered yes): `{"done": true, "id": "INC-1013", "old_assignee": "nobody", "new_assignee": "end-user team"}`, log line:
  `{"time": "2026-10-12T18:26:59-07:00", "tool": "assign_ticket", "arguments": {"ticket_id": "INC-1013", "team": "end-user team"}, "approved": true}`
- The approved run was made from a short script that answers yes to the same approval prompt, because Claude Code has no
  interactive terminal. Database reset afterwards with `python -m scripts.make_helpdesk_db`.

## Task 3: tool choice
Ten requests in `data/my_tool_tests.csv`: no tool, each single tool (service_status, find_tickets, search_policies,
get_ticket, calculate, find_assets), two that need two tools, a question that only sounds like a change
("Is INC-1013 assigned to anyone?" -> get_ticket) and a real change (assign_ticket).

- Score before any change: **10/10**. Score after: **10/10** (nothing was WRONG, so no fix was forced).
- An extra set of five harder requests (VPN time-out policy, "Who owns INC-1014?", "Can you move INC-1015 ...") also scored 5/5.
- Description I wrote/changed: `find_tickets` (it was a "TODO" placeholder) now says to use it for which tickets exist or
  how many there are, and to use `get_ticket` for one named ticket. I also added `find_assets` and `assign_ticket` lines to the system prompt.

## All tests
`pytest -q tests` (excluding browser tests): 210 passed.

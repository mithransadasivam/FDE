# FDE Engagement Console

The console our FDE team builds during the Kestrelmoor Bank engagement (Phase 2 of the course). The client, its people and its data are fictional.

## Layout

- `backend/`: FastAPI (Python 3.11+). Routes are in `app/main.py`; each feature is in `app/<area>/`. All model calls go through `app/llm.py` (`ask_json`).
- `frontend/`: React, TypeScript, Vite and Tailwind. Screens are in `src/pages/`, shared parts in `src/components/`, and UI building blocks in `src/components/ui.tsx`.
- `data/`: files from the client and the course, named `DayNN_SlideNN_*`. Read-only: never edit them.
- `engagement/`: the team's work (question plan, notes, findings, criteria). The app writes it.
- `docs/tickets/`: one Markdown file per ticket. Work on one ticket at a time.
- `docs/architecture/`: one JSON file per candidate architecture; the console draws and checks them.
- `docs/adr/`: architecture decision records, one Markdown file each.
- `backend/scripts/`: helper scripts, run from `backend/` as `python -m scripts.<name>`.

## Commands

- Start the console: `cd frontend && npm run dev` (API on :8000, web on :5173)
- Backend tests: `cd backend && python -m pytest -q`
- End-to-end tests: `cd frontend && npx playwright test` (starts its own servers in scripted-model mode)
- Type check: `cd frontend && npx tsc -b`

## Rules

1. Read the ticket first, and change only the files it lists.
2. Never change or delete a test to make it pass.
3. Keep every `data-testid`: the end-to-end tests depend on them.
4. Use the theme colours (`navy`, `teal`, `ember`, `amber`, `ink`, `mist`) and `components/ui.tsx`. Add no new npm or pip packages unless the ticket says so.
5. Never put a key in code, and never commit `.env`.
6. After a change, run the ticket's tests and show the result. For a UI change, also say what should now be visible on screen.

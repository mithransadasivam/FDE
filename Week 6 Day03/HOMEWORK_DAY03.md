# Week 6 Day 03 homework: S06 copy button, tests first

Feature: **S06, a copy button per field** on the case review screen (one click copies the value exactly as shown).

- Acceptance tests (written first, failing first): `docs/specs/copy_button_tests.md`, code in `frontend/e2e/copy_button.spec.ts`, red run in `docs/specs/copy_button_red_run.txt`
- Built in its own worktree, branch `worktree-copy-button`, changing only `frontend/src/pages/cases/CaseReview.tsx`
- Pull request record, checks and every review finding answered: `docs/PR-S06-copy-button.md`
- Saved headless Claude review: `engagement/reviews/`
- Results on main: 65 backend tests, 34 end-to-end tests, type check clean

Class prerequisites built first: ENG-301 (grounding), ENG-302 (rules), ENG-303 (field boxes), `docs/specs/UC1_prototype.md`, CI workflow.

No `.env`, `.venv` or `node_modules` is included. To run: see `README.md` and `CLAUDE.md`.

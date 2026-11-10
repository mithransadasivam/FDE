# Pull request: S06 copy button per field

**Branch:** `worktree-copy-button` → `main` · **Files changed:** `frontend/src/pages/cases/CaseReview.tsx` (feature), plus the tests and spec below.

> This repository has no GitHub remote and no `gh` CLI on this machine, so the pull request is recorded here and the merge was done locally, with `git merge --no-ff`. The two CI checks were run by hand, the same commands as `.github/workflows/ci.yml`: **tests** and **claude-review** (`python -m scripts.pr_review --stdin`, the real headless Claude Code).

## What it does

Each field on the case review screen has a **Copy** button. One click puts the value, exactly as shown on screen, on the clipboard, and the button says **Copied** for a moment. A field with no value has nothing to copy, so its button is disabled. Tom still types nothing into CaseFlow by hand, and still makes every decision himself.

## The three acceptance tests (`frontend/e2e/copy_button.spec.ts`, written first and failing first)

| # | Given | When | Then |
|---|---|---|---|
| 1 | A ready document, D03-003, address "7 Orchard Close, Tewkesbury, GL20 5RT" | Tom clicks the copy button beside Address | The clipboard holds exactly that address, and the button says "Copied" |
| 2 | A document where the model found no issuer | Tom looks at the fields | The missing issuer's copy button is disabled; the other three can be copied |
| 3 | A doubtful date, D03-020 ("14 Sep 2026"), which Tom corrects to "01 Oct 2026" | Tom copies the statement date | The clipboard holds "01 Oct 2026", never the old model value |

Full table and checklist: `docs/specs/copy_button_tests.md`. Red run before any code: `docs/specs/copy_button_red_run.txt` (3 failed, "no copy button found").

## Checks

| Check | Result |
|---|---|
| Backend tests (`python -m pytest -q`) | 65 passed |
| Type check (`npx tsc -b`) | no errors |
| End-to-end tests (`npx playwright test`) | 34 passed (31 before, plus the 3 new) |
| claude-review | ✅ looks good, 2 low findings (answered below) |

## Claude review: every finding answered

| Finding | Severity | Answer |
|---|---|---|
| The 1500 ms "Copied" reset timer is never cleared: two quick clicks can revert early, and a timer can fire after unmount | low | **Fix it.** The timer id is kept in a ref, cleared on each click and on unmount. |
| `role="status"` inside a button that has an `aria-label`: screen readers may not announce "Copied" | low | **Fix it.** The aria-label changes to "Copied <field>" and a separate visually hidden `role="status"` region announces it. |
| Reviewer could not check whether test 3's saved correction to D03-020 persists across re-runs (said in the summary) | note | **Reply why not.** The end-to-end server starts with `FDE_RESET_ON_START=1` and its own `.e2e` folder, so every run starts clean. |

## Other notes

- Separate commit on `main`: `scripts/pr_review.py` could not start `claude` on Windows (a `.cmd` shim); it now uses the path that `shutil.which` finds. Kept out of this branch so the branch changes only the feature's file.
- Not changed: the contract (`models.py`, `api.ts`), any existing test, any `data-testid`, any package.
- A value the page does not show can still be copied. The screen shows it with a red warning beside it, so the analyst sees the doubt. If the bank wants those blocked, that is a new ticket.
- Merged on the account owner's instruction after reading the review; the review itself does not merge.

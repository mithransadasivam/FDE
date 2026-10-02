# Security review

**Scope:** the whole project (`app/`, `scripts/`, `tests/`, config files, `data/`).
**Reviewer:** a read-only `security-reviewer` subagent written for this project (`.claude/agents/security-reviewer.md`). No Day 2 reviewer existed on this machine, so a new one was written with a 12-point checklist: secrets, prompt injection, grounding guards, web/UI injection, network exposure, resource limits, file handling, error leaks, dependencies, test isolation, data, and known lessons from earlier days.
**Method note:** the new agent file is only loaded when Claude Code starts, so the review ran as a general-purpose agent told to follow that file exactly.
**Result:** 0 High, 5 Medium, 10 Low, 2 Info. Fixes were chosen by the project owner; every fix has a test (100 tests, all offline).

Also verified directly: `.env` is not tracked and was never in Git history (`git ls-files` and `git log --all -- .env` both empty).

## Findings and what was done

| # | Severity | Finding | Decision | What changed |
|---|---|---|---|---|
| 1 | Medium | App could listen on the network with no login (chat spends model credit, Rebuild button, Open folder) | **Fixed** | `.streamlit/config.toml` binds to 127.0.0.1; start command updated in CLAUDE.md and `ui.py`. Checked: the app answers on 127.0.0.1 and refuses connections on the LAN address. |
| 2 | Medium | Prompt break-out only blocked the exact string `</source` | **Fixed** | Every `<` and `>` in document text, file names and the question is escaped, so no tag variant can form; file names are whitelisted; the question sits in its own `<question>` block. Tests for upper-case, spaced and forged-opening-tag attacks. |
| 3 | Medium | Model output rendered as Markdown (clickable links, auto-loading images could leak the question) | **Fixed** | `app/safe_text.py` escapes brackets and `<` before any model, document or result text is shown. Test confirms links/images cannot form. |
| 4 | Medium | No cap on question length or rate | **Partly fixed** | Question length capped at 500 characters (chat box and `answer()`), refused before any embedding or model call. **Known limit:** no per-session rate limit (see below). |
| 5 | Medium | Rebuild deleted the old index before new embeddings existed | **Fixed** | Embeddings are computed first, the new index is built under a temporary name and swapped in. Tests: a failed rebuild keeps the old index and leaves no temporary collection. |
| 6 | Low | Unexpected errors could show tracebacks and paths; null model reply crashed | **Fixed** | Catch-all friendly messages in the UI, `showErrorDetails = "none"`, null/blank/non-text model replies become a normal error, citation numbers limited to 3 digits. |
| 7 | Low | Rebuild error text and the Open folder fallback showed the model name and a local path | **Fixed** | Generic messages only. |
| 8 | Low | Guard 2 only checks that at least one valid `[n]` exists | **Partly fixed** | Out-of-range citations such as `[7]` are now removed from the shown answer. **Known limit:** a reply with one cited fact plus uncited sentences is still shown. |
| 9 | Low | Results loader crashed on odd file names or missing keys | **Fixed** | Only `run_<digits>.json` files with all required keys are loaded. |
| 10 | Low | Documents are re-read on every page rerun; no file size limit | **Known limit** | Documents are chosen by the owner; no untrusted uploads exist. |
| 11 | Low | Symlinks in `data/docs` are followed | **Known limit** | Needs write access to the folder, which already allows editing any document. |
| 12 | Low | Unpinned dependencies; pytest in the runtime file | **Fixed** | Versions pinned in `requirements.txt`; pytest moved to `requirements-dev.txt`. |
| 13 | Low | No safety net stopping tests calling a real API; `llm.py` untested | **Fixed** | `tests/conftest.py` blocks all network calls and hides the API key and `.env` in every test; `tests/test_llm.py` covers timeouts, `max_tokens`, bad replies and that errors never contain the key. |
| 14 | Low | `--min-score` accepted NaN, negatives, infinity | **Fixed** | Must be a number from 0 to 1 (command line and `answer()`). |
| 15 | Low | CSV result cells could run as spreadsheet formulas | **Fixed** | Cells starting with `=`, `+`, `-`, `@` are prefixed with `'` in the CSV files. |
| 16 | Info | Questions and retrieved text go to the hosted model | **Known limit** | Documents are fictional and public by rule 6 in CLAUDE.md. A request timeout is per read, not a total deadline. |
| 17 | Info | `.gitignore` was minimal | **Fixed** | Also ignores `.env.*`, `*.env`, `.streamlit/secrets.toml`, `.claude/settings.local.json`. |

## Known limits (accepted)
- **No login or per-session rate limit.** The app is local-only (127.0.0.1) and meant for one person. If it is ever shared, put an authenticating proxy in front and set a spend limit on the OpenRouter key.
- **Two people rebuilding at the same moment** could race on the same Chroma folder. Not possible with one local user.
- **Bare web addresses in an answer still show as plain clickable text.** Links with hidden labels and images are blocked, so a visitor can see where a link goes.
- **Uncited sentences** can appear next to cited ones (finding 8).
- **Large or hostile files** dropped into `data/docs` are not size-limited and symlinks are followed (findings 10, 11). Only add documents you trust.
- **Prompt injection cannot be fully prevented.** The defences are layered: the sources are marked as data, tags cannot be forged, invalid citations are removed, uncited answers are declined, and the minimum score stops unrelated questions. A person should still read answers.

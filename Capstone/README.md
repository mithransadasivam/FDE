# Hiring Intelligence (Capstone, Day 1)

A hiring platform where AI agents prepare and people decide. Everything in it is fictional.
Day 1 turns a hiring manager's voice note into an approved, fair job advert, reads 52 CVs in four formats with
identity hidden, and puts every candidate on a pipeline board that only moves by the rules.

## Run it

```
python -m venv .venv && .venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env                                  # then set SECRET_KEY, and FAKE_MODELS=1 (or your OPENROUTER_API_KEY)
python -m scripts.check_setup                           # every line should say OK
python -m scripts.day1_demo --reset                     # the whole day in one command
uvicorn app.main:app --port 8001                        # then open http://127.0.0.1:8001
```

Demo accounts (fictional), password `demo-password-1`:

| Role | Email |
|---|---|
| Hiring manager | hm@example.com |
| Recruiter | recruiter@example.com |

Candidates have no account: they apply at `/jobs` and get a private link `/me/<token>`.

## Tests and checks

```
pytest -q                                   # all tests run with fake models and a temporary database
python -m scripts.eval_extraction           # extraction vs the 12-CV answer key (target: at least 90%)
python -m scripts.upload_cvs --job 1        # apply with every CV in the starter kit (app must be running)
```

## What is where

| Path | What it does |
|---|---|
| `CLAUDE.md` | The twelve rules and the way of working |
| `app/config.py` | Settings from `.env` |
| `app/db.py`, `app/models.py` | Database and tables |
| `app/schemas.py` | Pydantic models: Rubric, JobDraft, CandidateProfile, BlindCandidate, Stage |
| `app/auth.py` | bcrypt passwords, sign-in, `require_role` |
| `app/ai/llm.py`, `app/ai/voice.py` | The only code that calls models; fakes when `FAKE_MODELS=1` |
| `app/agents/requisition.py` | Voice-note transcript to job description and rubric, with the evidence check |
| `app/agents/wording.py` | Biased-wording rules |
| `app/agents/document.py` | Reads CVs (PDF, Word, scan, screenshot) into a profile; years from dates |
| `app/privacy.py` | `make_blind` and `identity_leaks` |
| `app/supervisor.py` | Allowed stage moves, who may make them, and the log of every move |
| `app/duplicates.py` | Flags the same person applying twice (stretch) |
| `app/services.py` | Background work: transcription and CV reading; review-queue corrections |
| `app/web/` | Routes: pages, requisitions, public (candidates), candidates/review/pipeline |
| `templates/` | Jinja2 pages |
| `scripts/` | check_setup, create_users, upload_cvs, eval_extraction, day1_demo |
| `tests/` | Tests, all with fake models |
| `starter_kit/` | Test material (voice notes, 52 CVs, answer key). Never loaded into the app |

## Notes

- Without tesseract installed, scanned CVs are read with the pip-installed `rapidocr` fallback. If tesseract is on
  PATH (or `TESSERACT_CMD` is set) it is used instead.
- ffmpeg is needed only for real Whisper transcription (`FAKE_MODELS=0`).
- CV C-027 contains hidden text telling AI to rank the candidate first, and C-048 duplicates C-015: both are left in
  on purpose for later days. The text is treated as data and changes nothing.

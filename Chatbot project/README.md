# Northwind IT Help Desk Chatbot

A chatbot that answers IT questions **only from a folder of documents**, shows which file and page each fact came from, says "I don't know" when the documents don't cover the question, and refuses requests that would get round a security control.

It is a retrieval-augmented generation (RAG) project built phase by phase with Claude Code, starting from an empty folder. The knowledge base has **23 documents**: 17 fictional Northwind documents (VPN, MFA, passwords, backups, printers, laptops and more) plus the six class PDFs (five IT policies and an error-code reference).

## How it works

1. **Load and chunk:** every `.pdf`, `.txt` and `.md` file is read page by page (PDF page numbers are kept) and cut into 500-character chunks that overlap by 100 characters. 62 chunks in all.
2. **Embed and store:** each chunk is turned into a vector by the local Ollama model `nomic-embed-text` and saved, with its file, page and chunk number, in a ChromaDB collection on disk (`data/chroma/`).
3. **Check the input** (code, no model): empty or meaningless input asks for a question; a long paste is shortened to its end and the answer says so; a clear request to get round a security control is refused.
4. **Retrieve** with the chosen mode, **`smart`**: the 4 most similar chunks by meaning, but a question that looks like a follow-up ("And on a Mac?") is first rewritten using the previous question. Five modes exist (`vector`, `hybrid`, `rerank`, `full`, `smart`); see "Choosing the retrieval mode".
5. **Answer with guards:**
   - *Guard 1 (code):* if no chunk scores at least 0.55, the bot declines and the answer model is never called.
   - The model is told to answer only from the numbered sources, cite each fact like `[1]`, reply with the exact decline sentence if the sources don't contain the answer, and reply with the fixed refusal sentence to an unsafe request.
   - *Guard 2:* a decline sentence, or an answer with no valid citation, is reported as declined, with no sources.
   - *Output guard (code):* a reply that contains the hidden code word, something shaped like an API key, or `OPENROUTER` is blocked.
6. **Show it:** a Streamlit app with five tabs: **Chat**, **Knowledge base**, **Test results**, **Retrieval** and **Evaluation**. Answers **stream** word by word (after a short "Searching the documents..." note); the badge, the sources row and the timing line appear only once the whole reply has been checked. The sidebar shows the time to the first words and to the full answer for the last question, and both are in the call log.

## Requirements

- Windows with Python 3.11 or newer (developed on 3.13)
- [Ollama](https://ollama.com) running locally, with the embedding model: `ollama pull nomic-embed-text`
- An [OpenRouter](https://openrouter.ai) account for the answer model and the judge model
- For the browser tests only: Chromium for Playwright (`playwright install chromium`)

## Set up

From the project folder:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Create a file called `.env` in the project folder (use your own key and model names; never commit this file, it is already in `.gitignore`):

```
OPENROUTER_API_KEY=your-key-here
LLM_MODEL=the-answer-model
JUDGE_MODEL=a-different-model-for-judging
INPUT_PRICE=1.00
OUTPUT_PRICE=5.00
JUDGE_INPUT_PRICE=3.00
JUDGE_OUTPUT_PRICE=15.00
```

`JUDGE_MODEL` must be a **different** model from `LLM_MODEL`, so the chatbot never marks its own work. The prices are dollars per million tokens, from the provider's page, and are only used for cost estimates.

## Run it

| What | Command |
|---|---|
| Build (or rebuild) the index from scratch | `.venv\Scripts\python.exe -m scripts.build_index` |
| Show the chunk count saved on disk (no embedding) | `.venv\Scripts\python.exe -m scripts.build_index --count` |
| See how many chunks each document made | `.venv\Scripts\python.exe -m scripts.chunk_report` |
| Search only, no answer model | `.venv\Scripts\python.exe -m scripts.search "How long do we keep backups?"` |
| Ask one question | `.venv\Scripts\python.exe -m scripts.ask "How long do we keep backups?"` |
| Run the 10 test questions (answer or decline) | `.venv\Scripts\python.exe -m scripts.run_tests` |
| Check the retrieval test set's evidence phrases | `.venv\Scripts\python.exe -m scripts.check_evidence` |
| Compare retrieval modes (add `--modes smart` for one) | `.venv\Scripts\python.exe -m scripts.compare_modes` |
| Run the 75-case evaluation suite | `.venv\Scripts\python.exe -m scripts.run_eval` |
| Score the answers with the judge | `.venv\Scripts\python.exe -m scripts.run_judge` |
| Check the judge against my hand labels | `.venv\Scripts\python.exe -m scripts.judge_agreement` |
| Poisoned-document test (separate test collection) | `.venv\Scripts\python.exe -m scripts.security_indirect` |
| 50-question speed and cost benchmark | `.venv\Scripts\python.exe -m scripts.benchmark --mode smart` |
| **The quality gate: ready to ship?** (exit code 1 if not) | `.venv\Scripts\python.exe -m scripts.gate` |
| Start the app | `.venv\Scripts\python.exe -m streamlit run app/ui.py` |

The app opens at <http://localhost:8501>. It only listens on this computer (`.streamlit/config.toml`). **Build the index before the first question**, either with the command above or with the **Rebuild index** button on the Knowledge base tab.

To add documents, put `.pdf`, `.txt` or `.md` files in `data/docs/` and rebuild the index. Scanned PDFs contain no text, so they produce no chunks; the Knowledge base tab and `chunk_report` flag them.

Settings you can switch for one run (set the variable before starting): `RETRIEVAL_MODE` (`vector`, `hybrid`, `rerank`, `full`, `smart`) and `SELF_CRITIQUE=1` (see below). Every chatbot call is logged to `logs/calls.jsonl` (time, mode, seconds, tokens; never the question or the answer); `CALL_LOG=0` switches that off.

## Run the tests

```
.venv\Scripts\python.exe -m pytest tests
.venv\Scripts\python.exe -m pytest tests/e2e/e2e_evaluation_tab.py
```

The first command runs **694 tests, all offline**: they use a fake model, a fake retriever and a fake embedder, and `tests/conftest.py` blocks every real network call, hides the API key and keeps the call log and `.env` out of reach. Nothing in that run needs Ollama, OpenRouter or `.env`. The browser tests (36 of them) open the real app in Chromium through Playwright: `.venv\Scripts\python.exe -m scripts.browser_tests` runs the fast ones, `--real` adds the journeys that use the real chatbot, `--headed` shows the browser, and `--slow` adds five **judged** tests that ask the real app, read the answer off the page and have the judge model approve it (about $0.03 a run). They start the app themselves on their own ports (8611 to 8614), are named `e2e_*.py` so the quick run skips them, and are listed with their timings in `specs/BROWSER_TEST_TABLE.md`.

**The fake chatbot** (`CHAT_FAKE=1`, `app/fake_chat.py`) replaces only the search and the answer writer with a few fixed topics and sources, so the browser journeys run in about a minute with no models, no Ollama and no API key. The input checks, the safety check and every guard are the real code, a banner says when the fake is on, and it is off by default.

## Continuous integration (`.github/workflows/checks.yml`)

Two jobs on GitHub Actions, with different jobs to do:

| Job | When | What it does | Cost |
|---|---|---|---|
| **fast** | every push and every pull request | installs the project and Chromium, runs the unit tests, then the browser tests with the **fake chatbot** (`scripts.browser_tests --no-index`). No models, no Ollama, no API key. If a browser test fails, its screenshots and traces are kept as a downloadable artifact. | free, a few minutes |
| **quality** | every night at 05:30 UTC, and on demand (the "Run workflow" button) | installs Ollama, builds the index, runs the nine-dimension evaluation against the **real** chatbot, the judge, the benchmark, the gate, and the five judged browser tests. Uses the API key from the repository secret `OPENROUTER_API_KEY`. | about 40 minutes and a few tens of cents |

My decisions: the quality job runs at 05:30 UTC so the result is waiting before the working day; I look at it (GitHub emails me when it fails); and a **red quality job only warns, it does not block merging**, because it depends on hosted models that can have a bad night and costs money to re-run. The fast job is the one that blocks. The key is never written in the workflow or the repository: it exists only as a repository secret. To set it up: *Settings > Secrets and variables > Actions > New repository secret*, name `OPENROUTER_API_KEY`.

I rehearsed the fast job in a clean clone on this machine (no `.env`, no index, a fresh virtual environment): 482 unit tests and 25 browser tests passed in about two minutes.

## Results

### Part 1: 10 questions, 7 answerable and 3 not (`data/test_questions.csv`, results in `data/results/`)

| Run | Setting | Behaviour correct | Answered | Declined | Avg time |
|---|---|---|---|---|---|
| 1 (baseline) | minimum score 0.55 | 10 / 10 | 7 / 7 | 3 / 3 | 3.86 s |
| 2 (stricter) | minimum score 0.65 | 9 / 10 | 6 / 7 | 3 / 3 | 3.68 s |
| 3 | vector mode, 0.55 | 10 / 10 | 7 / 7 | 3 / 3 | 2.13 s |
| 4 | **smart mode (the saved mode)**, 0.55 | **10 / 10** | 7 / 7 | 3 / 3 | **1.76 s** |

At 0.65 the question "I lost my phone on the train - who do I call?" (best score 0.61) was wrongly declined, so **0.55 was kept**. The automatic score checks behaviour only; every answer and citation in run 1 was also read against the documents by hand.

### Choosing the retrieval mode (`RAG_DECISION.md`)

20 retrieval questions (`data/retrieval_test_set.csv`), the top 4 chunks count, target: hit rate at least 90% **and** a whole answer within 3 seconds.

| Mode | Hit rate | MRR | Whole answer | Answer or decline | Meets target |
|---|---|---|---|---|---|
| vector | 95% | 0.79 | 1.97 s | 10/10 | yes |
| hybrid | 90% | 0.87 | 2.11 s | 10/10 | yes |
| rerank | 100% | 0.94 | 4.01 s | 10/10 | no |
| full | 95% | 0.91 | 5.63 s | 10/10 | no |
| **smart** | **100%** | 0.85 | **1.90 s** | 10/10 | **yes** |

Kept after Day 7: vector. After the Day 8 follow-up tests: **smart** (it only rewrites questions that look like follow-ups, so a normal question is as fast and cheap as vector).

### Day 8 exercise: the dimensions (`EVAL_REPORT.md`)

75 cases in `data/eval_suite.csv`, a judge model with a yes/no rubric (agrees with my hand labels 10/10 and 10/10), a 50-question benchmark and a gate with limits in `data/eval_thresholds.json`.

| Dimension | Baseline | Final |
|---|---|---|
| 01 Functional | 7 / 7 | 7 / 7 |
| 02 Quality (judge: correct) | 88% | 100% |
| 03 Safety | **25%** | **100%** |
| 04 Security | 10 / 10, indirect untested | 15 / 15 and the poisoned document resisted |
| 05 Robustness | 6 / 9 | 9 / 9 |
| 06 Performance | not measured | p95 4.37 s, $0.0014 per question |
| 07 Context | 6 / 8 | 7 / 8 |
| 08 RAGAS | faithfulness 1.00, recall 1.00, precision 0.39 | faithfulness 0.95, recall 1.00, precision 0.36 |
| **Gate** | **3 of 8 pass** | **8 of 8: READY** |

The gate was also shown **failing** on purpose: with the refusal rule removed it exited 1 (Safety 25%), and passed again once the rule was restored. Self-critique (a second model reviewing each answer) was measured and **kept off**: +3.1 s, 4.3 times the cost, p95 over target.

### Day 10 exercise: pictures, scans and voice (`EVAL_REPORT.md`)

The chatbot can now take a **screenshot** of an error (it reads the error code, finds it in the documents and answers with a citation, and can turn it into a **ticket**), read **scanned PDFs** page by page into the knowledge base, take a **voice question** (turned into text you can correct before it is asked) and, if switched on, draw an optional **picture** for an answer.

| Measure | Result |
|---|---|
| Ticket field accuracy (15 screenshots) | 72 / 75 = 96% (held-out severity 3 / 5) |
| Screenshot questions | 13 / 13 |
| Voice questions | 5 / 5 |
| Scan questions answered from the scanned file | 5 / 5 |
| Injection images resisted | 2 / 2 |
| Image size | 1024 px: same scores as full size, 40% fewer tokens (768 px loses 4 error codes) |
| Cost | screenshot question $0.0023, one scanned page $0.0021 (once), voice about $0.0006, picture out $0.04 |

Pictures and recordings are never saved (a test checks it). Pictures out are off by default (`ILLUSTRATIONS=1`). The gate now has a ninth dimension, Multimodal: **9 of 9: READY**. The 75-case evaluation was re-run after the scans joined the index: 74 / 75, unchanged.

## Settings (`app/config.py`)

| Setting | Value | Why |
|---|---|---|
| Chunk size / overlap | 500 / 100 characters | A few sentences hold one fact with its context; the overlap keeps a fact from being cut in half. |
| Chunks retrieved | 4 | Enough context for one answer without much noise or cost. |
| Minimum score | 0.55 | Sits in the gap between unrelated questions (about 0.51) and the weakest real answer (0.61). |
| Temperature | 0.1 | Answers should stay close to the sources and be repeatable. |
| Max tokens / timeout | 400 / 60 s | Limits cost and stops a call hanging. |
| Retrieval mode | smart | See above. |
| Long messages | over 500 characters: shortened to their end; over 100,000: refused | A pasted log usually has the question last. |
| Self-critique | off (`SELF_CRITIQUE=1` to try) | Measured: not worth its time and cost. |
| p95 target | 5 s | Set before measuring the benchmark. |
| Image size | 1024 px longest side, 5 MB | Measured: smallest size with no loss. |
| Voice | up to 60 s, 5 MB, silence refused before any call | A silent recording costs nothing. |
| Scanned pages | confirm above 6 pages | Shows the price first. |
| Pictures out | off (`ILLUSTRATIONS=1` to turn on) | Decoration, about $0.04 each. |

## Security

A whole-project review was done in Part 1 and the findings are in [SECURITY_REVIEW.md](SECURITY_REVIEW.md). The Day 8 exercise added: a canary code word in the instructions plus an output guard that blocks any reply containing it, fifteen injection attacks (five of them on-topic so the model really reads them), and a poisoned test document that is only ever indexed in a separate test collection (`data/security_tests/`). Untrusted text (questions, documents, the reviewer's note) is always escaped before it goes into a prompt.

## Known limits

- **One follow-up still fails (CTX-03):** "Is that the same for contractors?" after a question about the 12-hour VPN limit. The two facts needed are in two different chunks and no single search finds both.
- **My documents and the class PDFs disagree on 5 facts** (password expiry 90 vs 180 days, lockout 30 vs 15 minutes, service desk hours, lost-equipment deadline, guest Wi-Fi midnight vs 8 hours). The chatbot can quote either one, and the judge sometimes marks an answer wrong because of it.
- **The follow-up detector is a heuristic** written after seeing which questions failed. Small test sets (20 retrieval questions, 8 conversations) mean one question moves a score by 5 to 12 points.
- **The judge and the self-critique reviewer are the same model**, so a self-critique score is not independent of the judge's.
- **Chunks can start or end mid-sentence.** The overlap usually covers this.
- **Uncited sentences:** an answer needs at least one valid citation, but a long answer could still contain a sentence without one.
- **One user, one computer.** There is no login; do not expose the app on a network. Rebuilding from two browser tabs at once is not protected.
- **Questions and retrieved text are sent to the hosted models** (OpenRouter). Only use public or fictional documents. The same goes for pictures, scanned pages and recordings: they leave the computer to be read.
- **A scanned page can be misread** (one wrong word in a transcript), and nothing checks it automatically; pages read by vision are tagged "(read by vision)" in the sources. The voice notes in my tests are computer voices, which is easier than real people.
- **Ticket severity is the weak field** (3 of 5 on pictures I did not tune against).
- **Ollama must be running with the model loaded.** The embedding model is kept loaded for 30 minutes, but the first question after a long break can be slow.

## Project layout

```
app/        loader, chunker, embeddings, store, retriever, hybrid, rerank, rewrite, followup, retrieval, answer, input_check,
            safety, critique, llm, calllog, images, vision, screenshot, ticket, scanned, uploads, voice, illustrate, evaluate, eval_suite, judge, gate, benchmark, comparison, security_check, kb, ui
scripts/    build_index, search, ask, run_tests, compare_modes, run_eval, run_judge, judge_agreement, benchmark, gate, ...
tests/      pytest tests (offline) and tests/e2e/ (browser tests)
data/       docs/ (the knowledge base), test and evaluation suites, results, thresholds, security_tests/, chroma/ (not committed)
specs/      the browser test plan
.streamlit/ app settings (local-only address)
.claude/    the project's security-reviewer subagent
```

Also in the root: `REQUIREMENTS.md` (what it must do), `CLAUDE.md` (project rules for Claude Code), `REQUEST_LOG.md` (every request sent, phase by phase), `SECURITY_REVIEW.md`, `RAG_DECISION.md`, `PART2_NOTES.md`, `EVAL_REPORT.md` and `REFLECTION.md`.

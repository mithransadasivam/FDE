# Northwind IT Help Desk Chatbot

A chatbot that answers IT questions **only from a folder of documents**, shows which file and page each fact came from, and says "I don't know" when the documents don't cover the question.

It is a retrieval-augmented generation (RAG) project built phase by phase with Claude Code, starting from an empty folder. The 17 documents in `data/docs/` are fictional (a made-up company called Northwind): VPN, MFA, passwords, backups, printers, laptops and more.

## How it works

1. **Load and chunk:** every `.pdf`, `.txt` and `.md` file is read page by page (PDF page numbers are kept) and cut into 500-character chunks that overlap by 100 characters.
2. **Embed and store:** each chunk is turned into a vector by the local Ollama model `nomic-embed-text` and saved, with its file, page and chunk number, in a ChromaDB collection on disk (`data/chroma/`).
3. **Retrieve:** a question is embedded with the same model and the 4 most similar chunks are found, each with a similarity score.
4. **Answer with two guards:**
   - *Guard 1 (code):* if no chunk scores at least 0.55, the bot declines and the answer model is never called.
   - The model is told to answer only from the numbered sources, cite each fact like `[1]`, and reply with an exact decline sentence if the sources don't contain the answer.
   - *Guard 2:* if the model replies with the decline sentence, or gives an answer with no valid citation, the result is reported as declined, with no sources.
5. **Show it:** a Streamlit app with three tabs: **Chat**, **Knowledge base** and **Test results**.

## Requirements

- Windows with Python 3.11 or newer (developed on 3.13)
- [Ollama](https://ollama.com) running locally, with the embedding model: `ollama pull nomic-embed-text`
- An [OpenRouter](https://openrouter.ai) account for the answer model

## Set up

From the project folder:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Create a file called `.env` in the project folder with two lines (use your own key and model name; never commit this file, it is already in `.gitignore`):

```
OPENROUTER_API_KEY=your-key-here
LLM_MODEL=the-openrouter-model-name-you-want
```

## Run it

| What | Command |
|---|---|
| Build (or rebuild) the index from scratch | `.venv\Scripts\python.exe -m scripts.build_index` |
| Show the chunk count saved on disk (no embedding) | `.venv\Scripts\python.exe -m scripts.build_index --count` |
| See how many chunks each document made | `.venv\Scripts\python.exe -m scripts.chunk_report` |
| Search only, no answer model | `.venv\Scripts\python.exe -m scripts.search "How long do we keep backups?"` |
| Ask one question (uses the answer model) | `.venv\Scripts\python.exe -m scripts.ask "How long do we keep backups?"` |
| Run the 10 test questions and save the results | `.venv\Scripts\python.exe -m scripts.run_tests` |
| Start the app | `.venv\Scripts\python.exe -m streamlit run app/ui.py` |

The app opens at <http://localhost:8501>. It only listens on this computer (`.streamlit/config.toml`). **Build the index before the first question**, either with the command above or with the **Rebuild index** button on the Knowledge base tab.

To add documents, put `.pdf`, `.txt` or `.md` files in `data/docs/` and rebuild the index. Scanned PDFs contain no text, so they produce no chunks; the Knowledge base tab and `chunk_report` flag them.

## Run the tests

```
.venv\Scripts\python.exe -m pytest tests
```

100 tests, all offline: they use a fake model, a fake retriever and a fake embedder, and `tests/conftest.py` blocks every real network call and hides the API key. Nothing in the test run needs Ollama, OpenRouter or `.env`.

## Test results (10 questions: 7 answerable, 3 not)

Written in `data/test_questions.csv`; results saved in `data/results/`; reasoning in `data/results/TUNING.md`.

| Run | Minimum score | Behaviour correct | Answered when it should | Declined when it should | Avg time |
|---|---|---|---|---|---|
| 1 (baseline) | 0.55 | 10 / 10 | 7 / 7 | 3 / 3 | 3.86 s |
| 2 (stricter) | 0.65 | 9 / 10 | 6 / 7 | 3 / 3 | 3.68 s |

The one setting changed was the minimum score. At 0.65 the question "I lost my phone on the train - who do I call?" (best retrieval score 0.61) was wrongly declined, so **0.55 was kept**. The automatic score checks behaviour only (answered or declined); every answer and citation in run 1 was also read against the documents by hand and was correct.

## Settings (`app/config.py`)

| Setting | Value | Why |
|---|---|---|
| Chunk size / overlap | 500 / 100 characters | A few sentences hold one fact with its context; the overlap keeps a fact from being cut in half. |
| Chunks retrieved | 4 | Enough context for one answer without much noise or cost. |
| Minimum score | 0.55 | Sits in the gap between unrelated questions (about 0.51) and the weakest real answer (0.61). |
| Temperature | 0.1 | Answers should stay close to the sources and be repeatable. |
| Max tokens / timeout | 400 / 60 s | Limits cost and stops a call hanging. |
| Max question length | 500 characters | Longer questions are refused before any embedding or model call. |

## Security

A whole-project review was done and the findings are in [SECURITY_REVIEW.md](SECURITY_REVIEW.md), with what was fixed and what was accepted as a known limit.

## Known limits

- **The minimum score cannot catch near-misses.** Questions close to a covered topic (a printer on floor 3, Linux laptops) score as high as real answers (about 0.71). They are caught by the model's decline sentence (Guard 2), which depends on the answer model following instructions.
- **Chunks can start or end mid-sentence.** The overlap usually covers this, but splitting at headings or paragraphs would be cleaner.
- **Small test set.** 10 questions on 17 short documents, with the answer text checked by hand. A 10/10 score does not mean the bot is always right.
- **Only markdown documents were tested with real content.** PDF reading is covered by tests that build small PDFs, but no real-world or scanned PDFs have been run through the chatbot.
- **Uncited sentences:** an answer needs at least one valid citation, but a long answer could still contain a sentence without one.
- **One user, one computer.** There is no login or per-session rate limit; do not expose the app on a network. Rebuilding from two browser tabs at once is not protected.
- **Questions and retrieved text are sent to the hosted model** (OpenRouter). Only use public or fictional documents.
- **No conversation memory.** Each question is answered on its own, so "and on a Mac?" does not know what "it" refers to.

## Project layout

```
app/        loader, chunker, embeddings, store (ChromaDB), retriever, answer, llm, evaluate, kb, safe_text, ui
scripts/    build_index, chunk_report, search, ask, run_tests
tests/      pytest tests (offline)
data/       docs/ (the knowledge base), test_questions.csv, results/, chroma/ (not committed)
.streamlit/ app settings (local-only address)
.claude/    the project's security-reviewer subagent
```

Also in the root: `REQUIREMENTS.md` (what it must do), `CLAUDE.md` (project rules for Claude Code), `REQUEST_LOG.md` (every request sent, phase by phase) and `SECURITY_REVIEW.md`.

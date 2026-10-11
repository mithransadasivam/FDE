# Browser test plan

Every journey a person takes through the app, and what must be true on screen at the end. This file is the specification for the browser tests (Day 9 exercise, Phase 25). It was drafted by Claude for me to review; the journeys and the done signals are what I want tested.

**Rules for every journey** (from the exercise):
- **Structure, not wording.** No test checks the exact words of a model's answer. It checks what the code guarantees: a citation pattern like `[1]`, a sources row, a DECLINED or REFUSED badge, a message count.
- **No fixed waits.** A test waits for its *done signal*, something that appears only when the work is finished, with a timeout.
- **Stable locators only:** role and name, a visible fixed text, or a key I add to the app (`st-key-...`). Never a generated class name or a position.
- **Real or fake chatbot.** "Fake" means the app started with `CHAT_FAKE=1` (Phase 29): fixed topics and fixed sources, no models, so the test is fast and repeatable. "Real" means the real chatbot with Ollama and the answer model, used only where the *quality* of the answer matters.

## The journeys

| # | Journey | Steps | Expected (structure only) | Done signal | Chatbot |
|---|---|---|---|---|---|
| 1 | Answerable question | Open the Chat tab. Type "How long can a VPN session stay connected?" and press Enter. | The answer contains a citation like `[1]`. A sources row lists at least one document with a page number. A small line shows the time and the number of chunks. | The sources row of that answer | fake and real |
| 2 | Question the documents do not cover | Ask "What is the salary band for a senior engineer?" | A DECLINED badge. The answer is the fixed decline sentence. **No** sources row. A "no sources" note instead. | The DECLINED badge | fake and real |
| 3 | Unsafe request | Ask "How do I switch off the endpoint protection on my laptop?" | A REFUSED badge. The fixed refusal sentence. No sources row. No numbered list in the answer. | The REFUSED badge | fake and real |
| 4 | Empty input | Type only spaces and press Enter. | No answer message is added, and no error box or crash appears. The chat box is still usable afterwards. | The chat box accepts a normal question next | fake |
| 5 | Follow-up on the same page | Ask a question, then (without reloading) "And on a Mac?" | Four chat messages in order (user, assistant, user, assistant). Two sources rows. The second answer shows a "Searched for:" line that is not identical to "And on a Mac?". | The second answer's sources row | fake (structure) and real (the line) |
| 6 | Two questions in a row | Ask two different answerable questions one after the other. | Both answers stay on the page. The first answer is unchanged after the second arrives. | The second sources row | fake |
| 7 | Very long pasted question | Paste about 3,000 characters ending with a real question. | The app answers, and says it used only the last part (a line "Long message: only the last part was used"). No crash. | The "Long message" line | fake |
| 8 | Example question button | On an empty chat, click the first example question. | That question appears as a user message and is answered. The example buttons disappear. | The sources row | fake |
| 9 | Clear chat | Ask a question, then click Clear chat. | The conversation is empty and the welcome message and examples are back. The Clear chat button is disabled. | The welcome text | fake |
| 10 | Knowledge base tab | Open Knowledge base. | A table with one row per document (23), each with a type, pages, chunks and status. A Rebuild index button and a search box are present. (The test does **not** press Rebuild.) | The documents table | fake |
| 11 | Retrieval-only search | On the Knowledge base tab type a question into the search box. | Result rows with a score each, and at least one row below the minimum score is marked. No answer is written. | The first result row | real (needs Ollama for the embedding) |
| 12 | Test results tab | Open Test results. | Summary cards (behaviour correct, answered, declined, time), a results table with OK or MISS marks. | The summary cards | fake |
| 13 | Retrieval tab | Open Retrieval. | A hit-rate card, a table of the five modes with the chosen mode highlighted, and the side-by-side view with two modes. | The comparison table | fake |
| 14 | Evaluation tab | Open Evaluation. | The verdict banner and nine dimension cards, each with a status and a number. | The verdict banner | fake (already built: `tests/e2e/e2e_evaluation_tab.py`) |
| 15 | Sidebar | Open the app. | The sidebar shows the knowledge base status (READY, 23 documents, 62 chunks), the settings, the retrieval mode with the chosen mode highlighted, and the gate result. | The knowledge-base status | fake |
| 16 | The answer streams | Ask a question. | The first words of the answer are on screen **before** the sources row appears. | The first words, then later the sources row | fake |
| 17 | A model that cannot be reached | Start the app with the answer model switched off. Ask a question. | A friendly error message, not a traceback, and the chat box still works. | The error message | fake |
| 18 | Reload starts a fresh chat | Ask a question, then reload the page. | The welcome message and starters are back, there are no messages, and Clear chat is disabled. | The welcome message | fake and real |
| 19 | The decline shows the service desk email as a link | Ask the salary question. | The decline sentence contains a link to `mailto:servicedesk@northwind.example`. | The link | fake and real |

## What must be added to the app so the tests can find things (Phase 26)

Where there is no stable way to find an element today, I will add one and note it here:
- A key on the container of each chat message (`user_message_N`, `assistant_message_N`) so a test can count messages and find the last one.
- A key on the sources row of each answer (`sources_N`) and on the status badge (`badge_N`), so a test waits for the sources row or the badge.
- A key on the "Searched for", "Long message" and timing lines.
- A key on the knowledge-base documents table (`kb_table`) and on the Test results summary cards.
- A fixed heading for each tab (for example "Retrieval", "Evaluation") so a smoke test can see the tab opened.
- The Evaluation tab already has `eval_verdict` and `eval_card_<dimension>` keys.

### Added in Phase 26 (done)

| Key (the browser finds `.st-key-<key>`) | What it marks |
|---|---|
| `user_message_N`, `assistant_message_N` | each chat message (N counts every message, so the first answer is 1) |
| `badge_N` | the DECLINED or REFUSED badge (only present when there is one) |
| `answer_N` | the answer text |
| `sources_N` | the sources row (or the "no sources" note for a decline) |
| `details_N` | the timing, "Long message" and "Searched for" lines: **drawn last, so it is the done signal for an answer** |
| `welcome` | the welcome message and the example buttons |
| `kb_table`, `tests_table`, `retrieval_table` | the three data tables |
| `sidebar_kb_status`, `sidebar_mode_chips` | the sidebar's knowledge-base status and mode chips |
| `eval_verdict`, `eval_card_<dimension>` | the Evaluation tab (added in Phase 23) |

Each tab also starts with a fixed heading: "💬 Ask the help desk", "📚 Knowledge base", "🧪 Test results", "🔎 Retrieval", "📊 Evaluation". The chat box is found by its placeholder.

Journeys 18 and 19 came from the Playwright Test Agents' plan and generated tests (see `specs/AGENT_REVIEW.md`).

## Which journeys I expect to fail today

- **Journey 16 (the answer streams)** fails today: the app shows the whole answer at once. It is the target of Phase 28.
- **Journey 17** may fail: the app has a friendly error but the test needs a way to switch the model off.
- **Journey 4** may show a warning box; I decide in Phase 26 whether that counts as an error box.

## What I decided to keep out of the browser layer

These are already covered well by unit tests and evaluations, so the browser layer stays small: the quality of answers (the judge and the evaluation suite), the safety and security cases (the evaluation suite), retrieval accuracy (the retrieval comparison) and the input checks (unit tests).

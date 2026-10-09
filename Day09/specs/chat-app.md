# IT Policies Chat App — Test Plan

App under test: `app/rag_app_stream.py` (Streamlit), run with `CHAT_FAKE=1` at http://localhost:8597.
Seed: `tests-ts/seed.spec.ts` (opens the app and waits for the chat box).

The real chatbot's wording changes from run to run, so expected results describe the **structure**
of the page (what elements appear, in what order, with what pattern), never exact sentences.
The one fixed piece of text is the decline line, which is a constant in the app.

Every scenario starts from a fresh page (empty chat history).

## 1. Page opens in its starting state

**Steps**
1. Open the app (`/`).

**Expected (structure)**
- A level-1 heading "Ask the IT policies" is visible.
- An introduction line is visible ("Answers come only from the IT policy documents...").
- A chat box with the placeholder "Ask a question about the IT policies" is visible and empty.
- No chat messages are on the page (zero `stChatMessage` elements).
- No "Sources:" line and no "No sources:" line is visible.

## 2. An answerable question gets a cited answer and a Sources line

**Steps**
1. Open the app.
2. Type "How long can a VPN session stay connected?" in the chat box and press Enter.
3. Wait for the "Sources: " line (it appears only when the answer has finished streaming).

**Expected (structure)**
- Two chat messages: the user's question first, then the assistant's answer.
- The user message shows the question text.
- The assistant message is not empty and contains at least one citation matching `[n]` (for example `[1]`).
- Exactly one line starting with "Sources: " is visible, and it names at least one document (`.pdf` or `.md`) with a page number.
- The decline line "No sources: the bot declined." is NOT visible.

## 3. A question the documents don't cover is declined

**Steps**
1. Open the app.
2. Ask "What is on the cafeteria menu this week?".
3. Wait for the decline line.

**Expected (structure)**
- Two chat messages (question, answer).
- The line "No sources: the bot declined." is visible.
- No line starting with "Sources: " exists.
- The assistant message has no `[n]` citation.

## 4. Two questions in a row build up the conversation

**Steps**
1. Open the app, ask the VPN question, wait for "Sources: ".
2. Without reloading, ask "How often are laptops replaced?" and wait for the second "Sources: ".

**Expected (structure)**
- Four chat messages in order: question 1, answer 1, question 2, answer 2.
- Two "Sources: " lines are visible (one per answer); the first answer is still on the page.
- Each answer has its own `[n]` citation.

## 5. A decline and an answer can appear in the same conversation

**Steps**
1. Open the app, ask the cafeteria question, wait for the decline line.
2. Ask the VPN question, wait for "Sources: ".

**Expected (structure)**
- Four chat messages.
- Exactly one "No sources: the bot declined." line and exactly one "Sources: " line.
- The decline comes first, the sourced answer second.

## 6. Topic matching ignores capital letters

**Steps**
1. Open the app.
2. Ask "WHAT IS THE PASSWORD RULE?" and wait for the answer to finish.

**Expected (structure)**
- The answer has a `[n]` citation and a "Sources: " line (it is not declined).

## 7. A blank message (edge case)

**Steps**
1. Open the app.
2. Type only spaces in the chat box and press Enter.

**Expected (structure)**
- Observed today: the app accepts it as a question and replies with the decline line (two messages appear).
- Pass criterion: the page does not crash or show an error/traceback; it stays usable and the chat box is still visible.
- Note for the team: ideally a blank message would be ignored. This scenario records current behaviour.

## 8. Reloading the page clears the conversation

**Steps**
1. Open the app, ask the VPN question, wait for "Sources: ".
2. Reload the page.

**Expected (structure)**
- After the reload the chat shows zero messages and no "Sources: " line.
- The chat box is visible and empty.

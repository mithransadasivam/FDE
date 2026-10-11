# IT Help Desk Assistant - Test Plan (Chat tab and Knowledge base tab)

Application under test: Streamlit app at http://127.0.0.1:8620, running with the FAKE chatbot.
Scope: the **Chat** tab and the **Knowledge base** tab (plus the sidebar parts that react to chat).
Not covered: Test results, Retrieval and Evaluation tabs.

## Observed application summary

- Page title: "IT Help Desk Assistant". A banner always shows: "FAKE CHATBOT: answers come from a few fixed topics, not from the real documents or models. For testing only."
- Tabs: Chat, Knowledge base, Test results, Retrieval, Evaluation. Chat is selected on load.
- Sidebar: KNOWLEDGE BASE status (Northwind IT docs, READY, 23 documents - 62 chunks), SETTINGS table (Chunk size 500, Overlap 100, Chunks retrieved 4, Minimum score 0.55), retrieval mode, test set, decision, evaluation, gate, latest test run, a LAST QUESTION panel and a "Clear chat" button (disabled when the chat is empty).
- Chat tab, fresh state: a welcome message from the assistant and three starter buttons: "How do I set up MFA on a new phone?", "How long do you keep daily server backups?", "My VPN keeps cutting out at home. What can I try?". Below is a text box ("Ask a question about your IT documents...") with a Send button.
- Every assistant reply shows: the answer text with [n] markers, a source line such as `[1] mfa_setup_guide.md · page 1`, a timing line such as `0.45 s · 1 chunks`, and a `Searched for: ...` line (the query actually used).
- Declined replies show a DECLINED label, the text "I don't know: the documents don't cover that. Please contact the service desk on extension 4357 or servicedesk@northwind.example.", the warning "No sources: nothing relevant was found" and `0.0 s · 0 chunks`.
- Fixed fake topics seen: MFA, VPN (only phrasing about the VPN cutting out), daily backups, email attachments, ticket priorities. Anything else is declined.
- Knowledge base tab: summary line "23 of 23 documents indexed · 62 chunks · chunk size 500, overlap 100", buttons "Rebuild index" and "Open folder", a documents table (canvas-based grid with show/hide columns, download CSV, search and fullscreen toolbar), and a "Try a search (retrieval only, no model call)" text box. A search lists chunks with a score in bold, the file name, page and chunk number and a text excerpt. Results below the minimum score (0.55) are marked "(below the minimum score: not used)".

Conventions: every scenario starts from a **fresh browser context** (new page load, empty chat). Scenarios are independent. The expected answers are repeatable because the chatbot is fake, but timings vary, so only check timings for format, not value.

---

## Area A: Chat - page load and starter questions

### 1. Chat tab initial state
**Assumptions:** Fresh browser context, the app has just been opened.
**Steps:**
1. Open http://127.0.0.1:8620 and wait for the page to finish loading.
2. Observe the page title, the banner, the tabs and the Chat tab content.
3. Observe the sidebar "Clear chat" button and the "LAST QUESTION" section.
**Expected results:**
- Title "IT Help Desk Assistant" and the FAKE CHATBOT banner are visible.
- Five tabs are listed and Chat is selected.
- The welcome message and exactly three starter buttons are shown, plus an empty message box.
- "Clear chat" is disabled; LAST QUESTION says "Ask a question to see details."
**Success:** All items present. **Failure:** Any item missing, Clear chat enabled, or an error message displayed.

### 2. Starter button: MFA question
**Assumptions:** Fresh state.
**Steps:**
1. Click "How do I set up MFA on a new phone?".
2. Wait for the reply.
**Expected results:**
- The question appears as a user message.
- The assistant answers "Raise a Reset MFA ticket first [1]. Then install the authenticator app and scan the QR code [1]."
- Source line `[1] mfa_setup_guide.md · page 1`, a timing line of the form `<n> s · 1 chunks`, and `Searched for: How do I set up MFA on a new phone?`.
- The starter buttons and welcome message are no longer shown.
- Sidebar LAST QUESTION shows First words after, Full answer after, Chunks used = 1 and Best match score 0.90; Clear chat becomes enabled.
**Success:** All of the above. **Failure:** Different answer or source, missing citation, or sidebar not updated.

### 3. Starter button: backups question
**Assumptions:** Fresh state.
**Steps:**
1. Click "How long do you keep daily server backups?".
**Expected results:**
- Answer "Daily server backups are kept for 30 days [1]." with source `[1] backup_and_recovery_runbook.md · page 1` and 1 chunk.
**Success:** Exact answer and source. **Failure:** Declined reply, wrong source or no source.

### 4. Starter button: VPN question
**Assumptions:** Fresh state.
**Steps:**
1. Click "My VPN keeps cutting out at home. What can I try?".
**Expected results:**
- Answer lists three tips: update NorthLink to version 5.2 or later, move closer to the router or use a cable, switch protocol from Auto to TCP, each with [1].
- Source `[1] vpn_troubleshooting.md · page 1`, 1 chunk.
**Success:** Three tips and a source. **Failure:** Declined or missing tips/citation.

---

## Area B: Chat - typing questions

### 5. Type a question and submit with Enter
**Assumptions:** Fresh state.
**Steps:**
1. Click the message box and type "How do I attach files to email?".
2. Press Enter.
**Expected results:**
- Answer "The attachment limit is 25 MB [1]. For larger files, share a NorthDrive link [1]." with source `[1] email_and_calendar_faq.md · page 1`.
- The message box is cleared and ready for another question.
- `Searched for:` shows the typed question unchanged.
**Success:** All as above. **Failure:** Question not sent, box not cleared, wrong answer.

### 6. Submit with the Send button
**Assumptions:** Fresh state.
**Steps:**
1. Type "What priority levels do tickets have?" in the message box.
2. Click "Send message" instead of pressing Enter.
**Expected results:**
- Answer "A P1 ticket gets a response within 15 minutes [1]. A P3 ticket gets a response within 4 hours [1]." with source `[1] Day06_Slide15_policy_it_support_slas.pdf · page 2`.
**Success:** Same result as with Enter. **Failure:** Nothing happens or a different result.

### 7. Question wording is case-insensitive
**Assumptions:** Fresh state.
**Steps:**
1. Type "HOW LONG ARE BACKUPS KEPT" and press Enter.
**Expected results:**
- The backups answer (30 days, backup_and_recovery_runbook.md) is returned, not a decline.
**Success:** Backups answer. **Failure:** DECLINED reply.

### 8. Several questions build a conversation in order
**Assumptions:** Fresh state.
**Steps:**
1. Click the MFA starter button.
2. Type "How do I attach files to email?" and press Enter.
3. Type "How long do you keep daily server backups?" and press Enter.
**Expected results:**
- Three question/answer pairs appear in chronological order, each with its own sources and timing line.
- Earlier answers are unchanged after later questions.
- Sidebar LAST QUESTION reflects only the most recent question.
**Success:** Order and content kept. **Failure:** Earlier messages vanish, reorder or change.

---

## Area C: Chat - declined and error handling

### 9. Out-of-scope question is declined
**Assumptions:** Fresh state.
**Steps:**
1. Type "Tell me a joke" and press Enter.
**Expected results:**
- Reply labelled DECLINED: "I don't know: the documents don't cover that. Please contact the service desk on extension 4357 or servicedesk@northwind.example."
- The email is a mailto link to servicedesk@northwind.example.
- Warning "No sources: nothing relevant was found" and `0.0 s · 0 chunks`; no [n] citations.
- Sidebar Chunks used = 0.
**Success:** Decline with contact details and no invented facts. **Failure:** Any fabricated answer or source.

### 10. Question on a topic the starter text promises but the bot does not handle
**Assumptions:** Fresh state. The welcome message says passwords, printers and laptops are covered, but the fake bot only knows a few topics.
**Steps:**
1. Type "How do I reset my password?" and press Enter.
2. Type "vpn" (a single word) in a fresh chat after clicking "Clear chat", and press Enter.
**Expected results:**
- Both receive the DECLINED reply (the fake bot only recognises its fixed topics, and a bare "vpn" is not enough).
- No crash, no stack trace.
**Success:** Graceful decline. **Failure:** Error, blank reply or hang.
**Note for the tester:** record this as a known limitation of the fake bot, not a product bug.

### 11. Empty and whitespace-only input
**Assumptions:** Fresh state.
**Steps:**
1. With the box empty, observe the Send button and try pressing Enter in the box.
2. Type three spaces and press Enter.
**Expected results:**
- Nothing is added to the chat for an empty submit.
- For whitespace-only text, a message "Please type a question first." appears and no user message is added.
**Success:** No message sent, warning visible for whitespace. **Failure:** A blank message is added or the app errors.

### 12. Very long input (3000 characters, no spaces)
**Assumptions:** Fresh state.
**Steps:**
1. Type or paste a string of 3000 letter "x" into the box and press Enter.
2. Type "How do I attach files to email?" and press Enter.
**Expected results:**
- The long text is shown as the user message and the assistant replies "I could not find any words to search for. Please type your question in words." with `0.0 s · 0 chunks`.
- The page layout is not broken beyond the long line, and the second question still gets its normal answer.
**Success:** Graceful message and the app stays usable. **Failure:** Crash, hang or the second question fails.

### 13. Special characters and HTML are shown as plain text
**Assumptions:** Fresh state.
**Steps:**
1. Type `<b>hi</b> backups?` and press Enter.
**Expected results:**
- The user message shows the literal text `<b>hi</b> backups?` (no bold formatting, no script execution).
- The backups answer (30 days) is returned and `Searched for:` echoes the literal text.
**Success:** Text escaped, answer correct. **Failure:** HTML rendered or answer missing.

---

## Area D: Chat - follow-up behaviour and clearing

### 14. Follow-up question carries the previous topic
**Assumptions:** Fresh state.
**Steps:**
1. Click the backups starter button.
2. Type "and for weekly ones?" and press Enter.
3. Look at the `Searched for:` line of the second reply.
**Expected results:**
- The second reply is not declined; it gives the backups answer again (the fake bot has no weekly-backup fact).
- `Searched for:` shows the earlier topic word combined with the new text (for example "backups and for weekly ones"), showing the question was rewritten using the conversation history.
**Success:** Rewritten query visible and an answer returned. **Failure:** Decline, or the rewrite ignores history.
**Note:** The answer repeats the daily-backup fact for a weekly question; confirm with the product owner whether this is acceptable.

### 15. Conversation history can leak into an unrelated question
**Assumptions:** Fresh state.
**Steps:**
1. Click the MFA starter button.
2. Type "What is the weather in Paris?" and press Enter.
3. Click "Clear chat". Then type "What is the weather in Paris?" again and press Enter.
**Expected results:**
- Step 2: the bot answers with the MFA answer, and `Searched for:` shows "mfa What is the weather in Paris" (history was prepended).
- Step 3: the same question on a fresh chat is DECLINED.
**Success:** Behaviour matches the above and is reproducible. **Failure:** Results differ between runs.
**Note:** This is a probable bug (off-topic questions are answered with unrelated content after a previous on-topic question). Log it and confirm.

### 16. Clear chat resets everything
**Assumptions:** Fresh state.
**Steps:**
1. Ask two questions (any starter button, then a typed one).
2. Click "Clear chat" in the sidebar.
3. Reload the page (F5).
**Expected results:**
- After step 2 the conversation disappears, the welcome message and three starter buttons return, "Clear chat" is disabled again, and LAST QUESTION says "Ask a question to see details."
- After step 3 the page again shows the empty initial state.
**Success:** Both states are empty. **Failure:** Old messages persist or the sidebar keeps stale data.

### 17. Chat is not kept across a page reload
**Assumptions:** Fresh state.
**Steps:**
1. Click the MFA starter button and wait for the answer.
2. Reload the page.
**Expected results:**
- After reload the chat is empty (welcome message and starter buttons shown), because a reload starts a new session.
**Success:** Empty chat. **Failure:** Previous chat is restored (record it and ask whether that is intended).

---

## Area E: Knowledge base tab

### 18. Knowledge base tab overview
**Assumptions:** Fresh state.
**Steps:**
1. Open the app and click the "Knowledge base" tab.
2. Compare the summary line with the sidebar KNOWLEDGE BASE and SETTINGS sections.
**Expected results:**
- Heading "Knowledge base" and summary "23 of 23 documents indexed · 62 chunks · chunk size 500, overlap 100".
- Buttons "Rebuild index" and "Open folder" are visible, and a documents table with a toolbar (show/hide columns, download CSV, search, fullscreen) is shown.
- The numbers match the sidebar (23 documents, 62 chunks, chunk size 500, overlap 100).
- Switching back to the Chat tab shows the chat unchanged.
**Success:** Numbers consistent in both places. **Failure:** Mismatch, missing table or buttons.

### 19. Documents table interactions
**Assumptions:** Fresh state, Knowledge base tab open. (The table is drawn on a canvas, so use visible text and the toolbar rather than cell selectors.)
**Steps:**
1. Count the rows in the table (scroll if needed) and note the column headings.
2. Use "Show/hide columns" to hide one column, then show it again.
3. Use the table search to look for "vpn".
4. Click "Fullscreen", then leave fullscreen.
5. Click "Download as CSV".
**Expected results:**
- 23 documents are listed, with VPN-related files such as the VPN remote access policy found by the search.
- Hiding and showing a column works; fullscreen opens and closes; a CSV file is downloaded containing the same 23 rows.
**Success:** All five actions work and numbers agree with the summary. **Failure:** Row count differs from 23, toolbar action fails, or the CSV is empty.

### 20. Retrieval-only search: relevant result
**Assumptions:** Fresh state, Knowledge base tab open.
**Steps:**
1. Click the "Search the knowledge base" box (placeholder "How long do we keep server backups?").
2. Type "How long do we keep server backups?" and press Enter.
**Expected results:**
- Ranked results appear, highest score first. The first is score 0.81 from `backup_and_recovery_runbook.md`, page 1, chunk 1, with an excerpt mentioning daily backups kept for 30 days. A second result from `data_retention_policy.md` (0.77) follows.
- Each result shows score, file name, page, chunk and an excerpt ending in "...".
- No model answer is produced (retrieval only).
**Success:** Top result is the backup runbook with a score above 0.55. **Failure:** No results, wrong ordering, or a generated answer.

### 21. Retrieval-only search: several documents and ordering
**Assumptions:** Fresh state, Knowledge base tab open.
**Steps:**
1. Search for "VPN".
2. Search for "mfa reset".
**Expected results:**
- "VPN": results from the VPN remote access policy PDF (about 0.75), the error codes PDF and others, in descending score order.
- "mfa reset": the first result is `mfa_setup_guide.md` (about 0.70), followed by other chunks.
- Scores never increase as you read down the list. Record how many results are shown (about 4 were seen, matching the "Chunks retrieved" setting of 4).
**Success:** Sensible ranking and descending scores. **Failure:** Unordered or irrelevant top result.

### 22. Retrieval-only search: nonsense query and the minimum score
**Assumptions:** Fresh state, Knowledge base tab open.
**Steps:**
1. Search for "zzzzqq".
**Expected results:**
- Weak results are still listed, but each has a score below 0.55 and is labelled "(below the minimum score: not used)".
- The page does not crash.
**Success:** Low-score results are clearly flagged. **Failure:** Low-score results shown without the flag, or an error.

### 23. Retrieval-only search: blank input
**Assumptions:** Fresh state, Knowledge base tab open.
**Steps:**
1. Type three spaces in the search box and press Enter.
2. Clear the box and press Enter.
**Expected results:**
- No results and no error are shown; the page stays on the search box.
**Success:** Nothing breaks. **Failure:** Error, stack trace or arbitrary results.

### 24. Rebuild index (run only on a disposable environment)
**Assumptions:** Fresh state; the tester is allowed to change the index. This scenario could alter shared state, so run it last or on a copy.
**Steps:**
1. Open the Knowledge base tab and note the summary line.
2. Click "Rebuild index" and wait for it to finish.
3. Re-read the summary line and the sidebar KNOWLEDGE BASE status.
4. Return to Chat and click the MFA starter button.
**Expected results:**
- A progress or success indication appears; afterwards the summary is again "23 of 23 documents indexed · 62 chunks" and the status is READY.
- The MFA answer is unchanged.
**Success:** Index rebuilt with identical counts. **Failure:** Error, changed counts, or the chat stops working.

---

## Not explored (needs follow-up)

- "Open folder" opens a folder on the machine running the server; behaviour could not be checked from a headless browser.
- The documents table is drawn on a canvas, so its column names and cell contents could not be read from the accessibility snapshot; verify them visually.
- "Rebuild index" was deliberately not clicked during exploration because it may change shared state.
- The Test results, Retrieval and Evaluation tabs are out of scope.

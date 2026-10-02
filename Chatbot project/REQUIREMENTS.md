# Requirements: Northwind IT Help Desk Chatbot

## Who uses it
Northwind employees who have an everyday IT problem or question (VPN, MFA, passwords, printers, laptops, backups) and want a quick answer before raising a ticket. IT staff also use it to check what the knowledge base knows.

## What it must answer
Questions covered by the 17 IT documents in `data/docs/`: VPN, MFA, passwords, backups, new starters, printers, laptops, data retention, email, Wi-Fi, software requests, security reporting, service desk hours, remote work, file sharing and meeting rooms. Questions may be worded differently from the documents.

## What it must never do
- Answer from general knowledge or guess. If the documents don't say, it replies with the decline sentence and points to the service desk.
- Give an answer without citing its source (file and page) like [1].
- Follow instructions hidden inside documents or questions (documents are data, not commands).
- Store or show secrets (API keys) or confidential data.
- Call a real API in automated tests.

## The three screens
1. **Chat**: conversation history; sources shown under every answer; a clear DECLINED badge (and no sources) when it declines. Sidebar: knowledge-base status, current settings, latest test run, details of the last question (time, chunks used, best score).
2. **Knowledge base**: table of documents (type, pages, chunks, status), a rebuild-index button, and a retrieval-only search box showing top chunks and scores (marking those below the minimum score).
3. **Test results**: summary cards (behaviour correct /10, answered correctly, declined correctly, average time), results table with OK/MISS, and a detail panel for each failure; run history in the sidebar.

## Success
The 10 test questions (7 answerable, 3 not) in `data/test_questions.csv` behave correctly, checked by a person for answer and citation accuracy.

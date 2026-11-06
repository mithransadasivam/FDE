# Prototype backlog for Day 3

*One-day prototype of UC1, the proof-of-address check, on fictional documents. Ordered by priority. Every story traces back to a finding (F01 and so on, from `engagement/findings.json`), a client rule from Helen or Tom, or ADR-001. The Musts test the risky idea: will analysts trust a tool that shows where an answer came from and how sure it is (F08, F09)?*

| Id | As a … I want … so that … | Priority | Acceptance criteria | Traces to |
|---|---|---|---|---|
| S01 | As an analyst, I want the document page beside its extracted fields on one screen, so that I do not switch between two screens or read the whole document. | Must | One screen shows the page and the fields side by side · opening a document takes one click from the list · no second window is needed | F05, F12 |
| S02 | As an analyst, I want four fields (name, address, document date, issuer) each with a confidence between 0 and 1, so that I can see how sure the tool is. | Must | Each field shows a value and a confidence · the confidence comes from the OCR words, not a fixed number · a field that is not found shows "not found", never a guess | F08, F09, ADR-001 |
| S03 | As an analyst, I want doubtful fields boxed on the page, so that I look there first and can see where the answer came from. | Must | Fields below 0.85 confidence are boxed in amber on the page image · clicking a field highlights its place on the page · fields at or above 0.85 are not boxed | F09, F12 |
| S04 | As an analyst, I want the document date, name and address checked against the application automatically, so that old or mismatched documents are caught. | Must | A date older than 3 months is flagged · name and address are compared with the application · each check shows pass or doubt with its evidence · a check never approves or rejects | F07, F10 |
| S05 | As the MLRO (Helen), I want every analyst decision logged with the evidence shown at the time, so that I can show a regulator who decided what, when, and on what evidence. | Must | Approve, ask applicant and escalate are buttons for the analyst · each click saves who, when, the fields and confidences shown, and the check results · the tool never makes a decision itself | F10, F11, Helen's rules |
| S06 | As an analyst, I want a copy button on each field, so that I do not retype it into CaseFlow. | Should | One button per field copies its value · nothing is written to CaseFlow | F05, F17 |
| S07 | As the FDE, I want to run the prototype on 30 labelled fictional documents and see how often it is right, so that we have a first accuracy number. | Should | 30 documents with known answers · the result shows right and wrong per field · it shows whether the low-confidence fields were the wrong ones | F13, F14 |
| S08 | As an analyst, I want a suggested "ask applicant" reason when a check fails, so that the message to the applicant is clear. | Could | A failed check offers a reason such as "older than 3 months" · the analyst edits it before anything is sent | F07 (later: UC4) |

Five Musts (S01 to S05) prove the idea. S06 and S07 make it pleasant and give us a number. S08 waits.

## Cut list: what the prototype will not do

| Not in the prototype | Why it can wait | When it comes |
|---|---|---|
| Real CaseFlow connection | API access is not granted and the API is read-only for us (F17); the prototype uses fictional documents | Day 8 |
| Bedrock in AWS London | The prototype uses fictional documents, so no customer data is at risk; a test model is enough to try the screen. Real use must be in London (F16) | Day 5 |
| Phone photos and HEIC | They are the known risk for OCR, and blur is the top reason for "ask applicant" (DATA_CHECK); start with clean PDFs | Day 6 |
| Business accounts (UC3) | Biggest time cost (F03) but the hardest (feasibility 2 in the use case list); build UC1 first and earn trust | Day 7 |
| Single sign-on and user accounts | It does not test the risky idea; one test user is enough | Day 8 |
| Writing results back to CaseFlow | Needs a vendor change (8 weeks, F17) and breaks the read-only rule | Not planned |
| Automatic decisions | A person must make every KYC decision (F10); out for good, not just for now | Never |

*Share this list with Deborah and Tom before the demo, so nothing in it is a surprise.*

# Class backlog for the UC1 prototype (agreed at the start of Day 3)

From your Day 2 homework, merged into one list. Every story traces to a finding (F01…), a rule or the ADR.

| Id | As a … I want … so that … | Priority | Acceptance criteria | Traces to |
|---|---|---|---|---|
| S01 | As an analyst, I want the document beside its extracted fields, so that I stop switching screens | Must | One screen shows the page and the four fields | F04 copy-typing, F09 |
| S02 | As an analyst, I want name, address, statement date and issuer extracted with a confidence each, so that I know what to trust | Must | Four fields, each with a 0–1 confidence taken from the words on the page | F08 show how sure, ADR-001 |
| S03 | As an analyst, I want doubtful fields boxed on the page, so that I look there first | Must | Fields below 0.85 boxed amber or red, where they are on the page | F09 point to the problem |
| S04 | As an analyst, I want the name, address, 3-month date and issuer checks done for me, so that rework drops | Must | Four checks shown as pass, fail or needs a look | F05 rework reasons |
| S05 | As the MLRO, I want every accept, correction and decision logged with the analyst's ID, so that I can show a regulator | Must | No decision without an analyst ID; every action in a log | Helen: audit trail, a person decides |
| S06 | As an analyst, I want a copy button per field, so that typing into CaseFlow is faster | Should | One click copies a field | F04, CaseFlow is read-only |
| S07 | As the FDE, I want the prototype run on Tom's 30 checked documents, so that we know its accuracy before the PoC gate | Should | Field accuracy against Tom's labels, shown against the success criteria | Plan T03, SC3 |
| S08 | As an analyst, I want a suggested reason when I ask the applicant, so that requests are clear | Could | Suggested reason from the failed check, editable | UC4, later |
| S09 | As an analyst, I want to filter the queue by what the prototype says, so that I can clear the ready ones first | Could | Filters: all, ready, needs a look, fails a rule, decided | Tom, 05:40 |

## Known limits to cut or keep

- Real CaseFlow connection: API access not granted yet (Day 8)
- Bedrock in AWS London: the prototype uses OpenRouter and fictional documents (Day 5)
- Phone photos and HEIC files: the known risk from ADR-001 (Day 6)
- Business accounts, UC3 (Day 7)
- Single sign-on (Day 8)

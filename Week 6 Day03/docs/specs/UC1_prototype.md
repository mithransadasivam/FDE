# Prototype spec: UC1 proof-of-address check

**Date:** 2026-11-04 · **Owner:** FDE team · **Demo:** end of Day 3, to Helen (MLRO) and Tom (analyst)

## 1. The riskiest assumption

A model can read name, address, statement date and issuer from a proof-of-address document, and say how sure it is, well enough that the analyst trusts the green fields and looks only at the doubtful ones. The demo runs the prototype on Tom's 30 checked documents and shows field accuracy against the success criteria.

## 2. Who, and the one job

Tom, a KYC analyst. The job: decide approve, ask the applicant, or escalate for one proof-of-address document, without switching screens or reading the whole page.

## 3. In scope

| Story | Acceptance criteria (how we will know) |
|---|---|
| S01 | One screen shows the page and the four fields |
| S02 | Four fields, each with a 0–1 confidence taken from the words on the page (ENG-301) |
| S03 | Fields below 0.85 boxed amber or red, where they are on the page (ENG-303) |
| S04 | Name, address, 3-month date and issuer checks shown as pass, fail or look (ENG-302) |
| S05 | No decision without an analyst ID; every action logged |
| S07 | Accuracy against Tom's labels, shown against the success criteria |

## 4. The contract

`backend/app/prototype/models.py` and the Day 3 section of `frontend/src/api.ts`. Changed only in the main checkout, by agreement.

## 5. Cut list

| Not in the prototype | Why it can wait | When |
|---|---|---|
| S06 Copy button per field | Saves seconds per field; the check works without it | Homework, Day 3 |
| S08 Suggested reason | Analysts can type the reason today | Later (UC4) |
| S09 Queue filter | 30 documents fit on one screen | Later |
| Real CaseFlow connection | API access not granted | Day 8 |
| Bedrock in AWS London | Prototype uses OpenRouter and fictional documents | Day 5 |
| Phone photos and HEIC | Known risk from ADR-001 | Day 6 |
| Business accounts (UC3), single sign-on | Out of the first pilot | Day 7, Day 8 |

## 6. What the demo shows against the success criteria

| Criterion | What the prototype can measure | What waits for the pilot |
|---|---|---|
| SC1 handling time | Not measurable on 30 fictional documents | Timed analysts on real work |
| SC3 field accuracy | Accuracy on Tom's 30 labels | Real, varied documents |
| SC4 a person decides | Every decision carries an analyst ID | Audit sample by the MLRO |

## 7. Parallel plan

| Session | Ticket | Branch | Files it changes |
|---|---|---|---|
| extract | ENG-301 | worktree-extract | `backend/app/prototype/grounding.py` |
| rules | ENG-302 | worktree-rules | `backend/app/prototype/rules.py` |
| ui | ENG-303 | worktree-ui | `frontend/src/components/FieldBoxes.tsx` |

## 8. Demo script (5 minutes)

1. Open Cases: 30 documents, counts by state.
2. Open D03-001: the date is boxed amber; approve is disabled until Tom accepts it.
3. Open D03-014: the date is not what the page says; use the page's value.
4. Open D03-007: a mobile bill fails the issuer rule; ask the applicant.
5. Demo tab: run Tom's 30 documents and compare with the success criteria.

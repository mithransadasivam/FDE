# Prototype spec: UC1 proof-of-address check

**Date:** 2026-11-04 · **Owner:** FDE team · **Demo:** end of Day 3, to the class

## 1. The riskiest assumption

If the page's own words do not set each field's confidence, analysts cannot tell what to trust, as in the 2024 pilot (F08, ADR-001). The demo opens D03-014, whose statement date is not what the page says, and shows it flagged.

## 2. Who, and the one job

Tom, an analyst: see the page beside four fields, with the doubtful ones boxed, and decide.

## 3. In scope

| Story | Acceptance criteria |
|---|---|
| S01 | One screen shows the page and the four fields |
| S02 | Four fields, each with a 0–1 confidence from its cited words; a value not on the page is flagged (ENG-301) |
| S03 | Fields below 0.85 boxed amber or red, in place on the page (ENG-303) |
| S04 | Name, address, 3-month date and issuer checks show pass, fail or look (ENG-302) |
| S05 | No decision without an analyst ID; every action logged |
| S07 | Field accuracy on Tom's 30 labelled documents, shown against the criteria |

## 4. The contract

The shapes are in `backend/app/prototype/models.py` and the Day 3 section of `frontend/src/api.ts`. Only the main checkout changes them, by agreement.

## 5. Cut list

| Not in the prototype | Why it can wait | When |
|---|---|---|
| S06 copy button | Should; speed, not trust | Day 3 homework option |
| S08 suggested reason | Could; belongs to UC4 | Day 3 homework option |
| S09 queue filter | Could; the queue works unfiltered | Day 3 homework option |
| Real CaseFlow connection | API access not granted | Day 8 |
| Bedrock in AWS London | Prototype uses OpenRouter, fictional documents | Day 5 |
| Phone photos, HEIC | Known ADR-001 risk | Day 6 |
| Business accounts (UC3) | Different job | Day 7 |
| Single sign-on | Needs the bank's systems | Day 8 |

## 6. Success criteria

| Criterion | Prototype can measure | Waits for the pilot |
|---|---|---|
| SC3 | Proxy only: field accuracy on 30 labelled documents | The real measure: share accepted unchanged by analysts |
| SC4 | Decision refused without an analyst ID | Weekly decision-log check |
| SC1, SC2, SC5 | Nothing | All three |

## 7. Parallel plan

| Session | Ticket | Branch | File |
|---|---|---|---|
| extract | ENG-301 | worktree-extract | `backend/app/prototype/grounding.py` |
| rules | ENG-302 | worktree-rules | `backend/app/prototype/rules.py` |
| ui | ENG-303 | worktree-ui | `frontend/src/components/FieldBoxes.tsx` |

## 8. Demo script

1. Open D03-014: the date is flagged as not on the page.
2. Click its box; the field highlights.
3. Open D03-007: fails the issuer rule.
4. Run the demo on Tom's 30 documents.
5. Read the cut list aloud.

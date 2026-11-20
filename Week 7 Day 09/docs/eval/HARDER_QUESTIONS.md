# Harder questions: what the semantic layer needed

**Date:** 2026-11-17 · **Questions:** data/Day07_HW_Slide03_questions.json (20) · **Model:** scripted (class model price: anthropic/claude-haiku-5.5; pilot model price: anthropic.claude-sonnet-5, London)

Every number below is from Data agent → Evaluation (the runs saved in `engagement/data_agent/runs/`), for both sets and all three layers. Because the model is scripted, "fixed" means: the question is answered right once the layer defines the term the question needs. With a real model, what each term says under `means` is what counts, and the numbers will differ; which questions need which term should not.

## The runs

| Set | Semantic layer | Right | Most common failure |
|---|---|---|---|
| harder | caseflow_v1 | 6 of 20 (30.0%) | Time period, 7 |
| harder | caseflow_v2 | 6 of 20 (30.0%) | Time period, 7 |
| harder | caseflow_v3 | 19 of 20 (95.0%) | Join or double counting, 1 |
| bank30 | caseflow_v1 | 20 of 30 (66.7%) | Ambiguous term, 8 |
| bank30 | caseflow_v2 | 28 of 30 (93.3%) | Time period, 1 and Join or double counting, 1 |
| bank30 | caseflow_v3 | 30 of 30 (100.0%) | none |

caseflow_v3 takes the harder set past Deborah's bar of 90% (95.0%, one question short of perfect). v2 does no better than v1 on the harder questions (6 of 20 for both): the two words v2 added, turnaround and backlog, fix the bank's 30 but are not the words these 20 use.

The 14 failures with caseflow_v2, by kind: Time period 7 (H01, H02, H03, H15, H16, H17, H20), Ambiguous term 5 (H04, H05, H07, H08, H19), Join or double counting 2 (H06, H09). The most common kind is time periods. H18 (pay) is right with every layer: the agent was refused `hr.analyst_pay`, said it cannot answer, and never guessed.

### What the agent assumed in H01, H03 and H07 (caseflow_v2)

| Question | What the agent assumed | What the bank means |
|---|---|---|
| H01, applications this financial year | "This financial year is taken as 2026": it counted from 1 January 2026 (16,359) | 1 April 2026, FY2026/27 (12,724) |
| H03, documents reviewed last week | "The last 7 days": 24 to 30 October (920) | Monday to Sunday before the extract: 19 to 25 October (779) |
| H07, applications overdue right now | Open for more than 3 calendar days, any status (3,463) | Open or escalated, not waiting for the applicant, more than 3 working days not counting waits (1,532) |

## What caseflow_v3 adds

Six terms and one example, all from data/Day07_HW_Slide04_more_definitions.md. v1 and v2 are unchanged.

| Term or example | From | Questions it fixed |
|---|---|---|
| financial_year | MI definitions (more), "Financial year" | H01, H02, H15, H17, H20 (H02 and H15 also use turnaround from v2) |
| last_week | "Last week" | H03, H16 (H16 also needs per_working_day) |
| per_working_day | "Per working day" | H16, and Q23 in the bank's 30 |
| first_time_right | "First-time right" | H04 (H06 is not fixed, see below) |
| within_promise | "Within the promise" | H05, H19 |
| overdue | "Overdue" | H07, H08 |
| distinct_applications (example) | "Counting applications across documents" | H09, and Q24 in the bank's 30 |

That is 13 of the 14 questions that were wrong with caseflow_v2. caseflow_v3 has 8 terms and 4 examples.

## Did anything that was right turn wrong?

No. Compared question by question:

- **v2 to v3 on the bank's 30:** 28 were right with v2, and all 28 are still right with v3. The two that were wrong with v2, Q23 (per working day) and Q24 (applications counted across documents), are fixed by per_working_day and distinct_applications. Result: 30 of 30.
- **v1 to v2 on the bank's 30:** 20 were right with v1, and all 20 are still right with v2. The ten wrong with v1 were Q07, Q08, Q09, Q10, Q20, Q21, Q23, Q24, Q26 and Q30; v2 fixed eight (all the turnaround and backlog questions) and left Q23 and Q24.
- **v2 to v3 on the harder set:** the 6 right with v2 (H10, H11, H12, H13, H14, H18) are all still right with v3.

Two documents were repaired in the bank's 30 with every layer (Q18 and Q22: the first query was refused, the second ran). None were refused or failed for good.

## Still wrong

One question: **H06**, "Which analyst in my region had the highest first-time-right rate in October 2026?" (asked by Grace Mensah). Failure kind: Join or double counting.

| | |
|---|---|
| What the agent did | Credited each document to the analyst who reviewed it (`documents.reviewed_by`) and ranked analysts by the share of their reviewed documents accepted. Answer: **Priya Nair** (88.5). Its stated assumption: "Credited to the analyst who reviewed each document". |
| What the bank's query does | Credits each application to the analyst who decided it (`cases.analyst_id`) and ranks analysts by first-time-right applications over their decided applications in October. Answer: **Sofia Marino**. |
| Who must decide | **Deborah's MI team.** The definitions say: "Not agreed yet: when we compare analysts, which analyst an application counts for. The MI team is to confirm." No semantic layer can settle this: v3 says so in the first_time_right term and asks the model to state the choice rather than guess. Once Deborah confirms, her answer goes in caseflow_v4. |

The bank's own query is one reasonable reading, not an agreed rule, so even this "still wrong" is a question for the bank, not for the model. Until then, an answer to an analyst comparison should carry the assumption with it.

## Cost

Tokens in are the average over each set, across the scripted model's one query (and the repair, where there was one). £ a month is the pilot model (Claude Sonnet 5, London) at 2,000 questions a month, which is an assumption to check with Deborah.

| Set | Layer | Tokens in per question | £ a month, pilot | £ a month, class model |
|---|---|---|---|---|
| bank30 | caseflow_v1 | 2,040 | £8.75 | £0.40 |
| bank30 | caseflow_v2 | 2,419 | £10.02 | £0.46 |
| bank30 | caseflow_v3 | 3,519 | £13.81 | £0.63 |
| harder | caseflow_v2 | 2,377 | £9.77 | £0.44 |
| harder | caseflow_v3 | 3,460 | £13.50 | £0.61 |

The price of the longer layer, on the bank's 30: **1,100 more tokens in every question (2,419 to 3,519) and £3.79 a month more on the pilot model (£10.02 to £13.81)**, and £0.17 more a month on the class model. In return the bank's 30 go from 93.3% to 100%, and the harder set from 30.0% to 95.0%.

The extra tokens are the six terms' wording. There is room to cut it: the `sql` under each term repeats what `means` says, and the synonym lists are long. Trimming that would take back part of the cost, but only worth doing when a real model's accuracy is measured on the shorter layer first. A longer layer also grows with every new word the bank adds, so it is worth asking at each version whether a word is used often enough to earn its tokens.

## What I did to get here

- Created `engagement/data_agent/question_sets.json` with the set `harder`.
- Built what Day 7's class work left for the evaluation to run: the validator (ENG-701) and row security (ENG-702), 28 tests passing; and `semantic/caseflow_v2.yml` (turnaround and backlog, from the MI definitions), because the homework compares against it and it did not exist.
- Wrote `semantic/caseflow_v3.yml`: six terms and one example, named exactly as the scripted model expects.
- Ran both sets with all three layers, then, on the Warehouse page, set Ask the data to caseflow_v3. As Helen, "How many applications did we receive this financial year?" answers 12,724 (FY2026/27 from 1 April 2026), the bank's answer.
- Whole backend test suite: 196 passed.

# The whole journey in one command

**Result: PASS**  
Date: 2026-10-30T03:49:35+00:00  
Run: fake models (simulated); models: openrouter/anthropic/claude-haiku-4.5  
Settings: {"mode": "fake models (fictional data)", "database": "data/journey.db (fresh)", "cvs": 52}

## Steps
| # | step | who | result | seconds | detail |
|---|---|---|---|---|---|
| 1 | Upload the starter-kit voice note | ON A PERSON'S BEHALF: hiring manager | OK | 0.25 | REQ_cloud_support_engineer.wav uploaded |
| 2 | Generate and approve the job and rubric (with a reason) | ON A PERSON'S BEHALF: hiring manager | OK | 0.61 | 8 rubric skills, 2 wording flag(s), approved with a reason |
| 3 | Publish the job | ON A PERSON'S BEHALF: hiring manager | OK | 0.15 | the job page is public |
| 4 | Upload the 52 CVs (candidates apply; CVs are read and blinded) | candidates (public page) | OK | 56.74 | 52 CVs read; 8 sent to the review queue |
| 5 | Review queue confirmed (a person would do this: logged) | ON A PERSON'S BEHALF: recruiter | OK | 1.92 | 8 CV(s) confirmed; the log notes that a person would do this |
| 6 | Security scan: hidden and planted instructions | code | OK | 0.63 | 3 hidden or planted instruction(s) found and flagged for a person; nothing was rejected |
| 7 | Screening and the evidence checker | AI + code | OK | 26.08 | 52 candidates scored, every quote verified, 0 checker item(s) for a person |
| 8 | Shortlist the top 6 (with a reason) | ON A PERSON'S BEHALF: recruiter | OK | 0.18 | top 6 shortlisted with a reason: [27, 49, 4, 11, 18, 20] |
| 9 | The scoring scale | code + ON A PERSON'S BEHALF: recruiter | OK | 0.2 | 5 core questions have a described 0-3 scale (8 of 8 rubric skills have questions with scales) |
| 10 | Invite 2 to the AI interview and approve the invitations | ON A PERSON'S BEHALF: recruiter | OK | 1.02 | candidates 27 and 20 invited; both invitation emails approved |
| 11 | AI interviews: a strong and a weak simulated candidate | AI interviewer + simulated candidates | OK | 20.52 | strong simulated candidate 81.0/100, weak simulated candidate 19.0/100 |
| 12 | Recordings and the recruiter's own review of the AI interviews | code + ON A PERSON'S BEHALF: recruiter | OK | 0.58 | full_conversation.mp3 and recording.json for both; the replay room opens after the recruiter's own levels |
| 13 | A practice recruiter interview followed by the copilot | copilot + ON A PERSON'S BEHALF: recruiter | OK | 6.29 | practice interview followed by the copilot: 1 forbidden-question warning(s), 1 CV check(s) |
| 14 | The recruiter's scores and decisions | ON A PERSON'S BEHALF: recruiter | OK | 0.72 | recruiter scored and decided ADVANCE with a reason; the weak candidate was withdrawn with a reason |
| 15 | Emails approved | ON A PERSON'S BEHALF: recruiter | OK | 0.35 | 2 more email(s) approved by the recruiter; nothing is sent without a person |
| 16 | The scorecard | code | OK | 0.36 | all three stages side by side; play links work; the hiring manager's view is blind |

Total time: **117.3 s**. Total cost: **$0.1440** (fake mode: what the same calls would cost at list prices).

## Who did what
Every row marked ON A PERSON'S BEHALF is a step a person does in real use (the hiring manager approves the job; the recruiter confirms unsure fields, shortlists, invites, enters their own levels, decides and approves every email). The script plays those roles through the same web pages so the whole journey can run; the decision log records each of them under the person's own account, and the review step carries a note saying a person would do it.

## Open it in the app
Serve the journey's own database:

    DATABASE_URL=sqlite:///data/journey.db OPS_DATABASE_URL=sqlite:///data/journey_ops.db STORAGE_DIR=data/journey_storage FAKE_MODELS=1 python -m uvicorn app.main:app --port 8003

- The strong candidate's scorecard: http://127.0.0.1:8003/candidates/27/scorecard
- The replay room: http://127.0.0.1:8003/interviews/27/replay
- Trust and cost: http://127.0.0.1:8003/trust
- The pipeline: http://127.0.0.1:8003/pipeline
- The outbox: http://127.0.0.1:8003/outbox

## Limits
- Fake mode: the AI parts are rule-based stand-ins, so this proves the platform works end to end, not how good a real model is. Run with `--real` for that.
- The AI interviews use recorded answers from the starter kit ('strong' and 'weak' simulated candidates).

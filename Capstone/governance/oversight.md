# Human oversight

Read from `app/supervisor.py::ALLOWED`: every move marked as a person's decision cannot be made by the system (`move()` refuses it, tested in `tests/test_supervisor.py::test_table_every_decision_is_a_persons_and_only_early_steps_are_automatic`).

## Moves only a person can make (with a reason)
| From | To |
|---|---|
| APPLIED | WITHDRAWN |
| REVIEW | EXTRACTED |
| REVIEW | WITHDRAWN |
| EXTRACTED | WITHDRAWN |
| SCREENED | SHORTLISTED |
| SCREENED | WITHDRAWN |
| SHORTLISTED | AI_INTERVIEW |
| SHORTLISTED | HUMAN_INTERVIEW |
| SHORTLISTED | WITHDRAWN |
| AI_INTERVIEW | HUMAN_INTERVIEW |
| AI_INTERVIEW | WITHDRAWN |
| HUMAN_INTERVIEW | DECISION |
| HUMAN_INTERVIEW | WITHDRAWN |
| DECISION | WITHDRAWN |

## Automatic steps the system may take (never a decision about a person)
| From | To |
|---|---|
| APPLIED | EXTRACTED |
| APPLIED | REVIEW |
| EXTRACTED | SCREENED |

## Other points where a person decides
| Point | Who decides, and how | Control |
|---|---|---|
| An email reaches a candidate | a person approves it in the outbox | `app/agents/communications.py::approve_and_send` |
| A final decision is recorded | a recruiter chooses, with a reason, after the evidence check was read | `app/decisions.py::decide` |
| The evidence checker's problems | a person acknowledges them before a shortlist or decision | `app/agents/checker.py::acknowledge` |
| The AI interview scorecard | the recruiter enters their own level for each must-have before any audio | `app/web/interview.py::save_review` |
| The human interview | the recruiter enters their own levels; the copilot only suggests | `app/web/copilot.py::recruiter_scores` |
| A candidate's explanation | a recruiter reviews the draft before it is sent | `app/decisions.py::explain_not_shortlisted` |
| Erasure approved by the company | a recruiter approves or refuses with a reason | `app/datarights.py::erase` |

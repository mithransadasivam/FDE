# Final check: the repository and requirements BR-01 to BR-20

**Result: PASS**  
Date: 2026-10-30T04:05:04+00:00  
Run: fake models (simulated); models: openrouter/anthropic/claude-haiku-4.5  
Settings: {"full_suite": false}

## Repository
| check | result | detail |
|---|---|---|
| no .env file is tracked, now or in the history | OK | git ls-files and git log --all |
| .gitignore covers .env, data/, storage/, the raw audio in reports/ and the virtual environment | OK | .env, data/, storage/, reports/accent_audio/, .venv/ |
| no API key or secret in any tracked file | OK | 586 files scanned |
| the real value of SECRET_KEY in .env appears nowhere in the files or history | OK | searched every commit |
| no API key pattern appears anywhere in the history | OK | git log --all -G (key patterns) |
| no real personal data: every e-mail address in the files is a fictional one (example.com and similar) | OK | all addresses are fictional |
| no large files or model weights are tracked | OK | largest tracked file is under 15 MB; no model weights |
| fictional data only is stated in the project rules | OK | CLAUDE.md rule 11 |
| the working tree is committed (nothing left uncommitted) | OK | clean |

## Requirements BR-01 to BR-20: 20 of 20 OK
Tests run for this check: 50 passed in 120.22s (0:02:00) (the tests each requirement names).

| id | requirement | status | tests | reports | problems |
|---|---|---|---|---|---|
| BR-01 | Voice note to job description and weighted rubric; biased wording flagged | OK | 2 | - | - |
| BR-02 | Read CVs in PDF, Word, scan and screenshot form; unclear fields go to review | OK | 2 | - | - |
| BR-03 | Hide name, age, gender, photo, nationality and contact details before scoring | OK | 2 | - | - |
| BR-04 | Set stages; stop for a person's approval before each move | OK | 3 | - | - |
| BR-05 | Score each skill with the exact CV sentence behind each score | OK | 2 | - | - |
| BR-06 | A ranked shortlist with strengths and gaps, approved by the recruiter | OK | 1 | - | - |
| BR-07 | A first-round voice interview: spoken questions, diagrams, recorded and transcribed answers, follow-ups, each answer scored with a quote | OK | 4 | - | - |
| BR-08 | Tell candidates AI is used before the interview; let them ask for a person | OK | 2 | - | - |
| BR-09 | Answer recruiters' questions about the pool and the policy, with sources | OK | 2 | - | - |
| BR-10 | Follow a recruiter-led interview: live transcript, suggested questions, key points, CV conflicts | OK | 2 | copilot_eval | - |
| BR-11 | Warn at once on a question that must not be asked | OK | 2 | copilot_eval | - |
| BR-12 | Draft emails; send nothing without a person's approval | OK | 2 | - | - |
| BR-13 | Check every score has real evidence and no protected detail was used, before the recruiter sees it | OK | 2 | - | - |
| BR-14 | Ignore instructions hidden in CVs, emails or spoken answers | OK | 3 | attack_report | - |
| BR-15 | One scorecard per candidate with every score, quote and link to the moment in the recording; the recruiter's decision and reason | OK | 2 | journey | - |
| BR-16 | Changing only name, gender or age clues, or the accent of the same answer, does not change the score | OK | 2 | identity_swap, accent_test | - |
| BR-17 | Cost per 100 CVs and per interview, and how fast the voice interview responds | OK | 2 | cost_and_speed | - |
| BR-18 | A governance pack for the EU AI Act: classification, model card, risk register and evidence | OK | 2 | - | - |
| BR-19 | Explain to a candidate, on request, why they were not shortlisted, reviewed by a recruiter before sending | OK | 2 | - | - |
| BR-20 | Check certifications against a register and flag overlapping job dates | OK | 2 | - | - |

## How to read this
OK means every test the requirement names exists and passed in this run, and every report it names is fresh and passed. MISSING goes into the demo as a known gap. Fake models were used where the reports say so.

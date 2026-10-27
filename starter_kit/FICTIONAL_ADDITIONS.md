# Fictional additions to the starter kit (Days 2-4)

The course's full starter kit (`Capstone_Hiring_Starter_Kit.zip`) was not available, so everything the brief lists beyond the Day 1 material was **generated for this project**, in the formats
the brief describes. All of it is fictional. Rebuild it with `python -m scripts.make_fictional_kit` (the audio needs the Windows speech engine; add `--no-audio` to skip it).

| Item | Where | How it was made | Difference from the brief |
|---|---|---|---|
| Question bank: 40 technical (key points, 0-3 guide, follow-ups, hint, core flag) and 10 behavioural (STAR) questions | `question_bank.json` | `scripts/kit/bank_data.py` | none |
| Diagram bank: 8 architecture diagrams with a description and an answer key | `diagrams/`, `diagrams.json` | drawn with Pillow | none |
| Hiring policy: numbered sections (stages, approvals, retention, rights, interview rules, forbidden questions) | `hiring_policy.md` | written | none |
| Fictional calendar for interview slots | `calendar.json` | generated | none |
| Red-team library: 20 attacks, the place each comes in, a rule for when it worked | `red_team_library.json` | written | none |
| Governance templates: model card, risk register, candidate notice, "why was I not shortlisted" | `governance_templates/` | written | none |
| CVs for the other two roles: 20 Data Analyst, 20 Platform Engineer (Word) | `cvs/data_analyst/`, `cvs/platform_engineer/` | `scripts/kit/build_cvs.py` | 20 per role (the brief says 41 and 27); Word only |
| Recruiter's ranking key for 20 CVs per role | `answer_keys/ranking_key_*.json` | a rule separate from the platform's scoring rule | a fictional recruiter, not a real one |
| Bias variants: 6 CVs x 5 versions (name, gender clues, age clues) | `bias_variants/` | Word files written from real CVs in the kit | none |
| 30 recorded AI-interview answers (strong, partial, weak, off-topic, spoken injection), each with an expected score | `recorded_answers/` | text built from the question bank, spoken with the Windows speech engine | "several voices and accents" are 4 speaking styles of 2 voices |
| 4 recorded human interviews (strong, weak, CV conflict, forbidden question), one speaker per stereo channel | `human_interviews/` | same | **70-140 seconds** each, not 10-15 minutes |
| Accent set: the same 5 answers in 4 variants | `accent_set/` | same | variants are speaking styles, **not real accents** |
| Tracking-system database with private columns | built at run time by `mcp_server/tracking.py` from the platform's own data (`storage/tracking_system.db`) | exported | none |

Not provided and not built: a real ATS, email server or calendar (out of scope by the brief), and any real person's CV or voice.

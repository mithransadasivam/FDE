# Reflection (DRAFT: please rewrite in your own words)

The course asks for **one page per person**: what you built, the hardest decision your team made about fairness or safety, and what you would do with another week.
This draft only collects the facts so you do not have to dig for them. **It is not your reflection**: your own thinking and voice are what is being assessed, so rewrite it,
add what you learned, and delete this note.

## What I built (facts to draw on)
- The whole AI Hiring Intelligence Platform from an empty folder with Claude Code: a hiring manager's voice note becomes an approved rubric; CVs are read in four formats with identity hidden;
  candidates are scored with verified quotes; a recruiter approves a shortlist; an AI interviewer and a copilot support the two interview rounds; a compliance reviewer checks the work; a person decides.
- The proof: 14 quality-bar numbers each measured by a script, a 20-attack red team (5/20 stopped before the guardrails, 20/20 after), bias tests, cost and speed, and a governance pack with a risk register and hashed evidence.

## The hardest decision about fairness or safety (pick one that was hard for you)
- Hiding identity with exact matches and rules instead of a name detector, because the detector hid tool names and would have lowered scores unfairly.
- Making "no quote, no score" absolute, even when it makes the system harsher on a model that paraphrases.
- Deciding to say plainly that the accent test used speaking styles, not real accents, and that all numbers came from fake models.

## What I would do with another week
- Run everything with real models and compare with the fake-mode numbers; test with real accented speech.
- Add an LLM judge for paraphrased injections; extend the bias test to intersections of name, gender and age.
- Replace the template CV scoring rules with a calibrated model and measure it against a real recruiter's judgements.
- A proper redesign of the console so it looks like a product (Stage 5 of the plan).

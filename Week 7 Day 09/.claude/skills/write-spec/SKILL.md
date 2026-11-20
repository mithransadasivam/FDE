---
name: write-spec
description: Write a one-page prototype spec and cut list from a backlog, using the course template
disable-model-invocation: true
argument-hint: [backlog file]
allowed-tools: Read, Glob, Grep
---

Write the one-page prototype spec for UC1, the proof-of-address check.

Read, in this order:
1. The backlog: $ARGUMENTS (if empty, use data/Day03_Slide10_class_backlog.md)
2. The template: data/Day03_Slide10_spec_template.md
3. engagement/success_criteria.json (the success criteria agreed on Day 1)
4. docs/adr/ADR-001-extraction-architecture.md (the chosen architecture)
5. backend/app/prototype/models.py and the "Day 3" section of frontend/src/api.ts (the contract)
6. docs/tickets/ENG-301.md, ENG-302.md and ENG-303.md (the three parallel tickets)

Then write docs/specs/UC1_prototype.md, following the template's eight sections:

- **Riskiest assumption:** the one belief that, if false, makes UC1 worthless. Say how the demo tests it.
- **In scope:** only the Must stories, plus any Should story the demo needs. Each with acceptance criteria someone can check.
- **Contract:** name the shapes and the two files. Say that only the main checkout changes them.
- **Cut list:** every story and known limit you leave out, each with a reason and a day. "No time" is not a reason.
- **Success criteria:** use the criteria IDs (SC1…). Say what the prototype can measure and what only the pilot can.
- **Parallel plan:** one row per ticket, with the branch `worktree-<name>` and the one file each changes.
- **Demo script:** five steps, riskiest assumption first, and say the cut list out loud.

Rules: at most 450 words. Use only facts from the files you read; invent no numbers, names or dates. Write nothing else.
When done, list any section where the inputs disagree or something is missing, so a person can decide.

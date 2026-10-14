# Day 11 Activity Log

Name: ________________

## Before we start (slide 5)
- Database built: ___ tickets (___ open), ___ assets
- HELPDESK_DB added to .env; data/helpdesk.db and logs/actions.jsonl in .gitignore: yes / no

## Activity 1: the tool-calling loop (slide 9)
- Loop tests passing: __ / 5

| Question | Model calls | Tool calls (name and arguments) |
|---|---|---|
| Hello, what can you help me with? | | |
| Is the Finance Portal down? | | |
| 12 VPN licences at 7.50 a month for a year? | | |

## Activity 2: describing find_tickets (slide 14)
- Schema tests passing: __ / 5

| Question | Tools and arguments the model chose | Right? |
|---|---|---|
| How many open Print Queue tickets are there? | | |
| Is the Finance Portal down, and how many open tickets are about it? | | |
| What is the response target for a P1 incident? | | |

- If a choice was wrong, what did you change in the description?

## Activity 3: checking arguments (slide 20)
- Validation tests passing: __ / 5
- The error message you think helps the model most, and why:
- "Show me the 50 newest tickets": did the model correct itself after the error? How?

## Activity 4: approval before a change (slide 25)
- Approval tests passing: __ / 5
- Prompt 2 (through Claude Code): approved or refused? Was the ticket changed?
- Your own terminal: what did the approval sentence say? What changed after you typed yes?
- INC-1037: did the assistant follow the note in the ticket? Did it try to call update_ticket?
- Database reset afterwards: yes / no

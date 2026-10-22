# Day 13 Activity Log

Name: ________________

## Before we start (slide 5)
- mcp (version 2) installed and in requirements.txt: yes / no
- Staff table added: ___ people
- Node.js version: ________ (22.19 or later for MCP Inspector)

## Activity 1: the query tool (slide 9)
- Server tests passing: __ / 8
- Where did each tool's description come from?
- The P1 query returned: ____________
- What did "DELETE FROM tickets" return?

## Activity 2: the schema resource and MCP Inspector (slide 14)
- Schema tests passing: __ / 5
- Open tickets by severity (from Inspector): P1 __  P2 __  P3 __  P4 __
- Which badge did Inspector show on the tools?
- Did the schema resource show any personal column? yes / no
- What did SELECT * FROM staff return in Inspector?

## Activity 3: the server in Claude Code (slide 20)
- Log tests passing: __ / 5
- /mcp shows helpdesk as: ____________
- Open tickets by department: the department with the most is ________ (__)
- What did Claude say about INC-1037?
- Did "everything the staff table holds about t.sato" show personal data? yes / no
- One SQL query Claude wrote that you would not have written:

## Activity 4: hiding personal data (slide 25)
- Security tests passing: __ / 12

| Request | Activity 3 | After Activity 4 |
|---|---|---|
| Everything about t.sato | | |
| People born before 1980 | | |
| Close ticket INC-1037 | | |

- Where is the rule enforced now, and why is that safer than the server's instructions?

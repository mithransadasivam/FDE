# MCP test log: the helpdesk server in Claude Code

Name: ________________   Date: ____________

Before you start: after changing app/mcp_server.py, run /mcp in Claude Code, select helpdesk and choose Reconnect.

## The three tries

| # | What I typed | Tools Claude called | What the answer said | Right? (yes / partly / no) |
|---|---|---|---|---|
| 1 | `@helpdesk:helpdesk://tickets/INC-1020  Who should handle this, and why?` | | | |
| 2 | `/mcp__helpdesk__triage_ticket INC-1014` | | | |
| 3 | `/mcp__helpdesk__triage_ticket INC-1037` | | | |

## The queries Claude ran

Copy the SQL from logs/mcp_queries.jsonl for try 2 or 3:

```
```

Was any query refused? Which one, and why?

## What I noticed

- Did any answer show personal data? (It must not.)
- What did Claude do with INC-1037's hidden instruction?
- One thing that surprised me:
- One change I would make to my prompt template, and why:

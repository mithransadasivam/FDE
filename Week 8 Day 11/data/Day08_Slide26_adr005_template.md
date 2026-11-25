# ADR-005: How the console and its agents reach the bank's systems

**Status:** proposed · **Date:** <date> · **Deciders:** Helen Achebe, Deborah Okafor, <your name>

## Context

<!-- The systems (CRM, KYC exceptions; Slack for notifications), who uses them through the console and Claude Code, and the bank's rules:
     each person sees only their remit, the MLRO's CRM access is read-only, every action is audited in the person's name. -->

## Options considered

### Option A: a service account for the console

<!-- One identity, svc-fde-console, for every call. What the Act-as tab showed before ENG-802. -->

### Option B: the person signs in; the MCP server exchanges their token

<!-- OAuth with PKCE at the bank's sign-in service; the MCP server checks every token (ENG-801) and exchanges it for each system (ENG-802). -->

### Option C: pass the person's token through to every system

<!-- The same token for the MCP server, the CRM and the ticketing system. -->

| | Option A | Option B | Option C |
|---|---|---|---|
| Permission matrix (21 cells) | <n> | <n> | <> |
| Who the audit names | <> | <> | <> |
| A stolen token reaches | <> | <> | <> |
| Run cost a month | <£> | <£> | <£> |

## Decision

<!-- Which option, and why, in two or three sentences. -->

## Consequences

<!-- What the bank must set up (registering the MCP server as a client allowed to exchange tokens, the shared webhook secret, Slack channels),
     how a new system is added (homework), and what you will monitor (refused tokens, refused webhooks). -->

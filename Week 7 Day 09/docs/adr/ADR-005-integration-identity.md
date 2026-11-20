# ADR-005: How the console and its agents reach the bank's systems

**Status:** accepted · **Date:** 2026-11-18 · **Deciders:** Helen Achebe, Deborah Okafor, Mithran Sadasivam

## Context

The console and Claude Code need to read and write the bank's CRM and KYC exceptions system (and send Slack notifications) for the people who use them. The bank's rules: each person sees only their remit (an analyst their team, a team lead their region, the MLRO every team), the MLRO's CRM access is read-only, and every action is audited in the person's name.

## Options considered

### Option A: a service account for the console

One identity, svc-fde-console, for every call. What the Act-as tab showed before ENG-802: every call works, so nothing looks broken, but every person sees everything and the audit names the console.

### Option B: the person signs in; the MCP server exchanges their token

OAuth with PKCE at the bank's sign-in service. The MCP server checks every token (ENG-801) and exchanges it for a token for each system (ENG-802, RFC 8693), which says the MCP server acts for the person.

### Option C: pass the person's token through to every system

The same token for the MCP server, the CRM and the ticketing system. The MCP specification forbids this ("token passthrough").

| | Option A | Option B | Option C |
|---|---|---|---|
| Permission matrix (30 cells, P1 to P10) | 16 of 30 | 30 of 30 | 11 of 30 |
| Who the audit names | svc-fde-console | the person, via fde-mcp | the person, but the systems refuse the token |
| A stolen token reaches | every system, every team | one system, one person's remit, for minutes | every system the person may use |
| Run cost a month | £0 in model cost (no model calls) | £0 in model cost (no model calls) | £0 in model cost (no model calls) |

A and C were measured by running the same 30 cells with the service account and with the passed-through token. A passes only where the right answer is "allowed to everything"; C passes only where the right answer is "refused".

## Decision

Option B. It is the only option where the bank's own systems apply their own rules to the actual person, so the MCP server holds no permission logic of its own and the audit tells the truth. Option A fails 14 of 30 cells and Option C is forbidden by the MCP specification and refused by the systems.

## Consequences

The bank must register the MCP server (fde-mcp) as a client allowed to exchange tokens, share the webhook secret with the ticketing system, and keep the Slack channels. We monitor refused tokens (Integrations, Sign-in tab, 9 of 9 probes) and refused webhooks. A new system is added the way the document store was (next section).

## A second system: the document store

**Date:** 2026-11-18

**What was added:** Two tools, list_documents and get_document, each calling the store as the person through `_call()` with audience documents and scope kyc.read. `_call()` exchanges the person's token for one with aud = documents, so the store applies its own rules and the MCP server has no rule of its own about documents: the same remit as the CRM (an analyst their team, a team lead their region, the MLRO everything), a 404 as if the customer or document did not exist outside it, and at most 20 documents opened an hour per person (the 21st answers 429). Nothing was changed in the bank's code.

**Permissions, tested:** Three rows, P8 to P10, for Tom, Grace and Helen. P8 (documents of a North 1 customer): allowed (1) for all three. P9 (a South 1 document, DS-0075): refused for Tom ("No document DS-0075"), refused for Grace (the same), allowed for Helen. P10 (documents of a South 1 customer, CU-022478): refused ("No customer CU-022478"), refused, allowed (2). The matrix is now 30 of 30. Four tests in test_documents.py hold the rules: remit, outside the remit, the 21st open in an hour refused, and the audit naming the person: every entry reads tom.reyes (or grace.mensah) via fde-mcp, never the console.

**The rule for every new system:** before an agent may reach it, a system must have (1) a resource the bank's sign-in service issues tokens for, (2) its own permission check for each person, with the same refusal for "not yours" as for "does not exist", (3) every call recorded in the person's name, and (4) rows in the permission matrix for every role, refusals included. The MCP server adds a tool and a docstring, never a rule.

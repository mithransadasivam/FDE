# ADR-002: Run the UC1 pilot on Amazon Bedrock with Claude Sonnet 5, in-Region in London

- **Status:** proposed
- **Date:** Day 5 of the engagement; the section "Other platforms considered" was added on 10 November 2026
- **Deciders:** Helen Achebe (MLRO) for the rules, Martin Hale (COO) for the cost
- **Supersedes in part:** ADR-001 (the model choice)

## Context

ADR-001 chose Textract plus Claude Haiku. On Day 5 the pilot went onto the bank's cloud, AWS London (eu-west-2), and the Bedrock model cards show that Claude Haiku 5.5 is not available in-Region in London: it only runs through the EU profile, which routes to seven EU Regions. Helen's rule is that customer documents must not leave the UK, so the model must be called in-Region in London. The pilot has to prove that UC1 can read a proof of address under all eight pilot rules (UK processing, private access, least privilege, no plain-text secrets, every call logged, guardrails, a spending limit, and a person decides), at a budget of USD 20 a month agreed with Martin.

## Options considered

| | Option A · Claude Haiku 5.5 (ADR-001's model) | Option B · Claude Sonnet 5 | Option C · Claude Opus 5.5 |
|---|---|---|---|
| Model ID called from London | eu.anthropic.claude-haiku-5-5 (EU profile) | anthropic.claude-sonnet-5 (in-Region) | anthropic.claude-opus-5-5 (in-Region) |
| Where the call is processed | Any of 7 EU Regions, not only the UK | London only | London only |
| Meets the client rules? | No: breaks the UK-only rule | Yes | Yes |
| Model cost a month (GBP, 8,600 documents) | £3 (USD 0.11 / 0.55 per million tokens) | £56 (USD 2.20 / 11.00) | £112 (USD 4.40 / 22.00, list 4 / 20 plus 10 percent) |
| Main risk | Not allowed for customer documents | Costs about 20 times Option A | Twice the cost of Option B for a gain nobody has measured |

Costs use 8,600 documents a month at 1,680 input and 420 output tokens each, and the course exchange rate of 0.78 GBP per USD. Sources: data/Day05_Slide10_bedrock_models.csv (Bedrock model cards, checked 5 Nov 2026) and the Anthropic pricing page for Opus 5.5 (checked 10 Nov 2026).

## Decision

Option B, Claude Sonnet 5 called in-Region in London on Amazon Bedrock. Three reasons:

1. **Rules:** it is the cheapest option that keeps processing in the UK. Option A fails the UK-only rule.
2. **Quality:** the Day 4 evaluation (prompt extract_v2, 98.5 percent of fields correct on 100 cases) was not run on this model. Before the pilot reads real documents, run `python -m scripts.run_eval --prompt extract_v2` on Sonnet 5 and accept it only if it scores at least as well. Until then this reason is a plan, not a result.
3. **Cost:** £56 a month for the model at the full 8,600 documents (USD 71.52). The pilot week reads far fewer documents and stays under the USD 20 budget; Martin must agree the full-volume figure before production.

Also decided for the pilot:
- **Guardrail:** policy uc1_v1 (infra/guardrails/uc1_v1.json), read by both Terraform and the scripted guardrail. Its probe results (`python -m scripts.probe_guardrail uc1_v1`) and its effect on the evaluation are not yet recorded here, so they must be run and written down before go-live.
- **Knowledge base:** none. UC1 reads one document at a time and compares it with the application; there is no collection of documents to search, so a retrieval layer would add cost and a place for customer data to live without adding anything the model needs.
- **Spend:** a monthly budget of USD 20 (variable budget_usd). An email alert at 80 percent of actual spend and at 100 percent of forecast spend. At 100 percent of actual spend the budget action attaches a policy that denies the pilot's role every Bedrock call. Billing data reaches AWS a few times a day, so this is a backstop, not a real-time cap.

## Other platforms considered

Facts are taken from docs/eval/PLATFORM_COMPARISON.md (checked 10 November 2026, each cell has a source there). Correct a fact in that file, not here.

| | Amazon Bedrock | Microsoft Foundry | Google Gemini Enterprise Agent Platform |
|---|---|---|---|
| Claude processed in the UK only | Yes: Sonnet 5 in-Region in London | No: Global Standard (any Azure Region) or US Data Zone only; Europe Data Zone not available; no UK Region lists Claude | No: global, US or EU multi-region only; the EU multi-region excludes the UK; regional endpoints stop at Sonnet 4.6 |
| Private access to the model | Yes: VPC interface endpoint | Private Link exists for the Foundry account; not confirmed for Claude | Private Service Connect: not confirmed for Claude |
| Role, no long-lived keys | Yes: Lambda execution role | Yes: Entra ID | Yes: IAM role and service account |
| Secrets in a vault | Yes: Secrets Manager | Yes: Key Vault | Yes: Secret Manager |
| Every model call logged | Yes: invocation logging | Not confirmed | Yes: request-response logging to BigQuery |
| Guardrails | Yes: Bedrock Guardrails | No built-in filter for Claude | Model Armor exists; with Claude not confirmed |
| Spending limit that stops calls | Yes: budget action | No: alerts only | Yes: spend cap, not instant |
| Terraform | Yes: hashicorp/aws | Yes: Bicep or Terraform documented | Not checked |
| Model cost a month (8,600 documents) | £56 | £51 on the global endpoint, £56 on the US Data Zone: neither usable | £51 on the global endpoint, £56 on the EU multi-region: neither usable |

**Verdict.** Bedrock stays: both other platforms fail the UK-only rule for Claude, so the Decision above is unchanged.

**What would reopen it.** Any one of these, each of which Helen can check on a public page:
1. Microsoft's "Region availability by deployment type" table lists Claude Sonnet 5 (or the model we run) as deployable in UK South or UK West, or adds a UK or EU Data Zone for Claude whose processing stays in the UK.
2. Google's data residency page or the Claude Sonnet 5 model card lists London (europe-west2), or a UK-only endpoint, for the model we run.
3. Bedrock stops offering our model in-Region in London.

**When I will look again.** On 10 December 2026, and again at the pilot review before any real customer document is used. These platforms change every month, so the check is by date, not by event.

## Consequences

- **Good:** the model is processed only in London; every rule in the pilot is met by one provider and one Terraform provider; the budget stops calls itself; the decision shows it was compared with the other two clouds and says what would change it.
- **Bad:** Option B costs about 20 times Haiku; the Day 4 quality figures and the guardrail probe results still have to be produced for this model.
- **To watch:** the three reopen triggers above, on 10 December 2026; the cost if volume rises to the January peak of 17,200 documents (about £112 a month for the model); and the open points in PLATFORM_COMPARISON.md that I could not confirm.

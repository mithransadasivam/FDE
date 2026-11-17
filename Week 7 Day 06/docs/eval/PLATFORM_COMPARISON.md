# The other two platforms, for UC1

**Checked on:** 10 November 2026 · **By:** Mithran Sadasivam (with Claude Code doing the page reading)

Every fact below carries a source tag like [S3]; the sources are listed at the end with the date I opened them. Microsoft Foundry was Azure AI Foundry; Google's Gemini Enterprise Agent Platform was Vertex AI. Most articles still use the old names.

## The question

Could the UC1 pilot run on Microsoft Foundry or on Google's Gemini Enterprise Agent Platform instead of Amazon Bedrock, under the bank's eight rules?

## Against the bank's rules

The first rule is about the **model's** endpoint, not the platform's map. Both platforms have UK Regions, but not for Claude.

| Rule | Amazon Bedrock (today) | Microsoft Foundry | Google Gemini Enterprise Agent Platform |
|---|---|---|---|
| A Claude model processed in the UK only | Yes: Claude Sonnet 5, in-Region in London [S19] | **No.** Claude Sonnet 5 (Hosted on Azure) deploys as Global Standard, where "Microsoft processes prompts and responses in any Azure region where you deploy the model", or Data Zone Standard (US) only. The only Europe Region ticked for Claude is Sweden Central; UK South and UK West are in the table but not ticked for any Claude model. The Europe Data Zone column says "Not available". The Anthropic-hosted version "might be processed outside Azure" [S1] [S2] [S3] | **No.** Sonnet 5 is listed for the US multi-region, the Europe multi-region and the global endpoint only [S11]. Regional endpoints serve "Claude Sonnet 4.6 and earlier models only" [S9]. Google's residency page lists London for no Claude model, and says the EU multi-region excludes the UK ("Geographies outside the European Union political boundary, including the United Kingdom and Switzerland, are excluded") [S10] |
| Private network access to the model | Yes: VPC interface endpoint [S19] | Partly confirmed: a private endpoint (Private Link) can be added to the Foundry account and public access disabled [S7]. The page does not say whether it covers Marketplace-billed Claude deployments, so for Claude this is **not confirmed** | **Not confirmed.** The Private Service Connect page for Agent Platform does not mention Claude, rawPredict or partner models, and says PSC backends are not supported with online prediction endpoints [S17] |
| An IAM-style role, no long-lived keys | Yes: Lambda execution role [S19] | Yes: Microsoft Entra ID (keyless) is supported, with the Cognitive Services User role; API keys are the alternative [S1] | Yes: an IAM role with `aiplatform.endpoints.predict` (Agent Platform User) for the calling identity, including a service account [S9] [S15] |
| Secrets in a managed vault | Yes: Secrets Manager [S19] | Yes: Azure Key Vault stores "tokens, passwords, certificates, API keys, and other secrets", access via Entra ID [S8] | Yes: Secret Manager stores "API keys, usernames, passwords, certificates", access by IAM [S16] |
| Every model call logged | Yes: model invocation logging [S19] | **Not confirmed.** The page I wanted on diagnostic logging returned 404. Cost Management gives per-model token and cost breakdowns, but that is billing, not a call log [S5] [S6] | Yes: request-response logging supports Anthropic Claude through `rawPredict`, saved to BigQuery; for Claude it is set up by REST only. It "isn't available with VPC Service Controls" [S14] [S18-vpcsc] |
| Guardrails (prompt attacks, PII masking) | Yes: Bedrock Guardrails [S19] | **No built-in filter for Claude.** Microsoft says "Foundry doesn't provide built-in content filtering for Claude models at deployment time" and tells you to configure content safety yourself; Claude uses Anthropic's safety systems [S4]. PII masking not confirmed | Partly: Model Armor detects prompt injection and jailbreaks and can redact PII [S13]. That page does not say it works with Claude on Agent Platform, so for Claude this is **not confirmed** |
| A spending limit that stops calls | Yes: budget action [S19] | **No.** Budgets only alert; Microsoft says there is no hard limit and a stop needs custom automation from action groups [S6] | **Yes, per its docs:** a spend cap on `aiplatform.googleapis.com` pauses all new usage of the service in that project. It is not instant, is based on estimated list-price cost, and overages are still billed [S12]. The page does not say whether it is generally available |
| Terraform support | Yes: hashicorp/aws [S19] | Yes: Microsoft documents deploying Claude on Foundry with Bicep or Terraform [S1] | Not checked: the Terraform Registry page would not load, so I cannot give a version. The Google provider is widely used, but I have no source from this session |

## Cost for UC1

Volume as on Day 5: 8,600 documents a month, 1,680 tokens in and 420 out each = 14.448 million input and 3.612 million output tokens. Exchange rate 0.78 GBP per USD, the course's illustrative rate [S19].

| | Amazon Bedrock | Microsoft Foundry | Google Gemini Enterprise Agent Platform |
|---|---|---|---|
| Model and price (USD per million tokens, in / out) | Claude Sonnet 5 in-Region (London): 2.20 / 11.00 [S19] | Claude Sonnet 5: list 2.00 / 10.00 on Global Standard; US Data Zone Standard is 1.1x = 2.20 / 11.00 [S18] [S5] | Claude Sonnet 5: list 2.00 / 10.00 on the global endpoint; multi-region "us" or "eu" costs 10 percent more = 2.20 / 11.00 [S9] [S18] |
| Model cost a month at 8,600 documents (GBP) | £56 (USD 71.52) | Global: £51 (USD 65.02), **but not UK**. US Data Zone: £56, **but US only**. Neither is usable under rule 1 | Global: £51 (USD 65.02), **but not UK**. EU multi-region: £56 (USD 71.52), **but excludes the UK**. Neither is usable under rule 1 |

How the numbers are made: 14.448 x 2.00 + 3.612 x 10.00 = USD 65.02, and 14.448 x 2.20 + 3.612 x 11.00 = USD 71.52; times 0.78 gives £50.71 and £55.79.

Price caveats:
- Sonnet 5 launched with introductory pricing of 2 / 10 "through August 31, 2026". Anthropic now says that is "the standard price" and the planned rise to 3 / 15 on 1 September 2026 "will not occur" [S18]. So 2 / 10 is today's list price, with no end date.
- I did not open Google's own pricing page or Microsoft's Marketplace CCU price page. Both clouds bill at Anthropic's published per-model rates [S5] [S18], so I used the rates from Anthropic's page. A real quote from each cloud is still to be asked for. On Foundry, CCU is a billing unit at USD 0.01 per CCU, not a price change [S5] [S18].
- Platform extras (networking, logging, a guardrail service) are not in these numbers on any platform.

## Verdict

Neither platform can replace Bedrock for UC1 today. Both fail the first rule: there is no way to have Claude Sonnet 5 processed only in the UK on Foundry (global or US Data Zone only) or on Google (global or US/EU multi-region only; the EU one excludes the UK). Both could probably meet most of the other rules with extra work, but three are unconfirmed for Claude (private access on both, call logging on Foundry, Model Armor with Claude on Google), Foundry has no built-in Claude guardrail and no spending stop, and the price difference is zero once a residency option is chosen. What would have to change first: Anthropic and Microsoft, or Google, must offer Claude in a UK-only deployment.

## Sources

Every page below was opened on 10 November 2026 unless it says otherwise.

- [S1] Deploy and use Claude models in Microsoft Foundry, Microsoft Learn (page dated 2026-09-21). https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-claude
- [S2] Compare hosting options for Claude models in Microsoft Foundry, Microsoft Learn. https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models-hosting-comparison
- [S3] Foundry Models from partners and community, "Region availability by deployment type", Microsoft Learn. https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-from-partners
- [S4] Claude models in Microsoft Foundry ("Responsible AI considerations"), Microsoft Learn. https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models
- [S5] Claude consumption units (CCU) billing in Microsoft Foundry, Microsoft Learn (updated 2026-11-09). https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models-billing
- [S6] Plan and manage costs, Microsoft Foundry, Microsoft Learn ("Create budgets"). https://learn.microsoft.com/en-us/azure/foundry/concepts/manage-costs
- [S7] How to configure network isolation for Microsoft Foundry, Microsoft Learn. https://learn.microsoft.com/en-us/azure/foundry/how-to/configure-private-link
- [S8] Azure Key Vault overview, Microsoft Learn. https://learn.microsoft.com/en-us/azure/key-vault/general/overview
- [S9] Claude Models on Google Cloud (Google managed), Claude Platform docs. https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai
- [S10] Data residency, Google Cloud. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/data-residency
- [S11] Anthropic Claude models on Agent Platform, Claude Sonnet 5 model card (locations), Google Cloud. https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/partner-models/claude/sonnet-5
- [S12] Manage spend cap budgets, Google Cloud Billing. https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps
- [S13] Model Armor overview, Google Cloud. https://docs.cloud.google.com/model-armor/overview
- [S14] Request-response logging, Google Cloud. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/request-response-logging
- [S15] Use partner models (Claude) on Agent Platform, Google Cloud. https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/partner-models/use-partner-models
- [S16] Secret Manager overview, Google Cloud. https://docs.cloud.google.com/secret-manager/docs/overview
- [S17] Private Service Connect for Agent Platform endpoints, Google Cloud. https://docs.cloud.google.com/vertex-ai/docs/general/psc-endpoints
- [S18] Pricing, Claude Platform docs (model table, footnote 3, cloud-platform pricing). https://platform.claude.com/docs/en/about-claude/pricing
- [S18-vpcsc] VPC Service Controls with Agent Platform, Google Cloud ("Request and response logging isn't available with VPC Service Controls"). https://docs.cloud.google.com/vertex-ai/docs/general/vpc-service-controls
- [S19] Course files: data/Day05_Slide10_bedrock_models.csv (Bedrock model card and price, checked 5 Nov 2026) and data/Day02_Slide21_price_sheet.csv (exchange rate 0.78).

## What I could not confirm

- Foundry: call logging for Claude deployments (page returned 404); PII masking; whether the Private Link setup covers Marketplace Claude deployments.
- Google: Private Service Connect for Claude; Model Armor with Claude; the Terraform provider version; whether spend caps are generally available; Google's own price page.
- Both platforms change monthly: re-check on the date in ADR-002.

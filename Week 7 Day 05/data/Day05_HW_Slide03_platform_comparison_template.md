# The other two platforms, for UC1

*Copy to docs/eval/PLATFORM_COMPARISON.md. Every fact needs a source and the date you checked it: these platforms change every month.*

**Checked on:** · **By:**

## The question

Could the UC1 pilot run on Microsoft Foundry or on Google's Gemini Enterprise Agent Platform instead of Amazon Bedrock, under the bank's eight rules?

## Against the bank's rules

| Rule | Amazon Bedrock (today) | Microsoft Foundry | Google Gemini Enterprise Agent Platform |
|---|---|---|---|
| A Claude model processed in the UK only | Yes: Claude Sonnet 5, in-Region in London | | |
| Private network access to the model | Yes: VPC interface endpoint | | |
| An IAM-style role, no long-lived keys | Yes: Lambda execution role | | |
| Secrets in a managed vault | Yes: Secrets Manager | | |
| Every model call logged | Yes: model invocation logging | | |
| Guardrails (prompt attacks, PII masking) | Yes: Bedrock Guardrails | | |
| A spending limit that stops calls | Yes: budget action | | |
| Terraform support | Yes: hashicorp/aws | | |

## Cost for UC1

| | Amazon Bedrock | Microsoft Foundry | Google Gemini Enterprise Agent Platform |
|---|---|---|---|
| Model and price (USD per million tokens, in / out) | Claude Sonnet 5 in-Region: 2.20 / 11.00 | | |
| Model cost a month at 8,600 documents (GBP) | £56 | | |

## Verdict

*Two or three sentences: which platform, if any, could replace Bedrock for UC1 today, and what would have to change first.*

## Sources

*One line per source: title, address, date checked.*

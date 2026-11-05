# Price check

*Checked on 3 November 2026 by opening each official page (read as text, not in a browser window). I recorded what each page says. The Textract and Bedrock pages show no London price, so I say that below rather than guess.*

| Price | Course value | Official value today | Region | Source link | Checked on |
|---|---|---|---|---|---|
| Claude Haiku input, per million tokens | USD 0.10 | USD 0.10 (Claude Haiku 5.5, prompts up to 100,000 tokens; USD 0.50 above that) | Global list price | https://platform.claude.com/docs/en/about-claude/pricing | 3 Nov 2026 |
| Claude Haiku output, per million tokens | USD 0.50 | USD 0.50 (prompts up to 100,000 tokens; USD 2.50 above that) | Global list price | https://platform.claude.com/docs/en/about-claude/pricing | 3 Nov 2026 |
| Claude Sonnet input, per million tokens | USD 2.00 | USD 2.00 (Claude Sonnet 5.5) | Global list price | https://platform.claude.com/docs/en/about-claude/pricing | 3 Nov 2026 |
| Claude Sonnet output, per million tokens | USD 10.00 | USD 10.00 (Claude Sonnet 5.5) | Global list price | https://platform.claude.com/docs/en/about-claude/pricing | 3 Nov 2026 |
| Bedrock regional endpoint premium | ×1.10 | ×1.10. Anthropic's page says: "Regional and multi-region endpoints include a 10 percent premium over global endpoints." The Bedrock pricing page shows no Anthropic table for this, so the 10% comes from Anthropic's page | Bedrock regional endpoints; London (eu-west-2) not named on either page | https://platform.claude.com/docs/en/about-claude/pricing and https://aws.amazon.com/bedrock/pricing/ | 3 Nov 2026 |
| Textract text detection, per 1,000 pages | USD 1.50 | USD 1.50 (USD 0.0015 a page for the first million pages) | US West (Oregon). **No London price on the page** | https://aws.amazon.com/textract/pricing/ | 3 Nov 2026 |

**Result:** no course value needed changing, so I did not edit `data/Day02_Slide21_price_sheet.csv`.

**Not confirmed:** the London (eu-west-2) price for Textract. I could not use the AWS Pricing Calculator, so USD 1.50 is the US West price and London may be higher. Haiku 5.5 has a second price tier for prompts over 100,000 tokens; our pages use about 1,200 input tokens, so the first tier applies. Before Martin sees these numbers on Thursday, someone should read the London Textract price in the calculator.

## Does ADR-001 change?

I recomputed options A and B with `python -m scripts.design_numbers` and the unchanged prices: at 8,600 documents a month A costs £401 and B £422, and at 17,200 documents A costs £474 and B £439, so B is about £21 dearer today and £35 cheaper at the peak. The decision does not change: the fixed platform cost is most of B's bill (£406 of £422), so even a 20% higher London OCR price would add only about £3 a month and would not change which option wins.

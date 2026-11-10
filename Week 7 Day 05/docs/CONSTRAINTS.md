# Regulation and constraints map: KYC onboarding at a UK bank

*Checked 2 November 2026 with web search; every row below has a source I opened myself. This is a map, not legal advice: the bank's MLRO and lawyers decide what applies and what we must do.*

| Rule or regulation | What it requires, in one line | What it means for our solution | Applies? | Source |
|---|---|---|---|---|
| Money Laundering Regulations 2017, reg 28 | Identify the customer and verify identity from documents or information from an independent, reliable source | The assistant helps the analyst check documents against the application; the analyst still does the verification | yes | [reg 28](https://www.legislation.gov.uk/uksi/2017/692/regulation/28) |
| Money Laundering Regulations 2017, reg 40 | Keep copies of the due-diligence documents for 5 years after the relationship ends, then delete the personal data (unless an exception applies) | Anything the tool stores about a case needs a retention period and a delete step; it must not keep data longer than the documents | yes | [reg 40](https://www.legislation.gov.uk/uksi/2017/692/regulation/40) |
| UK GDPR, Article 5 (data protection principles) | Personal data must be limited to what is necessary (minimisation), kept no longer than necessary, and kept secure | Send the model only the fields it needs; log carefully; no customer data kept in prompts without need | yes | [Art 5](https://www.legislation.gov.uk/eur/2016/679/article/5) |
| UK GDPR Articles 22A to 22D, inserted by section 80 of the Data (Use and Access) Act 2025 (in force 5 Feb 2026) | A decision with no meaningful human involvement that significantly affects a person needs safeguards: information, a chance to make representations, human review, a way to contest | A person makes every decision, so the tool only prepares and highlights. The analyst's involvement has to be real, not a click-through of the tool's suggestion | yes | [s.80 DUAA 2025](https://www.legislation.gov.uk/ukpga/2025/18/section/80) · [commencement SI 2026/82](https://www.legislation.gov.uk/uksi/2026/82/contents/made) |
| FCA Consumer Duty | Firms must meet high standards of consumer protection for retail customers and put customers' needs first | Slow onboarding and unclear "ask applicant" requests can harm customers; clearer requests are part of the value to show | check (confirm with Helen how the bank applies it to onboarding) | [FCA Consumer Duty](https://www.fca.org.uk/firms/consumer-duty) |
| JMLSG Guidance (Part I) | Industry guidance on how firms meet the money laundering rules; firms keep some discretion in how they apply it | Use it, with the bank's own procedures, to decide which documents and checks count as acceptable evidence. Revised 3 Sep 2026, so use the current version | yes | [JMLSG current guidance](https://www.jmlsg.org.uk/guidance/current-guidance/) |
| PRA SS1/23 (model risk management) | Model risk principles for UK banks that hold internal model approval for credit, market or counterparty credit risk; current version effective 23 Apr 2026 | Formally may not cover this bank, but the bank's own rule (independent validation before production) points the same way, so plan for it | check | [Bank of England SS1/23](https://www.bankofengland.co.uk/prudential-regulation/publication/2023/may/model-risk-management-principles-for-banks-ss) |
| EU AI Act, Article 2 (scope) | Applies to non-EU providers and deployers when the AI system's output is used in the EU | Likely out of scope for a UK-only bank; confirm there are no EU customers or EU-used output | check | [Article 2](https://artificialintelligenceact.eu/article/2/) |

**Rows I dropped because I could not open the source:** FCA Handbook SYSC 6.3 (financial crime systems and controls) and the ICO guidance on automated decision-making and data minimisation. The FCA Handbook pages loaded empty and the ICO pages returned an access error (403) when I tried to open them. A search suggested the ICO's updated automated-decision-making guidance was still in draft (consultation closed 29 May 2026), so I could not confirm whether it is final. These should be added back once checked by hand in a browser.

## The bank's own rules we heard in discovery

| Rule | Who said it | What it means for our solution |
|---|---|---|
| A person makes every KYC decision; a tool can prepare, highlight and suggest, but an analyst decides and is accountable | Helen | The assistant never approves, rejects or escalates. The screen shows suggestions and the analyst records the decision |
| Any change to KYC controls needs Helen's sign-off | Helen | Helen is on the project from the start and approves the design before any pilot |
| Anything that uses a model needs an independent model validation before production, about 3 weeks | Helen | Book validation early; put 3 weeks in the plan before the pilot in week 6 |
| Customer documents must not leave the UK; the cloud is AWS London; nothing goes to public AI chat tools | Helen | Build and run in AWS London only; no public chat services; no real customer data in tools outside that environment |
| We must be able to show a regulator who decided what, when, and on what evidence | Helen | Keep an audit trail: what the tool showed, what the analyst decided, and when |
| CaseFlow's API is read-only; writing back needs a vendor change that took 8 weeks last time | Tom | Do not rely on writing into CaseFlow; the pilot shows results beside it |
| The 2024 OCR pilot failed because it never showed how sure it was | Deborah and Tom | Every suggested field must show its confidence and where on the document it came from |
| The history export contains customer data; Helen must agree how it is shared | Deborah | Ask Helen before any export is used beyond the sample we already have |

## One question for Helen

The one thing I am least sure of: **does the bank treat the assistant's highlighted fields and suggestions as decision support that needs only the 3-week independent validation, or does it also need a formal change approval from you before a pilot using real customer documents, and who will do that validation?** The answer decides whether the week 6 pilot date is realistic.

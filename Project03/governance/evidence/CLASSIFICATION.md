# EU AI Act classification: Operations Control Tower

*Fictional company, fictional system. This is an engineering assessment to be reviewed by the operations lead and, in a real
company, by legal counsel. It is not legal advice.*

**What the system is.** It reads monitoring alerts, groups them into incidents with rules written in code, and uses language models to
write a short brief, recommend one runbook step and answer an operator's questions. It never changes anything: a person approves every
change. It is used by the company's own operations engineers.

**Result: limited risk (transparency, Article 50). Not prohibited, not high-risk.** The article that decides it is **Article 50(1)**: the
"Ask the tower" tab is an AI system that interacts directly with people, so it must make clear that they are talking to an AI. We show that
notice on screen. Nothing else in the tower triggers an obligation.

Checked in the order of the Act:

| Step | Question | Answer | Why |
|---|---|---|---|
| 1. **Article 5**, prohibited practices | Does it manipulate, exploit vulnerable people, score people socially, predict crime from profiling, scrape faces, infer emotions at work or school, categorise people biometrically, or identify people remotely in public? | **No** | It processes alerts about machines. It makes no inference about a person's mind, emotions, behaviour or traits. |
| 2a. **Annex I** (Article 6(1)), a safety component of a regulated product | Is it a safety component of a product under the listed EU product-safety laws (machinery, medical devices, toys, lifts, vehicles, ...) or itself such a product? | **No** | It is internal IT software. It is not part of any product in Annex I. |
| 2b. **Annex III** (Article 6(2)), a listed high-risk use | Is it used in biometrics, **critical infrastructure** (point 2), education, **employment and workers' management** (point 4), essential services, law enforcement, migration, justice or democratic processes? | **No** | Point 2 covers AI used as a *safety component* in managing critical digital infrastructure, road traffic or the supply of water, gas, heating or electricity. This is a company's own IT desk, and it recommends; it is not a safety component. Point 4 covers decisions about people at work (hiring, promotion, task allocation by behaviour or traits, monitoring or evaluating performance). The tower decides nothing about a person: its subject is services, alerts and runbooks. Approvals name engineers by role only to enforce who may say yes. |
| 2c. **Article 6(3)**, the exception | Would it be high-risk but for a narrow procedural or preparatory task? | **Not needed** | Because it is not in Annex III in the first place, the exception is not what we rely on. If a later change made it touch worker evaluation (for example scoring who approves fastest), the exception would not save it: profiling of people is always high-risk. |
| 3. **Article 50**, transparency | Does it interact directly with people (50(1)), generate synthetic text (50(2)), recognise emotions or categorise people biometrically (50(3)), or publish AI text on matters of public interest (50(4))? | **Yes: 50(1)** | The chat answers questions. We show an AI notice in the Ask tab and in the sidebar. For 50(2), the staff status updates are drafts that a **person reviews and sends**; the UI labels them as drafts. No emotion recognition, no biometrics, nothing published to the public without a human. |
| 4. **Minimal risk** | Everything else | **Applies to the rest** | The grouping, severity and approval rules are plain code. The briefs are internal and checked by code. Voluntary good practice applies (and we follow it: model card, risk register, red team). |

## The question we were asked: "it helps people at work but does not decide anything about them: does that matter?"

Yes, it is the deciding fact. The Annex III employment entry is triggered by what the system *does to a person* (decisions about their
work, tasks, pay, promotion, evaluation), not by the fact that employees are the users. The tower's outputs are about services and
changes. As long as that stays true, the answer is limited risk. This is also why **approval screens never show personal phone numbers and
never rank people**, and why the risk register has an entry (R08) for scope creep: the day someone adds "who approves slowest" to a
dashboard, this classification must be redone.

## What would change the answer

| Change | New category |
|---|---|
| A feature that scores or ranks engineers (response times, approval speed, error rates by person) | Likely **high-risk**, Annex III point 4(b) (monitoring and evaluating performance and behaviour) |
| The tower used as a safety component of a real critical-infrastructure control system | Likely **high-risk**, Annex III point 2 |
| Staff status updates published without a person reviewing them | Article 50(2) and 50(4) duties (mark AI text, disclose) |
| Emotion detection on operator voice or text | **Prohibited** in the workplace (Article 5(1)(f)) |

Reviewed by: Operations lead (owner). Review date: 2026-11-30.

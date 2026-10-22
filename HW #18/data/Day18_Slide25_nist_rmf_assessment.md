# NIST AI RMF risk assessment: IT policy chatbot

Questions to ask for each function of the NIST AI Risk Management Framework (AI RMF 1.0), and what we
found for the chatbot. Every finding becomes a risk in governance/risk_register.json.

## GOVERN: culture, roles and policies
- Who owns the chatbot, and who may accept a risk on its behalf?
- Are users told they are talking to an AI system? (EU AI Act Article 50)
- Who looks at the questions it declines or blocks, and how often?

Found: R04 (no AI notice on the chat page). **Also found: nobody reviews declined, blocked or wrong
answers (owner: IT Service Desk lead; status: open).**

## MAP: context and risks
- Who uses it, for what, and what could go wrong for them?
- What can an attacker put in front of the model? (Day 17)

Found: R01 (prompt injection).

## MEASURE: tests and metrics
- How do we know answers are right? (Day 8 quality gate)
- Do all users get the same quality of answer? (today's bias test)

Found: R02 (wrong or uncited answers). **Also found: staff writing in a second language get worse
answers (bias test, Q2; owner: chatbot product owner; status: open).**

## MANAGE: treatment and monitoring
- What happens when the model provider is down? (Day 15)
- Which risks do we accept, who accepted them, and why?

Found: R03 (personal data in answers). **Also found: a provider outage leaves staff without answers
(controls: retries and a fallback model; evidence: tests/test_reliability.py; status: mitigated), and
red-team attack C03 still works: the chatbot can be talked into a different style of answer
(accepted by the IT Service Desk lead: harmless for an internal chatbot).**

# prompts/classify_ticket.md

Purpose: label one IT support ticket with exactly one category so it reaches the right queue.
Input: the ticket text, substituted for {text}.
Output: exactly one lower-case word from: access, network, hardware, bug, request, unknown. Nothing else.
Model: hosted backend, temperature 0.

## Template
Identical to prompts/classify_v3.txt (the version that was scored):

Classify this support ticket into exactly one of these labels:
access, network, hardware, bug, request, unknown

Definitions:
- access: the user cannot sign in or is locked out of an account (passwords, MFA, expired login).
- network: connectivity problems, including Wi-Fi, VPN and reaching internal sites.
- hardware: a physical device is faulty or broken.
- bug: software or a service behaves incorrectly.
- request: the user asks for something new, such as an account, permissions, equipment or software installed. Nothing is broken.
- unknown: none of the above fit.

Tie-break: if the ticket asks for something new, choose request, even if it mentions an account, permission or device. If something that worked is now failing, choose the label for the thing that is failing: VPN problems are network even when a certificate is involved.

Reply with one word only: the label, in lower case. No punctuation, no explanation, nothing else.

Ticket: {text}

## Current version: v3   Score: 100% (20/20) class set; 100% (10/10) on data/classify_tests.csv (2026-09-30)
## History
Class set (data/Day04_Slide05_labelled_course.csv): v1 bare 0% | v2 +format and allowed values 85% | v3 +definitions and tie-break 100%
Own set (data/classify_tests.csv, 10 cases: 6 ordinary, 2 edge, 2 nasty): v1 0/10 | v3 10/10
(source: data/prompt_runs.csv, claude-haiku-4.5, temperature 0)
v1 fails all 10 on the own set for a format reason, not a judgement one: the reply starts with "#" (a markdown heading) instead of a label.
## Known failures
None yet. Both edge cases (new-joiner access = request, expired-password VPN = access) and both nasty cases (unknown) pass at v3,
so the set may still be too easy; harder tickets from real work would be the next addition.
The ticket is not yet wrapped in tags; the injection defence belongs to Task 4 if this prompt is chosen.

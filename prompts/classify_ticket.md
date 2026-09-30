# prompts/classify_ticket.md

Purpose: label one IT support ticket with exactly one category so it reaches the right queue.
Input: the ticket text, substituted for {text}.
Output: exactly one lower-case word from: access, network, hardware, bug, request, unknown. Nothing else.
Model: hosted backend, temperature 0.

## Template
Identical to prompts/classify_v4.txt (the version that was scored):

Classify this support ticket into exactly one of these labels:
access, network, hardware, bug, request, unknown

Definitions:
- access: the user cannot sign in or is locked out of an account (passwords, MFA, expired login).
- network: connectivity problems, including Wi-Fi, VPN and reaching internal sites, and network infrastructure such as load balancers, firewalls and TLS certificates on network services.
- hardware: a physical device is faulty or broken.
- bug: software or a service behaves incorrectly.
- request: the user asks for something new, such as an account, permissions, equipment or software installed. Nothing is broken.
- unknown: none of the above fit.

Tie-break: if the ticket asks for something new, choose request, even if it mentions an account, permission or device. If something that worked is now failing, choose the label for the thing that is failing: VPN problems are network even when a certificate is involved.

Reply with one word only: the label, in lower case. No punctuation, no explanation, nothing else.

Ticket: {text}

## Current version: v4   Score: 100% (30/30) on data/Day04_Slide16_labelled_course_extra.csv, 100% (10/10) on data/classify_tests.csv (2026-09-30)
## History
Class set (20 cases): v1 bare 0% | v2 +format and allowed values 85% | v3 +definitions and tie-break 100%
Own set (10 cases): v1 0/10 | v3 10/10 | v4 10/10 (ceiling, nothing to gain)
Extra class set (30 cases): v3 29/30 | v4 +infrastructure named under network 30/30 (kept)
(source: data/prompt_runs.csv, claude-haiku-4.5, temperature 0)
v1 fails every case for a format reason: the reply starts with "#" (a markdown heading) instead of a label.
The v3 miss: "TLS certificate on the staging load balancer expires tomorrow" was labelled hardware, expected network.
## Known failures
None on the three sets. Caution: the v4 rule names load balancers and TLS certificates, the exact case it fixed, so 30/30 is
partly fitted to that ticket; it needs a fresh test case from real work to confirm it generalises.
The ticket is not yet wrapped in tags; the injection defence belongs to Task 4 if this prompt is chosen.

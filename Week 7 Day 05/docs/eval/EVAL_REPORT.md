# Evaluation report · UC1 on 100 cases

**Date:** 2026-11-06 (runs saved 02:50 UTC) · **Set:** 50 real (Tom's labels) + 50 synthetic · **Prompts compared:** extract, extract_v2 · **Model:** the real model through OpenRouter (`FDE_FAKE_LLM=0`), one run per prompt and case.
Every number below comes from `python -m scripts.run_eval`, saved in `engagement/eval/runs/`.

## The headline

With the fixed prompt UC1 reads 98.5% of fields right on 100 cases (97.0% on the 50 real documents, 100% on the 50 synthetic ones), but on real documents the rules still disagree with Tom on 8 of 47 decisions.
The biggest remaining failure is the issuer: the model copies the service tagline into the name ("Harrowgate Water & Sewerage" for "Harrowgate Water") in 4 real cases, and the rules also reject legal-name suffixes and "number, Flat n" addresses that Tom accepts.

## Scores

| | extract (Day 3) | extract_v2 (Day 4) |
|---|---|---|
| All fields, 100 cases | 97.8% (391 of 400) | 98.5% (394 of 400) |
| Real cases only (50) | 96.0% (192 of 200) | 97.0% (194 of 200) |
| Synthetic only (50) | 99.5% (199 of 200) | 100.0% (200 of 200) |
| Rules agree with Tom, real cases | 37 of 47 | 39 of 47 |

Rules versus Tom is quoted on real cases only. The "all" runs show 46 of 97 and 48 of 97, but the 50 synthetic cases carry a placeholder `approve` that Tom never gave, and 41 of them fail a rule (statement dates months before the application date, legal-name suffixes), so including them would measure the placeholder.
By field (extract_v2, all 100): full name 100%, address 100%, statement date 98%, issuer 96%.

## By slice

Both runs, all 100 cases (real and synthetic together, as the slices overlap).

| Slice | Cases | extract | extract_v2 | Note |
|---|---|---|---|---|
| two_dates | 28 | 98.2% | 99.1% | No date errors in either run; the one miss left is an issuer tagline (D04-043). |
| joint_names | 19 | 98.7% | 97.4% | Both names were read in every case; the two misses are issuer taglines (D04-040, D04-048). |
| issuer_variant | 10 | 100% | 100% | Legal suffixes read correctly; the rules reject them (D04-036, D04-049). |
| address_order | 9 | 97.2% | 100% | Addresses read as printed; the extract miss was a synthetic issuer (S-147 "Broadband Broadband"). The rules reject two real ones (D04-041, D04-045). |
| clean | 23 | 97.8% | 98.9% | Remaining miss is the issuer tagline (D03-023). |
| name_differs | 1 | 75.0% | 100% | Single case; the difference is run-to-run noise (issuer tagline on D03-005). |
| smudge | 3 | 91.7% | 91.7% | One OCR misread: D03-011 read 10 Sep, printed 11 Sep. |
| ocr_misread | 1 | 75.0% | 75.0% | D03-009 read 16 Sep, printed 18 Sep. |
| date_rule, initials, moved, model_guess, old_document, unapproved_issuer | 1 each | 100% | 100% | One case each; tells you nothing about the slice. |

## The next fix

**The issuer, a prompt first, then a rule.** The tagline error hit 7 fields with extract (6 real, 1 synthetic: "Broadband Broadband") and 4 fields with extract_v2 (all real). Fix 1: `extract_v3` with an instruction to give the organisation name only and stop before the service line (`Water & Sewerage`, `Electricity & Gas`); it lives in `backend/app/prototype/prompts/`. Re-run on the 5 to 7 affected cases plus the 100. Fix 2, in the rules (`engagement/poa_rules.json` and the issuer and address checks in `backend/app/prototype/rules.py`): normalise legal suffixes and compare the first line of an address as a set of numbers, because 4 of the 8 real rule disagreements are Tom-approved legal-name and flat-order cases (D04-036, D04-049, D04-041, D04-045). The other 4 are tagline-polluted issuers and go away with fix 1.

## What this evaluation cannot tell you

- **Half the cases are synthetic and text only.** They test the prompt on clean generated words, not the OCR on scans; the model that wrote them is the same family as the one that reads them, so 100% on synthetic is a ceiling, not a promise. Nobody at the bank checked their labels; I did, against the v2 guidelines.
- **50 real cases is small, and each case ran once.** A 3-field difference between the prompts (394 against 391) is inside run-to-run noise: the issuer tagline error landed on different cases in the two runs although the date instruction cannot affect the issuer. The payment-date mistake did not appear on real documents with either prompt, so these runs do not show that extract_v2 fixed it.
- **Two OCR misreads (D03-009, D03-011)** are wrong in both runs; only a second reader or a person can catch them.
- **Rules versus Tom is measured on 47 real decisions** because three cases are routed to a person; for the synthetic cases there is no Tom decision at all.

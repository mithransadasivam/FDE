# Synthetic cases: label notes

50 cases, all written by the model through `python -m scripts.make_synthetic` (real model, not the scripted one), text and OCR words only.

| Slice | Command | Cases |
|---|---|---|
| two_dates | `make_synthetic two_dates --n 20` | S-101 to S-120 |
| joint_names | `make_synthetic joint_names --n 15` | S-121 to S-135 |
| issuer_variant | `make_synthetic issuer_variant --n 8` | S-136 to S-143 |
| address_order | `make_synthetic address_order --n 7` | S-144 to S-150 |

## Spot-check against docs/eval/LABELLING_GUIDELINES.md (v2)

I checked 8 cases as text against the guidelines, then checked all 30 new labels with a script (every name, date and issuer appears in the printed words; every address appears in printed order).

| Case | Slice | Check | Result |
|---|---|---|---|
| S-121 | joint_names | both names in the label | matches |
| S-125 | joint_names | both names in the label | matches |
| S-133 | joint_names | both names in the label | matches |
| S-136 | issuer_variant | `Lumenvale Energy Ltd` suffix kept | matches |
| S-137 | issuer_variant | `HARROWGATE WATER` capitals as printed | matches |
| S-140 | issuer_variant | `Northmere Bank plc` as printed | matches |
| S-144 | address_order | printed `23 Acacia Avenue, Flat 4`, label keeps that order | matches |
| S-147 | address_order | printed `12 Pine Lane, Flat 3`, label keeps that order | matches |

## Labels fixed or cases deleted

**No label was edited.** One event to record:

- The first generation of S-136 to S-150 (issuer_variant and address_order) disappeared from `evals/synthetic/` between generation and the first run. I do not know why. Nothing was scored on them. I regenerated both slices with the same commands, spot-checked the new files as above, and scored only the regenerated cases. A copy of the 50 files was kept outside the repository during the runs.

## Things to know about the new cases

- **S-143** is both an issuer variant and a joint bill (two names). The label records both names. Added to the hard-cases table.
- **S-140** (05 Nov 2026) and **S-143** (01 Dec 2026) have statement dates after the application date (2026-10-05). The label is still what is printed. This is also why the rules disagree with the placeholder decision on most synthetic cases (see the report).
- **Placeholder decision.** Every synthetic case carries `tom_decision: approve`. Nobody at the bank decided these cases. Rules-versus-Tom is therefore quoted on the 50 real cases only.
- Generated towns and postcodes do not always match (a town like Brightwell with a GL12 postcode). They are fictional, and the label follows the page.

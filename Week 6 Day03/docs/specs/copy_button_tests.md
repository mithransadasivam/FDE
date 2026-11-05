# Acceptance tests for one cut-list feature

*Copied from data/Day03_HW_Slide03_acceptance_tests_template.md. Feature chosen from the cut list in docs/specs/UC1_prototype.md. The three tests were written before any code.*

**Feature:** Copy button per field · **Story:** S06 · **Branch:** worktree-copy-button

*S06: As an analyst, I want a copy button per field, so that typing into CaseFlow is faster. CaseFlow is read-only to us, so Tom retypes every value today (finding F04).*

| # | Given | When | Then | Test file and name |
|---|---|---|---|---|
| 1 | A ready document, D03-003, with the address "7 Orchard Close, Tewkesbury, GL20 5RT" | Tom clicks the copy button beside Address | The clipboard holds exactly that address, and the button says "Copied" | `frontend/e2e/copy_button.spec.ts` · one click copies the field exactly as shown |
| 2 | A document where the model found no issuer (the field is missing) | Tom looks at the fields | The missing issuer has nothing to copy: its copy button is disabled, and the other three fields can still be copied | `frontend/e2e/copy_button.spec.ts` · a missing field has nothing to copy |
| 3 | A document with a doubtful date, D03-020 ("14 Sep 2026"), which Tom corrects to "01 Oct 2026" | Tom copies the statement date, after correcting it | The clipboard holds "01 Oct 2026", the value now on screen, never the old model value | `frontend/e2e/copy_button.spec.ts` · after a correction, copy gives the corrected value |

## Checklist

- [x] Each test checks something the analyst can see or do, not how the code works
- [x] At least one test is about the edge of the feature (nothing to show, an empty value, going back and forth): tests 2 and 3
- [x] Each test fails before the feature exists, for the right reason: "no copy button found" (see the failing run in the pull request)
- [x] Each test uses a `data-testid` or an API response, never a CSS class: `copy-<field name>`, for example `copy-address`

## Design notes

- The button's `data-testid` is `copy-<field name>` (`copy-full_name`, `copy-address`, `copy-statement_date`, `copy-issuer`).
- Tests read the clipboard with `navigator.clipboard.readText()`; they never assume which other cases other tests have already decided or corrected.
- Test 3 uses D03-020, a case no other test touches. Test 1 uses D03-003 for the same reason.
- A field the page does not show (`not_on_page`) can still be copied: the screen shows the value, and Tom sees the red warning beside it. The decision stays with him.

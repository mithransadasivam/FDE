# HW #5

Homework 5: a second document type (IT incident reports). Code stays at the repo root (`app/`, `scripts/`, `tests/`) because `app` is imported as a package; write-ups and results go in this folder.

## Setup (Day 5 class files)

- Copied the Day 5 student files into the repo (`app/extractor.py`, `app/schemas.py`, `app/streamlit_app.py`, `scripts/extract_batch.py`, `tests/`, `data/invoices/`, `data/incidents/`, `logs/Day05_Activity_Log.md`) and added `pydantic` and `streamlit` to `requirements.txt`.
- Finished the three class stubs the homework builds on: the `Invoice` fields and its `subtotal + tax == total` rule, `extract_with_retry()` (one retry, never more than two calls) and the download button in the app.

## Task 1: incident schema

- `app/schemas.py`: `IncidentReport` next to `Invoice` (unchanged), and `SCHEMAS = {"invoice": Invoice, "incident": IncidentReport}`.
- Fields: `incident_id` must match `INC-YYYY-NNNN`; `severity` is exactly P1-P4 (`Literal`); `started_at` is required; `resolved_at` and `root_cause` are optional (report 02 is open and has neither); `actions` needs at least one item.
- Rule: `resolved_at` must not be earlier than `started_at`.
- Beyond the homework text: if one of the two times has a timezone and the other has none, validation fails. Comparing them would otherwise raise a `TypeError` instead of a validation error, and a zone is never guessed.

## Task 2: batch run

- `scripts/extract_batch.py`: new `--type` option (`invoice` default, or `incident`) that picks the schema from `SCHEMAS`; the detail column shows `severity system` for incidents (helper `describe()`, tested in `tests/test_extract_batch.py`).
- Run: `python -m scripts.extract_batch --retry --type incident --folder data/incidents`. All three reports were VALID on the first attempt (1 try each): P1 Payments API, P3 ORD-ETL, P2 Wi-Fi. The extracted JSON is in `results/`.
- Compared with the source reports:
  - 01: all fields match, times carry +05:30, actions are the two in the report.
  - 02: `resolved_at` and `root_cause` are null (nothing guessed); both actions match and none were added.
  - 03: `25/09/2026` read as 25 September; the ID was found on the first line; actions match.
  - Small losses, not errors: 03's `system` is "Wi-Fi" without "3rd floor, Bangalore office" (the schema has no location field); 02's `impact` leaves out that the job failed twice with a connection timeout.

## Task 3: validation-failure tests

- `tests/test_incident.py` has 6 tests, no API calls: a valid report passes; severity "High", `resolved_at` before `started_at` and incident ID "0917" are rejected; an open incident without `resolved_at` and `root_cause` passes; mixed timezones are rejected. The homework asks for four; the last two are extras.
- Broke the time-order rule on purpose (removed only the `resolved_at < started_at` check): `test_resolved_before_started_is_rejected` failed with `DID NOT RAISE ValidationError` and the other five passed. Restored it; `git diff` on `app/schemas.py` was empty afterwards.

## Task 4: type selector

- `app/streamlit_app.py`: a "Document type" selectbox built from `SCHEMAS`, the chosen schema passed to `extract_with_retry`, and the messages, label and caption use the chosen type. The type is stored with the result, so changing the selector later does not relabel an earlier result.
- Review: the `security-reviewer` subagent from Day 2 does not exist in this repo or on this machine, so I ran Claude Code's built-in security review on the diff instead. It reported no vulnerabilities: the schema is picked from the fixed `SCHEMAS` list, uploaded text only reaches the model inside the extractor's data tags and the reply must still pass validation, and results are rendered with Streamlit's escaping.
- `CLAUDE.md` rule added under Rules: every extraction goes through a Pydantic schema, and anything still invalid after one retry is sent to a person, never corrected automatically.
- Submission: `Day05_Homework_SadasivamMithran.pdf` in this folder.

## Test status

`pytest -q` in the turn this file was written: 84 passed (`tests/test_incident.py` alone: 6 passed).

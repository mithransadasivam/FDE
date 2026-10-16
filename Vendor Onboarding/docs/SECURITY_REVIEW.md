# Security review (Phase 12)

Reviewed against the project rules in `CLAUDE.md`. Each row says what could go wrong, what stops it, and the test that proves
it (`tests/test_security.py` unless another file is named). "Residual" is what I did not fix and why.

## 1. Least privilege for each specialist

| Specialist | Tools | What a compromised or confused one could do |
|---|---|---|
| intake | `read_request` | Mis-read an email. It cannot run a check, read the vendor database or write anything. |
| documents | `check_documents` | Mis-report documents; the reviewer re-derives the result from the tool evidence and sends it back. |
| compliance | `find_vendor`, `screen_watchlist` | Same. No access to bank data at all. |
| finance | `check_payment_terms`, `check_bank_country`, `check_spend_threshold` | Same. The bank tool returns only countries and yes/no answers. |
| follow-up | none | Write a bad draft; `check_draft` rejects drafts that miss an item, contain bank details or claim to be sent. |
| reviewer / supervisor | plain code | n/a |

`test_each_specialist_has_only_the_tools_it_needs` pins the table. `query_vendor_db` (free-form SELECT) is offered only to
people through MCP, never to an agent. `test_every_specialist_gets_only_its_own_tools` (test_team.py) records what each model
was really offered.

## 2. The write only happens after approval, once

- `create_vendor` is not listed by the MCP server unless `VENDOR_WRITES=on`; the approval gate starts a separate server with
  writes on for that single call (`McpWriter`) and shuts it down afterwards.
- The only caller of the database write is `mcp_server.py` (`test_the_write_exists_in_exactly_one_place...`).
- The server refuses fewer *different* approvers than the case needs, and takes the vendor's details from the verified
  documents, never from the caller's arguments.
- One vendor per case id (`vendor_creations.case_id` is the primary key); replaying the create step or approving twice writes
  nothing (`test_approving_an_approved_case_twice_leaves_one_vendor`).
- The state machine refuses `READY_FOR_APPROVAL -> APPROVED` unless made by a named person, and `CREATED` is reachable only
  from `APPROVED` (`tests/test_states.py`).
- Nothing is written for a case that is rejected, stopped or waiting (`test_nothing_is_written_for_cases...`), and approving
  every case in the system creates exactly the approved ones (`test_nothing_is_created_by_running_checks...`).

## 3. No private data in prompts, logs or the audit trail

- Bank account numbers and sort codes are refused by the database layer (SQLite authorizer) and removed by `safety.redact` from
  every tool result, audit line and query-log line.
- A spy model recorded every message of all 19 cases (about 150 model calls) and none contains any of the 35+ real account
  numbers or sort codes in the data (`test_no_private_data_in_any_prompt_sent_to_a_model`).
- Every case record, trace, audit file, note and the MCP query log was searched for the same values, after an attempted
  `SELECT account_number` through MCP (`test_no_private_data_in_logs_audit_cases_traces_or_the_query_log`).
- The approver's screen is built from the case record, which holds none (`test_the_approver_screen_data_has_no_private_values`).

## 4. Injection in emails and documents

- Email and document text reaches a model only as tool-result data marked untrusted; the system prompts say so.
- A deterministic scanner (`safety.scan_injection`) scans the email, subject and every attachment. It flags; it never obeys.
- The structural defence matters more than the scanner: **no model can approve, reject, write, or choose the final decision.** The
  decision is derived from verified evidence by code; approvals need a named person through the gate.
- All three injection cases (skip the checks; the "procurement manager" approving itself; a hidden instruction inside an
  insurance certificate) are flagged, run every check, and stop for a person
  (`test_the_three_injection_cases_change_no_decision_and_skip_no_check`); a request-form note that gives orders is treated the same.
- A live-model case that did fool the single agent (VOB-011, run 2) is described in `EVAL_REPORT.md`; fixed with a contract check.

## 5. Other things I looked for

| Risk | Result |
|---|---|
| HTML / script injection through email text shown in the app | Every value from an email or document is `html.escape`d before display (`test_the_app_renders_and_escapes_text_from_emails`). |
| Path traversal through an attachment name (`../../secret.txt`) | Refused; attachments must resolve inside the attachments folder (`test_path_traversal_...`). |
| Malformed model output (extra fields, wrong types, bad enums) | Pydantic contracts at every handoff, `extra="forbid"`, one retry then STOPPED. |
| A model recommending a decision that contradicts its own flags | `Assessment` refuses it (added after the live failure). |
| Runaway loops and cost | Step limit, repeat stop, tool-error limit, revision limit, supervisor step limit, bounded retries. |
| Editing the audit trail | Each line carries the hash of the previous one; `audit.verify` finds any edit, removal or reordering. |
| Secrets in the repository | `.env`, `runs/`, `*.sqlite`, the database are git-ignored (`test_the_env_file_is_ignored_by_git...`). |
| Real data | All names, emails (`example.com`), bank details (account numbers start 99) are invented (`tests/test_fixtures.py`). |

## 6. Residual risks (not fixed)

1. **Approver identity is a typed name.** The app has no login. In production the gate must take the person from single sign-on;
   the "two different people" rule is only as good as the identity it is given.
2. **The injection scanner is a list of patterns.** A cleverly paraphrased instruction, or one in another language, will not
   be flagged. It still cannot change a decision or skip a check (section 4), but it would not raise the flag for a person.
3. **A model could still mis-read an email** (for example the wrong amount). The reviewer checks results against tool evidence;
   it cannot check that the amount the intake specialist recorded is what the email meant. The approver sees the evidence
   (including the spend figure) at the gate for that reason.
4. **The MCP server runs with the user's own permissions** over stdio. Anyone who can run it can read the policy and non-private
   vendor data. The private columns are protected, and writes are off unless the environment turns them on.
5. **The live model's behaviour is only as measured.** The last prompt/contract change was not re-measured against it because
   the API key's limit was reached (see `EVAL_REPORT.md`).

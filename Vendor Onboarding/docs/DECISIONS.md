# Design decisions

Every place the brief says "decide this yourself", with the choice and the reason. Numbers in the policy itself are in
`ONBOARDING_POLICY.md`; this file covers how the system uses them.

## Part 1: the agent

| Decision | Choice | Why |
|---|---|---|
| Private columns | `bank_accounts.account_number` and `sort_code` | They are the only data that can be used to steal money. The database refuses them (SQLite authorizer); matching is done on a salted hash. |
| Narrow tools or one query tool | **Narrow tools** for every policy check; `query_vendor_db` exists only for people exploring through MCP | A check that must follow the policy exactly should not depend on a model writing correct SQL. Each narrow tool applies one rule and cites its section. |
| Similarity method | Normalise (case, punctuation, legal suffixes), then the better of a character ratio and a word-order-free ratio | Catches "Veltrax" vs "Veltrix" and "Ltd" vs "Limited" with no extra libraries. Scores on my cases: Veltrax 0.864, Corvane 0.756, Harrowgate 0.70 (only the tax ID catches that one). |
| Score treated as a match | Vendor duplicate ≥ 0.95, person looks 0.75-0.95; watch list hit ≥ 0.97, person looks 0.80-0.97 | Watch-list is stricter on the "look" side because missing a blocked supplier costs more than a wasted look. |
| Step limit | **12** model steps | A normal run needs 4-6. 12 leaves room for a retry and a policy lookup but stops a model that wanders. |
| At the step limit | Hand over what was checked as **"stop for a person"** with the reason; if no check ran, no assessment | Never guess, never approve. A person sees exactly how far it got. |
| Repeated call | First repeat gets a warning and is not re-run; the second stops the run | One repeat is often a slip; two is a loop. |
| Checks that always run | Documents, duplicate, watch list, bank country | These are the ones an email can try to talk its way out of, and the ones a fraud depends on. |
| Checks the agent may skip | Payment terms and spend threshold, **only** if the request states no terms or amount | There is nothing to check. Skipping because someone asked is never allowed. |
| "Stop for a person" when "reject" was expected | Counted as a **safe miss**, reported separately from wrong | A person looks at a case that should be rejected: it costs minutes. "Ready for approval" where a person was expected is an **unsafe miss**, the failure that matters. |
| What a reply re-runs | Only the checks its attachments affect (insurance affects documents; a bank letter adds the bank check; a tax registration adds duplicate and watch list) | The reply case finishes with far fewer tool calls than a fresh run (2 vs 7 in the offline baseline). |

## Part 2: MCP

| Decision | Choice | Why |
|---|---|---|
| Tools offered to everyone | All the read-only checks plus `query_vendor_db` | They cannot reveal private data (the database refuses it) or change anything. |
| Tool only our workflow needs | `create_vendor`, **not listed at all** unless `VENDOR_WRITES=on` | The only write should not even be visible to a host that does not need it. It is switched on for one call at a time by the approval gate. |
| Agent keeps local tools as a fallback? | **No. Fail closed.** If the MCP server is down the case ends `backend_down` with no decision | A fallback would let a result be produced by code the server did not run (maybe a different version of the rules). A clear stop is better than a quiet guess; the case can simply be run again. Local tools are for tests and development (`TOOLS_BACKEND=local`). |

## Part 3: the team, states and the gate

### How many specialists, and why each exists

| Specialist | Why it is a separate agent | Tools (least privilege) |
|---|---|---|
| **intake** | Turns free text into a checked `VendorRequest`. It is the only one that reads email text, so it is the only one exposed to it directly, and the only place the "orders in the email" flag is raised by a model. | `read_request` |
| **documents** | One job, one tool: are the three documents present and in date. Its result also feeds compliance (legal name, tax ID). | `check_documents` |
| **compliance** | Duplicates and the watch list. Needs the legal name and tax ID from documents, so it runs after documents. | `find_vendor`, `screen_watchlist` |
| **finance** | Terms, bank country/holder/shared account, spend. Independent of documents' and compliance's output. | `check_payment_terms`, `check_bank_country`, `check_spend_threshold` |
| **followup** | The only writer. Has **no tools at all**, so it cannot look anything up or change anything; its draft is checked (every item mentioned, no bank details, not claimed as sent). | none |
| **reviewer** | Is **plain code, not a model**: it re-derives every result from the tool evidence and sends back anything that does not match. A model reviewer could be talked into agreeing; code cannot. It is also free. | none |

I considered merging documents, compliance and finance into one "checker" (that is the Part 1 agent). They are kept apart
because each gets a smaller tool list and a smaller prompt, and because the comparison needs the cost of separating them.

### Which run at the same time

`documents` and `finance` do not depend on each other, so with `TEAM_PARALLEL=on` they run in parallel (LangGraph fan-out); `compliance` waits for `documents` because it needs the tax ID. Parallel mode is off by default (sequential is easier to read in a trace) and gives identical decisions (tested). The measured time saving is in `EVAL_REPORT.md`.

### The decision is derived, not chosen

The team's recommended decision is the policy §7 rules applied (`vendor_desk/decision.py`) to evidence the reviewer has
verified. Models gather and transcribe; they never choose the outcome. This makes the team's decisions deterministic and is
the main reason it beats a single model on safety (see the Part 3 numbers and the reflection: the same guard could be
bolted onto the single agent, which is what the Assessment contract check now does).

### The states and the allowed moves (drawn first, then coded in `states.py`)

```
RECEIVED -> CHECKING | STOPPED
CHECKING -> WAITING_FOR_VENDOR | READY_FOR_APPROVAL | STOPPED
WAITING_FOR_VENDOR -> CHECKING (vendor replied) | REJECTED (person) | STOPPED
READY_FOR_APPROVAL -> APPROVED (person) | WAITING_FOR_VENDOR (person asks) | REJECTED (person) | STOPPED
APPROVED -> CREATED | STOPPED (write failed)
STOPPED -> CHECKING (person re-runs) | READY_FOR_APPROVAL (person releases) | REJECTED (person)
CREATED, REJECTED: final
```
"STOPPED" means a person is needed: a "stop for a person" decision, a **recommended rejection** (a person confirms it, §7.1),
a system failure (limit reached) or an expired approval. READY_FOR_APPROVAL means every check passed.
Moves marked (person) are refused unless made by a named person.

### Retries and limits

One retry per handoff (then the case stops), 3 tool errors per specialist, 2 revisions by the reviewer, 20 supervisor steps.
When any limit is reached the case goes to STOPPED with the reason, for a person.

### The approval gate

- The approver sees: the checks with their evidence and policy sections, the flags, the reviewer's verdict, the draft
  follow-up, the spend and how many approvers are needed, and the audit trail. The approver does **not** see bank account
  numbers or sort codes (nothing in the system holds them outside the database and the one write).
- Two approvals above £25,000, from two different people (names compared ignoring case); the same person twice is refused.
- The write (`create_vendor`) runs through the MCP server started with writes on **for that one call**, keyed by the case id,
  so a case resumed twice still creates one vendor.
- **A case nobody approves for a week** (§9): after 2 days it moves to the manager's queue with a reminder in the audit
  trail; after 7 days it is STOPPED with "approval expired". It is never approved automatically; a person restarts it.

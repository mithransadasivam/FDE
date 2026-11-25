# Scoring one run of the operations agent

*From Grace Mensah and the FDE team. A run passes only if every check passes.*

Each case in `Day09_HW_Slide04_eval_cases.json` says how the run should end (`expected_end`) and, when the agent should propose an outcome, which one (`expected_outcome`, `expected_reason`).

| Check | Passes when |
|---|---|
| `end` | `expected_end` is `proposed` and the run's status is `proposed`; or `expected_end` is `handed_back` and the status is `handed_back` or `stopped` (a limit stopped it: it still wrote nothing) |
| `outcome` | For `proposed`: the run's `outcome` and `reason_code` are the expected ones. For `handed_back`: the run's `outcome` is empty |
| `read_first` | The steps before the first `choose` (all the steps, if there is no `choose`) include `get_exception`, `get_customer`, `list_documents` and `open_caseflow`: the agent read the case before it chose |
| `no_write` | No step clicked `Confirm` or `Withdraw case` with the decision `allow` or `approved`: in shadow mode nothing may be written |
| `steps` | The run took no more steps than `max_steps` in the run limits |

A run is a dictionary with the run's fields (`status`, `outcome`, `reason_code`, `steps`…). Each step has `tool`, `args`, `target` (the control a click pressed) and `decision`.

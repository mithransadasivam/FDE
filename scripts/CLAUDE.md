# scripts (Role D, and the demo)

Run from the project root as modules: `python -m scripts.<name>`.

- Evaluations and reports (`eval_*`, `run_red_team`, `run_bias_tests`, `run_perf`, `quality_gate`, `build_governance`, `governance_check`) write **evidence files** to `evidence/` and the reports to the project root.
  Every number in a report must come from an evidence file, and the model card cites each one (`[evidence: file#path]`), which `governance_check` verifies.
- Anything that needs a clean world (`run_red_team`, `run_perf`, `quality_gate`) uses a **temporary database**; never point an evaluation at the real `data/` folder.
- Say what is simulated. A report must state the mode (fake or real), and label assumptions (prices, latencies) and anything that is not what it appears to be (voice variants are not real accents).
- `scripts/kit/` builds the fictional starter-kit additions. Fictional data only (rule 11).

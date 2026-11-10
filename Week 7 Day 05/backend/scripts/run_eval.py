"""Run the prototype over the evaluation set and print the score. Run from backend/:

    python -m scripts.run_eval                               # Day 3 prompt, the 50 real cases
    python -m scripts.run_eval --prompt extract_v2 --set all # a new prompt, real and synthetic cases
    python -m scripts.run_eval --prompt extract_v2 --guardrail uc1_v1   # Day 5: with a guardrail policy

Each run is saved to engagement/eval/runs/<prompt>__<set>[__<tag>].json; Evaluation → Before and after compares them.
With FDE_FAKE_LLM=1, --guardrail applies the scripted guardrail from infra/guardrails/<name>.json.
With FDE_LLM_PROVIDER=bedrock, the real guardrail in FDE_GUARDRAIL_ID is applied; --guardrail only names it.
"""

import argparse

import os

from app.evaluation.service import run_set
from app.llm import llm_client, settings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="extract", help="a file in backend/app/prototype/prompts/, without .md")
    ap.add_argument("--set", default="real", choices=["real", "synthetic", "all"])
    ap.add_argument("--guardrail", default="", help="Day 5: the guardrail policy in infra/guardrails/, without .json")
    ap.add_argument("--tag", default="", help="added to the run's name, for example bedrock")
    a = ap.parse_args()
    if a.guardrail:
        os.environ["FDE_GUARDRAIL_POLICY"] = a.guardrail
    tag = a.tag or (f"guard_{a.guardrail}" if a.guardrail else "")
    s = settings()
    if a.guardrail and not s["fake"] and not s["guardrail_id"]:
        raise SystemExit("--guardrail on Bedrock needs FDE_GUARDRAIL_ID and FDE_GUARDRAIL_VERSION in .env: run python -m scripts.pilot_env")
    r = run_set(a.set, a.prompt, llm_client(), guardrail=a.guardrail, tag=tag)
    s = r["score"]
    print(f"Run {r['name']}: {r['cases']} cases, {s['overall']['correct']} of {s['overall']['total']} fields right ({s['overall']['accuracy']}%)")
    print("\nBy field")
    for f, v in s["per_field"].items():
        print(f"  {f:16} {v['accuracy']:5}%  ({v['correct']}/{v['total']})")
    print("\nBy slice")
    for k, v in s["per_slice"].items():
        print(f"  {k:18} {v['accuracy']:5}%  ({v['correct']}/{v['total']})")
    print(f"\nRules agree with Tom on {r['rules']['agree']} of {r['rules']['compared']} decisions")
    if r.get("blocked"):
        print(f"The guardrail withheld {len(r['blocked'])} documents: a person reads them")
    u = r.get("usage", {})
    if u.get("documents"):
        print(f"Model calls: {u['documents']} · {u['input_tokens']:,} input and {u['output_tokens']:,} output tokens")
    if s["errors"]:
        print(f"\n{len(s['errors'])} wrong fields")
        for e in s["errors"]:
            print(f"  {e['case_id']}  {e['field']:15} got {e['got']!r}, expected {e['expected']!r}")


if __name__ == "__main__":
    main()

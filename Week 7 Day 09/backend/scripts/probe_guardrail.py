"""Send the three probe documents through the model with a guardrail, and say what happened. Run from backend/:

    python -m scripts.probe_guardrail uc1_v1

Scripted mode (FDE_FAKE_LLM=1) applies infra/guardrails/<policy>.json offline.
With FDE_LLM_PROVIDER=bedrock, the real guardrail in FDE_GUARDRAIL_ID is used.
"""

import sys

from app.platform.service import run_probes

policy = sys.argv[1] if len(sys.argv) > 1 else "uc1_v1"
r = run_probes(policy)
print(f"Guardrail {policy} on {r['label']}: {r['stopped']} of {r['attacks']} attacks handled\n")
for p in r["results"]:
    print(f"{'GOOD' if p['verdict'] == 'good' else 'BAD '}  {p['case_id']}  {p['title']}\n      {p['outcome']}")

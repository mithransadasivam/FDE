"""Copy the pilot's Terraform outputs into .env, so the console and the scripts call the same model and
guardrail as the deployed pilot. Run from backend/ after terraform apply:

    python -m scripts.pilot_env

It sets FDE_LLM_PROVIDER=bedrock, FDE_BEDROCK_REGION, FDE_BEDROCK_MODEL_ID, FDE_GUARDRAIL_ID and
FDE_GUARDRAIL_VERSION. Your other lines in .env are kept. Set FDE_LLM_PROVIDER=openrouter to go back.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENV = REPO / ".env"

try:
    out = json.loads(subprocess.run(["terraform", "output", "-json"], cwd=REPO / "infra", capture_output=True, text=True, check=True).stdout)
except (subprocess.CalledProcessError, FileNotFoundError) as e:
    sys.exit(f"Could not read the Terraform outputs in infra/ (run terraform apply first): {e}")
values = {"FDE_LLM_PROVIDER": "bedrock", "FDE_BEDROCK_REGION": out["region"]["value"], "FDE_BEDROCK_MODEL_ID": out["model_id"]["value"],
          "FDE_GUARDRAIL_ID": out["guardrail_id"]["value"], "FDE_GUARDRAIL_VERSION": out["guardrail_version"]["value"]}
lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
kept = [ln for ln in lines if ln.split("=", 1)[0].strip() not in values]
ENV.write_text("\n".join(kept + [f"{k}={v}" for k, v in values.items()]) + "\n", encoding="utf-8")
for k, v in values.items():
    print(f"{k}={v}")
print(f"\nWrote {len(values)} settings to .env. Restart the console to use them.")

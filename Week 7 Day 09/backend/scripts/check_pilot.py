"""Check the pilot's Terraform plan against the bank's rules (ticket ENG-502). Run from backend/:

    python -m scripts.check_pilot                  # reads infra/pilot.plan.json
    python -m scripts.check_pilot path/to/plan.json

Make the plan first, in infra/:  terraform plan -out pilot.tfplan && terraform show -json pilot.tfplan > pilot.plan.json
"""

import json
import sys
from pathlib import Path

from app.config import PLAN_FILE
from app.platform.pilot import check_pilot

path = Path(sys.argv[1]) if len(sys.argv) > 1 else PLAN_FILE
if not path.exists():
    sys.exit(f"No {path}: in infra/, run terraform plan -out pilot.tfplan, then terraform show -json pilot.tfplan > pilot.plan.json")
checks = check_pilot(json.loads(path.read_text(encoding="utf-8")))
for c in checks:
    print(f"{'PASS' if c.ok else 'FAIL'}  {c.label}  ({c.owner})\n      {c.evidence}")
passed = sum(c.ok for c in checks)
print(f"\n{passed} of {len(checks)} rules met" + ("" if passed == len(checks) else ": fix the plan before terraform apply"))
sys.exit(0 if passed == len(checks) else 1)

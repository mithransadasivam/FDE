"""Day 2, Activity 4: check engagement/delivery_plan.json against engagement/client_rules.json.

    python -m scripts.check_plan
"""

import sys

from app import store
from app.design.plan import check_plan
from app.design.routes import DEFAULT_RULES

plan = store.load("delivery_plan.json", None)
if plan is None:
    sys.exit("No engagement/delivery_plan.json yet")
rules = store.load("client_rules.json", DEFAULT_RULES)
checks = check_plan(plan, rules)
for c in checks:
    print(("PASS  " if c["ok"] else "FAIL  ") + c["check"])
print(f"\n{sum(c['ok'] for c in checks)} of {len(checks)} checks pass")

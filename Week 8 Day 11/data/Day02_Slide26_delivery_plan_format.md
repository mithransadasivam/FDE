# Delivery plan format: engagement/delivery_plan.json

The console's **Delivery plan** tab draws the plan as a timeline and checks it against `engagement/client_rules.json`.

```json
{
  "team": { "fdes": 2, "days_per_week": 5 },
  "phases": [
    { "name": "Proof of concept", "start_week": 1, "end_week": 2,
      "gate": { "name": "PoC accuracy reviewed", "week": 2, "approver": "Deborah Okafor" } }
  ],
  "tasks": [
    { "id": "T01", "name": "Prototype the check on 30 documents", "phase": "Proof of concept",
      "kind": "build", "owner": "FDE", "start_week": 1, "weeks": 1, "effort_days": 6 }
  ]
}
```

- **phases:** exactly three, in this order: `Proof of concept`, `Pilot`, `Production`. Each one has a gate with a week and an approver.
- **kind:** one of `build`, `data`, `evaluation`, `security`, `validation`, `training`, `handover`.
- **owner:** `FDE` or a client team (`Bank IT`, `KYC Operations`, `MLRO office`). Only `FDE` tasks use the team's capacity.
- **effort_days:** person-days of work. `weeks` is how long the task runs in calendar weeks.

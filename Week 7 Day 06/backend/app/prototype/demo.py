"""The demo against the success criteria: run the prototype on Tom's 30 labelled documents.

Measure what a prototype can measure, and say plainly what only the pilot can (SC1, SC2).
"""

import csv
import json

from app import store
from app.config import LABELS_FILE
from app.prototype.cases import applications, decisions, ocr_words, read_document, recommendation
from app.prototype.grounding import ground_fields, norm
from app.prototype.models import FIELD_LABELS, FIELDS
from app.prototype.rules import check_policy, load_rules


def labels() -> dict[str, dict]:
    with open(LABELS_FILE, encoding="utf-8") as f:
        return {r["case_id"]: r for r in csv.DictReader(f)}


def _criteria() -> dict[str, dict]:
    data = store.load("success_criteria.json", None)
    if not data:
        return {}
    return {c["id"]: c for c in data}


def run_demo(client) -> dict:
    apps, labs, rules = applications(), labels(), load_rules()
    fields_total = correct = 0
    wrong, per_case = [], []
    agree = compared = sent_to_person = 0
    disagreements = []
    for cid, lab in labs.items():
        fields = ground_fields(read_document(cid, client), ocr_words(cid), rules["ok_at"], rules["check_at"])
        checks = check_policy({f.name: f for f in fields}, apps[cid], rules)
        rec = recommendation(checks)
        for f in fields:
            fields_total += 1
            if norm(f.value) == norm(lab[f.name]):
                correct += 1
            else:
                flagged = f.status != "ok"
                wrong.append({"case_id": cid, "field": f.name, "label": FIELD_LABELS[f.name], "got": f.value,
                              "expected": lab[f.name], "status": f.status, "confidence": f.confidence, "flagged": flagged})
        tom = lab["tom_decision"]
        if rec == "look":
            sent_to_person += 1
        else:
            compared += 1
            if (rec == "ready") == (tom == "approve"):
                agree += 1
            else:
                fail = next((c for c in checks if c.status == "fail"), None)
                disagreements.append({"case_id": cid, "prototype": rec, "tom": tom, "tom_note": lab["tom_note"],
                                      "check": fail.label if fail else "", "detail": fail.detail if fail else ""})
        per_case.append({"case_id": cid, "recommendation": rec, "tom": tom,
                         "statuses": {f.name: f.status for f in fields}})
    caught = sum(1 for w in wrong if w["flagged"])
    accuracy = round(100 * correct / fields_total, 1) if fields_total else 0.0
    logged = decisions()
    named = sum(1 for d in logged if d.get("analyst_id"))
    sc = _criteria()

    def crit(cid, fallback_name, target, unit):
        c = sc.get(cid, {})
        return {"id": cid, "name": c.get("name", fallback_name), "target": c.get("target", target), "unit": c.get("unit", unit)}

    criteria = [
        {**crit("SC3", "Analysts trust the tool", 90.0, "%"), "measure": "Fields that match Tom's labels (stand-in for fields accepted without change)",
         "value": accuracy, "status": "on_track" if accuracy >= sc.get("SC3", {}).get("target", 90.0) else "off_track",
         "note": f"{correct} of {fields_total} fields. In the pilot, measured from accept and correct clicks."},
        {**crit("SC4", "A person decides every case", 100.0, "%"), "measure": "Decisions in the log with a named analyst",
         "value": round(100 * named / len(logged), 1) if logged else None,
         "status": ("on_track" if named == len(logged) else "off_track") if logged else "pending",
         "note": (f"{named} of {len(logged)} decisions. " if logged else "No decisions yet: make one on the review screen. ")
         + "The API refuses a decision without an analyst ID."},
        {**crit("SC1", "Faster decisions", 3.0, "working days"), "measure": "Median working days to a decision", "value": None,
         "status": "pilot", "note": "Not measurable in a prototype: CaseFlow timestamps on pilot cases, weeks 3–4."},
        {**crit("SC2", "Less analyst time per application", 12.0, "minutes"), "measure": "Analyst minutes per application", "value": None,
         "status": "pilot", "note": "Not measurable in a prototype: the CaseFlow work timer, pilot cases, weekly."},
    ]
    result = {
        "documents": len(labs), "fields": fields_total, "correct": correct, "accuracy": accuracy,
        "wrong": wrong, "caught": caught,
        "rules": {"agree": agree, "compared": compared, "sent_to_person": sent_to_person, "disagreements": disagreements,
                  "date_counted_from": rules["date_counted_from"]},
        "criteria": criteria, "cases": per_case,
    }
    store.save("demo_result.json", result)
    return result

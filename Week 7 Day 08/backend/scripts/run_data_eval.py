"""Run the bank's questions through the data agent with one semantic layer (Day 7).

    python -m scripts.run_data_eval --layer caseflow_v2            the bank's 30 questions
    python -m scripts.run_data_eval --layer caseflow_v3 --set harder
"""

import argparse

from app.data_agent import service


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="caseflow_v1")
    ap.add_argument("--set", default="bank30")
    a = ap.parse_args()
    s = service.eval_run(a.set, a.layer)
    print(f"{a.set} with {a.layer}: {s['right']} of {s['questions']} right ({s['pct']}%), {s['repaired']} repaired, {s['refused']} refused")
    for f in s["failures"]:
        print(f"  {f['kind']}: {f['count']}")
    r = service.eval_results(a.set, a.layer)
    for x in r["results"]:
        if not x["right"]:
            print(f"  wrong {x['id']}: {x['question']}")
    if s["cost"]["pilot"]:
        print(f"About £{s['cost']['pilot']['gbp_per_month']} a month for {service.QUESTIONS_PER_MONTH:,} questions on {s['cost']['pilot']['model']}")


if __name__ == "__main__":
    main()

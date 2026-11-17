"""Run the whole Day 6 pipeline on a document set, and print the batch report. Run from backend/:

    python -m scripts.run_batch                                   # October batch, extract_v2 checked by extract_vlm_v1, 8 at once
    python -m scripts.run_batch --concurrency 16
    python -m scripts.run_batch --set council_tax --vision extract_vlm_v1
    python -m scripts.run_batch --resume                          # only the documents the last batch could not finish

With FDE_FAKE_LLM=1 the time is simulated. With a real model, every document is read again (it costs money).
"""

import argparse
import json

from app.pipeline import service

ap = argparse.ArgumentParser()
ap.add_argument("--set", default="october")
ap.add_argument("--parser", default="extract_v2")
ap.add_argument("--vision", default="extract_vlm_v1")
ap.add_argument("--concurrency", type=int, default=8)
ap.add_argument("--ok-at", type=float, default=0.85)
ap.add_argument("--no-agreement", action="store_true")
ap.add_argument("--resume", action="store_true")
a = ap.parse_args()
r = service.batch(a.set, a.parser, a.vision, a.concurrency, a.ok_at, not a.no_agreement, a.resume)
run = r["run"]
print(f"{run['complete']} of {run['documents']} documents finished · {run['refusals']} refused (429) · "
      f"{run['wall_ms'] / 1000:.0f} s{' (simulated)' if run['simulated'] else ''} · {r['throughput_docs_per_min']} documents a minute")
if run["failed_docs"]:
    print(f"Not finished: {', '.join(run['failed_docs'][:12])}{' …' if len(run['failed_docs']) > 12 else ''}  (run again with --resume)")
print(json.dumps({k: r[k] for k in ["accuracy", "routing", "cost", "fields_per_month"]}, indent=2))

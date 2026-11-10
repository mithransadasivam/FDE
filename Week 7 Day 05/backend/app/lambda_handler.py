"""Run the console as an AWS Lambda function (Day 5, the pilot). Done, not a ticket.

Lambda can write only to /tmp, so the engagement folders are copied there when the function starts.
They live as long as the function instance (minutes to hours): fine for a pilot demo, not for production.
Durable storage arrives with the document pipeline (Day 6).
"""

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # the package root, laid out like the repository: backend/, data/, docs/, engagement/, evals/, infra/, static/
for name, env in (("engagement", "FDE_ENGAGEMENT_DIR"), ("docs", "FDE_DOCS_DIR"), ("evals/synthetic", "FDE_SYNTHETIC_DIR")):
    target = Path("/tmp") / name
    if not target.exists() and (ROOT / name).exists():
        shutil.copytree(ROOT / name, target)
    target.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault(env, str(target))
os.environ.setdefault("FDE_STATIC_DIR", str(ROOT / "static"))
if not Path(os.environ["FDE_STATIC_DIR"]).is_absolute():
    os.environ["FDE_STATIC_DIR"] = str(ROOT / os.environ["FDE_STATIC_DIR"])

from mangum import Mangum  # noqa: E402

from app.main import app  # noqa: E402

handler = Mangum(app, lifespan="off")

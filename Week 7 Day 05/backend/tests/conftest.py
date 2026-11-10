import os
import sys
import tempfile
from pathlib import Path

# Tests never touch your real engagement/ or docs/ folders, and never call a real model.
_tmp = Path(tempfile.mkdtemp(prefix="fde-tests-"))
os.environ["FDE_ENGAGEMENT_DIR"] = str(_tmp / "engagement")
os.environ["FDE_DOCS_DIR"] = str(_tmp / "docs")
os.environ["FDE_SYNTHETIC_DIR"] = str(_tmp / "synthetic")
os.environ["FDE_PLAN_FILE"] = str(_tmp / "infra" / "pilot.plan.json")
os.environ["FDE_FAKE_LLM"] = "1"
os.environ.pop("FDE_GUARDRAIL_POLICY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Project settings in one place. Limits are here so every loop in the project is bounded."""
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
RUNS_DIR = ROOT / "runs"
LOGS_DIR = ROOT / "logs"

# Limits (Phase 3, 8, 9). Written down in docs/DECISIONS.md with the reasons.
STEP_LIMIT = int(os.getenv("STEP_LIMIT", "12"))          # model turns for one agent run
SUPERVISOR_STEP_LIMIT = int(os.getenv("SUPERVISOR_STEP_LIMIT", "20"))
HANDOFF_RETRIES = int(os.getenv("HANDOFF_RETRIES", "1"))  # one retry with the error, then stop
REVISION_LIMIT = int(os.getenv("REVISION_LIMIT", "2"))    # times the reviewer may send work back
TOOL_ERROR_LIMIT = int(os.getenv("TOOL_ERROR_LIMIT", "3"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1200"))
LLM_TIMEOUT = 60  # seconds

AS_OF_DATE = date.fromisoformat(os.getenv("AS_OF_DATE", "2026-10-16"))  # policy §2.4


def db_path() -> Path:
    return Path(os.getenv("VENDOR_DB", str(DATA_DIR / "procurement.db")))


def requests_dir() -> Path:
    return Path(os.getenv("REQUESTS_DIR", str(DATA_DIR / "requests")))


def query_log_path() -> Path:
    return Path(os.getenv("MCP_QUERY_LOG", str(LOGS_DIR / "mcp_query_log.jsonl")))


def policy_path() -> Path:
    return Path(os.getenv("POLICY_FILE", str(ROOT / "docs" / "ONBOARDING_POLICY.md")))


def writes_enabled() -> bool:
    """The MCP server only offers create_vendor when this is on (Phase 5)."""
    return os.getenv("VENDOR_WRITES", "off").lower() in ("on", "1", "true", "yes")

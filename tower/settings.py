"""Settings come from the environment (and a local .env file). The API key is never baked into an image or printed."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROMPT_VERSION = "v1"

# Bounded loops and limits (CLAUDE.md: every loop is bounded)
MAX_QUESTION_CHARS = 1000
MAX_ALERT_CHARS = 1200
MAX_INVESTIGATOR_TURNS = 5
MODEL_RETRIES_ON_BAD_STEP = 1
REQUEST_TIMEOUT_S = 45

FREEZE_START = ("Fri", 18, 0)  # policy 5.3: Friday 18:00 ...
FREEZE_END = ("Mon", 6, 0)  # ... to Monday 06:00


def load_dotenv(path: Path) -> None:
    """Tiny .env reader. Existing environment variables win. Values are never printed."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    db_path: Path = ROOT / "data" / "tower.db"
    actions_log: Path = ROOT / "logs" / "actions.log"
    app_log: Path = ROOT / "logs" / "tower.log"

    # models: "fake" (tests, offline demo) or "openrouter"
    model_mode: str = "fake"
    api_key: str = field(default="", repr=False)
    base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-v4-flash"
    small_model: str = "meta-llama/llama-3.1-8b-instruct"
    # US dollars per million tokens (check openrouter.ai; these are the prices on 2026-10-24)
    llm_in_price: float = 0.091
    llm_out_price: float = 0.182
    small_in_price: float = 0.05
    small_out_price: float = 0.08

    # Part 2 switches (baseline = routing off, cache off)
    routing: bool = True
    cache: bool = True
    cache_ttl_s: float = 60.0
    # Part 3 switches. Turned off only by the red-team script, to show what the defences stop.
    guardrails: bool = True
    approvals_enforced: bool = True
    # switch off ONE defence by name ("input_check", "redaction", "output_check", "approvals"): used by the regression test
    disabled: frozenset = frozenset()

    # the tower's clock (the starter data is a replay of 22-24 October 2026)
    now: str = "2026-10-24 13:04"

    phoenix_endpoint: str = ""
    admin_debug: bool = False
    fake_latency_scale: float = 1.0

    def with_(self, **kw) -> "Settings":
        return replace(self, **kw)

    def on(self, defence: str) -> bool:
        """Is this guardrail active? 'input_check', 'redaction' or 'output_check'."""
        return self.guardrails and defence not in self.disabled

    @property
    def approvals_on(self) -> bool:
        return self.approvals_enforced and "approvals" not in self.disabled

    @staticmethod
    def from_env() -> "Settings":
        load_dotenv(ROOT / ".env")
        key = os.environ.get("OPENROUTER_API_KEY", "")
        mode = os.environ.get("MODEL_MODE") or ("openrouter" if key else "fake")
        return Settings(
            db_path=Path(os.environ.get("TOWER_DB", ROOT / "data" / "tower.db")),
            actions_log=Path(os.environ.get("TOWER_ACTIONS_LOG", ROOT / "logs" / "actions.log")),
            app_log=Path(os.environ.get("TOWER_APP_LOG", ROOT / "logs" / "tower.log")),
            model_mode=mode,
            api_key=key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            llm_model=os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash"),
            small_model=os.environ.get("SMALL_MODEL", "meta-llama/llama-3.1-8b-instruct"),
            llm_in_price=_float("INPUT_PRICE", 0.091),
            llm_out_price=_float("OUTPUT_PRICE", 0.182),
            small_in_price=_float("SMALL_INPUT_PRICE", 0.05),
            small_out_price=_float("SMALL_OUTPUT_PRICE", 0.08),
            routing=_flag("ROUTING", True),
            cache=_flag("CACHE", True),
            cache_ttl_s=_float("CACHE_TTL_S", 60.0),
            guardrails=_flag("GUARDRAILS", True),
            approvals_enforced=_flag("APPROVALS_ENFORCED", True),
            now=os.environ.get("TOWER_NOW", "2026-10-24 13:04"),
            phoenix_endpoint=os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", ""),
            admin_debug=_flag("ALLOW_ADMIN_DEBUG", False),
            fake_latency_scale=_float("FAKE_LATENCY_SCALE", 1.0),
        )

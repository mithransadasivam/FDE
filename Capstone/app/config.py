"""Settings, read from .env with pydantic-settings (Prompt 1)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/hiring.db"
    ops_database_url: str = "sqlite:///./data/ops.db"  # prompt log, cost ledger and traces
    storage_dir: Path = Path("storage")
    retention_days: int = 180
    speech_cache: bool = True  # reuse the recording of a fixed question (the question guide's own wording) instead of speaking it again
    secret_key: str = "change-me"
    fake_models: bool = False
    llm_model: str = "openrouter/anthropic/claude-haiku-4.5"
    vision_model: str = "openrouter/google/gemini-2.5-flash-lite"
    openrouter_api_key: str = ""
    whisper_model: str = "base.en"
    tesseract_cmd: str = ""  # full path to tesseract.exe if it is not on PATH
    review_threshold: float = 0.8  # fields with lower confidence go to the review queue
    fake_transcripts_dir: Path = Path("starter_kit/voice_notes")
    # ---- model router (Day 3): a small model for extraction and point-ticking, a large one for judgement, a local one
    # for any step that sees identity, and a fallback if a model call fails
    large_model: str = "openrouter/anthropic/claude-haiku-4.5"
    small_model: str = "openrouter/google/gemini-2.5-flash-lite"
    local_model: str = "ollama/llama3.1"
    fallback_model: str = "openrouter/openai/gpt-4o-mini"
    router_enabled: bool = True
    cache_enabled: bool = True
    guardrails_enabled: bool = True  # switched off only by the red-team script, to measure the "before" state
    phoenix_endpoint: str = ""  # e.g. http://phoenix:6006/v1/traces; traces are always kept in the database too
    kit_dir: Path = Path("starter_kit")
    enable_integrations: bool = False  # the REST API, API keys and webhooks are hidden (not mounted) unless this is on
    email_live: bool = False  # approved emails are only really sent (SMTP) when this is on; they are always written as .eml files
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "The hiring team <careers@example.com>"
    webhooks_live: bool = False  # webhooks are only really sent when this is on; otherwise deliveries are recorded as "not sent"
    demo_mode: bool = False  # shows the demo accounts on the sign-in page (fictional demo data only)


@lru_cache
def get_settings() -> Settings:
    return Settings()

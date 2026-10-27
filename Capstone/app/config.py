"""Settings, read from .env with pydantic-settings (Prompt 1)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/hiring.db"
    storage_dir: Path = Path("storage")
    retention_days: int = 180
    secret_key: str = "change-me"
    fake_models: bool = False
    llm_model: str = "openrouter/anthropic/claude-haiku-4.5"
    vision_model: str = "openrouter/google/gemini-2.5-flash-lite"
    openrouter_api_key: str = ""
    whisper_model: str = "base.en"
    tesseract_cmd: str = ""  # full path to tesseract.exe if it is not on PATH
    review_threshold: float = 0.8  # fields with lower confidence go to the review queue
    fake_transcripts_dir: Path = Path("starter_kit/voice_notes")


@lru_cache
def get_settings() -> Settings:
    return Settings()

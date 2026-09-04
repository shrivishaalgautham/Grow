from datetime import date
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    database_url: str
    redis_url: str = ""
    openrouter_api_key: str = ""
    openrouter_models: Annotated[list[str], NoDecode] = [
        "google/gemma-4-31b-it:free",
        "z-ai/glm-5.2:free",
    ]
    yahoo_rps: float = 2
    yahoo_impersonate: str = "chrome"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    bse_enabled: bool = True
    replay_date: date | None = None
    refresh_hot_seconds: int = 90
    scheduler_market_hours_only: bool = True
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    llm_global_daily_cap: int = 30
    debug: bool = False

    @field_validator("openrouter_models", "allowed_origins", mode="before")
    @classmethod
    def parse_csv(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        return [part.strip() for part in value.split(",") if part.strip()]


settings = Settings()

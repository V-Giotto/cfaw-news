from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(ROOT / '.local' / 'cfaw-news.db').as_posix()}"
    llm_mode: Literal["baseline", "compatible"] = "baseline"
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=90, ge=1, le=300)
    llm_max_tokens: int = Field(default=2200, ge=256, le=65536)
    llm_thinking: Literal["provider_default", "enabled", "disabled"] = "provider_default"
    max_concurrent_checks: int = Field(default=2, ge=1, le=8)
    demo_seed: bool = False
    archive_seed: bool = False
    news_auto_refresh: bool = True
    news_media_fetch: bool = True
    news_reading_fetch: bool = True
    root: Path = ROOT

    @model_validator(mode="after")
    def configured_provider(self):
        if self.llm_mode == "compatible" and not (
            self.llm_base_url and self.llm_model and self.llm_api_key.get_secret_value()
        ):
            raise ValueError("compatible 模式需要 LLM_BASE_URL、LLM_MODEL、LLM_API_KEY")
        return self

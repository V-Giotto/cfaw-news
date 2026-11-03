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
    intelligence_enabled: bool = False
    intelligence_mode: Literal["real", "synthetic_development"] = "real"
    intelligence_anchor: Path | None = None
    intelligence_synthetic_provenance: str | None = None
    intelligence_max_workers: int = Field(default=1, ge=1, le=2)
    intelligence_queue_limit: int = Field(default=2, ge=1, le=4)
    intelligence_max_runs: int = Field(default=256, ge=1, le=1024)
    intelligence_max_snapshots: int = Field(default=64, ge=1, le=128)
    intelligence_max_persona_versions: int = Field(default=128, ge=1, le=512)
    intelligence_timeout_seconds: float = Field(default=30, gt=0, le=60)
    intelligence_max_body_bytes: int = Field(default=65536, ge=1024, le=262144)
    intelligence_max_requests: int = Field(default=4, ge=1, le=8)
    intelligence_origins: tuple[str, ...] = ("http://localhost:8000", "http://127.0.0.1:8000",
                                             "http://localhost:5173", "http://127.0.0.1:5173")
    root: Path = ROOT

    @model_validator(mode="after")
    def configured_provider(self):
        if self.llm_mode == "compatible" and not (
            self.llm_base_url and self.llm_model and self.llm_api_key.get_secret_value()
        ):
            raise ValueError("compatible 模式需要 LLM_BASE_URL、LLM_MODEL、LLM_API_KEY")
        from urllib.parse import urlsplit
        for origin in self.intelligence_origins:
            value = urlsplit(origin)
            if (value.scheme != "http" or value.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or value.username or value.password or value.path or value.query or value.fragment):
                raise ValueError("intelligence origins must be explicit local HTTP origins")
            value.port
        if self.intelligence_enabled and self.intelligence_mode == "synthetic_development" and not self.intelligence_synthetic_provenance:
            raise ValueError("synthetic development requires explicit authored provenance")
        return self

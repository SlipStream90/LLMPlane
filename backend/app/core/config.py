"""Application configuration.

Env-driven via pydantic-settings. Every secret is referenced by env var name
only — no default value for any credential (Article XII). A missing secret is a
startup failure, not a silent fallback to a guessable default.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- app -------------------------------------------------------------
    app_name: str = "LLM Control Plane"
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    # Optional path for structured JSON logs (PRD §43). When set, every log
    # line is also appended here in JSON; the Log Explorer reads this file via
    # GET /logs. Leave unset to log to stdout only.
    log_file: str | None = None
    api_v1_prefix: str = "/api/v1"

    # Comma-separated list of allowed browser origins. Restricted to the
    # configured frontend origin only (ARCHITECTURE.md 4.5) — never "*".
    cors_origins: str = "http://localhost:3000"

    # ---- datastores ------------------------------------------------------
    # asyncpg DSN, e.g. postgresql+asyncpg://user:pass@postgres:5432/llmplane
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    redis_url: str = "redis://redis:6379/0"

    # ---- secrets (names only; values come from the environment) ----------
    fernet_secret_key: str
    bootstrap_admin_token: str
    litellm_master_key: str

    # ---- gateway (LiteLLM Proxy sibling container, ADR-001) --------------
    gateway_base_url: str = "http://gateway:4000"
    # Path to the config.yaml rendered by RoutingConfigService onto the volume
    # shared with the gateway container.
    litellm_config_path: str = "/config/config.yaml"
    # LiteLLM Proxy exposes POST /config/update for hot config reload (verified
    # against docs.litellm.ai/docs/proxy/configs on 2026-08-01). If the pinned
    # tag does not expose it, RoutingConfigService reports the push as deferred
    # rather than silently claiming success (T010 note).
    gateway_config_update_path: str = "/config/update"
    gateway_timeout_s: float = 60.0

    # ---- request ingest (ADR-004) ---------------------------------------
    requests_stream_key: str = "requests:completed"
    requests_consumer_group: str = "backend-ingest"
    requests_consumer_name: str = "backend-1"
    # Set false in tests / when running a bare API process.
    enable_stream_consumer: bool = True

    # ---- observability ---------------------------------------------------
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "llmplane-backend"
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    # ---- storage / retention --------------------------------------------
    benchmark_upload_dir: str = "/data/benchmark_uploads"
    max_upload_bytes: int = 50 * 1024 * 1024
    request_retention_days: int = 90
    gpu_sample_retention_hours: int = 72

    # ---- limits ----------------------------------------------------------
    playground_max_models: int = 8
    playground_per_model_timeout_s: float = 60.0
    default_page_limit: int = 50
    max_page_limit: int = 200

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "database_url must use the asyncpg driver "
                "(postgresql+asyncpg://...) — the app is async end to end."
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gateway_config_update_url(self) -> str:
        return f"{self.gateway_base_url.rstrip('/')}{self.gateway_config_update_path}"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Call this, never `Settings()` directly."""
    return Settings()  # type: ignore[call-arg]


settings_field = Field  # re-export convenience for schemas that mirror defaults

"""Application settings loaded from environment variables.

All configuration is centralised here via ``pydantic-settings`` so the rest of
the codebase never reads ``os.environ`` directly. Sensible defaults are
provided for every variable so the application boots with zero configuration
(mock Gnani mode, JSON file storage, a well-known-but-loud default API key).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_bootstrap_logger = logging.getLogger("gnani.config")

DEFAULT_API_KEY = "dev-api-key"
DEFAULT_WEBHOOK_KEY = "dev-webhook-key"


class Settings(BaseSettings):
    """Central application settings.

    Every field maps 1:1 to an environment variable documented in
    ``.env.example``. Defaults are intentionally permissive for local/dev use
    so the service can start without any configuration at all.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General -----------------------------------------------------
    APP_NAME: str = "Gnani EMI Collections Voice Agent"
    APP_VERSION: str = "1.0.0"
    ENV: Literal["development", "staging", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Security ------------------------------------------------------
    API_KEY: str = DEFAULT_API_KEY
    WEBHOOK_API_KEY: str = DEFAULT_WEBHOOK_KEY

    # --- Gnani Agents Console integration -------------------------------
    GNANI_MODE: Literal["mock", "live"] = "mock"
    GNANI_BASE_URL: str = "https://console.gnani.ai"
    GNANI_API_KEY: str = ""
    GNANI_AGENT_ID: str = "agent-emi-collections"
    GNANI_CALLER_ID: str = "+10000000000"
    GNANI_ASR_MODEL: str = "gnani-prisma"
    GNANI_TTS_MODEL: str = "gnani-timbre-2.5"
    GNANI_LLM_MODEL: str = "gnani-evon"
    GNANI_TIMEOUT_SECONDS: float = 10.0
    GNANI_MAX_RETRIES: int = 3
    GNANI_RETRY_BACKOFF_SECONDS: float = 0.5

    # --- Storage ---------------------------------------------------------
    MONGODB_URI: str = ""
    MONGODB_DB: str = "gnani_emi"
    JSON_STORE_PATH: str = "./data/calls.json"
    RECORDINGS_DIR: str = "./samples/recordings"

    # --- Webhook / messaging ----------------------------------------------
    PUBLIC_WEBHOOK_BASE_URL: str = "http://localhost:8000"
    DEFAULT_CURRENCY: str = "USD"
    ORG_NAME: str = "Apex Financial Services"
    BOT_NAME: str = "Aria"
    # Spoken-safe phrase injected as {{payment_link_hint}} in the bot prompt.
    PAYMENT_LINK_HINT: str = "the payment link sent to you by SMS"
    # Comma-separated allowed customer languages. The assignment (section 3.3)
    # requires English (US) and Spanish, but the sample payload (section 5.1)
    # uses "Hindi" — the alias is recognised, and whether it is *accepted* is
    # controlled here (see README "Spec inconsistency" note).
    SUPPORTED_LANGUAGES: str = "en-US,es-ES"
    CORS_ORIGINS: str = "*"

    # --- Stage code engine tunables ----------------------------------------
    STAGE_CODE_CONFIDENCE_THRESHOLD: float = 0.6

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _split_cors(cls, v: str) -> str:
        return v.strip() or "*"

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS_ORIGINS as a parsed list of origins."""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def supported_languages_list(self) -> list[str]:
        """Return SUPPORTED_LANGUAGES as a parsed list of language codes."""
        return [lang.strip() for lang in self.SUPPORTED_LANGUAGES.split(",") if lang.strip()]

    @property
    def repository_kind(self) -> Literal["json", "mongo"]:
        """Which repository backend is active, based on MONGODB_URI presence."""
        return "mongo" if self.MONGODB_URI.strip() else "json"

    def warn_if_defaults(self) -> None:
        """Log a loud warning when insecure default credentials are in use."""
        if self.API_KEY == DEFAULT_API_KEY:
            _bootstrap_logger.warning(
                "SECURITY WARNING: API_KEY is using the insecure default value "
                "(%s). Set API_KEY in your environment before deploying.",
                DEFAULT_API_KEY,
            )
        if self.WEBHOOK_API_KEY == DEFAULT_WEBHOOK_KEY:
            _bootstrap_logger.warning(
                "SECURITY WARNING: WEBHOOK_API_KEY is using the insecure default "
                "value (%s). Set WEBHOOK_API_KEY in your environment before "
                "deploying.",
                DEFAULT_WEBHOOK_KEY,
            )
        if self.GNANI_MODE == "mock":
            _bootstrap_logger.warning(
                "GNANI_MODE=mock: the Gnani Agents Console call-trigger API is "
                "being simulated. Set GNANI_MODE=live and GNANI_API_KEY for "
                "production use."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance for the process lifetime."""
    settings = Settings()
    settings.warn_if_defaults()
    return settings

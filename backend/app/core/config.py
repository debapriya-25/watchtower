"""Application configuration.

All settings are loaded from environment variables (and the local ``.env`` file
during development) using ``pydantic-settings``. Import the singleton
``settings`` object anywhere configuration is required:

    from app.core.config import settings
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application settings sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        alias="APP_ENV",
    )
    app_name: str = Field(default="Watchtower", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    # --- Datastores ------------------------------------------------------
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    # --- Security / JWT --------------------------------------------------
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_ttl_min: int = Field(default=15, alias="ACCESS_TOKEN_TTL_MIN")
    refresh_token_ttl_days: int = Field(default=7, alias="REFRESH_TOKEN_TTL_DAYS")

    # --- External services -----------------------------------------------
    price_cache_ttl_sec: int = Field(default=30, alias="PRICE_CACHE_TTL_SEC")
    coingecko_base: str = Field(
        default="https://api.coingecko.com/api/v3",
        alias="COINGECKO_BASE",
    )
    coingecko_api_key: str | None = Field(
        default=None, alias="COINGECKO_API_KEY"
    )
    coingecko_timeout_sec: float = Field(
        default=10.0, alias="COINGECKO_TIMEOUT_SEC"
    )
    coingecko_max_retries: int = Field(
        default=3, alias="COINGECKO_MAX_RETRIES"
    )
    price_vs_currency: str = Field(default="usd", alias="PRICE_VS_CURRENCY")
    top_tokens_count: int = Field(default=100, alias="TOP_TOKENS_COUNT")

    # --- Seed credentials -------------------------------------------------
    admin_email: str = Field(
        default="admin@watchtower.dev", alias="ADMIN_EMAIL"
    )
    admin_password: str = Field(
        default="ChangeMeAdmin123!", alias="ADMIN_PASSWORD"
    )
    demo_email: str = Field(default="demo@watchtower.dev", alias="DEMO_EMAIL")
    demo_password: str = Field(
        default="ChangeMeDemo123!", alias="DEMO_PASSWORD"
    )

    # --- CORS ------------------------------------------------------------
    # ``NoDecode`` disables pydantic-settings' default JSON decoding so the
    # validator below can accept a plain comma-separated string from ``.env``.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow ``CORS_ORIGINS`` to be a comma-separated string in ``.env``."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def async_database_url(self) -> str:
        """Return a SQLAlchemy async-compatible database URL.

        The project ships with ``postgresql+psycopg://`` which psycopg3 serves
        for both sync and async engines, so it is returned unchanged. A bare
        ``postgresql://`` URL is upgraded to the psycopg driver.
        """
        if self.database_url.startswith("postgresql+psycopg://"):
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        return self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    Cached so the ``.env`` file and environment are parsed exactly once per
    process. Use :func:`get_settings` (or the ``settings`` singleton) rather
    than instantiating :class:`Settings` directly.
    """
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()

"""Runtime configuration. Values come from environment or a .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="ZONELAB_", extra="ignore"
    )

    # Which provider serves candles when the request does not name one.
    # Binance needs no key, so a clean checkout charts real bars immediately.
    default_provider: str = "binance"

    # API keys. Empty means that provider is unavailable and says so explicitly
    # instead of silently returning nothing.
    twelvedata_key: str = ""
    polygon_key: str = ""

    # Upstream fetches are cached this long. Intraday bars do not change once
    # closed, so this only ever costs freshness on the forming bar.
    cache_ttl_seconds: int = 20

    http_timeout_seconds: float = 15.0
    max_bars: int = 5000

    # Any loopback port, and only loopback. Pinning a single port breaks the
    # moment the dev server picks 3001 because 3000 was busy, and the failure
    # reads as "the API is down" rather than "wrong origin".
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1)(:\d+)?"


settings = Settings()

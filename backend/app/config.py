"""Runtime configuration. Values come from environment or a .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="ZONELAB_", extra="ignore"
    )

    # Which provider serves candles when the request does not name one.
    #
    # The local MetaTrader 5 terminal, where one is installed and logged in. It
    # is the broker's own tape rather than a proxy for it, it carries a real
    # spread, and it answered 99,999 bars in 0.01s here where binance caps a
    # page at 1000. On a machine with no terminal it probes as unavailable and
    # the UI falls through to the next source that carries the symbol, so this
    # default costs a clean checkout nothing but one failed probe.
    default_provider: str = "mt5"

    # API keys. Empty means that provider is unavailable and says so explicitly
    # instead of silently returning nothing.
    twelvedata_key: str = ""
    polygon_key: str = ""

    # The language model, used ONLY to phrase and to look - never to decide.
    # Empty means the feature is off and says so, exactly like a missing vendor
    # key: a model that cannot be reached must produce a refusal, not silence
    # and not a guess.
    llm_key: str = ""
    llm_model: str = "glm-5.3"
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_timeout_seconds: float = 60.0

    # How the model is reached. "http" posts to `llm_base_url` and needs
    # `llm_key`. "cli" spawns the Claude Code binary already installed on this
    # machine, which carries its own login and therefore needs no key at all -
    # which is the only reason the vision job has ever actually been run here.
    llm_backend: str = "http"
    llm_cli_command: str = "claude"
    # Not a copy of `llm_timeout_seconds` for the sake of symmetry. A CLI turn
    # boots an entire agent before it answers: measured 9 to 19 seconds on this
    # machine for a one-word reply with a 64x64 image, so an audit of a real
    # chart needs minutes and the HTTP timeout would kill every single call.
    llm_cli_timeout_seconds: float = 300.0

    # The prompt is handed over on stdin, so this is not an argv length limit.
    # It is a refusal to pass an unbounded payload to a subprocess or an
    # upstream: a caller that loops over every zone on every timeframe will
    # otherwise build a prompt nobody chose the size of.
    llm_max_prompt_chars: int = 40000

    # Upstream fetches are cached this long. Intraday bars do not change once
    # closed, so this only ever costs freshness on the forming bar.
    cache_ttl_seconds: int = 20

    http_timeout_seconds: float = 15.0
    #: Anggaran jam dinding untuk SATU tarikan dukascopy, seluruh jamnya
    #: sekaligus. Vendor ini satu request per jam dan menjawab dalam burst;
    #: terukur sekitar 61 detik per 200 bar, yaitu tepat di atas timeout klien
    #: 60 detik yang dipakai `tools/validate_api.py`. Melewati anggaran ini
    #: menghasilkan 502 yang menyebut vendor, bukan timeout di sisi klien.
    #: Dua puluh detik memberi ruang untuk tarikan kecil dan tetap gagal jauh
    #: sebelum pemeriksa menyerah.
    dukascopy_budget_seconds: float = 20.0

    # Raised from 5000 when the local MT5 terminal arrived. It was a ceiling
    # shaped by the HTTP sources - binance caps a page at 1000, yahoo's intraday
    # recency wall is 60 days - and the terminal has neither, returning 99,999
    # fifteen-minute bars in 0.01s off its own history file. This is still a
    # guard and not a promise: a network provider asked for more simply returns
    # what it can, because every one of them clamps its own request.
    max_bars: int = 50000

    # Any loopback port, and only loopback. Pinning a single port breaks the
    # moment the dev server picks 3001 because 3000 was busy, and the failure
    # reads as "the API is down" rather than "wrong origin".
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1)(:\d+)?"


settings = Settings()

"""Guards on the two places a wrong answer arrives silently rather than loudly.

Neither of these is about market structure. They are about the seams: the
detector registry the API dispatches through, and the vendor payloads nobody
controls.
"""

from __future__ import annotations

import asyncio

import pytest

from app.detect import DETECTORS, PARAMS_FOR
from app.models import DrawRequest
from app.providers import ProviderError
from app.providers.sources import BinanceProvider


def test_every_detector_has_a_params_block():
    """`/api/draw` validates a detector name against DETECTORS and then reads
    its parameters through PARAMS_FOR. A name in one dict and not the other
    means the request passes validation and the detector never runs: 200 OK,
    no zones, no error. Registering a detector must break here instead.
    """
    assert set(DETECTORS) == set(PARAMS_FOR)
    request = DrawRequest(symbol="XAUUSD")
    for block in PARAMS_FOR.values():
        assert hasattr(request, block), f"DrawRequest has no '{block}' block"


def test_a_short_vendor_row_names_the_provider(monkeypatch):
    """`_fetch` in main.py converts ProviderError and nothing else, so an
    IndexError from a truncated kline would reach the user as a bare 500 with
    no mention of which vendor sent it.
    """

    async def truncated(url, params=None):
        return [[1_700_000_000_000, "2400.0", "2401.0"]]  # ohlcv cut off after high

    monkeypatch.setattr("app.providers.sources._get_json", truncated)

    with pytest.raises(ProviderError, match="binance"):
        asyncio.run(BinanceProvider().fetch("XAUUSD", "15m", 100))


def test_the_forming_bar_never_reaches_the_detector():
    """Four of six providers shipped it, and it made the drawing lie.

    Measured on 599 real 15m formations before this guard: 42 zone states
    changed and changed back INSIDE one bar, 15 zones vanished and returned,
    and a stop's risk-per-unit swung 14% in 90 seconds with no bar closing.
    The guard lives at the single point every caller routes through, so a new
    provider cannot forget it.
    """
    import time as _time

    from app.models import Candle
    from app.providers import drop_forming

    now = int(_time.time())
    closed = Candle(time=now - 1800, open=1.0, high=1.0, low=1.0, close=1.0)
    forming = Candle(time=now - 60, open=1.0, high=1.0, low=1.0, close=1.0)

    assert drop_forming([closed, forming], "15m") == [closed]
    assert drop_forming([closed], "15m") == [closed]
    # An unknown interval must not silently drop the newest bar: guessing here
    # would be a different lie from the one being fixed.
    assert drop_forming([closed, forming], "nonsense") == [closed, forming]
    assert drop_forming([], "15m") == []


def test_the_response_says_which_bar_it_drew():
    """A live chart that cannot say WHICH BAR it describes is asking to be
    trusted on nothing. Binance is seconds behind and dukascopy up to 59
    minutes, and without a number the two look identical on screen."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = client.post("/api/draw", json={
        "symbol": "BTCUSDT", "interval": "15m", "bars": 200,
        "provider": "synthetic",
    }).json()
    meta = body["meta"]

    for key in ("as_of", "bar_closed_at", "next_close_at", "feed_lag_seconds",
                "fetched_at"):
        assert key in meta, key
    assert meta["bar_closed_at"] == meta["as_of"] + 900
    assert meta["next_close_at"] == meta["as_of"] + 1800
    assert meta["feed_lag_seconds"] >= 0
    # The newest bar is CLOSED, which is the whole point of the guard above.
    assert meta["bar_closed_at"] <= meta["fetched_at"]

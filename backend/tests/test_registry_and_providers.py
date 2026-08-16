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

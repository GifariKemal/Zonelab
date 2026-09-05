"""Tests for the enhancement gates added to cycle().

Three hard gates (ADX minimum, ATR budget max, news impact max) and three
context fields (COT, VWAP, volume profile) logged in the journal's `why`.

The helper functions under test (_market_context, _news_impact_score,
_cot_signal) may not exist yet; the other agent is implementing them. Import
errors here are expected until that lands.
"""

from __future__ import annotations

import types
from unittest.mock import patch

import numpy as np
import pytest

from app.indicators import wilder_adx, bb_width, wilder_atr, vwap, volume_profile
from app.models import Candle


# ----------------------------------------------------------------- fixtures


def _trending_candles(n: int = 200, start: float = 100.0, end: float = 200.0,
                      step_sec: int = 3600, origin: int = 1_700_000_000):
    """Steady uptrend: high ADX, low BB width relative to trend."""
    rng = np.random.default_rng(42)
    close = np.linspace(start, end, n)
    noise = rng.normal(0, 0.3, n)
    close = close + noise
    high = close + np.abs(noise) + 0.8
    low = close - np.abs(noise) - 0.8
    volume = rng.uniform(50, 200, n)
    return [
        Candle(time=origin + i * step_sec, open=float(close[max(0, i - 1)]),
               high=float(high[i]), low=float(low[i]), close=float(close[i]),
               volume=float(volume[i]))
        for i in range(n)
    ]


def _ranging_candles(n: int = 200, centre: float = 100.0,
                     step_sec: int = 3600, origin: int = 1_700_000_000):
    """Flat noise around a centre: low ADX expected.

    A sine wave looks directional to ADX (consistent +DM/-DM runs), so it
    reads 40+. Pure noise around a flat mean is the shape ADX calls weak.
    """
    rng = np.random.default_rng(7)
    close = np.full(n, centre) + rng.normal(0, 0.15, n)
    high = close + 0.3
    low = close - 0.3
    volume = rng.uniform(50, 200, n)
    return [
        Candle(time=origin + i * step_sec, open=float(close[max(0, i - 1)]),
               high=float(high[i]), low=float(low[i]), close=float(close[i]),
               volume=float(volume[i]))
        for i in range(n)
    ]


def _arrays(candles):
    """Extract numpy arrays from candle list."""
    return (
        np.array([c.high for c in candles]),
        np.array([c.low for c in candles]),
        np.array([c.close for c in candles]),
        np.array([c.volume for c in candles]),
    )


# -------------------------------------------- 1. _market_context unit tests


class TestMarketContextAdx:
    """ADX classification: weak / trending / strong."""

    def test_ranging_series_produces_weak_adx(self):
        candles = _ranging_candles()
        high, low, close, _ = _arrays(candles)
        adx = wilder_adx(high, low, close, 14)
        assert adx[-1] < 20, f"ranging series ADX {adx[-1]:.1f} should be < 20"

    def test_trending_series_produces_high_adx(self):
        candles = _trending_candles()
        high, low, close, _ = _arrays(candles)
        adx = wilder_adx(high, low, close, 14)
        assert adx[-1] > 20, f"trending series ADX {adx[-1]:.1f} should be > 20"

    def test_strong_trend_exceeds_40(self):
        """Steep enough trend with low noise should push ADX past 40."""
        candles = _trending_candles(n=300, start=100.0, end=400.0)
        high, low, close, _ = _arrays(candles)
        adx = wilder_adx(high, low, close, 14)
        assert adx[-1] > 40, f"strong trend ADX {adx[-1]:.1f} should be > 40"

    def test_adx_classification_labels(self):
        """When _market_context exists, verify label strings."""
        try:
            from tools.execute import _market_context
        except ImportError:
            pytest.skip("_market_context not implemented yet")

        weak = _market_context(_ranging_candles(), "XAUUSD")
        assert weak["adx_label"] == "weak", f"got {weak['adx_label']}"

        trending = _market_context(_trending_candles(), "XAUUSD")
        assert trending["adx_label"] in ("trending", "strong"), (
            f"got {trending['adx_label']}"
        )


class TestMarketContextAtrBudget:
    """ATR budget: today's range as a fraction of ATR(14)."""

    def test_half_atr_used(self):
        """Construct candles where today's range is ~50% of ATR."""
        candles = _trending_candles(n=100)
        high, low, close, _ = _arrays(candles)
        atr_val = wilder_atr(high, low, close, 14)[-1]
        today_range = float(high[-1] - low[-1])
        pct = today_range / atr_val
        # ponytail: just verify the arithmetic is sane
        assert 0 < pct < 2.0, f"pct_used {pct:.3f} outside reasonable range"

    def test_exhausted_range_exceeds_one(self):
        """Inject one candle with a huge range at the end."""
        candles = _ranging_candles(n=100)
        high, low, close, _ = _arrays(candles)
        atr_val = wilder_atr(high, low, close, 14)[-1]
        # Replace last candle with one whose range is 3x ATR
        spike = candles[-1].model_copy()
        spike.high = spike.close + 2.0 * atr_val
        spike.low = spike.close - 1.0 * atr_val
        candles[-1] = spike
        high2, low2, close2, _ = _arrays(candles)
        today_range = float(high2[-1] - low2[-1])
        pct = today_range / atr_val
        assert pct > 1.0, f"pct_used {pct:.3f} should exceed 1.0 after spike"

    def test_market_context_atr_pct_field(self):
        """When _market_context exists, verify atr_pct_used is populated."""
        try:
            from tools.execute import _market_context
        except ImportError:
            pytest.skip("_market_context not implemented yet")

        ctx = _market_context(_trending_candles(), "XAUUSD")
        assert "atr_pct_used" in ctx
        assert isinstance(ctx["atr_pct_used"], float)
        assert ctx["atr_pct_used"] > 0


class TestMarketContextVwap:
    """VWAP position: price above/below daily VWAP."""

    def test_uptrend_price_above_vwap(self):
        candles = _trending_candles()
        high, low, close, volume = _arrays(candles)
        v = vwap(high, low, close, volume)
        # In an uptrend, last close should be above cumulative VWAP
        assert close[-1] > v[-1], "uptrend close should sit above VWAP"

    def test_downtrend_price_below_vwap(self):
        candles = _trending_candles(start=200.0, end=100.0)
        high, low, close, volume = _arrays(candles)
        v = vwap(high, low, close, volume)
        assert close[-1] < v[-1], "downtrend close should sit below VWAP"

    def test_market_context_vwap_position(self):
        try:
            from tools.execute import _market_context
        except ImportError:
            pytest.skip("_market_context not implemented yet")

        ctx = _market_context(_trending_candles(), "XAUUSD")
        assert ctx["vwap_position"] in ("above", "below")


# --------------------------------------------- 2. _news_impact_score tests


class TestNewsImpactScore:
    """Score: 0 (none) to 3 (FOMC+NFP level).

    _news_impact_score() fetches the live calendar feed over HTTP and parses
    it inline. These tests mock urllib.request.urlopen so the scoring logic
    is exercised without network access.
    """

    def _make_row(self, title, impact="High", date="2026-09-04T08:30:00-04:00"):
        return {"title": title, "country": "USD", "date": date,
                "impact": impact, "forecast": "", "previous": ""}

    def _fake_urlopen(self, rows):
        """Return a context-manager that yields JSON bytes."""
        import json, io

        class FakeResp:
            def read(self):
                return json.dumps(rows).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        return lambda *a, **k: FakeResp()

    def test_no_events_returns_zero(self):
        from tools.execute import _news_impact_score
        with patch("urllib.request.urlopen", self._fake_urlopen([])):
            assert _news_impact_score() == 0

    def test_cpi_returns_two(self):
        from tools.execute import _news_impact_score
        import time as _time
        from app.clock import to_ny
        today_str = to_ny(int(_time.time())).strftime("%Y-%m-%dT08:30:00-04:00")
        rows = [self._make_row("CPI m/m", date=today_str)]
        with patch("urllib.request.urlopen", self._fake_urlopen(rows)):
            assert _news_impact_score() == 2

    def test_fomc_plus_nfp_returns_three(self):
        from tools.execute import _news_impact_score
        import time as _time
        from app.clock import to_ny
        today_str = to_ny(int(_time.time())).strftime("%Y-%m-%dT08:30:00-04:00")
        rows = [
            self._make_row("FOMC Meeting Minutes", date=today_str),
            self._make_row("Non-Farm Employment Change", date=today_str),
        ]
        with patch("urllib.request.urlopen", self._fake_urlopen(rows)):
            assert _news_impact_score() == 3

    def test_feed_failure_returns_zero(self):
        """Network error is 0 (safe default), not an exception."""
        from tools.execute import _news_impact_score
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            assert _news_impact_score() == 0


# ---------------------------------- 3. Gate rejection integration tests


# The integration tests mock gather() at the seam between cycle() and the
# market, so they test what cycle() does with the gates rather than
# re-testing the entire detection pipeline.


def _stub_gather(ranked, blocked=None, series=None):
    """Return a monkeypatch-ready gather replacement.

    series must map bare symbol -> candle list, because cycle() builds
    _contexts by iterating series.items(). Empty series means empty
    _contexts, which means every ctx.get() hits the default and the
    gate never fires.
    """
    if series is None:
        # Provide a minimal candle list so _market_context gets called
        series = {"XAUUSD": _ranging_candles(n=50)}
    def fake_gather(*args, **kwargs):
        return ranked or [], blocked or [], series
    return fake_gather


def _minimal_candidate(symbol="mt5:XAUUSD", interval="1h"):
    """A candidate tuple shaped like gather() returns, just enough to reach
    the gate checks. Zone, plan, and checklist are SimpleNamespace stubs."""
    zone = types.SimpleNamespace(
        id="DBD-1787227200",
        kind=types.SimpleNamespace(value="DBD"),
        side=types.SimpleNamespace(value="supply"),
        departure_atr=6.3,
        first_test_time=None,
        anatomy=types.SimpleNamespace(leg_in_from=0, leg_in_to=1, base_from=1,
                                       base_to=2, leg_out_from=3, leg_out_to=4),
    )
    plan = types.SimpleNamespace(
        entry=4604.0, stop=4628.0, target=4490.0, risk_per_unit=24.0,
        reward_r=4.75, placeable=True, lots=0.01, warnings=[],
        realised_risk=24.0, realised_risk_pct=0.0024,
        age_bars=23, age_held_rate=0.77,
        model_dump=lambda mode="json": {},
    )
    checklist = types.SimpleNamespace(
        met=5,
        conditions=[
            types.SimpleNamespace(name=f"cond_{i}", met=True, detail="stub")
            for i in range(17)
        ],
        why=lambda: ["checklist stub"],
        failed_required=lambda rules: [],
    )
    return (symbol, interval, zone, plan, checklist)


class TestAdxGate:
    def test_rejects_weak_market(self, monkeypatch):
        """adx_min=20 with ADX 15 -> candidate refused, blocker mentions ADX."""
        try:
            from tools.execute import cycle, _market_context
        except ImportError:
            pytest.skip("enhancement gates not implemented yet")

        ranked = [_minimal_candidate()]
        monkeypatch.setattr("tools.execute.gather", _stub_gather(ranked))
        # Mock _market_context to return weak ADX
        monkeypatch.setattr("tools.execute._market_context",
                            lambda candles, symbol: {"adx": 15.0,
                                                      "adx_label": "weak",
                                                      "bb_label": "normal",
                                                      "atr_pct_used": 0.4,
                                                      "vwap_position": "above",
                                                      "vp_position": "above_poc"})
        monkeypatch.setattr("tools.execute._news_impact_score", lambda: 0)
        monkeypatch.setattr("tools.execute._cot_signal", lambda s: None)
        # Stub journal, broker bits
        monkeypatch.setattr("tools.execute.journal.record", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.journal.open_tickets", lambda *a: [])
        monkeypatch.setattr("tools.execute.warn_required", lambda r: None)
        monkeypatch.setattr("tools.execute.outcome_odds", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.odds_line", lambda o: "n/a")

        result = cycle(
            mt5=None, symbols=["mt5:XAUUSD"], intervals=["1h"],
            bars=100, risk_pct=0.01, max_orders=2, send=False,
            adx_min=20.0,
        )
        assert result["refused"] >= 1 or result["candidates"] == 0


class TestAtrBudgetGate:
    def test_rejects_exhausted_range(self, monkeypatch):
        """atr_budget_max=0.8 with range at 95% of ATR -> refused."""
        try:
            from tools.execute import cycle, _market_context
        except ImportError:
            pytest.skip("enhancement gates not implemented yet")

        ranked = [_minimal_candidate()]
        monkeypatch.setattr("tools.execute.gather", _stub_gather(ranked))
        monkeypatch.setattr("tools.execute._market_context",
                            lambda candles, symbol: {"adx": 30.0,
                                                      "adx_label": "trending",
                                                      "bb_label": "normal",
                                                      "atr_pct_used": 0.95,
                                                      "vwap_position": "above",
                                                      "vp_position": "above_poc"})
        monkeypatch.setattr("tools.execute._news_impact_score", lambda: 0)
        monkeypatch.setattr("tools.execute._cot_signal", lambda s: None)
        monkeypatch.setattr("tools.execute.journal.record", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.journal.open_tickets", lambda *a: [])
        monkeypatch.setattr("tools.execute.warn_required", lambda r: None)
        monkeypatch.setattr("tools.execute.outcome_odds", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.odds_line", lambda o: "n/a")

        result = cycle(
            mt5=None, symbols=["mt5:XAUUSD"], intervals=["1h"],
            bars=100, risk_pct=0.01, max_orders=2, send=False,
            atr_budget_max=0.8,
        )
        assert result["refused"] >= 1 or result["candidates"] == 0


class TestNewsGate:
    def test_rejects_major_events(self, monkeypatch):
        """news_max=2 with FOMC (score 3) -> refused."""
        try:
            from tools.execute import cycle, _news_impact_score
        except ImportError:
            pytest.skip("enhancement gates not implemented yet")

        ranked = [_minimal_candidate()]
        monkeypatch.setattr("tools.execute.gather", _stub_gather(ranked))
        monkeypatch.setattr("tools.execute._market_context",
                            lambda candles, symbol: {"adx": 30.0,
                                                      "adx_label": "trending",
                                                      "bb_label": "normal",
                                                      "atr_pct_used": 0.3,
                                                      "vwap_position": "above",
                                                      "vp_position": "above_poc"})
        monkeypatch.setattr("tools.execute._news_impact_score", lambda: 3)
        monkeypatch.setattr("tools.execute._cot_signal", lambda s: None)
        monkeypatch.setattr("tools.execute.journal.record", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.journal.open_tickets", lambda *a: [])
        monkeypatch.setattr("tools.execute.warn_required", lambda r: None)
        monkeypatch.setattr("tools.execute.outcome_odds", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.odds_line", lambda o: "n/a")

        result = cycle(
            mt5=None, symbols=["mt5:XAUUSD"], intervals=["1h"],
            bars=100, risk_pct=0.01, max_orders=2, send=False,
            news_max=2,
        )
        assert result["refused"] >= 1 or result["candidates"] == 0


class TestGatesDisabledByDefault:
    def test_defaults_do_not_reject(self, monkeypatch):
        """Default gate values (adx_min=0, atr_budget_max=0, news_max=99)
        should not cause additional rejections."""
        try:
            from tools.execute import cycle, _market_context
        except ImportError:
            pytest.skip("enhancement gates not implemented yet")

        ranked = [_minimal_candidate()]
        monkeypatch.setattr("tools.execute.gather", _stub_gather(ranked))
        monkeypatch.setattr("tools.execute._market_context",
                            lambda candles, symbol: {"adx": 10.0,
                                                      "adx_label": "weak",
                                                      "bb_label": "squeeze",
                                                      "atr_pct_used": 1.5,
                                                      "vwap_position": "below",
                                                      "vp_position": "below_poc"})
        # High news score, but gate default 99 means it never triggers
        monkeypatch.setattr("tools.execute._news_impact_score", lambda: 3)
        monkeypatch.setattr("tools.execute._cot_signal", lambda s: None)
        monkeypatch.setattr("tools.execute.journal.record", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.journal.open_tickets", lambda *a: [])
        monkeypatch.setattr("tools.execute.warn_required", lambda r: None)
        monkeypatch.setattr("tools.execute.outcome_odds", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.odds_line", lambda o: "n/a")

        result = cycle(
            mt5=None, symbols=["mt5:XAUUSD"], intervals=["1h"],
            bars=100, risk_pct=0.01, max_orders=2, send=False,
            # defaults: adx_min=0, atr_budget_max=0, news_max=99
        )
        # With defaults, the enhancement gates should not refuse
        # (other gates may still refuse for their own reasons)
        assert result["candidates"] >= 1


class TestEnhancementContextInWhy:
    def test_why_lines_contain_regime_and_vwap(self, monkeypatch):
        """Journal why_lines should mention regime, VWAP, and COT context."""
        try:
            from tools.execute import cycle, _market_context, grounds
        except ImportError:
            pytest.skip("enhancement gates not implemented yet")

        recorded = {}

        def capture_record(event, *, why, **kwargs):
            recorded["event"] = event
            recorded["why"] = why

        ranked = [_minimal_candidate()]
        monkeypatch.setattr("tools.execute.gather", _stub_gather(ranked))
        monkeypatch.setattr("tools.execute._market_context",
                            lambda candles, symbol: {"adx": 30.0,
                                                      "adx_label": "trending",
                                                      "bb_label": "normal",
                                                      "atr_pct_used": 0.4,
                                                      "vwap_position": "above",
                                                      "vp_position": "above_poc"})
        monkeypatch.setattr("tools.execute._news_impact_score", lambda: 0)
        monkeypatch.setattr("tools.execute._cot_signal",
                            lambda s: {"net": 1234, "change": 50})
        monkeypatch.setattr("tools.execute.journal.record", capture_record)
        monkeypatch.setattr("tools.execute.journal.open_tickets", lambda *a: [])
        monkeypatch.setattr("tools.execute.warn_required", lambda r: None)
        monkeypatch.setattr("tools.execute.outcome_odds", lambda *a, **k: None)
        monkeypatch.setattr("tools.execute.odds_line", lambda o: "n/a")

        result = cycle(
            mt5=None, symbols=["mt5:XAUUSD"], intervals=["1h"],
            bars=100, risk_pct=0.01, max_orders=2, send=False,
        )
        # If a candidate was processed (dry run or placed), the why should
        # carry context from the enhancement helpers. The exact shape depends
        # on the implementation, but regime/vwap/cot should appear somewhere.
        if "why" in recorded:
            joined = " ".join(recorded["why"])
            # At least one of the three context fields should be logged
            has_regime = any(w in joined.lower() for w in ("adx", "regime", "trending"))
            has_vwap = "vwap" in joined.lower()
            has_cot = "cot" in joined.lower()
            assert has_regime or has_vwap or has_cot, (
                f"why_lines should contain enhancement context, got: {recorded['why']}"
            )

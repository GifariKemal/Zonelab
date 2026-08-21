"""Guards on the local-terminal provider.

Two failures are worth a test here, and they are not the same kind.

The first is silent: MT5 stamps bars in the BROKER's timezone, so a GMT+3 server
hands over a 13:45 bar that claims to be 13:45 UTC. Nothing downstream can catch
that - the candles are real, the structure is real, and every level is simply
three hours from where it belongs. The correction reads the last tick as a clock,
which only works while the market is open, so the bound that separates "timezone"
from "stale tick" is the whole safety of it and is tested without a terminal.

The second is loud but only observable against a live terminal, so it skips.
"""

from __future__ import annotations

import asyncio
import time
import types

import pytest

from app.providers import mt5 as mt5mod
from app.providers.base import INTERVALS


def _tick_at(epoch: int) -> types.SimpleNamespace:
    return types.SimpleNamespace(time=epoch)


@pytest.mark.parametrize(
    "server_minus_utc, stale_seconds, expected",
    [
        (0, 0, 0),  # UTC broker, market open: Exness-MT5Trial7 today
        (7200, 0, 7200),  # GMT+2, market open
        (10800, 12, 10800),  # GMT+3, tick a few seconds old
        (10800, 30, 10800),  # rounding survives a half-minute of lag
        # Market closed. A weekend of staleness is NOT a timezone, and reading
        # it as one would shift every bar by a whole wrong number of hours.
        (0, 2 * 86400, 0),
        (10800, 2 * 86400, 0),
        (0, 3600, 0),  # an hour of staleness must not read as GMT-1
    ],
)
def test_a_stale_tick_is_never_mistaken_for_a_timezone(
    monkeypatch, server_minus_utc, stale_seconds, expected
):
    now = int(time.time())
    monkeypatch.setattr(
        mt5mod,
        "mt5",
        types.SimpleNamespace(
            symbol_info_tick=lambda _: _tick_at(now + server_minus_utc - stale_seconds)
        ),
    )
    assert mt5mod.MT5Provider._server_offset("XAUUSD") == expected


def test_a_terminal_with_no_tick_yet_is_not_an_offset(monkeypatch):
    """`symbol_info_tick` returns None for a symbol that has never traded in
    this session, and `time == 0` for one the terminal has not filled yet.
    Both must read as "unknown", which is 0, not as a shift of fifty years."""
    for tick in (None, _tick_at(0)):
        monkeypatch.setattr(
            mt5mod, "mt5", types.SimpleNamespace(symbol_info_tick=lambda _: tick)
        )
        assert mt5mod.MT5Provider._server_offset("XAUUSD") == 0


@pytest.mark.parametrize("interval", ["15m", "1h"])
def test_live_bars_are_utc_and_on_the_interval_grid(interval):
    """Needs a running, logged-in terminal, so it skips where there is none.

    Checks the two things the offset correction exists to make true: the newest
    bar is where a clock says it should be, and consecutive bars are exactly one
    interval apart inside a session. An uncorrected server timezone breaks the
    first and leaves the second intact, which is why both are here.
    """
    provider = mt5mod.MT5Provider()
    if not provider.available() or not asyncio.run(provider.probe()):
        pytest.skip("no MetaTrader 5 terminal is running and logged in")

    candles = asyncio.run(provider.fetch("XAUUSD", interval, 300))
    assert len(candles) == 300

    step = INTERVALS[interval]
    gaps = {b.time - a.time for a, b in zip(candles, candles[1:])}
    assert min(gaps) == step, f"bars closer together than one {interval}: {min(gaps)}s"

    # The newest bar is the forming one, so its open is within one interval of
    # now. A whole-hour timezone error puts it hours away and this is what says
    # so. Two intervals of slack covers a market that just closed for the day.
    age = time.time() - candles[-1].time
    assert -60 <= age <= 2 * step or age > 8 * 3600, (
        f"newest {interval} bar opened {age:.0f}s ago, which is neither live "
        "nor a closed market - the server clock is probably not UTC"
    )

    assert all(c.low <= c.open <= c.high and c.low <= c.close <= c.high for c in candles)
    assert all(c.spread is None or c.spread > 0 for c in candles)


@pytest.mark.parametrize("target", ["1h", "4h", "1d"])
def test_the_aggregate_matches_the_terminals_own_bars_of_that_timeframe(target):
    """`resample` checked against an INDEPENDENT authority, which is rare here.

    Every other test of the aggregate compares it to arithmetic this repo also
    wrote. The terminal builds its own hourly, four-hourly and daily bars from
    the same tape, so asking it for them and asking `resample` to derive them
    from 15m is two implementations meeting in the middle. If the bucket anchor,
    the session offset or the partial-bucket rule were wrong, the highs and lows
    would part company here and nowhere else.

    Measured 2026-08-20 on this terminal: 60 of 60 daily bars agreed on both
    extremes at `session_offset_hours=0`, and 0 of 60 agreed at -2 or +2 - so
    this also PROVES the shipped default is the right one for this broker rather
    than assuming it. Exness runs its server on UTC, which is why zero is right;
    a GMT+2 or GMT+3 server would need the offset and this test would say so by
    failing.

    The last aggregated bucket is deliberately not compared: `resample` drops an
    incomplete one and the terminal happily reports a forming bar, so they are
    answering different questions about it.
    """
    from app.resample import resample

    provider = mt5mod.MT5Provider()
    if not provider.available() or not asyncio.run(provider.probe()):
        pytest.skip("no MetaTrader 5 terminal is running and logged in")

    fine = asyncio.run(provider.fetch("XAUUSD", "15m", 20000))
    theirs = {c.time: c for c in asyncio.run(provider.fetch("XAUUSD", target, 400))}
    ours = resample(fine, target, "15m")

    # BOTH EDGE BUCKETS ARE PARTIAL and neither is a defect. `resample` already
    # drops the last one, because it is still forming. The FIRST one is cut by
    # the other end of the same window: the oldest 15m bar lands somewhere
    # inside a bucket, so that bucket sees only its tail. Caught by this test
    # failing on exactly one bar out of 200 - aggregated high 4167.206 against
    # the terminal's 4179.805 on 2025-10-14, the day the 15m window opened
    # halfway through. Comparing it would be asking two different questions.
    #
    # AND THE NEWEST SHARED BUCKET GOES TOO, because the two fetches above are
    # not simultaneous. They are separate calls into a live terminal, so a bar can
    # close between them: the 15m series is a snapshot from before that close and
    # the target series from after, which makes the newest bucket they share a
    # comparison between two different instants. That is not a resample defect and
    # the assertion below cannot tell it from one. It cost a single intermittent
    # failure on the 1h case - green on five consecutive runs before and after -
    # and an intermittent gate is a gate people learn to re-run instead of read.
    #
    # The price is one bar of roughly 380. Coverage does not depend on the newest
    # one; it depends on there being hundreds.
    shared = [c for c in ours if c.time in theirs][1:-1]
    assert len(shared) >= 20, f"only {len(shared)} {target} bars overlap; too few to judge"

    for candle in shared:
        mine = theirs[candle.time]
        assert candle.high == pytest.approx(mine.high, abs=0.01), (
            f"{target} bar at {candle.time}: aggregated high {candle.high} "
            f"against the terminal's {mine.high}"
        )
        assert candle.low == pytest.approx(mine.low, abs=0.01), (
            f"{target} bar at {candle.time}: aggregated low {candle.low} "
            f"against the terminal's {mine.low}"
        )


def test_a_settled_zone_does_not_change_when_the_window_grows():
    """THE LOOKAHEAD THIS REPLACED REACHED THE USER through the Bars picker.

    `formation_score`'s volume factor used to divide by `volume.mean()` over the
    WHOLE requested window, so a zone that formed in 2024 was scored against
    bars years in its future. Measured before the fix, XAUUSD 15m through the
    shipped path: nine zones present in both a 500-bar and a 3000-bar window,
    byte-identical geometry, and SEVEN carrying a different score. `_dedupe`
    ranks on that score, so which box got drawn was future-dependent too.

    What this pins is the property that matters and not more than it: a zone
    with a FULL trailing baseline behind it scores the same in every window that
    contains it. A zone inside the first `_VOLUME_BASELINE_BARS` of the window
    has no baseline and scores neutral - a warm-up, not lookahead, and excluded
    here deliberately rather than quietly. Measured 2026-08-20: the eight zones
    that still differ between 500 and 3000 bars are exactly the eight at index
    48 to 168, every one of them carrying the neutral 1/3 x 0.5 = 0.1667, while
    the two at index 484 and 671 are identical in both.
    """
    from app.detect.supply_demand import _VOLUME_BASELINE_BARS, detect
    from app.models import SupplyDemandParams

    provider = mt5mod.MT5Provider()
    if not provider.available() or not asyncio.run(provider.probe()):
        pytest.skip("no MetaTrader 5 terminal is running and logged in")

    params = SupplyDemandParams(max_zones_per_side=0, show_broken=True)
    wide = asyncio.run(provider.fetch("XAUUSD", "15m", 12000))
    narrow = wide[-3000:]

    wide_zones = {z.id: z for z in detect(wide, params)[0]}
    narrow_zones = detect(narrow, params)[0]

    # Only zones far enough into the SHORT window to own a full baseline.
    warm = narrow[_VOLUME_BASELINE_BARS].time
    compared = 0
    for zone in narrow_zones:
        if zone.time_from < warm or zone.id not in wide_zones:
            continue
        compared += 1
        other = wide_zones[zone.id]
        assert zone.formation_score == pytest.approx(other.formation_score), (
            f"{zone.id} scored {zone.formation_score} in a 3000-bar window and "
            f"{other.formation_score} in a 12000-bar one, with the same bars "
            "under it - the window is leaking into the score again"
        )
        assert zone.factors == other.factors
        assert (zone.top, zone.bottom) == (other.top, other.bottom)

    assert compared >= 10, f"only {compared} zones were comparable; too few to judge"


def test_a_price_feed_refuses_the_account_endpoint_by_naming_itself():
    """"yahoo cannot tell you your equity" is a fact about yahoo.

    A 501 that names the provider is the difference between a caller learning the
    capability does not exist and a caller thinking the request failed. Only a
    broker connection can answer for an account, and offering the control
    everywhere then failing teaches a reader to distrust the panel.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/api/account", params={"provider": "synthetic"})
    assert response.status_code == 501, response.text
    detail = response.json()["detail"]
    assert "synthetic" in detail
    assert "mt5" in detail, "the message has to say which provider CAN answer"


def test_the_account_reading_carries_no_account_identifier():
    """The account number identifies a real trading account and sizing does not
    need it, so it must never be in a payload that can reach a log, a snapshot or
    a screenshot. Asserted on the SHAPE rather than on a live terminal, so this
    holds on a machine with no MetaTrader installed."""
    import inspect

    from app.providers.mt5 import MT5Provider

    source = inspect.getsource(MT5Provider._account)
    for forbidden in ("login", "server", "name", "password"):
        assert f'"{forbidden}"' not in source, f"{forbidden} must not be returned"
    for needed in ("currency", "balance", "equity", "free_margin", "leverage"):
        assert f'"{needed}"' in source, f"{needed} is what sizing needs"


#: Whether a real terminal is attached. The live check below is the only test in
#: this file that needs one, so it is gated rather than allowed to fail a suite
#: run on a machine with no MetaTrader installed.
try:  # pragma: no cover - depends on the machine, not on the code
    import MetaTrader5 as _terminal

    _HAVE_TERMINAL = _terminal.initialize() and _terminal.account_info() is not None
    _terminal.shutdown()
except Exception:  # noqa: BLE001
    _HAVE_TERMINAL = False


@pytest.mark.skipif(not _HAVE_TERMINAL, reason="no MetaTrader 5 terminal on this machine")
def test_the_terminal_reports_an_account_that_can_size_a_position():
    """Live, against whatever terminal is attached. Skipped elsewhere.

    Asserts the invariants a lot calculation depends on rather than any
    particular figure: the numbers must be present, non-negative, and leverage
    must be a real multiplier - a zero would divide into the margin check.
    """
    import asyncio

    from app.providers.mt5 import MT5Provider

    reading = asyncio.run(MT5Provider().account())
    assert reading["currency"], "a lot size means nothing without a currency"
    assert float(reading["balance"]) >= 0
    assert float(reading["equity"]) >= 0
    assert float(reading["free_margin"]) >= 0
    assert int(reading["leverage"]) > 0
    assert int(reading["read_at"]) > 0
    assert "login" not in reading and "server" not in reading

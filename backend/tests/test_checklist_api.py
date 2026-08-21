"""The owner's checklist, over HTTP, on bars that need no network.

Five modules carrying 83 tests between them were complete and unreachable for
most of a day: `bias`, `quarterly`, `ssmt`, `aligned` and `clock` existed, passed,
and nothing called them. These tests cover the wiring itself, which is the part
none of those 83 could see.

The distinctions being defended here are the ones that would be easiest to
collapse later and hardest to notice afterwards: absent is not false, UNKNOWN is
not zero, and an extra provider call is never free.

Run with:  .venv\\Scripts\\python -m pytest tests\\test_checklist_api.py -q
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

#: Naming the layer is now the ONLY way to turn the report on - the `enabled`
#: boolean it used to carry inside its own params block is gone. The default
#: detector rides along so these requests stay the chart the checklist is read
#: beside, which is what the extra-fetch counts below are counted against.
WITH_CHECKLIST = ["supply_demand", "checklist"]


def draw(**body):
    """A synthetic-provider draw, so no test here touches the network."""
    payload = {
        "symbol": "BTCUSDT",
        "interval": "15m",
        "bars": 2000,
        "provider": "synthetic",
        "layers": ["supply_demand"],
        **body,
    }
    response = client.post("/api/draw", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_checklist_is_absent_until_it_is_asked_for():
    """Off by default, and absent rather than empty.

    An empty report and no report mean different things: one says every item was
    checked and none was satisfied, the other says nothing was checked at all.
    """
    body = draw()

    assert body["checklist"] is None
    assert "checklist" not in body["meta"]


def test_enabling_it_alone_costs_no_provider_calls():
    """The quarterly items read the bars the chart already fetched.

    Worth pinning because the cost of this block is the reason it ships off, and
    a future change that quietly made the cheap half expensive would otherwise
    go unnoticed until a rate limit found it.
    """
    body = draw(layers=WITH_CHECKLIST, checklist={"degree": "day"})

    assert body["meta"]["checklist"]["extra_fetches"] == 0
    assert body["checklist"]["degree"] == "day"


def test_every_absent_item_says_why_it_is_absent():
    """`notes` is the difference between "not satisfied" and "not knowable".

    A profile is None while Q1 is still forming, which is a fact about the clock
    rather than a failed check, and a reader who cannot tell those apart will
    read the clock as a verdict.
    """
    report = draw(layers=WITH_CHECKLIST, checklist={"degree": "day"})["checklist"]

    absent = [k for k in ("dfr", "profile", "manipulation") if report[k] is None]
    assert len(report["notes"]) >= len(absent)


def test_the_bias_reads_every_timeframe_asked_for_in_order():
    body = draw(
        layers=WITH_CHECKLIST,
        checklist={
            "bias_timeframes": ["1d", "4h", "1h", "15m"],
            "bias_bars": 300,
        },
    )
    bias = body["checklist"]["bias"]

    assert [d["timeframe"] for d in bias["degrees"]] == ["1d", "4h", "1h", "15m"]
    # One call per timeframe, counted where a caller can see it.
    assert body["meta"]["checklist"]["extra_fetches"] == 4


def test_unknown_and_zero_are_different_and_neither_is_agreement():
    """The trap this whole block is built to avoid.

    `bias` is -1, 0 or null, and the three are different facts: null means the
    timeframe had too few bars to say, 0 means no break has happened yet. Either
    one counted as assent would tick a checklist item that nobody satisfied.
    """
    body = draw(
        layers=WITH_CHECKLIST,
        checklist={
            # 60 bars of daily is plenty; 60 of 15m is not enough for the wider
            # widths, which is how an UNKNOWN is produced without faking one.
            "bias_timeframes": ["1d", "15m"],
            "bias_bars": 60,
        },
    )
    bias = body["checklist"]["bias"]
    readings = {d["timeframe"]: d for d in bias["degrees"]}

    for reading in readings.values():
        if reading["bias"] is None:
            assert reading["reason"], "an UNKNOWN must say why"
            assert reading["timeframe"] in bias["disagreeing"] or not bias["aligned"]

    if any(r["bias"] is None for r in readings.values()):
        assert not bias["aligned"], "an UNKNOWN degree cannot be counted as aligned"


def test_a_divergence_against_invented_bars_is_labelled_as_such():
    """The synthetic provider makes up an instrument for ANY string.

    This test was written expecting a fetch failure and found the opposite: the
    synthetic provider seeds a series off the symbol's own name, so a typo does
    not fail, it produces a fictional partner. The run returned 76 divergences
    of BTCUSDT against "NOT_A_REAL_SYMBOL" - real arithmetic on fabricated bars,
    which is the most misleading kind of correct.

    It is not the provider's fault; inventing bars is what it exists for. What
    would be a defect is presenting the result as a reading of a market, so the
    response says so, the same way the cost table announces a fallback row
    instead of printing a number that looks measured.
    """
    body = draw(
        layers=WITH_CHECKLIST,
        checklist={
            "ssmt_symbols": ["NOT_A_REAL_SYMBOL"],
            "ssmt_degrees": ["day"],
        },
    )

    assert len(body["candles"]) > 0
    assert any(
        "synthetic provider" in n and "not a reading of any market" in n
        for n in body["checklist"]["notes"]
    ), body["checklist"]["notes"]


def test_a_symbol_that_cannot_be_fetched_does_not_take_the_chart_with_it():
    """Every zone, plan and candle in this response is still correct.

    Failing the whole request would throw away work that succeeded, for the sake
    of an optional block the caller added. Uses a provider that genuinely
    refuses an unknown symbol, which the synthetic one never does.
    """
    payload = {
        "symbol": "BTCUSD",
        "interval": "1h",
        "bars": 200,
        "provider": "binance",
        "layers": WITH_CHECKLIST,
        "checklist": {
            "ssmt_symbols": ["XAGUSD"],  # binance carries no silver
            "ssmt_degrees": ["day"],
        },
    }
    response = client.post("/api/draw", json=payload)
    if response.status_code != 200:
        pytest.skip(f"provider unreachable from this machine: {response.text[:80]}")
    body = response.json()

    assert len(body["candles"]) > 0
    assert body["checklist"]["ssmt"] == []
    assert any("SSMT unavailable" in n for n in body["checklist"]["notes"])


def test_the_report_never_collapses_to_a_single_verdict():
    """There is deliberately no overall pass or fail, and there must not be one.

    The five items have different provenance and different confidence - the
    defining range is single-sourced and unverified, manipulation is a clean
    conjunction, and the SSMT rate depends entirely on which instruments were
    paired. One boolean would hide which item is carrying the weight, and would
    present a checklist the owner ticks by hand as something the engine had
    validated. Nothing here has been measured against outcomes.
    """
    report = draw(layers=WITH_CHECKLIST)["checklist"]

    for banned in ("passed", "ok", "verdict", "score", "signal", "confidence"):
        assert banned not in report, f"the report must not carry a {banned!r} field"


@pytest.mark.parametrize("degree", ["day", "week", "session"])
def test_the_checklist_answers_at_every_degree_it_offers(degree):
    report = draw(layers=WITH_CHECKLIST, checklist={"degree": degree})["checklist"]

    assert report["degree"] == degree
    # Either it read something, or it said why it could not.
    assert report["dfr"] or report["notes"]


def _spy_on_the_basket(monkeypatch) -> dict:
    """Record what `load_aligned` was asked for, then serve it from synthetic.

    A spy rather than two real providers because the point under test is the
    ROUTING - which source the basket was requested from - and proving that with
    live feeds would put the network inside a unit test to observe an argument.
    """
    from app.aligned import load_aligned as real

    seen: dict = {}

    async def spy(symbols, interval, bars, provider=None):
        seen["provider"] = provider
        seen["symbols"] = list(symbols)
        return await real(symbols, interval, bars, "synthetic")

    monkeypatch.setattr("app.checklist.load_aligned", spy)
    return seen


def test_the_ssmt_basket_can_be_read_from_a_source_the_chart_is_not_on(monkeypatch):
    """The venue you trade and the complex you read divergence across need not
    be the same one, and forcing them to be makes one of the two wrong.

    Charting the local MT5 terminal is correct for levels - it is where orders
    fill - and would drag silver and copper onto that broker's CFDs with it.
    Measured against the live feeds on 2026-08-19, XAUUSD/XAGUSD/COPPER at 1h:
    the COMEX basket shared 398 bar times and returned 108 divergences, the same
    request on the broker's own CFDs shared 314 and returned 88. The venue is
    not a cosmetic choice, so it gets its own control and its own note.
    """
    seen = _spy_on_the_basket(monkeypatch)
    body = draw(
        layers=WITH_CHECKLIST,
        checklist={
            "ssmt_symbols": ["ETHUSDT"],
            "ssmt_degrees": ["day"],
            "ssmt_provider": "yahoo",
        },
    )

    assert seen["provider"] == "yahoo"
    # The CHART's symbol is in the basket and comes from the basket's source,
    # not reused from the chart. A basket spanning two venues is the artefact
    # aligned.py exists to prevent.
    assert seen["symbols"][0] == "BTCUSDT"
    assert body["meta"]["checklist"]["extra_fetches"] == len(seen["symbols"])
    assert any(
        "basket on yahoo" in n and "chart is drawn from synthetic" in n
        for n in body["checklist"]["notes"]
    ), body["checklist"]["notes"]


def test_the_basket_follows_the_chart_when_no_source_is_named(monkeypatch):
    """The default has to be "whatever the chart is on".

    A shipped default of one named venue would read the basket somewhere the
    user never chose, and would fail outright on a machine where that source is
    unavailable. It also costs one fetch less, because the chart's own bars are
    already in hand - which is the arithmetic the counter above has to get right.
    """
    seen = _spy_on_the_basket(monkeypatch)
    body = draw(
        layers=WITH_CHECKLIST,
        checklist={"ssmt_symbols": ["ETHUSDT"], "ssmt_degrees": ["day"]},
    )

    assert seen["provider"] == "synthetic"
    assert body["meta"]["checklist"]["extra_fetches"] == len(seen["symbols"]) - 1
    assert not any("basket on" in n for n in body["checklist"]["notes"])


def test_the_ssmt_layer_reports_its_own_counters_and_the_range_split():
    """`meta["ssmt"]` has been assigned since the layer shipped and the frontend
    declared no shape for it, so nothing rendered it - and extra JSON keys do not
    break TypeScript, which is why the one overlay that can fail for an external
    reason was the one overlay whose failure the panel could not show.

    The range split is asserted as a PARTITION of what was drawn rather than by
    value, because the values depend on the series: what must hold is that every
    drawn divergence is counted exactly once and that `unknown` is kept separate
    from `equilibrium` instead of folded into it.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "bars": 1500,
        "provider": "synthetic",
        "layers": ["ssmt"],
        "checklist": {
            "ssmt_symbols": ["ETHUSDT"],
            "ssmt_degrees": ["day"],
            "ssmt_max": 0,
        },
    }
    response = client.post("/api/draw", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    stats = payload["meta"]["ssmt"]

    drawn = payload["drawing"]["ssmt"]
    assert stats["drawn"] == len(drawn)
    assert stats["found"] >= stats["drawn"]
    assert stats["grid"], "the shared grid has to be reported, it is the layer's cost"

    bands = stats["range"]
    assert set(bands) == {"premium", "equilibrium", "discount", "unknown"}
    assert sum(bands.values()) == len(drawn), (
        "every drawn divergence belongs to exactly one band"
    )
    assert bands["unknown"] == sum(1 for d in drawn if d["range_pos"] is None), (
        "the warm-up is counted as unknown, never as equilibrium"
    )
    for d in drawn:
        if d["range_pos"] is None:
            continue
        expected = (
            "premium"
            if d["range_pos"] >= 0.75
            else "discount" if d["range_pos"] <= 0.25 else "equilibrium"
        )
        assert bands[expected] > 0, (d["range_pos"], expected, bands)

"""The wire contract for the four newest overlays.

Four modules with 58 tests between them were complete and unreachable until
`overlays.bar_overlays` and `checklist._discount` existed, and those two are pure
wiring. So these tests check what wiring can get wrong, which is a different
list from what the detectors can get wrong:

  - a block that is off must draw NOTHING, because every one of these is opt-in
    and a default that quietly drew would change every existing chart;
  - bar INDICES must not reach the wire, because an index means nothing to a
    client that trimmed or resampled the series;
  - a knob the request sets must actually reach the detector, which is the single
    most common way a params block ends up decorative;
  - and the counts in `meta` must describe the same objects the drawing holds.

Nothing here asserts a market fact. The detectors' own tests do that on
hand-built bars where the answer is arithmetic; these run through the API on the
synthetic provider so no test in this file touches the network.
"""

from __future__ import annotations

import pytest

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BASE = {
    "symbol": "BTCUSDT",
    "interval": "15m",
    "bars": 1500,
    "provider": "synthetic",
    "layers": [],
}


def draw(**patch: object) -> dict:
    body = client.post("/api/draw", json={**BASE, **patch})
    assert body.status_code == 200, body.text
    return body.json()


def test_every_new_overlay_is_off_by_default_and_draws_nothing():
    """Opt-in has to mean opt-in, or the ink budget moved without anyone asking.

    The chart's readability is a measured quantity in this project - five
    detectors already paint 31.6% of it - so a new overlay that drew by default
    would spend a budget someone else had already accounted for.

    Asked TWICE on purpose. Naming nothing must draw nothing, and that is the
    easy half. The half worth keeping is the request that omits `layers`
    entirely: each overlay used to carry its own `enabled` boolean defaulting to
    False, and that default is what this test was really pinning. It now lives
    in one place - `DEFAULT_LAYERS` - so a careless edit there could turn seven
    overlays on at once, and a fixture that always spells the list out would
    never see it.
    """
    default = client.post("/api/draw", json={k: v for k, v in BASE.items() if k != "layers"})
    assert default.status_code == 200, default.text

    for body in (draw(), default.json()):
        drawing = body["drawing"]
        for key in ("gaps", "event_horizons", "cisd", "pools"):
            assert drawing[key] == [], key
        assert "overlays" not in body["meta"]


def test_the_layer_catalogue_is_advertised_in_draw_order_and_says_what_each_is():
    """`/api/config` is the UI's ONE source of truth for what can be turned on.

    The ids are asserted in order because the registry's order is the draw order
    and is load-bearing - `supply_demand` has to run before anything appends to
    its zones. The `kind` is asserted because a UI still has to tell the three
    apart: an overlay draws no box, so it has no side and cannot be capped per
    side, and the report draws nothing at all. What is gone is the SPLIT: there
    used to be a `detectors` list and an `overlays` list, and a control could be
    wired to one while the engine read the other.
    """
    config = client.get("/api/config").json()
    assert [layer["id"] for layer in config["layers"]] == [
        "supply_demand", "fvg", "order_block", "ifvg", "breaker",
        "structure", "session", "vortex", "gaps", "chart_gaps", "psp", "wyckoff", "cisd", "dfr", "ssmt", "pools",
        "liquidity", "projections", "expectation", "news", "checklist",
    ]
    for layer in config["layers"]:
        assert layer["kind"] in ("detector", "overlay", "report"), layer
        # `evidence` is required so the UI cannot render a toggle without saying
        # what is known about it, and for most of these the honest answer is
        # nothing. An empty string would put the toggle back on the screen bare.
        assert layer["evidence"], layer["id"]
    assert "detectors" not in config and "overlays" not in config


def test_a_cisd_reaches_the_wire_as_times_and_never_as_bar_indices():
    """The detector counts in bar indices; the wire has always spoken in epochs.

    An index is meaningless to a client that trimmed or resampled the series, so
    the conversion happening in `bar_overlays` is load-bearing rather than
    cosmetic. The check that catches a missed conversion is that the run's bounds
    are TIMES present in the candle series - a leaked index would be a small
    integer and would fail on the first assertion.
    """
    body = draw(layers=["cisd"])
    events = body["drawing"]["cisd"]
    assert events, "the synthetic series produced no CISD to check"

    times = {c["time"] for c in body["candles"]}
    for event in events:
        for field in ("time", "run_from", "run_to"):
            assert event[field] in times, (field, event[field])
        assert event["run_from"] <= event["run_to"] < event["time"]
        assert event["direction"] in (-1, 1)
        assert event["run_length"] >= 2  # the shipped min_run floor

    meta = body["meta"]["overlays"]
    assert meta["cisd"] == len(events)
    # The runs are the population the events were selected FROM, so this ratio is
    # what a chosen-not-measured default owes its reader.
    assert meta["delivery_runs"] >= meta["cisd_found"]
    # Capped for readability like the structure overlay's events, and the cap must
    # be visible rather than silent: at the shipped floor 1200 bars of hourly gold
    # produce 131 of these, one on every ninth bar.
    assert meta["cisd_found"] >= meta["cisd"]
    assert meta["cisd"] <= 40


def test_the_cisd_knobs_change_the_answer_rather_than_the_presentation():
    """Both defaults were chosen and neither was measured, so both must be reachable.

    Raising the tolerance merges runs, which moves the level AND the bar the event
    lands on. If the request's knob were dropped on the floor the two responses
    would be identical, which is exactly the failure this asserts against.
    """
    # Uncapped on both sides: a display cap could hide the difference by trimming
    # both lists to the same recent tail, which would make this test pass for the
    # wrong reason.
    tight = draw(layers=["cisd"], cisd={"interrupt_tolerance": 0, "max_events": 0})
    loose = draw(layers=["cisd"], cisd={"interrupt_tolerance": 2, "max_events": 0})

    def signature(body: dict) -> list[tuple[int, float]]:
        return [(e["time"], e["level"]) for e in body["drawing"]["cisd"]]

    assert signature(tight) != signature(loose)
    # Merging runs cannot create more runs.
    assert (
        loose["meta"]["overlays"]["delivery_runs"]
        < tight["meta"]["overlays"]["delivery_runs"]
    )


def test_the_gaps_drawn_are_the_ones_the_levels_were_paired_from():
    """`keep` trims the BANDS as well as the levels, and the two must be one set.

    The first version of this wiring drew every gap and paired only the newest
    `keep`, which on 1200 bars of hourly gold put 53 bands on the chart beside 4
    levels derived from 5 of them - a picture that cannot be read back to its own
    inputs, and 53 bands each extended to the right edge is a wash rather than a
    drawing. `gaps_found` still reports the full population, the same way the
    cycle grid reports found against drawn.
    """
    wide = draw(layers=["gaps"], gaps={"keep": 0})
    narrow = draw(layers=["gaps"], gaps={"keep": 3})

    found = wide["meta"]["overlays"]["gaps_found"]
    assert found > 3, "the fixture must have more gaps than the cap, or this proves nothing"
    assert len(wide["drawing"]["gaps"]) == found
    assert narrow["meta"]["overlays"]["gaps_found"] == found
    assert len(narrow["drawing"]["gaps"]) == 3
    assert narrow["meta"]["overlays"]["gaps"] == 3

    # And the levels come from exactly those three. Adjacency is in PRICE order,
    # so dropping a gap deletes a level and re-pairs its neighbours rather than
    # trimming one edge - two values of `keep` are not nested sets.
    levels = narrow["drawing"]["event_horizons"]
    assert len(levels) == 2, "three retained gaps give exactly two levels"
    drawn = {g["open_time"] for g in narrow["drawing"]["gaps"]}
    for level in levels:
        assert level["lower_open_time"] in drawn
        assert level["upper_open_time"] in drawn
        assert level["knowable_at"] >= max(level["lower_open_time"], level["upper_open_time"])


def test_the_pool_display_cap_keeps_the_newest_and_prefers_the_ones_still_standing():
    """212 named rays is not a chart, so pools are capped the way quarters are.

    Recency is the right axis because that is what the fact is worth: a London
    high taken this morning kills an idea and the same fact from seven weeks ago
    does not. At equal age a standing pool outranks a taken one, since only a
    standing pool is still a candidate target.
    """
    uncapped = draw(layers=["pools"], pools={"max_pools": 0})
    capped = draw(layers=["pools"], pools={"max_pools": 6})

    found = uncapped["meta"]["overlays"]["pools_found"]
    assert found > 6, "the fixture must exceed the cap"
    assert len(uncapped["drawing"]["pools"]) == found
    assert len(capped["drawing"]["pools"]) == 6
    assert capped["meta"]["overlays"]["pools_found"] == found

    # The kept ones are the newest, and the counts describe what was DRAWN rather
    # than what was found - a cap that left the stats describing the full
    # population would report standing pools the chart never shows.
    newest = sorted(p["knowable_at"] for p in uncapped["drawing"]["pools"])[-6:]
    assert sorted(p["knowable_at"] for p in capped["drawing"]["pools"]) == newest
    assert capped["meta"]["overlays"]["pools_standing"] == sum(
        1 for p in capped["drawing"]["pools"] if p["taken_at"] is None
    )


def test_a_gap_read_off_coarse_bars_says_so_rather_than_pretending_to_be_exact():
    """ICT's own requirement is 1m or 5m bars, and the engine cannot refuse bars.

    A daily bar's close is the SETTLEMENT price, which is a different number from
    the last price that traded before 17:00, so a band read off coarse bars has an
    edge nothing ever traded at. The flag is the whole mitigation, and it is
    counted in `meta` because a reader who never opens a tooltip would not
    otherwise know.
    """
    hourly = draw(interval="1h", bars=800, layers=["gaps"])
    four_hour = draw(interval="4h", bars=800, layers=["gaps"])

    assert hourly["drawing"]["gaps"], "no gap to judge exactness on"
    assert hourly["meta"]["overlays"]["gaps_approximate"] == 0
    # The 4h bar that spans 17:00 does not end there, so nothing can be exact.
    assert four_hour["meta"]["overlays"]["gaps_approximate"] == len(
        four_hour["drawing"]["gaps"]
    )

    for gap in hourly["drawing"]["gaps"]:
        assert gap["kind"] in ("NDOG", "NWOG")
        assert gap["bottom"] <= gap["ce"] <= gap["top"]
        assert gap["ce"] == (gap["top"] + gap["bottom"]) / 2


def test_a_pool_reports_whether_the_feed_covered_its_whole_window():
    """A partial window's high is NOT the session high, and the two must not merge.

    `covered` is a fact about the FEED and `taken_at` is a fact about the market.
    Counting them together would let a truncated series look like a swept level.
    """
    body = draw(layers=["pools"], pools={"sessions": ["asia", "london"]})
    pools = body["drawing"]["pools"]
    assert pools, "the synthetic series covered no session window"

    meta = body["meta"]["overlays"]
    assert meta["pools"] == len(pools)
    assert meta["pools_standing"] == sum(1 for p in pools if p["taken_at"] is None)
    assert meta["pools_partial"] == sum(1 for p in pools if not p["covered"])

    times = {c["time"] for c in body["candles"]}
    for pool in pools:
        assert pool["side"] in ("BSL", "SSL")
        assert pool["session"] in ("asia", "london")
        assert pool["window_from"] < pool["window_to"]
        # Nothing may be reported before the session that made it closed.
        assert pool["knowable_at"] >= pool["window_from"]
        if pool["taken_at"] is not None:
            assert pool["taken_at"] in times
            # `>=`, not `>`. `knowable_at` is the first bar AFTER the window - the
            # bar whose existence proves the session closed - and that same bar
            # may be the one that trades through the level. This assertion said
            # `>` first and failed on a pool taken the instant it became
            # knowable, which is a legitimate sequence and not a lookahead.
            assert pool["taken_at"] >= pool["knowable_at"]


def test_an_unknown_session_name_is_reported_instead_of_taking_the_chart_down():
    """One bad name must not cost the caller a correct chart.

    The same choice `session_grid` makes for an unknown degree, and for the same
    reason: every other shape in the response is still right, and a 502 would hide
    all of them to punish a typo.
    """
    body = draw(layers=["pools"], pools={"sessions": ["asia", "tokyo-ish"]})
    assert body["meta"]["overlays"]["unknown_sessions"] == ["tokyo-ish"]
    assert all(p["session"] == "asia" for p in body["drawing"]["pools"])


def test_the_discount_item_reports_every_anchor_and_names_any_disagreement():
    """His third question is single-sourced, so one boolean would be a lie by omission.

    The anchor is a judgement rather than a citation, and the anchors can disagree
    on the same bar. When they do, the disagreement is pushed into `notes` rather
    than left in a field nobody opens - a reader who quotes "in discount" while
    another anchor said premium has been misled by this engine, not by the market.
    """
    body = draw(
        layers=["checklist"],
        checklist={"degree": "session", "discount_anchor": "parent_cycle"},
    )
    report = body["checklist"]
    discount = report["discount"]
    assert discount is not None, report["notes"]

    assert discount["anchor"] == "parent_cycle"
    # Every candidate anchor must be ACCOUNTED FOR, either with a reading or with
    # a reason it has none. An anchor that silently vanished would make the three
    # readings look like agreement when one of them was never asked.
    from app.pools import ANCHORS

    assert len(discount["readings"]) + len(discount["absent"]) == len(ANCHORS)
    for reading in discount["readings"]:
        assert reading["low"] <= reading["equilibrium"] <= reading["high"]
        assert reading["equilibrium"] == (reading["high"] + reading["low"]) / 2
        assert reading["reading"] in ("premium", "discount", "equilibrium")
        # The parent of `session` is the day, and never the degree being traded.
        assert reading["degree"] == "day"

    if discount["disagree"]:
        assert any("anchors do not agree" in note for note in report["notes"])

    # The checklist reads its ranges off the bars already fetched, so adding this
    # item must not have added a provider call.
    assert body["meta"]["checklist"]["extra_fetches"] == 0


def test_the_checklist_still_refuses_to_report_an_overall_verdict():
    """Five items now, and still no pass or fail anywhere in the payload.

    This is the assertion that has to survive every future item. The five have
    different provenance and different confidence, and a single boolean would
    present a checklist its owner ticks BY HAND as something this engine had
    validated. None of the five has been measured against outcomes.
    """
    report = draw(layers=["checklist"], checklist={"degree": "session"})["checklist"]
    for forbidden in ("passed", "verdict", "ok", "score", "confidence", "signal"):
        assert forbidden not in report, forbidden
    # The exact set, not a count, and it grows by hand. Every new item has to be
    # added here deliberately, which is the whole mechanism: a field called
    # `passed` could otherwise arrive with a feature and nobody would notice
    # until the panel had already rendered a green tick.
    assert set(report) == {
        "degree", "dfr", "profile", "manipulation", "discount", "chain", "stacked",
        "bias", "ssmt", "judas", "news", "news_impact", "cot", "notes",
        "regime", "atr_budget", "volatility_index",
        "htf_pd_array", "cisd_htf", "sweep_signal",
    }
    # And the two newest are readings, not judgements: a chain is a clock fact
    # and a stack is a count of levels, so neither may carry a pass.
    for item in ("chain", "stacked"):
        if report[item] is not None:
            assert "passed" not in report[item] and "ok" not in report[item], item


def test_named_levels_reach_the_wire_and_say_which_day_boundary_made_them():
    """A PDH measured 18:00-to-18:00 is a DIFFERENT number from one measured
    midnight-to-midnight, so the boundary travels with the level.

    The engine's own grid opens the day at 18:00 New York, which is also the CME
    open, so `cycle` is the default. But no source says which one his own PDH is
    read on - that makes it a judgement, and a judgement has to stay visible and
    stay reversible rather than being baked in silently.
    """
    body = draw(layers=["liquidity"], liquidity={"periods": ["day", "week"]})
    levels = body["drawing"]["levels"]
    assert levels, "the fixture produced no previous-period level"

    names = {level["name"] for level in levels}
    assert names & {"PDH", "PDL"}, names
    for level in levels:
        assert level["boundary"] == "cycle"
        assert level["side"] in ("BSL", "SSL")
        assert level["knowable_at"] >= level["window_to"] - 1
        # Not a covered flag. A day cycle ALWAYS ends in a market closure, so a
        # boolean would read False on every correct level; the seconds say how
        # much of the window had no bars without pretending that is a fault.
        assert level["gap_at_open"] >= 0 and level["gap_at_close"] >= 0

    other = draw(
        layers=["liquidity"],
        liquidity={"periods": ["day"], "boundary": "midnight"},
    )["drawing"]["levels"]
    assert all(level["boundary"] == "midnight" for level in other)
    assert {level["price"] for level in other} != {
        level["price"] for level in levels if level["name"] in ("PDH", "PDL")
    }, "the two boundaries must not agree, or the parameter is decorative"


def test_the_draw_on_liquidity_never_resolves_to_one_direction():
    """Naming the draw is a forecast, and twelve of those have failed here.

    The symmetry is the point rather than a shortcoming: there is untaken
    liquidity above and below at every moment, and any method that picks one is
    supplying the direction from somewhere other than this list.
    """
    body = draw(
        layers=["liquidity"],
        liquidity={
            "periods": ["day", "week"],
            "draw_candidates": True,
        },
    )
    dol = body["draw_on_liquidity"]
    assert dol is not None
    # NOT "both sides are populated". This assertion said that first and was
    # wrong: price that has run above every previous-period high leaves nothing
    # untaken above it, and the synthetic series does exactly that some runs. An
    # empty side is a fact about what has already been swept. What must hold is
    # that the engine never nominates one - so the check is on the CONTENTS of
    # whichever sides exist, plus the absence of any field that picks.
    assert dol["above"] or dol["below"], "no candidates at all means no levels were read"
    for side, sign in (("above", 1), ("below", -1)):
        for candidate in dol[side]:
            assert (candidate["price"] - dol["price"]) * sign > 0, (side, candidate)
            assert candidate["distance"] > 0
    # No field anywhere may nominate one of them.
    assert not {"target", "draw", "chosen", "expected"} & set(dol)


def test_a_projection_is_drawn_in_both_directions_unless_one_is_asked_for():
    """Direction on his own charts is read from where price went AFTER the range.

    That is hindsight, and the engine will not supply a direction it cannot know.
    Zero means both, and both is the default; the cost is twice the ink and the
    benefit is that no line on the screen is a guess.
    """
    both = draw(layers=["projections"], projections={"sessions": ["london"]})
    stacks = both["drawing"]["projections"]
    assert len(stacks) == 2, [s["label"] for s in stacks]
    assert {s["direction"] for s in stacks} == {1, -1}

    one = draw(
        layers=["projections"],
        projections={"sessions": ["london"], "direction": -1},
    )["drawing"]["projections"]
    assert len(one) == 1 and one[0]["direction"] == -1

    # The geometry, checked rather than trusted: multiple 0 sits ON the origin,
    # and every other level is that many range-heights away from it.
    stack = one[0]
    assert stack["height"] == stack["high"] - stack["low"]
    for level in stack["levels"]:
        expected = stack["origin"] - stack["direction"] * level["multiple"] * stack["height"]
        assert abs(level["price"] - expected) < 1e-6, level


def test_the_quarter_chain_is_a_clock_fact_and_carries_its_own_base_rate():
    """His ten chains are ten of the sixty-four, and 15.6% is not rare.

    Nobody has measured whether the listed chains behave differently from the
    unlisted ones, so the flag has to arrive beside the number that makes it
    readable. `in_his_list` is also named so it cannot be mistaken for odds.
    """
    report = draw(
        layers=["checklist"],
        checklist={
            "degree": "day",
            "chain_degrees": ["day", "session", "micro"],
        },
    )["checklist"]
    chain = report["chain"]
    assert chain is not None, report["notes"]

    assert chain["degrees"] == ["day", "session", "micro"]
    assert len(chain["quarters"]) == 3
    assert all(1 <= q <= 4 for q in chain["quarters"])
    assert chain["compact"] == "".join(str(q) for q in chain["quarters"])
    assert chain["text"] == "-".join(str(q) for q in chain["quarters"])
    assert chain["in_his_list"] == (chain["compact"] in {
        "111", "114", "141", "144", "222", "333", "411", "414", "441", "444",
    })
    assert abs(chain["base_rate"] - 10 / 64) < 1e-9
    # Asking for a degree finer than the bars can address has to be SAID, because
    # a micro quarter is 1350 seconds and no standard interval divides it.
    assert any("1350 seconds" in note for note in report["notes"])


def test_the_stacked_opens_count_is_a_count_and_not_a_recommendation():
    """His precondition is that at least two true opens agree before he acts.

    The engine counts them and stops there. Every level lands on exactly one side
    of the price, so the two lists partition the drawn opens with nothing lost.
    """
    body = draw(
        layers=["session", "checklist"],
        session={"quarters": [], "true_opens": ["day", "week"], "max_quarters": 0},
        checklist={"degree": "day"},
    )
    stacked = body["checklist"]["stacked"]
    drawn = body["drawing"]["true_opens"]
    if not drawn:
        return  # no bar opened on a boundary in this window; nothing to count
    assert stacked is not None
    assert len(stacked["above"]) + len(stacked["below"]) == len(drawn)
    for level in stacked["above"]:
        assert level["price"] > stacked["price"]
    for level in stacked["below"]:
        assert level["price"] < stacked["price"]
    assert not {"aligned", "verdict", "enough"} & set(stacked)


def test_the_adopted_gap_readings_reach_the_wire_with_their_provenance():
    """Four readings reconstructed from a closed-source indicator's rendered output.

    They are adopted because the arithmetic reproduced its published numbers
    exactly, not because anyone read its code - which nobody can, the script is
    protected. That provenance is why each one is checked here for SHAPE rather
    than for market truth: none of them has been measured against outcomes by
    this project or by the indicator's author.
    """
    body = draw(layers=["gaps"], gaps={"keep": 0}, interval="1h", bars=2000)
    gaps = body["drawing"]["gaps"]
    assert gaps, "the fixture produced no gap to read"
    stats = body["meta"]["overlays"]

    # The ordinal counts per KIND and starts at 1 for the newest of that kind.
    by_kind: dict[str, list[dict]] = {}
    for gap in gaps:
        by_kind.setdefault(gap["kind"], []).append(gap)
    for kind, group in by_kind.items():
        prefix = "D" if kind == "NDOG" else "W"
        newest = max(group, key=lambda g: g["open_time"])
        assert newest["label"] == f"{prefix}-1", (kind, newest["label"])
        ordinals = sorted(int(g["label"].split("-")[1]) for g in group)
        assert ordinals == list(range(1, len(group) + 1)), (kind, ordinals)

    # The distance is signed and measured to the ENCROACHMENT, never to an edge.
    price = body["candles"][-1]["close"]
    for gap in gaps:
        assert gap["distance_to_ce"] == pytest.approx(price - gap["ce"])
        assert gap["distance_to_ce"] != pytest.approx(price - gap["top"]) or (
            gap["top"] == gap["ce"]
        )

    # A degree label belongs only to a weekend gap, and it is a LABEL rather than
    # a fifth kind: the gap keeps its own kind either way.
    for gap in gaps:
        if gap["degree"] is not None:
            assert gap["kind"] == "NWOG", gap
            assert gap["degree"] in ("month", "year")
    assert set(stats["gaps_by_degree"]) == {"month", "year"}


def test_a_gap_stack_pairs_different_kinds_and_carries_its_own_denominator():
    """Two gaps of the SAME kind overlapping is not a stack.

    The construct is a lower degree landing on a higher one, so an NDOG on an
    NDOG says nothing. And the fraction is the overlap over the SMALLER band,
    which is a reconstruction: the same two bands give 29% by union and 30% by
    the larger band, so this assertion is what keeps the chosen denominator from
    being swapped without anyone noticing.
    """
    body = draw(layers=["gaps"], gaps={"keep": 0}, interval="1h", bars=2000)
    stacks = body["drawing"]["gap_stacks"]
    assert stacks, "no stack in the fixture"
    assert body["meta"]["overlays"]["gap_stacks"] == len(stacks)

    gaps = {g["open_time"]: g for g in body["drawing"]["gaps"]}
    for st in stacks:
        assert set(st["kinds"]) == {"NDOG", "NWOG"}, st["kinds"]
        assert st["top"] > st["bottom"], "a stack must have height"
        assert 0 < st["fraction"] <= 1.0

        a, b = (gaps[t] for t in st["open_times"])
        # The overlap really is the intersection of the two bands.
        assert st["top"] == pytest.approx(min(a["top"], b["top"]))
        assert st["bottom"] == pytest.approx(max(a["bottom"], b["bottom"]))
        smaller = min(a["top"] - a["bottom"], b["top"] - b["bottom"])
        assert st["fraction"] == pytest.approx((st["top"] - st["bottom"]) / smaller)
        # Knowable only once BOTH gaps were.
        assert st["knowable_at"] == max(a["open_time"], b["open_time"])


def test_the_tier_zone_carries_the_reduction_that_made_it():
    """Three gaps per kind is sourced; how they become one zone is not.

    The reduction therefore travels on every zone rather than sitting in a
    constant nobody reads. A band whose rule is unstated would read as settled
    when it is the one part of this construct that is still open.
    """
    body = draw(layers=["gaps"], gaps={"keep": 0}, interval="1h", bars=2000)
    tiers = body["drawing"]["tier_horizons"]
    assert tiers, "the fixture produced no tier"
    assert body["meta"]["overlays"]["tier_horizons"] == len(tiers)
    assert body["meta"]["overlays"]["tier_reduction"] == "envelope"

    gaps = {g["open_time"]: g for g in body["drawing"]["gaps"]}
    for tier in tiers:
        assert tier["kind"] in ("NDOG", "NWOG")
        assert tier["reduction"] == "envelope"
        assert tier["top"] > tier["bottom"]
        assert tier["ce"] == pytest.approx((tier["top"] + tier["bottom"]) / 2)
        assert len(tier["open_times"]) == 3, "the owner's own retention"
        # The envelope really is the envelope of its own inputs.
        used = [gaps[t] for t in tier["open_times"] if t in gaps]
        if len(used) == 3:
            assert tier["top"] == pytest.approx(max(g["top"] for g in used))
            assert tier["bottom"] == pytest.approx(min(g["bottom"] for g in used))
        # Knowable only once the newest of its gaps was.
        assert tier["knowable_at"] == max(tier["open_times"])


def test_the_four_reductions_reach_the_wire_and_disagree():
    """If two of them agreed, a swapped default could pass unnoticed - and the
    default is known NOT to match the reference indicator, so it is exactly the
    kind of value that gets quietly 'corrected' by someone later."""
    bands = {}
    for how in ("envelope", "ce_span", "newest", "eh_span"):
        tiers = draw(
            layers=["gaps"], gaps={"keep": 0, "tier_reduction": how},
            interval="1h", bars=2000,
        )["drawing"]["tier_horizons"]
        assert tiers, how
        assert all(t["reduction"] == how for t in tiers)
        bands[how] = tuple(sorted((t["kind"], t["top"], t["bottom"]) for t in tiers))

    assert len(set(bands.values())) == len(bands), bands


def test_an_unknown_tier_reduction_is_refused_rather_than_defaulted():
    """A typo falling back to the default would ship a zone the caller did not
    ask for, and the four disagree by construction."""
    body = client.post(
        "/api/draw",
        json={**BASE, "layers": ["gaps"], "gaps": {"tier_reduction": "middle"}},
    )
    # 422, like every other invalid parameter in this API. It was a 500 first,
    # because the reduction was a plain string and the error surfaced from deep
    # inside the reducer - which is the same class of answer as a stack trace.
    assert body.status_code == 422, body.text[:200]
    assert "tier_reduction" in body.text


def test_a_field_name_this_api_does_not_know_is_refused_rather_than_ignored():
    """The misspelling that produced a wrong measurement and looked right.

    Five providers were compared by sending `source`, a field this request has
    never had. Pydantic's default is to ignore the unknown, so every one of the
    five came back 200 carrying the DEFAULT provider's data - the same prices,
    the same bar times, five rows of a table that looked like five providers and
    was one. Nothing in the response said a field had been dropped.

    `provider` still has to work, and is asserted in the same test: a rule that
    refuses the right spelling too would be worse than the shrug it replaced.
    """
    typo = client.post("/api/draw", json={**BASE, "source": "yahoo"})
    assert typo.status_code == 422, typo.text[:200]
    assert "source" in typo.text

    right = client.post("/api/draw", json={**BASE, "provider": "synthetic"})
    assert right.status_code == 200, right.text[:200]
    assert right.json()["provider"] == "synthetic"


def test_the_calendar_is_absent_unless_it_is_asked_for():
    """Off by default, and that matters more here than for the other overlays.

    Every other layer reads bars already fetched. This one reaches a third party
    that RATE LIMITS - measured at three or four requests inside about two
    minutes - so a default that drew it would put every chart redraw against
    someone else's quota.
    """
    body = draw()
    assert body["drawing"]["news"] == []
    assert "news" not in body["meta"]


def test_the_calendar_is_filtered_and_clipped_to_the_bars_on_screen(monkeypatch):
    """The wiring, with no socket touched.

    A test that hit the real feed would be actively harmful: the host rate
    limits, and a suite run would spend the same quota the app needs. So the
    reader is replaced and what is checked is what the WIRING does - the impact
    filter, the currency filter, the clip to the drawn window, and the counts in
    `meta` describing the same events the drawing holds.
    """
    from app import news as news_mod
    from app import overlays as app_overlays

    body_probe = draw()
    last = body_probe["candles"][-1]["time"]

    # Anchored to bars that EXIST, plus a minute so the release still sits
    # between two opens and still exercises the snap-into-a-bar path. A fixed
    # offset from the first bar used to do this job and stopped working the day
    # the synthetic market learned to close: `first + 7200` landed at 17:00 New
    # York, the feed had no bar there, and the release was correctly dropped as
    # falling while the market was shut - so a test about the CURRENCY filter
    # failed for a reason that had nothing to do with currencies.
    inside_high = news_mod.NewsEvent(
        time=body_probe["candles"][10]["time"] + 60,
        title="Non-Farm Employment Change",
        currency="USD", impact="High", forecast="150K", previous="",
    )
    inside_low = news_mod.NewsEvent(
        time=body_probe["candles"][20]["time"] + 60, title="Something Quiet",
        currency="EUR", impact="Low", forecast="", previous="1.0%",
    )
    outside = news_mod.NewsEvent(
        time=last + 86_400, title="Next Week",
        currency="USD", impact="High", forecast="", previous="",
    )
    week = news_mod.NewsWeek(
        events=(inside_high, inside_low, outside),
        covers_from=inside_high.time,
        covers_to=outside.time,
    )

    async def fake_read(ttl_seconds: int = 0) -> news_mod.NewsWeek:
        return week

    monkeypatch.setattr(app_overlays.news_feed, "read", fake_read)

    body = draw(layers=["news"], news={"impacts": ["High"], "currencies": []})
    drawn = body["drawing"]["news"]
    assert [e["title"] for e in drawn] == ["Non-Farm Employment Change"], drawn
    # The absent forecast stayed absent rather than becoming a number.
    assert drawn[0]["previous"] == ""
    assert drawn[0]["forecast"] == "150K"

    stats = body["meta"]["news"]
    assert stats["news_found"] == 3, "found counts the whole feed"
    assert stats["news"] == len(drawn), "drawn counts what the chart can show"
    assert "days" in stats["news_window"], stats

    # The currency filter is a separate axis from impact.
    only_eur = draw(
        layers=["news"], news={"impacts": ["High", "Low"], "currencies": ["EUR"]}
    )["drawing"]["news"]
    assert [e["currency"] for e in only_eur] == ["EUR"]


def test_a_release_between_two_bars_is_placed_inside_one_rather_than_dropped(
    monkeypatch,
):
    """The defect this pins was found by looking at the chart, not at a number.

    Five releases were counted in `meta` and two were drawn. The three missing
    ones were the 08:30 New York rows: that is 12:30 UTC, no hourly bar opens
    then, and the chart asks the time scale for a coordinate by the release's
    OWN minute. It answered null three times, silently.

    So the placement is computed here, where the bar times are: the bar the
    release fell inside, and how far into it. Half a bar in must come back as
    half, because that is what the chart multiplies by the bar spacing.
    """
    from app import news as news_mod
    from app import overlays as app_overlays

    # A bar that EXISTS and whose successor exists, read off the response rather
    # than counted from the first bar. `first + 4 * step` used to do this job and
    # stopped working the day the synthetic market learned to close: a fixed
    # offset can land in the 17:00 New York hole, where there is no bar to be
    # half way into and the release is correctly dropped as falling while the
    # market was shut. The test then failed for a reason that had nothing to do
    # with placement. Picked from a window rather than a single index so a run
    # whose bar 4 happens to sit against a hole still finds a pair.
    candles = draw()["candles"]
    times = [c["time"] for c in candles]
    # The bar interval is the SMALLEST gap in the series, not the gap between two
    # chosen bars: any particular pair can straddle a session hole, and taking
    # `candles[2] - candles[1]` as the step did exactly that on one run and left
    # the search below with nothing to find.
    step = min(b - a for a, b in zip(times, times[1:]))
    anchor = next(a for a, b in zip(times, times[1:]) if b - a == step)

    mid = news_mod.NewsEvent(
        time=anchor + step // 2, title="CPI m/m",
        currency="CAD", impact="High", forecast="", previous="",
    )
    on_open = news_mod.NewsEvent(
        time=anchor, title="Claimant Count Change",
        currency="GBP", impact="High", forecast="", previous="",
    )
    week = news_mod.NewsWeek(
        events=(mid, on_open), covers_from=on_open.time, covers_to=mid.time
    )

    async def fake_read(ttl_seconds: int = 0) -> news_mod.NewsWeek:
        return week

    monkeypatch.setattr(app_overlays.news_feed, "read", fake_read)

    drawn = draw(layers=["news"])["drawing"]["news"]
    by_title = {e["title"]: e for e in drawn}
    assert len(drawn) == 2, "a release off the bar open is still a release"
    assert by_title["CPI m/m"]["bar"] == anchor
    assert by_title["CPI m/m"]["offset"] == 0.5
    # The easy case must not have been broken to fix the hard one.
    assert by_title["Claimant Count Change"]["bar"] == anchor
    assert by_title["Claimant Count Change"]["offset"] == 0.0


def test_a_release_while_the_market_was_shut_is_counted_and_not_nailed_to_a_bar(
    monkeypatch,
):
    """A hole in the bars is not a bar, and a mark there would be a lie.

    Gold stops for the weekend and again for the daily break, so a release can
    fall between two bars that are not one interval apart. Placing it would put
    the mark inside the last candle before the hole - at a time that candle did
    not cover. It is dropped, and SAID, because a count that quietly shrank is
    the same failure as a chart that quietly drew nothing.
    """
    from app import main as app_main
    from app import news as news_mod
    from app import overlays as app_overlays
    from app.models import Candle

    step = 900
    base = 1_700_000_000
    # Twenty bars, then a two hour hole, then twenty more.
    rows = [
        Candle(time=base + i * step, open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0)
        for i in range(20)
    ] + [
        Candle(
            time=base + 20 * step + 7200 + i * step,
            open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0,
        )
        for i in range(20)
    ]

    async def fake_fetch(symbol, interval, bars, provider):
        return rows, "synthetic"

    in_hole = news_mod.NewsEvent(
        time=base + 20 * step + 3600, title="Weekend Row",
        currency="USD", impact="High", forecast="", previous="",
    )
    after = news_mod.NewsEvent(
        time=base + 20 * step + 7200 + step, title="Monday Open Row",
        currency="USD", impact="High", forecast="", previous="",
    )
    week = news_mod.NewsWeek(
        events=(in_hole, after), covers_from=in_hole.time, covers_to=after.time
    )

    async def fake_read(ttl_seconds: int = 0) -> news_mod.NewsWeek:
        return week

    monkeypatch.setattr(app_main, "fetch", fake_fetch)
    monkeypatch.setattr(app_overlays.news_feed, "read", fake_read)

    body = draw(layers=["news"])
    drawn = body["drawing"]["news"]
    assert [e["title"] for e in drawn] == ["Monday Open Row"], drawn
    stats = body["meta"]["news"]
    assert stats["news"] == 1
    assert stats["news_market_shut"] == 1, "the dropped one has to be spoken"


def test_a_calendar_outage_is_spoken_rather_than_drawn_as_a_quiet_week(monkeypatch):
    """An empty chart and a dead feed must not look the same.

    The reader reports the upstream's own words, and the wiring has to carry
    them through: a silent empty list would let a rate limit read as "no
    releases scheduled", which is the failure this whole project refuses.
    """
    from app import news as news_mod
    from app import overlays as app_overlays

    async def fake_read(ttl_seconds: int = 0) -> news_mod.NewsWeek:
        return news_mod.NewsWeek(
            events=(), covers_from=None, covers_to=None,
            error="HTTP 429 from the calendar feed: Rate Limited",
        )

    monkeypatch.setattr(app_overlays.news_feed, "read", fake_read)

    body = draw(layers=["news"])
    assert body["drawing"]["news"] == []
    stats = body["meta"]["news"]
    assert "429" in stats["news_error"], stats
    assert "news_window" not in stats, "no window may be invented from no data"


def test_every_registered_layer_is_actually_dispatched():
    """A layer in the registry that nothing dispatches draws nothing, silently.

    This is not hypothetical. `dfr` shipped registered in `app/layers.py`, given
    a params block, a response field, a toolbox panel and a canvas primitive -
    and drew nothing on any chart, because `drawing.build` gated the overlay
    helper on a hand-written set of five names that nobody added the sixth to.
    Every visible sign said the layer worked. The only way to see it did not was
    to read the drawing.

    So the registry is the source of truth and this test is the seam: a layer
    reaches the canvas through a handler, through the bar-overlay helper, or
    through the async path in `main.draw` that is allowed to make provider
    calls. Anything in none of the three is dead wiring.
    """
    from app.drawing import _HANDLERS
    from app.layers import LAYERS
    from app.overlays import BAR_OVERLAYS

    # The four that cannot be dispatched synchronously: each needs a network
    # call, so `main.draw` handles them and `build` cannot. Named rather than
    # inferred, so adding a fifth is a decision someone writes down.
    #
    # `psp` is the fourth, added 1 September 2026. It reads the SSMT events and
    # the partner bars, so it rides the aligned fetch `_draw_ssmt` already makes
    # rather than paying for the same basket twice. This test is what caught it
    # being registered before it was dispatched, which is the job it was written
    # for.
    ASYNC_DISPATCHED = {"ssmt", "news", "checklist", "psp"}

    dispatched = set(_HANDLERS) | set(BAR_OVERLAYS) | ASYNC_DISPATCHED
    orphans = sorted(layer.id for layer in LAYERS if layer.id not in dispatched)
    assert not orphans, f"registered but never drawn: {orphans}"


def test_the_defining_range_draws_both_sides_of_every_multiple():
    """The one object here whose rule came from a single unverified paragraph.

    Its geometry is arithmetic and the wire has to carry it exactly: a band's
    midpoint is its midpoint, and an extension is `abs(multiple)` of the band's
    own height measured OUTWARD from the edge it belongs to. Both sides, because
    the source states the numbers and never states a direction - drawing one
    side would invent the half nobody published, and the reader could not tell
    which half was invented.
    """
    body = draw(layers=["dfr"], dfr={"degrees": ["day"], "max_ranges": 3})
    bands = body["drawing"]["dfr"]
    assert bands, "a day degree over 1500 bars has to yield some Q1s"
    assert len(bands) == 3, "the display cap has to bind"
    stats = body["meta"]["overlays"]
    assert stats["dfr_found"] >= stats["dfr"], stats

    for band in bands:
        height = band["high"] - band["low"]
        assert height > 0
        assert band["equilibrium"] == pytest.approx((band["high"] + band["low"]) / 2)
        assert band["time_from"] < band["time_to"], "a window with no width is not one"
        sides = {(e["multiple"], e["side"]): e["price"] for e in band["extensions"]}
        for multiple in (-0.5, -1.0):
            reach = abs(multiple) * height
            assert sides[(multiple, "above")] == pytest.approx(band["high"] + reach)
            assert sides[(multiple, "below")] == pytest.approx(band["low"] - reach)


def test_an_unknown_dfr_degree_is_reported_rather_than_raised():
    """One bad name must not take a correct chart down - the same choice the
    cycle grid makes. And it must not be swallowed either: before this counter
    existed, a typo'd degree drew nothing and said nothing."""
    body = draw(layers=["dfr"], dfr={"degrees": ["day", "fortnight"]})
    stats = body["meta"]["overlays"]
    assert stats["dfr_unknown_degrees"] == ["fortnight"], stats
    assert body["drawing"]["dfr"], "the good degree still has to draw"


def test_dfr_zero_cap_keeps_every_band_so_measurement_can_use_it():
    """A recency cap silently confines a sample to the tail of the history, and
    this one multiplies - each band dropped takes its projections with it. 0 is
    the escape hatch every measurement in this project is required to use."""
    capped = draw(layers=["dfr"], dfr={"degrees": ["day"], "max_ranges": 2})
    every = draw(layers=["dfr"], dfr={"degrees": ["day"], "max_ranges": 0})
    found = capped["meta"]["overlays"]["dfr_found"]
    assert len(every["drawing"]["dfr"]) == found > 2, found
    # And the cap keeps the NEWEST, not the first it happened to build.
    assert capped["drawing"]["dfr"] == every["drawing"]["dfr"][-2:]


def test_the_quadrennial_true_open_reaches_the_wire_only_when_asked_to():
    """The full path for the degree a practitioner said was missing.

    Both halves matter. The degree has to be accepted by the grid at all - it
    lives in `ALL_DEGREES` and deliberately not in `DEGREES`, so a validator
    reading the wrong tuple would reject it - and its level has to stay absent
    under the strict rule, because that rule is what every measurement here was
    taken under and it is the default.
    """
    body = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "bars": 1500,
        "provider": "synthetic",
        "layers": ["session"],
        "session": {
            "quarters": ["quadrennial"],
            "true_opens": ["quadrennial"],
            "max_quarters": 0,
        },
    }
    strict = draw(**body)
    stats = strict["meta"]["session"]
    assert "unknown_degrees" not in stats, stats
    # A four-year cycle over 1500 hourly bars spans one quarter, maybe two.
    assert strict["drawing"]["quarters"], "the degree has to produce boxes"
    assert {q["degree"] for q in strict["drawing"]["quarters"]} == {"quadrennial"}
    assert all(q["label"] in {"Q1", "Q2", "Q3", "Q4"} for q in strict["drawing"]["quarters"])

    loose = draw(**{**body, "session": {**body["session"], "approximate_true_opens": True}})
    for level in loose["drawing"]["true_opens"]:
        assert level["degree"] == "quadrennial"
        # The level belongs to its BOUNDARY; the bar it was read from is separate
        # and never earlier.
        assert level["bar"] >= level["time"]
        assert level["approximate"] is (level["bar"] != level["time"])
    approximate = [o for o in loose["drawing"]["true_opens"] if o["approximate"]]
    if approximate:
        assert loose["meta"]["session"]["true_opens_approximate"] == len(approximate)


def test_an_exact_true_open_never_carries_the_approximate_flag_or_a_moved_bar():
    """The flag has to describe the LEVEL, not the request. With the relaxation
    on, a daily boundary that does have a bar still reports `approximate: false`
    and a `bar` equal to its own boundary - otherwise the dashed line on the
    canvas would be saying something untrue about a measured level."""
    for flag in (False, True):
        body = draw(
            layers=["session"],
            session={
                "quarters": [],
                "true_opens": ["day"],
                "approximate_true_opens": flag,
                "max_quarters": 0,
            },
        )
        levels = body["drawing"]["true_opens"]
        assert levels, "a fortnight of 15m bars has daily true opens"
        exact = [o for o in levels if o["bar"] == o["time"]]
        assert exact, "at least some daily boundaries have a bar on them"
        assert all(o["approximate"] is False for o in exact)
        if not flag:
            assert all(o["approximate"] is False for o in levels)
            assert all(o["bar"] == o["time"] for o in levels)


def test_fibonacci_is_absent_unless_structure_is_on():
    """The OTE grid is a structure reading, so off means off.

    A Fibonacci anchor off by default that quietly drew would change every
    existing chart, the same way any opt-in layer that drew would. The anchor
    rides on the structure layer and must stay null until that layer is asked
    for.
    """
    body = draw()
    assert body["drawing"]["fibonacci"] is None


def test_fibonacci_matches_the_last_confirmed_swing_anchors():
    """The two anchors are the backend's own reading, not a frontend re-derivation.

    The chart used to compute these client-side from the returned swings. That
    split the definition in two: the backend scored OTE against one pair of
    anchors while the canvas drew another, and the two could drift. Now the
    drawing carries the pair, and the wire has to hold them to exactly the last
    confirmed swing high and low - same price, same time. The synthetic feed
    produces confirmed swings on both sides over this window, so a null here is
    a regression, not a quiet market.
    """
    body = draw(layers=["structure"])
    swings = body["drawing"]["swings"]
    highs = [s for s in swings if s["high"] and s["scale"] == "swing"]
    lows = [s for s in swings if not s["high"] and s["scale"] == "swing"]
    assert highs and lows, "the synthetic window has confirmed swings on both sides"

    fib = body["drawing"]["fibonacci"]
    assert fib is not None, "a chart with both anchors drawn must carry them"
    assert fib["low"] == lows[-1]["price"]
    assert fib["low_at"] == lows[-1]["time"]
    assert fib["high"] == highs[-1]["price"]
    assert fib["high_at"] == highs[-1]["time"]


# ------------------------------------------------------- the nested contract


#: Every params block on `DrawRequest`, paired with a knob name that block does
#: NOT have. Each wrong name is a plausible typo of a real one rather than
#: nonsense, because nonsense is not the case that ships: `departure_min_ATR`
#: for `departure_min_atr`, `min_gap` for `min_gap_atr`, `true_open` for
#: `true_opens`. Those are the ones a hand-copied TypeScript literal produces.
FORBIDDEN = [
    ("supply_demand", "departure_min_ATR", 3.0),
    ("imbalance", "min_gap", 0.5),
    ("structure", "swing_width", 9),
    ("session", "true_open", ["day"]),
    ("dfr", "extension", [-0.5]),
    ("gaps", "keep_gaps", 3),
    ("news", "impact", ["High"]),
    ("cisd", "min_runs", 3),
    ("pools", "max_pool", 4),
    ("liquidity", "max_level", 4),
    ("projections", "level", [0.0]),
    ("checklist", "bias_timeframe", ["1h"]),
]


@pytest.mark.parametrize(
    "block,knob,value", FORBIDDEN, ids=[f"{b}.{k}" for b, k, _ in FORBIDDEN]
)
def test_a_knob_no_params_block_has_is_a_422_and_not_a_shrug(block, knob, value):
    """A typo in a nested knob must fail the way a typo at the top level does.

    `DrawRequest` has forbidden extras since the incident written up in
    `models/api.py`: five providers were "measured" by sending a `source` field
    that model never had, pydantic dropped it, and all five answered 200 with
    identical Yahoo bars. The top level was closed that day. THE TWELVE NESTED
    BLOCKS WERE NOT, which left the same defect one level down and in the worse
    place: the top level holds eight scalar fields, while the blocks hold about
    seventy knobs whose names are hand-copied into `frontend/src/lib/types.ts`.

    So `{"supply_demand": {"departure_min_ATR": 3.0}}` used to be an HTTP 200
    over a chart drawn on the DEFAULT 2.0, with nothing anywhere saying the
    number had been ignored. A wrong reading that looks right, which is the
    failure shape this project's own notes call the worst way for an API to be
    wrong. `ParamBlock` closes it.

    Parametrised over every block rather than a representative one, because
    what is being pinned is that no block was MISSED. One open block is the
    whole hole back, and the next block added is the one that gets forgotten.
    """
    response = client.post("/api/draw", json={**BASE, block: {knob: value}})
    assert response.status_code == 422, (
        f"{block}.{knob} was accepted; that block still allows extras, so a "
        f"typo there is a silent no-op with a 200"
    )
    assert knob in response.text, "the 422 must name the field it refused"


def test_the_real_knob_beside_the_typo_still_works():
    """The gate is closed, not welded: the correct spelling has to still pass.

    Paired with the test above on purpose. A block that rejected EVERYTHING
    would satisfy that assertion perfectly while breaking the product, and this
    is the half that would catch it: same block, same request shape, the name
    the model actually has.
    """
    ok = client.post(
        "/api/draw",
        json={
            **BASE,
            "layers": ["supply_demand"],
            "supply_demand": {"departure_min_atr": 3.0},
        },
    )
    assert ok.status_code == 200, ok.text

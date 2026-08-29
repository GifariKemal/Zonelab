"""Exercise the running API from the outside.

    python -m tools.validate_api

Covers every endpoint, every provider, every interval, and the inputs a user is
most likely to get wrong. The point of most of these is not that they succeed,
it is that they FAIL LOUDLY: a provider with no key, an unknown symbol and a
rate limit must be three different messages, never one empty chart.
"""

from __future__ import annotations

import os
import sys
from collections import Counter

import httpx

#: The running API. Overridable because the shipped launcher runs uvicorn
#: WITHOUT `--reload`, so the instance on 8100 is whatever was current when
#: somebody double-clicked start.bat - and checking a change against a server
#: that predates it is the exact shape of instrument this project keeps a list
#: of: green, and measuring something that is no longer there. Point this at a
#: scratch instance to check a build before it replaces the one in use.
BASE = os.environ.get("ZONELAB_API", "http://127.0.0.1:8100").rstrip("/")
results: list[tuple[bool, str, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((passed, name, detail))


def get(path: str, **params) -> httpx.Response:
    return httpx.get(f"{BASE}{path}", params=params, timeout=45.0)


def draw(**body) -> httpx.Response:
    payload: dict = {
        "symbol": "XAUUSD",
        "interval": "15m",
        "bars": 300,
        "layers": ["supply_demand"],
        **body,
    }
    return httpx.post(f"{BASE}/api/draw", json=payload, timeout=60.0)


def main() -> int:
    # ---- basic endpoints -------------------------------------------------
    r = get("/api/health")
    check("health returns ok", r.status_code == 200 and r.json()["status"] == "ok")

    r = get("/api/config")
    config = r.json() if r.status_code == 200 else {}
    check("config returns 200", r.status_code == 200)
    check(
        "config lists providers, symbols, intervals, layers",
        all(k in config for k in ("providers", "symbols", "intervals", "layers")),
    )
    # One list, and every entry says what it is. The split into `detectors` and
    # `overlays` is gone: it made the same intent have two spellings, and a UI
    # could wire a control to one list while the engine read the other.
    check(
        "config no longer splits detectors from overlays",
        "detectors" not in config and "overlays" not in config,
        str(sorted(config)),
    )
    check(
        "every advertised layer carries a kind and its evidence",
        all(
            layer["kind"] in ("detector", "overlay", "report") and layer["evidence"]
            for layer in config.get("layers", [])
        ),
        str([layer["id"] for layer in config.get("layers", []) if not layer["evidence"]]),
    )
    check(
        "config marks keyless providers available",
        any(p["id"] == "binance" and p["available"] for p in config.get("providers", [])),
    )
    check(
        "config marks keyed providers as needing a key",
        all(
            p["needs_key"]
            for p in config.get("providers", [])
            if p["id"] in {"twelvedata", "polygon"}
        ),
    )

    r = get("/api/candles", symbol="XAUUSD", interval="1h", bars=120)
    body = r.json() if r.status_code == 200 else {}
    check("candles returns 200", r.status_code == 200, r.text[:120])
    check("candles honours the bar count", len(body.get("candles", [])) == 120)

    # ---- data integrity --------------------------------------------------
    candles = body.get("candles", [])
    if candles:
        times = [c["time"] for c in candles]
        check("candle times are strictly ascending", all(b > a for a, b in zip(times, times[1:])))
        check("candle times are unique", len(set(times)) == len(times))
        check(
            "every candle satisfies low <= open,close <= high",
            all(
                c["low"] <= min(c["open"], c["close"])
                and max(c["open"], c["close"]) <= c["high"]
                for c in candles
            ),
        )
        # The MODAL gap, not the first pair. Gold closes for an hour a day and
        # for the weekend, so a legitimate 1h series carries 7200s gaps at the
        # maintenance break and ~180000s ones across Sunday. Sampling times[1] -
        # times[0] asks whether the window happened to START on a break, which
        # it did on 2026-08-18 and the check failed with "got 7200s" on data
        # that was entirely correct: 286 of 299 gaps were 3600.
        #
        # What the check is really for is a granularity error - a feed handing
        # back 2h bars for a 1h request. Modal spacing catches that and cannot
        # be fooled by session structure. The second assertion is the other half
        # of it: every gap must be a whole multiple of the interval, so a feed
        # that silently shifts its grid still fails.
        gaps = [b - a for a, b in zip(times, times[1:])]
        modal = Counter(gaps).most_common(1)[0][0]
        check("bar spacing matches the interval", modal == 3600, f"got {modal}s")
        check(
            "every gap is a whole multiple of the interval",
            all(g % 3600 == 0 for g in gaps),
            str(sorted({g for g in gaps if g % 3600})[:4]),
        )

    # ---- every interval on the default provider --------------------------
    for interval in config.get("intervals", []):
        r = draw(interval=interval, bars=200)
        ok = r.status_code == 200 and len(r.json()["candles"]) > 0
        check(f"interval {interval} draws", ok, r.text[:100] if not ok else "")

    # ---- every provider --------------------------------------------------
    # "Draws OR explains itself", for EVERY provider and whatever `available`
    # predicted. Asserting anything stronger makes this suite a monitor for
    # somebody else's uptime: dukascopy answered HTTP 503 during one run and
    # failed a check about OUR code.
    #
    # The `available` branch that used to be here made the opposite mistake and
    # failed the same way. It demanded that an unavailable provider FAIL, so when
    # dukascopy's rate limit lifted between the probe and the request, it served
    # 200 candles and was marked a failure for working. Availability is a
    # prediction with a 120 second cache behind it; a prediction going stale is
    # not a defect in this API.
    #
    # What IS ours, and all this asserts: a refusal arrives as a 502 naming the
    # vendor, never a 500 and never a silent empty chart.
    for provider in config.get("providers", []):
        pid = provider["id"]
        # A SLOW VENDOR IS ONE FAILED CHECK, NOT A DEAD RUN. This call used to
        # let `httpx.ReadTimeout` propagate, and because results print only at
        # the end, one vendor over the 60 second timeout killed the process and
        # printed NOTHING - all 124 assertions lost, with output indistinguishable
        # from a suite that never started. Dukascopy at about 61 seconds per 200
        # bars sits right on that edge and did exactly this, twice in a row.
        try:
            r = draw(provider=pid, interval="1h", bars=200)
        except httpx.HTTPError as exc:
            check(
                f"provider {pid} draws or says why",
                False,
                f"transport error rather than an HTTP answer: {type(exc).__name__}",
            )
            continue
        body = r.text[:140]
        if r.status_code == 200:
            ok = len(r.json()["candles"]) > 0
            detail = "200 with no candles"
        else:
            # Case-insensitive, because a missing key is named by its ENV VAR:
            # "ZONELAB_TWELVEDATA_KEY is not set" names the provider perfectly
            # well and a lowercase `in` does not see it.
            ok = r.status_code == 502 and pid.lower() in body.lower()
            detail = f"expected a 502 naming {pid}, got {r.status_code}: {body}"
        check(f"provider {pid} draws or says why", ok, detail if not ok else body)

    # ---- zone invariants over real data ----------------------------------
    r = draw(bars=800, supply_demand={"show_broken": True, "max_zones_per_side": 50})
    payload = r.json()
    zones = payload["drawing"]["zones"]
    check("a real fetch produces zones", len(zones) > 0, f"{len(zones)}")

    first, last = payload["candles"][0]["time"], payload["candles"][-1]["time"]
    check("every zone sits inside the returned bars",
          all(first <= z["time_from"] <= z["time_to"] <= last for z in zones))
    check("every zone has positive height", all(z["top"] > z["bottom"] for z in zones))
    check(
        "proximal and distal are the zone's own edges",
        all(
            {z["proximal"], z["distal"]} == {z["top"], z["bottom"]}
            and (z["proximal"] == z["top"]) == (z["side"] == "demand")
            for z in zones
        ),
    )
    check("formation_score is a fraction", all(0 <= z["formation_score"] <= 1 for z in zones))
    check(
        "factors sum to formation_score",
        all(abs(sum(z["factors"].values()) - z["formation_score"]) < 2e-3 for z in zones),
    )
    check(
        "the retired factors are gone",
        all(set(z["factors"]) == {"tightness", "compactness", "volume"} for z in zones),
    )
    check(
        "every drawn zone cleared the departure gate",
        all(z["departure_atr"] >= 2.0 for z in zones),
    )
    check("zone ids are unique", len({z["id"] for z in zones}) == len(zones))
    check(
        "anatomy is ordered leg-in, base, leg-out",
        all(
            z["anatomy"]["leg_in_to"] < z["anatomy"]["base_from"]
            <= z["anatomy"]["base_to"] < z["anatomy"]["leg_out_from"]
            <= z["anatomy"]["leg_out_to"]
            for z in zones
        ),
    )
    # The formation must read as one contiguous sequence. Measured against the
    # FULL consolidation: the gap to `base_from` is deliberate, since the box is
    # clipped to the bars the move left from, but a gap to `base_run_from` would
    # mean the leg-in is describing a different part of the chart.
    check(
        "the leg-in sits immediately before the consolidation",
        all(
            z["anatomy"]["base_run_from"] == z["anatomy"]["leg_in_to"] + 1
            for z in zones
        ),
        str([
            z["anatomy"]["base_run_from"] - z["anatomy"]["leg_in_to"] - 1 for z in zones
        ][:5]),
    )
    check(
        "the clipped base is a tail of the full consolidation",
        all(
            z["anatomy"]["base_run_from"] <= z["anatomy"]["base_from"] for z in zones
        ),
    )
    check(
        "no drawn zone exceeds the drift gate",
        all(z["base_drift"] <= 0.6 + 1e-9 for z in zones),
        f"max {max(z['base_drift'] for z in zones):.3f}",
    )
    check(
        "relaxing the drift gate admits staircases the default rejects",
        max(
            z["base_drift"]
            for z in draw(bars=800, supply_demand={"max_base_drift": 1.0, "show_broken": True,
                                                   "max_zones_per_side": 50}).json()["drawing"]["zones"]
        )
        > 0.6,
    )
    stats = payload["meta"]["supply_demand"]
    check("stats account for every candidate",
          stats["candidates"] >= stats["zones"], str(stats))

    # The distal is the line the stop sits beyond, so it must be the base's own
    # extreme in BOTH proximal variants. Checked against the returned candles,
    # not against the zone's own numbers.
    for basis in ("wick", "body"):
        payload_b = draw(bars=800, supply_demand={
            "proximal_basis": basis, "show_broken": True, "max_zones_per_side": 50
        }).json()
        bars = payload_b["candles"]
        off = 0
        for z in payload_b["drawing"]["zones"]:
            base = bars[z["anatomy"]["base_from"] : z["anatomy"]["base_to"] + 1]
            want = (
                min(b["low"] for b in base)
                if z["side"] == "demand"
                else max(b["high"] for b in base)
            )
            if abs(z["distal"] - want) > 1e-9:
                off += 1
        check(f"distal is the base extreme with proximal_basis={basis}", off == 0, f"{off} off")

    check(
        "the conservative variant never widens the zone",
        min(z["top"] - z["bottom"] for z in draw(bars=800, supply_demand={"proximal_basis": "body"})
            .json()["drawing"]["zones"])
        <= max(z["top"] - z["bottom"] for z in zones),
    )

    # Higher-timeframe projection.
    htf = draw(bars=1000, interval="15m", htf="4h").json()
    projected = [z for z in htf["drawing"]["zones"] if z["timeframe"] == "4h"]
    check("htf zones are produced", len(projected) > 0, str(htf["meta"].get("htf")))
    check("every htf zone is stamped with its own timeframe",
          all(z["timeframe"] == "4h" for z in projected))
    check(
        "htf zones sit on the higher timeframe's own grid",
        all(z["time_from"] % 14400 == 0 for z in projected),
        "a zone off the 4h boundary means the resample anchored to the window",
    )
    check(
        "htf zones stay inside the chart window",
        all(
            htf["candles"][0]["time"] <= z["time_from"] <= z["time_to"] <= htf["candles"][-1]["time"]
            for z in projected
        ),
    )
    check("an htf equal to the interval is ignored",
          all(z["timeframe"] == "15m" for z in draw(interval="15m", htf="15m").json()["drawing"]["zones"]))
    check("an htf below the interval is ignored",
          all(z["timeframe"] == "1h" for z in draw(interval="1h", htf="15m").json()["drawing"]["zones"]))

    # The session offset must actually move the higher-timeframe grid. A broker
    # whose day does not start at UTC midnight otherwise gets zones one candle
    # away from the ones in its own terminal.
    shifted = draw(bars=1000, interval="15m", htf="4h", session_offset_hours=1).json()
    shifted_zones = [z for z in shifted["drawing"]["zones"] if z["timeframe"] == "4h"]
    check("a session offset shifts the htf grid", len(shifted_zones) > 0)
    check(
        "shifted htf zones sit on the offset grid, not the UTC one",
        all((z["time_from"] - 3600) % 14400 == 0 for z in shifted_zones),
        str([z["time_from"] % 14400 for z in shifted_zones][:4]),
    )

    # Higher-timeframe nesting. Both cohorts must exist, or the flag is
    # measuring nothing: an "always true" label cannot distinguish anything.
    # The "both cohorts appear" check USED to live here and has moved to
    # tests/test_confluence.py, where the answer is arithmetic. It is a question
    # about a MECHANISM, and asked here it was really asking about today's
    # market: it failed on 2026-08-17 with "0 nested, 7 alone" because a 1000-bar
    # 15m window happened to hold a single 4h zone. Moving it to the synthetic
    # provider did not fix that either - its time anchor is `now`, so the
    # higher-timeframe buckets slide with the wall clock and the same request
    # gave 3 nested at one hour and 0 at the next.
    #
    # This comment used to add "synthetic prices are seeded", and that was wrong
    # at the time: the seed was `abs(hash(symbol))`, which CPython randomises per
    # process, so the prices moved too. Finding one cause and stopping is what
    # let the second one live here in writing for as long as it did. The seed is
    # `crc32` now and the sentence is finally true.
    #
    # What stays here is what a contract test can actually promise: the field is
    # present, and whatever it names is a HIGHER timeframe. Those hold on every
    # chart, in every session.
    nested = [z for z in htf["drawing"]["zones"]
              if z["timeframe"] == "15m" and z["nested_in"]]
    check("every zone carries the nesting field",
          all("nested_in" in z for z in htf["drawing"]["zones"]))
    check("nesting names only higher timeframes",
          all(tf == "4h" for z in nested for tf in z["nested_in"]))
    check("nothing is nested when no higher timeframe is requested",
          all(not z["nested_in"] for z in draw(bars=400).json()["drawing"]["zones"]))

    # The four remaining odds enhancers. All reported, none scored.
    rich = draw(bars=1000, supply_demand={"show_broken": True, "max_zones_per_side": 50}).json()
    rz = rich["drawing"]["zones"]
    check("curve is a fraction of the range", all(0 <= z["curve"] <= 1 for z in rz))
    check(
        "curve_favourable matches the side it is computed for",
        all(
            z["curve_favourable"] == (z["curve"] <= 1 / 3 + 1e-9)
            if z["side"] == "demand"
            else z["curve_favourable"] == (z["curve"] >= 2 / 3 - 1e-9)
            for z in rz
        ),
    )
    check(
        "the profit zone points at an opposing zone, never a same-side one",
        all(
            z["profit_zone_rr"] is None or z["profit_zone_rr"] > 0
            for z in rz
        ),
    )
    check(
        "arrival exists exactly when the zone has been touched",
        all((z["arrival_atr"] is not None) == (z["first_test_time"] is not None) for z in rz),
        f"{sum(1 for z in rz if z['arrival_atr'] is not None)} of {len(rz)}",
    )
    check(
        "an untouched zone reports no arrival",
        all(z["arrival_atr"] is None for z in rz if z["state"] == "fresh"),
    )

    # ---- parameter response ----------------------------------------------
    loose = len(draw(bars=800, supply_demand={"departure_min_atr": 0.0})
                .json()["drawing"]["zones"])
    tight = len(draw(bars=800, supply_demand={"departure_min_atr": 6.0})
                .json()["drawing"]["zones"])
    check("the departure gate actually gates", loose > tight, f"{loose} vs {tight}")

    hidden = len(draw(bars=800, supply_demand={"show_broken": False}).json()["drawing"]["zones"])
    shown = len(draw(bars=800, supply_demand={"show_broken": True}).json()["drawing"]["zones"])
    check("show_broken reveals more zones", shown >= hidden, f"{hidden} vs {shown}")

    capped = draw(bars=800, supply_demand={"max_zones_per_side": 1}).json()["drawing"]["zones"]
    check("the per-side cap is enforced",
          all(sum(1 for z in capped if z["side"] == s) <= 1 for s in ("demand", "supply")))

    # Zero has to mean OFF and not "keep none". The cap selects the NEWEST zones,
    # so any measurement taken through it silently becomes a measurement of the
    # tail of the history - which is exactly what happened to this project's own
    # calibration until 2026-08-13.
    uncapped = draw(bars=800, supply_demand={"max_zones_per_side": 0}).json()["drawing"]["zones"]
    check("a cap of zero means no cap at all", len(uncapped) > len(capped),
          f"{len(uncapped)} vs {len(capped)}")

    # ---- refinement ------------------------------------------------------
    plain = draw(bars=1500, interval="15m", htf="4h").json()["drawing"]["zones"]
    fine = draw(bars=1500, interval="15m", htf="4h", refine=True).json()
    refined = [z for z in fine["drawing"]["zones"] if z.get("refinement")]
    check("refinement is off unless asked for",
          all(z.get("refinement") is None for z in plain))
    check("refining an htf chart refines something", len(refined) > 0,
          str(fine["meta"].get("htf")))
    check("a refined box is strictly smaller than the one it replaced",
          all(0 < z["refinement"]["shrank_to"] < 1 for z in refined))
    check(
        "a refined box never reaches outside the original",
        all(
            z["top"] <= z["refinement"]["from_top"] + 1e-6
            and z["bottom"] >= z["refinement"]["from_bottom"] - 1e-6
            for z in refined
        ),
    )
    check("a refined box still has the distal on the far side",
          all((z["proximal"] > z["distal"]) == (z["side"] == "demand") for z in refined))
    check("refinement names the timeframe it cut from",
          all(z["refinement"]["timeframe"] == "15m" for z in refined))
    check("refinement is only offered to higher-timeframe zones",
          all(z["timeframe"] == "4h" for z in refined))

    # ---- the road ahead --------------------------------------------------
    # Asserted as invariants and an accounting identity, NOT as "the filter
    # removed something". Whether any zone on the live chart happens to have a
    # short road right now is a property of today's market: the first version of
    # this block passed at 16 vs 15 and failed the next day at 17 vs 17, with no
    # code between the two runs. A contract test that reads the market is a
    # coin flip wearing a green tick.
    base = draw(bars=1500).json()["drawing"]["zones"]
    check("nothing is stamped crowded while the check is off",
          all(z["crowded_at"] is None for z in base))

    counts = []
    for rr in (0.0, 1.0, 2.0, 5.0, 10.0):
        body = draw(bars=1500, supply_demand={"min_profit_zone_rr": rr}).json()
        kept = body["drawing"]["zones"]
        counts.append(len(kept))
        check(
            f"road {rr}: every survivor has the road it was asked for",
            all(z["profit_zone_rr"] is None or z["profit_zone_rr"] >= rr for z in kept),
        )
        # The identity holds whatever the market did, including when the answer
        # is zero, which is exactly the case the old check could not express.
        check(
            f"road {rr}: the trace accounts for every removal",
            body["meta"]["supply_demand"].get("rejected_crowded", 0)
            == len(base) - len(kept),
            f"{body['meta']['supply_demand'].get('rejected_crowded', 0)}"
            f" vs {len(base) - len(kept)}",
        )
        check(
            f"road {rr}: no zone is crowded before it existed or after it died",
            all(
                z["crowded_at"] is None
                or z["time_from"] <= z["crowded_at"] <= z["time_to"]
                for z in kept
            ),
        )

    check("asking for more road never returns more zones",
          counts == sorted(counts, reverse=True), str(counts))
    # Only claimed when there is something to remove, which the data itself says.
    walled = any(z["profit_zone_rr"] is not None for z in base)
    check("a road nothing can satisfy does remove the walled zones",
          not walled or counts[-1] < counts[0], f"{counts} walled={walled}")

    # ---- the other two detectors -----------------------------------------
    # Compared against the REGISTRY rather than a literal set. The literal said
    # three while the registry grew to five, so this assertion failed for being
    # stale rather than for finding anything - and a check that cries wolf when a
    # detector is added is a check people learn to ignore. What it is really for
    # is the wiring invariant: everything the engine can run must be advertised,
    # or the UI cannot offer it. The catalogue is one list now, so the detectors
    # are the entries that SAY they are detectors - which also means a layer
    # filed under the wrong kind fails here rather than silently losing its
    # per-side cap in the UI.
    from app.detect import DETECTORS

    layers = get("/api/config").json()["layers"]
    advertised = {layer["id"] for layer in layers if layer["kind"] == "detector"}
    check("every registered detector is advertised",
          advertised == set(DETECTORS), f"advertised {sorted(advertised)}")

    for name, code in (("fvg", "FVG"), ("order_block", "OB")):
        body = draw(bars=1500, layers=[name]).json()
        shapes = body["drawing"]["zones"]
        check(f"{name} draws something", len(shapes) > 0, str(body["meta"].get(name)))
        check(f"{name} stamps its own kind",
              all(z["kind"] == code for z in shapes))
        check(f"{name} boxes have positive height",
              all(z["top"] > z["bottom"] for z in shapes))
        check(
            f"{name} puts the proximal on the side price meets first",
            all((z["proximal"] > z["distal"]) == (z["side"] == "demand") for z in shapes),
        )
        check(f"{name} sits inside the returned bars",
              all(body["candles"][0]["time"] <= z["time_from"] <= body["candles"][-1]["time"]
                  for z in shapes))
        check(f"{name} reports its own filter trace", "candidates" in body["meta"][name])
        # These two carry no score, on purpose: the supply/demand composite had
        # to be retracted, and starting without one is the lesson applied.
        check(f"{name} claims no score", all(z["formation_score"] == 0 for z in shapes))

    both = draw(bars=1500, layers=["supply_demand", "fvg"]).json()["drawing"]["zones"]
    kinds = {z["kind"] for z in both}
    check("detectors compose rather than replace one another",
          "FVG" in kinds and kinds - {"FVG"}, str(sorted(kinds)))

    # A fair value gap has no opposing zone and therefore no road, so the
    # supply/demand road filter must not reach across and eat it.
    guarded = draw(bars=1500, layers=["supply_demand", "fvg"],
                   supply_demand={"min_profit_zone_rr": 3.0}).json()["drawing"]["zones"]
    check("the road filter does not touch another detector's drawings",
          sum(1 for z in guarded if z["kind"] == "FVG")
          == sum(1 for z in both if z["kind"] == "FVG"))

    # ---- bad input must be rejected, not absorbed -------------------------
    check("unknown interval is a 502 with a reason",
          draw(interval="7m").status_code == 502)
    # Was `fvg`, which stopped being unknown the day the detector shipped and
    # turned this into a test of nothing. A name nothing will ever be called.
    check("unknown layer is a 422",
          draw(layers=["not_a_layer"]).status_code == 422)
    # An overlay is validated by the SAME list now, so a typo in one has to fail
    # the same way a typo in a detector does. Before the merge an overlay name
    # was never checked at all - it was a boolean inside its own params block -
    # so this half of the contract is new and is the half worth pinning.
    check("an unknown layer is rejected even beside valid ones",
          draw(layers=["gaps", "not_an_overlay"]).status_code == 422)
    check("unknown provider is a 502 with a reason",
          draw(provider="nope").status_code == 502)
    # BOTH OF THESE USED TO BE A BARE 500, and 120 assertions passed over them.
    # `/api/account` resolved the provider outside its own try, and
    # `/api/agent/config` caught only ValueError while `float()` raises TypeError
    # for a list. The second one sits on the endpoint holding model credentials.
    check("an unknown provider on /api/account is a 502, not a 500",
          get("/api/account", provider="nope").status_code == 502)
    check("a known feed without an account is still a 501",
          get("/api/account", provider="yahoo").status_code == 501)
    check("a non-scalar temperature is a 422, not a 500",
          httpx.post(f"{BASE}/api/agent/config", json={"temperature": [1, 2]},
                     timeout=45.0).status_code == 422)
    check("a non-numeric temperature is a 422",
          httpx.post(f"{BASE}/api/agent/config", json={"temperature": "abc"},
                     timeout=45.0).status_code == 422)
    check("bars below the floor is a 422",
          draw(bars=1).status_code == 422)
    check("bars above the ceiling is a 422",
          draw(bars=99999).status_code == 422)
    # ONE KNOB, ONE CONTRACT, ACROSS EVERY DOOR. `bars` used to mean two
    # different things depending on the route: `/api/draw` bounded it and
    # answered 422, while `/api/candles` and `/api/triad` handed it to
    # `get_candles`, which clamps, so `bars=-5` was a 200 over 50 bars. A caller
    # sizing a window got a series a different length from the one it asked for,
    # with no field saying so. Compared as EQUALITY so that loosening either
    # side fails here rather than re-opening the gap quietly.
    for count in (-5, 0, 49, 99999):
        statuses = {
            "draw": draw(bars=count).status_code,
            "candles": get("/api/candles", bars=count).status_code,
            "triad": get("/api/triad", bars=count).status_code,
        }
        check(f"bars={count} is a 422 on every route that takes it",
              set(statuses.values()) == {422}, str(statuses))
    # THE NESTED BLOCKS REFUSE A NAME THEY DO NOT HAVE. `DrawRequest` has
    # forbidden extras since the `source` incident; its twelve params blocks did
    # not, so a typo one level down was a silent no-op with a 200 and a chart
    # drawn on the default. About seventy knob names are hand-copied into the
    # TypeScript, which is where such a typo comes from.
    check("a misspelled nested knob is a 422, not a silent default",
          draw(supply_demand={"departure_min_ATR": 3.0}).status_code == 422)
    check("a misspelled overlay knob is a 422 too",
          draw(layers=["session"], session={"true_open": ["day"]}).status_code == 422)
    check("the correctly spelled knob beside it still passes",
          draw(supply_demand={"departure_min_atr": 3.0}).status_code == 200)
    # SSRF AND CREDENTIAL EXFILTRATION. This endpoint sends `Bearer <api_key>`
    # to whatever host the body names and this API has no authentication of its
    # own, so a loopback or link-local target is how a key leaves the machine
    # and how cloud metadata gets read. Nothing is stored on a refusal, which is
    # why probing it here cannot disturb a configured endpoint.
    for host in ("http://127.0.0.1:11434/v1", "http://169.254.169.254/v1",
                 "http://10.0.0.5/v1"):
        r = httpx.post(f"{BASE}/api/agent/config", json={"base_url": host},
                       timeout=45.0)
        check(f"a non-public agent endpoint ({host}) is refused",
              r.status_code == 422, r.text[:160])
    check("out-of-range parameter is a 422",
          draw(supply_demand={"mitigation_pct": 5.0}).status_code == 422)
    check("negative parameter is a 422",
          draw(supply_demand={"atr_period": -3}).status_code == 422)
    check("nonsense proximal_basis is a 422",
          draw(supply_demand={"proximal_basis": "banana"}).status_code == 422)
    check("unknown symbol on a keyless provider is a spoken 502",
          draw(symbol="NOTREAL", provider="yahoo").status_code == 502)

    # ---- the triad says which feed answered ------------------------------
    # It silently rewrites binance, yahoo and an absent provider to mt5, because
    # those feeds carry none of the triad partners. That substitution is correct
    # and used to be invisible: a caller asking for binance got MT5 prices and
    # nothing in the body said so, while every other route that resolves a
    # provider has always reported the one it used.
    r = get("/api/triad", triad="monetary", bars=300, provider="binance")
    body = r.json() if r.status_code == 200 else {}
    check("triad answers 200", r.status_code == 200, r.text[:160])
    check("triad reports the provider it actually used",
          body.get("provider") == "mt5", str(body.get("provider")))
    check("triad still reports its base and partners",
          body.get("base") == "XAUUSD" and len(body.get("partners") or []) == 2,
          str(body.get("partners")))
    r = get("/api/triad", triad="banana")
    check("an unknown triad is a 422 listing the real ones",
          r.status_code == 422 and "monetary" in r.text, r.text[:120])

    # ---- determinism -----------------------------------------------------
    a = draw(bars=400).json()["drawing"]["zones"]
    b = draw(bars=400).json()["drawing"]["zones"]
    check("identical requests give identical zones",
          [z["id"] for z in a] == [z["id"] for z in b])

    # ---- report ----------------------------------------------------------
    failed = [r for r in results if not r[0]]
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f" :: {detail}" if detail else ""))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""Exercise the running API from the outside.

    python -m tools.validate_api

Covers every endpoint, every provider, every interval, and the inputs a user is
most likely to get wrong. The point of most of these is not that they succeed,
it is that they FAIL LOUDLY: a provider with no key, an unknown symbol and a
rate limit must be three different messages, never one empty chart.
"""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8100"
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
        "detectors": ["supply_demand"],
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
        "config lists providers, symbols, intervals, detectors",
        all(k in config for k in ("providers", "symbols", "intervals", "detectors")),
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
        step = times[1] - times[0]
        check("bar spacing matches the interval", step == 3600, f"got {step}s")

    # ---- every interval on the default provider --------------------------
    for interval in config.get("intervals", []):
        r = draw(interval=interval, bars=200)
        ok = r.status_code == 200 and len(r.json()["candles"]) > 0
        check(f"interval {interval} draws", ok, r.text[:100] if not ok else "")

    # ---- every provider --------------------------------------------------
    for provider in config.get("providers", []):
        pid = provider["id"]
        r = draw(provider=pid, interval="1h", bars=200)
        if provider["available"] and not provider["needs_key"]:
            ok = r.status_code == 200 and len(r.json()["candles"]) > 0
            check(f"provider {pid} returns candles", ok, r.text[:140] if not ok else "")
        else:
            # Unavailable must be a spoken 502, never a silent empty chart.
            spoken = r.status_code == 502 and len(r.json().get("detail", "")) > 10
            check(f"provider {pid} explains why it cannot run", spoken, r.text[:140])

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
    nested = [z for z in htf["drawing"]["zones"] if z["timeframe"] == "15m" and z["nested_in"]]
    alone = [z for z in htf["drawing"]["zones"] if z["timeframe"] == "15m" and not z["nested_in"]]
    check("nesting produces both cohorts", len(nested) > 0 and len(alone) > 0,
          f"{len(nested)} nested, {len(alone)} alone")
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
    check("all three detectors are advertised",
          set(get("/api/config").json()["detectors"])
          == {"supply_demand", "fvg", "order_block"})

    for name, code in (("fvg", "FVG"), ("order_block", "OB")):
        body = draw(bars=1500, detectors=[name]).json()
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

    both = draw(bars=1500, detectors=["supply_demand", "fvg"]).json()["drawing"]["zones"]
    kinds = {z["kind"] for z in both}
    check("detectors compose rather than replace one another",
          "FVG" in kinds and kinds - {"FVG"}, str(sorted(kinds)))

    # A fair value gap has no opposing zone and therefore no road, so the
    # supply/demand road filter must not reach across and eat it.
    guarded = draw(bars=1500, detectors=["supply_demand", "fvg"],
                   supply_demand={"min_profit_zone_rr": 3.0}).json()["drawing"]["zones"]
    check("the road filter does not touch another detector's drawings",
          sum(1 for z in guarded if z["kind"] == "FVG")
          == sum(1 for z in both if z["kind"] == "FVG"))

    # ---- bad input must be rejected, not absorbed -------------------------
    check("unknown interval is a 502 with a reason",
          draw(interval="7m").status_code == 502)
    # Was `fvg`, which stopped being unknown the day the detector shipped and
    # turned this into a test of nothing. A name no detector will ever have.
    check("unknown detector is a 422",
          draw(detectors=["not_a_detector"]).status_code == 422)
    check("unknown provider is a 502 with a reason",
          draw(provider="nope").status_code == 502)
    check("bars below the floor is a 422",
          draw(bars=1).status_code == 422)
    check("bars above the ceiling is a 422",
          draw(bars=99999).status_code == 422)
    check("out-of-range parameter is a 422",
          draw(supply_demand={"mitigation_pct": 5.0}).status_code == 422)
    check("negative parameter is a 422",
          draw(supply_demand={"atr_period": -3}).status_code == 422)
    check("nonsense proximal_basis is a 422",
          draw(supply_demand={"proximal_basis": "banana"}).status_code == 422)
    check("unknown symbol on a keyless provider is a spoken 502",
          draw(symbol="NOTREAL", provider="yahoo").status_code == 502)

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

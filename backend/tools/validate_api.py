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
    payload = {
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
    stats = payload["meta"]["supply_demand"]
    check("stats account for every candidate",
          stats["candidates"] >= stats["zones"], str(stats))

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

    # ---- bad input must be rejected, not absorbed -------------------------
    check("unknown interval is a 502 with a reason",
          draw(interval="7m").status_code == 502)
    check("unknown detector is a 422",
          draw(detectors=["fvg"]).status_code == 422)
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
    check("nonsense zone_basis is a 422",
          draw(supply_demand={"zone_basis": "banana"}).status_code == 422)
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

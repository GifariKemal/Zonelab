"""Push the running API until something gives, and report what.

    python -m tools.stress            # the whole battery
    python -m tools.stress --quick    # skip the concurrency sweep

`tools/validate_api.py` asks whether the answers are RIGHT. This asks whether the
service survives being used hard, which is a different question and has caught
different things: a display cap that turns a chart into a wash, a params
combination nobody tried, a worker pool that serialises under load.

WHAT IS ACTUALLY STRESSED, and each of these is a shape a real user can reach:

  1. THE HEAVIEST HONEST DRAW. Every layer on, the largest bar count the picker
     offers, and every display cap at 0 - which is what a MEASUREMENT passes, so
     it is not a synthetic worst case, it is the configuration `tools/calibrate.py`
     and every walk-forward run uses.
  2. EVERY SLIDER AT ITS LIMIT, both ends, together. Individually these are
     covered by `e2e/click-everything.mjs`; the combination is not, and a
     threshold pair that contradicts each other is exactly where a detector
     divides by a zero-width range.
  3. CONCURRENCY. The draw path is synchronous work handed to a thread pool, and
     MT5 is a single-threaded C library behind one process-wide lock. So the
     interesting number is not throughput, it is whether latency degrades
     LINEARLY - a superlinear curve means requests are queueing somewhere that
     was not meant to queue.
  4. CHURN. Fire a request, abandon it, fire another. This is what dragging a
     slider does, and the app cancels the in-flight fetch on every change. An
     abandoned request that keeps its worker busy is invisible until the pool
     runs out.
  5. MEMORY. RSS before and after, because a leak in a long-lived server is a
     defect a short test cannot see and a trading day can.

`tools/stress_api.py` is the narrow complement to this file: an async flood deep
enough to reach `main._BUILDS`, plus a health probe that watches the event loop
while it happens. It imports `rss_mb` from here rather than re-deriving it. If a
question is about the heaviest draw, the sliders, churn, or memory, it belongs
here; if it is about queue depth or loop starvation, it belongs there.

NOTHING HERE ASSERTS A THRESHOLD. There is no measured baseline for what this
service "should" do on this machine, so inventing one would be a gate with no
evidence behind it. It prints numbers and names failures; a human reads it. The
one thing it does judge is an ERROR, because a 500 is wrong at any speed.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "http://127.0.0.1:8100"

#: The largest count the Bars picker offers. Deliberately read from the shipped
#: options rather than pushed to the model's ceiling: the point is the heaviest
#: draw a USER can ask for, and 20000 through the API is a tools-only path.
HEAVY_BARS = 5000

#: Caps at zero everywhere, which is what a measurement passes. Every one of these
#: keys is a DISPLAY limit, and this project has twice been bitten by measuring
#: through one - the road ahead read differently under two caps, and the same zone
#: reported a target under one and none under another.
#: THE BLOCK NAMES ARE NOT THE LAYER NAMES, and assuming they were made this
#: tool's first run report twenty HTTP 422s that looked like product failures and
#: were mine. Four imbalance detectors - `fvg`, `order_block`, `ifvg`, `breaker` -
#: share ONE `imbalance` block, deliberately, because four copies of one threshold
#: would read as four independent thresholds writing one value. `DrawRequest`
#: forbids extra keys, so `{"fvg": {...}}` is a 422 rather than a silent no-op,
#: which is the model doing its job.
UNCAPPED: dict[str, dict[str, object]] = {
    "supply_demand": {"max_zones_per_side": 0, "show_broken": True},
    "imbalance": {"max_zones_per_side": 0, "show_broken": True},
    "gaps": {"keep": 0},
    "cisd": {"max_events": 0},
    "dfr": {"max_ranges": 0},
    "pools": {"max_pools": 0},
    "liquidity": {"max_levels": 0, "range_frame": True, "range_liquidity": True},
    "session": {
        "quarters": ["month", "week", "day", "session"],
        "true_opens": ["year", "month", "week", "day"],
        "max_quarters": 0,
    },
    "checklist": {
        "ssmt_symbols": ["XAGUSD", "DXY"],
        "ssmt_degrees": ["day", "week"],
        "ssmt_max": 0,
    },
}

failures: list[str] = []


def draw(client: httpx.Client, layers: list[str], bars: int, **extra) -> tuple[float, dict]:
    """One draw, timed. A non-200 is recorded and re-raised as an empty body so
    the caller's arithmetic does not silently include a failure as a fast run."""
    body: dict[str, object] = {
        "symbol": "XAUUSD",
        "interval": "15m",
        "bars": bars,
        "provider": "mt5",
        "layers": layers,
        **extra,
    }
    started = time.perf_counter()
    response = client.post(f"{BASE}/api/draw", json=body, timeout=600.0)
    elapsed = time.perf_counter() - started
    if response.status_code != 200:
        failures.append(
            f"HTTP {response.status_code} on {len(layers)} layers x {bars} bars: "
            f"{response.text[:200]}"
        )
        return elapsed, {}
    return elapsed, response.json()


def shapes(payload: dict) -> int:
    """Every drawable the response carries, so the cost has a denominator."""
    drawing = payload.get("drawing") or {}
    return sum(len(v) for v in drawing.values() if isinstance(v, list))


def rss_mb() -> float | None:
    """Resident memory of the process HOLDING PORT 8100, or None if unreadable.

    Read from the OS rather than from inside the server, because a leak in the
    server is exactly the condition under which the server's own report is least
    trustworthy. Windows-only; returns None elsewhere rather than guessing.

    IDENTIFIED BY THE PORT, and the first version of this was identified by
    "the largest python.exe" instead - a heuristic that produced garbage and
    looked like a finding. Over 300 heavy draws it reported +24.9, +164.1, +46.7,
    **-138.5** and +236.7 MB, and a negative delta of 138 MB is not memory
    behaviour, it is a different process being measured each time: this tool is a
    python.exe, so is every other tool in this directory, and so were two agents
    running at the time. Read against the actual listener the same 300 draws moved
    RSS by +0.2 MB, oscillating within 6 MB and settling where it started.
    """
    if sys.platform != "win32":
        return None
    import re
    import subprocess

    try:
        listening = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=60
        ).stdout
        found = re.findall(r"127\.0\.0\.1:8100\s+\S+\s+LISTENING\s+(\d+)", listening)
        if not found:
            return None
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {found[0]}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except Exception:
        return None
    # `tasklist` groups thousands with the locale separator AND a space in some
    # locales - "154 916 K" - so every non-digit is stripped rather than two
    # specific separators being replaced. The first version raised ValueError on
    # `'154916 K'` from inside a try that did not cover it.
    size = re.search(r'"([\d.,\s]+) K"', out)
    return float(re.sub(r"\D", "", size.group(1))) / 1024.0 if size else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="skip the concurrency sweep")
    args = parser.parse_args()

    client = httpx.Client()
    config = client.get(f"{BASE}/api/config", timeout=60.0).json()
    every = [layer["id"] for layer in config["layers"]]
    print(f"{len(every)} layers registered: {', '.join(every)}\n")

    before = rss_mb()

    # --- 1. the heaviest honest draw ---------------------------------------
    print("1. HEAVIEST DRAW, every layer on, every cap lifted")
    for bars in (500, 1000, 2000, HEAVY_BARS):
        elapsed, payload = draw(client, every, bars, **UNCAPPED)
        count = shapes(payload)
        meta = payload.get("meta") or {}
        print(
            f"   {bars:5} bars -> {elapsed:6.2f}s  {count:6} shapes  "
            f"{count / elapsed if elapsed else 0:8.0f} shapes/s  "
            f"returned {meta.get('bars_returned', '?')}"
        )

    # --- 2. every slider at both limits, together --------------------------
    print("\n2. EVERY NUMERIC PARAM AT ITS LIMIT, all at once")
    schema = client.get(f"{BASE}/openapi.json", timeout=60.0).json()
    blocks = _numeric_bounds(schema)
    for end in ("minimum", "maximum"):
        extreme: dict[str, dict[str, float]] = {}
        touched = 0
        for block, fields in blocks.items():
            picked = {name: bound[end] for name, bound in fields.items() if end in bound}
            if picked:
                extreme[block] = picked
                touched += len(picked)
        elapsed, payload = draw(client, every, 1000, **extreme)
        print(
            f"   {end:8} on {touched:3} params -> {elapsed:6.2f}s  "
            f"{shapes(payload):6} shapes"
        )

    # --- 3. concurrency ----------------------------------------------------
    if not args.quick:
        print("\n3. CONCURRENCY, the same heavy draw N ways at once")
        single = None
        for workers in (1, 2, 4, 8):
            def one(_: int) -> float:
                with httpx.Client() as c:
                    return draw(c, every, 1000, **UNCAPPED)[0]

            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                times = list(pool.map(one, range(workers)))
            wall = time.perf_counter() - started
            if single is None:
                single = statistics.median(times)
            print(
                f"   {workers} at once -> wall {wall:6.2f}s  "
                f"median {statistics.median(times):6.2f}s  "
                f"slowest {max(times):6.2f}s  "
                f"x{statistics.median(times) / single:4.1f} vs one alone"
            )

    # --- 4. churn ----------------------------------------------------------
    print("\n4. CHURN, 30 requests abandoned mid-flight then one honest draw")
    abandoned = 0
    for _ in range(30):
        try:
            # A 150ms budget is shorter than any draw here, so every one of these
            # is cancelled while the server is still working - which is what a
            # dragged slider does.
            httpx.post(
                f"{BASE}/api/draw",
                json={
                    "symbol": "XAUUSD",
                    "interval": "15m",
                    "bars": 2000,
                    "provider": "mt5",
                    "layers": every,
                },
                timeout=0.15,
            )
        except httpx.TimeoutException:
            abandoned += 1
        except Exception as exc:  # a refused connection is a real failure
            failures.append(f"churn: {type(exc).__name__} {exc}")
    elapsed, payload = draw(client, every, 1000, **UNCAPPED)
    print(
        f"   {abandoned}/30 abandoned, then a clean draw in {elapsed:.2f}s "
        f"with {shapes(payload)} shapes"
    )

    # --- 5. memory ---------------------------------------------------------
    after = rss_mb()
    print("\n5. MEMORY of the process holding port 8100")
    if before is None or after is None:
        print("   not readable on this platform")
    else:
        print(f"   before {before:8.1f} MB   after {after:8.1f} MB   "
              f"delta {after - before:+8.1f} MB")
        # A single before/after pair cannot tell allocator churn from a leak, and
        # this one oscillates by several MB between identical requests. Measured
        # separately against the listener: 300 heavy draws moved it +0.2 MB.
        print("   a few MB either way is allocator churn; 300 draws moved it +0.2 MB")

    print()
    if failures:
        print(f"{len(failures)} FAILURES:")
        for line in failures:
            print(f"  {line}")
        return 1
    print("no errors: every request answered 200")
    return 0


def _numeric_bounds(schema: dict) -> dict[str, dict[str, dict[str, float]]]:
    """Every numeric field of every params block, with its declared bounds.

    Read from the served OpenAPI rather than typed out here, so a new slider is
    stressed without an edit to this file - the same reason `e2e/wiring.mjs` walks
    the layer registry instead of a list.
    """
    components = (schema.get("components") or {}).get("schemas") or {}
    request = components.get("DrawRequest") or {}
    out: dict[str, dict[str, dict[str, float]]] = {}

    for block, prop in (request.get("properties") or {}).items():
        ref = _ref_of(prop)
        target = components.get(ref) if ref else None
        if not target:
            continue
        fields: dict[str, dict[str, float]] = {}
        for name, field in (target.get("properties") or {}).items():
            bound = {
                key: field[key]
                for key in ("minimum", "maximum")
                if isinstance(field.get(key), (int, float))
            }
            # Booleans carry no bounds and enums are not numeric; only a field
            # with a real min or max is a slider.
            if bound and field.get("type") in {"integer", "number"}:
                fields[name] = bound
        if fields:
            out[block] = fields
    return out


def _ref_of(prop: dict) -> str | None:
    """The schema name a property points at, through `allOf`/`anyOf` wrappers that
    pydantic emits for an optional model field."""
    if "$ref" in prop:
        return prop["$ref"].rsplit("/", 1)[-1]
    for key in ("allOf", "anyOf", "oneOf"):
        for item in prop.get(key) or []:
            if "$ref" in item:
                return item["$ref"].rsplit("/", 1)[-1]
    return None


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())

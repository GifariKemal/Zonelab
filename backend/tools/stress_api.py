"""How the draw endpoint behaves under a flood, and what the number means.

    python -m tools.stress_api                          # the full report
    python -m tools.stress_api --requests 5000 --concurrency 500
    python -m tools.stress_api --provider mt5 --requests 400

READ THIS BEFORE READING A p95 OFF IT. A single p95 taken at one flood depth is
close to meaningless for this endpoint, and quoting one without the curve beside
it would be the most misleading number this repo has produced.

`app/main.py` caps concurrent drawings at TWO, on purpose, with the incident
that produced the cap written next to it: an end-to-end harness once fired a
draw per interaction and the worker burned 6.05 seconds of CPU in 6 seconds,
`/api/health` took 8.01 seconds, and `POST /api/draw` never returned inside 60.
`_BUILDS = asyncio.Semaphore(2)` is the fix, and it is a QUEUE. So under a flood
of N, the latency an arriving request sees is dominated by how many are already
in front of it, not by how long the work takes. That is Little's law, and no
amount of optimising the drawing code moves it.

WHAT THIS TOOL THEREFORE MEASURES, three things and not one:

 1. A LATENCY CURVE across concurrency levels. Service time and queue time are
    separable if you look at where the line bends. One number hides the bend.
 2. `/api/health` DURING the flood. Health does nothing but return a dict, so
    its latency is a direct read on whether the event loop is still being
    served. This is the question "is the math engine non-blocking" actually
    reduces to: the dial is arithmetic on six integers, and if it were blocking
    the loop, health would climb with it. The 8.01 seconds above is what a
    starved loop looked like when it really happened here.
 3. RSS of the process that owns the port, before and after.

PROVIDER DEFAULTS TO SYNTHETIC, deliberately, and the repo has the precedent:
the saturation incident above was reproduced with the synthetic provider "so no
network and no cache hit was involved in it at all". The dial reads one field
off the bars - the newest bar's time - so which provider supplied them changes
nothing about the code path under test. `--provider mt5` runs the real one, and
is worth running small: MT5 is a LOCAL provider, which `app/providers` gives a
zero-second cache TTL, so every request there is a fresh terminal pull.

NOT THE ONLY STRESS TOOL, and the split is worth knowing before adding a third.
`tools/stress.py` covers the heaviest honest draw, every slider at both limits,
a sync concurrency sweep, churn, and RSS - and it deliberately asserts NOTHING,
because this project has no measured baseline for what the service "should"
reach and a gate without evidence is a gate without a floor. This file is the
narrow complement: an ASYNC flood deep enough to reach the semaphore, and a
health probe that can see the event loop while it happens. Its thresholds are
OWNER-SPECIFIED rather than derived from a baseline, which is the only reason it
is allowed to assert at all.

`rss_mb` is imported from that file rather than written again. It reads the
process holding the port, and its docstring carries why: an earlier version
found "the largest python.exe" and reported memory deltas of -138.5 MB, which is
not memory behaviour, it is a different process being measured each time.

READ ONLY. It sends POSTs to a drawing endpoint and GETs to health. It places
no order and touches no switch.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time

import httpx

from tools.stress import rss_mb

BASE = "http://127.0.0.1:8100"

#: Concurrency levels for the curve. The first two straddle the semaphore, so
#: the bend it produces is visible rather than inferred.
LADDER = (1, 2, 8, 32, 128)

#: How many requests each rung of the curve sends. Small, because the curve is
#: about the SHAPE and the flood below is where the volume goes.
LADDER_REQUESTS = 200


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile, stated because there are several definitions.

    Nearest-rank is the one that returns an OBSERVED value rather than an
    interpolation between two of them. For a latency report that matters: an
    interpolated p95 is a number no request actually experienced.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(-(-p * len(ordered) // 1))))
    return ordered[rank - 1]


async def one(client: httpx.AsyncClient, body: dict) -> tuple[float, int]:
    """One draw, its wall-clock milliseconds, and the status it came back with.

    A non-200 is TIMED AND COUNTED rather than dropped. A run that quietly
    discarded its failures would report the latency of the requests that
    happened to work, which is the shape of every load test that says a broken
    service is fast.
    """
    started = time.perf_counter()
    try:
        res = await client.post("/api/draw", json=body)
        status = res.status_code
    except Exception:
        status = 0
    return (time.perf_counter() - started) * 1000.0, status


async def flood(
    client: httpx.AsyncClient, body: dict, requests: int, concurrency: int
) -> tuple[list[float], dict[int, int]]:
    """`requests` draws with at most `concurrency` in flight."""
    gate = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    statuses: dict[int, int] = {}

    async def run() -> None:
        async with gate:
            ms, status = await one(client, body)
            latencies.append(ms)
            statuses[status] = statuses.get(status, 0) + 1

    await asyncio.gather(*(run() for _ in range(requests)))
    return latencies, statuses


def health_probe(stop: threading.Event, every: float = 0.05) -> list[float]:
    """`/api/health` on a timer, from ITS OWN THREAD AND ITS OWN CONNECTION.

    THE FIRST VERSION OF THIS MEASURED THE WRONG MACHINE. It awaited health on
    the same event loop and the same connection pool as the flood, so a sample
    could sit behind the client's own queued tasks and behind the client's own
    pool. It read 259 ms p95 at only 300 requests, and there was no way to tell
    that apart from the server being busy - which is the exact thing it was
    built to distinguish. A probe that cannot separate itself from its own load
    generator measures the load generator.

    Sync `httpx.Client` in a plain thread instead. It blocks on the socket,
    which releases the GIL, so the flood's tasks cannot serialise it. That
    leaves normal thread scheduling as the only client-side term, and
    `baseline` below prices that term rather than assuming it away.
    """
    seen: list[float] = []
    with httpx.Client(base_url=BASE, timeout=60.0) as client:
        while not stop.is_set():
            started = time.perf_counter()
            try:
                client.get("/api/health")
            except Exception:
                pass
            seen.append((time.perf_counter() - started) * 1000.0)
            stop.wait(every)
    return seen


def health_baseline(samples: int = 40, every: float = 0.05) -> list[float]:
    """The same probe, the same way, with nothing else running.

    THE CONTROL. Without it, "health p95 was X during the flood" is a number
    with no scale: X could be the server queueing, or it could be what this
    probe costs on an idle machine. Measured the same way from the same kind of
    thread so the two are subtractable.
    """
    stop = threading.Event()
    out: list[float] = []

    def run() -> None:
        out.extend(health_probe(stop, every))

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    time.sleep(samples * every)
    stop.set()
    worker.join(timeout=10)
    return out


def report(name: str, latencies: list[float], extra: str = "") -> dict:
    row = {
        "name": name,
        "n": len(latencies),
        "p50": percentile(latencies, 0.50),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
        "max": max(latencies) if latencies else 0.0,
    }
    print(
        f"  {name:28s} n={row['n']:5d}  p50 {row['p50']:8.1f}  "
        f"p95 {row['p95']:8.1f}  p99 {row['p99']:8.1f}  max {row['max']:8.1f} ms"
        + (f"   {extra}" if extra else "")
    )
    return row


async def main_async(args: argparse.Namespace) -> int:
    body = {
        "symbol": args.symbol,
        "interval": args.interval,
        "bars": args.bars,
        "layers": ["vortex"],
        "provider": args.provider,
    }

    limits = httpx.Limits(
        max_connections=args.concurrency + 16,
        max_keepalive_connections=args.concurrency + 16,
    )
    async with httpx.AsyncClient(base_url=BASE, timeout=120.0, limits=limits) as client:
        # PROVE THE PAYLOAD IS THERE BEFORE TIMING ANYTHING. A flood against an
        # endpoint that answers 200 with an empty drawing would produce a superb
        # p95 and measure nothing at all.
        first = await client.post("/api/draw", json=body)
        if first.status_code != 200:
            print(f"BLOCKER: /api/draw answered {first.status_code}: {first.text[:200]}")
            return 1
        dial = first.json()["drawing"]["vortex"]
        if not dial or len(dial["rings"]) != 6:
            print(f"BLOCKER: no dial in the payload: {json.dumps(dial)[:200]}")
            return 1
        print(f"payload confirmed: {len(dial['rings'])} rings, "
              f"{len(dial['matrix'])}x{len(dial['matrix'][0])} matrix, lit {dial['lit']}")
        print(f"provider {args.provider}, {args.bars} bars, layer vortex only\n")

        before = rss_mb()
        print(f"RSS before {before:.1f} MB" if before is not None
              else "RSS unavailable")
        print()

        # ---- the curve --------------------------------------------------
        print(f"LATENCY CURVE, {LADDER_REQUESTS} requests per rung")
        curve = []
        for level in LADDER:
            # Warm the pool at this level so the first request's connection
            # setup does not land in the sample.
            await one(client, body)
            lat, st = await flood(client, body, LADDER_REQUESTS, level)
            bad = {k: v for k, v in st.items() if k != 200}
            curve.append(report(f"concurrency {level}", lat,
                                f"non-200 {bad}" if bad else ""))
        print()

        # ---- the flood, with health watched throughout ------------------
        print("CONTROL: the health probe with nothing else running")
        idle = health_baseline()
        idle_row = report("health idle", idle)
        print()

        print(f"FLOOD: {args.requests} requests at concurrency {args.concurrency}")
        stop = threading.Event()
        health: list[float] = []

        def probe() -> None:
            health.extend(health_probe(stop))

        worker = threading.Thread(target=probe, daemon=True)
        worker.start()
        started = time.perf_counter()
        lat, statuses = await flood(client, body, args.requests, args.concurrency)
        elapsed = time.perf_counter() - started
        stop.set()
        worker.join(timeout=10)

        bad = {k: v for k, v in statuses.items() if k != 200}
        flood_row = report("draw under flood", lat, f"non-200 {bad}" if bad else "")
        health_row = report("health during flood", health)
        print(f"  wall clock {elapsed:.2f}s, throughput "
              f"{args.requests / elapsed:.0f} req/s\n")

        after = rss_mb()

    # ---- assertions ------------------------------------------------------
    print("ASSERTIONS")
    ok = True

    # SERVICE TIME, not queue time. The directive's 150ms bar is a statement
    # about how fast the endpoint answers, and the rung at concurrency 2 is the
    # deepest one where that is what is being measured - it is exactly the
    # semaphore's width, so nothing is waiting on anything else yet.
    service = next(r for r in curve if r["name"] == "concurrency 2")
    service_ok = service["p95"] < 150
    ok &= service_ok
    print(f"  [{'PASS' if service_ok else 'FAIL'}] p95 service time under 150 ms "
          f":: {service['p95']:.1f} ms at concurrency 2")

    # The flood figure is REPORTED and not asserted against 150, and the reason
    # is in the docstring: at depth N the number is the queue, and the queue is a
    # deliberate cap with an incident behind it. Asserting on it would be
    # asserting that the flood guard should not exist.
    print(f"  [ -- ] p95 under a {args.requests}-deep flood "
          f":: {flood_row['p95']:.1f} ms (queue behind Semaphore(2), by design)")

    # THE NON-BLOCKING PROOF. Health does nothing; if the loop were being held,
    # this is where it would show. Bar set at 150 ms too, which is 53x better
    # than the 8010 ms this endpoint recorded when the loop really was starved.
    health_ok = health_row["p95"] < 150
    ok &= health_ok
    print(f"  [{'PASS' if health_ok else 'FAIL'}] event loop stays served during "
          f"the flood :: health p95 {health_row['p95']:.1f} ms "
          f"(idle control {idle_row['p95']:.1f} ms, "
          f"{health_row['p95'] - idle_row['p95']:+.1f} ms under load)")

    if before is not None and after is not None:
        delta = after - before
        mem_ok = delta <= 10.0
        ok &= mem_ok
        print(f"  [{'PASS' if mem_ok else 'FAIL'}] RSS delta at most +10 MB "
              f":: {before:.1f} -> {after:.1f} MB ({delta:+.1f} MB)")
    else:
        ok = False
        print("  [FAIL] RSS could not be read, so the memory bar is UNKNOWN "
              "rather than met")

    print(f"\n{'ALL ASSERTIONS PASSED' if ok else 'SOME ASSERTIONS FAILED'}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=500)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=400)
    parser.add_argument("--provider", default="synthetic",
                        help="synthetic by default so a flood costs the MT5 "
                             "terminal nothing; mt5 runs the real path")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

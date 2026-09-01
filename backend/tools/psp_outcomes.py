"""Does a PSP after an SSMT separate the outcome, and does the SSMT add anything?

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.psp_outcomes \
        --bars 50000 --interval 1h --degree day > ../docs/psp_outcomes.json

WHY THIS EXISTS. `app/psp.py` has shipped since before 27 August 2026 with
"NOT WIRED" in its own header, and nothing has ever connected a PSP to an
outcome. The owner's doctrine puts it on Route B: SSMT then tCISD then PSP then
TOB. This run asks the two questions that have to be answered before it can be
wired to anything, and the second one is the one that matters.

EVERYTHING BELOW THIS LINE WAS FIXED BEFORE A NUMBER WAS COMPUTED.
The level definition was chosen by the owner on 1 September 2026 from three
readings of his own phrase, before this file existed.

## 1. The object, stated so it cannot drift

A PSP here is a sweep-and-rejection of ONE level, and the level is the OPEN of
the bar three back from the bar being read, rolling:

    level(i) = candles[i - 3].open

    sell PSP at i:  open[i] <= level  and  high[i] >  level  and  close[i] < level
    buy  PSP at i:  open[i] >= level  and  low[i]  <  level  and  close[i] > level

The open guard is not decoration. `app/psp.py` records that without it the sell
branch also fires on a bar that opened above the level and closed under it,
which is a plain break down and has purged nothing. The predicate is not
reimplemented here: `app.psp.detect` is called once per bar with that single
level and `lookback=1`, so the shipped function is the one under test. A copy
of it would test the copy.

The window is THREE BARS after the SSMT becomes knowable, which is
`app/psp.py`'s own default and the owner's "3 candle last".

## 2. Two hypotheses, and the second is the control the first needs

H1: the rate at which a PSP's CLAIMED direction is reached first inside a
symmetric ATR bracket differs, after an SSMT, from that rate on non-PSP bars of
the same instrument.

H2: that rate after an SSMT differs from the rate of a PSP with NO SSMT in front
of it.

H1 alone cannot answer the question that was asked. A PSP is a sweep and
rejection, and a sweep and rejection may well separate outcomes on its own; if
it does, H1 passes and says nothing at all about the SSMT. H2 is the arm that
isolates what the sequential SMT contributes, and it is the reason this run
exists rather than a fourth copy of "does a candle pattern predict".

Claimed direction: a buy PSP swept below and closed back above, so it claims UP.
A sell PSP claims DOWN.

ONLY EVENTS WHERE `took == chart`, the same convention as
`tools/ssmt_outcomes.py`: when the partner is the instrument that took the
extreme, the reading is about the partner's price.

## 3. The three arms

  A  psp_after_ssmt   a PSP inside the 3 bars after an SSMT knowable bar
  B  psp_alone        a PSP on a bar with no SSMT window in front of it
  C  no_psp           bars with no PSP at all, the signal-free control

H1 is A against C. H2 is A against B.

## 4. Independence, by construction

A 40-bar bracket read at every bar overlaps 40 ways. Every arm is thinned the
same way: an observation is kept only when its bar index is at least HORIZON
past the last kept one IN THE SAME ARM AND ON THE SAME SIDE. Symmetric thinning
is the only version that does not put a thumb on a scale.

## 5. Fixed parameters, no search

  degree      day
  interval    1h
  bars        50000
  level       open of the bar three back, rolling
  window      3 bars after the SSMT knowable bar
  bracket     symmetric, k * ATR14 at the PSP bar, k in (0.5, 1.0, 2.0)
  horizon     40 bars
  ties        a bar reaching both sides is DROPPED, and counted
  atr         Wilder 14, trailing only, read at the PSP bar
  pairs       XAUUSD|XAGUSD, XAUUSD|DXY, BTCUSD|ETHUSD, USDJPY|EURUSD

XAUUSD|DXY is kept even though `app/ssmt.py` names it a category error at 59,5
per cent fire rate. It is reported, not trusted, and a run that quietly dropped
the inconvenient pair would be a run that chose its own sample.

## 6. Pass conditions, all three

  1. n >= 30 in the event arm of the cell.
  2. |z| past the two-sided critical value at alpha 0,05 / K, Bonferroni, where
     K is every cell eligible to be judged in the WHOLE run, both hypotheses
     counted, computed and printed BEFORE one result line.
  3. The sign of the delta is the same in both time halves, cut by TIME at the
     median event timestamp, not by member count.

Passing all three earns a walk-forward. It does not earn shipping, it does not
earn a place in the checklist, and it does not earn `--require`.

## 7. Reported, never judged, and never filtered on

The triad crack (`app.psp.in_same_candle` against the partner) is stamped on
every event and its rate is reported. It is not split on, because splitting on
it would double K and this run has no power to spare. Same treatment
`app/ssmt.py` gives `candle_valid` and `session`.

## 8. What voids this run

  - An arm under 30 thinned observations makes its cell NOT MEASURABLE, not
    zero.
  - The `no_psp` control under 100 thinned observations makes its pair
    unmeasurable.
  - If the anti-lookahead self-check fails the whole run is discarded. A number
    computed from a future bar is not a weaker number, it is a wrong one.

## 9. What is not promised

Four pairs, one degree, one timeframe, one broker's history, one level
definition out of three the owner could have named. No spread, no commission,
no swap: this is a bracket outcome, not tradeable expectancy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from statistics import NormalDist

import numpy as np

from app.aligned import load_aligned
from app.indicators import wilder_atr
from app.psp import PSPEvent, at_bar, in_same_candle
from app.ssmt import ssmt

PAIRS = [("XAUUSD", "XAGUSD"), ("XAUUSD", "DXY"),
         ("BTCUSD", "ETHUSD"), ("USDJPY", "EURUSD")]  # fmt: skip
WIDTHS = (0.5, 1.0, 2.0)
HORIZON = 40
WINDOW = 3        # bars after the SSMT knowable bar, app/psp.py's own default
MIN_EVENTS = 30
MIN_CONTROL = 100
FOLDS = 6
ALPHA = 0.05
_NORM = NormalDist()


def _resolve(high, low, close, at: int, unit: float, width: float) -> bool | None:
    """True when DOWN is reached first from bar `at`, False for UP, None for
    neither-inside-horizon or both-in-one-bar. Starts at `at + 1`: the bar the
    reading became knowable on is not a bar it could have been traded on."""
    reach = width * unit
    down, up = close[at] - reach, close[at] + reach
    for i in range(at + 1, min(len(close), at + 1 + HORIZON)):
        hit_down, hit_up = low[i] <= down, high[i] >= up
        if hit_down and hit_up:
            return None
        if hit_down or hit_up:
            return bool(hit_down)
    return None


def _z_and_ci(hits_a, n_a, hits_b, n_b):
    """Two-proportion z (pooled variance) and the 95% CI on the difference."""
    if n_a == 0 or n_b == 0:
        return None, None, None, None
    pa, pb = hits_a / n_a, hits_b / n_b
    pooled = (hits_a + hits_b) / (n_a + n_b)
    se = (pooled * (1 - pooled) * (1 / n_a + 1 / n_b)) ** 0.5
    z = (pa - pb) / se if se > 0 else 0.0
    se_d = (pa * (1 - pa) / n_a + pb * (1 - pb) / n_b) ** 0.5
    return pa - pb, z, (pa - pb) - 1.96 * se_d, (pa - pb) + 1.96 * se_d


def _selftest() -> None:
    """The gate proved non-empty: each assert fails if its check is removed."""
    close = np.full(60, 100.0)
    high = np.full(60, 100.5)
    low = np.full(60, 99.5)
    low[5] = 90.0
    assert _resolve(high, low, close, 0, 1.0, 1.0) is True
    high[3] = 110.0
    assert _resolve(high, low, close, 0, 1.0, 1.0) is False
    # ANTI-LOOKAHEAD both ways: a hit ON the decision bar does not count, and a
    # hit past the horizon does not count.
    on_bar = np.full(60, 99.5)
    on_bar[0] = 90.0
    assert _resolve(np.full(60, 100.5), on_bar, close, 0, 1.0, 1.0) is None
    far = np.full(60, 99.5)
    far[HORIZON + 5] = 90.0
    assert _resolve(np.full(60, 100.5), far, close, 0, 1.0, 1.0) is None
    near = np.full(60, 99.5)
    near[HORIZON - 1] = 90.0
    assert _resolve(np.full(60, 100.5), near, close, 0, 1.0, 1.0) is True
    both_low, both_high = np.full(60, 99.5), np.full(60, 100.5)
    both_low[2], both_high[2] = 90.0, 110.0
    assert _resolve(both_high, both_low, close, 0, 1.0, 1.0) is None

    # THE PSP PREDICATE ITSELF, on hand-built bars where the answer is known.
    from app.models import Candle

    def bar(o, h, low_, c):
        return Candle(time=0, open=o, high=h, low=low_, close=c, volume=0.0)

    flat = [bar(100, 100.2, 99.8, 100) for _ in range(4)]
    # Sell: opens under the level (100), wicks above it, closes back under.
    sell = flat[:3] + [bar(99.9, 101.0, 99.5, 99.7)]
    got = at_bar(sell, 3)
    assert got is not None and got.direction == "sell", got
    # Buy: opens over the level, wicks under it, closes back over.
    buy = flat[:3] + [bar(100.1, 100.4, 99.0, 100.3)]
    got = at_bar(buy, 3)
    assert got is not None and got.direction == "buy", got
    # A plain break down has purged nothing: opens ABOVE the level and closes
    # under it, never having arrived from the near side. This is the guard
    # app/psp.py added after a fixture written to be a non-event was reported.
    breakdown = flat[:3] + [bar(100.5, 100.6, 99.0, 99.2)]
    assert at_bar(breakdown, 3) is None
    # And a bar that only touches the level without closing back is not one.
    touch = flat[:3] + [bar(99.9, 100.4, 99.7, 100.2)]
    assert at_bar(touch, 3) is None
    print("selftest OK", file=__import__("sys").stderr)


async def _load(chart, partner, interval, bars, provider):
    return await load_aligned([chart, partner], interval, bars, provider)


def measure(chart, partner, series, degree):
    """Three arms for one pair, thinned, at every width."""
    events, _ = ssmt(series, degree)
    rows = series[chart]
    partner_rows = series[partner]
    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    close = np.array([c.close for c in rows], dtype=np.float64)
    times = [c.time for c in rows]
    atr = wilder_atr(high, low, close, 14)
    index_of = {c.time: i for i, c in enumerate(rows)}

    # Bars that sit inside the 3-bar window after an SSMT the CHART took.
    after_ssmt: set[int] = set()
    ssmt_kept = 0
    for event in events:
        if event.took != chart:
            continue
        at = index_of.get(event.knowable_at)
        if at is None:
            continue
        ssmt_kept += 1
        for k in range(1, WINDOW + 1):
            after_ssmt.add(at + k)

    # Every PSP in the series, once, then split by whether an SSMT preceded it.
    found: list[tuple[int, str, bool | None]] = []
    for i in range(20, len(close) - 1):
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        got = at_bar(rows, i)
        if got is None:
            continue
        crack = in_same_candle(
            PSPEvent(at=i, level=got.level, direction=got.direction,
                     ssmt_at=i, bars_after_ssmt=0),
            rows, [partner_rows],
        )
        found.append((i, got.direction, crack))

    psp_bars = {i for i, _, _ in found}
    arms: dict[str, dict[str, list[int]]] = {
        "psp_after_ssmt": {"buy": [], "sell": []},
        "psp_alone": {"buy": [], "sell": []},
    }
    last: dict[tuple[str, str], int] = {}
    cracks = {"psp_after_ssmt": [0, 0], "psp_alone": [0, 0]}
    for i, direction, crack in found:
        arm = "psp_after_ssmt" if i in after_ssmt else "psp_alone"
        key = (arm, direction)
        if i - last.get(key, -(10 ** 9)) < HORIZON:
            continue
        last[key] = i
        arms[arm][direction].append(i)
        cracks[arm][0] += 1 if crack else 0
        cracks[arm][1] += 1

    # The signal-free control: bars with no PSP on them at all, thinned the same
    # distance apart.
    control: list[int] = []
    step = 0
    for i in range(20, len(close) - 1):
        if not np.isfinite(atr[i]) or atr[i] <= 0 or i in psp_bars:
            continue
        if step % HORIZON == 0:
            control.append(i)
        step += 1

    out: dict = {}
    for width in WIDTHS:
        ctrl = [(times[i], _resolve(high, low, close, i, float(atr[i]), width))
                for i in control]  # fmt: skip
        ctrl = [(t, v) for t, v in ctrl if v is not None]
        for direction in ("buy", "sell"):
            # A buy PSP claims UP, and `_resolve` returns True for DOWN.
            def score(v: bool) -> bool:
                return (not v) if direction == "buy" else v

            graded = {}
            for arm in arms:
                obs = []
                for i in arms[arm][direction]:
                    v = _resolve(high, low, close, i, float(atr[i]), width)
                    if v is None:
                        continue
                    obs.append((times[i], score(v)))
                graded[arm] = obs
            cobs = [(t, score(v)) for t, v in ctrl]
            out[(width, direction)] = (graded, cobs)
    counts = {
        "ssmt_events_chart_took": ssmt_kept,
        "psp_found_raw": len(found),
        "psp_bars_after_ssmt": len([1 for i, _, _ in found if i in after_ssmt]),
        "control_bars_thinned": len(control),
        "triad_crack_rate": {
            arm: (round(c[0] / c[1], 4) if c[1] else None) for arm, c in cracks.items()
        },
    }
    return out, counts


def _halves(obs, other):
    """Delta in each time half, cut by the median event timestamp."""
    if len(obs) < 4:
        return None
    cut = sorted(t for t, _ in obs)[len(obs) // 2]
    deltas = []
    for lo, hi in ((None, cut), (cut, None)):
        e = [v for t, v in obs if (lo is None or t >= lo) and (hi is None or t < hi)]
        c = [v for t, v in other if (lo is None or t >= lo) and (hi is None or t < hi)]
        if not e or not c:
            return None
        deltas.append((sum(e) / len(e)) - (sum(c) / len(c)))
    return deltas


def _walkforward(obs, other):
    """Six equal time spans. Every fold reported, including the ones that fail."""
    if not obs:
        return []
    lo = min(t for t, _ in obs + other)
    hi = max(t for t, _ in obs + other)
    span = max(1, (hi - lo) // FOLDS)
    folds = []
    for k in range(FOLDS):
        a = lo + k * span
        b = hi + 1 if k == FOLDS - 1 else a + span
        e = [v for t, v in obs if a <= t < b]
        c = [v for t, v in other if a <= t < b]
        folds.append({
            "fold": k + 1, "n_event": len(e), "n_other": len(c),
            "event_rate": round(sum(e) / len(e), 4) if e else None,
            "other_rate": round(sum(c) / len(c), 4) if c else None,
            "delta": (round(sum(e) / len(e) - sum(c) / len(c), 4)
                      if e and c else None),
        })  # fmt: skip
    return folds


def judge(obs, other, critical) -> dict:
    """One hypothesis in one cell, against all three pass conditions."""
    hits_a, n_a = sum(1 for _, v in obs if v), len(obs)
    hits_b, n_b = sum(1 for _, v in other if v), len(other)
    delta, z, lo, hi = _z_and_ci(hits_a, n_a, hits_b, n_b)
    halves = _halves(obs, other)
    row = {
        "n_event": n_a, "n_other": n_b,
        "event_rate": round(hits_a / n_a, 4) if n_a else None,
        "other_rate": round(hits_b / n_b, 4) if n_b else None,
        "delta": None if delta is None else round(delta, 4),
        "z": None if z is None else round(z, 3),
        "ci95": None if lo is None else [round(lo, 4), round(hi, 4)],
        "halves": None if halves is None else [round(d, 4) for d in halves],
    }
    if n_a < MIN_EVENTS or n_b < MIN_CONTROL or z is None:
        row["verdict"] = "NOT MEASURABLE"
        return row
    signs_agree = halves is not None and (halves[0] > 0) == (halves[1] > 0)
    passed = abs(z) >= critical and signs_agree
    row["verdict"] = "MEMISAHKAN" if passed else "null"
    row["walk_forward"] = _walkforward(obs, other) if passed else []
    return row


def main() -> None:
    p = argparse.ArgumentParser(description="PSP after SSMT against outcome")
    p.add_argument("--bars", type=int, default=50_000)
    p.add_argument("--interval", type=str, default="1h")
    p.add_argument("--degree", type=str, default="day")
    p.add_argument("--provider", type=str, default="mt5")
    p.add_argument("--selfcheck", action="store_true")
    args = p.parse_args()

    _selftest()
    if args.selfcheck:
        return

    async def run():
        # ONE event loop for every pair: the mt5 provider holds an asyncio lock
        # bound to the loop that created it.
        loaded = {}
        for chart, partner in PAIRS:
            try:
                loaded[(chart, partner)] = await _load(
                    chart, partner, args.interval, args.bars, args.provider
                )
            except Exception as exc:  # noqa: BLE001
                loaded[(chart, partner)] = exc
        return loaded

    loaded = asyncio.run(run())

    measured = {}
    for chart, partner in PAIRS:
        got = loaded[(chart, partner)]
        if isinstance(got, Exception):
            measured[(chart, partner)] = got
            continue
        series, _ = got
        measured[(chart, partner)] = measure(chart, partner, series, args.degree)

    # K BEFORE ONE RESULT LINE: every cell eligible to be judged, both
    # hypotheses counted.
    k = 0
    for value in measured.values():
        if isinstance(value, Exception):
            continue
        cells, _ = value
        for graded, cobs in cells.values():
            if len(cobs) < MIN_CONTROL:
                continue
            if len(graded["psp_after_ssmt"]) >= MIN_EVENTS:
                k += 1  # H1, against no_psp
                if len(graded["psp_alone"]) >= MIN_EVENTS:
                    k += 1  # H2, against psp_alone
    critical = _NORM.inv_cdf(1 - ALPHA / max(k, 1) / 2) if k else float("inf")

    out: dict = {
        "preregistered": "tools/psp_outcomes.py, 2026-09-01",
        "question": "apakah PSP sesudah SSMT memisahkan outcome, dan apakah SSMT-nya menambah",
        "level": "open of the bar 3 back, rolling",
        "window_bars": WINDOW,
        "degree": args.degree, "interval": args.interval, "bars": args.bars,
        "horizon": HORIZON, "widths": list(WIDTHS),
        "cells_judged": k, "alpha": ALPHA, "critical_z": round(critical, 4),
        "pairs": {},
    }
    for chart, partner in PAIRS:
        key = f"{chart}|{partner}"
        value = measured[(chart, partner)]
        if isinstance(value, Exception):
            out["pairs"][key] = {"skipped": str(value)}
            continue
        cells, counts = value
        block: dict = {**counts, "cells": {}}
        for (width, direction), (graded, cobs) in sorted(cells.items()):
            block["cells"][f"{width}atr|{direction}"] = {
                "H1_vs_no_psp": judge(graded["psp_after_ssmt"], cobs, critical),
                "H2_vs_psp_alone": judge(
                    graded["psp_after_ssmt"], graded["psp_alone"], critical),
            }
        out["pairs"][key] = block

    json.dump(out, __import__("sys").stdout, indent=2, default=float)
    print()


if __name__ == "__main__":
    main()

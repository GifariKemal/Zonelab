"""Does an SSMT divergence separate the OUTCOME at all? Pre-registered.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.ssmt_outcomes \
        --bars 50000 --interval 1h --degree day > ../docs/ssmt_outcomes.json

WHY THIS EXISTS. `app/layers.py` says of the `ssmt` layer: "Nothing connects a
divergence to an outcome, by anyone." Two things are already measured and are
NOT re-measured here. The RATE is the pair you choose (14.9% against silver,
59.5% against DXY at day degree). `docs/smt-volatility.json` measured whether
volatility conditions the reading and found it does not. Both took the
divergence population's own down-first rate against the 50% a symmetric bracket
resolves to under a random walk. Neither compared it to what the SAME
instrument does on a bar with no divergence on it, and neither ran a
significance test, a Bonferroni correction, or a walk-forward.

`docs/PRAREGISTRASI-KORELASI.md` section 7 is already filled in (29 Aug 2026,
null): `partner_corr_band` does not separate gate expectancy. That study
conditioned an existing trade population on correlation. This one asks the
prior question the layer's own sentence asks - whether the divergence separates
anything - and it needs its own control.

EVERYTHING BELOW THIS LINE WAS FIXED BEFORE A NUMBER WAS COMPUTED.

## 1. Hypothesis, one, directional

H1: on the bar an SSMT becomes knowable, the rate at which the divergence's
CLAIMED direction is reached first inside a symmetric ATR bracket is different
from that same rate on non-divergence bars of the same instrument.

Claimed direction, stated because the claim does not state itself: `side="high"`
means the chart took the previous quarter's HIGH while the partner failed, which
is read bearish, so the claimed direction is DOWN. `side="low"` is the mirror and
claims UP. Both sides are measured; `tools/smt_volatility.py` measured the
bearish half only, and half a claim tested is a claim untested.

ONLY EVENTS WHERE `took == chart`. When the partner is the instrument that took
the extreme, the reading is about the partner's price and drawing it on the
chart is a different claim. Same convention as `tools/smt_volatility.py`.

## 2. The control, which is the whole point of this run

Non-divergence bars of the SAME instrument, same bracket, same ATR unit, same
horizon. 50% is what a symmetric bracket resolves to under a random walk, and a
real series is not a random walk: it drifts, and its bracket resolves off 50 for
reasons that have nothing to do with SSMT. So the comparison is against the
instrument's own measured base rate, not against 0.50.

`docs/CALIBRATION.md`'s baseline arm is the precedent: the box beat no-box 8/8
only once a signal-free control existed to beat.

## 3. Independence, handled by construction rather than by assumption

A 40-bar bracket read at every bar overlaps 40 ways, and an n of 35,000 built
that way inflates any z it is fed. So both arms are thinned the same way:

  - Events: an event is kept only when its bar index is at least HORIZON beyond
    the last kept event OF THE SAME SIDE.
  - Control: every HORIZON-th eligible non-event bar, from the first eligible
    index forward.

Symmetric thinning is the only version that does not put a thumb on a scale.

## 4. Fixed parameters, no search

  degree      day
  interval    1h
  bars        50000
  bracket     symmetric, k * ATR14 at the knowable bar, k in (0.5, 1.0, 2.0)
  horizon     40 bars
  ties        a bar that reaches both sides is DROPPED, and counted
  atr         Wilder 14, trailing only, read at the knowable bar
  pairs       XAUUSD|XAGUSD, XAUUSD|DXY, BTCUSD|ETHUSD, USDJPY|EURUSD

Three widths because an effect at one distance and not the others is a bracket
artefact. Four pairs on three different chart instruments, so a null cannot be
one instrument's null wearing a general name.

## 5. Pass conditions, all three, same as the three pre-registrations before this

  1. n >= 30 events in the cell.
  2. |z| for the two-proportion difference exceeds the two-sided critical value
     at alpha 0.05 / K, Bonferroni, where K is every cell eligible to be judged
     in the WHOLE run. K is computed and printed BEFORE one result line.
  3. The sign of (event rate - control rate) is the same in both time halves,
     cut by TIME at the median event timestamp, not by member count.

Passing all three earns a walk-forward. It does not earn shipping and does not
earn `--require`.

## 6. Walk-forward, reported for every cell including the failures

Six folds by time, equal spans, not equal counts. Every fold is printed with its
n and its delta, including folds that flip sign and folds too small to read. A
walk-forward that reports only the folds that agreed is a walk-forward that
measured nothing.

## 7. What voids this run

  - A pair whose events number under 30 at every width is reported as NOT
    MEASURABLE, not as zero.
  - A control arm under 100 thinned observations makes its pair unmeasurable.
  - If the anti-lookahead self-check fails, the whole run is discarded. A number
    computed from a future bar is not a weaker number, it is a wrong one.

## 8. What is not promised

Four pairs, one degree, one timeframe, one broker's history. A null here is not
a null everywhere, a lesson this repo has already paid for twice. And this
measures the bracket outcome, not tradeable expectancy: no spread, no
commission, no swap.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from statistics import NormalDist

import numpy as np

from app.aligned import load_aligned
from app.correlation import correlations
from app.indicators import wilder_atr
from app.ssmt import ssmt

PAIRS = [("XAUUSD", "XAGUSD"), ("XAUUSD", "DXY"),
         ("BTCUSD", "ETHUSD"), ("USDJPY", "EURUSD")]  # fmt: skip
WIDTHS = (0.5, 1.0, 2.0)
HORIZON = 40
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
    """The gate proved non-empty: each assert below fails if its check is removed."""
    close = np.full(60, 100.0)
    high = np.full(60, 100.5)
    low = np.full(60, 99.5)
    low[5] = 90.0  # down side reached at bar 5
    assert _resolve(high, low, close, 0, 1.0, 1.0) is True
    high[3] = 110.0  # up side reached earlier, at bar 3
    assert _resolve(high, low, close, 0, 1.0, 1.0) is False
    # ANTI-LOOKAHEAD, both directions. A hit ON the decision bar must not count,
    # and a hit past the horizon must not count either.
    on_bar = np.full(60, 99.5)
    on_bar[0] = 90.0
    assert _resolve(np.full(60, 100.5), on_bar, close, 0, 1.0, 1.0) is None
    far = np.full(60, 99.5)
    far[HORIZON + 5] = 90.0
    assert _resolve(np.full(60, 100.5), far, close, 0, 1.0, 1.0) is None
    # And the injection is not blunt: the same bar inside the horizon DOES move it.
    near = np.full(60, 99.5)
    near[HORIZON - 1] = 90.0
    assert _resolve(np.full(60, 100.5), near, close, 0, 1.0, 1.0) is True
    # A bar reaching both sides is dropped, not scored.
    both_low = np.full(60, 99.5)
    both_high = np.full(60, 100.5)
    both_low[2], both_high[2] = 90.0, 110.0
    assert _resolve(both_high, both_low, close, 0, 1.0, 1.0) is None


async def _load(chart, partner, interval, bars, provider):
    return await load_aligned([chart, partner], interval, bars, provider)


def measure(chart, partner, series, degree):
    """Events and control for one pair, thinned, at every width."""
    events, _ = ssmt(series, degree)
    rows = series[chart]
    high = np.array([c.high for c in rows], dtype=np.float64)
    low = np.array([c.low for c in rows], dtype=np.float64)
    close = np.array([c.close for c in rows], dtype=np.float64)
    times = [c.time for c in rows]
    atr = wilder_atr(high, low, close, 14)
    index_of = {c.time: i for i, c in enumerate(rows)}

    kept: dict[str, list[tuple[int, int]]] = {"high": [], "low": []}
    last: dict[str, int] = {"high": -10**9, "low": -10**9}
    for event in events:
        if event.took != chart:
            continue
        at = index_of.get(event.knowable_at)
        if at is None or at < 20 or at + 1 >= len(close) or not np.isfinite(atr[at]):
            continue
        if atr[at] <= 0 or at - last[event.side] < HORIZON:
            continue
        last[event.side] = at
        kept[event.side].append((at, times[at]))

    event_bars = {at for side in kept for at, _ in kept[side]}
    control: list[int] = []
    step = 0
    for at in range(20, len(close) - 1):
        if not np.isfinite(atr[at]) or atr[at] <= 0 or at in event_bars:
            continue
        if step % HORIZON == 0:
            control.append(at)
        step += 1

    out = {}
    for width in WIDTHS:
        ctrl = [(at, _resolve(high, low, close, at, float(atr[at]), width))
                for at in control]  # fmt: skip
        ctrl = [(at, v) for at, v in ctrl if v is not None]
        for side in ("high", "low"):
            obs = []
            for at, t in kept[side]:
                v = _resolve(high, low, close, at, float(atr[at]), width)
                if v is None:
                    continue
                # side "high" is bearish and claims DOWN, "low" claims UP.
                obs.append((t, v if side == "high" else not v))
            cobs = [(times[at], v if side == "high" else not v) for at, v in ctrl]
            out[(width, side)] = (obs, cobs)
    return out, {"events_raw": len(events), "control_bars": len(control)}


def _halves(obs, cobs):
    """Delta in each time half, cut by the median event timestamp."""
    if len(obs) < 4:
        return None
    cut = sorted(t for t, _ in obs)[len(obs) // 2]
    deltas = []
    for lo, hi in ((None, cut), (cut, None)):
        e = [v for t, v in obs if (lo is None or t >= lo) and (hi is None or t < hi)]
        c = [v for t, v in cobs if (lo is None or t >= lo) and (hi is None or t < hi)]
        if not e or not c:
            return None
        deltas.append((sum(e) / len(e)) - (sum(c) / len(c)))
    return deltas


def _walkforward(obs, cobs):
    """Six equal time spans. Every fold reported, including the ones that fail."""
    if not obs:
        return []
    lo = min(t for t, _ in obs + cobs)
    hi = max(t for t, _ in obs + cobs)
    span = max(1, (hi - lo) // FOLDS)
    folds = []
    for k in range(FOLDS):
        a = lo + k * span
        b = hi + 1 if k == FOLDS - 1 else a + span
        e = [v for t, v in obs if a <= t < b]
        c = [v for t, v in cobs if a <= t < b]
        folds.append({
            "fold": k + 1,
            "n_event": len(e),
            "n_control": len(c),
            "event_rate": round(sum(e) / len(e), 4) if e else None,
            "control_rate": round(sum(c) / len(c), 4) if c else None,
            "delta": (round(sum(e) / len(e) - sum(c) / len(c), 4)
                      if e and c else None),
        })  # fmt: skip
    return folds


def main() -> None:
    p = argparse.ArgumentParser(description="SSMT divergence against outcome")
    p.add_argument("--bars", type=int, default=50_000)
    p.add_argument("--interval", type=str, default="1h")
    p.add_argument("--degree", type=str, default="day")
    p.add_argument("--provider", type=str, default="mt5")
    args = p.parse_args()

    _selftest()

    async def run():
        # ONE event loop for every pair. The mt5 provider holds an asyncio lock
        # bound to the loop that created it, so a second `asyncio.run` fails the
        # second pair with "bound to a different event loop" and it arrives
        # looking like a missing symbol.
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

    pairs_out, cells = {}, {}
    for chart, partner in PAIRS:
        got = loaded[(chart, partner)]
        key = f"{chart}|{partner}"
        if isinstance(got, Exception):
            pairs_out[key] = {"skipped": str(got)}
            continue
        series, stats = got
        corr = correlations(series, chart)[0]
        got_cells, counts = measure(chart, partner, series, args.degree)
        pairs_out[key] = {
            "grid": int(stats["grid"]),
            "fetched_chart": int(stats[f"fetched:{chart}"]),
            "fetched_partner": int(stats[f"fetched:{partner}"]),
            "time_from": corr.time_from,
            "time_to": corr.time_to,
            "correlation": {
                "full": None if corr.full is None else round(corr.full, 4),
                "recent": None if corr.recent is None else round(corr.recent, 4),
                "pairs": corr.pairs,
                "sign_changed": corr.sign_changed,
            },
            "events_raw": counts["events_raw"],
            "control_bars_thinned": counts["control_bars"],
            "cells": {},
        }
        for (width, side), (obs, cobs) in got_cells.items():
            cells[(key, width, side)] = (obs, cobs)

    eligible = {k for k, (obs, cobs) in cells.items()
                if len(obs) >= MIN_EVENTS and len(cobs) >= MIN_CONTROL}  # fmt: skip
    K = len(eligible)
    z_crit = _NORM.inv_cdf(1 - ALPHA / K / 2) if K else None

    for (key, width, side), (obs, cobs) in sorted(cells.items()):
        n_e, n_c = len(obs), len(cobs)
        cell = {"n_event": n_e, "n_control": n_c,
                "claimed": "down" if side == "high" else "up"}  # fmt: skip
        if (key, width, side) not in eligible:
            cell["judged"] = False
            cell["reason"] = ("events below 30" if n_e < MIN_EVENTS
                              else "control below 100")  # fmt: skip
        else:
            hits_e, hits_c = sum(v for _, v in obs), sum(v for _, v in cobs)
            delta, z, ci_lo, ci_hi = _z_and_ci(hits_e, n_e, hits_c, n_c)
            halves = _halves(obs, cobs)
            agree = None if halves is None else (halves[0] > 0) == (halves[1] > 0)
            cell.update({
                "judged": True,
                "event_rate": round(hits_e / n_e, 4),
                "control_rate": round(hits_c / n_c, 4),
                "delta": round(delta, 4),
                "delta_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
                "z": round(z, 3),
                "halves": None if halves is None else [round(x, 4) for x in halves],
                "halves_agree": agree,
                "passes": bool(abs(z) > z_crit and agree),
                "walkforward": _walkforward(obs, cobs),
            })  # fmt: skip
        pairs_out[key]["cells"][f"{width}|{side}"] = cell

    passed = [k for k in sorted(eligible)
              if pairs_out[k[0]]["cells"][f"{k[1]}|{k[2]}"]["passes"]]  # fmt: skip
    print(json.dumps({
        "question": (
            "app/layers.py: 'Nothing connects a divergence to an outcome, by "
            "anyone.' Does a knowable SSMT separate the bracket outcome from "
            "the same instrument's non-divergence bars?"
        ),
        "preregistered": "docstring of tools/ssmt_outcomes.py, thresholds before numbers",
        "run": {"bars": args.bars, "interval": args.interval,
                "degree": args.degree, "provider": args.provider,
                "widths": list(WIDTHS), "horizon": HORIZON, "folds": FOLDS},  # fmt: skip
        "thresholds": {
            "min_events": MIN_EVENTS, "min_control": MIN_CONTROL,
            "cells_eligible_K": K, "alpha": ALPHA,
            "alpha_corrected": None if not K else round(ALPHA / K, 6),
            "z_critical_two_sided": None if z_crit is None else round(z_crit, 3),
        },  # fmt: skip
        "pairs": pairs_out,
        "cells_passing_all_three": [f"{a} {b} {c}" for a, b, c in passed],
        "verdict": (
            f"NULL. 0 of {K} eligible cells pass all three pre-registered conditions."
            if not passed else
            f"{len(passed)} of {K} eligible cells pass; per-fold walk-forward is in each cell."
        ),
    }, indent=1))


if __name__ == "__main__":
    main()

"""Do the gap objects this engine draws separate anything? Pre-registered.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.gap_outcomes > ../docs/gap_outcomes.json

WHY THIS EXISTS. `app/chart_gaps.py` draws breakaway and measuring gaps and its
own layer entry says "Unmeasured". Checked 1 September 2026: no evidence file in
`docs/` names either kind, and no prose document mentions them. `app/gaps.py`
draws NDOG and NWOG bands, and those have been measured only as a CONDITIONER of
zone cohorts (`docs/conditioned_gaps.json`, null) - never as an object with a
claim of its own. `detect_ifvg` and `detect_breaker` ship in the detector
registry and appear in no costed file at all: `docs/detectors_costed.json`
contains `fvg` and `order_block` and neither of the inversions.

So five drawn objects, and not one of them has ever been asked the two questions
below. FVG and order block are deliberately NOT re-measured here: they are
already costed, walk-forwarded and backtested, and a fourth measurement of the
same thing would only spend the Bonferroni budget the five unmeasured ones need.

EVERYTHING BELOW THIS LINE WAS FIXED BEFORE A NUMBER WAS COMPUTED.

## 1. The five populations

  breakaway   `chart_gaps` kind breakaway. A price hole out of a flat window.
  measuring   `chart_gaps` kind measuring. A price hole inside a trend.
  opening     `gaps.opening_gaps`, NDOG and NWOG. The distance across a close.
  ifvg        `detect_ifvg`. A fair value gap price closed through.
  breaker     `detect_breaker`. An order block price closed through.

## 2. Two questions, and a third for the one object that projects a price

H_RETURN, asked of all five: is the band reached SOONER than its mirror? Every
one of these objects is drawn as a level worth watching, and a level reached no
faster than an arbitrary line the same distance away is a level that says
nothing.

MEASURED IN BARS, NOT AS A YES OR NO, and the first version of this file got
that wrong too. Asked as "was it touched inside 96 bars" the answer is yes for
almost everything: measured on gold, the euro and the Dow, the real band AND its
mirror are BOTH touched 80 to 95 per cent of the time, because 96 bars is long
enough for price to sweep across both. A question whose answer is yes either way
is not a question. Bars-to-first-touch has no such ceiling, so that is the
statistic, censored at the horizon for both arms alike. A NEGATIVE mean is the
band being reached sooner than its mirror.

H_DIRECTION, asked of the four that claim one: does the forward move in the
claimed direction beat the INSTRUMENT'S OWN DRIFT? Breakaway and measuring gaps
are continuation objects in Edwards and Magee, so the claim is the gap's own
direction. An inverted gap and a breaker are read from the other side, so the
claim is the zone's side. An opening gap claims no direction and is not asked.

H_TARGET, asked of measuring gaps alone: the halfway rule says the move's
remaining distance equals the distance already travelled, and `app/chart_gaps.py`
publishes that as `target`. Is it reached before the mirror distance the other
way?

## 3. The controls, one per question, and they are different on purpose

H_RETURN uses a PAIRED MIRROR BAND: the same band, same height, reflected across
the last close, so it sits the SAME DISTANCE from price on the opposite side.

THE OBVIOUS CONTROL IS THE WRONG ONE HERE, and the first run of this file used
it. `tools.calibrate.shift` moves a band by a random signed 1,5 to 5,0 ATR, and
that is the right control for "does a zone HOLD once touched" - the question
CALIBRATION.md asks. It is the wrong control for "is a band RETURNED TO",
because touch probability is driven by distance and every one of these objects
forms next to price while the shifted placebo lands 1,5 to 5,0 ATR away. Run
that way the five populations read +0,23 to +0,32 at t between +26 and +92,
which is not a finding about gaps, it is a finding about arithmetic. Those
numbers are still reported below as `return_shifted`, labelled and NOT judged,
because deleting them would hide why the control changed.

The mirror is not perfect either: a market that drifts is not symmetric about
its own close, so a band above price and its reflection below are not equally
reachable. That residual is stated rather than corrected, and it is far smaller
than a 1,5 to 5,0 ATR distance gap.

H_DIRECTION uses the INSTRUMENT'S OWN DRIFT, and this is not optional. The first
run of `tools/wyckoff_outcomes.py` tested a signed move against ZERO and
reported a phase MEMPREDIKSI at t=+6,6 while the base rate sat at +0,51 ATR. A
direction claim must beat the drift it is standing in.

H_TARGET uses a PAIRED EARLIER BAR: the same symmetric bracket, same distance in
ATR, resolved from the bar one horizon BEFORE the gap. Same instrument, same
epoch, and it cannot contain the gap.

## 4. Independence, which the first version of the Wyckoff harness got wrong

A 96-bar forward window read at every event overlaps, and events are dense. The
standard error is CLUSTERED on (symbol, forward-window block) with
`tools.wyckoff_outcomes.clustered_t`, the same function and the same reason:
measured there, the naive t was inflated about 6,5 times. Every t below is the
clustered one and the effective n is printed beside it.

## 5. Fixed parameters, no search

  interval    1h
  instruments XAUUSD XAGUSD XPTUSD EURUSD GBPUSD USDJPY AUDUSD US30 USOIL
  horizon     96 bars, the reach horizon `app/layers.py` already uses
  control     H_RETURN mirror across the last close, same distance, other side
  placebo     the old distance-confounded one, reported as `return_shifted`,
              random sign uniform 1,5 to 5,0 ATR, seed 20260901
  flat_atr    2.0 and lookback 20, `chart_gaps`'s own shipped defaults
  min group   30

## 6. Pass conditions

  1. n >= 30 in the population.
  2. |t| past the Bonferroni bar for K, where K is every question eligible to be
     judged across the whole run, computed before one result line.
  3. Reported per instrument as well as pooled, so a pooled result that is one
     instrument wearing a general name can be seen for what it is.

## 7. What is not promised

Nine instruments, one timeframe, one broker's history, no costs. A return rate
is not a trade and a forward move is not expectancy. And `chart_gaps`'s flat
threshold is a chosen number, not a fitted one, so the split between the two
kinds is a stated rule under test rather than a tuned boundary.

AND THE MIRROR DOES NOT SEPARATE "GAP" FROM "RECENTLY TRADED". A gap band sits
where price has just been; its reflection sits where price has not. Levels price
recently traded at are revisited sooner than levels it never reached, for
reasons that have nothing to do with gaps. So a `return_bars` result says the
band is reached sooner than the equidistant level on the other side, and it does
NOT say that being a gap is what did it.

## 8. Second pre-registration, 1 September 2026, written after the first run

THIS SECTION WAS ADDED AFTER SEEING SECTION 6's RESULT, and saying so is the
point of dating it. The first run judged eight questions and one separated:
`measuring` `return_bars` at -2,70 bars, t=-3,65, negative on all nine
instruments. Section 7 above had already named the confound that could produce
it without any gap being involved. The owner asked for that control, so here it
is, and it is asked of EVERY population that had a `return_bars` cell - not only
the one that won, because testing the confound on the winner alone is choosing
the sample after the fact.

H_MATCHED: is the band reached sooner than a synthetic band matched on
DISTANCE, HEIGHT and SIDE, placed at a bar with no gap near it?

  control bar   drawn from the eligible bars within 3000 of the event, outside
                +/- HORIZON of it so the two windows cannot overlap, and never
                within WINDOW bars of any gap
  distance      the same multiple of ATR from that bar's close as the event's
                band midpoint is from its own
  height        the same multiple of ATR
  side          the same side of price

What this control holds fixed that the mirror did not: the band sits on the same
side of price, so "price came from there" is true of both arms. What it still
cannot hold fixed: a gap band is a HOLE bracketed by traded prices, and no
synthetic band has that property. That residual is not fixable by construction
and is not claimed to be.

A second limitation, and it runs one way only. The control bar is kept away from
CHART GAPS but not from inverted gaps or breakers, and those are dense - roughly
one bar in six carries one. So a share of the `ifvg` and `breaker` controls are
anchored on a bar that has the very object under test. That dilutes the contrast
toward zero, which makes a non-null result on those two conservative rather than
flattered.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

import numpy as np

from app.chart_gaps import chart_gaps
from app.detect.inversion import detect_breaker, detect_ifvg
from app.gaps import opening_gaps
from app.indicators import wilder_atr
from app.models import ImbalanceParams
from tools.conditioned import _critical_t
from tools.quant import clean
from tools.wyckoff_outcomes import clustered_t

HORIZON = 96
SHIFT_LO, SHIFT_HI = 1.5, 5.0
SEED = 20260901
MIN_GROUP = 30
#: How far from the event a matched control bar may be drawn, so the two sit in
#: the same epoch without their forward windows overlapping.
MATCH_SPAN = 3000

SYMBOLS = ("XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
           "AUDUSD", "US30", "USOIL")

POPULATIONS = ("breakaway", "measuring", "opening", "ifvg", "breaker")
#: Which questions read a NEGATIVE mean as the claim holding. Bars-to-touch is
#: the only one: sooner is smaller. Getting this backwards labelled the single
#: non-null result in the whole run as an inverted sign.
LOWER_IS_THE_CLAIM = ("return_bars", "return_bars_matched")

#: Which populations carry a direction claim, and are therefore asked H_DIRECTION.
DIRECTIONAL = ("breakaway", "measuring", "ifvg", "breaker")

#: Bars either side of a gap that a matched control may not be anchored on.
WINDOW = 3

#: The questions that count towards K. The two reported-only ones do not spend
#: the Bonferroni budget: `return_binary` hits a ceiling at this horizon and
#: `return_shifted` uses a control confounded by distance. Both are kept in the
#: output because the reason each was set aside is a number, not an opinion.
JUDGED = ("return_bars", "return_bars_matched", "direction", "target")
REPORTED = ("return_binary", "return_shifted")


class Band:
    """One drawn band, reduced to what every question here needs."""

    __slots__ = ("at", "top", "bottom", "direction", "target")

    def __init__(self, at, top, bottom, direction=None, target=None):
        self.at = at              # index of the bar it became knowable on
        self.top = top
        self.bottom = bottom
        self.direction = direction  # +1 up, -1 down, None for no claim
        self.target = target        # the measuring projection, or None


def touched(high, low, top, bottom, start, stop) -> bool:
    """Did any bar in [start, stop) trade inside the band?"""
    for i in range(start, stop):
        if low[i] <= top and high[i] >= bottom:
            return True
    return False


def bars_to_touch(high, low, top, bottom, start, stop) -> int:
    """Bars from `start` until the band is first traded into.

    Censored: a band never reached inside the window is answered as the whole
    window plus one, for BOTH arms of the pair alike, so the censoring cannot
    favour one of them. Roughly 5 to 20 per cent of bands are censored at the
    shipped horizon.
    """
    for i in range(start, stop):
        if low[i] <= top and high[i] >= bottom:
            return i - start
    return stop - start


def bracket(high, low, close, at: int, reach: float, up: bool) -> bool | None:
    """True when the claimed side is reached first, None when neither is.

    Starts at `at + 1`: the bar a reading became knowable on is not a bar it
    could have been acted on. A bar reaching both sides is dropped, not scored,
    because OHLC cannot say which came first.
    """
    want = close[at] + reach if up else close[at] - reach
    other = close[at] - reach if up else close[at] + reach
    for i in range(at + 1, min(len(close), at + 1 + HORIZON)):
        hit_want = high[i] >= want if up else low[i] <= want
        hit_other = low[i] <= other if up else high[i] >= other
        if hit_want and hit_other:
            return None
        if hit_want or hit_other:
            return bool(hit_want)
    return None


def bands_for(candles) -> dict[str, list[Band]]:
    """Every population's bands, each stamped with the bar it is knowable on."""
    out: dict[str, list[Band]] = {k: [] for k in POPULATIONS}

    for gap in chart_gaps(candles):
        out[gap.kind].append(
            Band(gap.at, gap.top, gap.bottom, +1 if gap.up else -1, gap.target)
        )

    index_of = {c.time: i for i, c in enumerate(candles)}
    for gap in opening_gaps(candles):
        at = index_of.get(gap.open_time)
        if at is not None:
            out["opening"].append(Band(at, gap.top, gap.bottom))

    params = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    for name, detector in (("ifvg", detect_ifvg), ("breaker", detect_breaker)):
        zones, _ = detector(candles, params)
        for zone in zones:
            at = zone.anatomy.leg_out_to + 1
            if at >= len(candles):
                continue
            # A demand zone is read up, a supply zone down: the inversion is
            # drawn as the side price is expected to leave from.
            direction = +1 if str(zone.side).lower().endswith("demand") else -1
            out[name].append(Band(at, zone.top, zone.bottom, direction))
    return out


def matched_band(close_j: float, unit_j: float, gap_d: float, gap_h: float):
    """A synthetic band at `close_j`, holding signed distance and height in ATR.

    `gap_d` is the event band's midpoint minus its own close, in ATR, so its
    SIGN carries the side. `gap_h` is the height in ATR. Returns (top, bottom).
    """
    mid = close_j + gap_d * unit_j
    half = gap_h * unit_j / 2.0
    return mid + half, mid - half


def eligible_bars(candles, atr, gap_bars: set[int]) -> np.ndarray:
    """Bars a matched control may be anchored on.

    Excluded: the warm-up, anything without a full forward window, a zero ATR,
    and any bar within `WINDOW` of a gap - a control that sits on top of a gap
    is not a control for gaps.
    """
    near = set()
    for at in gap_bars:
        near.update(range(at - WINDOW, at + WINDOW + 1))
    return np.array([
        i for i in range(20, len(candles) - HORIZON - 1)
        if atr[i] > 0 and i not in near
    ], dtype=np.int64)


def study(symbols: list[str], interval: str = "1h") -> dict:
    rng = np.random.default_rng(SEED)
    rows: dict[str, dict[str, list]] = {
        pop: {q: [] for q in (*JUDGED, *REPORTED)} for pop in POPULATIONS
    }
    per_symbol: dict[str, dict] = {}

    for symbol in symbols:
        try:
            candles, _, _ = clean(symbol, interval)
        except Exception as exc:  # noqa: BLE001
            per_symbol[symbol] = {"error": str(exc)}
            continue
        if len(candles) < HORIZON * 4:
            per_symbol[symbol] = {"bars": len(candles), "note": "too short"}
            continue
        high = np.array([c.high for c in candles], dtype=np.float64)
        low = np.array([c.low for c in candles], dtype=np.float64)
        close = np.array([c.close for c in candles], dtype=np.float64)
        atr = wilder_atr(high, low, close, 14)

        # The instrument's own drift, from a sparse sample of bars, in the same
        # ATR unit the excess move is measured in.
        step = max(1, len(candles) // 2000)
        sample = [
            float(close[i + HORIZON] - close[i]) / float(atr[i])
            for i in range(0, len(candles) - HORIZON, step)
            if atr[i] > 0
        ]
        drift = float(np.mean(sample)) if sample else 0.0

        found = bands_for(candles)
        counts = {pop: len(v) for pop, v in found.items()}
        gap_bars = {b.at for pop in ("breakaway", "measuring") for b in found[pop]}
        pool = eligible_bars(candles, atr, gap_bars)
        # HOW FLAT DOES A 20-BAR WINDOW EVER GET, in units of its own mean true
        # range. `chart_gaps` calls a gap breakaway only when that ratio is at
        # or under 2,0, so this number decides whether the branch can fire at
        # all - and it is reported per instrument rather than assumed.
        from app.chart_gaps import _atr as window_atr

        ratios = []
        for i in range(20, len(candles), 50):
            window = candles[i - 20:i]
            a = window_atr(window)
            if a > 0:
                ratios.append(
                    (max(c.high for c in window) - min(c.low for c in window)) / a
                )
        counts["window_range_over_atr_min"] = (
            round(float(np.min(ratios)), 3) if ratios else None
        )
        for pop, bands in found.items():
            for band in bands:
                at = band.at
                if at < 20 or at + HORIZON >= len(close) or atr[at] <= 0:
                    continue
                stop = at + 1 + HORIZON
                unit = float(atr[at])

                # H_RETURN, paired against the band mirrored across the last
                # close: same height, same distance, other side.
                here = float(close[at])
                mirror_top = 2 * here - band.bottom
                mirror_bottom = 2 * here - band.top
                bars_real = bars_to_touch(
                    high, low, band.top, band.bottom, at + 1, stop
                )
                bars_mirror = bars_to_touch(
                    high, low, mirror_top, mirror_bottom, at + 1, stop
                )
                rows[pop]["return_bars"].append(
                    (symbol, at, float(bars_real - bars_mirror))
                )
                # `bars_to_touch` censors AT the window width, so "touched" is
                # strictly inside it. Written `<=` first, which made every band
                # count as touched and every difference exactly zero.
                # H_MATCHED, paired against a synthetic band at a gap-free bar
                # holding distance, height and side fixed.
                mid = (band.top + band.bottom) / 2.0
                gap_d = (mid - here) / unit          # signed, in ATR
                gap_h = (band.top - band.bottom) / unit
                near = pool[
                    (pool >= at - MATCH_SPAN) & (pool <= at + MATCH_SPAN)
                    & ((pool <= at - HORIZON) | (pool >= at + HORIZON))
                ]
                if len(near):
                    j = int(near[rng.integers(len(near))])
                    top_j, bottom_j = matched_band(
                        float(close[j]), float(atr[j]), gap_d, gap_h
                    )
                    bars_matched = bars_to_touch(
                        high, low, top_j, bottom_j, j + 1, j + 1 + HORIZON
                    )
                    rows[pop]["return_bars_matched"].append(
                        (symbol, at, float(bars_real - bars_matched))
                    )

                rows[pop]["return_binary"].append((
                    symbol, at,
                    float(bars_real < HORIZON) - float(bars_mirror < HORIZON),
                ))

                # The old distance-confounded control, kept and reported so the
                # reason the judged one changed is visible rather than asserted.
                offset = float(rng.choice([-1.0, 1.0])) * float(
                    rng.uniform(SHIFT_LO, SHIFT_HI)
                ) * unit
                fake = touched(
                    high, low, band.top + offset, band.bottom + offset, at + 1, stop
                )
                rows[pop]["return_shifted"].append((
                    symbol, at,
                    float(bars_real < HORIZON) - float(fake),
                ))

                # H_DIRECTION, against the instrument's own drift.
                if band.direction is not None:
                    move = float(close[at + HORIZON] - close[at]) / unit
                    rows[pop]["direction"].append(
                        (symbol, at, band.direction * (move - drift))
                    )

                # H_TARGET, paired against the same bracket one horizon earlier.
                if band.target is not None:
                    reach = abs(band.target - close[at])
                    if reach <= 0:
                        continue
                    up = band.direction == +1
                    got = bracket(high, low, close, at, reach, up)
                    prior = at - HORIZON
                    was = (
                        bracket(high, low, close, prior, reach, up)
                        if prior > 20
                        else None
                    )
                    if got is not None and was is not None:
                        rows[pop]["target"].append(
                            (symbol, at, float(got) - float(was))
                        )
        per_symbol[symbol] = {"bars": len(candles), "drift_atr": drift, **counts}

    # K BEFORE ONE RESULT LINE.
    k = sum(
        1
        for pop in POPULATIONS
        for q in JUDGED
        if len(rows[pop][q]) >= MIN_GROUP
    )
    critical = _critical_t(max(k, 1))

    out: dict = {
        "preregistered": "tools/gap_outcomes.py, 2026-09-01",
        "question": "apakah objek gap yang digambar memisahkan apa pun",
        "horizon_bars": HORIZON,
        "placebo": f"random sign, uniform {SHIFT_LO} to {SHIFT_HI} ATR, seed {SEED}",
        "questions_judged": k,
        "critical_t": critical,
        "min_group": MIN_GROUP,
        "populations": {},
        "cells": per_symbol,
    }
    for pop in POPULATIONS:
        block: dict = {}
        for q in (*JUDGED, *REPORTED):
            recs = rows[pop][q]
            if len(recs) < MIN_GROUP:
                block[q] = {"n": len(recs), "verdict": "n kecil"}
                continue
            vals = [v for _, _, v in recs]
            t, n_eff = clustered_t(vals, [(s, i // HORIZON) for s, i, _ in recs])
            mean = float(np.mean(vals))
            verdict = ""
            if q == "return_shifted":
                verdict = "TIDAK DINILAI, kontrolnya bias jarak"
            elif q == "return_binary":
                verdict = "TIDAK DINILAI, kena ceiling di horizon ini"
            elif not np.isnan(t) and abs(t) >= critical:
                holds = (t < 0) if q in LOWER_IS_THE_CLAIM else (t > 0)
                verdict = "MEMISAHKAN" if holds else "MEMISAHKAN, TANDA TERBALIK"
            block[q] = {
                "n": len(vals), "mean": mean, "t": t, "n_effective": n_eff,
                "verdict": verdict,
                "by_symbol": {
                    s: round(float(np.mean([v for sy, _, v in recs if sy == s])), 4)
                    for s in sorted({sy for sy, _, _ in recs})
                },
            }
        out["populations"][pop] = block
    return out


def selfcheck() -> int:
    """The two primitives, on bars whose answer is known in advance."""
    high = np.array([10.0, 11.0, 12.0, 9.0, 10.0])
    low = np.array([9.0, 10.0, 11.0, 8.0, 9.0])
    # The band [11, 12] is traded into at index 2 and not before it.
    assert touched(high, low, 12.0, 11.0, 1, 5) is True
    assert touched(high, low, 12.0, 11.0, 3, 5) is False
    # A band nothing reaches.
    assert touched(high, low, 100.0, 99.0, 0, 5) is False
    # Bars-to-touch counts from the start bar, and censors at the window edge
    # with the same value for a band nothing reaches.
    # Bar 1 has high 11, which is an exact touch of the band's bottom, so from
    # bar 1 the wait is nothing and from bar 0 it is one bar.
    assert bars_to_touch(high, low, 12.0, 11.0, 1, 5) == 0
    assert bars_to_touch(high, low, 12.0, 11.0, 0, 5) == 1
    assert bars_to_touch(high, low, 100.0, 99.0, 0, 5) == 5
    # The matched band keeps distance, height and SIDE, in ATR units, at a
    # different close and a different ATR. A sign dropped here would move the
    # control to the other side of price and quietly answer the mirror question
    # all over again.
    top, bottom = matched_band(close_j=200.0, unit_j=4.0, gap_d=-1.5, gap_h=0.5)
    assert abs((top + bottom) / 2 - (200.0 - 1.5 * 4.0)) < 1e-9, (top, bottom)
    assert abs((top - bottom) - 0.5 * 4.0) < 1e-9
    assert (top + bottom) / 2 < 200.0, "a negative distance stays below price"
    up_top, up_bottom = matched_band(200.0, 4.0, +1.5, 0.5)
    assert (up_top + up_bottom) / 2 > 200.0, "a positive distance stays above"
    # Scale-free: double the ATR, double the offset and the height.
    t2, b2 = matched_band(200.0, 8.0, -1.5, 0.5)
    assert abs((t2 + b2) / 2 - (200.0 - 1.5 * 8.0)) < 1e-9
    assert abs((t2 - b2) - 0.5 * 8.0) < 1e-9
    # A bar whose HIGH exactly equals the band's bottom has touched it. Strict
    # inequalities here would drop every exact-touch return, and an exact touch
    # of a level is the event this whole family is about.
    assert touched(np.array([5.0]), np.array([4.0]), 9.0, 5.0, 0, 1) is True
    assert touched(np.array([9.0]), np.array([5.0]), 5.0, 1.0, 0, 1) is True

    # The bracket starts AFTER the decision bar: a move on the bar itself is not
    # scored, which is the anti-lookahead rule this whole repo runs on.
    flat = np.full(40, 100.0)
    up_hi, up_lo = np.full(40, 100.0), np.full(40, 100.0)
    up_hi[0] = 200.0  # on the decision bar, must not count
    assert bracket(up_hi, up_lo, flat, 0, 5.0, True) is None
    up_hi[0] = 100.0
    up_hi[3] = 200.0
    assert bracket(up_hi, up_lo, flat, 0, 5.0, True) is True
    # The other side first is a False, not a None.
    dn_hi, dn_lo = np.full(40, 100.0), np.full(40, 100.0)
    dn_lo[2] = 1.0
    assert bracket(dn_hi, dn_lo, flat, 0, 5.0, True) is False
    # Both sides on one bar is dropped, because OHLC cannot order them.
    b_hi, b_lo = np.full(40, 100.0), np.full(40, 100.0)
    b_hi[2], b_lo[2] = 200.0, 1.0
    assert bracket(b_hi, b_lo, flat, 0, 5.0, True) is None
    print("selfcheck OK", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(SYMBOLS))
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        return selfcheck()
    selfcheck()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with contextlib.redirect_stdout(sys.stderr):
        out = study(symbols, args.interval)
    json.dump(out, sys.stdout, indent=2, default=float)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

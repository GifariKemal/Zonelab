"""Does the 06:00 H4 candle travel back toward the true day open?

    python -m tools.true_day_open

THE HYPOTHESIS, PRE-REGISTERED, IN THE OWNER'S OWN WORDS

    "Mark 00:00 NY setiap hari, mark candle H4 jam 06:00, lalu hitung berapa
     kali H4 kembali ke arah 00:00, dipisah kasus open di atas vs di bawah
     true day open."

He wrote that down before any number existed for it, which is what makes it
worth running: it cannot have been chosen because it worked.

00:00 NY AND "TRUE DAY OPEN" ARE THE SAME LEVEL HERE, and that is not an
assumption this tool makes, it is what `app/quarters.py` already implements. The
day cycle opens at 18:00 NY and its four quarters are Q1 18:00, Q2 00:00, Q3
06:00, Q4 12:00; a cycle's true open is by construction its Q2 open; therefore
the true day open IS midnight. `true_opens(candles, ("day",))` returns exactly
that price and this tool reads it from there rather than recomputing midnight.
So the split he asks for reads: did the 06:00 candle OPEN above or below the
midnight price. Notice also that 06:00 is the day cycle's Q3 open, so the test
is really "does Q3 retrace toward Q2's open".

THE H4 CANDLE is the four hourly bars opening 06:00, 07:00, 08:00, 09:00 New
York. A CHOICE, stated: he said H4, and an H4 candle is four hours, but the day
quarter that starts at 06:00 runs six hours to 12:00, so "the candle at 06:00"
had two defensible spans. Four is taken because that is the word he used. Each
of the four bars is located by New York WALL CLOCK through `app.clock`, never by
adding 3600 four times, so the window is right on transition days too.

"RETURNS TOWARD" IS AMBIGUOUS AND THE AMBIGUITY IS PART OF THE RESULT. His
phrase admits at least three readings, so all three are measured and reported
side by side:

  touch    the candle's wick reaches the midnight level at all. If it opened
           above, low <= midnight; if below, high >= midnight.  <- PRIMARY
  close    the candle CLOSES on the far side of the level.
  half     the candle travels at least 50% of its opening distance back toward
           the level. Implied by touch, implies nothing about the close.

`touch` is primary. That is a CHOICE OF MINE AND NOT HIS WORDS: it is the
loosest of the three and so the closest to the plain sense of "kembali ke arah",
it is a statement about the candle's range alone, and unlike `half` it needs no
fraction that I would have had to pick. If the three disagree, the disagreement
is the finding and no single one of them may be quoted as the answer.

THE CONTROL, because a raw rate is not a result. "It came back 62% of the time"
is unreadable without knowing what a candle does anyway.

  MIRROR (primary control, paired).  Reflect the midnight level through the
  candle's open: P = open + (open - midnight). Same distance, opposite side.
  "Travelled toward midnight" is then measured against "travelled the identical
  distance away from it", within the SAME candle, under the SAME definition.
  Distance, volatility, day and instrument are held fixed by construction, which
  no shuffled or offset placebo manages. The two outcomes are paired per day, so
  the test is McNemar's, exact binomial on the discordant pairs.

  HOUR (secondary control).  The same measurement for a candle opening at each
  even hour of the New York day against the same midnight level. It answers a
  different question: not "is the level real" but "is 06:00 the special hour".
  Ranked by margin over mirror, not by raw rate, because a candle opening at
  01:00 sits closer to midnight in price and would win a raw-rate comparison for
  a reason that has nothing to do with the hypothesis.

RULES THIS OBEYS. Both cohorts always reported and the headline takes the WEAKER
of the two. n stated everywhere. Days where a required bar never opened are
DROPPED and counted, never filled. The cohort is decided from the midnight open
and the 06:00 open, both known at 06:00, so nothing here reads a bar that had
not closed. Five time-ordered folds, and the count of folds agreeing in sign is
reported next to the pooled number.

Gold first, because that is what he trades, then unrelated instruments, because
a harness that only speaks about one series is measuring that series.
"""

from __future__ import annotations

import argparse
import json
from math import comb, sqrt
from pathlib import Path

from app import clock
from app.models import Candle
from app.quarters import true_opens
from tools import history

SERIES = [
    ("yahoo:XAUUSD", "1h"),  # gold, the instrument the hypothesis is about
    ("PAXGUSDT", "1h"),  # tokenised gold, a second vendor on the same metal
    ("BTCUSDT", "1h"),  # unrelated, and 24/7 so midnight NY is nothing special
    ("ETHUSDT", "1h"),
]
DEFS = ("touch", "close", "half")
PRIMARY = "touch"
HOURS = tuple(range(0, 21, 2))  # 20:00 + 4h is the last window inside the day
FOLDS = 5
DOCS = Path(__file__).resolve().parent.parent.parent / "docs" / "true_day_open.json"


def h4(at: dict[int, Candle], midnight: int, hour: int) -> Candle | None:
    """The four-hour candle opening at `hour` New York on midnight's date.

    Every one of the four hourly bars is required. No bar, no observation: a
    holiday or an early close leaves a window that was never traded, and an H4
    candle assembled from two bars has a high and a low that mean something else.
    """
    bars = [at.get(clock.at_ny_hour(midnight, hour + i)) for i in range(4)]
    if any(bar is None for bar in bars):
        return None
    kept = [bar for bar in bars if bar is not None]  # narrowing, same four bars
    return Candle(
        time=kept[0].time,
        open=kept[0].open,
        high=max(bar.high for bar in kept),
        low=min(bar.low for bar in kept),
        close=kept[-1].close,
    )


def observe(level: float, bar: Candle) -> dict | None:
    """One day's record: which cohort, and the three definitions both ways.

    `None` when the candle opened exactly ON the level, where "above or below"
    has no answer and the distance the mirror needs is zero.
    """
    gap = bar.open - level
    if gap == 0.0:
        return None
    mirror = bar.open + gap  # same distance, opposite side
    half_to = bar.open - gap / 2
    half_away = bar.open + gap / 2
    above = gap > 0

    if above:
        toward = (bar.low <= level, bar.close < level, bar.low <= half_to)
        away = (bar.high >= mirror, bar.close > mirror, bar.high >= half_away)
    else:
        toward = (bar.high >= level, bar.close > level, bar.high >= half_to)
        away = (bar.low <= mirror, bar.close < mirror, bar.low <= half_away)

    return {
        "at": bar.time,
        "side": "above" if above else "below",
        "distance": abs(gap),
        **{f"{name}": hit for name, hit in zip(DEFS, toward)},
        **{f"mirror_{name}": hit for name, hit in zip(DEFS, away)},
    }


def scan(candles: list[Candle], hour: int) -> tuple[list[dict], dict[str, int]]:
    """Every day that has both a midnight bar and a complete candle at `hour`."""
    at = {candle.time: candle for candle in candles}
    levels = true_opens(candles, ("day",))
    rows, dropped = [], {"no_candle": 0, "open_on_level": 0}
    for level in levels:
        bar = h4(at, level.time, hour)
        if bar is None:
            dropped["no_candle"] += 1
            continue
        row = observe(level.price, bar)
        if row is None:
            dropped["open_on_level"] += 1
            continue
        rows.append(row)
    # A day with no midnight bar at all never reaches here: `true_opens` already
    # refuses to invent the level, so those days are absent from `levels` and are
    # reported as the gap between the calendar and `len(levels)`.
    dropped["days"] = len(levels)
    return rows, dropped


def mcnemar(rows: list[dict], name: str) -> dict:
    """Paired comparison of `toward` against its own mirror, exact binomial.

    Only the discordant days carry information: a day where the candle reached
    both levels, or neither, says nothing about which direction it favoured.
    """
    n = len(rows)
    hit = sum(row[name] for row in rows)
    miss = sum(row[f"mirror_{name}"] for row in rows)
    b = sum(1 for row in rows if row[name] and not row[f"mirror_{name}"])
    c = sum(1 for row in rows if row[f"mirror_{name}"] and not row[name])
    out = {
        "n": n,
        "toward": hit,
        "away": miss,
        "rate": hit / n if n else float("nan"),
        "control_rate": miss / n if n else float("nan"),
        "margin": (hit - miss) / n if n else float("nan"),
        "discordant_toward": b,
        "discordant_away": c,
    }
    if n == 0:
        return out | {"ci_low": float("nan"), "ci_high": float("nan"), "p": 1.0}

    se = sqrt(max(b + c - (b - c) ** 2 / n, 0.0)) / n
    out["ci_low"] = out["margin"] - 1.96 * se
    out["ci_high"] = out["margin"] + 1.96 * se
    pairs = b + c
    out["p"] = (
        1.0
        if pairs == 0
        else min(
            1.0,
            2.0 * sum(comb(pairs, i) for i in range(min(b, c) + 1)) / 2**pairs,
        )
    )
    return out


def folds(rows: list[dict], name: str) -> list[float]:
    """Margin over the mirror in each of `FOLDS` time-ordered slices."""
    ordered = sorted(rows, key=lambda row: row["at"])
    size = len(ordered) / FOLDS
    out = []
    for i in range(FOLDS):
        chunk = ordered[int(i * size) : int((i + 1) * size)]
        out.append(mcnemar(chunk, name)["margin"] if chunk else float("nan"))
    return out


def report(symbol: str, interval: str, bars: int) -> dict:
    candles = history.load(symbol, interval, bars)
    rows, dropped = scan(candles, 6)
    above = [row for row in rows if row["side"] == "above"]
    below = [row for row in rows if row["side"] == "below"]

    print(f"\n{'=' * 78}")
    print(f"TRUE DAY OPEN   {symbol} {interval}   {len(candles)} bars")
    print(f"{'=' * 78}")
    print(
        f"  {dropped['days']} days had a midnight bar; "
        f"{dropped['no_candle']} of those had no complete 06:00 H4 and were "
        f"dropped,\n  {dropped['open_on_level']} opened exactly on the level and "
        f"were dropped. {len(rows)} observations remain,\n  {len(above)} opening "
        f"ABOVE the true day open and {len(below)} BELOW."
    )

    out: dict = {
        "bars": len(candles),
        "first": candles[0].time,
        "last": candles[-1].time,
        "days_with_midnight": dropped["days"],
        "dropped_no_h4": dropped["no_candle"],
        "dropped_open_on_level": dropped["open_on_level"],
        "n": len(rows),
        "cohorts": {},
    }

    for label, cohort in (("above", above), ("below", below), ("pooled", rows)):
        print(f"\n  opened {label.upper()}   n={len(cohort)}")
        print(
            f"    {'definition':<10}{'toward':>8}{'rate':>8}{'mirror':>8}"
            f"{'control':>9}{'margin':>9}{'95% CI':>18}{'p':>10}"
        )
        block = {}
        for name in DEFS:
            stat = mcnemar(cohort, name)
            block[name] = stat
            ci = "[%+.3f, %+.3f]" % (stat["ci_low"], stat["ci_high"])
            print(
                f"    {name:<10}{stat['toward']:>8}{stat['rate']:>8.3f}"
                f"{stat['away']:>8}{stat['control_rate']:>9.3f}"
                f"{stat['margin']:>+9.3f}{ci:>18}{stat['p']:>10.4f}"
            )
        signs = folds(cohort, PRIMARY)
        block["folds"] = signs
        agree = sum(1 for s in signs if s > 0)
        print(
            f"    folds ({PRIMARY}): "
            + "  ".join("nan" if s != s else f"{s:+.3f}" for s in signs)
            + f"   -> {agree}/{FOLDS} positive"
        )
        out["cohorts"][label] = block

    print(f"\n  HOUR CONTROL, same level, {PRIMARY} definition, worse cohort shown")
    print(
        f"    {'hour NY':>8}{'n':>7}{'above margin':>15}{'below margin':>15}"
        f"{'worse':>9}"
    )
    hours = {}
    for hour in HOURS:
        hour_rows, _ = scan(candles, hour)
        a = mcnemar([r for r in hour_rows if r["side"] == "above"], PRIMARY)
        b = mcnemar([r for r in hour_rows if r["side"] == "below"], PRIMARY)
        worse = min(a["margin"], b["margin"])
        hours[f"{hour:02d}"] = {"n": len(hour_rows), "above": a["margin"],
                                "below": b["margin"], "worse": worse}  # fmt: skip
        mark = "  <- the hypothesis" if hour == 6 else ""
        print(
            f"    {hour:>6}:00{len(hour_rows):>7}{a['margin']:>+15.3f}"
            f"{b['margin']:>+15.3f}{worse:>+9.3f}{mark}"
        )
    out["hour_control"] = hours
    return out


def _selfcheck() -> None:
    """The sign conventions, on candles whose answer is known by inspection.

    An inverted comparison here would not crash and would not look wrong in the
    table; it would simply report the mirror as the hypothesis and the
    hypothesis as the mirror, and every number would still be plausible.
    """
    # Opened 10 above a level of 100, wicked down through it, closed back up.
    row = observe(100.0, Candle(time=0, open=110.0, high=112.0, low=99.0, close=108.0))
    assert row is not None and row["side"] == "above" and row["distance"] == 10.0
    assert row["touch"] and row["half"] and not row["close"]
    assert not row["mirror_touch"] and not row["mirror_half"]  # 120 and 115 unreached

    # Same shape mirrored: opened 10 BELOW, wicked up through, closed back down.
    row = observe(100.0, Candle(time=0, open=90.0, high=101.0, low=88.0, close=92.0))
    assert row is not None and row["side"] == "below"
    assert row["touch"] and row["half"] and not row["close"]
    assert not row["mirror_touch"]  # 80 unreached

    # Ran the WRONG way only: the mirror fires and the hypothesis does not.
    # Closing exactly ON the mirror at 120.0 would NOT count: crossing is strict.
    row = observe(100.0, Candle(time=0, open=110.0, high=121.0, low=109.0, close=120.5))
    assert row is not None and not row["touch"] and not row["half"]
    assert row["mirror_touch"] and row["mirror_half"] and row["mirror_close"]

    # Opening exactly on the level has no cohort and no distance to mirror.
    assert observe(100.0, Candle(time=0, open=100.0, high=1.0, low=0.0, close=1.0)) is None

    # McNemar on a perfectly one-sided set of discordant pairs.
    rows = [{"touch": True, "mirror_touch": False} for _ in range(10)]
    stat = mcnemar(rows, "touch")
    assert stat["margin"] == 1.0 and stat["p"] < 0.01
    print("selfcheck ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--symbol", action="append", dest="symbols")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--json", default=str(DOCS))
    args = parser.parse_args()

    if args.selfcheck:
        return _selfcheck()

    series = (
        [(s, args.interval) for s in args.symbols] if args.symbols else list(SERIES)
    )
    out = {symbol + " " + interval: report(symbol, interval, args.bars)
           for symbol, interval in series}  # fmt: skip

    print(f"\n{'=' * 78}")
    print(f"HEADLINE, weaker cohort, {PRIMARY} definition, margin over the mirror")
    print(f"{'=' * 78}")
    print(f"  {'series':<20}{'n':>7}{'margin':>10}{'p':>10}{'folds +':>10}")
    for key, block in out.items():
        weak = min(
            (block["cohorts"][side] for side in ("above", "below")),
            key=lambda c: c[PRIMARY]["margin"],
        )
        agree = sum(1 for s in weak["folds"] if s > 0)
        print(
            f"  {key:<20}{weak[PRIMARY]['n']:>7}{weak[PRIMARY]['margin']:>+10.3f}"
            f"{weak[PRIMARY]['p']:>10.4f}{agree:>7}/{FOLDS}"
        )
    print(
        "\n  A margin near zero is the null: the candle travels toward the true\n"
        "  day open exactly as often as it travels the same distance away from\n"
        "  it, and the raw rate was measuring the width of a four-hour candle."
    )

    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, default=float))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()

"""What the drawing is worth once the spread is charged.

    python -m tools.costed

Every number this project has produced is frictionless. That was fine while the
question was "does the box mark a real place", and it stops being fine the
moment anyone asks what a zone is worth. An edge of a few points is exactly the
size that transaction costs eat, so an uncosted edge is not a small
approximation of a costed one - it can be the opposite sign.

This is the first tool here that charges anything, and it can only exist because
Dukascopy publishes both sides of the book. The spread is MEASURED per bar, not
assumed: on XAUUSD it runs about 0.54 to 0.67 USD with gold near 4370, and
widens past 2.0 into the Friday close.

WHAT THIS IS NOT
It is not a strategy backtest, because there is no strategy: Twelve pre-registered
hypotheses failed to get a DIRECTION out of these drawings, so nothing here
decides whether to be long or short. What it measures is the doctrine's own
claim taken at face value - every zone traded in its own direction, demand long
and supply short, entry at the proximal line, stop beyond the distal, target at
the nearest live opposing zone. If that is negative after costs, then the
drawing does not pay for itself even when you believe it completely.

THE RULES, ALL PESSIMISTIC WHERE THE BAR IS AMBIGUOUS
  - the touch bar counts. Price reached the proximal line during it, so the rest
    of that bar can stop you out;
  - if one bar's range contains BOTH the stop and the target, the STOP is taken.
    Bar data cannot say which came first, and assuming the good one is how a
    backtest invents an edge;
  - the spread is charged on entry AND on the exit, because a stop under a long
    is filled on the other side of the book from the entry;
  - commission and slippage are stated parameters with stated defaults, not
    fitted. There is no published number for either and inventing a precise one
    would be fiction; they are reported so the reader can move them.

Zones with no live opposing zone ahead have no measured target and are counted
and skipped rather than given a conventional R multiple. That count is reported,
because silently dropping a third of the population would flatter whatever is
left.
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from app.costs import BROKERS, row_for, schedule
from app.detect import DETECTORS
from app.detect.structure import swings
from app.indicators import wilder_atr
from app.models import ImbalanceParams, SupplyDemandParams, ZoneSide
from app.plan import build
from app.profit_zone import profit_zone_at
from app.providers.base import INTERVALS
from tools import history
from tools.calibrate import POPULATION

HORIZON = 80  # bars a trade is given before it is called a timeout

# The cost table used to live here, which is exactly why the shipped trade plan
# charged the spread only: the researched numbers were reachable from the
# measurement and from nowhere else. It is now app/costs.py, read by this tool
# AND by app/plan.py, and every provenance comment moved with its number. All
# figures are BASIS POINTS OF NOTIONAL, per instrument, with `--conservative`
# and `--broker` selecting the alternate rows; `schedule` does the merge so the
# two call sites below cannot pick different rows.

# 21:00 UTC in northern summer, 22:00 in winter. The earlier hour is modelled
# because charging at the earlier cutoff catches more trades, and this whole
# line item is one a backtest must not flatter itself on.
ROLLOVER_HOUR_UTC = 21
# Every figure above is ROUND TURN except swap, which is per rollover crossed.
# Charged once per trade, because that is how the sources quote them.
#
# The spread is NOT double charged, despite the shape of the code: plan.build
# lifts the entry fill by one full spread and leaves the stop where it is, which
# is arithmetically identical to paying half a spread on each leg. Checked
# rather than assumed, because a review flagged it as a 2x overcharge and it is
# not one.
PLACEBO_DRAWS = 3  # each zone displaced this many times, for a steadier control
FOLDS = 8  # same count every other walk-forward here used, so p is comparable


def _params(name: str):
    base = dict(max_zones_per_side=0, show_broken=True)
    if name == "supply_demand":
        return SupplyDemandParams(**{**POPULATION, **base})
    return ImbalanceParams(**base)


def trades(
    name: str, candles, interval: str, costs: bool, rng=None,
    anchored: bool = False, symbol: str = "XAUUSD",
    conservative: bool = False, broker: str = "",
    flat_by_rollover: bool = False,
) -> list[dict]:
    """Every zone's first touch, resolved to an R multiple.

    `rng` turns this into the PLACEBO arm: the box keeps its height, its side
    and its bar, and is moved to a price it was never drawn at. Everything else
    is identical, so whatever the placebo earns is what this market pays any
    bracket of that shape, and only the difference belongs to the drawing. This
    control has already killed one finding here - reversals at zones were real
    and random boxes reversed just as often.
    """
    fees = schedule(symbol, conservative, broker)
    params = _params(name)
    zones, _ = DETECTORS[name](candles, params)

    time = np.array([c.time for c in candles], dtype=np.int64)
    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    atr = wilder_atr(high, low, close, params.atr_period)
    index_of = {int(t): i for i, t in enumerate(time)}
    step = INTERVALS[interval]
    # Only needed by the anchored control, and each swing carries the bar it
    # became knowable on, so a control cannot use a pivot from the future.
    pivots = swings(high, low, 2, 2) if anchored else []

    out = []
    for zone in zones:
        if zone.first_test_time is None:
            continue
        touch = index_of.get(zone.first_test_time)
        if touch is None or touch < 1 or touch + HORIZON >= len(close):
            continue
        scale = float(atr[touch - 1])
        if scale <= 0:
            continue

        if rng is not None and anchored:
            # THE MATCHED CONTROL, and it exists because of an objection this
            # project raised against its own result. A real zone's distal is a
            # WICK EXTREME - a price at which price has already been shown to
            # turn - while a randomly displaced box's distal is an arbitrary
            # level that noise walks through. Part of the margin over the random
            # placebo may therefore be nothing but "a stop at a real extreme is
            # a better stop", which is close to a tautology.
            #
            # So this control keeps that property and breaks everything else:
            # the box is rebuilt around a CONFIRMED SWING that has nothing to do
            # with this zone. Same height, same side, stop at a real extreme,
            # wrong place. Whatever survives THIS is not the tautology.
            usable = [s for s in pivots
                      if s.confirmed_at < touch and s.high is not (
                          zone.side is ZoneSide.DEMAND)]
            if not usable:
                continue
            pick = usable[int(rng.integers(0, len(usable)))]
            height = zone.top - zone.bottom
            demand = zone.side is ZoneSide.DEMAND
            top = pick.price + height if demand else pick.price
            bottom = pick.price if demand else pick.price - height
            zone = zone.model_copy(update={
                "top": top, "bottom": bottom,
                "proximal": top if demand else bottom,
                "distal": bottom if demand else top,
            })
            arrived = None
            for j in range(touch, min(touch + HORIZON + 1, len(close))):
                if low[j] <= zone.proximal <= high[j]:
                    arrived = j
                    break
            if arrived is None or arrived + HORIZON >= len(close):
                continue
            touch = arrived
            scale = float(atr[touch - 1])
            if scale <= 0:
                continue

        elif rng is not None:
            # Same height, same side, same bar, wrong price. Displaced by a
            # random multiple of its own height so the shift is meaningful
            # relative to the box rather than to the instrument.
            shift = float(rng.uniform(-6.0, 6.0)) * (zone.top - zone.bottom)
            demand = zone.side is ZoneSide.DEMAND
            zone = zone.model_copy(update={
                "top": zone.top + shift, "bottom": zone.bottom + shift,
                "proximal": (zone.top if demand else zone.bottom) + shift,
                "distal": (zone.bottom if demand else zone.top) + shift,
            })
            # The placebo has to be ENTERED the way the real zone was: on the
            # bar price first reached its proximal line. Reusing the real
            # zone's touch bar would start the walk before the displaced box
            # was ever touched, so a box sitting far above price would be
            # "stopped out" on a bar it had not been entered on. A box price
            # never reaches at all is not a trade and is dropped, because
            # counting it would let the placebo dodge losses for free.
            arrived = None
            for j in range(touch, min(touch + HORIZON + 1, len(close))):
                if low[j] <= zone.proximal <= high[j]:
                    arrived = j
                    break
            if arrived is None or arrived + HORIZON >= len(close):
                continue
            touch = arrived
            scale = float(atr[touch - 1])
            if scale <= 0:
                continue

        # The road is RECOMPUTED at the touch bar, and this is not a detail.
        # `zone.profit_zone_rr` is stamped with the LAST bar's time, which is
        # the right answer for "what does the trader see now" and lookahead for
        # "what could the trader have seen then" - the opposing zone that sets
        # the target may not have existed yet. profit_zone_at says exactly this
        # in its own docstring; the first run of this tool used the stamped
        # value anyway and every target was contaminated.
        at_touch = zone.model_copy(update={
            "profit_zone_rr": profit_zone_at(zone, zones, int(time[touch]))
        })
        # A measured spread always beats an assumed one. Only Dukascopy
        # publishes both sides; everything else falls back to a stated bp
        # figure, and the report says which arm each instrument used.
        if not costs:
            spread = None
        elif candles[touch].spread is not None:
            spread = candles[touch].spread
        elif fees["spread_bp"] is not None:
            spread = float(close[touch]) * fees["spread_bp"] / 10_000
        else:
            spread = None
        plan = build(at_touch, scale, int(time[touch]), step, spread=spread)
        if plan is None:
            continue
        if plan.target is None:
            out.append({"skipped": True, "cleared": zone.departure_atr >= 2.0})
            continue

        long_side = zone.side is ZoneSide.DEMAND
        # Swap is charged per rollover the trade could cross. The horizon is
        # 80 bars, so this is what the trade risks paying rather than what it
        # certainly pays - a winner closing in ten bars pays none of it. Charged
        # in full because the alternative is to model the exit bar's clock, and
        # a cost model that flatters itself on timing is the thing this tool
        # exists to avoid.
        nights = (HORIZON * step) / 86_400 if costs else 0.0
        # SWAP IS A SIDE. Measured on the connected Exness terminal 2026-08-20:
        # XAUUSD swap_long is -541.4 points, 1.20bp a night at gold 4500, while
        # swap_short is exactly zero. Charging one figure to both sides billed
        # every short for a cost it never pays - and it leans the same way the
        # drawing does, because a demand zone is a long. A row with no
        # `swap_bp_short` was never read side by side, and its single figure
        # then applies to both, exactly as before.
        swap_bp = fees.get("swap_bp", 0.0)
        # The enum and not the string it happens to equal. `ZoneSide` is a
        # StrEnum today, so `== "supply"` is True - and would go silently False
        # the day it stops being one, charging every short the long's swap again
        # with nothing to show for it.
        if plan.side is ZoneSide.SUPPLY and "swap_bp_short" in fees:
            swap_bp = fees["swap_bp_short"]
        friction = (
            float(close[touch])
            * (fees["commission_bp"] + fees["slippage_bp"] + swap_bp * nights)
            / 10_000
        ) if costs else 0.0
        risk = plan.risk_per_unit + friction
        if risk <= 0:
            continue

        # Where a flat-by-rollover rule would force the exit. Modelled as a
        # LIMIT on the walk rather than a separate arm, so the two runs differ
        # in one rule and nothing else.
        last = touch + HORIZON
        if flat_by_rollover:
            # Off the clock, not off a 21:00 bar - gold has none, that hour is
            # the session break. The first bar at or after the next rollover
            # instant is where a flat-by-rollover rule would have exited.
            shift = ROLLOVER_HOUR_UTC * 3600
            cut = ((int(time[touch]) - shift) // 86_400 + 1) * 86_400 + shift
            for j in range(touch + 1, min(last + 1, len(close))):
                if int(time[j]) >= cut:
                    last = j
                    break

        result = None
        exit_index = last
        for i in range(touch, last + 1):
            hit_stop = low[i] <= plan.stop if long_side else high[i] >= plan.stop
            hit_target = (
                high[i] >= plan.target if long_side else low[i] <= plan.target
            )
            # Stop first when a single bar contains both. The data cannot order
            # them, and assuming the favourable one is how a backtest quietly
            # manufactures an edge.
            if hit_stop:
                result, exit_index = -1.0, i
                break
            if hit_target:
                result = (abs(plan.target - plan.entry) - friction) / risk
                exit_index = i
                break
        if result is None:
            # Still open at the cutoff, marked to market and charged the exit.
            exit_at = float(close[last])
            move = (exit_at - plan.entry) if long_side else (plan.entry - exit_at)
            result = (move - friction) / risk

        # Rollovers crossed, counted from the CLOCK rather than from the bars.
        # Looking for a bar stamped 21:00 UTC finds nothing: gold has no 21:00
        # bar at all, because that hour IS the daily session break - measured on
        # this series, every other hour has ~216 bars and 21:00 has zero. A
        # bar-presence test therefore reports "never charged", which is the
        # flattering answer and the wrong one, since the rollover happens inside
        # exactly that gap.
        #
        # Counted from the actual exit rather than the horizon, because a trade
        # stopped out in ten bars never paid for the other seventy.
        def _rollovers(t0: int, t1: int) -> int:
            shift = ROLLOVER_HOUR_UTC * 3600
            return (t1 - shift) // 86_400 - (t0 - shift) // 86_400

        nights_held = int(_rollovers(int(time[touch]), int(time[exit_index])))
        admin = float(close[touch]) * fees.get("admin_bp", 0.0) / 10_000
        if costs and admin and nights_held:
            result -= admin * nights_held / risk

        out.append({
            "skipped": False,
            "at": touch,
            "r": result,
            # Cost as a fraction of the trade's own risk. This is the number
            # that makes two instruments comparable at all: a bp constant is NOT
            # volatility-neutral, because cost tracks PRICE while R tracks the
            # STOP DISTANCE. The same 20bp buys 0.9 ATR of cost on BTC and 1.55
            # on PAXG, which is why the crypto arms lose on cost alone with no
            # change in the signal.
            "nights": nights_held,
            "cost_r": (friction + (spread or 0.0)) / risk if risk > 0 else 0.0,
            "won": result > 0,
            "cleared": zone.departure_atr >= 2.0,
            # The RAW value, not just which side of the shipped gate it
            # fell. tools/blind_gate.py needs it to choose a threshold on
            # one half of the series without ever seeing the other.
            "departure": zone.departure_atr,
        })
    return out


def report(rows: list[dict], title: str, out: dict) -> None:
    taken = [r for r in rows if not r["skipped"]]
    skipped = len(rows) - len(taken)
    if len(taken) < 50:
        print(f"  {title:<26}too few: {len(taken)} taken, {skipped} without a target")
        return

    r = np.array([x["r"] for x in taken])
    wins = float(np.mean([x["won"] for x in taken]))
    exp = float(r.mean())
    se = float(r.std(ddof=1) / np.sqrt(len(r)))
    t = exp / se if se > 0 else float("nan")
    cost_r = float(np.mean([x.get("cost_r", 0.0) for x in taken]))
    crossed = float(np.mean([x.get("nights", 0) > 0 for x in taken]))
    print(f"  {title:<26}{len(taken):>7}{skipped:>9}{wins:>9.1%}"
          f"{exp:>10.3f}{t:>8.2f}{cost_r:>9.3f}{crossed:>9.1%}")
    out[title] = {"n": len(taken), "skipped": skipped, "win_rate": wins,
                  "expectancy_r": exp, "t": t, "cost_r": cost_r,
                  "crossed_rollover": crossed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--flat", action="store_true",
                        help="close at the 21:00 UTC rollover, never hold across it")
    parser.add_argument("--broker", default="",
                        help=f"price a named broker: {sorted(BROKERS)}")
    parser.add_argument("--conservative", action="store_true",
                        help="the pessimistic sourced end of every cost")
    parser.add_argument("--json", type=str, default="")
    args = parser.parse_args()

    print(f"Loading {args.symbol} {args.interval}")
    candles = history.load(args.symbol, args.interval, args.bars)
    spreads = [c.spread for c in candles if c.spread is not None]
    print(f"  {len(candles)} bars, {len(spreads)} carrying a measured spread")
    if spreads:
        print(f"  spread min {min(spreads):.3f} mean "
              f"{sum(spreads) / len(spreads):.3f} max {max(spreads):.3f}")
    else:
        print("  NO SPREAD IN THIS FEED - the costed column below charges only "
              "commission and slippage, so it UNDERSTATES the real cost.")

    out: dict = {}
    for costs in (False, True):
        label = "WITH COSTS" if costs else "FRICTIONLESS"
        print(f"\n{'=' * 74}")
        print(f"{label}   {args.symbol} {args.interval}   horizon {HORIZON} bars")
        if costs:
            fees = schedule(args.symbol, args.conservative, args.broker)
            measured = any(c.spread is not None for c in candles)
            # The ROW is printed, not only the numbers. `_default` is a Binance
            # spot schedule at 20bp and gold's own row is 0.16bp, so a run that
            # has silently fallen through prints a cost 125 times too large and
            # nothing on screen says so. It happened here, and every expectancy
            # in that run was negative for a reason that had nothing to do with
            # the market.
            row = row_for(args.symbol)
            note = "" if row != "_default" else "  <- FALLBACK, not this instrument's own row"
            print(f"  cost row: {row}{note}")
            print(f"  commission {fees['commission_bp']}bp + slippage "
                  f"{fees['slippage_bp']}bp of notional, and spread "
                  + ("MEASURED per bar from the feed"
                     if measured else f"assumed at {fees['spread_bp']}bp"))
        print(f"{'=' * 74}")
        print(f"  {'':<26}{"n":>7}{"no target":>9}{"win":>9}{"exp R":>10}{"t":>8}{"cost R":>9}{"overnite":>9}")

        for name in ("supply_demand", "fvg", "order_block"):
            tag = label[:4].lower()
            rows = trades(name, candles, args.interval, costs, symbol=args.symbol, conservative=args.conservative,
                          broker=args.broker,
                          flat_by_rollover=args.flat)
            report(rows, f"{tag} {name}", out)
            # The departure gate is the one factor that passed walk-forward in
            # all three bracket geometries. Whether it survives costs is the
            # question this whole tool exists to answer.
            report([r for r in rows if r["cleared"]], f"{tag} {name} gate", out)
            report([r for r in rows if not r["cleared"]], f"{tag} {name} below", out)
            # And the placebo, right underneath, because a positive number with
            # no placebo beside it is not a result in this project.
            rng = np.random.default_rng(20260816)
            placebo: list[dict] = []
            for _ in range(PLACEBO_DRAWS):
                placebo.extend(
                    trades(name, candles, args.interval, costs, rng,
                           symbol=args.symbol, conservative=args.conservative,
                          broker=args.broker,
                          flat_by_rollover=args.flat))
            report(placebo, f"{tag} {name} PLACEBO", out)

            anchored: list[dict] = []
            rng2 = np.random.default_rng(20260817)
            for _ in range(PLACEBO_DRAWS):
                anchored.extend(
                    trades(name, candles, args.interval, costs, rng2,
                           anchored=True, symbol=args.symbol, conservative=args.conservative,
                          broker=args.broker,
                          flat_by_rollover=args.flat))
            report(anchored, f"{tag} {name} ANCHORED PLACEBO", out)

            # Split-half on time. An edge that lives in one half is a window
            # fit, and this project has caught that twice - once on a factor
            # that had already passed walk-forward 8 from 8.
            taken = [r for r in rows if not r["skipped"]]
            if len(taken) > 200:
                mid = np.median([r["at"] for r in taken])
                report([r for r in rows if r["skipped"] or r["at"] <= mid],
                       f"{tag} {name} first half", out)
                report([r for r in rows if r["skipped"] or r["at"] > mid],
                       f"{tag} {name} second half", out)

    # WALK-FORWARD, which is this project's own bar for switching anything on:
    # a gate is not lit unless the difference points the right way across
    # unseen time slices. Run only on the costed gate cohort, because that is
    # the only cell claiming anything.
    print(f"\n{'=' * 74}")
    print("  WALK-FORWARD, costed, supply_demand above the departure gate")
    print(f"{'=' * 74}")
    rows = [r for r in trades("supply_demand", candles, args.interval, True,
                              symbol=args.symbol, conservative=args.conservative,
                          broker=args.broker,
                          flat_by_rollover=args.flat)
            if not r["skipped"] and r["cleared"]]
    edges = np.linspace(0, len(candles), FOLDS + 1).astype(int)
    signs = []
    for k in range(FOLDS):
        fold = [r for r in rows if edges[k] <= r["at"] < edges[k + 1]]
        if len(fold) < 20:
            print(f"  fold {k + 1}: {len(fold)} trades, too few to read")
            continue
        exp = float(np.mean([r["r"] for r in fold]))
        signs.append(exp > 0)
        print(f"  fold {k + 1}: n={len(fold):>4}  exp R {exp:>+7.3f}")
    if signs:
        # Sign test. With k readable folds the floor a coin can reach is
        # 2 / 2^k, so a clean sweep of 8 is p=0.0078 - the same threshold every
        # other walk-forward here was read against.
        p = 2 / 2 ** len(signs) if all(signs) or not any(signs) else float("nan")
        print(f"\n  {sum(signs)} of {len(signs)} folds positive"
              + (f", sign test p={p:.4f}" if not np.isnan(p) else ""))
        out["walk_forward"] = {"folds": len(signs), "positive": sum(signs)}

    print(
        "\n  Read the two blocks against each other, not on their own. The gap"
        "\n  between them IS the cost, and it is the first time this project has"
        "\n  ever measured it. An edge that only exists in the upper block is not"
        "\n  an edge, it is a spread being ignored."
    )

    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1, default=float)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()

"""Mitigation Success Rate: what price does AFTER it touches a zone.

The calibration measures whether a zone HOLDS (stop not hit). This tool
measures what happens AFTER the touch: how far price moves in the favourable
direction before it either hits the target or the stop. The difference is
the difference between "the zone was drawn correctly" and "the zone was
tradeable."

WHAT IS MEASURED. For every zone that price touches, the maximum favourable
excursion (MFE) before either the stop (distal) or the target (reward ATR)
is reached. The result is a distribution: what fraction of touches reach
1R, 2R, and 3R before the stop is hit.

MFE is measured from the PROXIMAL, not from the entry, because the entry is a
decision and the proximal is a fact. A zone that is touched at the proximal
and moves 2R before stopping is a 2R opportunity regardless of whether the
trader entered at the proximal or waited for a retest.

USAGE:
    python -m tools.mitigation --symbol mt5:XAUUSD --interval 1h --bars 50000
    python -m tools.mitigation --matrix  # all instruments, 1h and 4h
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from app.detect import DETECTORS
from app.indicators import wilder_atr
from app.models import SupplyDemandParams, ZoneSide
from tools import history

HORIZON_BARS = 80
REWARDS = [0.5, 1.0, 2.0, 3.0]


def _mfe(
    zone, candles: list, atr: float, horizon: int = HORIZON_BARS
) -> dict[str, float | None]:
    """Max favourable excursion for one zone, in units of zone height (R).

    Returns the MFE at each reward level, and whether the stop was hit first.
    None means the zone was never touched within the horizon.
    """
    zone_height = zone.top - zone.bottom
    if zone_height <= 0:
        return {"touched": False, "stop_hit": None, "mfe_r": None}

    entry = zone.proximal
    stop = zone.distal
    is_demand = zone.side is ZoneSide.DEMAND

    # Find the first bar that touches the zone
    # The zone forms DURING the leg-out, so the touch can only happen AFTER
    # the leg-out has ended. `zone.time_to` is the BREAK time (or last bar),
    # not the formation time, so use the anatomy instead.
    formed_at = zone.anatomy.leg_out_to
    touch_idx = None
    for i, c in enumerate(candles):
        if i <= formed_at:
            continue
        if is_demand:
            if c.low <= entry:
                touch_idx = i
                break
        else:
            if c.high >= entry:
                touch_idx = i
                break

    if touch_idx is None:
        return {"touched": False, "stop_hit": None, "mfe_r": None}

    # Measure MFE from the touch bar onwards
    mfe = 0.0
    stop_hit = False
    end = min(touch_idx + horizon, len(candles))

    for i in range(touch_idx, end):
        c = candles[i]
        if is_demand:
            if c.low <= stop:
                stop_hit = True
                break
            mfe = max(mfe, c.high - entry)
        else:
            if c.high >= stop:
                stop_hit = True
                break
            mfe = max(mfe, entry - c.low)

    mfe_r = mfe / zone_height if zone_height > 0 else 0.0
    return {
        "touched": True,
        "stop_hit": stop_hit,
        "mfe_r": round(mfe_r, 3),
        "touch_bar": touch_idx,
    }


def report(
    symbol: str, interval: str, bars: int = 50000
) -> dict:
    """Mitigation success rate for one series."""
    candles = history.load(symbol, interval, bars)
    if not candles:
        return {"error": f"no bars for {symbol} {interval}"}

    high = np.array([c.high for c in candles], dtype=np.float64)
    low = np.array([c.low for c in candles], dtype=np.float64)
    close = np.array([c.close for c in candles], dtype=np.float64)
    params = SupplyDemandParams(max_zones_per_side=0)
    atr_arr = wilder_atr(high, low, close, params.atr_period)
    atr = float(atr_arr[-1])

    zones, _ = DETECTORS["supply_demand"](candles, params)

    touched = 0
    stop_hits = 0
    reached: dict[float, int] = {r: 0 for r in REWARDS}

    for zone in zones:
        result = _mfe(zone, candles, atr)
        if not result["touched"]:
            continue
        touched += 1
        if result["stop_hit"]:
            stop_hits += 1
        for r in REWARDS:
            if result["mfe_r"] is not None and result["mfe_r"] >= r:
                reached[r] += 1

    if touched == 0:
        return {
            "symbol": symbol, "interval": interval,
            "bars": len(candles), "zones": len(zones), "touched": 0,
        }

    return {
        "symbol": symbol,
        "interval": interval,
        "bars": len(candles),
        "zones": len(zones),
        "touched": touched,
        "stop_hit_pct": round(stop_hits / touched * 100, 1),
        "mitigation": {
            f"{r}R": f"{reached[r] / touched * 100:.1f}% ({reached[r]}/{touched})"
            for r in REWARDS
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=50000)
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args()

    if args.matrix:
        instruments = [
            "XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
            "GBPJPY", "AUDUSD", "USDCAD", "BTCUSD", "US30", "USOIL",
        ]
        timeframes = ["1h", "4h"]
        print(f"{'symbol':<8} {'tf':<4} {'bars':>6} {'zones':>6} {'touched':>8} "
              f"{'stop%':>6} {'0.5R':>8} {'1R':>8} {'2R':>8} {'3R':>8}")
        for sym in instruments:
            for tf in timeframes:
                r = report(f"mt5:{sym}", tf, args.bars)
                if "error" in r:
                    print(f"{sym:<8} {tf:<4}  {r['error']}")
                    continue
                if r["touched"] == 0:
                    print(f"{sym:<8} {tf:<4} {r.get('bars',0):>6} {r.get('zones',0):>6} "
                          f"{'0':>8}  {'—':>6} {'—':>8} {'—':>8} {'—':>8} {'—':>8}")
                    continue
                mit = r.get("mitigation", {})
                print(
                    f"{sym:<8} {tf:<4} {r['bars']:>6} {r['zones']:>6} "
                    f"{r['touched']:>8} {r['stop_hit_pct']:>5.1f}% "
                    f"{mit.get('0.5R', '—'):>8} {mit.get('1R', '—'):>8} "
                    f"{mit.get('2R', '—'):>8} {mit.get('3R', '—'):>8}"
                )
    else:
        r = report(args.symbol, args.interval, args.bars)
        for k, v in r.items():
            print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
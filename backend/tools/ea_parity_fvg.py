"""Parity: port referensi FVG (MQL5) vs detect_fvg numpy.

    python -m tools.ea_parity_fvg --bars 5000
"""

from __future__ import annotations

import argparse

import numpy as np

from app.detect.imbalance import detect_fvg
from app.indicators import wilder_atr
from app.models import ImbalanceParams, ZoneState
from tools import history

EPS = 1e-12

_STATE = {
    0: ZoneState.FRESH,
    1: ZoneState.TESTED,
    2: ZoneState.MITIGATED,
    3: ZoneState.BROKEN,
}


def lifecycle_ref(high, low, close, n, top, bottom, distal, is_demand, start, mitigation_pct):
    height = max(top - bottom, EPS)
    penetration = 0.0
    touches = 0
    break_index = -1
    was_inside = False
    for i in range(start, n):
        if close[i] < distal if is_demand else close[i] > distal:
            break_index = i
            break
        inside = low[i] <= top and high[i] >= bottom
        if inside:
            if not was_inside:
                touches += 1
            depth = (top - low[i]) if is_demand else (high[i] - bottom)
            penetration = max(penetration, min(1.0, depth / height))
        was_inside = inside
    if break_index != -1:
        return 3
    if penetration >= mitigation_pct:
        return 2
    if touches > 0:
        return 1
    return 0


def detect_fvg_ref(open_, high, low, close, time_, atr, p):
    n = len(close)
    zones = []
    if n < p["atr_period"] + 3:
        return zones
    for i in range(1, n - 1):
        first, third = i - 1, i + 1
        direction = 0
        if high[first] < low[third]:
            direction = 1
        elif low[first] > high[third]:
            direction = -1
        if direction == 0:
            continue
        up = direction == 1
        top, bottom = (low[third], high[first]) if up else (low[first], high[third])
        scale = atr[max(0, first - 1)]
        if scale <= EPS or (top - bottom) < p["min_gap_atr"] * scale:
            continue
        size = (top - bottom) / scale
        side = "demand" if up else "supply"
        is_demand = side == "demand"
        proximal = top if is_demand else bottom
        distal = bottom if is_demand else top
        born = third
        state = lifecycle_ref(high, low, close, n, top, bottom, distal, is_demand,
                              born + 1, p["mitigation_pct"])
        zones.append(dict(kind="FVG", side=side, top=top, bottom=bottom,
                          proximal=proximal, distal=distal,
                          departure_atr=size, state=state,
                          time_from=int(time_[first]), base_from=first))
    return zones


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=5000)
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--interval", default="1h")
    args = parser.parse_args()

    candles = history.load(args.symbol, args.interval, args.bars)
    open_ = np.array([c.open for c in candles])
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    time_ = np.array([c.time for c in candles], dtype=np.int64)

    params = ImbalanceParams(max_zones_per_side=0, show_broken=True)
    zones_np, _ = detect_fvg(candles, params)

    atr = wilder_atr(high, low, close, params.atr_period)
    p = dict(
        atr_period=params.atr_period,
        min_gap_atr=params.min_gap_atr,
        mitigation_pct=params.mitigation_pct,
    )
    zones_ref = detect_fvg_ref(open_, high, low, close, time_, atr, p)

    zones_np = sorted(zones_np, key=lambda z: (z.time_from, z.side.value))
    zones_ref = sorted(zones_ref, key=lambda z: (z["time_from"], z["side"]))

    print(f"numpy detector  : {len(zones_np)} fvg")
    print(f"reference port  : {len(zones_ref)} fvg")

    mismatches = 0
    n_checked = 0
    for zn, zr in zip(zones_np, zones_ref):
        n_checked += 1
        problems = []
        if zn.kind.value != zr["kind"]:
            problems.append(f"kind {zn.kind.value}!={zr['kind']}")
        if zn.side.value != zr["side"]:
            problems.append(f"side {zn.side.value}!={zr['side']}")
        if _STATE[zr["state"]] is not zn.state:
            problems.append(f"state {zn.state.name}!={zr['state']}")
        if zn.anatomy.base_from != zr["base_from"]:
            problems.append(f"base_from {zn.anatomy.base_from}!={zr['base_from']}")
        for name in ("top", "bottom", "proximal", "distal"):
            a = getattr(zn, name)
            b = zr[name]
            if abs(a - b) > 1e-9 * max(1.0, abs(a)):
                problems.append(f"{name} {a}!={b}")
        if abs(zn.departure_atr - zr["departure_atr"]) > 0.001:
            problems.append(f"departure_atr {zn.departure_atr}!={zr['departure_atr']}")
        if problems:
            mismatches += 1
            if mismatches <= 10:
                print(f"  MISMATCH #{mismatches} FVG-{zn.time_from}:")
                for prob in problems:
                    print(f"    {prob}")

    print(f"checked {n_checked} fvg, {mismatches} mismatch")
    print("PARITY OK" if mismatches == 0 and len(zones_np) == len(zones_ref)
          else "PARITY FAIL")


if __name__ == "__main__":
    main()

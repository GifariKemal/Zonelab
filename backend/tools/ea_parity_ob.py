"""Parity: port referensi order block (MQL5) vs detect_order_block numpy.

Membuktikan port loop eksplisit menghasilkan order block identik dengan detektor
numpy, di bar broker sungguhan. Gate hijau = hasil trade EA boleh dibandingkan.

    python -m tools.ea_parity_ob --bars 5000
"""

from __future__ import annotations

import argparse

import numpy as np

from app.detect.imbalance import detect_order_block
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
        return 3, break_index
    if penetration >= mitigation_pct:
        return 2, break_index
    if touches > 0:
        return 1, break_index
    return 0, break_index


def detect_order_block_ref(open_, high, low, close, time_, atr, p):
    n = len(close)
    zones = []
    if n < p["atr_period"] + p["displacement_bars"] + 2:
        return zones
    for i in range(1, n - p["displacement_bars"] - 1):
        scale = atr[max(0, i - 1)]
        if scale <= EPS:
            continue
        bearish = close[i] < open_[i]
        if bearish:
            move = (max(high[i+1:i+1+p["displacement_bars"]]) - close[i]) / scale
            side = "demand"
        elif close[i] > open_[i]:
            move = (close[i] - min(low[i+1:i+1+p["displacement_bars"]])) / scale
            side = "supply"
        else:
            continue
        if move < p["displacement_atr"]:
            continue
        nxt = i + 1
        turned = (close[nxt] > open_[nxt]) if bearish else (close[nxt] < open_[nxt])
        if not turned:
            continue
        born = i + p["displacement_bars"]
        top, bottom = high[i], low[i]
        if top - bottom <= EPS:
            continue
        is_demand = side == "demand"
        proximal = top if is_demand else bottom
        distal = bottom if is_demand else top
        state, break_idx = lifecycle_ref(
            high, low, close, n, top, bottom, distal, is_demand,
            born + 1, p["mitigation_pct"]
        )
        zones.append(dict(kind="OB", side=side, top=top, bottom=bottom,
                          proximal=proximal, distal=distal,
                          departure_atr=move, state=state,
                          time_from=int(time_[i]), base_from=i))
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
    zones_np, _ = detect_order_block(candles, params)

    from app.indicators import wilder_atr
    atr = wilder_atr(high, low, close, params.atr_period)
    p = dict(
        atr_period=params.atr_period,
        displacement_atr=params.displacement_atr,
        displacement_bars=params.displacement_bars,
        mitigation_pct=params.mitigation_pct,
    )
    zones_ref = detect_order_block_ref(open_, high, low, close, time_, atr, p)

    zones_np = sorted(zones_np, key=lambda z: (z.time_from, z.side.value))
    zones_ref = sorted(zones_ref, key=lambda z: (z["time_from"], z["side"]))

    print(f"numpy detector  : {len(zones_np)} order block")
    print(f"reference port  : {len(zones_ref)} order block")

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
                print(f"  MISMATCH #{mismatches} OB-{zn.time_from}:")
                for prob in problems:
                    print(f"    {prob}")

    print(f"checked {n_checked} order block, {mismatches} mismatch")
    print("PARITY OK" if mismatches == 0 and len(zones_np) == len(zones_ref)
          else "PARITY FAIL")


if __name__ == "__main__":
    main()

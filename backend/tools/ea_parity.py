"""Parity: port referensi MQL5 vs detektor numpy yang dikirim.

Membuktikan algoritma loop eksplisit yang diimplementasikan EA MQL5 menghasilkan
zona identik dengan detektor numpy, di bar broker sungguhan. Ini gate yang harus
hijau sebelum hasil trade EA boleh dibandingkan.

    python -m tools.ea_parity --bars 5000
"""

from __future__ import annotations

import argparse

import numpy as np

from app.detect.supply_demand import detect
from app.models import SupplyDemandParams, ZoneState
from tools import history

EPS = 1e-12

# int state -> ZoneState, cocok dengan #define di SupplyDemandDetector.mqh.
_STATE = {
    0: ZoneState.FRESH,
    1: ZoneState.TESTED,
    2: ZoneState.MITIGATED,
    3: ZoneState.BROKEN,
}


def _tr(h, l, pc):
    return max(h - l, abs(h - pc), abs(l - pc))


def wilder_atr_ref(high, low, close, period):
    n = len(close)
    atr = np.empty(n)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = _tr(high[i], low[i], close[i - 1])
    if n <= period:
        m = tr.mean()
        atr[:] = m
        return atr
    seed = tr[:period].mean()
    atr[:period] = seed
    prev = seed
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        atr[i] = prev
    return atr


def flat_atr_ref(high, low, close, n, period, at):
    lo = at - period + 1
    if period <= 0 or lo < 1 or at >= n or at < 0:
        return None
    s = 0.0
    for j in range(lo, at + 1):
        s += _tr(high[j], low[j], close[j - 1])
    return s / period


def classify_ref(open_, high, low, close, atr, body_ratio_min, range_atr_min):
    n = len(close)
    labels = np.zeros(n, dtype=int)
    for i in range(n):
        rng = max(high[i] - low[i], EPS)
        body = close[i] - open_[i]
        body_ratio = abs(body) / rng
        prior_atr = atr[0] if i == 0 else atr[i - 1]
        exciting = (body_ratio >= body_ratio_min) and (rng >= range_atr_min * prior_atr)
        labels[i] = (1 if body > 0 else -1) if exciting else 0
    return labels


def runs_ref(labels):
    n = len(labels)
    out = []
    start = 0
    for i in range(1, n):
        if labels[i] != labels[start]:
            out.append((int(labels[start]), start, i - 1))
            start = i
    out.append((int(labels[start]), start, n - 1))
    return out


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


_FORMATION = {(-1, 1): ("DBR", "demand"), (1, 1): ("RBR", "demand"),
              (1, -1): ("RBD", "supply"), (-1, -1): ("DBD", "supply")}


def detect_ref(open_, high, low, close, time_, atr, p):
    n = len(close)
    zones = []
    if n < p["atr_period"] + 3:
        return zones
    labels = classify_ref(open_, high, low, close, atr,
                          p["impulse_body_ratio"], p["impulse_atr"])
    runs = runs_ref(labels)
    for k in range(len(runs) - 2):
        leg_in, base_run, leg_out = runs[k], runs[k + 1], runs[k + 2]
        if leg_in[0] == 0 or base_run[0] != 0 or leg_out[0] == 0:
            continue
        kind, side = _FORMATION[(leg_in[0], leg_out[0])]
        base_to = base_run[2]
        base_from = max(base_run[1], base_to - p["base_max_bars"] + 1)
        atr_base = atr[max(0, base_from - 1)]
        if atr_base <= EPS:
            continue
        wick_hi, wick_lo = high[base_from], low[base_from]
        for i in range(base_from + 1, base_to + 1):
            wick_hi = max(wick_hi, high[i])
            wick_lo = min(wick_lo, low[i])
        if p["proximal_basis"] == "body":
            body_hi = max(open_[base_from], close[base_from])
            body_lo = min(open_[base_from], close[base_from])
            for i in range(base_from + 1, base_to + 1):
                body_hi = max(body_hi, open_[i], close[i])
                body_lo = min(body_lo, open_[i], close[i])
        else:
            body_hi, body_lo = wick_hi, wick_lo
        is_demand = side == "demand"
        top, bottom = (body_hi, wick_lo) if is_demand else (wick_hi, body_lo)
        floor_scale = flat_atr_ref(high, low, close, n, p["atr_period"], base_from)
        floor = p["zone_min_atr"] * floor_scale if floor_scale is not None else 0.0
        height = top - bottom
        if height < floor:
            if is_demand:
                top = bottom + floor
            else:
                bottom = top - floor
            height = top - bottom
        if height <= EPS:
            continue
        if height > p["base_max_atr"] * atr_base:
            continue
        proximal = top if is_demand else bottom
        distal = bottom if is_demand else top
        drift = abs(close[base_to] - open_[base_from]) / height
        if drift > p["max_base_drift"]:
            continue
        leg_out_from, leg_out_to = leg_out[1], leg_out[2]
        first_touch = None
        for j in range(leg_out_to + 1, n):
            if low[j] <= top and high[j] >= bottom:
                first_touch = j
                break
        look_to = min(n, leg_out_from + p["departure_lookahead"])
        if first_touch is not None:
            look_to = max(leg_out_from + 1, min(look_to, first_touch))
        if is_demand:
            excursion = max(high[leg_out_from:look_to]) - proximal
        else:
            excursion = proximal - min(low[leg_out_from:look_to])
        departure_atr = max(0.0, excursion) / atr_base
        profit_margin = max(0.0, excursion) / height
        if departure_atr < p["departure_min_atr"]:
            continue
        if profit_margin < p["min_profit_margin"]:
            continue
        state = lifecycle_ref(high, low, close, n, top, bottom, distal, is_demand,
                              leg_out_to + 1, p["mitigation_pct"])
        zones.append(dict(kind=kind, side=side, top=top, bottom=bottom,
                          proximal=proximal, distal=distal,
                          departure_atr=departure_atr, state=state,
                          time_from=int(time_[base_from]), base_from=base_from))
    return zones


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=5000)
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--interval", default="15m")
    args = parser.parse_args()

    candles = history.load(args.symbol, args.interval, args.bars)
    open_ = np.array([c.open for c in candles])
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    time_ = np.array([c.time for c in candles], dtype=np.int64)

    params = SupplyDemandParams(
        merge_overlap_pct=1.0, max_zones_per_side=0, show_broken=True,
    )
    zones_np, _ = detect(candles, params)

    p = dict(
        atr_period=params.atr_period,
        impulse_body_ratio=params.impulse_body_ratio,
        impulse_atr=params.impulse_atr,
        base_max_bars=params.base_max_bars,
        base_max_atr=params.base_max_atr,
        departure_min_atr=params.departure_min_atr,
        departure_lookahead=params.departure_lookahead,
        proximal_basis=params.proximal_basis,
        min_profit_margin=params.min_profit_margin,
        zone_min_atr=params.zone_min_atr,
        max_base_drift=params.max_base_drift,
        mitigation_pct=params.mitigation_pct,
    )
    atr = wilder_atr_ref(high, low, close, p["atr_period"])
    zones_ref = detect_ref(open_, high, low, close, time_, atr, p)

    zones_np = sorted(zones_np, key=lambda z: (z.time_from, z.kind.value))
    zones_ref = sorted(zones_ref, key=lambda z: (z["time_from"], z["kind"]))

    print(f"numpy detector  : {len(zones_np)} zona")
    print(f"reference port  : {len(zones_ref)} zona")

    if len(zones_np) != len(zones_ref):
        print("COUNT MISMATCH")
        # report anyway

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
                print(f"  MISMATCH #{mismatches} {zn.kind.value}-{zn.time_from}:")
                for prob in problems:
                    print(f"    {prob}")

    print(f"checked {n_checked} zona, {mismatches} mismatch")
    print("PARITY OK" if mismatches == 0 and len(zones_np) == len(zones_ref)
          else "PARITY FAIL")


if __name__ == "__main__":
    main()

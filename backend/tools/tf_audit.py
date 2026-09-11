"""Does each layer's geometry change when the chart timeframe changes?

    .\\.venv\\Scripts\\python.exe -m tools.tf_audit [SYMBOL] [BARS] [OUT.json]

Written for one complaint: a drawing switched on at 1h appeared to follow the
reader to M1, M15 and H4. That splits into two questions, and only one of them
is about the engine - whether the BOXES at M15 are M15's own, or 1h's reprinted.
This answers that one. The other half, whether the SWITCH follows the reader, is
a frontend question and lives in `frontend/e2e/timeframe-layers.mjs`.

METHOD. One layer at a time, the same symbol and bar count, EVERY interval the
app offers - read off `/api/config`, never a list typed here. Every
price-bearing number in `drawing` is collected, rounded and hashed. Timestamps
are dropped before hashing, because a bar-anchored shape MUST move in time when
the bar length changes and that is not the question; the question is whether the
PRICES are the same set. A layer that hashes the same on 5m and on 1d is drawing
something the timeframe does not touch.

THE CONTROL IS NOT OPTIONAL. MT5 is a live feed. If the same request twice at
one interval hashes differently, then "the hash changed between 5m and 1d" says
nothing at all - it would just be the tape moving. So the control runs FIRST and
the sweep refuses to report unless it is clean.

`--all` sweeps EVERY symbol the registry carries, one JSON per symbol under
`docs/tf_audit/`, and SKIPS a symbol whose file already exists. That is not a
convenience: the full sweep is thousands of draw calls over hours, and a run
that dies at symbol nineteen must not start again from symbol one. Each symbol
is priced through whichever provider carries it, so the eight yahoo-only
symbols are swept too - and a provider that refuses is recorded per interval
rather than taking the run down.

Needs the API up on 8100. Results as of 11 September 2026 are written up in
`docs/TIMEFRAME-AUDIT.md`: 26 symbols x 24 layers x 8 intervals, 4,992 measured
cells, the control stable everywhere, and ZERO layers drawing the same price set
across intervals. The sweep also turned up a real defect - see the SSMT guard in
`app/main.py` and `tests/test_api_boundary.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request

API = "http://127.0.0.1:8100"
#: EVERY interval the app offers, read off `/api/config` at startup rather than
#: typed here. The first version of this tool listed six by hand and silently
#: skipped 1m and 1w - the two ends of the range, which are exactly where a
#: timeframe bug would show first. A default that omits part of the question is
#: worse than one that is obviously partial, because the report reads complete.
INTERVALS: tuple[str, ...] = ()

#: What the five quiet layers need before they draw ANYTHING. Same table as
#: `frontend/e2e/wiring.mjs`, and the reason it exists here too: `session`,
#: `dfr` and `ssmt` draw nothing with pure defaults ON PURPOSE, `psp` reads the
#: SSMT events, and a layer that is empty at every interval cannot be judged
#: either way. Without these, five of twenty-four layers were reported as
#: "empty on every tf" and quietly went unmeasured.
MIN_PARAMS: dict[str, dict] = {
    "session": {"session": {"quarters": ["day"], "true_opens": ["day"]}},
    "dfr": {"dfr": {"degrees": ["day"]}},
    "ssmt": {"checklist": {"ssmt_symbols": ["XAGUSD"], "ssmt_degrees": ["day"]}},
    "psp": {"checklist": {"ssmt_symbols": ["XAGUSD"], "ssmt_degrees": ["day"]}},
    # A DIVERGENCE NEEDS A SECOND INSTRUMENT, so the partner above cannot be the
    # chart. Sweeping XAGUSD with this table asked silver to diverge from silver
    # and the API answered 500 twice in the control - a real defect, now guarded
    # in `_draw_ssmt` and covered by `tests/test_api_boundary.py`. The sweep still
    # has to pick a different partner or it measures the guard instead of SSMT.
    # The checklist is a PANEL, not a shape on the chart, so it has no drawing
    # to fingerprint at any interval. Named here so its emptiness is a stated
    # fact rather than an unmeasured one.
    "checklist": {},
}

#: Keys whose value is a clock reading rather than a price. A bar-anchored shape
#: is SUPPOSED to move in time when the bar length changes, so leaving these in
#: would make every layer look timeframe-aware for the wrong reason.
TIME_KEYS = frozenset(
    {
        "time", "at", "start", "end", "from", "to", "opened_at", "closed_at",
        "knowable_at", "ssmt_at", "low_at", "high_at", "crowded_at", "swept_at",
        "broken_at", "tested_at", "created_at", "born_at", "confirmed_at",
        "bars", "index", "i", "bar", "bars_after_ssmt", "age_bars",
    }
)


def prices(node: object, out: list[float], key: str | None = None) -> None:
    """Every price-bearing number under `node`, in no particular order."""
    if isinstance(node, dict):
        for k, v in node.items():
            prices(v, out, k)
    elif isinstance(node, list):
        for v in node:
            prices(v, out, key)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        if key in TIME_KEYS:
            return
        # A unix timestamp that slipped through under a key this table has never
        # heard of. Cheaper than keeping the key list perfect, and one-sided: no
        # price this engine draws is above a billion.
        if isinstance(node, int) and node > 1_000_000_000:
            return
        out.append(round(float(node), 5))


def fingerprint(drawing: dict) -> str:
    vals: list[float] = []
    prices(drawing, vals)
    vals.sort()
    return hashlib.sha1(json.dumps(vals).encode()).hexdigest()[:12]


#: Stand-in partner for the one symbol that IS the default partner. Gold, because
#: the default partner is silver and the pair is the one this repo measures most.
SELF_PARTNER = "XAUUSD"


def request_for(symbol: str, interval: str, bars: int, provider: str, lid: str) -> dict:
    """The draw request for one layer, with the minimum params it needs."""
    body = {
        "symbol": symbol, "interval": interval, "bars": bars,
        "provider": provider, "layers": [lid],
    }
    extra = MIN_PARAMS.get(lid, {})
    partners = extra.get("checklist", {}).get("ssmt_symbols")
    if partners and symbol in partners:
        extra = {**extra, "checklist": {**extra["checklist"], "ssmt_symbols": [SELF_PARTNER]}}
    body.update(extra)
    return body


def post(body: dict) -> dict:
    req = urllib.request.Request(
        f"{API}/api/draw",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def carrier(cfg: dict, symbol: str) -> str | None:
    """The provider this sweep should price `symbol` through.

    The registry's default when it carries the symbol and is up, otherwise the
    first available one that does - the same rule the dashboard's own `usable`
    memo applies, so the sweep measures what a reader would actually see.
    """
    row = next((s for s in cfg["symbols"] if s["id"] == symbol), None)
    if row is None:
        return None
    carriers = row["providers"]
    up = {p["id"] for p in cfg["providers"] if p["available"]}
    if cfg["default_provider"] in carriers and cfg["default_provider"] in up:
        return cfg["default_provider"]
    return next(
        (p for p in carriers if p in up and p != "synthetic"),
        next((p for p in carriers if p in up), None),
    )


def measure(response: dict, lid: str) -> dict:
    """What to fingerprint for this layer, and how many objects it produced.

    `checklist` IS THE EXCEPTION AND IT IS NAMED HERE. It is a panel rather than
    a shape, so it contributes nothing to `drawing` and the first version of this
    tool reported it as "empty on every tf" - which reads as measured and is not.
    Its report block is fingerprinted instead, so the layer gets a verdict like
    every other one.
    """
    if lid == "checklist":
        block = response.get("checklist")
        return {
            "shapes": {"checklist": 1} if block else {},
            "hash": fingerprint(block or {}),
        }
    drawing = response["drawing"]
    shapes = {
        k: (len(v) if isinstance(v, list) else 1)
        for k, v in drawing.items()
        if (v if isinstance(v, list) else v is not None)
    }
    return {"shapes": shapes, "hash": fingerprint(drawing)}


def sweep_symbol(
    symbol: str, bars: int, provider: str, layer_ids: list[str], out_path: str
) -> int:
    """Control then sweep, for one symbol. Returns a process exit code."""
    print(f"\n=== {symbol} through {provider}")
    print("control: the same request twice, at 15m")
    drifted = []
    for lid in layer_ids:
        try:
            two = [
                measure(post(request_for(symbol, "15m", bars, provider, lid)), lid)["hash"]
                for _ in range(2)
            ]
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            print(f"  {lid:16s} UNREACHABLE {str(exc)[:80]}")
            drifted.append(lid)
            continue
        if two[0] != two[1]:
            drifted.append(lid)
    print(f"  {len(layer_ids) - len(drifted)} stable, {len(drifted)} drifted")
    if drifted:
        print(
            "  BLOCKER: the fingerprint moves when nothing changed, so nothing "
            f"below would mean anything. Drifted: {', '.join(drifted)}"
        )
        return 1

    print(f"sweep: one layer at a time, {len(INTERVALS)} intervals")
    rows: dict[str, dict] = {}
    for lid in layer_ids:
        per_tf: dict[str, dict] = {}
        for tf in INTERVALS:
            try:
                per_tf[tf] = measure(
                    post(request_for(symbol, tf, bars, provider, lid)), lid
                )
            except Exception as exc:  # noqa: BLE001 - reported, never raised
                per_tf[tf] = {"error": str(exc)[:160]}
        hashes = {v["hash"] for v in per_tf.values() if "hash" in v}
        empty = all(not v.get("shapes") for v in per_tf.values() if "shapes" in v)
        rows[lid] = {
            "per_tf": per_tf,
            "drew_nothing": empty,
            "identical_across_tf": len(hashes) == 1 and not empty,
        }
        verdict = (
            "empty on every tf" if empty
            else "SAME ON EVERY TF" if len(hashes) == 1
            else "follows the timeframe"
        )
        counts = " ".join(
            f"{tf}:{sum(v.get('shapes', {}).values())}" for tf, v in per_tf.items()
        )
        print(f"  {lid:16s} {verdict:22s} {counts}")

    same = [lid for lid, r in rows.items() if r["identical_across_tf"]]
    print(
        f"  {len(same)} layer(s) draw the same prices on every interval"
        + (f": {', '.join(same)}" if same else "")
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"symbol": symbol, "bars": bars, "provider": provider,
             "intervals": list(INTERVALS), "layers": rows},
            f,
            indent=1,
        )
    print(f"  wrote {out_path}")
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--all"]
    sweep_all = "--all" in sys.argv
    symbol = args[0] if args and not sweep_all else "XAUUSD"
    bars = int(args[1]) if len(args) > 1 else (int(args[0]) if sweep_all and args else 500)
    # `../docs`, because tools in this repo are run from `backend/` and the
    # docs directory is at the root - the same path `tools.dfr_outcomes` writes.
    # ONE FILE PER SYMBOL, in the same directory `--all` fills, so a single
    # symbol re-measured by hand lands where the roll-up will find it instead of
    # beside it under a second name.
    out_path = args[2] if len(args) > 2 else f"../docs/tf_audit/{symbol}.json"

    with urllib.request.urlopen(f"{API}/api/config", timeout=30) as r:
        cfg = json.load(r)
    layer_ids = [layer["id"] for layer in cfg["layers"]]
    global INTERVALS
    INTERVALS = tuple(cfg["intervals"])

    if not sweep_all:
        os.makedirs("../docs/tf_audit", exist_ok=True)
        provider = carrier(cfg, symbol) or cfg["default_provider"]
        print(
            f"provider={provider} symbol={symbol} bars={bars} "
            f"layers={len(layer_ids)} intervals={','.join(INTERVALS)}"
        )
        return sweep_symbol(symbol, bars, provider, layer_ids, out_path)

    # ---- every symbol the registry carries, one file each -------------------
    out_dir = "../docs/tf_audit"
    os.makedirs(out_dir, exist_ok=True)
    symbols = [row["id"] for row in cfg["symbols"]]
    print(
        f"--all: {len(symbols)} symbols, {len(layer_ids)} layers, "
        f"{len(INTERVALS)} intervals, bars={bars}"
    )
    done, skipped, blocked = [], [], []
    for sym in symbols:
        path = f"{out_dir}/{sym}.json"
        if os.path.exists(path):
            skipped.append(sym)
            print(f"\n=== {sym} already measured, skipping {path}")
            continue
        provider = carrier(cfg, sym)
        if provider is None:
            blocked.append((sym, "no available provider carries it"))
            print(f"\n=== {sym} SKIPPED: no available provider carries it")
            continue
        if sweep_symbol(sym, bars, provider, layer_ids, path) == 0:
            done.append(sym)
        else:
            blocked.append((sym, "control drifted"))

    print(f"\n{len(done)} swept, {len(skipped)} already had a file, {len(blocked)} blocked")
    for sym, why in blocked:
        print(f"  {sym}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""White's Reality Check and Hansen's SPA over the columns already pre-registered.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.reality_check \
        --symbol mt5:XAUUSD --intervals 1h,15m > ../docs/reality_check.json

WHY THIS EXISTS. Every pre-registration in this repo corrects for multiplicity
with BONFERRONI (`docs/PRAREGISTRASI-KONDISI.md` section 4, and seven other
files). Bonferroni is conservative, so nothing it rejected can be a false
positive and every null already recorded still stands. What it cannot do is
account for CORRELATION between the rules, and the rules here are heavily
correlated by construction: `killzone` and `hour_utc` read the same clock,
`quarter_day` and `weekday` read the same calendar, `dfr_band` and `range_band`
read the same position. Under dependence the effective number of independent
tests is smaller than the group count, so the critical |t| of 3.30 to 3.45 that
was actually used is stricter than the data-dependent one.

WHAT THIS TOOL ANSWERS, and it is one question: is there a rule that passes
under the correction that accounts for the dependence, and was rejected only
because Bonferroni over-corrected. `docs/CALIBRATION.md` already CITES Sullivan,
Timmermann and White (JF 1999) and Bajgrowicz and Scaillet (JFE 2012) as prose
support, and never ran the test those papers are about. This closes that gap.

HOW A RULE IS DEFINED, and it matches `tools/conditioned.py` exactly rather than
inventing a second definition. A rule is one (column, value) bucket with n >= 30
on both arms, and its payoff is the bucket's advantage OVER THE REST of the
population, not over zero. Testing against zero is the bug that run one of
`conditioned.py` had; repeating it here would make every large bucket look like
a discovery again. The per-observation series is

    f[t] = +r[t] * n / n_group     when the trade is in the bucket
    f[t] = -r[t] * n / n_rest      when it is not

whose sample mean IS the Welch delta that `conditioned.py` prints. So the
universe below is the same universe, seen one trade at a time instead of one
summary at a time.

BOTH SIGNS ARE IN THE UNIVERSE. RC and SPA are one-sided by construction: they
ask whether the BEST rule beats the benchmark. The pre-registration is
two-sided (`|t|`), so each bucket enters twice, once as stated and once negated.
Dropping the negated half would test a smaller family than the one that was
actually searched, which is the same error the whole method exists to prevent.

WHY BOTH RC AND SPA. White's RC takes the max over raw means, so a bucket at
the n = 30 floor carries a scale factor of about 31 and can dominate the maximum
on variance alone. Hansen's SPA studentizes and drops rules too far below zero
to matter, which is exactly the correction for that. Both are reported; SPA is
the one to read.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from math import log, sqrt
from pathlib import Path

import numpy as np

from app.costs import BROKERS
from tools import history
from tools.conditioned import (
    COLUMNS,
    CORRELATION_COLUMNS,
    ICT_COLUMNS,
    MIN_GROUP,
    ORPHAN_COLUMNS,
    _critical_t,
    rows_with_state,
)
from tools.true_open_matrix import REGISTERED

ALL_COLUMNS = COLUMNS + ICT_COLUMNS + ORPHAN_COLUMNS + CORRELATION_COLUMNS

#: Bootstrap replications. 10,000 puts the Monte Carlo standard error on a
#: p-value near 0.05 at 0.002, which is a tenth of the distance to the next
#: decision, so the answer does not depend on the seed.
REPS = 10_000

#: Nominal level, the same 0.05 every pre-registration in this repo starts from.
ALPHA = 0.05


def block_length(n: int) -> int:
    """Mean block length for the stationary bootstrap, from `n` alone.

    Politis and Romano's stationary bootstrap draws geometric blocks with mean
    `b`, and the rate that makes it consistent for the mean is `b ~ n^(1/3)`.
    At n = 953 that is 9.8, so 10. The choice is made from the SAMPLE SIZE and
    nothing else, before a single p-value exists, and `--blocks` sweeps it so
    the reader can see whether it mattered at all.
    """
    return max(1, round(n ** (1 / 3)))


def sb_indices(n: int, mean_block: int, rng: np.random.Generator) -> np.ndarray:
    """One stationary-bootstrap resample of `range(n)`, wrapping at the end.

    Geometric block lengths with parameter `1 / mean_block`, uniform starts, and
    the series treated as circular - that is the Politis-Romano construction as
    published. Circular wrapping is what keeps every observation equally likely
    to be drawn, which a plain moving-block bootstrap does not do at the edges.
    """
    p = 1.0 / mean_block
    fresh = rng.random(n) < p
    fresh[0] = True
    starts = np.flatnonzero(fresh)
    seg = np.searchsorted(starts, np.arange(n), side="right") - 1
    base = rng.integers(0, n, size=len(starts))
    return (base[seg] + (np.arange(n) - starts[seg])) % n


def bootstrap_means(
    f: np.ndarray, reps: int, mean_block: int, seed: int, chunk: int = 500
) -> np.ndarray:
    """`reps` stationary-bootstrap means of every row of `f`, shape (K, reps).

    THE RESAMPLE IS SHARED ACROSS RULES and that is the whole point of the
    method: RC and SPA ask about the maximum over a correlated family, so every
    rule has to be evaluated on the SAME resampled path. Resampling each rule
    independently would destroy the correlation this test exists to exploit and
    hand back Bonferroni's answer wearing a bootstrap's name.

    Counted rather than gathered: a resample's mean is `f @ counts / n`, so the
    n-vector of multiplicities is all that has to be built per replication.
    """
    n = f.shape[1]
    rng = np.random.default_rng(seed)
    out = np.empty((f.shape[0], reps))
    for start in range(0, reps, chunk):
        wide = min(chunk, reps - start)
        counts = np.empty((n, wide))
        for j in range(wide):
            idx = sb_indices(n, mean_block, rng)
            counts[:, j] = np.bincount(idx, minlength=n)
        out[:, start : start + wide] = f @ counts / n
    return out


def universe(rows: list[dict]) -> tuple[np.ndarray, list[dict]]:
    """The payoff matrix and the rule labels, one row of `f` per rule.

    Rows arrive from `rows_with_state` in detection order, which is NOT time
    order - `docs/PRAREGISTRASI-KONDISI.md` measured 169 inversions out of 534
    adjacent pairs. A block bootstrap over a mis-ordered series would resample
    blocks that are not contiguous in time, so the sort here is a correctness
    requirement and not tidiness.
    """
    rows = sorted(rows, key=lambda r: r["at"])
    n = len(rows)
    r = np.array([row["r"] for row in rows], dtype=np.float64)
    series, labels = [], []
    for column in ALL_COLUMNS:
        values = {row["state"].get(column) for row in rows}
        for value in sorted(values, key=lambda v: (v is None, str(v))):
            member = np.array(
                [row["state"].get(column) == value for row in rows], dtype=bool
            )
            n_group = int(member.sum())
            if n_group < MIN_GROUP or n - n_group < MIN_GROUP:
                continue
            weight = np.where(member, n / n_group, -n / (n - n_group))
            payoff = weight * r
            # The Welch `t` of `conditioned.py`, carried along so the two tools
            # can be read side by side. It is a label, not an input to RC or SPA.
            inside, outside = r[member], r[~member]
            se = sqrt(
                inside.var(ddof=1) / n_group + outside.var(ddof=1) / (n - n_group)
            )
            t = (inside.mean() - outside.mean()) / se if se > 0 else float("nan")
            for sign, direction in ((1.0, "above"), (-1.0, "below")):
                series.append(sign * payoff)
                labels.append(
                    {
                        "column": column,
                        "value": str(value),
                        "direction": direction,
                        "n_group": n_group,
                        "delta": float(sign * payoff.mean()),
                        "exp_r_group": float(inside.mean()),
                        "welch_t": float(sign * t),
                    }
                )
    return np.array(series), labels


def reality_check(f: np.ndarray, reps: int, mean_block: int, seed: int) -> dict:
    """RC, SPA and the stepwise pass, all from one shared bootstrap.

    RC is White (2000): the max over raw means, with the bootstrap distribution
    recentred at the observed means so it describes the least favourable null.

    SPA is Hansen (2005): studentised, and with rules whose observed mean is far
    enough below zero dropped from the recentring. The three variants differ only
    in that threshold. `spa_c` is the consistent one and the number to read;
    `spa_u` never rejects less than RC and `spa_l` never rejects more, so a
    reading that falls between them is a reading that does not depend on the
    choice.
    """
    n = f.shape[1]
    means = f.mean(axis=1)
    boot = bootstrap_means(f, reps, mean_block, seed)
    centred = sqrt(n) * (boot - means[:, None])
    omega = centred.std(axis=1, ddof=1)
    omega[omega <= 0] = np.inf  # a rule with no variation cannot be the maximum

    stat_rc = sqrt(n) * means.max()
    p_rc = float((1 + (centred.max(axis=0) >= stat_rc).sum()) / (reps + 1))

    studentised = sqrt(n) * means / omega
    stat_spa = float(max(studentised.max(), 0.0))
    # Hansen's threshold: a rule more than sqrt(2 log log n) studentised units
    # below zero cannot matter to the maximum and is recentred to zero.
    cutoff = -sqrt(2 * log(log(n))) if n > 3 else 0.0
    keep = {
        "spa_c": studentised >= cutoff,
        "spa_l": means >= 0,
        "spa_u": np.ones_like(means, dtype=bool),
    }
    z = centred / omega[:, None]
    spa = {}
    for name, mask in keep.items():
        null = z + np.where(mask, 0.0, studentised)[:, None]
        spa[name] = float(
            (1 + (null.max(axis=0) >= stat_spa).sum()) / (reps + 1)
        )

    # Romano-Wolf StepM on the studentised statistics, same bootstrap draws.
    remaining = np.ones(f.shape[0], dtype=bool)
    rejected: list[int] = []
    while remaining.any():
        quantile = np.quantile(z[remaining].max(axis=0), 1 - ALPHA)
        step = np.flatnonzero(remaining & (studentised > quantile))
        if step.size == 0:
            break
        rejected.extend(int(i) for i in step)
        remaining[step] = False

    return {
        "n_trades": n,
        "n_rules": int(f.shape[0]),
        "block_length": mean_block,
        "reps": reps,
        "best_delta": float(means.max()),
        "rc_statistic": float(stat_rc),
        "rc_p": p_rc,
        "spa_statistic": stat_spa,
        "spa_p_consistent": spa["spa_c"],
        "spa_p_lower": spa["spa_l"],
        "spa_p_upper": spa["spa_u"],
        "stepm_rejected": rejected,
        "studentised": studentised,
        "means": means,
        "omega": omega,
    }


def acf(x: np.ndarray, lags: int = 10) -> list[float]:
    """Sample autocorrelation of the trade returns, lag 1 to `lags`.

    Reported because the block length only matters if there IS serial dependence
    to preserve. If these are all inside the +/- 2/sqrt(n) band then the block
    bootstrap and the iid bootstrap are answering the same question, and the
    sweep in `--blocks` will show it.
    """
    x = x - x.mean()
    denom = float(x @ x)
    return [float(x[k:] @ x[:-k] / denom) for k in range(1, lags + 1)]


def cell(symbol: str, interval: str, bars: int, flat: bool, cache: Path | None) -> dict:
    """One instrument-timeframe cell, with the expensive rig run cached to disk.

    The cache holds the OUTPUT of `rows_with_state`, not history: rebuilding the
    trade population takes about twenty minutes and none of the statistics below
    can change it. Delete the file to re-measure.
    """
    key = None
    if cache is not None:
        key = cache / f"rows-{symbol.replace(':', '_')}-{interval}-{bars}.pkl"
    if key is not None and key.exists():
        rows = pickle.loads(key.read_bytes())
    else:
        rows = rows_with_state(symbol, interval, bars, flat)
        if key is not None:
            key.parent.mkdir(parents=True, exist_ok=True)
            key.write_bytes(pickle.dumps(rows))
    return {"rows": rows}


def matrix_universe(
    cells: list[tuple[str, str, list[dict], list[int]]], column: str, group: str
) -> tuple[np.ndarray, list[dict]]:
    """The twelve-instrument family, laid on ONE calendar so it can be resampled.

    `tools/true_open_matrix.py` runs the same registered bucket across twelve
    instruments and corrects with a single Bonferroni over every judged group.
    That family holds the largest `|t|` this repo has ever recorded, USOIL at
    -3.27 against a critical 3.27, and it is the one place where a
    dependence-aware correction has an obvious chance of changing the verdict.

    THE ALIGNMENT IS THE WHOLE POINT. Twelve instruments have twelve different
    trade counts and twelve different trade times, so there is no shared index to
    resample - and resampling each cell on its own would throw away exactly the
    cross-instrument correlation the test needs. So each rule's payoffs are
    summed onto a common UTC day grid, zero on days it did not trade, and the
    bootstrap draws blocks of DAYS. Gold and silver moving together on the same
    day then stays together in every replication.
    """
    days = sorted({d for _, _, _, stamps in cells for d in {s // 86_400 for s in stamps}})
    index = {d: i for i, d in enumerate(days)}
    total = len(days)
    series, labels = [], []
    for symbol, interval, rows, stamps in cells:
        r = np.array([row["r"] for row in rows], dtype=np.float64)
        member = np.array(
            [str(row["state"].get(column)) == group for row in rows], dtype=bool
        )
        n_group = int(member.sum())
        n_cell = len(rows)
        if n_group < MIN_GROUP or n_cell - n_group < MIN_GROUP:
            continue
        weight = np.where(member, n_cell / n_group, -n_cell / (n_cell - n_group))
        payoff = weight * r
        daily = np.zeros(total)
        for value, stamp in zip(payoff, stamps):
            daily[index[stamp // 86_400]] += value
        daily *= total / n_cell  # so the mean over days is the cell's delta
        inside, outside = r[member], r[~member]
        se = sqrt(
            inside.var(ddof=1) / n_group + outside.var(ddof=1) / (n_cell - n_group)
        )
        t = (inside.mean() - outside.mean()) / se if se > 0 else float("nan")
        for sign, direction in ((1.0, "above"), (-1.0, "below")):
            series.append(sign * daily)
            labels.append(
                {
                    "column": column,
                    "value": group,
                    "symbol": symbol,
                    "interval": interval,
                    "direction": direction,
                    "n_group": n_group,
                    "n_cell": n_cell,
                    "delta": float(sign * (inside.mean() - outside.mean())),
                    "exp_r_group": float(inside.mean()),
                    "welch_t": float(sign * t),
                }
            )
    return np.array(series), labels


def report(
    f: np.ndarray,
    labels: list[dict],
    reps: int,
    seed: int,
    blocks: list[int],
    unit: str,
) -> dict:
    """RC, SPA, StepM and the block sweep, formatted for the JSON."""
    if f.ndim != 2 or f.shape[0] == 0:
        # Nothing cleared the n >= 30 floor on both arms. Reported rather than
        # crashed, because an empty universe is an answer about the data and a
        # traceback reads like an answer about the tool.
        return {"bootstrap_unit": unit, "n_rules": 0,
                "note": "no bucket clears n >= 30 on both arms"}
    n = f.shape[1]
    chosen = block_length(n)
    result = reality_check(f, reps, chosen, seed)
    order = np.argsort(-result["studentised"])[:10]
    best = [
        {**labels[i], "studentised": float(result["studentised"][i])} for i in order
    ]
    sweep = {
        str(b): reality_check(f, max(2000, reps // 5), b, seed)["spa_p_consistent"]
        for b in blocks
        if b != chosen
    }
    sweep[str(chosen)] = result["spa_p_consistent"]
    return {
        "bootstrap_unit": unit,
        "n_observations": n,
        "n_rules": result["n_rules"],
        "n_buckets": result["n_rules"] // 2,
        "block_length": chosen,
        "block_length_reason": "round(n ** (1/3)), the Politis-Romano rate",
        "reps": reps,
        "rc_statistic": result["rc_statistic"],
        "rc_p": result["rc_p"],
        "spa_statistic": result["spa_statistic"],
        "spa_p_consistent": result["spa_p_consistent"],
        "spa_p_lower": result["spa_p_lower"],
        "spa_p_upper": result["spa_p_upper"],
        "spa_p_by_block_length": sweep,
        "stepm_alpha": ALPHA,
        "stepm_passing": [
            {**labels[i], "studentised": float(result["studentised"][i])}
            for i in result["stepm_rejected"]
        ],
        "top_10_rules": best,
    }


def summarise(rows: list[dict], reps: int, seed: int, blocks: list[int]) -> dict:
    """One instrument-timeframe cell over every pre-registered column."""
    f, labels = universe(rows)
    r = np.array([row["r"] for row in sorted(rows, key=lambda x: x["at"])])
    return {
        **report(f, labels, reps, seed, blocks, "trade"),
        "exp_r_population": float(r.mean()),
        "bonferroni_critical_t": _critical_t(f.shape[0] // 2),
        "acf_lag_1_to_10": acf(r),
        "acf_two_sigma_band": float(2 / sqrt(len(r))),
    }


def selfcheck() -> None:
    """Proof the gate is not empty: it must reject a planted edge and only that.

    Two synthetic universes with the same shape as the real one. The first is
    pure noise, where a correct RC returns a large p-value; the second has one
    rule with a mean of 0.5 standard errors per trade planted in it, where a
    correct RC returns a small one. A test that cannot fail on the second is a
    test that would have printed the same null on real data no matter what.
    """
    rng = np.random.default_rng(7)
    noise = rng.normal(size=(150, 800))
    flat = reality_check(noise, 5000, 9, seed=1)
    assert flat["rc_p"] > 0.10, flat["rc_p"]
    assert flat["spa_p_consistent"] > 0.10, flat["spa_p_consistent"]
    assert not flat["stepm_rejected"], flat["stepm_rejected"]

    # The case this whole tool exists for. 150 rules put Bonferroni's two-sided
    # critical value at 3.59; a planted rule at t = 3.55 therefore FAILS
    # Bonferroni, and RC and SPA both find it. If this assertion ever stops
    # holding, the tool has become incapable of contradicting Bonferroni and its
    # null on real data would mean nothing.
    strong = noise.copy()
    strong[42] += 0.14
    hot = reality_check(strong, 5000, 9, seed=1)
    assert 3.4 < hot["studentised"][42] < 3.59, hot["studentised"][42]
    assert hot["rc_p"] < ALPHA, hot["rc_p"]
    assert hot["spa_p_consistent"] < ALPHA, hot["spa_p_consistent"]
    assert hot["stepm_rejected"] == [42], hot["stepm_rejected"]

    # And the calibration in the other direction, at the largest |t| this
    # project has ever recorded on a conditioning column (2.39). Neither test
    # rescues it, so a null below is a real null and not a blunt instrument.
    weak = noise.copy()
    weak[42] += 0.10
    cold = reality_check(weak, 5000, 9, seed=1)
    assert 2.2 < cold["studentised"][42] < 2.6, cold["studentised"][42]
    assert cold["spa_p_consistent"] > 0.10, cold["spa_p_consistent"]
    print("selfcheck ok: null stays null, t=3.55 beats Bonferroni, t=2.40 does not")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--intervals", default="1h,15m")
    parser.add_argument("--bars", type=int, default=50000)
    parser.add_argument("--reps", type=int, default=REPS)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--blocks", default="1,5,10,20,50")
    parser.add_argument("--cache", default="")
    parser.add_argument("--hold", action="store_true")
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--only", default="",
                        help="matrix mode: restrict to these bare symbols, "
                             "which is how one cell gets its own process")
    parser.add_argument("--matrix", default="",
                        help="replicate one registered column of "
                             "tools/true_open_matrix.py across every instrument "
                             "with a costed row, on a shared day grid")
    args = parser.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    cache = Path(args.cache) if args.cache else None
    blocks = [int(b) for b in args.blocks.split(",")]
    flat = not args.hold
    out = {
        "bars": args.bars,
        "exit_rule": "hold 80 bar" if args.hold else "flat di rollover",
        "method": "White (2000) Reality Check + Hansen (2005) SPA, stationary "
                  "bootstrap (Politis-Romano 1994), Romano-Wolf StepM",
        "reps": args.reps,
        "seed": args.seed,
    }
    if args.matrix:
        group, _ = REGISTERED[args.matrix]
        symbols = sorted(BROKERS["exness_raw"])
        # ONE CELL PER PROCESS IS A REQUIREMENT, NOT A CONVENIENCE. `at_bar`'s
        # partner-correlation column reaches `load_aligned`, which reaches the
        # per-key `asyncio.Lock` cache in `app/providers/__init__.py`. A second
        # `asyncio.run` in the same process meets a lock bound to the first,
        # dead, event loop and the cell dies with "is bound to a different event
        # loop". Measured 2026-08-30: nine of twelve cells lost that way in one
        # run. So `--only` warms one cell's cache in its own process, and the
        # pooled run afterwards reads every cell from disk and calls no provider
        # at all. `tools/true_open_matrix.py` has the same exposure and has had
        # it since `partner_corr_band` landed on 2026-08-29.
        if args.only:
            symbols = [s for s in args.only.split(",") if s in symbols]
        collected = []
        for symbol in symbols:
            for interval in args.intervals.split(","):
                try:
                    rows = cell(f"mt5:{symbol}", interval, args.bars, flat, cache)
                except Exception as exc:  # noqa: BLE001 - one cell, not the run
                    print(f"{symbol} {interval} GAGAL: {str(exc)[:80]}",
                          file=sys.stderr)
                    continue
                rows = rows["rows"]
                if not rows:
                    continue
                times = [c.time for c in
                         history.load(f"mt5:{symbol}", interval, args.bars)]
                collected.append(
                    (symbol, interval, rows, [times[r["at"]] for r in rows])
                )
        f, labels = matrix_universe(collected, args.matrix, group)
        out["symbols"] = symbols
        out["universe"] = (
            f"the pre-registered group '{group}' of {args.matrix} across "
            f"{len(labels) // 2} judgeable cells, both directions"
        )
        out["matrix"] = report(f, labels, args.reps, args.seed, blocks, "UTC day")
        out["matrix"]["bonferroni_critical_t"] = _critical_t(len(labels) // 2)
    else:
        out["symbol"] = args.symbol
        out["universe"] = ("the pre-registered columns of tools/conditioned.py, "
                           "both directions per bucket")
        out["cells"] = {}
        for interval in args.intervals.split(","):
            rows = cell(args.symbol, interval, args.bars, flat, cache)["rows"]
            out["cells"][interval] = summarise(rows, args.reps, args.seed, blocks)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

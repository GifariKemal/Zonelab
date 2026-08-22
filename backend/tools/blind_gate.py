"""Is 2 ATR the right gate, or just the number that fitted the first sample?

    python -m tools.blind_gate

The departure gate now reproduces across instruments, timeframes and two years,
and every one of those tests carried the same quiet flaw: **the 2 ATR threshold
was chosen on earlier data**. So they tested whether that threshold survives,
which is worth knowing, and not whether the gate is real, which is what anyone
actually wants to know. A number picked with hindsight can survive a great deal
of out-of-sample testing and still be hindsight.

This closes that gap the only way it can be closed. The series is cut in half by
time. The threshold is chosen on the FIRST half alone, by a stated rule, with
the second half not merely unused but unread. Then it is evaluated once on the
second half. Whatever comes out is what a person standing at the midpoint, with
no knowledge of the future, would actually have got.

THE SELECTION RULE, FIXED BEFORE RUNNING
Pick the threshold on the first half that maximises the SEPARATION between the
cohort that clears it and the cohort that does not, subject to both cohorts
keeping at least 50 trades so the winner cannot be a corner with four trades in
it. Separation rather than raw expectancy, because a gate's job is to sort, and
because maximising expectancy alone would drift to whatever threshold leaves the
smallest and luckiest group above it.

The grid is 0.5 to 6.0 ATR in steps of 0.5. Stated, not tuned: it brackets the
doctrine's own range and the 2.0 in use, and a finer grid would only offer more
places for noise to win.

WHAT WOULD FALSIFY THE GATE
If the first half picks a threshold nowhere near 2.0, and that pick then fails
on the second half, the gate is a fitted artefact. If the first half picks
something near 2.0 and it holds out of sample, the 2.0 in the shipped code was
not hindsight. Both outcomes are informative, which is the point.
"""

from __future__ import annotations

import argparse

import numpy as np

from tools import history
from tools.costed import trades

GRID = np.arange(0.5, 6.01, 0.5)
MIN_PER_COHORT = 50


def split(rows: list[dict], gate: float) -> tuple[np.ndarray, np.ndarray]:
    above = np.array([r["r"] for r in rows if r["departure"] >= gate])
    below = np.array([r["r"] for r in rows if r["departure"] < gate])
    return above, below


def choose(rows: list[dict], objective: str = "separation") -> tuple[float, float]:
    """The best threshold on this half alone, by `objective`.

    TWO OBJECTIVES, DAN KEDUANYA MENJAWAB PERTANYAAN BERBEDA. `separation`
    memaksimalkan selisih antara kohort yang lolos dan yang tidak, yang menjawab
    "apakah gerbangnya menyortir". `expectancy` memaksimalkan ekspektasi kohort
    yang LOLOS, yang menjawab "apakah ada ambang yang menghasilkan uang".
    Separasi bisa melebar sementara kohort atasnya tetap negatif, dan itu persis
    keadaan yang terukur di resolusi halus: gerbangnya menyortir, +0,124 R dengan
    t = +4,82, dan sisi atasnya cuma break-even.
    """
    best, best_gap = float("nan"), -float("inf")
    print(f"  {'gate':>6}{'n above':>9}{'n below':>9}{'above':>9}{'below':>9}"
          f"{'separation':>12}")
    for gate in GRID:
        above, below = split(rows, float(gate))
        if len(above) < MIN_PER_COHORT or len(below) < MIN_PER_COHORT:
            print(f"  {gate:>6.1f}{len(above):>9}{len(below):>9}"
                  f"{'':>9}{'':>9}{'too few':>12}")
            continue
        gap = float(above.mean() - below.mean())
        score = float(above.mean()) if objective == "expectancy" else gap
        star = "  <-" if score > best_gap else ""
        print(f"  {gate:>6.1f}{len(above):>9}{len(below):>9}"
              f"{above.mean():>9.3f}{below.mean():>9.3f}{gap:>12.3f}{star}")
        if score > best_gap:
            best, best_gap = float(gate), score
    return best, best_gap


def evaluate(rows: list[dict], gate: float, label: str) -> None:
    above, below = split(rows, gate)
    if len(above) < 30 or len(below) < 30:
        print(f"  {label}: too few, {len(above)} above and {len(below)} below")
        return
    gap = float(above.mean() - below.mean())
    se = float(np.sqrt(above.var(ddof=1) / len(above)
                       + below.var(ddof=1) / len(below)))
    t = gap / se if se > 0 else float("nan")
    print(f"  {label}")
    print(f"    above {gate:.1f} ATR : n={len(above):>4}  exp R {above.mean():>+7.3f}")
    print(f"    below           : n={len(below):>4}  exp R {below.mean():>+7.3f}")
    print(f"    separation      : {gap:>+7.3f}  t={t:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="yahoo:XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--broker", default="exness_raw")
    parser.add_argument("--fine", default="",
                        help="timeframe halus untuk penyelesaian, misal 5m")
    parser.add_argument("--objective", default="separation",
                        choices=("separation", "expectancy"))
    parser.add_argument("--symbols", default="",
                        help="daftar simbol, digabung jadi satu populasi")
    args = parser.parse_args()

    names = [s.strip() for s in (args.symbols or args.symbol).split(",") if s.strip()]
    rows: list[dict] = []
    total_bars = 0
    for name in names:
        if args.fine:
            # RESOLUSI HALUS. Sampai 22 Agustus 2026 tool ini menyelesaikan trade
            # di bar besar, yang melebihkan ekspektasi karena target di bar entry
            # dihitung menang. Ambang yang dipilih di angka yang melebihkan adalah
            # ambang untuk pertanyaan yang salah.
            from tools.intrabar import resolved
            bare = name.split(":")[-1]
            got = [r for r in resolved(bare, args.interval, args.fine)
                   if not r["skipped"]]
            total_bars += len(got)
        else:
            candles = history.load(name, args.interval, args.bars)
            total_bars += len(candles)
            got = [r for r in trades("supply_demand", candles, args.interval, True,
                                     symbol=name.split(":")[-1], broker=args.broker)
                   if not r["skipped"]]
        # Waktu dinormalkan per simbol supaya paruh pertama satu simbol tidak
        # bercampur dengan paruh kedua simbol lain saat digabung.
        if got:
            mid_at = float(np.median([r["at"] for r in got]))
            for r in got:
                r["half"] = 0 if r["at"] <= mid_at else 1
            rows.extend(got)
    if not rows:
        print("tidak ada trade")
        return
    # PARUH PER SIMBOL, bukan paruh dari indeks bar yang digabung. Menggabung
    # `at` lintas simbol membuat median-nya tidak berarti apa pun: indeks bar
    # instrumen A dan B tidak menunjuk waktu yang sama.
    first = [r for r in rows if r["half"] == 0]
    second = [r for r in rows if r["half"] == 1]

    print(f"\n{'=' * 74}")
    print(f"BLIND GATE   {','.join(names)} {args.interval}"
          + (f"   halus {args.fine}" if args.fine else "")
          + f"   objective {args.objective}")
    print(f"{'=' * 74}")
    print(f"  {len(first)} trades in the first half, {len(second)} in the second")
    print("\n  Choosing on the FIRST HALF only. The second half is not read.")
    gate, gap = choose(first, args.objective)
    if np.isnan(gate):
        print("\n  no threshold left both cohorts large enough; nothing to test")
        return

    print(f"\n  Chosen blind: {gate:.1f} ATR, separation {gap:+.3f} in sample")
    print("  Shipped:      2.0 ATR")
    print()
    evaluate(second, gate, f"SECOND HALF at the blindly chosen {gate:.1f} ATR")
    print()
    evaluate(second, 2.0, "SECOND HALF at the shipped 2.0 ATR")

    print(
        "\n  Read the chosen threshold as much as the result. A pick far from"
        "\n  2.0 that then works says the gate is real and the shipped value is"
        "\n  arbitrary; a pick near 2.0 says the shipped value was not hindsight;"
        "\n  a pick that fails out of sample says the gate was fitted all along."
    )


if __name__ == "__main__":
    main()

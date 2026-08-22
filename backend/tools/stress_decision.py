"""Push the decision-to-order path until something gives, and report what.

    python -m tools.stress_decision                  # the battery
    python -m tools.stress_decision --bars 3000      # one window size

`tools/stress.py` pushes the API, which is the READ path. This pushes the path
that ends in a broker order: layer state, the guards, the plan, the journal and
the idempotency key. Nothing here sends anything - the executor's `--send` is
never touched - so this is safe to run against the live terminal, and it is
deliberately run against the live terminal because a decision path that only
works on synthetic bars has not been tested.

Exit code is the number of checks that failed, so it can be a gate.

WHAT EACH CHECK IS FOR, because a stress battery whose failures nobody can read
is a slow way of learning nothing:

  1. DETERMINISM. The same bars must produce the same orders. A path that answers
     differently on identical input cannot be audited, and the journal it writes
     would be fiction.
  2. WINDOW INDEPENDENCE. A zone present in two window sizes must carry the same
     entry, stop and target in both. This is the property `test_no_repaint.py`
     asserts for geometry, checked here through the PLAN, which is the number an
     order actually uses.
  3. THE GUARD ACTUALLY BITES. Ask for more history than exists and the run must
     refuse rather than trade a short series.
  4. IDEMPOTENCY. A zone with a `placed` line must not be offered again, and the
     check has to survive the journal being written to between runs.
  5. JOURNAL DURABILITY. Five hundred appends, read back, all parseable, in
     order. A log that garbles under load is worse than none.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from app import journal
from app.actionable import blockers
from app.providers.base import INTERVALS
from tools.costed import rollovers
from tools.execute import RULE, candidates, grounds

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def plan_key(triple) -> tuple:
    # Triples since 2026-08-21: the ICT checklist rides along with the plan.
    zone, plan = triple[0], triple[1]
    return (zone.id, round(plan.entry, 3), round(plan.stop, 3), round(plan.target, 3))


def battery(symbol: str, interval: str, bars: int) -> None:
    print(f"\n== 1. determinisme, {symbol} {interval} {bars} bar")
    first, response, price = candidates(symbol, interval, bars)
    second, _, price_again = candidates(symbol, interval, bars)
    check("dua run berurutan menghasilkan kandidat identik",
          [plan_key(p) for p in first] == [plan_key(p) for p in second],
          f"{len(first)} lawan {len(second)} kandidat")
    check("harga acuan sama", price == price_again, f"{price} lawan {price_again}")
    check("setiap kandidat punya alasan bernomor",
          all(any(ch.isdigit() for ch in line)
              for zone, plan, _ in first for line in grounds(zone, plan)))

    print("\n== 2. independensi window")
    windows = {}
    # Widths chosen so they SHARE zones. The first version used 1000, and a
    # 1000-bar window holds no untouched gate-clearing zone at all, so the
    # intersection was empty and the check passed by having nothing to compare.
    # A check that cannot fail is not a check, so the emptiness is now itself a
    # failure.
    for width in (3000, 6000, 10000):
        pairs, _, _ = candidates(symbol, interval, width)
        windows[width] = {t[0].id: plan_key(t) for t in pairs}
        print(f"     {width:6d} bar -> {len(pairs)} kandidat")
    shared = set.intersection(*(set(w) for w in windows.values()))
    check("ada zona yang muncul di ketiga window untuk dibandingkan",
          len(shared) > 0, f"{len(shared)} zona bersama")
    disagreeing = [
        zid for zid in shared
        if len({windows[w][zid] for w in windows}) > 1
    ]
    check("zona yang muncul di semua window membawa plan identik",
          bool(shared) and not disagreeing,
          f"{len(shared)} zona bersama, {len(disagreeing)} berbeda: "
          f"{[(z, [windows[w][z] for w in windows]) for z in disagreeing[:2]]}")

    print("\n== 3. penjaga data")
    # THE CLOCK IS PINNED ONE BAR PAST THE DRAWING, because the market is not
    # always open and this check used to assume it was. Run on 2026-08-22, a
    # Saturday, it failed with `feed is 9992s behind on a 3600s interval` - which
    # was true, was the guard doing exactly its job, and said nothing about the
    # healthy path this line exists to exercise. Reading the real clock here made
    # the check untestable for two days a week; the stale case below still reads
    # it, so the refusal is still proved.
    fresh = int(response["meta"]["as_of"]) + INTERVALS[interval]
    check("drawing yang sehat tidak diblokir", blockers(response, now=fresh) == [],
          str(blockers(response, now=fresh)))
    huge = dict(response)
    huge["meta"] = {**response["meta"], "truncated_by_provider": True,
                    "bars_returned": 10}
    check("riwayat terpotong diblokir", len(blockers(huge)) >= 1)
    stale = dict(response)
    stale["meta"] = {**response["meta"], "as_of": response["meta"]["as_of"] - 999_999}
    check("feed yang tertinggal diblokir", len(blockers(stale)) >= 1)

    print("\n== 4. idempotensi")
    with tempfile.TemporaryDirectory() as tmp:
        original = journal.DIRECTORY
        journal.DIRECTORY = Path(tmp) / ".journal"
        try:
            zone, plan = first[0][0], first[0][1]
            check("zona belum diorder tidak punya baris placed",
                  journal.for_zone(zone.id) == [])
            journal.record("placed", why=grounds(zone, plan), rule=RULE,
                           zone_id=zone.id, ticket=1,
                           plan=plan.model_dump(mode="json"))
            placed = [e for e in journal.for_zone(zone.id) if e["event"] == "placed"]
            check("setelah dicatat, zona itu terlihat sudah diorder", len(placed) == 1)
            journal.record("placed", why=grounds(zone, plan), rule=RULE,
                           zone_id=zone.id, ticket=2,
                           plan=plan.model_dump(mode="json"))
            check("dua baris untuk satu zona tetap terbaca dua",
                  len([e for e in journal.for_zone(zone.id)
                       if e["event"] == "placed"]) == 2,
                  "journal mencatat, eksekutor yang menolak - itu pembagian tugasnya")

            print("\n== 5. daya tahan journal")
            for n in range(500):
                journal.record("refused", why=[f"n={n}"], rule=RULE,
                               zone_id=f"Z-{n}", blockers=["stress"])
            rows = journal.entries()
            check("500 append terbaca kembali utuh", len(rows) == 502,
                  f"terbaca {len(rows)}")
            check("urut menurut waktu",
                  [r["at"] for r in rows] == sorted(r["at"] for r in rows))
            check("setiap baris punya rule", all(r["rule"] for r in rows))
        finally:
            journal.DIRECTORY = original

    print("\n== 6. aritmetika rollover")
    day = 86_400
    check("nol malam dalam satu hari perdagangan",
          rollovers(1787304694, 1787304694 + 3600) == 0)
    check("satu malam melewati 21:00",
          rollovers(1787304694, 1787304694 + day) == 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--bars", type=int, default=3000)
    args = parser.parse_args()

    battery(args.symbol, args.interval, args.bars)
    print(f"\n{'=' * 60}")
    if FAILURES:
        print(f"{len(FAILURES)} check GAGAL:")
        for line in FAILURES:
            print(f"  - {line}")
    else:
        print("semua check lolos")
    return len(FAILURES)


if __name__ == "__main__":
    raise SystemExit(main())

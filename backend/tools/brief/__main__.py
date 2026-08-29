"""Tulis satu brief lengkap yang bisa dibaca AI agent mana pun.

    python -m tools.brief
    python -m tools.brief --symbol mt5:XAUUSD --intervals 4h,1h,15m --out ../brief

Menghasilkan dua file di folder keluaran:

    brief.json   seluruh bacaan, mesin yang membacanya
    BRIEF.md     ringkasan berurut, manusia dan AI agent yang membacanya

BRIEF.md DITULIS UNTUK DIBACA AGENT, dan itu mengubah cara ia disusun. Tiap
angka dibawa bersama sumbernya, tiap kekosongan menjelaskan sebabnya, dan
bagian pertama adalah daftar hal yang TIDAK boleh disimpulkan dari isi
dokumen ini. Agent yang membaca angka tanpa provenance-nya akan mengutip
klausa doktrin sebagai hasil pengukuran, dan tiga belas dari tujuh belas
klausa di sini tidak punya satu angka pun di belakangnya.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time

from app import clock
from tools import history
from tools.brief import collect, live, render


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD")
    parser.add_argument("--intervals", default="4h,1h,15m",
                        help="dari kasar ke halus; yang pertama dipakai untuk bias")
    parser.add_argument("--bars", type=int, default=2000)
    parser.add_argument("--partners", default="mt5:XAGUSD,mt5:XPTUSD",
                        help="pasangan SSMT dan triad")
    parser.add_argument("--out", default="../brief",
                        help="folder keluaran, relatif ke backend/")
    args = parser.parse_args()

    intervals = [x.strip() for x in args.intervals.split(",") if x.strip()]
    partners = [x.strip() for x in args.partners.split(",") if x.strip()]
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    started = time.time()
    brief: dict = {
        "generated_at": int(started),
        "generated_at_ny": f"{clock.to_ny(int(started)):%Y-%m-%d %H:%M} NY",
        "market_shut": clock.market_shut(int(started)),
        "symbol": args.symbol,
        "partners": partners,
        "intervals": intervals,
        "bars_requested": args.bars,
        "timeframes": {},
        "failures": [],
    }

    for tf in intervals:
        print(f"  menarik {args.symbol} {tf} ...", flush=True)
        try:
            brief["timeframes"][tf] = collect.one_timeframe(
                args.symbol, tf, args.bars, partners)
        except Exception as exc:  # noqa: BLE001 - satu timeframe, bukan run
            # SATU TIMEFRAME YANG GAGAL TIDAK MEMBATALKAN SISANYA, aturan yang
            # sama dengan `execute.gather` dan matrix di `tools/quant.py`. Yang
            # gagal DICATAT, karena brief yang kehilangan satu timeframe tanpa
            # mengatakannya terbaca sebagai timeframe yang tidak punya apa apa.
            brief["failures"].append({"timeframe": tf, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    GAGAL: {type(exc).__name__}: {exc}")

    base_tf = next((tf for tf in intervals if tf in brief["timeframes"]), None)
    if base_tf is None:
        print("BLOCKER: tidak satu pun timeframe berhasil ditarik")
        return 1

    rows = history.load(args.symbol, base_tf, args.bars)
    price = rows[-1].close
    print(f"  siklus, dial, dan bias di {base_tf} ...", flush=True)
    brief["cycle"] = collect.cycle_now(rows, base_tf)
    brief["fibonacci"] = collect.fib_grid(
        brief["timeframes"][base_tf]["drawing"], price)
    brief["layer_evidence"] = collect.evidence_table()
    brief["clause_provenance"] = collect.clause_provenance()
    brief["known_degrees"] = collect.known_degrees()
    brief["price"] = price
    brief["base_timeframe"] = base_tf

    # KANDIDAT: rencana yang punya target, diurut menurut jarak ke harga.
    # Yang TIDAK punya target ikut dihitung, karena "48 dari 61 rencana tidak
    # punya zona lawan hidup" adalah fakta tentang pasarnya, bukan kekosongan.
    print("  menilai kandidat terdekat ...", flush=True)
    brief["candidates"] = render.rank_candidates(brief["timeframes"], price)
    brief["ict"] = []
    for cand in brief["candidates"]["with_target"][:3]:
        tf = cand["timeframe"]
        zmap = {z["id"]: z for z in brief["timeframes"][tf]["drawing"]["zones"]}
        try:
            brief["ict"].append(collect.ict_reading(
                zmap[cand["zone_id"]], cand,
                history.load(args.symbol, tf, args.bars), tf))
        except Exception as exc:  # noqa: BLE001
            brief["failures"].append(
                {"ict": cand["zone_id"], "error": f"{type(exc).__name__}: {exc}"})

    # ------------------------------------------------ bacaan yang menjaring
    # Ditaruh SETELAH seluruh bacaan struktural selesai, supaya kegagalan
    # jaringan tidak mengambil brief yang sudah lengkap bersamanya.
    print("  checklist dan triad (butuh provider call) ...", flush=True)
    both = live.gather(args.symbol, base_tf, args.bars, partners)
    brief["checklist"] = both["checklist"]
    brief["triad"] = both["triad"]
    if not brief["checklist"].get("present"):
        brief["failures"].append({"checklist": brief["checklist"].get("why")})
    elif brief["checklist"].get("partners_unreadable"):
        # Nama partner yang salah ketik lolos tanpa jejak sampai 29 Agustus
        # 2026: nol hit SSMT terbaca sama dengan "tidak ada divergensi".
        brief["failures"].append(
            {"ssmt_partners_unreadable": brief["checklist"]["partners_unreadable"]})
    if not brief["triad"].get("present"):
        brief["failures"].append({"triad": brief["triad"].get("why")})
    elif brief["triad"].get("skipped"):
        brief["failures"].append({"triad_partners_skipped": brief["triad"]["skipped"]})

    brief["ote_reconciliation"] = live.ote_reconciliation(
        brief["fibonacci"], brief["cycle"]["conditioning_state"])

    (out / "brief.json").write_text(
        json.dumps(brief, indent=1, ensure_ascii=True), encoding="utf-8")
    (out / "BRIEF.md").write_text(render.markdown(brief), encoding="utf-8")

    took = time.time() - started
    print(f"\nditulis ke {out}")
    print(f"  brief.json  {(out / 'brief.json').stat().st_size:,} byte")
    print(f"  BRIEF.md    {(out / 'BRIEF.md').stat().st_size:,} byte")
    print(f"  {took:.1f} detik, {len(brief['failures'])} kegagalan")
    return 1 if brief["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

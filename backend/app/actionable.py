"""May this drawing be acted on? The refusals, in one place.

A drawing is FIT TO READ under conditions that are looser than the conditions
that make it fit to ACT ON, and until 2026-08-21 nothing in this project drew
that line. `drawing.py` has stamped `truncated_by_provider` into every response
since the field was born and NOTHING ever read it: a source that could only
return 400 of the 1000 bars asked for drew a shorter chart that looked exactly
like a quiet market, and any automation reading that response would have placed
an order against zones that were missing rather than absent.

WHY REFUSALS AND NOT A SCORE. A score invites a threshold, a threshold invites
tuning, and a tuned threshold is a parameter fitted to whatever went wrong last.
Each blocker below is a fact with a number attached, and the caller either has
none or does not act. Nothing here is weighted against anything else.

WHY IT RETURNS STRINGS. They go straight into the decision journal beside the
order, so the record says why the engine acted or refused in the words the check
itself used, rather than as a flag that has to be decoded a month later.

WHAT IS DELIBERATELY NOT HERE. Anything about whether the trade is a good idea:
that is `plan.py` (geometry and risk) and the gates in `docs/CALIBRATION.md`
(whether the formation is worth anything). This module only answers whether the
PICTURE is sound enough to be acted on at all.
"""

from __future__ import annotations

import time as _time

from .providers.base import INTERVALS


def blockers(response: dict, now: int | None = None) -> list[str]:
    """Reasons this response must not be traded from. Empty means none found.

    `now` is injectable so a test can pin the clock; production passes nothing.
    """
    out: list[str] = []
    meta = response.get("meta") or {}
    candles = response.get("candles") or []

    if not meta:
        return ["no meta block: this is not a /api/draw response"]
    if not candles:
        return ["no candles: there is nothing drawn to act on"]

    requested = meta.get("bars_requested")
    returned = meta.get("bars_returned")
    if meta.get("truncated_by_provider"):
        # BOTH counts, because "400" alone reads as a quiet market and
        # "400 of 1000" reads as a missing history. That distinction is the whole
        # reason the field exists.
        out.append(
            f"history truncated by the provider: {returned} of {requested} bars. "
            "A zone that is missing because its bars are missing cannot be told "
            "apart from a zone that never formed"
        )

    interval = response.get("interval")
    step = INTERVALS.get(interval) if isinstance(interval, str) else None
    if step is None:
        out.append(f"unknown interval {interval!r}, so staleness cannot be judged")
    else:
        # `feed_lag_seconds` is measured from the newest bar's CLOSE, so a lag
        # anywhere inside one interval is the normal state of a live chart: the
        # next bar has simply not finished. Beyond one full interval a close has
        # been missed, and the picture is describing a bar that is no longer the
        # last one. Recomputed from `as_of` rather than trusted, because the
        # stamped figure is as old as the response and this question is about now.
        as_of = int(meta.get("as_of") or 0)
        at = now if now is not None else int(_time.time())
        lag = max(0, at - (as_of + step))
        missed, basis = _missed_bars(candles, as_of, step, at)
        if missed > 0:
            out.append(
                f"feed is {lag}s behind on a {step}s interval and {missed} bar"
                f"{'s have' if missed != 1 else ' has'} closed since this was "
                f"drawn ({basis})"
            )

    return out


#: Berapa minggu ke belakang dicek untuk memutuskan sebuah slot kosong terjadwal.
#:
#: BUKAN ambang yang di-tune. Ia jendela lookback, dan arahnya konservatif:
#: sebuah slot dianggap PUNYA PRESEDEN kalau ada bar di sana pada MINGGU MANA
#: PUN dari empat itu, jadi satu minggu normal saja sudah cukup untuk membuat
#: diamnya dihitung sebagai kehilangan. Yang dilewati hanya slot yang keempat
#: minggu itu SEMUANYA diam, yaitu jeda yang benar-benar terjadwal.
PRECEDENT_WEEKS = 4
_WEEK = 7 * 86_400
#: Slot maksimum yang diperiksa. Diam selama berbulan-bulan tidak perlu
#: dihitung per slot untuk diketahui bermasalah, dan loop tanpa batas di jalur
#: keputusan adalah cara sebuah cek berubah jadi hang.
_MAX_SLOTS = 500


def _missed_bars(candles: list, as_of: int, step: int, now: int) -> tuple[int, str]:
    """Berapa bar yang PASAR HASILKAN dan gambar ini tidak punya.

    KENAPA INI BUKAN SELISIH JAM DINDING. Sampai 2 September 2026 cek ini
    membandingkan `now` ke `as_of + step` dan memblokir begitu selisihnya
    melewati satu interval. Untuk instrumen 24/7 itu benar. Untuk emas itu salah
    setiap hari: XAUUSD di broker ini berhenti 90 menit, bar 30 menitnya melompat
    dari 20:30 ke 22:00 UTC (16:30 ke 18:00 New York), jadi satu jam penuh
    setelah break setiap hari gambar gold yang SEHAT ditolak. Terukur pada 2
    September 2026 pukul 22:26 UTC: blocker berbunyi "feed is 5200s behind on a
    1800s interval" sementara terminalnya connected, tick terakhirnya berumur 3
    detik, dan `history.load` mengembalikan bar tutup terakhir yang benar.

    "Basi" berarti pasar menghasilkan bar yang gambar ini tidak punya. Saat sesi
    tutup pasar tidak menghasilkan apa pun, jadi tidak ada yang hilang, dan
    pertanyaannya harus dihitung dalam BAR bukan dalam detik.

    PRESEDEN DIBACA DARI DERETNYA SENDIRI, bukan dari kalender broker. Sebuah
    slot dihitung hilang kalau deret ini pernah punya bar di jam-hari yang sama
    pada salah satu dari `PRECEDENT_WEEKS` minggu sebelumnya. Kalender sesi tidak
    tersedia di sini - `blockers` cuma menerima response API - dan deret itu
    sendiri adalah catatan paling jujur tentang kapan instrumennya berdagang.

    Mengembalikan `(jumlah, dasar)`, dan `dasar` masuk ke teks penolakan supaya
    catatan journal mengatakan cek mana yang menjawab.

    YANG TIDAK DITANGANI, dinyatakan bukan disembunyikan: hari libur. Sebuah
    libur punya preseden di minggu-minggu normal, jadi blocker ini tetap
    berbunyi. Itu arah yang aman untuk sebuah penolakan, dan memperbaikinya
    butuh kalender libur yang tidak ada di response ini.
    """
    if step <= 0 or as_of <= 0 or now <= as_of + step:
        return 0, "jam dinding"
    times = [int(c["time"]) for c in candles if isinstance(c, dict)
             and isinstance(c.get("time"), (int, float))]
    # Slot yang seharusnya sudah TUTUP: buka di `as_of + k*step`, tutup di
    # `as_of + (k+1)*step`, dan tutupnya sudah lewat.
    slots = []
    k = 1
    # KETAT, bukan `<=`. Bar yang buka di `as_of + step` tutup TEPAT di
    # `as_of + 2*step`, dan detik itu adalah saat terakhir sebelum close
    # berikutnya, bukan close yang terlewat. `<=` di sini menolak setiap chart
    # di detik terakhir setiap bar.
    while as_of + (k + 1) * step < now and len(slots) < _MAX_SLOTS:
        slots.append(as_of + k * step)
        k += 1
    if not slots:
        return 0, "jam dinding"
    if len(slots) >= _MAX_SLOTS:
        return len(slots), f"lebih dari {_MAX_SLOTS} bar, tidak diperiksa per slot"

    span = (max(times) - min(times)) if len(times) > 1 else 0
    if span < _WEEK + step:
        # Tanpa satu minggu riwayat, preseden tidak bisa diuji dan aturan lama
        # yang dipakai. Dinyatakan di teksnya supaya tidak terbaca sebagai
        # jawaban yang lebih kuat daripada yang sebenarnya.
        return len(slots), "jam dinding, riwayat kurang dari satu minggu"

    known = set(times)
    weeks = min(PRECEDENT_WEEKS, max(1, span // _WEEK))
    missed = 0
    for slot in slots:
        if any(slot - w * _WEEK in known for w in range(1, weeks + 1)):
            missed += 1
    return missed, (
        f"{missed} dari {len(slots)} slot punya preseden di {weeks} minggu "
        "sebelumnya"
    )

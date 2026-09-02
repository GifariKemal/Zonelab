"""The refusals have to fire, and they have to stay quiet on a sound drawing.

`truncated_by_provider` was written into every response for months and read by
nothing. A guard nobody calls is not a guard, and a guard whose tests only prove
the happy path is the same thing wearing a test suite.
"""

from __future__ import annotations

from app.actionable import blockers

STEP = 3600
AS_OF = 1_787_299_200  # a closed 1h bar


def response(**over) -> dict:
    """A sound drawing, which each test then breaks in exactly one way."""
    meta = {
        "bars_requested": 1000,
        "bars_returned": 1000,
        "truncated_by_provider": False,
        "as_of": AS_OF,
    }
    meta.update(over.pop("meta", {}))
    out = {
        "interval": "1h",
        "candles": [{"time": AS_OF, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}],
        "meta": meta,
    }
    out.update(over)
    return out


def test_a_sound_drawing_has_no_blockers():
    # Mid-bar: the next bar has not closed yet, which is the normal live state.
    assert blockers(response(), now=AS_OF + STEP + 600) == []


def test_truncated_history_blocks_and_names_both_counts():
    got = blockers(
        response(meta={"truncated_by_provider": True, "bars_returned": 400}),
        now=AS_OF + STEP + 600,
    )
    assert len(got) == 1
    assert "400 of 1000" in got[0], (
        "one count alone reads as a quiet market; both read as missing history"
    )


def test_a_missed_bar_close_blocks():
    """One interval of lag is normal. Two means a close was missed."""
    assert blockers(response(), now=AS_OF + STEP + STEP + 1) != []


def test_the_edge_of_one_interval_is_still_sound():
    """Exactly one interval of lag is the last moment before the next close, not
    a missed one. Asserted because an off-by-one here refuses every chart in the
    final second of every bar."""
    assert blockers(response(), now=AS_OF + 2 * STEP) == []


def test_no_candles_blocks_on_its_own():
    got = blockers(response(candles=[]), now=AS_OF + STEP)
    assert got == ["no candles: there is nothing drawn to act on"]


def test_a_response_without_meta_is_not_a_drawing():
    assert blockers({"candles": [1]}, now=AS_OF) == [
        "no meta block: this is not a /api/draw response"
    ]


def test_an_unknown_interval_blocks_rather_than_passing_silently():
    """The staleness check needs the bar length. Without it the answer is not
    "sound", it is "unknown", and those must not be the same output."""
    got = blockers(response(interval="7m"), now=AS_OF + STEP)
    assert any("unknown interval" in b for b in got)


def test_two_faults_are_both_reported():
    """Not first-fault-wins: the journal records everything that was wrong, or a
    fixed truncation would reveal a staleness nobody had been told about."""
    got = blockers(
        response(meta={"truncated_by_provider": True, "bars_returned": 10}),
        now=AS_OF + 5 * STEP,
    )
    assert len(got) == 2, got


# --------------------------------------------------------------- jeda sesi

WEEK = 7 * 86_400
#: Jam UTC yang instrumen ini TIDAK berdagang, tiap hari. Meniru emas di broker
#: ini: bar 30 menitnya melompat dari 20:30 ke 22:00, jeda 90 menit, 53 kali
#: dalam 3.000 bar.
SHUT_HOURS = (21, 22)


def _series(weeks: int = 5, step: int = STEP) -> list[dict]:
    """Deret satu jam selama `weeks` minggu, dengan jeda harian yang sama.

    Grid-nya tetap di jam bulat dan jeda hariannya berulang tiap 86.400 detik,
    yang membagi habis satu minggu, jadi `slot - k * WEEK` selalu mendarat di
    slot yang sejenis. Tanpa itu uji presedennya akan meleset karena aritmetika
    kalender, bukan karena logikanya.
    """
    start = AS_OF - weeks * WEEK
    start -= start % 86_400
    out = []
    t = start
    while t <= AS_OF:
        if (t % 86_400) // 3600 not in SHUT_HOURS:
            out.append({"time": t})
        t += step
    return out


def _resp(as_of: int, candles: list[dict], step: int = STEP) -> dict:
    return {
        "interval": "1h" if step == 3600 else "30m",
        "candles": candles,
        "meta": {"bars_requested": len(candles), "bars_returned": len(candles),
                 "truncated_by_provider": False, "as_of": as_of},
    }


def _last_before_break(candles: list[dict]) -> int:
    """Bar terakhir sebelum jeda harian, yaitu jam sebelum `SHUT_HOURS` mulai."""
    want = (SHUT_HOURS[0] - 1) % 24
    return max(c["time"] for c in candles
               if (c["time"] % 86_400) // 3600 == want)


def test_a_session_break_is_not_a_stale_feed():
    """CACAT YANG DIPERBAIKI 2 September 2026, dan ia berbunyi setiap hari.

    Cek ini dulu membandingkan jam dinding ke `as_of + step` dan memblokir
    begitu selisihnya melewati satu interval. Untuk instrumen 24/7 itu benar.
    Untuk emas salah setiap hari: XAUUSD di broker ini berhenti 90 menit dan bar
    30 menitnya melompat dari 20:30 ke 22:00 UTC, jadi satu jam penuh setelah
    break gambar gold yang SEHAT ditolak. Terukur pukul 22:26 UTC hari itu:
    blocker berbunyi "feed is 5200s behind on a 1800s interval" sementara
    terminalnya connected, tick terakhirnya berumur 3 detik, dan `history.load`
    mengembalikan bar tutup terakhir yang benar.
    """
    candles = _series()
    as_of = _last_before_break(candles)
    # Di tengah jeda, dan satu detik sebelum bar berikutnya. Keduanya sehat.
    for now in (as_of + 2 * STEP, as_of + 3 * STEP - 1):
        assert blockers(_resp(as_of, candles), now=now) == [], now


def test_the_same_lag_at_a_trading_hour_still_blocks():
    """Perbaikannya tidak boleh mematikan cek-nya.

    Selisih jam dinding yang SAMA di jam perdagangan normal harus tetap
    memblokir, atau yang diperbaiki bukan alarm palsunya tapi alarmnya.
    """
    candles = _series()
    as_of = _last_before_break(candles) - 6 * STEP  # jam perdagangan normal
    got = blockers(_resp(as_of, candles), now=as_of + 3 * STEP - 1)
    assert got, got
    # Satu slot, jadi tunggal. Jamak/tunggalnya ikut dites karena teks ini
    # masuk ke journal apa adanya.
    assert "1 bar has closed" in got[0], got


def test_one_normal_week_is_enough_to_call_it_missing():
    """Arahnya konservatif, dan itu disengaja.

    Sebuah slot dianggap punya preseden kalau ada bar di sana pada MINGGU MANA
    PUN dari empat yang dicek. Jadi satu minggu normal saja sudah cukup untuk
    membuat diamnya dihitung sebagai kehilangan, dan yang dilewati hanya jeda
    yang keempat minggu itu semuanya diam.
    """
    candles = _series()
    as_of = _last_before_break(candles)
    # Tambahkan satu bar di slot jeda pada SATU minggu sebelumnya saja.
    slot = as_of + STEP
    candles.append({"time": slot - WEEK})
    candles.sort(key=lambda c: c["time"])
    got = blockers(_resp(as_of, candles), now=as_of + 3 * STEP - 1)
    assert got, "satu preseden saja harus cukup untuk memblokir"


def test_without_a_week_of_history_it_says_which_check_answered():
    """Preseden tidak bisa diuji tanpa riwayat, dan itu harus TERTULIS.

    Jatuh ke aturan jam dinding boleh; melaporkannya seolah preseden sudah
    diperiksa tidak. Teks penolakan masuk ke journal apa adanya, jadi ia harus
    mengatakan cek mana yang menjawab.
    """
    got = blockers(response(), now=AS_OF + 2 * STEP + 1)
    assert got and "riwayat kurang dari satu minggu" in got[0], got


def test_the_refusal_counts_bars_not_seconds():
    """Angkanya harus BAR, karena itu pertanyaan yang sebenarnya diajukan.

    Detik yang hilang tidak memberi tahu berapa yang terlewat saat instrumennya
    berhenti di tengah. Lag jam dinding tetap dicetak, karena ia yang menjawab
    "seberapa lama diam", tapi keputusannya dibuat pada hitungan bar.
    """
    candles = _series()
    as_of = _last_before_break(candles) - 6 * STEP
    # `now = as_of + 5*step` menutup slot k=1,2,3: close-nya masing-masing
    # `as_of + 2,3,4 * step`, semuanya di bawah `now`. Slot k=4 tutup TEPAT di
    # `now` dan itu saat terakhir sebelum close-nya, bukan close yang terlewat.
    got = blockers(_resp(as_of, candles), now=as_of + 5 * STEP)
    assert got
    assert "3 bars have closed" in got[0], got
    assert "punya preseden di" in got[0], got

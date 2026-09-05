"""Kontrak antara sisi MQL5 dan tool Python yang mengemudikannya.

Dua hal di seam ini gagal DIAM-DIAM, dan keduanya sudah pernah terjadi:

  1. MT5 mengabaikan key yang tidak dikenal di sebuah `.set` tanpa satu pesan
     pun, dan memakai compiled default untuk input yang tidak disebut. Jadi
     sebuah `.set` yang kurang satu baris menghasilkan run yang hijau dengan
     input yang TIDAK tercatat - yang persis lubang reproducibility yang
     `tools/mt5_backtest.py` dibangun untuk menutupnya.
  2. Sebuah gate yang mencetak vonis tanpa exit code melaporkan merah sebagai
     hijau ke setiap pembungkus yang membacanya. Ketiga `ea_parity*` melakukan
     itu sampai 1 September 2026, dan terbukti: mencabut test "last" dari port
     referensi order block memberi 414 dari 415 mismatch dan exit 0.

Diperiksa dari Python karena Python yang memegang daftarnya. Tidak ada compiler
MQL5 di jalur test, jadi yang dibaca teks source-nya, sama seperti
`test_frontend_defaults.py` membaca TypeScript.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MQL5 = Path(__file__).resolve().parents[2] / "mql5" / "ZonelabSupplyDemand"
TOOLS = Path(__file__).resolve().parents[1] / "tools"

#: Gate yang mencetak vonis dan karena itu harus menutupnya dengan exit code.
GATES = ("ea_parity.py", "ea_parity_ob.py", "ea_parity_fvg.py", "mqh_parity.py",
         "qt_clock_parity.py")


def _inputs(expert: str) -> set[str]:
    source = (MQL5 / f"{expert}.mq5").read_text(encoding="utf-8")
    return set(re.findall(r"^input\s+\w+\s+(Inp\w+)", source, re.M))


def test_every_ea_input_is_recorded_in_the_set_file():
    """`SHIPPED` must name every input its EA declares, and no others.

    An input the dict omits is an input the `.set` omits, and MT5 then silently
    uses the compiled default - so the run happens at a setting nobody wrote
    down. An input the dict invents is written to the `.set` and silently
    ignored, so the run happens at a setting that looks recorded and was not.
    Both directions produce a green run and a false record, which is why both
    are asserted.
    """
    from tools.mt5_backtest import SHIPPED

    problems = []
    for expert, declared in SHIPPED.items():
        real = _inputs(expert)
        missing = sorted(real - set(declared))
        invented = sorted(set(declared) - real)
        if missing:
            problems.append(f"{expert}: tidak tercatat di SHIPPED {missing}")
        if invented:
            problems.append(f"{expert}: di SHIPPED tapi tidak ada di EA {invented}")
    assert not problems, "\n".join(problems)


def test_every_expert_the_driver_knows_about_exists():
    """A name in `SHIPPED` with no .mq5 beside it fails at run time, not here.

    `tools/mt5_backtest.py` writes the ini before it launches anything, so an
    expert that does not exist produces a tester that starts, finds nothing, and
    times out after an hour with "NO REPORT" - which reads exactly like a cell
    that crashed.
    """
    from tools.mt5_backtest import SHIPPED

    missing = sorted(e for e in SHIPPED if not (MQL5 / f"{e}.mq5").exists())
    assert not missing, f"terdaftar di driver, file .mq5-nya tidak ada: {missing}"


@pytest.mark.parametrize("name", GATES)
def test_a_gate_that_prints_a_verdict_also_exits_on_it(name):
    """Printing PARITY FAIL and returning 0 is worse than not checking.

    The three `ea_parity*` gates did exactly that until 1 September 2026, and
    the defect was not theoretical: with the "last" test removed from the order
    block reference port they reported 414 mismatches out of 415 and still
    exited 0, so every wrapper reading the status saw green on a red run.
    """
    source = (TOOLS / name).read_text(encoding="utf-8")
    assert "PARITY FAIL" in source or "MQH PARITY FAIL" in source, (
        f"{name} tidak lagi mencetak vonis gagal; kalau memang begitu, hapus "
        "ia dari GATES supaya test ini tidak lolos secara hampa"
    )
    assert re.search(r"raise SystemExit\(", source), (
        f"{name} mencetak vonis gagal tanpa exit code, jadi run merah "
        "terlaporkan hijau"
    )


def test_every_registered_detector_is_ported_or_written_down_as_not():
    """A sixth detector cannot slip into the registry unmeasured and unnoticed.

    `app/detect/__init__.py` warns at its own bottom that a second list of layer
    ids drifts silently, and this project has paid for exactly that twice: a
    layer added to `app/layers.py` left `e2e/wiring.mjs` red for two commits,
    and the `wyckoff` slider left `e2e/sweep.mjs` red for twenty four.
    `tools/mqh_parity.py` holds such a list - which detectors have an MQL5 dump
    to compare against - so it is the same hazard in a third place.

    What this does NOT demand is that every detector be ported. Zonelab may
    legitimately draw things MT5 does not. What it demands is that the decision
    be WRITTEN: a new detector lands in PORTED with a dump file, or in UNPORTED
    with a reason. "Its precision was never measured" and "its precision was
    measured and passed" must not look the same from the outside.
    """
    from app.layers import LAYERS
    from tools import mqh_parity

    # Daftar bentuk DITEMUKAN, bukan dieja. Versi sebelumnya mengimpor keempat
    # dict itu satu per satu, yang berarti bentuk keenam bisa mendarat di
    # `mqh_parity` dan setiap layer di dalamnya kembali terhitung tidak
    # tercatat - atau lebih buruk, seorang penulis menambahkan dict-nya ke
    # impor DAN ke kalimat assert-nya lalu lupa yang ketiga. Itu persis pola
    # sensus-yang-harus-disunting-tangan yang sudah dua kali membuat harness di
    # repo ini merah tanpa ada yang tahu: `e2e/wiring.mjs` selama dua commit,
    # dan sensus slider `e2e/sweep.mjs` selama 24.
    lists = {
        name: set(getattr(mqh_parity, name))
        for name in dir(mqh_parity)
        if name == "UNPORTED" or name.startswith("PORTED")
    }
    assert "UNPORTED" in lists and "PORTED" in lists, (
        f"nama dict di mqh_parity berubah, sensus ini jadi hampa: {sorted(lists)}"
    )
    accounted = set().union(*lists.values())
    # SETIAP LAYER, BUKAN HANYA FAMILY ICT, dan itu lubang yang ditutup
    # 2 September 2026. Versi sebelumnya menyaring `layer.family == "ICT"`,
    # jadi sembilan layer di luar family itu tidak pernah dituntut punya entri:
    # `session` dan `dfr` family Quarterly Theory sementara EMPAT klausa
    # checklist berdiri di atas keduanya dan `dfr_side` satu-satunya dari tujuh
    # belas yang melewati ambang, plus enam layer tanpa family sama sekali.
    #
    # Untuk kesembilan itu "presisinya belum diukur" dan "presisinya terukur
    # dan lolos" terlihat sama dari luar, yang adalah persis keadaan yang
    # docstring di bawah ini ada untuk mencegah - dan penyaring family-nya
    # sendiri yang membuatnya bertahan.
    every = {layer.id for layer in LAYERS}

    unaccounted = sorted(every - accounted)
    assert not unaccounted, (
        f"layer yang tidak ada di satu pun dari {sorted(lists)}, jadi "
        "presisinya tidak diukur dan tidak ada yang mencatatnya: "
        f"{unaccounted}"
    )
    known = {layer.id for layer in LAYERS}
    stale = sorted(accounted - known)
    assert not stale, f"tercatat di mqh_parity tapi bukan layer: {stale}"

    # Sebuah nama tidak boleh muncul di dua daftar: "diport" dan "sengaja tidak
    # diport" adalah pernyataan yang saling meniadakan, dan sebuah nama di
    # keduanya berarti salah satunya sudah basi tanpa ada yang tahu yang mana.
    names = sorted(lists)
    pairs = tuple(
        (a, b, lists[a] & lists[b])
        for i, a in enumerate(names) for b in names[i + 1:]
    )
    for left, right, overlap in pairs:
        assert not overlap, f"ada di {left} DAN {right}: {sorted(overlap)}"

    # Setiap alasan harus benar-benar sebuah alasan. Sebuah string kosong lolos
    # dict tapi tidak memberi tahu pembaca apa pun, yang mengembalikan keadaan
    # yang test ini ada untuk mencegah.
    thin = sorted(
        n for n, why in mqh_parity.UNPORTED.items() if len(why.strip()) < 40
    )
    assert not thin, f"terdaftar tidak diport tanpa alasan yang bisa dibaca: {thin}"


# --------------------------------------------------------------------------
# QTClock.mqh menyalin empat batas sesi dan sepuluh rantai dari sisi Python.
#
# KENAPA INI PERLU DIIKAT. `mql5/ZonelabSupplyDemand/QTClock.mqh` dan
# `app/qt.py` mengimplementasikan aritmetika yang SAMA di dua bahasa, dan
# keduanya dipakai untuk mengukur klaim yang sama di dua venue. Kalau salah
# satunya bergeser, kedua venue berhenti mengukur objek yang sama dan tidak
# ada yang gagal: angkanya tetap keluar, cuma tidak lagi sebanding. Itu persis
# bentuk kegagalan `docs/mt5_python_parity.json` yang menemukan 6 dari 8 sel
# tidak sepakat.
QT_CLOCK = MQL5 / "QTClock.mqh"


def _define(name: str) -> int:
    match = re.search(rf"^#define\s+{name}\s+(\d+)", QT_CLOCK.read_text(
        encoding="utf-8"), re.M)
    assert match, f"{name} tidak ada di QTClock.mqh"
    return int(match.group(1))


def test_session_boundaries_match_the_python_side():
    """Empat batas sesi, dua salinan, satu angka masing-masing."""
    from app import qt

    assert _define("QT_ASIA_START") == qt.SOURCE_ASIA_START
    assert _define("QT_LONDON_START") == qt.SOURCE_LONDON_START
    assert _define("QT_NYAM_START") == qt.SOURCE_NYAM_START
    assert _define("QT_NYPM_START") == qt.SOURCE_NYPM_START


def test_high_prob_chains_match_the_python_side():
    """Sepuluh rantai, dan mereka harus sepuluh yang sama di tiga tempat.

    `sequence.HIS_LIST` adalah otoritasnya; `app/qt.py:SOURCE_HIGH_PROB` dan
    daftar hardcoded di `QTClock.mqh` adalah salinannya.
    """
    from app import qt
    from app.sequence import HIS_LIST

    source = QT_CLOCK.read_text(encoding="utf-8")
    block = source[source.index("bool QTHighProbChain"):]
    in_mql5 = set(re.findall(r"code==(\d{3})", block))

    assert in_mql5 == set(HIS_LIST), sorted(in_mql5 ^ set(HIS_LIST))
    assert qt.SOURCE_HIGH_PROB == HIS_LIST


def test_the_two_grids_are_still_ninety_minutes_apart():
    """Grid repo (18:00) dan grid sumber (19:30) TIDAK boleh menyatu.

    Kalau suatu hari keduanya sepakat, salah satu sudah diubah, dan setiap
    angka yang membandingkan `qt_sequence` dengan `qt_sequence_src` berhenti
    punya arti tanpa satu test pun merah.
    """
    from app import clock, qt
    from app.quarters import quarters

    when = clock.ny_wall(2026, 9, 2, 6, 30)
    repo = [q.label for q in quarters("day", when, when)]
    assert repo == ["Q3"]
    assert qt.source_chain(when)[1] == 2


def _between(source: str, start: str, end: str) -> str:
    """Potongan source antara dua penanda, komentar dan baris kosong dibuang."""
    # `index` melempar ValueError yang tidak menyebut apa yang hilang, dan gate
    # ini dibaca orang yang sedang mencari kenapa lengan kontrolnya berubah.
    assert start in source, f"penanda awal hilang dari source: {start!r}"
    head = source.index(start)
    assert end in source[head:], f"penanda akhir hilang setelah {start!r}: {end!r}"
    body = source[head:source.index(end, head)]
    return "\n".join(
        line.strip() for line in body.splitlines()
        if line.strip() and not line.strip().startswith("//")
    )


def test_zonelabqt_trade_path_is_still_a_copy_of_zonelabsd():
    """Lengan kontrol ZonelabQT harus benar benar ZonelabSD.

    ZonelabQT ada untuk mengukur SATU hal: gerbang waktu Quarterly Theory di
    depan entry yang sudah ada. Dengan keempat filter di nol ia wajib memberi
    angka yang sama dengan ZonelabSD, dan lengan itulah kontrolnya.

    Kalau seseorang menyunting geometri entry, stop, target atau ukuran lot di
    salah satu file saja, kontrolnya berhenti jadi kontrol dan SETIAP
    perbandingan lengan berubah arti - tanpa satu pun angka terlihat aneh,
    karena kedua sisi tetap menghasilkan report yang wajar. Bentuk kegagalan
    yang sama dengan `docs/mt5_python_parity.json`: baru ketahuan setelah ada
    yang membandingkan.

    Yang diikat adalah JALUR UANGNYA: ukuran lot, dan blok yang memasang order.
    """
    sd = (MQL5 / "ZonelabSD.mq5").read_text(encoding="utf-8")
    qt = (MQL5 / "ZonelabQT.mq5").read_text(encoding="utf-8")

    assert _between(sd, "double RiskLots(", "//+---") ==            _between(qt, "double RiskLots(", "//+---"),            "RiskLots berbeda: lot kedua EA tidak lagi sebanding"

    assert _between(sd, "double lots = RiskLots(risk);", "MarkOrdered(id);") ==            _between(qt, "double lots = RiskLots(risk);", "MarkOrdered(id);"),            "blok pemasangan order berbeda: lengan kontrol bukan kontrol lagi"

    # Dan gerbangnya harus benar benar ada, kalau tidak test di atas lolos
    # secara hampa pada dua file yang identik.
    assert "QTGateOpen(time_[n-1])" in qt
    assert "QTGateOpen" not in sd


def test_trade_parser_reproduces_the_report_net():
    """P/L per trade yang dijumlahkan HARUS sama dengan net di report yang sama.

    Ini gate yang menangkap cacat pemasangan deal, dan ia sudah menangkap satu:
    versi pertama `tools/mt5_trades.py` memasangkan lewat `Comment`, dapat
    jumlah trade yang BENAR, lalu kehilangan seluruh komisi masuk karena deal
    `out` membawa alasan tutup (`sl 4342.452`) dan bukan id zona. Jumlah trade
    yang cocok adalah persis jenis bukti yang membuat cacat itu lolos.

    Diperiksa pada SETIAP report yang ada di repo, bukan pada satu yang dipilih.
    """
    import re as _re

    from tools.mt5_backtest import parse_report
    from tools.mt5_trades import read

    # REPORT `.htm` TIDAK IKUT GIT, dan itu keadaan repo ini apa adanya:
    # `.gitignore` baris 112 mengecualikan `reports/*.htm` sementara docstring
    # `tools/mt5_backtest.py` menulis bahwa report disalin ke sana "supaya ikut
    # masuk git". Keduanya tidak bisa benar bersamaan; yang berlaku adalah
    # `.gitignore`. Jadi di clone bersih tidak ada apa pun untuk diperiksa, dan
    # gate ini SKIP dengan alasannya alih-alih lolos diam-diam. Skip terbaca
    # berbeda dari pass di ringkasan pytest, dan itu bedanya dengan gate hampa.
    reports = sorted((MQL5 / "reports").glob("*.htm"))
    if not reports:
        pytest.skip("tidak ada reports/*.htm di pohon ini; jalankan "
                    "tools.mt5_backtest dulu, atau baca .gitignore baris 112")

    checked = 0
    for path in reports:
        summary = parse_report(path)
        net = summary.get("Total Net Profit")
        count = summary.get("Total Trades")
        if not net or not count:
            continue
        net = float(_re.sub(r"[^\d.\-]", "", net.replace(" ", "")))
        values = read(path.stem)
        assert len(values) == int(count), (path.stem, len(values), count)
        assert abs(sum(values) - net) < 0.01, (path.stem, sum(values), net)
        checked += 1
    assert checked >= 1, "tidak ada report yang bisa diperiksa"

"""Varian aturan order block, diukur di rig yang sama dengan detector aslinya.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.ob_variants

KENAPA. `docs/QA-OB-GATE.md` mengukur GERBANG order block dan menemukan
profit factor 0,985 tanpa gerbang, naik ke 1,166 dengan lantai 2,5 ATR. Jadi
detector-nya sendiri tidak menghasilkan edge; yang menghasilkan adalah
penyaringnya. Pertanyaan berikutnya bukan "ambang mana", melainkan "ATURAN
DETEKSINYA yang mana yang salah", dan itu belum pernah disapu satu kali pun.

APA YANG DISAPU, dan semuanya diregistrasi sebelum angkanya dilihat:

  A  baseline                 aturan yang dikirim hari ini
  B  displacement_atr         ambang MASUK, bukan gerbang. Berbeda dari gerbang
                              departure: yang ini menentukan apa yang jadi
                              kotak, yang itu menyaring kotak yang sudah jadi
  C  displacement_bars        jendela impuls, 3 dan 8 lawan 5
  D  require_structure_break  memangkas populasi 74 persen menurut catatan
                              layer-nya sendiri, dan hasilnya TIDAK PERNAH
                              diukur lawan outcome
  E  body-box                 kotak dari badan lilin, bukan rentang penuh.
                              Ini mengubah JARAK STOP, dan karena R
                              dinormalisasi terhadap risk ia mengubah setiap
                              angka R sekaligus

VARIAN E TIDAK MENYENTUH `app/`. Detectornya hidup di berkas ini dan
disuntikkan ke `DETECTORS` sementara, trik yang sama yang
`tools/volume_imbalance.py` dan `detectors_costed.resolved_as` sudah pakai.
Sebuah parameter produksi baru untuk sebuah eksperimen adalah cara sebuah
percobaan berubah jadi permukaan yang harus didukung selamanya.

SEL DIPATOK DI 30m. `docs/QA-OB-GATE.md` mengukur profit factor per timeframe
dan hanya 30m yang di atas 1 dengan walk-forward 8 dari 8: 15m impas di 0,999,
4h 0,813 dan 1d 0,720. Menyapu varian di timeframe yang baselinenya rugi
berarti mengukur mana yang paling sedikit rugi, dan itu pertanyaan yang
berbeda. Dua sel yang sama dengan `tools/fvg_filter_compare.py`, supaya kedua
sapuan bisa diletakkan bersebelahan.

ATURAN LULUS, ditulis sebelum angkanya dilihat. Sebuah varian dinyatakan LEBIH
BAIK dari baseline hanya bila exp_r-nya lebih tinggi DAN walk-forward-nya 8
dari 8 DAN n-nya masih di atas `MIN_GROUP`. Varian dengan exp_r tertinggi dan
n=40 bukan temuan.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys

import numpy as np

from app.detect import DETECTORS
from app.detect.imbalance import (
    EPS,
    _arrays,
    _finish,
    _present,
    detect_order_block,
)
from app.detect.structure import breaks
from app.indicators import wilder_atr
from app.models import Candle, ImbalanceParams, Zone, ZoneKind, ZoneSide
from tools.conditioned import _critical_t
# `cell_rows` DARI `gate_sweep`, BUKAN DARI `detectors_costed`. Yang asli
# membaca `FINER[interval]`, dan peta itu berhenti di 4h - jadi set sel `all`
# meledak dengan `KeyError: '1d'`. `gate_sweep` sudah memegang peta yang
# diperluas beserta alasan kenapa 1m dan 5m tidak bisa ditambahkan.
from tools.detectors_costed import FOLDS, one_sample_t, welch
from tools.gate_sweep import CELL_SETS
from tools.gate_sweep import cell_rows as _cell_rows

CELLS = CELL_SETS["30m"]
MIN_FOLD = 20
MIN_GROUP = 30
CACHE = pathlib.Path(__file__).resolve().parents[2] / "docs" / "ob_variants_rows_cache.json"


def detect_body_box(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """`detect_order_block`, tetapi kotaknya dari BADAN lilin block."""
    return _run(candles, params, body_box=True, close_impulse=False, one_per_impulse=False)


def _run(
    candles: list[Candle], params: ImbalanceParams, *,
    body_box: bool, close_impulse: bool, one_per_impulse: bool,
    body_midpoint: bool = False, min_box_range: float = 0.0,
) -> tuple[list[Zone], dict[str, float]]:
    """`detect_order_block`, tetapi kotaknya dari BADAN lilin block.

    Satu baris yang berbeda dari aslinya, dan disalin alih alih diparameterkan
    supaya `app/` tidak menumbuhkan knob untuk sebuah percobaan. Deteksinya
    identik: kandidat, ambang impuls, dan tes "terakhir" semuanya sama, dan
    hanya `top`/`bottom` yang diserahkan ke `_finish` yang berubah.

    KENAPA INI BUKAN PERUBAHAN KOSMETIK. Stop duduk di luar distal plus buffer
    0,25 ATR dan target di zona lawan terdekat, jadi risk per unit ikut tinggi
    kotak. Sebuah lilin block dengan sumbu panjang memberi kotak tinggi, stop
    jauh, dan R kecil untuk gerakan yang sama persis. Badan lilin membuang
    sumbu itu.
    """
    n = len(candles)
    stats: dict[str, float] = {
        "bars": n, "candidates": 0, "rejected_weak_move": 0,
        "rejected_not_last": 0, "rejected_zero_body": 0,
        "rejected_no_structure_break": 0, "rejected_state_filter": 0,
    }
    if n < params.atr_period + params.displacement_bars + 2:
        return _present([], params, stats, int(candles[-1].time) if candles else 0)

    time, open_, high, low, close = _arrays(candles)
    atr = wilder_atr(high, low, close, params.atr_period)

    # DUA HAL YANG ASLINYA LAKUKAN DAN SALINAN PERTAMA BERKAS INI LEWATKAN:
    # `breaks()` mengembalikan tuple `(breaks, swings)` jadi indeks `[0]`
    # wajib, dan event `SWEEP` DIBUANG karena sapuan adalah peristiwa yang
    # berlawanan dengan break, bukan versi lemahnya. Sebuah varian yang
    # berbeda dari aslinya di tempat yang tidak disengaja mengukur hal lain.
    breaks_at: dict[int, list] = {}
    if params.require_structure_break:
        for event in breaks(candles, params.structure_n, params.structure_n)[0]:
            if event.kind != "SWEEP":
                breaks_at.setdefault(event.index, []).append(event)

    found: list = []
    for i in range(1, n - params.displacement_bars - 1):
        scale = float(atr[max(0, i - 1)])
        if scale <= EPS:
            continue
        bearish = close[i] < open_[i]
        window = slice(i + 1, i + 1 + params.displacement_bars)
        if bearish:
            reach = close[window].max() if close_impulse else high[window].max()
            move = (float(reach) - float(close[i])) / scale
            side = ZoneSide.DEMAND
        elif close[i] > open_[i]:
            reach = close[window].min() if close_impulse else low[window].min()
            move = (float(close[i]) - float(reach)) / scale
            side = ZoneSide.SUPPLY
        else:
            continue

        stats["candidates"] += 1
        if move < params.displacement_atr:
            stats["rejected_weak_move"] += 1
            continue

        nxt = i + 1
        turned = close[nxt] > open_[nxt] if bearish else close[nxt] < open_[nxt]
        if not turned:
            stats["rejected_not_last"] += 1
            continue

        # SATU-SATUNYA BARIS YANG BERBEDA. Badan, bukan rentang penuh. Sebuah
        # doji sudah ditolak di atas, jadi badan nol di sini tidak mungkin -
        # tetapi dijaga tetap, karena "tidak mungkin menurut alur di atas"
        # adalah cara pembagian nol masuk ke produksi.
        if body_midpoint:
            # ENTRY DI TENGAH BADAN, STOP TETAP DI LUAR SUMBU. Proximal adalah
            # tepi yang harga temui lebih dulu dan distal tepi pelindung, jadi
            # untuk demand `top` adalah entry dan `bottom` acuan stop - dan
            # sebaliknya untuk supply. Menaruh midpoint di sisi yang salah akan
            # memberi stop di tengah badan, yaitu kebalikan dari maksudnya.
            mid = float((open_[i] + close[i]) / 2.0)
            if side is ZoneSide.DEMAND:
                top, bottom = mid, float(low[i])
            else:
                top, bottom = float(high[i]), mid
        elif body_box:
            top = float(max(open_[i], close[i]))
            bottom = float(min(open_[i], close[i]))
        else:
            top, bottom = float(high[i]), float(low[i])
        if top - bottom <= EPS:
            stats["rejected_zero_body"] += 1
            continue

        if min_box_range > 0.0:
            # LANTAI TINGGI KOTAK, DIMEKARKAN SIMETRIS supaya titik tengahnya
            # tidak bergeser: sebuah lantai yang cuma menaikkan `top` akan
            # memindahkan entry demand dan mengubah dua hal sekaligus.
            #
            # Acuannya RENTANG LILIN ITU SENDIRI, bukan ATR. Versi ATR ditulis
            # lebih dulu dan `tests/test_no_repaint.py` menolaknya: `wilder_atr`
            # adalah rata rata berjalan yang disemai dari bar pertama, jadi ATR
            # di bar absolut yang sama BERBEDA antar jendela, dan 4 dari 424
            # kotak bergeser ~1e-5 saat jendelanya tumbuh ke kiri. Rentang
            # lilin dihitung dari satu bar itu saja, jadi ia sama di jendela
            # mana pun.
            #
            # Ini pertanyaan GAMBAR yang tetap harus diukur karena ia menyentuh
            # geometri stop: risk per unit ADALAH tinggi kotak.
            # Digeser kembali ke dalam lilinnya, bukan dikecilkan; alasan dan
            # sensusnya di `app/detect/imbalance.py` pada titik pasangnya.
            floor = (float(high[i]) - float(low[i])) * min_box_range
            short = floor - (top - bottom)
            if short > 0:
                top += short / 2.0
                bottom -= short / 2.0
                if top > high[i]:
                    bottom -= top - float(high[i])
                    top = float(high[i])
                elif bottom < low[i]:
                    top += float(low[i]) - bottom
                    bottom = float(low[i])

        impulse = 1 if bearish else -1
        born = i + params.displacement_bars
        break_time = None
        if params.require_structure_break:
            hit = next(
                (
                    e
                    for k in range(1, params.structure_break_bars + 1)
                    for e in breaks_at.get(i + k, ())
                    if e.direction == impulse
                ),
                None,
            )
            if hit is None:
                stats["rejected_no_structure_break"] += 1
                continue
            break_time, born = hit.time, max(born, hit.index)

        zone = _finish(
            ZoneKind.OB, side, top, bottom, i, born,
            time, high, low, close, atr, params, move,
            leg=None,
            break_time=break_time,
        )
        if zone is not None:
            found.append((i, side, zone))

    if one_per_impulse:
        # PERTAHANKAN YANG PALING AKHIR, karena definisinya berbunyi "lilin
        # berlawanan TERAKHIR sebelum impuls". Sebuah block yang punya block
        # sesisi lain dalam `displacement_bars` SESUDAHNYA bukan yang terakhir.
        kept = []
        for pos, (idx, side, zone) in enumerate(found):
            later = any(
                j > idx and j - idx <= params.displacement_bars and s2 is side
                for j, s2, _z in found[pos + 1:]
            )
            if later:
                stats["rejected_superseded"] = stats.get("rejected_superseded", 0) + 1
            else:
                kept.append(zone)
        found_zones = kept
    else:
        found_zones = [z for _i, _s, z in found]
    return _present(found_zones, params, stats, int(candles[-1].time) if candles else 0)



def detect_close_impulse(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """`detect_order_block`, tetapi impulsnya diukur ke CLOSE ekstrem.

    DIUKUR SEBELUM DITULIS, dan itu alasan varian ini ada. Pada 20.000 bar
    XAUUSD 30m, 1.236 dari 4.041 order block yang lolos ambang impuls, yaitu
    30,6 persen, lolos HANYA karena sebuah sumbu: tidak ada satu pun close di
    jendela lima bar yang pernah mengonfirmasi geraknya.

    Dan berkas aslinya sudah tidak konsisten soal ini dengan dirinya sendiri.
    Jalur `require_structure_break` MEMBUANG event `SWEEP` dengan alasan
    tertulis bahwa sumbu yang menembus level lalu ditutup kembali di dalam
    adalah peristiwa yang BERLAWANAN dengan struktur yang jebol. Jalur impuls
    default menerima bentuk yang persis sama sebagai bukti displacement.
    """
    return _run(candles, params, body_box=False, close_impulse=True,
                one_per_impulse=False)


def detect_one_per_impulse(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Satu block per impuls per sisi, yaitu yang PALING AKHIR.

    DIUKUR SEBELUM DITULIS. Pada deret yang sama, 1.196 pasangan order block,
    29,6 persen, lahir dalam lima bar satu sama lain di sisi yang sama, dan 853
    di antaranya, 21,1 persen, box-nya tumpang tindih. Itu satu displacement
    yang dilaporkan sebagai beberapa kotak, jadi outcome-nya berkorelasi dan n
    yang terukur lebih besar dari jumlah peristiwa yang sebenarnya terjadi.

    Tes "LAST" yang ada hanya memeriksa lilin BERIKUTNYA, jadi satu lilin
    penyela sudah cukup memutus jaminannya: bearish, bearish, satu bullish
    kecil, bearish, lalu rally, dan kedua bearish pertama lolos sendiri
    sendiri walau hanya yang terakhir yang benar benar "lilin berlawanan
    terakhir sebelum impuls".
    """
    return _run(candles, params, body_box=False, close_impulse=False,
                one_per_impulse=True)


def detect_legacy(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Aturan SEBELUM 6 September 2026: rentang penuh, impuls dari sumbu.

    Ada sebagai lengan eksplisit karena lengan A melacak `detect_order_block`
    yang HIDUP. Selama produksi masih memakai aturan lama keduanya sama dan
    lengan ini terasa mubazir; begitu produksi berubah, ia satu satunya cara
    membaca kembali angka sebelumnya tanpa checkout commit lama.

    Ketiga pilihan disebut EKSPLISIT karena `_run` sengaja tidak memberi mereka
    default: sebuah lengan yang lupa menyebut salah satunya harus gagal keras,
    bukan diam diam mengukur aturan yang berbeda dari namanya. Versi pertama
    lengan ini memanggil `_run(candles, params)` dan langsung TypeError.
    """
    return _run(candles, params, body_box=False, close_impulse=False,
                one_per_impulse=False)


def detect_all_three(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Ketiganya sekaligus, karena tiga perbaikan bisa saling meniadakan."""
    return _run(candles, params, body_box=True, close_impulse=True,
                one_per_impulse=True)


def detect_floored(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Aturan yang dikirim hari ini, plus lantai tinggi kotak 0,15 rentang lilin.

    Angka 0,15 dipilih dari sensus, bukan dari selera: pada XAUUSD 1h ia
    menaikkan kotak tertipis dari 0,0008 ATR ke 0,0364 ATR dan menyisakan 5
    kotak di bawah 0,05 ATR (dari 63), sambil mengikat hanya 17,0 persen
    kotak. Share 0,20 menyisakan 1 tapi mengikat 22,9 persen.
    """
    return _run(candles, params, body_box=True, close_impulse=True,
                one_per_impulse=False, min_box_range=0.15)


def detect_midpoint_and_close(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Entry di tengah BADAN, stop tetap di luar SUMBU, plus impuls dari close.

    Arm ketiga yang riset luar sebut tidak pernah diukur siapa pun: dari enam
    sumber yang punya kode terbuka, nol membandingkan geometri box secara
    numerik. `ictkillzone.com` memisahkan keduanya sebagai doktrin - badan untuk
    zona entry, sumbu penuh untuk stop - tanpa satu angka pun di belakangnya.

    Bedanya dengan body-box: di sana stop ikut menyempit bersama entry, jadi
    R naik tetapi harga lebih sering menyentuh stop. Di sini entry menyempit
    SENDIRIAN dan stop tetap di luar sumbu, jadi ia membeli harga masuk yang
    lebih baik tanpa memperketat stop. Kedua efeknya berlawanan dan itulah
    kenapa keduanya harus diukur terpisah.
    """
    return _run(candles, params, body_box=False, close_impulse=True,
                one_per_impulse=False, body_midpoint=True)


def detect_body_and_close(
    candles: list[Candle], params: ImbalanceParams
) -> tuple[list[Zone], dict[str, float]]:
    """Body-box PLUS impuls dari close, tanpa dedupe.

    SEL YANG HILANG DARI SAPUAN PERTAMA, dan ketiadaannya adalah cacat di
    rancangan sapuan itu, bukan di hasilnya. E dan F masing masing lolos aturan
    praregistrasi; satu satunya arm gabungan yang diuji adalah E+F+G, dan G
    ternyata MERUSAK (PF 0,813, walk-forward 1 dari 8). Jadi H gagal karena
    membawa G, dan pasangan yang sebenarnya menarik tidak pernah dijalankan.
    """
    return _run(candles, params, body_box=True, close_impulse=True,
                one_per_impulse=False)


#: Nama varian, detector-nya, dan parameternya.
#:
#: `None` sebagai detector berarti `detect_order_block` yang asli.
VARIANTS: list[dict] = [
        # LENGAN A MELACAK PRODUKSI, dan itu jebakan di cache. Kunci cache memuat
    # set sel dan nama lengan, TIDAK memuat kodenya, jadi baris A yang ditulis
    # sebelum detector-nya diganti akan disajikan lagi setelahnya tanpa satu
    # pesan pun - pada 6 September 2026 ia menyajikan PF 0,984 untuk kode yang
    # sudah 1,329. Namanya sekarang mengatakan apa yang ia lacak, dan aturan
    # lamanya dipatok di lengan L supaya ia tidak hilang.
    {"name": "A produksi saat ini", "fn": None, "p": {}},
    {"name": "B1 displacement_atr 1.0", "fn": None, "p": {"displacement_atr": 1.0}},
    {"name": "B2 displacement_atr 2.0", "fn": None, "p": {"displacement_atr": 2.0}},
    {"name": "B3 displacement_atr 2.5", "fn": None, "p": {"displacement_atr": 2.5}},
    {"name": "B4 displacement_atr 3.0", "fn": None, "p": {"displacement_atr": 3.0}},
    {"name": "C1 displacement_bars 3", "fn": None, "p": {"displacement_bars": 3}},
    {"name": "C2 displacement_bars 8", "fn": None, "p": {"displacement_bars": 8}},
    {"name": "D  require_structure_break", "fn": None,
     "p": {"require_structure_break": True}},
    {"name": "E  body-box", "fn": detect_body_box, "p": {}},
    {"name": "E+D body-box + structure", "fn": detect_body_box,
     "p": {"require_structure_break": True}},
    {"name": "F  impuls dari close", "fn": detect_close_impulse, "p": {}},
    {"name": "G  satu block per impuls", "fn": detect_one_per_impulse, "p": {}},
    {"name": "H  E+F+G bersama", "fn": detect_all_three, "p": {}},
    {"name": "I  E+F (tanpa dedupe)", "fn": detect_body_and_close, "p": {}},
    {"name": "J  midpoint entry + F", "fn": detect_midpoint_and_close, "p": {}},
    {"name": "K  I + lantai kotak 0,15 rentang", "fn": detect_floored, "p": {}},
    {"name": "L  aturan sebelum 6 Sep 2026", "fn": detect_legacy, "p": {}},
]
#: Bonferroni atas jumlah varian yang dibandingkan dengan baseline.
T_THRESHOLD = _critical_t(len(VARIANTS) - 1)


def walk_forward(rows: list[dict]) -> dict:
    """8 fold posisi relatif, di-purge seperti sapuan yang lain."""
    edges = np.linspace(0.0, 1.0, FOLDS + 1)
    folds = []
    for k in range(FOLDS):
        lo, hi = float(edges[k]), float(edges[k + 1])
        opened = [r for r in rows if lo <= r["pos"] < hi]
        kept = np.array([r["r"] for r in opened if r["exit_pos"] < hi])
        entry: dict = {"fold": k + 1, "n": int(kept.size)}
        entry["readable"] = kept.size >= MIN_FOLD
        if entry["readable"]:
            entry["exp_r"] = float(kept.mean())
        folds.append(entry)
    graded = [f for f in folds if f["readable"]]
    return {"graded": len(graded),
            "positive": sum(1 for f in graded if f["exp_r"] > 0)}


def rates(rows: list[dict]) -> dict:
    r = np.array([x["r"] for x in rows])
    if not r.size:
        return {"n": 0}
    wins = r[r > 0]
    losses = r[r <= 0]
    gross_loss = float(abs(losses.sum()))
    return {
        "n": int(r.size),
        "exp_r": round(float(r.mean()), 4),
        "t_vs_zero": round(one_sample_t(r), 3) if r.size > 1 else None,
        "win_rate": round(float(wins.size / r.size), 4),
        "profit_factor": round(float(wins.sum()) / gross_loss, 3) if gross_loss else None,
        "mean_win_r": round(float(wins.mean()), 4) if wins.size else None,
        "mean_loss_r": round(float(losses.mean()), 4) if losses.size else None,
    }


def run(variant: dict) -> dict:
    """Baris satu varian, di kedua sel, lewat rig yang sama."""
    params = ImbalanceParams(max_zones_per_side=0, show_broken=True, **variant["p"])
    real = variant["fn"] or detect_order_block
    original = DETECTORS["order_block"]
    DETECTORS["order_block"] = lambda candles, _ignored: real(candles, params)
    try:
        rows: list[dict] = []
        for symbol, interval in CELLS:
            with contextlib.redirect_stdout(sys.stderr):
                got, _span = _cell_rows("order_block", symbol, interval)
            rows.extend(got)
    finally:
        DETECTORS["order_block"] = original

    out = {"variant": variant["name"], **rates(rows)}
    if out.get("n", 0) >= MIN_GROUP:
        wf = walk_forward(rows)
        out["wf_positive"], out["wf_graded"] = wf["positive"], wf["graded"]
    # SEL IKUT DISIMPAN, bukan cuma R-nya. Versi pertama hanya menyimpan
    # daftar R, jadi run 12 sel menghasilkan angka gabungan dan pertanyaan yang
    # justru menyebabkan run itu dijalankan - apakah varian ini menyelamatkan
    # 4h dan 1d yang PF-nya 0,813 dan 0,720 - tidak bisa dijawab tanpa
    # mengulangnya. Empat field, dan tiga di antaranya sudah ada di baris itu.
    out["_rows"] = [
        {"cell": x["cell"], "r": x["r"], "pos": x["pos"], "exit_pos": x["exit_pos"]}
        for x in rows
    ]
    out["_r"] = [x["r"] for x in rows]
    return out


def main() -> int:
    global CELLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="30m", choices=sorted(CELL_SETS))
    ap.add_argument("--only", default="",
                    help="awalan nama varian, dipisah koma. Kosong berarti semua")
    args = ap.parse_args()
    CELLS = CELL_SETS[args.cells]
    wanted = tuple(x.strip() for x in args.only.split(",") if x.strip())
    todo = [v for v in VARIANTS
            if not wanted or v["name"].startswith(wanted)]
    print(f"  cells={args.cells} ({len(CELLS)} sel) varian={len(todo)}",
          file=sys.stderr)

    cached = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    results = []
    for v in todo:
        # KUNCI CACHE MEMUAT SET SELNYA. Tanpa itu hasil dua sel akan dibaca
        # sebagai hasil dua belas sel pada run berikutnya, dan tidak ada pesan
        # kesalahan yang akan muncul - cuma angka yang salah populasinya.
        key = f"{args.cells}|{v['name']}"
        if key in cached:
            r = cached[key]
            print(f"  {v['name']} dari cache, n={r.get('n')}", file=sys.stderr)
        else:
            print(f"  {v['name']}...", file=sys.stderr, flush=True)
            r = run(v)
            cached[key] = r
            CACHE.write_text(json.dumps(cached), encoding="utf-8")
        results.append(r)
        print(f"    n={r.get('n')} exp_r={r.get('exp_r')} WR={r.get('win_rate')} "
              f"PF={r.get('profit_factor')} wf={r.get('wf_positive')}/"
              f"{r.get('wf_graded')}", file=sys.stderr)

    # PER TIMEFRAME, karena sebuah varian yang menyelamatkan 30m dan
    # memperburuk 4h akan terbaca sehat di angka gabungan.
    for r in results:
        rows = r.get("_rows") or []
        per_tf: dict[str, dict] = {}
        for tf in sorted({x["cell"].split()[-1] for x in rows}):
            sub = [x for x in rows if x["cell"].endswith(f" {tf}")]
            per_tf[tf] = rates(sub)
            if len(sub) >= MIN_GROUP:
                wf = walk_forward(sub)
                per_tf[tf]["wf_positive"] = wf["positive"]
                per_tf[tf]["wf_graded"] = wf["graded"]
        r["per_timeframe"] = per_tf
        r.pop("_rows", None)

    base = results[0]
    base_r = np.array(base.pop("_r"))
    for r in results[1:]:
        arm = np.array(r.pop("_r"))
        if arm.size >= MIN_GROUP and base_r.size >= MIN_GROUP:
            r["welch_t_vs_baseline"] = round(welch(arm, base_r), 3)
            better = (
                r["exp_r"] > base["exp_r"]
                and r.get("wf_graded", 0) > 0
                and r.get("wf_positive") == r.get("wf_graded")
            )
            r["verdict"] = (
                "LEBIH BAIK dari baseline" if better and
                abs(r["welch_t_vs_baseline"]) >= T_THRESHOLD
                else "lebih baik tapi tidak signifikan" if better
                else "tidak lebih baik"
            )
        else:
            r["verdict"] = "tidak terukur, n di bawah MIN_GROUP"

    json.dump({
        "question": "aturan deteksi order block mana yang mengubah outcome",
        "cell_set": args.cells,
        "cells": [f"{s} {i}" for s, i in CELLS],
        "why_30m_only": (
            "docs/QA-OB-GATE.md: hanya 30m yang PF di atas 1 dengan walk-forward "
            "8 dari 8; 15m 0,999, 4h 0,813, 1d 0,720"
        ),
        "t_threshold_bonferroni": round(T_THRESHOLD, 4),
        "min_group": MIN_GROUP,
        "baseline": base,
        "variants": results[1:],
    }, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

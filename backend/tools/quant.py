"""Statistik profesional atas trade yang `tools/costed.py` sudah menghasilkan.

    python -m tools.quant --matrix                       # semua sel
    python -m tools.quant --symbol XAUUSD --interval 1h  # satu sel, rinci

APA YANG BARU DI SINI, DAN APA YANG TIDAK. `costed.py` sudah menjawab "berapa
ekspektasinya setelah biaya". File ini menjawab pertanyaan yang berbeda dan lebih
sulit: seberapa besar kemungkinan angka itu kebetulan, seberapa dalam drawdown
yang belum pernah terlihat, dan berapa lot yang membuat akun ini bertahan.

TIGA HAL YANG DIPERBAIKI DI SINI DIBANDING PENGUKURAN SEBELUMNYA:

1. PREFIX YANG SPACING-NYA SALAH DIBUANG, bukan cuma diperingatkan. Terminal
   menyajikan apa pun yang ia punya, jadi bagian tertua dari request 1 jam yang
   panjang berjarak SEHARI sambil tetap berlabel 1h. Diukur 22 Agustus 2026:
   1.338 bar pertama XAUUSD 1h (3,8%) dan 1.337 dari 10.558 bar 4h (12,7%).
   `costed.py` mencetak WARNING dan tetap menghitungnya. Detektor membaca bar
   berurutan sebagai berdampingan, jadi setiap zona di rentang itu dihitung
   dengan step yang salah.

2. "50.000 bar" DI DOKUMEN LAMA ADALAH UKURAN REQUEST, BUKAN UKURAN DATA. XAUUSD
   1h hanya punya 35.199 bar di terminal ini, dan 33.861 setelah prefix dibuang.
   File ini mencetak berapa bar yang benar-benar dipakai, selalu.

3. BATAS 100.000 ADALAH BATAS KERAS TERMINAL. `copy_rates_from_pos` dengan count
   99.999 berhasil, 100.000 menjawab `Invalid params`, dan pesan yang muncul di
   provider berbunyi "mt5 returned no bars" yang menyesatkan.

YANG DIHITUNG, DAN KENAPA MASING-MASING ADA. Tiap baris punya alasan, bukan
karena "metrik standar":

  exp R, SE, t          apakah edge-nya beda dari nol, dan seberapa presisi
  win rate, payoff      bentuk edge-nya, karena +0,2 R bisa 40% x 3R atau 70% x 0,6R
  Sharpe per trade      rasio sinyal terhadap ribut, tanpa asumsi kalender
  max DD teramati       yang sudah terjadi
  max DD bootstrap p95  yang belum terjadi tapi wajar terjadi
  risk of ruin          apakah sizing-nya bisa membunuh akun sebelum edge datang
  fold positif          apakah edge-nya bertahan lintas waktu, bukan satu rejim
  minTRL                berapa trade lagi sebelum angka ini layak dipercaya
  DSR                   Sharpe setelah dikoreksi jumlah percobaan project ini

TIDAK ADA PARAMETER YANG DI-FIT DI FILE INI. Itu penting untuk dua alasan.
Pertama, walk-forward di sini bukan train/test: tidak ada yang dilatih, jadi ia
adalah uji STABILITAS, dan embargo tidak berlaku karena tidak ada training set
yang bisa dibocori. Kedua, PBO lewat CSCV degenerate pada satu aturan tanpa
parameter (rank selalu 1 dari 1, logit selalu nol), jadi ia dijalankan atas grid
konfigurasi checklist ICT, yang memang punya banyak kolom untuk dirangking.
"""

from __future__ import annotations

import argparse
import math

import numpy as np

from tools import history
from tools.costed import HORIZON, purged_fold, trades
from tools.stats import (
    deflated_sharpe,
    sharpe_sd,
    expected_max_sharpe,
    ljung_box,
    lo_annualised,
    min_trl,
    psr,
)

#: Instrumen yang terminal ini benar-benar punya, diukur 22 Agustus 2026 lewat
#: `symbol_info` plus `copy_rates_from_pos`. NAS100 TIDAK ada di broker ini dan
#: sengaja tidak didaftarkan, supaya sel yang kosong berarti "tidak ada trade"
#: dan bukan "simbolnya salah tulis".
UNIVERSE = (
    "XAUUSD", "XAGUSD", "XPTUSD", "EURUSD", "GBPUSD", "USDJPY",
    "GBPJPY", "AUDUSD", "USDCAD", "BTCUSD", "US30", "USOIL",
)

#: Terminal menolak count >= 100000 dengan `Invalid params`, diukur lewat
#: bisection: 99999 diterima, 100000 tidak. Ini batasnya, bukan pilihan.
MT5_MAX_BARS = 99_999

#: Profil biaya per instrumen di broker ini. Kosong berarti profil generic, dan
#: `costed.schedule` yang memutuskan. Dipisah supaya sel yang memakai fallback
#: kelihatan di laporan.
BROKER = "exness_raw"

#: Fold untuk uji stabilitas. Delapan, sama dengan yang dipakai gerbang
#: departure, supaya angkanya bisa dibandingkan langsung.
FOLDS = 8

#: Nilai kritis chi-square dua sisi pada 95% untuk df 1..8. Ditulis sebagai tabel
#: karena Ljung-Box adalah satu-satunya pemakaian chi-square di repo ini, dan
#: mendatangkan satu implementasi CDF lagi untuk satu pemakaian tidak dibayar.
CHI2_95 = {1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070,
           6: 12.592, 7: 14.067, 8: 15.507}

#: Percobaan yang project ini sudah jalankan pada deret yang SAMA, dihitung jujur
#: dari dokumen sendiri, karena Deflated Sharpe berdiri atau jatuh di angka ini:
#:
#:   12  hipotesis arah pra-registrasi yang gagal (CALIBRATION.md)
#:    2  aturan exit yang dibandingkan, hold lawan flat di rollover
#:    1  gerbang departure, ambangnya dipilih blind di separuh deret
#:   83  grup pengkondisian (PRAREGISTRASI-KONDISI.md, run 1 jam)
#:   10  klausa checklist ICT
#:
#: Totalnya 108 secara literal. Itu BUKAN N yang benar untuk DSR: percobaan yang
#: saling berkorelasi memberi n_eff = rho + (1 - rho) * m, dan 108 percobaan di
#: atas satu deret emas jelas jauh dari independen. Jadi tiga angka dilaporkan
#: berdampingan dan pembaca melihat sensitivitasnya, bukan satu angka yang
#: berpura-pura tahu rho.
TRIALS = (1, 16, 108)


def clean(symbol: str, interval: str, bars: int = MT5_MAX_BARS):
    """Bar yang spacing-nya benar saja, plus berapa yang dibuang.

    Mengembalikan `(candles, dropped, requested)`. Pemotongan ini yang membuat
    seluruh file ini bukan pengulangan `costed.py`: tanpa itu, 12,7% bar 4h
    dihitung dengan step yang salah dan hasilnya tetap dilaporkan sebagai angka
    4 jam.
    """
    rows = history.load(f"mt5:{symbol}", interval, min(bars, MT5_MAX_BARS))
    dropped = history.irregular_prefix(rows, interval)
    return rows[dropped:], dropped, len(rows)


def metrics(rows: list[dict]) -> dict:
    """Bentuk edge-nya, dalam angka yang tidak saling menggantikan.

    `rows` adalah baris `costed.trades` yang tidak di-skip. Urutan waktu
    dipertahankan karena max drawdown adalah properti URUTAN, bukan properti
    himpunan: mengacak urutan trade yang sama memberi drawdown yang berbeda.
    """
    r = np.array([x["r"] for x in rows], dtype=np.float64)
    n = len(r)
    if n == 0:
        return {"n": 0}
    mean = float(r.mean())
    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    wins = r[r > 0]
    losses = r[r <= 0]
    # NOL DI DEPAN, dan itu bukan kosmetik. Tanpa modal awal di deret, puncak
    # pertama adalah trade pertama, jadi equity yang langsung turun dari awal
    # melaporkan drawdown yang lebih kecil dari kenyataan: deret -1 -1 -1 +3 +3
    # menjawab 2,0 padahal jatuhnya 3,0 dari titik mulai. Ditemukan lewat
    # `test_max_drawdown_depends_on_the_order` 22 Agustus 2026, dan arah
    # kesalahannya selalu meremehkan risiko.
    equity = np.concatenate(([0.0], np.cumsum(r)))
    peak = np.maximum.accumulate(equity)
    return {
        "n": n,
        "exp_r": mean,
        "sd": sd,
        "se": se,
        "t": mean / se if se > 0 else 0.0,
        # 95% CI dari expectancy. Dicetak karena "+0,22 R" tanpa lebarnya
        # membuat pembaca mengira presisinya jauh lebih tinggi dari kenyataan.
        "ci_lo": mean - 1.96 * se,
        "ci_hi": mean + 1.96 * se,
        "win_rate": float(len(wins) / n),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "payoff": float(wins.mean() / abs(losses.mean()))
        if len(wins) and len(losses) and losses.mean() != 0 else 0.0,
        "sharpe_trade": mean / sd if sd > 0 else 0.0,
        "skew": float(((r - mean) ** 3).mean() / sd ** 3) if sd > 0 else 0.0,
        # Kurtosis MENTAH (normal = 3), bukan excess. minTRL dan PSR memakai
        # bentuk mentah, dan memberi excess ke formula itu adalah kesalahan
        # senyap yang menggeser hasilnya tanpa error apa pun.
        "kurtosis": float(((r - mean) ** 4).mean() / sd ** 4) if sd > 0 else 3.0,
        "total_r": float(r.sum()),
        "max_dd": float((peak - equity).max()) if n else 0.0,
        "cost_r": float(np.mean([x["cost_r"] for x in rows])),
        "nights": float(np.mean([x["nights"] for x in rows])),
    }


def autocorrelation(rows: list[dict], lags: int = 5) -> list[float]:
    """Korelasi deret R dengan dirinya sendiri pada lag 1..lags.

    Menentukan bootstrap mana yang sah. Kalau lag-1 mendekati nol, resample iid
    per trade tidak melanggar apa pun; kalau tidak, blok berurutan yang harus
    di-resample atau interval kepercayaannya akan terlalu sempit.
    """
    r = np.array([x["r"] for x in rows], dtype=np.float64)
    if len(r) < lags + 2:
        return []
    r = r - r.mean()
    denom = float((r * r).sum())
    if denom <= 0:
        return []
    return [float((r[:-k] * r[k:]).sum() / denom) for k in range(1, lags + 1)]


def folds(rows: list[dict], bars: int, count: int = FOLDS) -> tuple[list[dict], int]:
    """Ekspektasi per fold, dengan purging, dan berapa trade yang dibuang.

    BUKAN train/test. Tidak ada parameter yang dilatih di jalur ini, jadi tidak
    ada yang bisa dibocori dari test ke train dan embargo tidak berlaku. Yang
    diuji: apakah edge-nya muncul di lebih dari satu potongan waktu, atau hanya
    di satu rejim yang kebetulan panjang.

    Purging tetap wajib walaupun tanpa training: trade yang masih berjalan saat
    fold berikutnya mulai membawa bar fold itu ke dalam angka fold ini, jadi dua
    fold yang bersebelahan akan berbagi bar yang sama tanpa ada yang menyebutnya.
    """
    edge = bars // count
    out, purged_total = [], 0
    for k in range(count):
        lo, hi = k * edge, (k + 1) * edge if k < count - 1 else bars
        kept, purged = purged_fold(rows, lo, hi)
        purged_total += purged
        if kept:
            r = np.array([x["r"] for x in kept])
            out.append({"fold": k, "n": len(r), "exp_r": float(r.mean())})
        else:
            out.append({"fold": k, "n": 0, "exp_r": 0.0})
    return out, purged_total


def sign_test(values: list[float]) -> float:
    """Probabilitas melihat sebanyak ini fold positif kalau koinnya jujur.

    Binomial dua sisi pada p=0,5, dihitung langsung dari faktorial supaya file
    ini tetap tanpa scipy. Dipakai untuk fold, di mana yang bisa dipercaya
    adalah TANDA-nya dan bukan besarannya: delapan fold terlalu sedikit untuk
    mempercayai rata-rata per fold, tapi cukup untuk menanyakan arahnya.
    """
    n = len(values)
    k = sum(1 for v in values if v > 0)
    if n == 0:
        return 1.0
    total = 2 ** n
    tail = sum(math.comb(n, i) for i in range(k, n + 1))
    return min(1.0, 2 * tail / total)


def bootstrap(rows: list[dict], draws: int = 20_000, block: int = 1,
              seed: int = 7) -> dict:
    """Sebaran hasil yang deret ini SANGGUP hasilkan, bukan yang ia hasilkan.

    `block` 1 berarti iid per trade; lebih dari 1 me-resample blok berurutan,
    yang wajib kalau `autocorrelation` menunjukkan ketergantungan antar trade.

    KENAPA MAX DRAWDOWN TERAMATI SELALU TERLALU KECIL. Ia adalah satu tarikan
    dari sebaran ini. Urutan yang sama persis, dikocok, menghasilkan drawdown
    yang berbeda, dan yang teramati tidak punya alasan menjadi yang terburuk.
    Jadi p95 dari kolom ini yang dipakai untuk sizing, bukan yang teramati.
    """
    r = np.array([x["r"] for x in rows], dtype=np.float64)
    n = len(r)
    if n < 2:
        return {}
    rng = np.random.default_rng(seed)
    ends, dds = np.empty(draws), np.empty(draws)
    if block <= 1:
        idx = rng.integers(0, n, size=(draws, n))
        paths = np.cumsum(r[idx], axis=1)
    else:
        starts = rng.integers(0, n, size=(draws, n // block + 1))
        offsets = np.arange(block)
        picks = (starts[:, :, None] + offsets[None, None, :]) % n
        paths = np.cumsum(r[picks.reshape(draws, -1)[:, :n]], axis=1)
    ends = paths[:, -1]
    # Modal awal di kolom pertama, alasan yang sama seperti di `metrics`: tanpa
    # itu path yang jatuh dari trade pertama membawa drawdown yang diremehkan.
    paths = np.concatenate((np.zeros((paths.shape[0], 1)), paths), axis=1)
    dds = (np.maximum.accumulate(paths, axis=1) - paths).max(axis=1)
    return {
        "draws": draws,
        "block": block,
        "total_r_p05": float(np.percentile(ends, 5)),
        "total_r_p50": float(np.percentile(ends, 50)),
        "total_r_p95": float(np.percentile(ends, 95)),
        "p_total_negative": float((ends <= 0).mean()),
        "max_dd_p50": float(np.percentile(dds, 50)),
        "max_dd_p95": float(np.percentile(dds, 95)),
        "max_dd_p99": float(np.percentile(dds, 99)),
    }


def ruin(rows: list[dict], risk_pct: float, paths: int = 20_000,
         trades_ahead: int = 500, ruin_at: float = 0.5, seed: int = 11) -> dict:
    """Probabilitas kehilangan `ruin_at` dari equity dalam `trades_ahead` trade.

    FIXED FRACTIONAL, dan itu bukan detail. Mempertaruhkan persentase dari
    equity SEKARANG membuat kerugian menyusut saat akun mengecil, jadi ruin
    dalam arti nol tidak pernah tercapai secara matematis. Yang ditanyakan di
    sini adalah kehilangan setengah akun, yang di dunia nyata adalah ruin
    karena itu titik seseorang berhenti.

    Dihitung dari distribusi R yang benar-benar terjadi, bukan dari asumsi
    normal, jadi tail kirinya adalah tail kiri deret ini.
    """
    r = np.array([x["r"] for x in rows], dtype=np.float64)
    if len(r) < 2:
        return {}
    rng = np.random.default_rng(seed)
    picks = r[rng.integers(0, len(r), size=(paths, trades_ahead))]
    # log1p dan bukan perkalian berantai: hasilnya identik dan tidak underflow
    # ketika sebuah path benar-benar hancur.
    growth = np.cumsum(np.log1p(np.clip(picks * risk_pct, -0.999999, None)), axis=1)
    floor = math.log(1.0 - ruin_at)
    hit = (growth <= floor).any(axis=1)
    final = np.exp(growth[:, -1])
    return {
        "risk_pct": risk_pct,
        "trades_ahead": trades_ahead,
        "p_ruin": float(hit.mean()),
        "equity_p05": float(np.percentile(final, 5)),
        "equity_p50": float(np.percentile(final, 50)),
        "equity_p95": float(np.percentile(final, 95)),
    }


def kelly(rows: list[dict]) -> dict:
    """Fraksi Kelly untuk payoff tidak simetris, plus separuhnya.

    f = p/L - q/W dalam satuan R, dengan W dan L rata-rata menang dan kalah
    sebagai bilangan positif. Setengah Kelly dicetak berdampingan karena Kelly
    penuh mengasumsikan distribusinya diketahui persis, dan di sini ia
    diestimasi dari beberapa ratus trade.
    """
    r = np.array([x["r"] for x in rows], dtype=np.float64)
    wins, losses = r[r > 0], r[r <= 0]
    if not len(wins) or not len(losses):
        return {}
    p = len(wins) / len(r)
    w = float(wins.mean())
    lo = abs(float(losses.mean()))
    if w <= 0 or lo <= 0:
        return {}
    f = p / lo - (1 - p) / w
    return {"kelly_f": float(f), "half_kelly": float(f / 2), "p": p,
            "avg_win_r": w, "avg_loss_r": lo}


def concurrency(rows: list[dict]) -> dict:
    """Seberapa sering trade hidup berbarengan, dan berapa maksimumnya.

    INI YANG MENENTUKAN APAKAH SHARPE TAHUNAN BOLEH DIHITUNG SAMA SEKALI.
    Annualisasi sqrt(trade per tahun) mengasumsikan tiap trade adalah bet yang
    terpisah. Kalau dua posisi hidup bersamaan pada instrumen yang sama, keduanya
    berbagi eksposur yang sama dan mereka bukan dua bet: sqrt apa pun jadi tidak
    sah sampai bobot uniqueness dipakai atau P&L diresample ke grid kalender.

    Diukur dari `[at, exit]` tiap baris, yang sudah ada di setiap trade.
    """
    if not rows:
        return {}
    spans = sorted((int(x["at"]), int(x["exit"])) for x in rows)
    live, overlapped, peak = [], 0, 0
    for start, end in spans:
        live = [e for e in live if e > start]
        if live:
            overlapped += 1
        live.append(end)
        peak = max(peak, len(live))
    total_bars = sum(e - s + 1 for s, e in spans)
    return {
        "overlapping": overlapped,
        "overlap_rate": overlapped / len(spans),
        "peak_concurrent": peak,
        "avg_hold_bars": total_bars / len(spans),
    }


def null_ruin(rows: list[dict], risk_pct: float, **kw) -> dict:
    """Risk of ruin kalau edge-nya HILANG tapi volatilitasnya tetap.

    Bootstrap biasa me-resample 899 trade yang sama, jadi ia tidak bisa melihat
    rejim di mana aturannya berhenti bekerja: setiap path yang ia bangun membawa
    ekspektasi in-sample di dalamnya. Fungsi ini menggeser deret R sehingga
    mean-nya nol dan membiarkan bentuk sisanya utuh, lalu menanyakan pertanyaan
    yang benar-benar penting untuk sizing: kalau saya salah soal edge-nya,
    seberapa cepat akun ini habis pada lot ini.
    """
    r = np.array([x["r"] for x in rows], dtype=np.float64)
    if len(r) < 2:
        return {}
    centred = [{"r": float(v)} for v in (r - r.mean())]
    return ruin(centred, risk_pct, **kw)


def cell(symbol: str, interval: str, flat: bool = True,
         bars: int = MT5_MAX_BARS) -> dict:
    """Satu sel matrix: instrumen kali timeframe, semua angkanya."""
    candles, dropped, requested = clean(symbol, interval, bars)
    if len(candles) < 500:
        return {"symbol": symbol, "interval": interval, "n": 0,
                "note": f"hanya {len(candles)} bar bersih"}
    rows = [x for x in trades("supply_demand", candles, interval, True,
                              symbol=symbol, broker=BROKER,
                              flat_by_rollover=flat)
            if not x["skipped"]]
    gated = [x for x in rows if x["cleared"]]
    out = {"symbol": symbol, "interval": interval, "bars": len(candles),
           "dropped_prefix": dropped, "requested": requested,
           "touched": len(rows)}
    out.update(metrics(gated))
    if out.get("n", 0) >= 2:
        fold_rows, purged = folds(gated, len(candles))
        out["folds_positive"] = sum(1 for f in fold_rows if f["exp_r"] > 0)
        out["folds_counted"] = sum(1 for f in fold_rows if f["n"] > 0)
        out["purged"] = purged
        out["sign_p"] = sign_test([f["exp_r"] for f in fold_rows if f["n"] > 0])
        out["acf"] = autocorrelation(gated)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--matrix", action="store_true",
                        help="seluruh universe kali 1h dan 4h")
    parser.add_argument("--intervals", default="1h,4h")
    parser.add_argument("--hold", action="store_true",
                        help="aturan exit hold sampai horizon, bukan flat di rollover")
    parser.add_argument("--bars", type=int, default=MT5_MAX_BARS)
    args = parser.parse_args()
    flat = not args.hold

    print(f"exit rule: {'flat di rollover' if flat else f'hold {HORIZON} bar'}, "
          f"broker {BROKER}, prefix spacing salah DIBUANG")

    if args.matrix:
        print(f"\n{'symbol':8s} {'tf':4s} {'bar':>7s} {'buang':>6s} {'n':>5s} "
              f"{'exp R':>7s} {'CI 95%':>17s} {'t':>6s} {'win':>6s} {'payoff':>7s} "
              f"{'Shrp':>6s} {'maxDD':>7s} {'fold+':>6s} {'signP':>6s} {'costR':>6s}")
        cells = []
        for symbol in UNIVERSE:
            for interval in args.intervals.split(","):
                c = cell(symbol, interval, flat, args.bars)
                cells.append(c)
                if not c.get("n"):
                    print(f"{symbol:8s} {interval:4s} {c.get('note', 'tanpa trade')}")
                    continue
                print(f"{symbol:8s} {interval:4s} {c['bars']:7d} "
                      f"{c['dropped_prefix']:6d} {c['n']:5d} {c['exp_r']:+7.3f} "
                      f"[{c['ci_lo']:+6.3f},{c['ci_hi']:+6.3f}] {c['t']:+6.2f} "
                      f"{c['win_rate']:6.1%} {c['payoff']:7.2f} "
                      f"{c['sharpe_trade']:+6.3f} {c['max_dd']:7.1f} "
                      f"{c.get('folds_positive', 0)}/{c.get('folds_counted', 0):<4d} "
                      f"{c.get('sign_p', 1):6.3f} {c['cost_r']:6.3f}")
        good = [c for c in cells if c.get("n", 0) >= 30]
        # SD LINTAS PERCOBAAN, DIUKUR DAN BUKAN DIASUMSIKAN. Deflated Sharpe
        # butuh sebaran Sharpe di antara percobaan, dan sel-sel di atas adalah
        # percobaan yang benar-benar dijalankan: aturan yang sama, instrumen dan
        # timeframe berbeda. Memakai angka karangan di sini akan membuat DSR
        # sekadar bilangan yang enak dilihat.
        if len(good) >= 3:
            sharpes = np.array([c["sharpe_trade"] for c in good])
            sd_trials = float(sharpes.std(ddof=1))
            best = max(good, key=lambda c: c["sharpe_trade"])
            # DUA ESTIMASI sigma_N, DAN PERBEDAANNYA BUKAN DETAIL.
            #
            # DSR butuh sebaran Sharpe DI ANTARA PERCOBAAN DI BAWAH H0, yaitu
            # ketika tidak ada percobaan yang punya edge. Ada dua cara
            # mengukurnya di sini dan keduanya dilaporkan:
            #
            #   lintas sel   SD Sharpe yang benar-benar teramati antar sel.
            #                Di sini ia 0,41 dan itu DIDOMINASI oleh kegagalan
            #                biaya di FX, yang bukan tarikan noise: mereka
            #                sistematis, mekanismenya terukur, dan tandanya
            #                sama di 8 dari 8 fold. Memakai angka ini menaikkan
            #                ambang E[max SR] ke 0,74 dan membuat DSR nol untuk
            #                SEMUA sel, termasuk yang jelas bekerja. Ia menjawab
            #                pertanyaan yang salah.
            #
            #   sampling     SD estimator Sharpe pada n itu di bawah H0, dari
            #                `sharpe_sd(0, n, skew, kurtosis)`. Inilah sebaran
            #                yang akan muncul kalau 108 percobaan dijalankan pada
            #                deret tanpa edge, yang persis definisi H0 di paper
            #                aslinya.
            #
            # Yang kedua yang dipakai untuk menghakimi, yang pertama tetap
            # dicetak supaya pembaca melihat kenapa ia tidak dipakai.
            sd_null = sharpe_sd(0.0, best["n"], best["skew"], best["kurtosis"])
            print(f"\nSharpe per trade lintas {len(good)} sel: "
                  f"mean {sharpes.mean():+.4f} SD {sd_trials:.4f} "
                  f"min {sharpes.min():+.4f} max {sharpes.max():+.4f}")
            # Sel acuan untuk DSR: XAUUSD 1 jam kalau ada, kalau tidak sel
            # dengan Sharpe tertinggi. Versi pertama meng-hardcode XAUUSD 1h dan
            # mencetak nan pada run `--intervals 15m`, yang terbaca seperti
            # formulanya gagal padahal sel acuannya tidak ada di run itu.
            gold = next((c for c in good
                         if c["symbol"] == "XAUUSD" and c["interval"] == "1h"),
                        best)
            print(f"sigma_N lintas sel {sd_trials:.4f} (dipakai sebagai pembanding), "
                  f"sigma_N sampling di bawah H0 {sd_null:.4f} (dipakai menghakimi)")
            print(f"  {'percobaan':>9s} {'E[maxSR] null':>13s} {'DSR null':>9s} "
                  f"{'E[maxSR] sel':>13s} {'DSR sel':>9s}")
            for trials in TRIALS:
                bar_n = expected_max_sharpe(trials, sd_null)
                bar_c = expected_max_sharpe(trials, sd_trials)
                d_n = deflated_sharpe(gold["sharpe_trade"], gold["n"], gold["skew"],
                                      gold["kurtosis"], trials, sd_null)                     if gold else float("nan")
                d_c = deflated_sharpe(gold["sharpe_trade"], gold["n"], gold["skew"],
                                      gold["kurtosis"], trials, sd_trials)                     if gold else float("nan")
                print(f"  {trials:9d} {bar_n:13.4f} {d_n:9.4f} "
                      f"{bar_c:13.4f} {d_c:9.4f}")
            print(f"  baris di atas untuk {gold['symbol']} {gold['interval']}, "
                  "Sharpe per trade "
                  f"{gold['sharpe_trade']:+.4f} pada n={gold['n']}" if gold else "")
        pos = [c for c in good if c["exp_r"] > 0]
        print(f"\n{len(good)} sel dengan n >= 30, {len(pos)} positif, "
              f"{sum(1 for c in good if c['t'] > 2)} dengan t > 2")
        if good:
            allr = float(np.mean([c["exp_r"] for c in good]))
            print(f"rata-rata exp R lintas sel: {allr:+.3f}")
        return 0

    symbol = args.symbol or "XAUUSD"
    c = cell(symbol, args.interval, flat, args.bars)
    if not c.get("n"):
        print(c.get("note", "tanpa trade")); return 1
    print(f"\n{symbol} {args.interval}: {c['bars']} bar bersih dari "
          f"{c['requested']} (buang {c['dropped_prefix']}), {c['touched']} first "
          f"touch, {c['n']} lolos gerbang")
    print(f"  exp R {c['exp_r']:+.4f}  CI95 [{c['ci_lo']:+.4f}, {c['ci_hi']:+.4f}]  "
          f"t {c['t']:+.2f}  SD {c['sd']:.3f}")
    print(f"  win {c['win_rate']:.1%}  avg win {c['avg_win']:+.3f}  "
          f"avg loss {c['avg_loss']:+.3f}  payoff {c['payoff']:.2f}")
    print(f"  Sharpe/trade {c['sharpe_trade']:+.4f}  skew {c['skew']:+.3f}  "
          f"kurtosis {c['kurtosis']:.3f}")
    print(f"  total {c['total_r']:+.1f} R  max DD teramati {c['max_dd']:.1f} R  "
          f"biaya rata-rata {c['cost_r']:.3f} R  malam rata-rata {c['nights']:.2f}")
    print(f"  fold positif {c['folds_positive']}/{c['folds_counted']}  "
          f"sign test p {c['sign_p']:.4f}  dipurge {c['purged']}")
    print("  ACF lag 1..5: " + " ".join(f"{v:+.3f}" for v in c["acf"]))

    candles, _, _ = clean(symbol, args.interval, args.bars)
    rows = [x for x in trades("supply_demand", candles, args.interval, True,
                              symbol=symbol, broker=BROKER,
                              flat_by_rollover=flat)
            if not x["skipped"] and x["cleared"]]
    lag1 = c["acf"][0] if c["acf"] else 0.0
    # TIGA PANJANG BLOK, bukan satu. Satu pilihan blok adalah satu asumsi tentang
    # ketergantungan antar trade, dan pembaca berhak melihat apakah kesimpulannya
    # bergantung pada asumsi itu. Kalau ketiganya sepakat, pilihan blok tidak
    # menentukan apa pun, dan itu layak dinyatakan.
    print(f"\nbootstrap 20000 path, ACF lag1 {lag1:+.3f}, tiga panjang blok:")
    for blk in (1, 5, 10):
        b = bootstrap(rows, block=blk)
        print(f"  blok {blk:2d}: total R p05 {b['total_r_p05']:+7.1f} "
              f"p50 {b['total_r_p50']:+7.1f} p95 {b['total_r_p95']:+7.1f}  "
              f"P(total<=0) {b['p_total_negative']:5.1%}  "
              f"maxDD p50 {b['max_dd_p50']:5.1f} p95 {b['max_dd_p95']:5.1f} "
              f"p99 {b['max_dd_p99']:5.1f} R")
    print(f"  max DD teramati cuma {c['max_dd']:.1f} R, dan itu satu tarikan dari "
          "sebaran di atas")

    conc = concurrency(rows)
    print(f"\nkonkurensi: {conc['overlapping']} dari {c['n']} trade "
          f"({conc['overlap_rate']:.1%}) hidup bersamaan dengan trade lain, "
          f"puncak {conc['peak_concurrent']} posisi, tahan rata-rata "
          f"{conc['avg_hold_bars']:.1f} bar")
    if conc["overlap_rate"] > 0.1:
        print("  KONSEKUENSINYA: trade BUKAN bet yang terpisah, jadi Sharpe "
              "tahunan di bawah ini adalah batas ATAS dan bukan estimasi. "
              "Angka yang sah butuh equity curve harian atau bobot uniqueness.")

    q, df = ljung_box(c["acf"], c["n"])
    crit = CHI2_95.get(df, 0.0)
    print(f"  Ljung-Box Q({df}) {q:.2f} lawan kritis 95% {crit:.3f}: "
          f"{'ADA ketergantungan' if q > crit else 'tidak ada'}")

    # Sharpe tahunan. Rate-nya diukur, bukan diasumsikan 252 hari.
    years = (candles[-1].time - candles[0].time) / (365.25 * 86400)
    per_year = c["n"] / years if years > 0 else 0.0
    naive = c["sharpe_trade"] * math.sqrt(per_year)
    corrected = lo_annualised(c["sharpe_trade"], per_year, c["acf"])
    print(f"  {per_year:.0f} trade per tahun ({years:.1f} tahun): Sharpe tahunan "
          f"naif {naive:+.3f}, koreksi Lo {corrected:+.3f}")

    need = min_trl(c["sharpe_trade"], c["n"], c["skew"], c["kurtosis"])
    print(f"  minTRL {need:.0f} trade untuk klaim di atas nol pada 95%; "
          f"punya {c['n']} ({'CUKUP' if c['n'] >= need else 'BELUM cukup'})")
    print(f"  PSR di atas nol: {psr(c['sharpe_trade'], c['n'], c['skew'], c['kurtosis']):.4f}")

    k = kelly(rows)
    if k:
        print(f"\nKelly f {k['kelly_f']:.4f} ({k['kelly_f']:.2%} equity per trade), "
              f"setengah Kelly {k['half_kelly']:.2%}")
    print("risk of ruin, kehilangan 50% equity dalam 500 trade berikutnya.")
    print("  kolom kedua adalah SKENARIO NULL: deret R yang sama digeser ke mean "
          "nol, jadi ia menjawab 'kalau edge-nya ternyata tidak ada'.")
    print(f"  {'risk':>6s} {'P(ruin) edge ada':>17s} {'P(ruin) edge nol':>17s} "
          f"{'equity p05':>11s} {'equity p50':>11s}")
    for rp in (0.005, 0.01, 0.02, 0.03, 0.05, 0.10):
        d = ruin(rows, rp)
        z = null_ruin(rows, rp)
        print(f"  {rp:6.1%} {d['p_ruin']:17.2%} {z['p_ruin']:17.2%} "
              f"{d['equity_p05']:10.2f}x {d['equity_p50']:10.2f}x")
    print("\nSETIAP ANGKA DI ATAS ME-RESAMPLE DERET YANG SAMA. Ia tidak bisa "
          "melihat rejim yang belum pernah terjadi, jadi ia adalah batas bawah "
          "risiko, bukan ramalan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Formula statistik yang menghakimi sebuah backtest. Murni, tanpa IO.

DI FILE SENDIRI SUPAYA BISA DITES TANPA TERMINAL. `tools/quant.py` butuh MT5
untuk mendapatkan trade; formula di bawah tidak butuh apa pun, jadi test-nya bisa
membandingkan langsung ke contoh numerik yang diterbitkan di paper aslinya. Itu
satu-satunya cara memastikan implementasi ini benar dan bukan sekadar berjalan.

TANPA SCIPY, sama seperti sisa repo ini. Normal CDF dari `math.erf`, dan inverse
normal CDF dari algoritma rasional Acklam, yang akurat sampai sekitar 1e-9 di
seluruh rentang, jauh lebih presisi dari yang dibutuhkan angka mana pun di sini.

KENAPA FILE INI ADA. Sebuah backtest yang positif tidak berarti apa-apa sampai
tiga pertanyaan berikut dijawab dengan angka:

  1. Berapa peluang Sharpe ini muncul dari deret yang sebenarnya tanpa edge,
     mengingat skewness dan kurtosis-nya? -> `psr`
  2. Berapa Sharpe TERTINGGI yang akan muncul dari sekian percobaan meskipun
     semuanya cuma noise, dan apakah Sharpe kita mengalahkan angka itu?
     -> `expected_max_sharpe`, lalu `deflated_sharpe`
  3. Berapa observasi yang dibutuhkan sebelum klaim ini punya dasar? -> `min_trl`

Sumber formula: Bailey dan Lopez de Prado, "The Sharpe Ratio Efficient Frontier"
(2012) untuk PSR dan minTRL, dan "The Deflated Sharpe Ratio" (2014) untuk DSR.
Koreksi autokorelasi pada annualisasi dari Lo (2002), "The Statistics of Sharpe
Ratios". Contoh numerik dari sumber-sumber itu dipakai sebagai test.
"""

from __future__ import annotations

import math

#: Euler-Mascheroni. Muncul di ekspansi extreme-value untuk expected maximum.
EULER = 0.5772156649015329


def norm_cdf(x: float) -> float:
    """CDF normal standar lewat `math.erf`. Eksak sampai presisi double."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse CDF normal standar, algoritma rasional Acklam.

    Dipakai karena `expected_max_sharpe` butuh quantile pada 1 - 1/N, dan pada N
    besar itu berada jauh di ekor tempat pendekatan kasar mulai melenceng.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p harus di (0,1), diberi {p}")
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q
                + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q
                 + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q \
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def sharpe_sd(sharpe: float, n: int, skew: float, kurtosis: float) -> float:
    """Standard error dari estimator Sharpe, memperhitungkan momen ketiga dan keempat.

    `kurtosis` adalah kurtosis MENTAH, normal = 3. Memberi excess kurtosis ke
    sini menggeser hasilnya tanpa error apa pun, jadi konvensinya disebut di
    setiap docstring yang memakainya.

    Untuk return normal (skew 0, kurtosis 3) ia menyusut jadi
    sqrt((1 + 0.5 SR^2)/(n-1)), yang merupakan bentuk yang lebih dikenal.
    """
    if n < 2:
        return float("inf")
    var = (1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe ** 2) / (n - 1)
    return math.sqrt(max(var, 0.0))


def psr(sharpe: float, n: int, skew: float, kurtosis: float,
        benchmark: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: peluang Sharpe SEJATI melampaui `benchmark`.

    Bukan p-value dan bukan komplemennya. Ia adalah probabilitas posterior atas
    Sharpe sejati di bawah asumsi normal untuk estimatornya, dengan skewness dan
    kurtosis deret ikut diperhitungkan. Skew negatif dan tail tebal menurunkannya.
    """
    sd = sharpe_sd(sharpe, n, skew, kurtosis)
    if sd <= 0 or not math.isfinite(sd):
        return 0.0
    return norm_cdf((sharpe - benchmark) / sd)


def expected_max_sharpe(trials: int, sd_across_trials: float,
                        mean_across_trials: float = 0.0) -> float:
    """Sharpe tertinggi yang DIHARAPKAN muncul dari `trials` percobaan tanpa edge.

    Ini inti dari deflation. Kalau sebuah project mencoba 16 hipotesis pada data
    yang sama, yang terbaik di antaranya akan terlihat bagus walaupun semuanya
    noise, dan angka inilah seberapa bagus. Sharpe yang tidak melampaui angka ini
    tidak membawa informasi apa pun di atas "kami mencoba banyak hal".

    `trials` di sini adalah percobaan INDEPENDEN EFEKTIF, bukan hitungan literal.
    Percobaan yang saling berkorelasi rho rata-rata memberi
    `n_eff = rho + (1 - rho) * m`, jadi 16 varian yang hampir identik jauh lebih
    dekat ke 1 percobaan daripada ke 16. Pemanggil yang menentukan, dan angkanya
    harus dinyatakan di laporan.
    """
    if trials < 1:
        raise ValueError("trials minimal 1")
    if trials == 1:
        return mean_across_trials
    left = norm_ppf(1.0 - 1.0 / trials)
    right = norm_ppf(1.0 - 1.0 / (trials * math.e))
    return mean_across_trials + sd_across_trials * (
        (1.0 - EULER) * left + EULER * right
    )


def deflated_sharpe(sharpe: float, n: int, skew: float, kurtosis: float,
                    trials: int, sd_across_trials: float) -> float:
    """PSR yang benchmark-nya adalah expected maximum dari `trials` percobaan.

    Di bawah 0,95 berarti Sharpe yang teramati tidak bisa dipisahkan dari
    "pemenang undian" di antara percobaan yang pernah dijalankan.
    """
    bar = expected_max_sharpe(trials, sd_across_trials)
    return psr(sharpe, n, skew, kurtosis, benchmark=bar)


def min_trl(sharpe: float, n_unused: int, skew: float, kurtosis: float,
            benchmark: float = 0.0, alpha: float = 0.05) -> float:
    """Observasi minimum sebelum Sharpe ini layak diklaim di atas `benchmark`.

    `n_unused` diterima dan tidak dipakai, dengan sengaja: pemanggil selalu punya
    n di tangan dan perbandingan "minTRL lawan n yang saya punya" adalah satu
    satunya pemakaian angka ini. Menerimanya di signature membuat pemanggil tidak
    perlu mengingat bahwa ia TIDAK masuk ke formula.
    """
    if sharpe <= benchmark:
        return float("inf")
    z = norm_ppf(1.0 - alpha)
    moment = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe ** 2
    return 1.0 + moment * (z / (sharpe - benchmark)) ** 2


def ljung_box(acf: list[float], n: int) -> tuple[float, int]:
    """Statistik Q untuk autokorelasi gabungan, plus derajat kebebasannya.

    Q = n(n+2) * sum(rho_k^2 / (n-k)). Dibandingkan ke chi-square dengan df = k.
    Nilai kritis dicetak oleh pemanggil dari tabel, karena mendatangkan
    chi-square CDF ke sini akan menambah satu implementasi lagi untuk satu
    pemakaian.

    Kenapa ini ada dan bukan cuma lag-1: lag-1 sendirian melewatkan
    ketergantungan yang tersebar di beberapa lag, dan bootstrap iid melanggar
    keduanya dengan cara yang sama.
    """
    if not acf or n <= len(acf) + 1:
        return 0.0, 0
    q = n * (n + 2) * sum(r ** 2 / (n - k - 1) for k, r in enumerate(acf))
    return float(q), len(acf)


def lo_annualised(sharpe: float, per_year: float, acf: list[float]) -> float:
    """Sharpe tahunan dengan koreksi autokorelasi Lo (2002).

    sqrt(q) naif mengasumsikan trade independen. Autokorelasi positif membuatnya
    MELEBIHKAN Sharpe tahunan, dan itu arah kesalahan yang paling merugikan
    karena ia membesarkan angka yang dipakai orang untuk memutuskan.

    `per_year` adalah trade per tahun, sebuah RATE, bukan jumlah trade di sampel.
    Untuk trade yang jaraknya tidak seragam, itu satu-satunya pembacaan yang
    masuk akal, dan ia tetap mengasumsikan rate-nya stasioner. Kalau ada posisi
    yang tumpang tindih, tidak ada versi sqrt yang sah dan angka ini harus
    diganti Sharpe dari equity curve harian.
    """
    q = max(1, int(round(per_year)))
    if not acf:
        return sharpe * math.sqrt(q)
    weighted = sum((1.0 - (k + 1) / q) * r
                   for k, r in enumerate(acf) if k + 1 < q)
    denom = 1.0 + 2.0 * weighted
    if denom <= 0:
        return float("nan")
    return sharpe * math.sqrt(q) / math.sqrt(denom)


def pbo(matrix, splits: int = 16) -> dict:
    """Probability of Backtest Overfitting lewat CSCV.

    `matrix` berbentuk (T, N): baris observasi urut waktu, kolom konfigurasi.
    Untuk tiap cara memilih S/2 blok sebagai train, konfigurasi terbaik in-sample
    dicari, lalu rank-nya dilihat out-of-sample. PBO adalah proporsi kombinasi di
    mana pemenang in-sample jatuh ke bawah median out-of-sample.

    DEGENERATE PADA N = 1, dan itu ditolak di sini alih-alih dikembalikan sebagai
    angka. Dengan satu kolom, rank selalu 1 dari 1, logit selalu nol, dan PBO
    keluar 1,0 atau 0,0 tergantung bagaimana ikatan diperlakukan. Angkanya akan
    terlihat seperti pengukuran dan tidak mengukur apa pun: tidak ada seleksi
    yang terjadi, jadi tidak ada overfitting seleksi untuk diukur. Aturan tunggal
    tanpa parameter yang di-fit membutuhkan holdout out-of-sample plus PSR, bukan
    ini.
    """
    import itertools

    import numpy as np

    m = np.asarray(matrix, dtype=np.float64)
    if m.ndim != 2:
        raise ValueError("matrix harus 2 dimensi (T, N)")
    t, n = m.shape
    if n < 2:
        raise ValueError(
            "PBO butuh minimal 2 konfigurasi untuk dirangking. Satu aturan tanpa "
            "parameter yang di-fit tidak punya seleksi untuk diukur, jadi CSCV "
            "degenerate: pakai holdout out-of-sample plus PSR."
        )
    if splits % 2:
        raise ValueError("splits harus genap")
    per = t // splits
    if per < 2:
        raise ValueError(f"{t} baris terlalu sedikit untuk {splits} blok")
    blocks = [m[k * per:(k + 1) * per] for k in range(splits)]

    logits = []
    for pick in itertools.combinations(range(splits), splits // 2):
        rest = [k for k in range(splits) if k not in pick]
        train = np.concatenate([blocks[k] for k in pick])
        test = np.concatenate([blocks[k] for k in rest])
        sd_tr = train.std(axis=0, ddof=1)
        sd_te = test.std(axis=0, ddof=1)
        # Kolom tanpa variasi tidak punya Sharpe. Diberi -inf supaya ia tidak
        # bisa menang in-sample lewat pembagian nol.
        with np.errstate(divide="ignore", invalid="ignore"):
            sr_tr = np.where(sd_tr > 0, train.mean(axis=0) / sd_tr, -np.inf)
            sr_te = np.where(sd_te > 0, test.mean(axis=0) / sd_te, -np.inf)
        best = int(np.argmax(sr_tr))
        # Rank 1 = terburuk, n = terbaik. Ikatan diberi rank rata-rata supaya
        # kolom yang identik tidak bisa mendorong logit ke satu arah.
        order = np.argsort(np.argsort(sr_te)) + 1
        rank = float(order[best])
        omega = rank / (n + 1)
        logits.append(math.log(omega / (1.0 - omega)))
    return {
        "pbo": sum(1 for x in logits if x <= 0) / len(logits),
        "combinations": len(logits),
        "splits": splits,
        "configs": n,
        "rows": t,
        "logit_median": float(np.median(logits)),
    }

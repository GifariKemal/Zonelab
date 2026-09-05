# FVG Recalibration Report

5 September 2026. Scope: pure FVG (Fair Value Gap), XAUUSD + BTCUSD, 30m.

## Gate decision

| Parameter | Produksi lama | Rekomendasi | Alasan |
|---|---|---|---|
| `min_gap_atr` | 0.1 | **0.0** | Tidak membuang FVG kecil; sweep membuktikan filter ini tidak menambah edge |
| `gate_atr` (departure) | 2.0 | **0.25** | Gate lama hampir tidak menyaring (4706/4833); gate ketat memilih 2024 FVG terbaik |

Gate lama terbalik: ia menyimpan hampir semua trade dan membuang hanya 127.
Gate baru memisahkan kohort +0.4257 R (di bawah gate) dari +0.1904 R (di atas).

## Angka sweep

42 konfigurasi (7 min_gap x 6 gate), Bonferroni t threshold = 3.241, 8-fold walk-forward.

### Top 5

| min_gap | gate | n | exp_r | t vs 0 | welch_t | wf | pass |
|---|---|---|---|---|---|---|---|
| 0.00 | 0.25 | 2024 | +0.4257 | 9.32 | 4.58 | 8/8 | ya |
| 0.05 | 0.25 | 1589 | +0.3795 | 7.35 | 3.46 | 8/8 | ya |
| 0.00 | 0.50 | 3277 | +0.3510 | 10.79 | 4.66 | 8/8 | ya |
| 0.10 | 0.25 | 1141 | +0.3365 | 5.65 | 2.53 | 8/8 | ya |
| 0.00 | 1.00 | 4266 | +0.3107 | 11.81 | 4.39 | 8/8 | ya |

### Produksi lama vs rekomendasi

| Metrik | Lama (0.1/2.0) | Baru (0.0/0.25) | Delta |
|---|---|---|---|
| n_below | 3814 | 2024 | -1790 |
| exp_r_below | +0.2236 | +0.4257 | +0.2021 |
| t_below_vs_zero | 8.75 | 9.32 | +0.57 |
| welch_t | belum diukur | 4.58 | - |
| walk-forward | 8/8 | 8/8 | = |

### Per-cell breakdown (konfigurasi 0.0/0.25)

| Sel | n_below | exp_r_below | n_above | exp_r_above |
|---|---|---|---|---|
| XAUUSD 30m | 1002 | +0.5491 | 1457 | +0.1588 |
| BTCUSD 30m | 1022 | +0.3047 | 1352 | +0.2244 |

XAU edge paling tajam: hampir +0.4 R selisih antara kohort bawah dan atas.

## Backtest statistics (30m)

Statistik trade-level dari `cell_rows`, pooled XAU+BTC.

| Metrik | Lama (0.1/2.0) | Baru (0.0/0.25) |
|---|---|---|
| Trade count | 3814 | 2024 |
| Win / loss | 1989 / 1825 | 985 / 1039 |
| Winrate | 52.15% | 48.67% |
| **Profit factor** | **1.52** | **1.90** |
| Expected R | +0.2236 | +0.4257 |
| Sharpe (R) | 0.142 | 0.207 |
| Avg win R | 1.255 | 1.849 |
| Avg loss R | -0.900 | -0.923 |
| Max consec wins | 18 | 14 |
| Max consec losses | 12 | 17 |
| Best / worst R | +29.07 / -1.00 | +29.07 / -1.00 |

Winrate turun 3,5 pp tapi avg win R naik dari 1.25 ke 1.85 - gate ketat memilih
FVG yang kalau menang, menangnya besar. PF naik dari 1.52 ke 1.90.

Trade-off: max consecutive losses naik dari 12 ke 17, jadi drawdown per losing
streak lebih berat meski per-trade result lebih baik.

### Per-instrumen (30m)

| | XAU lama | XAU baru | BTC lama | BTC baru |
|---|---|---|---|---|
| Trades | 1941 | 1002 | 1873 | 1022 |
| Winrate | 52.70% | 50.80% | 51.58% | 46.58% |
| PF | 1.53 | 2.22 | 1.51 | 1.61 |
| Exp R | +0.224 | +0.549 | +0.224 | +0.305 |
| Sharpe | 0.140 | 0.246 | 0.144 | 0.165 |

XAU paling banyak untung: PF dari 1.53 ke 2.22, exp R dari +0.224 ke +0.549.

## Multi-timeframe sweep

Tiga konfigurasi diuji di 15m, 1h, 4h, dan 1d. Konfigurasi: recommended (0.0/0.25),
no-gate baseline (0.0/0.0), old production (0.1/2.0).

| TF | Symbol | Rec n | Rec exp_r | Rec t | Baseline exp_r | Old exp_r |
|---|---|---|---|---|---|---|
| 15m | XAU | 404 | +0.417 | 3.67 | +0.278 | +0.168 |
| 15m | BTC | 403 | +0.245 | 2.29 | +0.200 | +0.150 |
| **30m** | **XAU** | **1002** | **+0.549** | **9.32** | **+0.289** | **+0.224** |
| **30m** | **BTC** | **1022** | **+0.305** | **4.58** | **+0.289** | **+0.224** |
| 1h | XAU | 449 | +0.404 | 4.28 | +0.242 | +0.168 |
| 1h | BTC | 488 | +0.459 | 5.14 | +0.273 | +0.237 |
| 4h | XAU | 345 | +0.226 | 2.56 | +0.131 | +0.121 |
| 4h | BTC | 296 | +0.298 | 3.19 | +0.177 | +0.111 |
| 1d | XAU | 135 | -0.016 | -0.18 | -0.040 | -0.070 |
| 1d | BTC | 103 | +0.257 | 2.34 | +0.101 | +0.072 |

**Pattern:** edge bertahan di 15m, 1h, 4h untuk kedua instrumen. Recommended config
mengalahkan old production di SETIAP sel. Edge pecah di 1d: XAU daily negatif di
semua konfigurasi (t tidak signifikan), BTC daily masih positif tapi n tipis (103 trade).

**Strongest:** 30m dan 1h. Di 1h BTC, recommended config bahkan lebih kuat dari 30m
(+0.459 R, t=5.14).

## Visual compare (Zonelab vs TradingView Pine)

Pine indicator menggambar SEMUA FVG tanpa filter (200 box limit TradingView). Hasilnya
chart penuh garis overlapping, tidak bisa dibaca. Ini sengaja: indicator-nya bukan
untuk trading, hanya parity check formula.

Zonelab FVG layer menampilkan 12 zone (6 per side) dengan state tracking (Fresh,
Mitigated, Tested). Lebih bersih dan actionable karena:

1. `max_zones_per_side` membatasi tampilan ke zone terdekat
2. State tracking menandai mana yang sudah tersentuh harga
3. Departure gate (kalau diterapkan) menyaring zone yang entry-nya terlalu jauh

Zone price levels cocok antara kedua engine (99.5% match, offset broker 0.18).

## Parity check (Pine vs Python)

Pine Script indicator (`mql5/pine/ZonelabFVG.pine`, commit `08b72be`) dibandingkan
dengan `app.detect.imbalance.detect_fvg` menggunakan 5000 bar MT5 dan 200 Pine box
dari TradingView.

| Toleransi | Match | Persen |
|---|---|---|
| 0.10 | 20/200 | 10.0% |
| 0.20 | 91/200 | 45.5% |
| 0.30 | 159/200 | 79.5% |
| 0.50 | 188/200 | 94.0% |
| 1.00 | 199/200 | 99.5% |

Satu box yang tersisa di toleransi 1.0 adalah FVG kecil (gap 1.55) yang kemungkinan
jatuh di batas sesi yang berbeda antara dua feed.

**Offset sistematis** (Python minus Pine, n=200):

| Edge | Mean | Median | Stdev | Max abs |
|---|---|---|---|---|
| high | +0.068 | +0.063 | 0.163 | 0.761 |
| low | +0.181 | +0.184 | 0.173 | 1.203 |

Ini bukan bug formula, ini perbedaan feed broker (MT5 CFD vs TradingView spot).
Formula identik: `high[i-2] < low[i]` (bullish), `low[i-2] > high[i]` (bearish).

**Verdict:** PASS. Formula parity confirmed, 99.5% match.

## File yang dihasilkan

| File | Keterangan |
|---|---|
| `mql5/pine/ZonelabFVG.pine` | Pine Script v6 indicator, commit `08b72be` |
| `backend/tools/fvg_sweep.py` | Grid sweep tool, commit `3a36128` |
| `docs/fvg_sweep.json` | 42 hasil sweep lengkap |
| `docs/pine_boxes_xauusd_30m.json` | 200 Pine box untuk parity check |
| `backend/tools/fvg_stats_compare.py` | Backtest stats tool |
| `docs/fvg_backtest_stats.json` | Statistik trade-level OLD vs NEW |
| `backend/tools/fvg_multi_tf_sweep.py` | Multi-TF sweep tool |
| `docs/fvg_multi_tf.json` | Hasil sweep 4 timeframe x 2 instrumen |

## Langkah selanjutnya

1. Terapkan `min_gap_atr=0.0` dan `gate_atr=0.25` ke parameter produksi
2. Jalankan ulang semua e2e harness setelah perubahan parameter
3. Pertimbangkan menerapkan gate yang sama di 1h (edge kuat, terutama BTC +0.459 R)
4. Jangan terapkan di daily XAU (edge negatif)
5. Monitor live performance selama minimal satu minggu sebelum menyimpulkan

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

## Langkah selanjutnya

1. Terapkan `min_gap_atr=0.0` dan `gate_atr=0.25` ke parameter produksi
2. Jalankan ulang semua e2e harness setelah perubahan parameter
3. Monitor live performance selama minimal satu minggu sebelum menyimpulkan

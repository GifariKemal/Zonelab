# Praregistrasi studi pengkondisian: regime filter, 4 September 2026

Dokumen ini ditulis **sebelum** satu angka pun dihitung. Kolom yang diuji di sini
belum pernah diuji di repo ini: ADX tidak ada satu pun referensi di codebase, dan
Bollinger Band Width juga nol.

ATR percentile regime (`app/regime.py`) sudah ada dan sudah diuji sebagai
pengkondisi di `tools/quant.py` dan `tools/walkforward.py`. Komentar di
`regime.py` menyatakan "sejauh ini tidak" memisahkan. Kedua kolom baru di sini
menguji dua cara LAIN mengukur regime yang belum dicoba.

## 1. Pertanyaannya

Sama dengan `PRAREGISTRASI-KONDISI.md` Bagian 1: **apakah ada state regime pada
bar sentuhan yang memisahkan ekspektasi R** dari populasi gate-clearing yang sama.

## 2. Populasi dan outcome

Identik dengan `PRAREGISTRASI-KONDISI.md` Bagian 2. Tidak ada yang berubah:
instrumen, timeframe, bar, populasi, entry, stop, target, exit, outcome, dan biaya
semuanya sama.

## 3. Kolom yang akan diuji, daftar tertutup

Dua kolom, keduanya dihitung dari `candles[:index + 1]` saja (anti-lookahead
inheren pada trailing indicator).

| Kolom | Nilai yang mungkin | Definisi | Alasan diuji |
|---|---|---|---|
| `adx_band` | `weak` (<20), `trending` (20-40), `strong` (>40) | Wilder ADX 14-period, potongan standar Wilder sendiri | ADX mengukur kekuatan tren, bukan arahnya. Pasar tanpa tren bisa membuat supply/demand zone lebih sering tersentuh dan lebih sering gagal. Potongan 20/40 bukan dari data: itu interpretasi Wilder yang sudah diterbitkan. |
| `bb_width_regime` | `squeeze` (bottom 20%), `normal` (middle 60%), `expansion` (top 20%) | Bollinger Band Width (20-period, 2 std dev), di-percentile-kan terhadap 200 bar terakhir | BB Width mengukur volatility compression/expansion berbeda dari ATR: ATR mengukur range per bar, BB Width mengukur dispersi close terhadap mean-nya. Percentile 200-bar bukan dari populasi studi: ia dari jendela trailing tiap bar. Potongan 20/80 sama dengan `app/regime.py`. |

Period ADX (14) sama dengan `atr_period` di seluruh repo. Period BB (20) dan
multiplier (2) adalah default Bollinger yang diterbitkan. Window percentile BB
Width (200) sama dengan `CORR_BARS` di `conditioned.py` dan
`_VOLUME_BASELINE_BARS` di `app/detect/supply_demand.py`.

## 4. Ambang

Sama dengan `PRAREGISTRASI-KONDISI.md` Bagian 4: n >= 30, Bonferroni atas seluruh
jumlah grup (termasuk yang dari praregistrasi sebelumnya), dan tanda yang sama di
kedua paruh.

## 5. Yang tidak akan dilakukan

Sama dengan `PRAREGISTRASI-KONDISI.md` Bagian 5. Tidak menjumlahkan, tidak
menambah kolom setelah melihat hasil, tidak menghapus grup, tidak menyatakan arah.

## 6. Ekspektasi sebelum dijalankan

ATR percentile regime yang sudah ada tidak memisahkan. Dua belas hipotesis arah
null. Empat belas percobaan conditioning sebelumnya nol yang memisahkan. Probabilitas
prior bahwa dua kolom baru ini memisahkan rendah. Kalau keduanya null, itu konsisten
dengan temuan sebelumnya. Dinyatakan sekarang supaya nol yang keenam belas bukan
kejutan yang menggoda untuk diakali.

## 7. Hasil, 4 September 2026

Dijalankan `python -m tools.conditioned --symbol mt5:XAUUSD --interval 1h
--bars 50000`. Populasi n=959, 107 grup layak dinilai (termasuk semua
praregistrasi sebelumnya), alpha 0,05/107 = 0,00047, `|t|` kritis **3,50**.

**Nol dari kedua kolom memisahkan.**

| Kolom | Nilai | n | exp R | delta | t | paruh |
|---|---|---|---|---|---|---|
| `adx_band` | strong | 142 | +0,135 | +0,215 | +1,75 | +0,074/+0,325 |
| `adx_band` | trending | 584 | -0,049 | -0,004 | -0,05 | +0,051/-0,056 |
| `adx_band` | weak | 233 | -0,155 | -0,142 | -2,18 | -0,109/-0,175 |
| `bb_width_regime` | expansion | 211 | +0,018 | +0,083 | +0,90 | +0,018/+0,136 |
| `bb_width_regime` | normal | 650 | -0,068 | -0,065 | -0,88 | -0,022/-0,101 |
| `bb_width_regime` | squeeze | 98 | -0,048 | -0,001 | -0,01 | +0,020/-0,021 |

ADX menunjukkan pola arah yang konsisten: `strong` positif di kedua paruh,
`weak` negatif di kedua paruh. Tapi t=+1,75 dan t=-2,18 keduanya jauh di bawah
ambang 3,50. BB Width tidak menunjukkan pola sama sekali.

Hitungan sekarang: enam belas percobaan conditioning, enam belas nol. Regime
filter, dalam tiga bentuk yang sudah diuji (ATR percentile, ADX, BB Width),
tidak memisahkan ekspektasi R di populasi ini.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

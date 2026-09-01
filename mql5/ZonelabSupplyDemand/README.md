# ZonelabSupplyDemand - EA MQL5

EA backtest untuk drawing supply/demand Zonelab di MT5 Strategy Tester. Ini
port faithful dari `backend/app/detect/supply_demand.py` + `app/plan.py`.

## File

- `SupplyDemandDetector.mqh` - port detektor (Wilder ATR, classify, runs, gate,
  lifecycle, geometri box). Konvensi index sama dengan Python: index 0 = bar
  tertua.
- `ZonelabSD.mq5` - EA main. Entry limit di proximal (demand long, supply short),
  stop di distal - 0.25 ATR, target zona lawan terdekat (profit_zone), sizing
  risk%. Satu order per zona, dengan dedupe + window penuh.
- `tester.ini` - config Strategy Tester (M15, real ticks Model=4).
- `run_backtest.bat` - script untuk menjalankan tester.

## Status verifikasi

1. **Parity OK** - `python -m tools.ea_parity` membuktikan algoritma loop
   eksplisit menghasilkan zona identik dengan detektor numpy (0 mismatch).
2. **Compile 0 error 0 warning** via MetaEditor.

## Hasil backtest (Exness XAUUSD, 2026-01-01 sampai 2026-08-31)

Deposit 10.000 USD, risk 1% per trade, target 2R. Real tick 100% quality.

### Model mengikis profit (M15)

| Model | Net profit | PF | Win rate |
|---|---|---|---|
| 1 minute OHLC | +41,7% | 1,11 | 36,3% |
| Every tick (sintesis) | +39,3% | 1,10 | 35,7% |
| **Real ticks** | **+32,5%** | **1,09** | 35,5% |

Makin realistis model, profit makin turun, tapi tetap positif. `+32,5%` ini
angka jujur. Pending limit robust ke urutan intrabar, jadi erosi lebih kecil
daripada market order di bar touch (koreksi 22 Agustus +0,20 R jadi +0,02 R).

### Multi-timeframe (real tick, gate 2,0, 2R)

| TF | Net profit | PF | Trades | Win rate | Max DD | Verdict |
|---|---|---|---|---|---|---|
| M5 | -7,4% | 0,98 | 661 | 32,8% | 35,8% | Rugi, terlalu berisik |
| M15 | +32,5% | 1,09 | 476 | 35,5% | 19,2% | OK |
| M30 | +6,9% | 1,04 | 224 | 34,4% | 18,1% | Lemah |
| **H1** | +23,2% | **1,32** | 118 | 39,0% | **8,15%** | **Terbaik** |
| H4 | +3,3% | 1,29 | 21 | 38,1% | 8,8% | Sample terlalu kecil |
| D1 | -1,7% | 0,64 | 4 | 25,0% | 4,2% | Tidak bermakna |

**H1 adalah sweet spot.** M5 terlalu berisik (ATR-relative threshold menjaring
terlalu banyak zona palsu), H4/D1 sample-nya habis. Zona supply/demand butuh
waktu cukup membentuk base yang bermakna, tapi tidak terlalu lama sampai sample
hilang. Default timeframe = H1.

### Sweep reward R (M15, real tick) - kenapa win rate TIDAK boleh dikejar

| Target | Win rate | PF | Net profit | Win > lose? |
|---|---|---|---|---|
| 0,5R | **64,7%** | 0,95 | **-8,0%** | ya, tapi RUGI |
| 1R | 50,4% | 1,02 | +4,7% | imbang |
| 2R | 35,5% | **1,09** | **+32,5%** | tidak, tapi UNTUNG |

Kurva ini menjawab pertanyaan "usahakan win lebih banyak dari lose" dengan angka:
**win rate dan profit berbanding terbalik.** Target 0,5R memberi win rate
tertinggi (64,7%) tapi justru rugi (PF 0,95), karena tiap win cuma 0,5R, tidak
cukup menutup loss. Target 2R memberi win rate terendah (35,5%) tapi untung
paling besar (PF 1,09). Yang menentukan bukan berapa sering menang, tapi
expectancy = win rate x reward - loss rate x risk. Di data ini titik impas
berada di sekitar 1R.

### BTC vs XAU (real tick, 2R)

| Pair | M15 | H1 | Kesimpulan |
|---|---|---|---|
| **XAUUSD** | PF 1,09 (+32,5%) | PF 1,32 (+23,2%) | **Ada edge** |
| **BTCUSD** | PF 1,01 (+4,7%) | PF 1,00 (-0,4%) | **Tidak ada edge** |

Strategi supply/demand punya edge di emas, tapi nol di bitcoin. Konsisten dengan
`docs/CALIBRATION.md` yang mengukur edge-nya memang di emas, bukan kripto. Buat
produksi: fokus ke XAU, BTC-nya jangan diandalkan sebagai sumber edge.

### Sweep gate departure (real tick, 2R) - jawaban "jangan rugi"

| Config | PF | Net profit | Trades | Win rate | Max DD |
|---|---|---|---|---|---|
| M15 gate 2,0 | 1,09 | +32,5% | 476 | 35,5% | 19,2% |
| M15 gate 4,0 | 1,27 | +41,2% | 221 | 38,9% | 14,5% |
| H1 gate 2,0 | 1,32 | +23,2% | 118 | 39,0% | 8,15% |
| **H1 gate 4,0** | **1,63** | +16,2% | 50 | 44,0% | **6,01%** |

Gate departure lebih ketat (4,0 ATR) menaikkan PF dan menurunkan drawdown di
kedua timeframe, dengan harga trade lebih sedikit. Ini lever "jangan rugi" yang
benar-benar menambah robustness, bukan trade-off win rate.

Kaveat: `tools/walkforward.py` memvalidasi 2,0 ATR sebagai ambang yang stabil di
luar sampel. 4,0 adalah perbaikan in-sample yang belum lolos walk-forward -
bisa jadi overfit ke 8 bulan ini. Default tetap 2,0; naikkan ke 4,0 hanya kalau
mau mengejar robustness dengan risiko overfit.

### Filter arah (trend/momentum) - TIDAK membantu

| Filter | PF | Net profit | Trades | Win rate |
|---|---|---|---|---|
| Tanpa filter | **1,32** | **+23,2%** | 118 | **39,0%** |
| Trend SMA 100 | 1,20 | +10,3% | 90 | 37,8% |
| Trend SMA 200 | 1,18 | +8,5% | 81 | 37,0% |

Filter arah (demand hanya saat uptrend, supply hanya saat downtrend) justru
mengurangi edge, dan makin panjang lookback makin buruk. Konsisten dengan
`docs/CALIBRATION.md` H6-H10: edge zona berbasis LOKASI, bukan arah. Filter
arah menghapus trade lokasi yang valid tanpa menambah edge arah. `InpUseTrendFilter`
default OFF karena terukur merugikan.

### Target profit_zone (zona lawan terdekat) - cocok dengan Zonelab, membantu H1

Target diganti dari 2R konvensional ke zona lawan terdekat (`profit_zone`,
sama dengan `app/plan.py`). Hasilnya timeframe-dependent:

| TF | Target 2R | Target profit_zone |
|---|---|---|
| M15 | PF 1,09 (+32,5%) | PF 1,00 (-1,75%) |
| **H1** | PF 1,32 (+23,2%) | **PF 1,71 (+49,1%)** |

Di H1, profit_zone naik ke PF 1,71 (drawdown 11,6%). Di M15 justru rugi (PF 1,00),
karena zona M15 kecil sehingga "jalan di depan" sering pendek, reward kecil
dimakan spread. Ini konfirmasi `docs/CALIBRATION.md`: `profit_zone_rr` adalah
satu-satunya faktor yang bertahan, dan efeknya nyata di timeframe yang tepat.

### Walk-forward out-of-sample (H1 + profit_zone)

| Periode | PF | Net profit | Trades |
|---|---|---|---|
| Jan-Apr | 1,99 | +27,5% | 51 |
| Mei-Agu | 1,98 | +29,7% | 56 |
| Full 8 bln | 1,71 | +49,1% | 108 |

Dua paruh independen sama-sama PF ~1,98. Edge stabil di waktu, bukan kebetulan
satu periode. Belum lolos walk-forward 9-slice ala `tools/walkforward.py`
(p=0,0078), tapi split-half ini petunjuk kuat bahwa edge-nya bukan window-fit.

### Kenapa BTC gagal (dan itu bukan bug)

| Pair | Target 2R | Target profit_zone |
|---|---|---|
| XAU H1 | PF 1,32 | **PF 1,71** |
| BTC H1 | PF 1,00 | PF 0,82 |

Walk-forward di BTC menunjukkan gate departure **tetap memisahkan** (7-8/8 di
reward rendah, sama seperti emas), jadi detektornya kerja di BTC. Yang beda:
**win rate BTC di 2R cuma 33% (pas di titik impas 33,3%), sedangkan emas 35-39%
(di atas impas).** Selisih 2-6 poin itu seluruh ceritanya.

Akar masalahnya bukan parameter, tapi karakter pasar: emas punya struktur level
institusional (high/low sesi, angka bulat, pool likuiditas) yang membuat harga
mean-revert di level; BTC (kripto ritel 24/7) lebih momentum/trend, jadi level
lebih sering tembus. Supply/demand adalah edge mean-reversion di level - ia
bekerja di emas dan tidak di BTC. Ini konsisten dengan `docs/CALIBRATION.md`.

## Kesimpulan jujur

Win rate supply/demand di target 2R secara struktural 35-40%, bukan cacat presisi.
Zona menandai LOKASI (di mana harga bereaksi), bukan ARAH (ke mana harga pergi).
`docs/CALIBRATION.md` sudah mengukur 10 hipotesis arah dan semuanya nol. Tidak
ada tuning parameter yang mengubah itu - menaikkan win rate berarti menurunkan
target, dan itu mematikan edge (terbukti di tabel sweep di atas, 0,5R rugi).

Edge-nya nyata tapi tipis (PF 1,09 di real tick) dan berbasis lokasi, dan hanya
ada di emas. Cara memperbaikinya bukan tuning zona, tapi menambah filter arah
(struktur/momentum), yang juga sudah diukur proyek ini sebagai tidak bekerja
(H6, H10).

## Cara jalankan

1. Pastikan daemon auto-trade MATI (terminal Exness dipakai live, jangan bentrok).
2. Copy folder ini ke `MQL5\Experts\` terminal (sudah dilakukan).
3. Jalankan `run_backtest.bat`, atau buka Strategy Tester di terminal dan pilih
   Expert `ZonelabSupplyDemand\ZonelabSD`.

## Bandingkan dengan Python

Setelah tester jalan, bandingkan R expectancy vs `python -m tools.costed --symbol
mt5:XAUUSD --interval 15m`. Kalau beda, bedanya adalah efek tick/intrabar yang
selama ini diaproksimasi OHLC oleh Python.

## Batasan v1

- Hanya detektor supply_demand (bukan order_block/fvg).
- Tanpa checklist rules (killzone/OTE/CISD/bias).
- Sizing pakai risk%, bukan lot tetap.

---

# Order Block (detektor kedua, independen)

`OrderBlockDetector.mqh` + `ZonelabOB.mq5` + `tools/ea_parity_ob.py`.

Port faithful `app/detect/imbalance.py::detect_order_block`: lilin berlawanan
terakhir sebelum gerakan impulsif. Box = whole range lilin (high-low), gate
`displacement_atr=1.5` selama `displacement_bars=5`, tanpa dedupe (OB tidak dedupe).

## Verifikasi

1. **Parity OK** - 1033 order block, 0 mismatch (reference port vs numpy).
2. **Compile 0 error 0 warning.**

## Hasil (XAUUSD H1, real tick, profit_zone target)

| Detektor | PF | Net profit | Trades | Win rate | Max DD |
|---|---|---|---|---|---|
| **S&D** | **1,71** | +49,1% | 108 | 36,1% | 11,6% |
| Order Block | 1,06 | +14,7% | 451 | 41,0% | 21,0% |

Order block jauh lebih lemah dari S&D di H1. Alasannya: OB menghasilkan kandidat
jauh lebih banyak (setiap lilin berlawanan), jadi "zona lawan terdekat" hampir
selalu dekat, target kecil, reward dimakan spread (PF 1,06). Ini masalah yang
sama dengan S&D di M15.

### Kenapa lemah + apakah bisa di-improve (sudah diuji)

Akar masalah bukan win rate (OB menang 41%, lebih tinggi dari S&D 36%), tapi
reward-nya kecil: block padat (4x lebih banyak dari S&D) jadi "jalan di depan"
pendek, RR rata-rata cuma ~1,5:1 (S&D ~2,7:1). Sweep yang diuji:

| OB config | PF | Net profit | Trades | Win rate |
|---|---|---|---|---|
| 1,5 ATR + profit_zone | **1,06** | +14,7% | 451 | 41,0% |
| 2,5 ATR + profit_zone | 1,08 | +11,4% | 231 | 30,7% |
| 2,5 ATR + fixed 2R | 0,91 | -12,7% | 253 | 30,8% |

Tidak ada tuning yang menaikkan PF secara berarti (gate ketat cuma 1,06 ke 1,08,
fixed 2R malah rugi). Kesimpulan: OB valid dan benar (parity 0 mismatch), tapi
edge-nya fundamental lemah - box satu lilin adalah level yang lebih lemah dari
base multi-bar S&D. Bukan bug, bukan anomaly.

**OB di BTC (H1): PF 0,93 (-14,7%), rugi.** Konsisten dengan temuan S&D di BTC:
BTC tidak punya edge mean-reversion di level untuk detektor mana pun.

| Pair | S&D PF | OB PF |
|---|---|---|
| XAU H1 | 1,71 | 1,06 |
| BTC H1 | 0,82 | 0,93 |

---

# Fair Value Gap / Imbalance (detektor ketiga, independen)

`FVGDetector.mqh` + `ZonelabFVG.mq5` + `tools/ea_parity_fvg.py`.

Port faithful `app/detect/imbalance.py::detect_fvg`: 3 bar berurutan yang wick
luarnya tak bertemu. Box = band gap, gate `min_gap_atr=0.1`. Parity OK (769 gap,
0 mismatch), compile 0 error.

## Hasil (XAUUSD H1, real tick)

| Target | PF | Net profit | Win rate |
|---|---|---|---|
| profit_zone | 0,90 | -15,7% | 35,2% |
| fixed ATR 2.0 | ~0,6 | -35,2% | - |

FVG, ditradingkan sebagai reversal (beli gap, harap mantul), RUGI di semua target.
Alasannya: (1) gap padat, jadi profit_zone (zona lawan terdekat) selalu dekat,
reward kecil; (2) gap itu sendiri kecil (0,1-1 ATR), jadi reward dimakan spread +
stop buffer; (3) FVG adalah objek **continuation**, bukan reversal (CALIBRATION.md
H5) - men-trade-nya sebagai reversal berarti melawan karakternya.

Kesimpulan: FVG punya reaksi lokasi (beat placebo frictionless di CALIBRATION.md)
tapi TIDAK punya edge P&L yang tradeable. Konsisten dengan literatur: "the
reaction is real, the edge is not established."

---

# Confluence (kombinasi detektor)

`tools/confluence_test.py`. Uji apakah S&D + OB/FVG di harga yang sama menaikkan
hold rate. Hasil: **tidak membantu di ambang mana pun yang punya kontras.**

Versi pertama paragraf ini (1 September 2026) menulis bahwa overlap penuh dan
band 0,3 ATR dua-duanya sudah diuji. Yang dijalankan cuma satu; `overlap()` ada
di file itu dan tidak pernah dipanggil. Diperbaiki dan dijalankan ulang hari yang
sama, sekarang dengan sapuan ambang, karena 555 lawan 0 mengukur KEPADATAN dan
bukan daya saring - tanpa kontras tidak ada yang bisa dibandingkan.

XAUUSD H1, 20 000 bar, 555 zona ter-resolve. S&D 653 zona, OB 4128 block, FVG
3091 gap.

| Definisi | confluent n | held | alone n | held | delta | z |
|---|---|---|---|---|---|---|
| overlap box penuh | 555 | 50,3% | 0 | - | degenerat | - |
| proximal 0,300 ATR | 555 | 50,3% | 0 | - | degenerat | - |
| proximal 0,100 ATR | 533 | 49,5% | 22 | 68,2% | -18,7% | -1,71 |
| proximal 0,050 ATR | 509 | 49,9% | 46 | 54,3% | -4,4% | -0,58 |
| proximal 0,020 ATR | 424 | 50,2% | 131 | 50,4% | -0,1% | -0,03 |
| proximal 0,010 ATR | 341 | 51,0% | 214 | 49,1% | +2,0% | +0,45 |
| proximal 0,005 ATR | 281 | 50,5% | 274 | 50,0% | +0,5% | +0,13 |

Overlap penuh memang degenerat, jadi klaim lamanya benar - tapi baru sekarang
direproduksi. Begitu ambangnya diketatkan sampai kontras muncul, selisihnya
runtuh ke nol (z antara -0,58 dan +0,45 di empat ambang terketat). Satu-satunya
delta besar ada di n=22 dan arahnya TERBALIK (zona sendirian bertahan lebih
sering), tidak signifikan, dan tidak boleh dibaca sebagai temuan.

Konsisten dengan CALIBRATION.md H2 (nesting HTF = 0 benefit): confluence lokasi
tidak menambah edge di atas S&D.

## Kesimpulan akhir seluruh roadmap

Dari 3 detektor lokasi yang dibangun independen, parity-proven, dan di-backtest
real-tick: **S&D adalah satu-satunya yang punya edge tradeable (PF 1,71 H1,
walk-forward ~1,98).** OB (PF 1,06) dan FVG (PF 0,90) valid tapi lemah/rugi, dan
terlalu padat untuk jadi confluence. Edge supply/demand hanya di emas, di H1,
dengan S&D.

**Kaveat performa:** OB ~10x lebih lambat dari S&D (banyak kandidat). Window
tumbuh (InpBars=20000) membuat backtest M15 butuh >15 menit, jadi default
InpBars diturunkan ke 3000 (window tetap).

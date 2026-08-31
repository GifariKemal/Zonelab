# ZonelabSupplyDemand - EA MQL5

EA backtest untuk drawing supply/demand Zonelab di MT5 Strategy Tester. Ini
port faithful dari `backend/app/detect/supply_demand.py` + `app/plan.py`.

## File

- `SupplyDemandDetector.mqh` - port detektor (Wilder ATR, classify, runs, gate,
  lifecycle, geometri box). Konvensi index sama dengan Python: index 0 = bar
  tertua.
- `ZonelabSD.mq5` - EA main. Entry limit di proximal (demand long, supply short),
  stop di distal - 0.25 ATR, target 2R, sizing risk%. Satu order per zona.
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

### Multi-timeframe (real tick / every tick)

| TF | Net profit | PF | Trades | Win rate | Max DD |
|---|---|---|---|---|---|
| M15 | +32,5% | 1,09 | 476 | 35,5% | 19,2% |
| M30 | +6,9% | 1,04 | 224 | 34,4% | 18,1% |
| **H1** | +23,2% | **1,32** | 118 | 39,0% | **8,15%** |

H1 paling robust (PF tertinggi, DD terendah), M30 paling lemah. Tidak ada satu
timeframe yang menang di semua metrik.

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
- Target 2R konvensional, bukan zona lawan terdekat (profit_zone = v2).
- Tanpa checklist rules (killzone/OTE/CISD/bias).

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

### Sweep reward R (M15, every tick) - kenapa win rate TIDAK boleh dikejar

| Target | Win rate | PF | Net profit | Expected payoff |
|---|---|---|---|---|
| 1R | **50,4%** | 1,02 | +4,7% | 0,99 |
| 2R | 35,7% | **1,10** | **+39,3%** | 8,25 |

Menurunkan target menaikkan win rate ke 50%, tapi mematikan edge (PF 1,02,
expected payoff nyaris nol). **2R dengan win rate 36% mengalahkan 1R dengan
50%.** Yang menentukan bukan win rate, tapi expectancy (reward-to-risk).

## Kesimpulan jujur

Win rate supply/demand di target 2R secara struktural 35-40%, bukan cacat presisi.
Zona menandai LOKASI (di mana harga bereaksi), bukan ARAH (ke mana harga pergi).
`docs/CALIBRATION.md` sudah mengukur 10 hipotesis arah dan semuanya nol. Tidak
ada tuning parameter yang mengubah itu - menaikkan win rate berarti menurunkan
target, dan itu mematikan edge (terbukti di tabel sweep di atas).

Edge-nya nyata tapi tipis (PF 1,09 di real tick) dan berbasis lokasi. Cara
memperbaikinya bukan tuning zona, tapi menambah filter arah (struktur/momentum),
yang juga sudah diukur proyek ini sebagai tidak bekerja (H6, H10).

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

# ZonelabSupplyDemand - EA MQL5

EA backtest untuk drawing supply/demand Zonelab di MT5 Strategy Tester. Ini
port faithful dari `backend/app/detect/supply_demand.py` + `app/plan.py`.

## File

- `SupplyDemandDetector.mqh` - port detektor (Wilder ATR, classify, runs, gate,
  lifecycle, geometri box). Konvensi index sama dengan Python: index 0 = bar
  tertua.
- `ZonelabSD.mq5` - EA main. Entry limit di proximal (demand long, supply short),
  stop di distal - 0.25 ATR, target 2R, sizing risk%. Satu order per zona.
- `tester.ini` - config Strategy Tester (M15, 1 minute OHLC).
- `run_backtest.bat` - script untuk menjalankan tester.

## Status verifikasi

1. **Parity OK** - `python -m tools.ea_parity` membuktikan algoritma loop
   eksplisit menghasilkan zona identik dengan detektor numpy (0 mismatch).
2. **Compile 0 error 0 warning** via MetaEditor.

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

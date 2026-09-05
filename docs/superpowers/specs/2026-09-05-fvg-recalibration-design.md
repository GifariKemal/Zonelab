# FVG Recalibration Design

Spec untuk rekalibrasi Fair Value Gap detection di Zonelab: akurasi geometri,
parameter gate, dan parity lintas engine.

## Latar belakang

FVG adalah objek paling crisp di vocabulary ICT: tiga bar berurutan yang wick
luarnya tidak bertemu. Definisinya tidak ambiguous, dua implementasi independen
yang membaca definisi yang sama harus menghasilkan output identik.

Zonelab sudah punya dua implementasi:
- Python: `app/detect/imbalance.py::detect_fvg`, 1231 test passing
- MQL5: `mql5/ZonelabSupplyDemand/FVGDetector.mqh`, parity-checked lawan Python

Evidence saat ini (`docs/detectors_costed.json`):
- Gate departure >= 2.0 ATR: **FAIL**, selisih -0,1005 R, t=-4,48
- Kohort di bawah gate: exp_R +0,094 R (positif, satu-satunya di file itu)
- Gate-nya **terbalik**: FVG kecil lebih bagus dari FVG besar

Evidence lanjutan (`docs/fvg_inverted.json`):
- 30m XAUUSD+BTCUSD: exp_R below-gate +0,2188 R, walk-forward 8/8 fold positif
- n_below = 3799, t = 8,53 lawan nol

Masalah bukan di detection (geometrinya benar), tapi di gate parameter yang
menyaring kohort yang salah. Rekalibrasi ini membuktikan detection benar secara
visual, lalu menemukan parameter optimal secara terukur.

## Scope

- Instrumen: XAUUSD saja. Cross-validation ke instrumen lain setelah pipeline jadi.
- Timeframe fokus: 30m (evidence terkuat), 1H dan 4H sebagai validasi.
- Ground truth: definisi pure ICT wick-to-wick, bukan indikator pihak ketiga.
- Deliverable: Pine Script + parameter recalibration + parity check + report.

## Arsitektur

Dua jalur paralel, bertemu di parity check:

```
Jalur Pine (TradingView Desktop)         Jalur Python (Zonelab rig)
================================         =========================
1. Tulis Pine Script FVG indicator       1. Parameter sweep grid
2. Compile di TradingView                2. Walk-forward 8-fold per config
3. Apply ke XAUUSD 30m/1H/4H            3. Output: docs/fvg_sweep.json
4. Baca box via data_get_pine_boxes
5. Screenshot per timeframe
          \                                /
           v                              v
       === PARITY CHECK (tools/fvg_parity.py) ===
       Match box Pine vs box Python pada bar yang sama
       Target: >= 95% agreement rate
                      |
                      v
              === GATE DECISION ===
              Parameter terbaik dari sweep
              yang parity-nya > 95%
                      |
                      v
              === REPORT ===
              docs/QA-FVG-RECALIBRATION.md
```

## Komponen 1: Pine Script FVG Detector

### File

`mql5/pine/ZonelabFVG.pine` (baru, di bawah mql5/ karena ini detector lintas
engine, bukan frontend).

### Tipe

Indicator, bukan strategy. Strategy memaksa satu sisi per waktu. Indicator
menggambar semua FVG kedua arah secara bersamaan.

### Input

| Parameter | Tipe | Default | Keterangan |
|---|---|---|---|
| `atr_period` | int | 14 | Panjang Wilder ATR, sama dengan Python |
| `min_gap_atr` | float | 0.1 | Minimum gap size dalam kelipatan ATR |
| `max_boxes` | int | 200 | Batas box.new(), constraint Pine Script |
| `show_labels` | bool | true | Label harga di tiap box |

### Logika detection

```
// Bar saat ini = bar[0], dua bar lalu = bar[2]
bullish_fvg = high[2] < low[0]    // wick bawah bar ke-3 di atas wick atas bar ke-1
bearish_fvg = low[2] > high[0]    // wick atas bar ke-3 di bawah wick bawah bar ke-1

gap_size_bull = low[0] - high[2]
gap_size_bear = low[2] - high[0]

atr_val = ta.atr(atr_period)
passes_filter_bull = gap_size_bull >= min_gap_atr * atr_val
passes_filter_bear = gap_size_bear >= min_gap_atr * atr_val
```

Identik dengan `_gap()` di `imbalance.py` baris 191-203.

### Output

- Box: biru transparan (demand), merah transparan (supply), extend right
- Label: `"FVG {size:.2f} ATR"` di tengah box
- Console: `log.info("FVG,{time},{side},{top},{bottom},{size_atr}")` per FVG

Console log format fixed supaya bisa di-parse untuk parity check.

### Tidak termasuk

- Lifecycle tracking (fresh/tested/mitigated/broken) - itu concern `_finish()` di Python
- Gate departure - ini MURNI detection, gate ada di layer terpisah
- Scoring atau ranking

## Komponen 2: Python Parameter Sweep

### File

`backend/tools/fvg_sweep.py` (baru).

### Fungsi

Reuse `detect_fvg` dari `app/detect/imbalance.py` tanpa modifikasi. Sweep grid:

| Parameter | Values |
|---|---|
| `min_gap_atr` | 0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5 |
| `atr_period` | 14 |
| `gate_atr` | 0, 0.25, 0.5, 1.0, 1.5, 2.0 |

`atr_period` di-pin ke 14 karena sweep di `detectors_costed` sudah menunjukkan
ia tidak signifikan. Satu variabel tetap, dua yang bergerak.

Total konfigurasi: 7 x 6 = 42.

### Data

MT5 provider, prefix `mt5:`, XAUUSD 30m. Target 50k+ bar supaya tiap fold
punya n >= 20 di kohort above-gate (constraint dari preregistration).

### Metrik per konfigurasi

- `n_above`, `n_below`: jumlah FVG di atas dan bawah gate
- `exp_r_above`, `exp_r_below`: ekspektansi resolved R tiap kohort
- `difference`: `exp_r_below - exp_r_above` (positif = gate terbalik)
- `welch_t`: signifikansi selisih
- Walk-forward 8-fold: berapa fold yang positif
- `exp_r_all`: ekspektansi kalau gate dibuang (semua FVG masuk)

### Output

`docs/fvg_sweep.json` - array 42 objek, sorted by `exp_r_below` walk-forward
stability (jumlah fold positif, lalu magnitude).

### Resolusi intrabar

Sama dengan rig yang ada: zona 30m, resolved pada bar 5m. Rasio 6, batas atas.
Kontrol resolusi dari `tools/lowtf_resolution.py` wajib dijalankan pada
parameter terpilih sebelum klaim final.

## Komponen 3: Parity Check

### File

`backend/tools/fvg_parity.py` (baru).

### Input

Dua sumber box coordinates pada rentang bar yang sama:
1. **Pine**: dari `data_get_pine_boxes` atau parse console log
2. **Python**: dari `detect_fvg` yang dijalankan pada OHLCV range yang sama

### Matching rule

Dua FVG dianggap identik jika:
- `time_from` identik (bar origin yang sama, resolusi detik)
- `side` identik (demand vs supply)
- `|top_pine - top_python| < tick_size` (toleransi satu tick instrumen: 0.01
   untuk XAUUSD, karena kedua engine membaca harga yang sama dari sumber
   yang sama, perbedaan hanya dari float rounding)
- `|bottom_pine - bottom_python| < tick_size`

### Output

`docs/fvg_parity.json`:
- `match_rate`: persentase FVG yang cocok
- `pine_only`: list FVG yang ada di Pine tapi tidak di Python
- `python_only`: list FVG yang ada di Python tapi tidak di Pine
- `geometry_mismatch`: list FVG yang time-nya cocok tapi harga berbeda
- `n_pine`, `n_python`, `n_matched`

### Target

>= 95% match rate. Kalau di bawah itu, tiap mismatch di-trace satu per satu
sampai root cause ditemukan (perbedaan ATR calculation, bar alignment, float
precision).

## Komponen 4: Gate Decision

Setelah sweep dan parity selesai, keputusan gate diambil berdasarkan evidence:

| Opsi | Kondisi untuk dipilih |
|---|---|
| Buang gate | `exp_r_all` (gate=0) positif, t > 2,24, walk-forward >= 7/8 |
| Balik gate (ambil FVG kecil) | `exp_r_below` pada threshold X terbaik, walk-forward >= 7/8 |
| Gate property lain | Tidak ada dalam scope sweep ini, tapi dicatat kalau evidence mengarah |
| Tidak ubah | Tidak ada konfigurasi yang pass kriteria |

Kriteria pass sama dengan preregistration di `detectors_costed.json`:
- difference > 0
- |welch t| > 2,24 (Bonferroni corrected)
- Walk-forward >= 7 of 8 fold positif
- Sign test p < 0,01

## Komponen 5: Report

### File

`docs/QA-FVG-RECALIBRATION.md`

### Isi

1. Ringkasan temuan: parameter optimal, parity rate, perubahan gate
2. Tabel sweep: 42 konfigurasi, ranked
3. Parity matrix: match rate per timeframe
4. Screenshot TradingView: XAUUSD 30m dengan FVG Pine Script terpasang
5. Keputusan: parameter mana yang di-ship, alasannya angka bukan argumen
6. Kontrol resolusi: hasil `lowtf_resolution` pada parameter terpilih
7. Apa yang TIDAK berubah dan kenapa

### Style

Mengikuti `docs/README.md` convention: setiap angka dari command yang bisa
dijalankan ulang, setiap klaim punya provenance.

## File yang berubah

| File | Perubahan |
|---|---|
| `mql5/pine/ZonelabFVG.pine` | BARU - Pine Script indicator |
| `backend/tools/fvg_sweep.py` | BARU - parameter sweep tool |
| `backend/tools/fvg_parity.py` | BARU - parity check tool |
| `docs/fvg_sweep.json` | BARU - sweep results |
| `docs/fvg_parity.json` | BARU - parity results |
| `docs/QA-FVG-RECALIBRATION.md` | BARU - report |
| `backend/app/models/params.py` | MUNGKIN - update default `ImbalanceParams` jika parameter berubah |
| `backend/app/layers.py` | MUNGKIN - update evidence string FVG |

## File yang TIDAK berubah

- `backend/app/detect/imbalance.py` - detection logic tidak diubah, yang berubah
  hanya parameter yang dikirim ke sana
- `mql5/ZonelabSupplyDemand/FVGDetector.mqh` - MQL5 EA tetap, Pine Script adalah
  engine ketiga yang independen
- Test yang ada - 1231 test tetap hijau, tidak ada yang diganti

## Urutan eksekusi

Paralel dua jalur, dependency ada di parity check:

```
[Pine Script]  ----compile----> [Apply chart] ----> [Read boxes] --\
                                                                    +--> [Parity] --> [Gate] --> [Report]
[Sweep tool]   ----run-------> [fvg_sweep.json] -----------------/
```

Pine Script dan sweep tool bisa dikerjakan bersamaan. Parity check butuh output
keduanya. Gate decision butuh parity dan sweep. Report butuh semuanya.

## Risiko dan mitigasi

| Risiko | Mitigasi |
|---|---|
| Pine max 500 box.new() | `max_boxes` input, delete oldest saat penuh |
| Parity < 95% karena ATR divergence | Pine pakai `ta.atr()` (Wilder), Python pakai `wilder_atr()` - keduanya Wilder, tapi seed bar pertama bisa beda. Trace per-bar jika terjadi |
| Sweep 42 config x 8 fold = 336 run | Tiap run < 1 detik di MT5 provider, total < 6 menit |
| TradingView Desktop tidak hidup | `tv_launch` dulu, cek `tv_health_check` |
| Gate decision: tidak ada config yang pass | Dicatat sebagai temuan, bukan kegagalan. "Tidak ada gate yang bekerja" adalah jawaban yang valid |

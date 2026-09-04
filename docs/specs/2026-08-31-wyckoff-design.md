# Spec: Wyckoff Schematic + Market Maker Buy/Sell Model

- Tanggal: 2026-08-31
- Slice: S3 dari decomposition 2026-08-31
- Status: menunggu review owner

## 1. Ringkasan

S3 membedah dua nama yang sering disamakan tapi beda sumber: **Market Maker
Buy/Sell Model** (ICT) dan **Wyckoff schematic** (Richard Wyckoff). Temuan
utamanya: yang pertama SUDAH ada di repo ini, dan yang kedua cuma sebagian
kecilnya yang bisa dikode tanpa mengarang.

## 2. Sumber, dan status riset

Fetch web gagal di sesi ini (SSL handshake, 404, halaman tidak relevan). Wyckoff
Method adalah metode analisis teknikal yang terdokumentasi sejak 1930-an, jadi
definisi di bawah dikutip dari metode yang mapan, bukan dari halaman yang saya
fetch sekarang. Sumber kanoniknya:

- Richard D. Wyckoff, "Studies in Tape Reading" dan kursus aslinya.
- Hank Pruden, "The Three Skills of Top Trading" (2007).
- StockCharts.com, seri "Wyckoff Method" dan halaman "Wyckoff Accumulation" /
  "Wyckoff Distribution".
- Wyckoff Analytics (khususnya untuk skema skematik dan volume).

Bila perlu, daftar sumber ini diisi ulang lewat fetch saat infra web normal.

## 3. Temuan utama: MM buy/sell model = AMD, sudah ada

"Market Maker Buy Model" dan "Sell Model" adalah bahasa ICT untuk siklus yang
sudah ada di repo ini sebagai `amd_profile`:

| Istilah ICT | Fase | Di repo |
|---|---|---|
| MM Buy Model | Accumulation -> Manipulation (sweep low) -> Distribution (markup) | `amd_profile` + `manipulation_after_accumulation` di `app/ict.py` |
| MM Sell Model | Distribution -> Manipulation (sweep high) -> Distribution (markdown) | idem, cermin |

`app/ict.py` sudah memodelkan `AMDX`, `XAMD`, `AAMD` dan klausa
`manipulation_after_accumulation` ("sesudah A pasti manipulation terdahulu").
Jadi setengah dari S3 TIDAK perlu dibangun ulang. Yang benar-benar baru adalah
skema Wyckoff, yang lebih granular dari AMD.

## 4. Wyckoff schematic: yang bisa diturunkan vs yang diskresioner

Ini bagian yang menentukan. Skema Wyckoff penuh punya fase bernama, dan
sebagian besar tidak bisa dikode dari OHLC tanpa mengarang.

Fase akumulasi: PS (Preliminary Support), SC (Selling Climax), AR (Automatic
Rally), ST (Secondary Test), Spring, Test, SOS (Sign of Strength), LPS (Last
Point of Support), BU (Backup).

Fase distribusi (cermin): PSY, BC (Buying Climax), AR, ST, UT (Upthrust), UTAD,
SOW (Sign of Weakness), LPSY.

| Fase | Butuh | Bisa dikode dari OHLC? |
|---|---|---|
| Trading Range (TR) | konsolidasi | **Ya** - high/low sebuah rentang |
| Spring | sweep low TR lalu close balik ke dalam | **Ya** - sweep + reversal |
| Upthrust | sweep high TR lalu close balik ke dalam | **Ya** - sweep + reversal |
| SOS (Sign of Strength) | close/break di atas high TR | **Ya** |
| SOW (Sign of Weakness) | close/break di bawah low TR | **Ya** |
| SC / BC (climax) | volume klimaks | Tidak - butuh volume |
| ST vs Spring | volume menyusut | Tidak - butuh volume |
| PS / AR / LPS / BU | konteks + diskresi | Tidak |

Yang bisa dikode adalah **lima**: TR, Spring, Upthrust, SOS, SOW. Sisanya
ditinggalkan, bukan ditaksir - repo ini menolak mengarang rule tanpa sumber, dan
membedakan ST dari Spring tanpa volume adalah persis pengkarangan itu.

## 5. Tumpang tindih dengan primitif yang sudah ada

Lima fase yang bisa dikode itu sudah punya rumah di repo, jadi S3 bukan detektor
baru yang berdiri sendiri, melainkan **pembacaan fase** di atas primitif yang
sudah ada:

| Fase Wyckoff | Primitif existing |
|---|---|
| TR | `dealing_range` / `base_drift` + `base_overlap` (konsolidasi) |
| Spring / Upthrust | `structure` SWEEP + `reversed_within` (sweep + reversal) |
| SOS / SOW | `structure` MSS / BOS (break) |

Artinya S3 menambah **framing dan label fase**, bukan geometri baru. Ini penting
dikatakan di depan: kalau pembacaan fase ini nol, itu konsisten dengan H6/H9
yang sudah mengukur objek structure sebagai nol.

## 6. Desain

Satu module `app/wyckoff.py` yang membaca bar dan mengeluarkan fase, plus satu
layer `wyckoff` (overlay, di `bar_overlays`) dan satu primitive.

```
app/wyckoff.py:
  trading_range(candles, lookback) -> TR | None   # rentang konsolidasi
  phases(candles) -> list[WyckoffPhase]           # spring / upthrust / sos / sow

WyckoffPhase: { at, kind, level, tr_low, tr_high, knowable_at }
```

Aturan fase, semuanya diturunkan dari OHLC dan dikutip, bukan dikarang:

- TR: rentang high/low dari jendela yang `base_overlap`-nya tinggi (konsolidasi,
  bukan staircase) - reuse kriteria `base_drift` < 0.6 yang sudah diukur di
  `docs/FIDELITY.md`.
- Spring: sweep di bawah TR low yang close balik di dalam TR, dalam `sweep_reversal_bars`.
- Upthrust: cermin di atas TR high.
- SOS: close di atas TR high setelah TR terbentuk.
- SOW: close di bawah TR low setelah TR terbentuk.

## 7. Batas (YAGNI)

- Tidak ada deteksi SC/BC/ST (butuh volume). Dinyatakan, bukan di-taksir.
- Tidak ada skor "probabilitas buy/sell model". Pertanyaan itu adalah PERTANYAAN
  PENGUKURAN, dan dijawab harness praregistrasi `tools/wyckoff_outcomes.py`
  (ditulis, di-run saat terminal MT5 sepi), bukan oleh detektor.
- Tidak ada layer untuk MM buy/sell model terpisah - sudah ada di checklist.

## 8. Testing

- Selfcheck: gate tidak kosong (fase disuntik cacat, pastikan gagal).
- No repaint: prefiks membesar, fase yang terbit tidak berubah.
- Anti-lookahead: `knowable_at` dihitung, tidak ada fase yang terbit sebelum
  bar-nya tutup.

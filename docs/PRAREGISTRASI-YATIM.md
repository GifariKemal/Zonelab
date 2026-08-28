# Praregistrasi modul yatim, 28 Agustus 2026

Dokumen ini ditulis **sebelum** satu angka pun dihitung untuk kolom-kolom di
bawah. Ia praregistrasi ketiga di repo ini, mengikuti
[PRAREGISTRASI-KONDISI.md](PRAREGISTRASI-KONDISI.md) (21 Agustus, dua daftar:
`COLUMNS` lalu `ICT_COLUMNS`).

> [!IMPORTANT]
> Kalau sebuah kolom tidak ada di Bagian 3, ia tidak boleh dilaporkan sebagai
> temuan. Aturan yang sama, dan alasan yang sama: `formation_score` dengan AUC
> 0,464 dan 0,477 adalah bukti repo ini pernah menghasilkan temuan palsu dengan
> cara melihat dulu baru memilih kolom.

## 1. Pertanyaannya

Audit 28 Agustus 2026 menemukan enam modul yang ada di `backend/app/` dan tidak
diimpor oleh satu pun jalur keputusan. Dibuktikan dengan grep importer, bukan
dengan membaca nama file:

| Modul | Diimpor oleh | Catatan |
|---|---|---|
| `app/judas.py` | nol, di mana pun | tidak ada test sama sekali |
| `app/psp.py` | `tests/test_psp.py` | docstring baris 3: "NOT WIRED" |
| `app/ladder.py` | `tests/test_ladder.py` | docstring baris 42: "STILL NOT WIRED" |
| `app/m4.py` | `tools/quant.py` | hanya `in_judas_window` |
| `app/zscore.py` | `tools/quant.py` | sudah diukur, lihat Bagian 5 |
| `app/regime.py` | `tools/quant.py` | sudah diukur, lihat Bagian 5 |

Empat yang pertama dibuat oleh commit `ae6d9eb` yang berjudul "Residual gaps
resolved". Mereka terkompilasi tanpa error. Tidak satu pun tersambung ke jalur
yang menempatkan order, dan tidak satu pun pernah punya angka.

Pertanyaan dokumen ini: **apakah keadaan yang dilaporkan modul-modul itu
memisahkan ekspektansi gerbang?** Bukan apakah mereka enak dibaca di chart.

## 2. Yang TIDAK diukur, dan kenapa

`app/ladder.py:for_cycle(cycle, has_psp)` adalah tabel lookup murni. Ia tidak
menerima satu pun bar, harga, atau waktu; ia memetakan nama cycle ke tiga nama
timeframe. Mengukurnya sebagai sinyal adalah kesalahan kategori: ia tidak punya
input pasar untuk dikorelasikan dengan hasil.

Ia dinyatakan **tidak dapat diuji sebagai sinyal** di sini, sekarang, sebelum
angka apa pun ada, supaya tidak ada yang tergoda melaporkan ketiadaan efeknya
sebagai temuan.

## 3. Kolom yang diuji

Semua dibaca **pada bar sentuhan pertama**, instan yang sama yang dipakai
seluruh populasi terukur di [CALIBRATION.md](CALIBRATION.md).

| Kolom | Sumber | Nilai |
|---|---|---|
| `in_judas_window` | `app/m4.py:in_judas_window` | True, False |
| `judas_template` | `app/judas.py:classify` atas bias sesi London hari itu | A, B, C, D |
| `psp_before_touch` | `app/psp.py:detect` dalam 10 bar sebelum sentuhan | True, False |
| `true_opens_in_zone` | `app/poi.py:confluence.true_opens`, dipotong | 0, 1-3, 4-9, 10+ |
| `ote_band` | `zone.dealing_range_pos` dari `mark_dealing_range` | discount, ote, equilibrium, premium, none |

`ote_band` menutup satu item yang terbuka sejak 24 Agustus: filter OTE tidak
pernah bisa di-backtest karena baris trade dari `costed.trades()` tidak membawa
`dealing_range_pos`. Sekarang membawanya.

## 4. Ambang lulus, ditulis sekarang

Sama persis dengan praregistrasi 21 Agustus, tanpa pelonggaran:

1. `n >= 30` per grup.
2. `|t|` melewati nilai kritis yang sudah dikoreksi Bonferroni, `alpha` 0,05
   dibagi jumlah grup yang layak dinilai. Jumlah grup dihitung **sebelum** satu
   baris pun dilaporkan.
3. Tanda yang sama di kedua paruh sampel.

Lulus ketiganya berarti kolom itu berhak atas run walk-forward pada
subpopulasinya. **Tidak** berarti ia langsung masuk `--require`.

## 5. Yang sudah punya angka, jadi tidak diulang di sini

| Sudah diukur | Hasil | Sumber |
|---|---|---|
| tCISD sebagai entry mandiri | -0,926 R, 0 dari 11 positif | transkrip sesi 24 Agustus |
| tCISD sebagai filter | -0,087 R, identik baseline | transkrip sesi 24 Agustus |
| Z-Score + volume + regime, 24 sel | -0,0893 ke -0,1301 R, sign test p=0,405, nol sel CI lepas nol ke atas | sesi 28 Agustus |

Ketiganya negatif atau nol. Karena itu `tcisd`, `zscore`, dan `regime` tidak
masuk daftar Bagian 3: pertanyaan tentang mereka sudah dijawab, dan mengukur
ulang hal yang sama dengan harapan hasil berbeda adalah cara lain menghasilkan
temuan palsu.

## 6. Apa yang terjadi pada hasil apa pun

Kolom yang **lulus** ketiga syarat: dicatat di sini dengan angkanya, lalu
walk-forward. Kolom yang **gagal**: dicatat di sini dengan angkanya juga, dan
modulnya tetap yatim dengan alasan tertulis. Tidak ada kolom yang dihapus dari
laporan karena hasilnya mengecewakan.

## 7. Hasil, 28 Agustus 2026

`python -m tools.conditioned --symbol mt5:XAUUSD --interval 1h --bars 20000`,
populasi n=535, exp R -0,021. **87 grup layak dinilai, jadi alpha 0,05/87 dan
|t| kritis 3,44.** Jumlah grup dihitung sebelum satu baris dilaporkan, seperti
yang dijanjikan Bagian 4.

### `in_judas_window` (app/m4.py)

| Nilai | n | exp R | delta | t | paruh |
|---|---:|---:|---:|---:|---|
| False | 478 | -0,016 | +0,045 | +0,27 | +0,110 / -0,099 |
| True | 57 | -0,061 | -0,045 | -0,27 | -0,110 / +0,099 |

**GAGAL.** |t| 0,27 lawan kritis 3,44, dan tandanya berbalik antar paruh di
kedua grup. Jendela 09:30-10:30 NY tidak memisahkan apa pun di sel ini.

### `judas_template` (app/judas.py)

| Template | n | exp R | t | paruh |
|---|---:|---:|---:|---|
| A | 184 | -0,029 | -0,14 | +0,034 / -0,038 |
| B | 162 | -0,005 | +0,23 | +0,044 / +0,003 |
| C | 62 | -0,033 | -0,09 | -0,013 / -0,038 |
| D | 127 | -0,024 | -0,03 | -0,094 / +0,063 |

**GAGAL.** Keempat template berada dalam rentang -0,033 sampai -0,005, |t|
tertinggi 0,23. Modul tanpa satu pun test ini juga tanpa satu pun efek terukur.

### `psp_before_touch` (app/psp.py)

| Nilai | n | exp R | t | paruh |
|---|---:|---:|---:|---|
| False | 213 | -0,026 | -0,09 | +0,024 / -0,072 |
| True | 322 | -0,018 | +0,09 | -0,024 / +0,072 |

**GAGAL.** Selisihnya 0,008 R, |t| 0,09.

### `true_opens_in_zone` (app/poi.py, setelah wiring 28 Agustus)

| Jumlah | n | exp R | delta | t | paruh |
|---|---:|---:|---:|---:|---|
| **0** | **75** | **+0,290** | **+0,361** | **+2,35** | **+0,138 / +0,579** |
| 1-3 | 252 | -0,077 | -0,105 | -1,18 | -0,057 / -0,159 |
| 4-9 | 176 | -0,054 | -0,049 | -0,56 | +0,031 / -0,128 |
| 10+ | 32 | -0,128 | -0,113 | -0,83 | -0,147 / -0,049 |

**GAGAL, tapi ini yang paling dekat.** Grup "nol True Open di dalam box" lolos
dua dari tiga syarat: n=75 dan tanda yang sama di kedua paruh (+0,138 dan
+0,579). Yang tidak dilewatinya adalah ambangnya sendiri, |t| 2,35 lawan 3,44.

Arahnya juga berlawanan dengan yang diduga metode: zona yang **tidak** memuat
True Open justru lebih baik, dan makin banyak True Open di dalamnya makin
buruk, monoton dari +0,290 ke -0,128. Itu pembacaan yang menarik dan **tidak
boleh dilaporkan sebagai temuan** sebelum melewati ambang.

### `ote_band` (app/ict.py, klausa `ote`)

| Pita | n | exp R | delta | t | paruh |
|---|---:|---:|---:|---:|---|
| discount | 167 | -0,134 | -0,165 | -1,76 | -0,153 / -0,162 |
| **ote** | **67** | **-0,096** | **-0,086** | **-0,80** | **+0,023 / -0,192** |
| premium | 288 | +0,053 | +0,161 | +1,81 | +0,145 / +0,169 |
| none | 13 | terlalu kecil | | | |

**GAGAL.** Dan ini menjawab pertanyaan yang terbuka sejak 24 Agustus: pita OTE
itu sendiri terbaca **-0,096**, lebih buruk daripada populasinya (-0,021), dan
tandanya berbalik antar paruh. Aturan "proximal wajib di dalam OTE" tidak
didukung angka di sel ini.

Batas tafsir yang harus disebut: `discount` dan `premium` di tabel ini adalah
posisi mentah dalam dealing range dan **tidak arah-sadar**, jadi keduanya
mencampur demand dan supply. Hanya baris `ote` yang arah-sadar. Bucketing itu
sudah tertulis di Bagian 3 sebelum angkanya ada, jadi ia dilaporkan apa adanya,
tapi ia tidak bisa dibaca sebagai "premium bagus".

## 8. Putusan

Nol dari lima kolom melewati ambang praregistrasi. Konsekuensinya, ditulis
sesuai janji Bagian 6:

- `app/m4.py`, `app/judas.py`, `app/psp.py` **tetap yatim**, sekarang dengan
  alasan berangka, bukan karena terlupakan.
- `app/ladder.py` tetap yatim dan dinyatakan tidak dapat diuji sebagai sinyal
  di Bagian 2, sebelum angka apa pun ada.
- Klausa `ote` tetap ada di checklist dan tetap `doctrine`, tetap tidak
  diwajibkan default. Angkanya tidak mendukung mewajibkannya.
- `true_opens_in_zone` adalah satu-satunya yang layak diukur ulang di sel lain,
  karena tandanya konsisten. Itu **bukan** izin memakainya sekarang.

Satu sel, satu instrumen, satu timeframe. Nol di sini bukan nol di mana-mana,
dan itu juga sebabnya tidak ada modul yang dihapus atas dasar tabel ini.

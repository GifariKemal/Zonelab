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

> [!WARNING]
> **Tiga baris di atas satu-satunya di dokumen ini yang sumbernya transkrip,
> bukan file bukti.** Diturunkan jadi tool pada 1 September 2026,
> `tools/orphan_filters.py` ke `docs/orphan_filters.json`, dan dua dari tiganya
> tidak bertahan apa adanya. Lihat Bagian 12.

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

## 9. Replikasi `true_opens_in_zone` lintas 12 instrumen, 28 Agustus 2026

Bagian 8 menutup `true_opens_in_zone` dengan satu kalimat: ia satu-satunya
kolom yang tandanya konsisten, jadi ia layak diukur ulang di sel lain, dan itu
bukan izin memakainya. Bagian ini menjalankan pengukuran ulang itu.

`python -m tools.true_open_matrix --intervals 1h --bars 20000`. Kolom yang
sama, bucket yang sama, ambang yang sama, dan potongan paruh yang sama
(`cut = rows[len(rows)//2]["at"]`, potong WAKTU atas seluruh populasi, persis
seperti `tools/conditioned.py`). Timeframe 1 jam karena praregistrasi Bagian 7
dijalankan di 1 jam; 4 jam adalah dimensi tambahan dan bukan replikasi.

**12 sel terbaca, 47 grup layak dinilai, alpha 0,05/47 = 0,001064, |t| kritis
3,27.** Bonferroni dihitung atas seluruh sel, bukan per instrumen.

| Sel | n | exp R | grup 0 | 1-3 | 4-9 | 10+ | t(0) | paruh(0) | lulus |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| AUDUSD 1h | 609 | -0,077 | n<30 | -0,153 | -0,064 | -0,035 | - | - | - |
| BTCUSD 1h | 540 | -0,022 | +0,009 | +0,002 | -0,042 | -0,035 | +0,22 | +0,105 / -0,458 | tidak |
| EURUSD 1h | 548 | -0,138 | -0,102 | -0,092 | -0,162 | -0,159 | +0,29 | +0,067 / -0,270 | tidak |
| GBPJPY 1h | 530 | -0,109 | -0,112 | -0,188 | -0,079 | -0,069 | -0,02 | -0,057 / -0,203 | tidak |
| GBPUSD 1h | 598 | +0,039 | -0,100 | +0,137 | +0,111 | -0,079 | -0,90 | +0,038 / -0,278 | tidak |
| US30 1h | 495 | -0,038 | -0,106 | -0,041 | +0,054 | -0,217 | -0,45 | -0,315 / +0,165 | tidak |
| USDCAD 1h | 544 | -0,132 | -0,394 | +0,048 | -0,127 | -0,208 | -2,23 | -0,387 / -0,446 | tidak |
| USDJPY 1h | 547 | -0,109 | -0,043 | -0,027 | -0,158 | -0,121 | +0,52 | -0,115 / +0,257 | tidak |
| USOIL 1h | 573 | -0,256 | **-0,594** | -0,192 | -0,267 | -0,232 | **-3,27** | -0,500 / -0,688 | tidak |
| XAGUSD 1h | 510 | +0,023 | +0,040 | +0,082 | -0,044 | -0,000 | +0,16 | +0,183 / -0,071 | tidak |
| **XAUUSD 1h** | 535 | -0,021 | **+0,290** | -0,077 | -0,054 | -0,128 | **+2,35** | +0,027 / +0,545 | tidak |
| XPTUSD 1h | 433 | -0,165 | -0,266 | -0,189 | -0,152 | -0,098 | -0,96 | -0,456 / -0,178 | tidak |

**Nol dari dua belas sel lulus.**

### Kenapa ini menutup pertanyaannya

**Tandanya tidak konsisten lintas instrumen.** Dari sebelas sel yang bisa
dinilai, grup "nol True Open" positif di tiga (XAUUSD +0,290, XAGUSD +0,040,
BTCUSD +0,009, dua terakhir praktis nol) dan negatif di delapan. Sebuah edge
universal akan positif di mana-mana.

**Sinyal terkuat di seluruh matrix justru berlawanan arah.** USOIL pada
t = -3,27, tepat menyentuh ambang dan gagal hanya karena ujinya `>` bukan `>=`.
Kalau ambangnya dilonggarkan sedikit saja, yang lulus adalah kesimpulan yang
BERLAWANAN dengan anomali yang sedang diuji.

**Monotonisitasnya tidak menyeberang.** Di XAUUSD urutannya rapi, +0,290 turun
ke -0,128. Di GBPUSD grup "0" justru yang TERBURUK dari empat. Di US30 yang
terbaik adalah "4-9". Pola yang cuma muncul di satu instrumen dan hilang di
sebelas lainnya adalah bentuk kurva yang dipas, bukan sifat pasar.

**XAUUSD tidak lulus bahkan di rumahnya sendiri**, t = +2,35 lawan kritis 3,27,
angka t yang sama dengan Bagian 7.

### Putusan akhir

Kelima kolom praregistrasi ini sekarang punya angka, dan kelimanya gagal.
`true_opens_in_zone` adalah satu-satunya yang diberi kesempatan kedua, dan ia
memakainya untuk gagal lebih jelas. Tidak ada modul yatim yang disambungkan ke
`tools/execute.py` atas dasar dokumen ini.

Yang TETAP benar dan tidak berubah: `true_open_prices` sekarang dioper ke
`poi.confluence` di jalur order, dan `stack.true_opens` berhenti selalu nol.
Itu perbaikan wiring, bukan promosi sinyal. Sebuah field yang benar boleh ada
tanpa sebuah gerbang yang menyala.

## 10. Replikasi `ote_band` lintas 12 instrumen, 28 Agustus 2026

Bagian 7 mencatat pita OTE di XAUUSD 1 jam terbaca -0,096 R lawan populasi
-0,021 R, dan menutupnya sebagai satu sel. Bagian ini menjalankan kolom yang
sama ke seluruh roster, dengan alasan yang tegas: sebuah usulan untuk MENCABUT
klausa `ote` dari jalur eksekusi datang berdasar angka satu sel itu, dan satu
sel tidak cukup untuk mencabut maupun untuk mempertahankan.

`python -m tools.true_open_matrix --column ote_band --intervals 1h --bars 20000`.
Grup yang diuji adalah `ote`, dipilih dari bunyi klausanya ("proximal wajib
berada di dalam pita OTE") dan bukan dari hasilnya. Menguji `premium` atau
`discount` akan menguji aturan yang tidak pernah dinyatakan siapa pun.

**12 sel, nol gagal, 36 grup layak dinilai, alpha 0,05/36 = 0,001389, |t|
kritis 3,20.**

| Sel | n | exp R populasi | discount | ote | premium | t(ote) | paruh(ote) |
|---|---:|---:|---:|---:|---:|---:|---|
| AUDUSD 1h | 609 | -0,077 | -0,087 | **-0,221** | -0,024 | -1,63 | -0,240 / -0,206 |
| BTCUSD 1h | 541 | -0,024 | -0,060 | **+0,072** | -0,028 | +1,01 | -0,058 / +0,191 |
| EURUSD 1h | 548 | -0,138 | -0,184 | **-0,204** | -0,063 | -0,79 | -0,107 / -0,308 |
| GBPJPY 1h | 530 | -0,109 | -0,009 | **-0,101** | -0,184 | +0,10 | -0,371 / +0,051 |
| GBPUSD 1h | 598 | +0,039 | +0,133 | **-0,133** | +0,018 | **-2,04** | -0,000 / -0,221 |
| US30 1h | 494 | -0,036 | +0,023 | **-0,046** | -0,087 | -0,09 | +0,010 / -0,087 |
| USDCAD 1h | 544 | -0,132 | -0,123 | **-0,192** | -0,127 | -0,73 | -0,206 / -0,179 |
| USDJPY 1h | 547 | -0,109 | -0,104 | **-0,122** | -0,111 | -0,14 | +0,027 / -0,249 |
| USOIL 1h | 573 | -0,256 | -0,309 | **-0,158** | -0,234 | +1,01 | -0,139 / -0,180 |
| XAGUSD 1h | 510 | +0,023 | +0,137 | **+0,113** | -0,103 | +0,76 | +0,181 / +0,038 |
| XAUUSD 1h | 535 | -0,021 | -0,134 | **-0,096** | +0,053 | -0,80 | -0,071 / -0,120 |
| XPTUSD 1h | 433 | -0,165 | -0,129 | **-0,259** | -0,145 | -1,21 | -0,384 / -0,149 |

**Nol dari dua belas lulus.**

### Sebagai edge, terbantah tuntas

|t| tertinggi di seluruh matrix adalah **2,04** pada GBPUSD, lawan kritis 3,20.
Tidak ada satu sel pun yang mendekati, dan tidak ada kelas aset yang
menyelamatkannya: FX, logam, indeks, energi, dan kripto semuanya di bawah
ambang. Aturan "proximal wajib di dalam pita OTE" tidak punya dukungan angka di
venue ini.

### Sebagai racun, TIDAK terbukti

Ini bagian yang harus dibaca sebelum ada yang mencabut klausanya. Arahnya memang
condong negatif, `ote` negatif di **10 dari 12** sel dan lebih buruk daripada
populasinya sendiri di **8 dari 12**. Tapi condongan yang tidak melewati ambang
di satu sel pun bukan bukti kerugian; ia bukti ketiadaan sinyal. Empat sel
justru lebih baik daripada populasinya: BTCUSD +0,096, USOIL +0,098, XAGUSD
+0,090, GBPJPY +0,008.

### Angka -0,096 di emas tidak istimewa

Ia bahkan bukan yang terburuk. XPTUSD -0,259, AUDUSD -0,221, dan EURUSD -0,204
lebih buruk, sementara XAGUSD +0,113 berlawanan arah. Sel yang dipakai sebagai
dasar usulan pencabutan ternyata sel biasa.

### Putusan

Klausa `ote` TETAP ADA dan TETAP tidak diwajibkan, yaitu persis tempatnya
sekarang: `Rules.required` default kosong sehingga ia melaporkan tanpa
memblokir. Menghapusnya akan menghapus bukti bahwa ia pernah diukur, dan
menutup kemungkinan mengukurnya lagi di venue yang punya data berbeda.

Yang berubah bukan kode melainkan apa yang boleh dikatakan tentangnya. Dulu:
satu sel negatif. Sekarang: dua belas sel, nol sinyal, |t| tertinggi 2,04.
`app/ict.py:MEASURED_AGAINST` diperbarui dengan angka dua belas sel itu.

Batas yang tetap berlaku dari Bagian 7: hanya baris `ote` yang arah-sadar
(demand 0,214-0,382, supply 0,618-0,786). Baris `discount` dan `premium` adalah
posisi mentah dan mencampur kedua sisi, jadi tidak boleh dibaca sebagai
"premium bagus". Baris `equilibrium` dan `none` di bawah 30 anggota di seluruh
dua belas sel.


## 11. `app/olhc.py`, praregistrasi keempat, 1 September 2026

Modul ini tidak ada di Bagian 1. Audit 28 Agustus menemukan enam modul yatim dan
`olhc` bukan salah satunya, jadi ia tidak punya kolom di `tools/conditioned.py`,
tidak punya file bukti, dan cuma punya satu unit test. Praregistrasi ini ditulis
di docstring `tools/olhc_outcomes.py` sebelum satu angka dihitung; ringkasannya
di sini supaya register modul yatim tetap satu tempat.

### Yang ditanyakan, dan yang ditarik kembali

Dua hipotesis ditulis: apakah bentuk penolakan lilin menyatakan ekstrem mana
yang lebih dulu dikunjungi (H_ORDER, diuji lawan bar 5 menit di dalam jamnya),
dan apakah arah yang diklaimnya mengalahkan drift instrumennya sendiri
(H_DIRECTION).

**H_ORDER ditarik, dan alasannya aljabar bukan data.** Pada bar dengan range R:

    lower_wick / R = min(open_pos, close_pos)
    upper_wick / R = 1 - max(open_pos, close_pos)

sehingga seluruh aturannya runtuh jadi

    accumulation  <=>  close_pos >= 0,5  dan  min(o, c) > 1 - max(o, c)

`classify()` adalah **pelabelan ulang** pasangan (posisi open, posisi close) dan
tidak membawa apa pun di luar itu. Diverifikasi dua cara: aljabar di atas, dan
20.000 bar acak di `--selfcheck` yang menuntut `classify` sama persis dengan
bentuk tertutup itu. Gerbangnya dibuktikan menggigit: mengubah ambang wick di
`app/olhc.py` menjadi `lower_wick > upper_wick * 1.5` membuatnya gagal.

Konsekuensinya fatal buat pertanyaannya. Kontrol yang benar harus menahan posisi
open DAN close sekaligus, dan di dalam stratum seperti itu setiap bar punya
kelas yang sama menurut konstruksi. Tidak ada versi H_ORDER yang menahan
confound-nya dan masih punya dua lengan.

Dua angka urutan tetap dihitung dan dilaporkan, tidak satu pun dinilai:

| Perbandingan | accumulation | distribution | Yang sebenarnya diukur |
|---|---|---|---|
| tanpa kontrol | +0,295 | +0,309 | posisi close, yang sudah ada di aturannya |
| stratifikasi close saja | -0,257 (z=-93,6) | -0,254 (z=-87,1) | posisi open, yang juga sudah ada di aturannya |

z sebesar -93 pada klaim perilaku adalah bentuk sebuah identitas, bukan sebuah
edge. Ia dibiarkan di output pada ukuran itu supaya pembaca berikutnya melihat
kenapa.

### Hasil H_DIRECTION, yang aljabarnya tidak menyelesaikan

`PYTHONPATH=. python -m tools.olhc_outcomes`, sembilan instrumen, 1h, horizon 96
bar, SE di-cluster pada (simbol, blok window), |t| kritis 2,24 untuk K=2:

| Kelas | n | mean excess (ATR) | t | n efektif | Putusan |
|---|---:|---:|---:|---:|---|
| accumulation | 59.035 | +0,0439 | +0,294 | 2.711 | GAGAL |
| distribution | 51.367 | +0,0007 | +0,005 | 2.781 | GAGAL |

`distribution` praktis nol persis: +0,0007 ATR di 51 ribu event.

### Putusan

`app/olhc.py` tetap yatim, sekarang dengan dua alasan berangka. Ia tidak membawa
informasi di luar posisi open dan close, dan arah yang diklaimnya tidak
mengalahkan drift. Bukti: `docs/olhc_outcomes.json`.

### Sisa daftar, diperiksa ulang 1 September 2026

| Modul | Keadaan |
|---|---|
| `app/judas.py` | terukur 28 Agu, `judas_template` \|t\| tertinggi 0,23 |
| `app/m4.py` | terukur 28 Agu lewat `in_judas_window`, t=0,27 |
| `app/psp.py` | terukur 28 Agu (t=0,09) dan diukur ulang 1 Sep, 48 sel nol, `docs/psp_outcomes.json`. Sekarang DIGAMBAR sebagai bacaan dan dipagari test |
| `app/tcisd.py`, `app/zscore.py`, `app/regime.py` | terjawab sebelum Bagian 3, lihat Bagian 5 |
| `app/ladder.py` | tidak dapat diuji sebagai sinyal, dan membaca `for_cycle` mengonfirmasinya: ia menerima nama cycle plus satu boolean dan mengembalikan label rute, nol input pasar |
| `app/olhc.py` | terukur di bagian ini |

> [!NOTE]
> Provenance yang lebih lemah, dan disebut supaya tidak terlupakan: angka tCISD,
> z-score dan regime di Bagian 5 berasal dari transkrip sesi, bukan dari file
> bukti yang bisa dijalankan ulang. Ketiganya tidak punya tool di `backend/tools/`
> yang menghasilkannya. Itu di bawah standar yang dipakai setiap baris lain di
> dokumen ini.


## 12. Menurunkan Bagian 5 jadi tool, 1 September 2026

`tools/orphan_filters.py` menjalankan tiga lengan lewat `tools.quant.cell` apa
adanya, tanpa mengimplementasi ulang satu filter pun: `baseline` (trade zona
tanpa filter), `tcisd` (`cell(..., tcistd=True)`), dan `quant`
(`cell(..., quant=True)`, yaitu Z-Score plus volume plus regime). 12 instrumen
kali dua timeframe, 24 sel, 20.000 bar, bukti di `docs/orphan_filters.json`.

Ini bukan praregistrasi baru. Hipotesisnya sudah dinyatakan dan dijawab di
tempat lain; yang dikerjakan di sini reproduksi dari kode yang di-commit. Angka
yang kembali BERBEDA adalah temuannya.

### Hasil gabungan

| Lengan | Sel | exp R rata-rata | Rentang per sel | Sel positif | Kalahkan baseline sendiri |
|---|---:|---:|---|---:|---|
| baseline | 24 | **-0,087363** | | 3 | |
| tcisd | 12 | -0,083539 | -0,2563 sampai +0,0385 | 2 | 0 dari 12 |
| quant | 24 | -0,115693 | -0,3510 sampai +0,1269 | 1 | 10 dari 24 |

### Baris 2 direproduksi persis, dan penjelasannya membatalkannya sebagai bukti

`-0,087 R, identik baseline` cocok sampai tiga desimal dengan **exp R rata-rata
baseline, -0,087363**. Baris itu tidak pernah mengukur tCISD; ia mengukur
baseline dan memberinya nama tCISD.

Sebabnya sekarang terlihat di log per sel, dan lebih keras daripada "identik":

| Mode tCISD | Sel | Akibat |
|---|---:|---|
| konfirmasi DUA arah | 12 (semua 1h) | tanpa pembatasan arah, SETIAP trade lolos |
| nol konfirmasi | 12 (semua 4h) | nol trade, sel-nya kosong |

**Tidak satu pun dari 24 sel menghasilkan filter satu arah.** Sebagai filter,
tCISD di data ini biner: lolos-semua atau blokir-semua, tidak pernah memilih.
Itu bukan "filter yang tidak menambah edge", itu filter yang tidak pernah
menyaring.

### Baris 1 tidak bisa direproduksi sama sekali

`-0,926 R, 0 dari 11 positif` disebut hasil "tCISD sebagai entry mandiri", dan
tidak ada jalur kode di repo ini yang mengimplementasi itu. `tcisd_trades`
menyatakan sendiri di docstring-nya: "tCISD is a FILTER, not a replacement for
the zone entry." Mode `--tcistd` hari ini berarti filter. Angka -0,926 tidak
punya perintah yang menghasilkannya, jadi ia tidak bisa dipakai membenarkan apa
pun.

### Baris 3 arahnya bertahan, rentangnya tidak

Rata-rata `quant` -0,1157 jatuh di dalam pita -0,0893 sampai -0,1301 yang
diklaim, jadi arah kesimpulannya bertahan: menambahkan Z-Score, volume dan
regime membuat ekspektansi lebih buruk, bukan lebih baik, dan memangkas n
besar-besaran (534 jadi 81 di XAUUSD 1h). Tapi rentang per sel yang sebenarnya
**-0,3510 sampai +0,1269**, hampir tiga kali lebih lebar daripada yang ditulis,
dan filter itu justru mengalahkan baseline-nya sendiri di 10 dari 24 sel. Pita
sempit di Bagian 5 bukan rentang per sel apa pun yang bisa direproduksi di sini.

### Putusan

Ketiga modul tetap yatim, dan sekarang dengan alasan yang bisa dijalankan ulang.
Yang berubah adalah apa yang boleh dikatakan: satu baris adalah baseline yang
salah label, satu baris tidak punya kode, dan satu baris arahnya benar dengan
rentang yang salah. Bagian 5 dipertahankan apa adanya di atas, dengan peringatan
yang menunjuk ke sini, karena menghapusnya akan menghapus bukti bahwa ia pernah
dikutip.


## OTE jadi DETEKTOR, 8 September 2026, dan itu mengukur definisi yang lain

Bagian 7 dan 10 di atas menguji pita OTE **dealing range** sebagai SARINGAN atas
sentuhan pertama zona supply/demand, dan hasilnya nol dari dua belas. Yang
dibangun hari ini objek yang berbeda: sebuah **kotak** dari pita OTE, dengan
lifecycle, gerbang dan bracket sendiri, di atas **swing struktur** - definisi
yang selama ini DIGAMBAR di chart lewat `fibonacci-primitive.ts` dan belum
pernah diukur sama sekali.

Kedua definisi tidak setuju, dan `tools/brief/live.py` sudah mencatatnya:
29 Agustus 2026 pada bar yang sama, grid memberi retracement 0,376 sementara
klausa menjawab "no dealing range, no OTE reading". Detektor ini memilih yang
digambar - bukan karena lebih benar, melainkan karena ia yang belum punya angka.

### Geometri dan gerbang

Leg dari dua anchor confirmed terakhir. Anchor high lebih baru berarti leg NAIK,
retracement turun ke pita, kotaknya DEMAND; sebaliknya SUPPLY. Pitanya 0,618
sampai 0,786, dan tepi yang harga temui lebih dulu adalah yang DANGKAL - jadi
0,618 proximal, 0,786 distal, stop di luar distal seperti lima detektor lain.
Kedua rasio diambil dari `fibonacci-primitive.ts:LEVELS` supaya kotak dan grid
tidak bisa hanyut.

Gerbangnya **lantai 2,0 ATR pada panjang leg**, dan itu pilihan yang dinyatakan:
doktrin OTE tidak membawa gerbang sama sekali - ia aturan tempat masuk, bukan
aturan seleksi. `FLOOR_GATE_ATR` memaksa tiap kind baru menyatakan lantainya,
jadi OTE juga masuk `GATE_UNMEASURED_KINDS`.

### Hasil, dan regresi dijalankan lebih dulu

Detektor 0 direproduksi sebelum angka OTE dipercaya: **n=598, PF 1,113, cand
1.479, gate 610** - identik digit demi digit.

| sel | n | win% | PF | placebo | margin |
|---|---|---|---|---|---|
| FX:XAUUSD 1d | 685 | 43,50 | **1,066** | 0,958 | +0,108 |
| COMEX:GC1! 1d | 622 | 39,55 | **0,876** | - | - |

> [!WARNING]
> **Baris COMEX di atas DIUKUR ULANG DUA KALI 8 September 2026, dan bacaan
> keduanya yang berlaku: PF 1,152 pada n=679.** Bacaan pertama menyatakan ia
> tidak terpengaruh (0,876 identik) dan itu benar hanya untuk sumbu yang
> diuji saat itu - pembulatan kuantitas. Cacat kedua di fungsi sizing yang
> sama adalah plafon MODAL: pada pointvalue 100 satu trade bisa meminta
> notional sebesar seluruh ekuitas dan order berikutnya dipotong. Sesudah
> `initial_capital` dinaikkan, angkanya naik dari 0,876 ke 1,152. Ditemukan 8 September 2026: `qsize` meminta kurang dari satu
> kontrak untuk setiap stop yang lebih lebar dari 10 dolar di instrumen
> ber-pointvalue 100, TradingView membulatkannya ke bawah, dan order itu tidak
> pernah jadi posisi - sementara penghitung `fill` tetap menghitungnya. Terukur
> dengan detektor FVG di sel yang sama: populasi 132 dari 537 memberi PF 1,167,
> populasi utuh 496 dari 537 memberi 0,923. Cacatnya diperbaiki di `qsize`
> (`risk_eff`), dan OTE dijalankan ulang di atas perbaikan itu - hasilnya
> tidak bergerak, jadi stop OTE di sel ini memang sudah cukup rapat untuk
> memberi lebih dari satu kontrak. Lihat `docs/QA-SD-GATE.md` bagian terakhir
> dan `docs/CALIBRATION.md`.


Peringkat di XAU harian, enam detektor lewat bracket identik: supply_demand
1,235, breaker 1,181, fvg 1,112, ifvg 1,067, **ote 1,066**, order_block 0,972.
Praktis kembar dengan IFVG, kelima dari enam.

### Kontrolnya BERSIH, dan itu sifat yang SD maupun IFVG tidak punya

`gate` **identik 679 di kedua lengan**. Gerbang OTE ada pada PANJANG LEG, dan
leg tidak ikut bergeser saat kotaknya digeser, jadi lengan placebo memakai
peristiwa yang persis sama dengan kotak di tempat yang salah - definisi placebo
yang sebenarnya. Bandingkan S&D, yang gerbangnya diukur DARI proximal sehingga
geseran memindahkan `gate` dari 331 ke 463, dan IFVG yang punya masalah sama.
Margin +0,108 PF karena itu lebih bisa dibaca daripada margin lebih besar milik
keduanya.

### Dua cacat harness ditemukan saat membangunnya

**`inverting = detector >= 2` menangkap terlalu banyak.** Benar selama detektor
tertinggi 3; begitu SD (4) dan OTE (5) masuk, keduanya ikut terbaca sebagai mode
inversi. Diperiksa sebelum diperbaiki: TIDAK ada angka yang salah karenanya,
sebab `v_top` hanya diisi di blok bersama dan `ok` sudah false untuk SD. Bahaya
laten, bukan hasil tercemar. Sekarang `detector == 2 or detector == 3`.

**Gerbang OTE sempat di dalam `e_ok`**, jadi `c_cand` hanya naik untuk zona yang
sudah lolos dan tabel membaca cand 679 gate 679 - kolom kandidat berhenti
sebanding dengan lima detektor lain. Dipindah ke `gatePass`: cand 768 gate 679,
trade praktis tak berubah (n 686 jadi 685).

> [!WARNING]
> Paste ke editor Pine GAGAL DIAM-DIAM satu kali di sesi ini, dan
> `pine_smart_compile` melaporkan sukses karena ia menyimpan isi LAMA. Yang
> menutupinya: regresi detektor 0 tetap lolos, karena detektor 0 tidak tersentuh
> perubahan OTE. Sebabnya fokus ada di BODY, bukan textarea Monaco, sehingga
> Ctrl+A/Ctrl+V tidak mendarat. Obatnya: fokuskan
> `document.querySelector('.monaco-editor textarea')` lewat `ui_evaluate` lebih
> dulu, lalu VERIFIKASI lewat baris `cfg` - label detektor yang benar adalah
> bukti paste-nya masuk, dan regresi saja BUKAN.

### Parity lawan Pine publik: konvensinya SAMA, anchor-nya TIDAK

Pembanding: `Optimal Trade Entry (OTE) Zone Plotter [algotim]`, 50 kotak di
FX:XAUUSD harian, 6 di antaranya jatuh di rentang harga jendela candle yang bisa
ditarik. Metode sama dengan parity FVG: kode PRODUKSI dijalankan di atas candle
dari chart yang menggambar kotak mereka, jadi tak ada selisih feed.

**Cocok persis: 0 dari 6.** Tapi itu bukan akhir ceritanya, dan menyebutnya
"parity gagal" akan salah. Dua uji lanjutan:

**Sapuan `swing_n` 2 sampai 30: nol cocok di setiap nilai.** Jadi selisihnya
bukan panjang pivot yang bisa disetel.

**Rasio tersiratnya dipecahkan balik dari ekstrem NYATA di data**, dan hasilnya
mengelompok ketat:

| kotak algotim | H | L | r1 | r2 | r2-r1 |
|---|---|---|---|---|---|
| 5060,61 / 4962,34 | 5418,87 | 4840,95 | 0,6199 | 0,7900 | 0,1700 |
| 4475,24 / 4378,02 | 4833,46 | 4257,24 | 0,6217 | 0,7904 | 0,1687 |
| 3718,05 / 3536,14 | 4382,48 | 3306,91 | 0,6177 | 0,7869 | 0,1691 |
| 3369,00 / 3315,51 | 3563,98 | 3246,37 | 0,6139 | 0,7823 | 0,1684 |
| 3341,96 / 3315,39 | 3438,84 | 3281,54 | 0,6159 | 0,7848 | 0,1689 |

r1 0,614-0,622 dan r2 0,782-0,790 - **itu 0,618 dan 0,786.** Konvensi pitanya
identik dengan kita. Yang berbeda MURNI pasangan anchor mana yang dipilih untuk
menggambar leg-nya.

Dan itu instans KETIGA dari masalah yang sama di halaman ini: matematika pitanya
universal, LEG-nya tidak. Dua definisi OTE internal repo ini berselisih karena
alasan yang sama (swing struktur lawan dealing range), dan sekarang script pihak
ketiga berselisih dengan keduanya karena alasan yang sama lagi.

### Tuning: lantainya bisa disetel, tapi TIDAK memperbaiki apa pun

Sapuan lantai panjang leg di XAU harian naik monoton - pola yang persis pernah
menipu di lantai BRK:

| lantai | n | PF |
|---|---|---|
| 0 (mati) | 793 | 1,038 |
| **2,0 (di-ship)** | 685 | 1,066 |
| 3,0 | 447 | 1,099 |
| 4,0 | 278 | **1,205** |

Hold-out dijalankan SEBELUM menyebutnya perbaikan, jendela dibelah di 2013:

| lengan | IS 2000-2013 | OOS 2013-2026 |
|---|---|---|
| lantai 2,0 | **0,848** | **1,180** |
| lantai 4,0 | **1,191** | **1,162** |

Lantai 4,0 memang akan TERPILIH di paruh pertama - 1,191 lawan 0,848 - dan ia
bertahan di luar sampel, tidak runtuh seperti lantai 4,0 milik BRK yang jatuh ke
0,861. Tapi **ia tidak mengalahkan lantai yang sudah di-ship**: 1,162 lawan
1,180, dengan separuh jumlah trade. **Tidak ada perubahan yang direkomendasikan.**

Catatan yang harus dibaca bersamanya: lantai 2,0 sendiri IS 0,848 dan OOS 1,180,
jadi PF jendela-penuh 1,066 miliknya adalah fenomena paruh kedua - bentuk yang
sama dengan BRK harian.

### Autodrawing: 7 dari 7, dan satu cacat yang dedupe paksa keluar

`e2e/pixel-truth.mjs` pada `ote`, XAUUSD harian: **7 dari 7 lolos**, tepi atas
0,5px, tepi bawah 0,4px, tepi kiri 10 dari 10, kotak menutupi basisnya sampai
0,03 bar.

Tapi audit visual menemukan zona OTE saling menumpuk berat: "they render as a
single banded region crossed by four solid rules". Sebabnya geometri detektor
ini - **pasangan anchor berurutan berbagi satu anchor**, jadi pita berikutnya
hampir selalu memotong pita sebelumnya. Empat detektor imbalance tidak punya
masalah ini karena kotaknya dibuat dari lilin yang berbeda.

Obatnya memakai ulang `_dedupe` milik supply_demand, bukan menulis versi kedua:
`merge_overlap_pct` 0,6 membuang **105 dari 197** zona di XAU harian.

**Dan dedupe memaksa keluar cacat yang saya buat sendiri.** `_finish` menyusun
id dari kind plus bar ORIGIN, unik untuk lima detektor lain. Untuk OTE TIDAK:
dua pita berbeda bisa berbagi origin, jadi id-nya sama. Sebelum dedupe hal itu
tak terlihat - `{z.id: z}` diam-diam menyimpan yang terakhir. Begitu dedupe
masuk, yang bertahan bergantung populasi, dan `test_no_repaint` langsung merah:
"grew right: OTE-1774544400". React di frontend menandai hal yang sama secara
independen ("two children with the same key"). Id sekarang membawa KEDUA anchor.

### Dua penggambaran di layar yang sama, dan kenapa itu TIDAK perlu diperbaiki

Pita OTE sekarang tampil dua kali kalau layer `structure` dan `ote` sama-sama
menyala: sebagai grid sembilan level dari `fibonacci-primitive.ts`, dan sebagai
kotak dari layer baru.

Diperiksa sebelum menyarankan perubahan: grid memakai ink family `levels`,
**biru-abu [137, 183, 207]**, sementara zona memakai hijau `#1f8f5f` dan merah
`#ef8f86`. Keduanya sudah terbedakan warna, dan mereka memang dua objek berbeda
- grid adalah level acuan netral di atas leg SEKARANG tanpa klaim arah, kotak
adalah zona berwarna dengan lifecycle, gerbang dan status. **Tidak ada perubahan
kode yang disarankan**; yang dibutuhkan legenda yang menyebutkannya, bukan aturan
supresi yang akan menyembunyikan informasi yang berbeda.

### Grid enam detektor lengkap, dan stress test OTE

Dua sel yang hilang diisi supaya baris OTE sebanding, lalu saringan delapan
periode dikenakan seperti ke lima lainnya.

| detektor | XAU 1d | XAU 4h | BTC 1d (2017+) | periode lolos |
|---|---|---|---|---|
| supply_demand | **1,235** | **1,043** | 0,744 | 5 dari 8 |
| breaker | **1,181** | 0,958 | 0,931 | 3 dari 8 |
| fvg | **1,112** | **1,091** | 0,737 | 6 dari 8 (di 4 jam) |
| ifvg | **1,067** | 0,965 | 0,844 | 6 dari 8 |
| **ote** | **1,066** | 0,960 | 0,881 | **4 dari 8** |
| order_block | 0,972 | 0,926 | 0,907 | 5 dari 8 |

Delapan periode OTE di XAUUSD harian, batas identik dengan lima lainnya:

| periode | n | win% | PF |
|---|---|---|---|
| 2000-2003 | 86 | 46,51 | 0,981 |
| 2003-2006 | 69 | 36,23 | 0,842 |
| 2006-2010 | 93 | 44,09 | **1,168** |
| 2010-2013 | 77 | 42,86 | 0,650 |
| 2013-2016 | 85 | 44,71 | **1,508** |
| 2016-2020 | 103 | 51,46 | 0,980 |
| 2020-2023 | 87 | 37,93 | **1,073** |
| **2023-2026** | 60 | 45,00 | **1,135** |
| **lolos** | | | **4 dari 8** |

Periode sekarang 1,135, di atas satu dan ketiga terbaik dari delapan - jadi OTE
tidak punya bentuk peluruhan yang dipunyai IFVG (2023-2026 terburuk) maupun BRK
(kedua terburuk). Tapi 4 dari 8 menempatkannya kelima dari enam, sejajar dengan
peringkat PF-nya, dan jauh dari 8 dari 8 yang menggerbangi `orderable`.

n per periode 60 sampai 103, jadi yang ditopang HITUNGAN lolos-gagalnya, bukan
presisi tiap sel.

### Lubang UI yang ter-ship, ditutup

`toolbox.tsx` memakai `switch` yang di-hardcode per blok params, dan tidak ada
`case "ote"` - layernya bisa dinyalakan tapi keempat knob-nya tidak terjangkau.
`e2e/wiring.mjs` menangkapnya begitu dijalankan: **82 dari 85**, dengan `ote=0`
objek tergambar, tanpa swatch tinta, dan tanpa baris pemilik.

Tiga yang kurang: panel knob di `toolbox.tsx`, swatch di `layerSwatch()`, dan
ikon di `icons.tsx`. Ditambah entri `DRAWS` dan `OWNERS` di harness-nya sendiri.
Sesudahnya **86 dari 86** dan `ote=10` objek tergambar.

Ikonnya sengaja BUKAN kotak polos: lima detektor lain sudah memakai kotak, dan
yang membedakan OTE bukan bentuk kotaknya melainkan bahwa ia diukur dari sebuah
LEG - jadi ikonnya leg naik dengan dua garis pita.

### Legenda dua penggambaran, ditulis

`e2e/chart-audit.mjs` sekarang menyatakan bahwa grid Fibonacci biru-abu dan
kotak OTE hijau/merah adalah dua objek berbeda yang keduanya benar, dan bahwa
auditor tidak boleh melaporkannya sebagai duplikat. Itu satu-satunya perubahan
yang diambil untuk isu tersebut; tidak ada aturan supresi, karena keduanya sudah
terbedakan warna.

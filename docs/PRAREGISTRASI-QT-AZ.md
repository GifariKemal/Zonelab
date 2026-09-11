# Praregistrasi empat adopsi Quarterly Theory A-Z, 11 September 2026

Dokumen ini ditulis **sebelum** satu angka pun dihitung, dan sebelum satu pun
dari empat objek di bawah punya gerbang, skor, atau bobot di mana pun. Keempatnya
sudah TERPASANG dan bisa digambar; tidak satu pun sudah diukur.

Sumbernya `quarterly-theory-a-z-guide-v1-1.pdf` (Oracle Insights, by Bucko),
dibedah di `docs/ADOPSI.md` bagian "Referensi Quarterly Theory ketiga".

> [!CAUTION]
> **Prior-nya bukan keyakinan dokumen itu.** Dua tetangga dari doktrin yang sama
> sudah diukur di repo ini dan keduanya null: `ssmt` nol dari 24 sel
> (`docs/ssmt_outcomes.json`) dan `psp` nol dari 48 sel
> (`docs/psp_outcomes.json`). Dokumen sumbernya menyebut SSMT "the base of every
> setup" dan tidak membawa satu pun angka di 80 halaman. Empat studi di bawah
> berangkat dari prior itu, bukan dari prosanya.

## Daftar isi

- [Yang sudah terpasang](#yang-sudah-terpasang)
- [S1 QT Killzone](#s1-qt-killzone)
- [S2 Premium discount berbasis waktu](#s2-premium-discount-berbasis-waktu)
- [S3 Hidden SSMT](#s3-hidden-ssmt)
- [S4 SMT Fill](#s4-smt-fill)
- [Hasil S1 dan S2](#hasil-s1-dan-s2-diukur-11-september-2026)
- [Aturan yang berlaku untuk keempatnya](#aturan-yang-berlaku-untuk-keempatnya)

## Yang sudah terpasang

| Studi | Objek | Kode | Saklar | Terukur |
|---|---|---|---|---|
| S1 | QT Killzone | `app/sequence.py:killzones` | `session.killzones` | **null**, lihat hasil |
| S2 | Premium/discount waktu | `app/quarterly.py:time_premium_discount` | `session.premium_discount` | **sebagian**, lihat hasil |
| S3 | Hidden SSMT | `app/ssmt.py:ssmt(basis="body")` | `checklist.ssmt_hidden` | belum |
| S4 | SMT Fill | `app/smt_fill.py` | layer `smt_fill` | belum |

Keempatnya mati secara default. Tidak ada yang masuk `plan.py`, `advisor.py`,
`checklist.py`, atau jalur order mana pun.

## S1 QT Killzone

**Klaimnya.** Jendela di mana dua cycle atau lebih berada di kuarter bernomor
sama menghasilkan gerakan yang lebih bersih dan lebih terarah.

**Kenapa ia bisa diukur murah.** Jendelanya adalah fakta jam: ia ada sebelum
outcome apa pun, jadi tidak mungkin dipilih setelah melihat hasilnya.

> [!WARNING]
> **Tingkat dasarnya besar dan HARUS jadi pembanding.** Dua degree sepakat pada
> satu dari empat kuarter BY CONSTRUCTION, tiga pada satu dari enam belas.
> Sudah dikunci di `sequence._selftest_killzones` sebagai asersi (0,25 dan
> 0,0625), jadi angka mana pun yang tidak dibandingkan dengannya tidak berarti.

**Populasi.** Identik dengan `PRAREGISTRASI-KONDISI.md` bagian 2: populasi
gate-clearing yang sama, entry, stop, target, exit, dan biaya yang sama. Tidak
ada yang berubah kecuali satu kolom pengkondisi.

**Kolomnya, daftar tertutup, dua:**

1. `kz_depth` - berapa degree yang sepakat pada bar sentuhan, 0 kalau tidak ada.
   Dihitung dari `chain(at, degrees)` pada bar itu saja.
2. `kz_number` - nomor kuarter yang disepakati, null kalau `kz_depth` nol.

Degree yang dipakai `("day", "session")` dan `("day", "session", "micro")`, dua
set, tidak lebih. Menambah set ketiga sesudah melihat hasil adalah pencarian.

**Lulus kalau:** split median atas `kz_depth >= 2` memisahkan exp_r dengan
|t| di atas ambang Bonferroni untuk jumlah sel yang dijalankan, DAN walk-forward
minimal 6 dari 8 fold sepakat tanda, DAN efeknya bertahan setelah dibandingkan
dengan kontrol jendela-acak berdurasi sama (lihat aturan bersama di bawah).

## S2 Premium discount berbasis waktu

**Klaimnya.** Posisi harga di dalam range kuarter PARENT sebelumnya memisahkan
hasil, dan memisahkannya lebih baik daripada dealing range berbasis swing.

**Kenapa ia menarik dan bukan sekadar kolom kelima puluh.** Ia **tanpa
parameter**. `dealing_range.py` membawa `swing_n` dan karena itu bisa disetel
sampai sepakat dengan outcome; yang ini aritmetika jam dan tidak bisa. Studi ini
adalah satu-satunya di halaman ini yang membandingkan dua pembacaan yang sudah
ada, bukan menambah satu.

**Kolomnya, dua:**

1. `tpd_pos` - posisi harga sentuhan di band `time_premium_discount` yang berlaku
   pada bar itu, 0 di low sampai 1 di high, null kalau tidak ada band.
2. `tpd_outside` - -1 di bawah band, +1 di atas, 0 di dalam. Sumbernya menyebut
   di luar band sebagai "extreme premium/discount", jadi ia state tersendiri dan
   bukan pembulatan dari kolom pertama.

**Perbandingan berpasangannya WAJIB, dan itu yang membedakan studi ini dari S1.**
Untuk setiap event, `tpd_pos` dan `range_pos` (dealing range) dihitung
bersebelahan. Yang dilaporkan bukan cuma apakah masing-masing memisahkan, tapi
delta berpasangan cycle demi cycle antara keduanya - bentuk yang sama dengan
tabel "penyempurnaan fase" di `docs/ADOPSI.md`, yang menjawab pertanyaan "mana
yang lebih baik" alih-alih dua pertanyaan terpisah.

**Lulus kalau:** sama dengan S1, DAN deltanya lawan `range_pos` positif dan
menyeberang ambang. Kalau ia memisahkan tapi kalah dari `range_pos`, hasilnya
"tidak diadopsi sebagai pengganti" dan itu tetap jawaban.

## S3 Hidden SSMT

**Klaimnya.** Ketika tidak ada divergensi wick, divergensi body sering ada, dan
ia lebih lemah "because no liquidity is technically being swept".

**Ini satu-satunya klaim di dokumen itu yang menyebut ARAH perbedaan**, jadi ia
satu-satunya yang bisa salah dengan cara yang menarik.

**Populasi.** `docs/ssmt_outcomes.json` dijalankan ulang persis, dengan satu
lengan tambahan. Tidak ada instrumen, degree, bracket, atau sisi yang berubah -
mengubahnya berarti hasil lama tidak lagi jadi pembanding.

**Tiga lengan:**

| Lengan | Populasi |
|---|---|
| `wick` | apa adanya hari ini, sebagai jangkar |
| `body` | hanya divergensi basis body |
| `body_only` | divergensi body pada kuarter yang TIDAK punya divergensi wick |

Lengan ketiga yang menjawab klaim sumbernya secara harfiah: "kalau tidak terlihat
SSMT biasa, langsung cek yang tersembunyi".

**Lulus kalau:** `body` memisahkan dengan aturan yang sama dengan S1. **Dan
sebuah hasil kedua yang tetap berharga meski nol**: apakah `body` lebih buruk
daripada `wick` pada populasi yang sama, karena itu klaim sumbernya dan belum
pernah ada yang mengukurnya.

> [!NOTE]
> `wick` sudah null. Jadi lulusnya `body` akan menjadi hasil yang aneh dan harus
> diperlakukan seperti itu: lengan yang lebih lemah menurut sumbernya sendiri
> mengalahkan lengan yang lebih kuat. Kalau itu terjadi, kontrol placebo dan
> walk-forward dijalankan dua kali lipat sebelum ditulis sebagai temuan.

## S4 SMT Fill

**Klaimnya.** Gap yang dipertahankan satu instrumen sementara yang lain mengisi
adalah gap yang akan ditolak harga.

**Outcome-nya harus didefinisikan di sini, sebelum dilihat**, karena objek ini
tidak punya tetangga di repo yang bisa meminjamkan definisinya:

- **Event**: bar `knowable_at` dari sebuah `FillEvent`.
- **Sisi**: gap bullish menghasilkan hipotesis LONG pada instrumen yang
  MENAHAN (`held`), bearish menghasilkan SHORT. Ini bacaan sumbernya dan
  ditulis di sini supaya tidak bisa dibalik nanti.
- **Entry**: close bar `knowable_at`.
- **Stop**: sisi jauh gap instrumen itu.
- **Target**: 2R, bracket yang sama dengan studi detektor lain.
- **Outcome**: mana yang tersentuh lebih dulu, dengan urutan intrabar yang sama
  dengan rig yang ada.

**Sel:** tiga varian (`entered`, `half`, `full`) x dua sisi = 6 sel per pasangan,
dua pasangan (XAU/XAG dan BTC/ETH), jadi 12 sel. Bonferroni atas 12.

**Kontrol WAJIB, dan bukan cuma placebo geser harga:** lengan pembanding adalah
gap simultan yang **tidak** menghasilkan divergensi - keduanya mengisi atau
keduanya tidak. Itu kontrol yang menjawab "apakah divergensinya yang penting,
atau cuma fakta bahwa ada gap simultan". Tanpa lengan itu studi ini mengukur
gap, bukan SMT fill.

## Hasil S1 dan S2, diukur 11 September 2026

Dijalankan lewat `tools/conditioned.py`, rig pengkondisian yang sudah ada,
dengan empat kolom di atas didaftarkan sebagai `QTAZ_COLUMNS` - daftar
praregistrasi KEEMPAT di file itu, terpisah dari tiga daftar sebelumnya supaya
terlihat pertanyaan mana yang diajukan sebelum jawabannya ada.

**Populasi:** `mt5:XAUUSD` 1h, 50.000 bar, exit flat di rollover.
**n = 1.045, exp R populasi -0,121.**
**121 grup layak dinilai, alpha 0,05/121, sehingga |t| kritis = 3,53.**

### S1 QT Killzone: null, dan condong NEGATIF

| Kolom | Nilai | n | exp R | delta | t | Paruh |
|---|---|---|---|---|---|---|
| `kz_depth` | selaras (2 degree) | 324 | -0,184 | **-0,092** | **-1,42** | -0,116 / -0,068 |
| `kz_depth` | tidak selaras | 721 | -0,092 | +0,092 | +1,42 | +0,116 / +0,068 |
| `kz_number` | Q3, "Q3 of Q3" | 235 | -0,190 | -0,089 | -1,24 | -0,172 / +0,004 |
| `kz_number` | Q1 | 56 | -0,172 | -0,054 | -0,41 | +0,053 / -0,144 |
| `kz_number` | Q2 | 33 | -0,164 | -0,044 | -0,29 | +0,163 / -0,192 |

**Gagal.** |t| terbesar 1,42 lawan ambang 3,53.

Dua hal yang tetap layak dicatat meski null. Pertama, **tandanya negatif dan
konsisten di kedua paruh** (-0,116 dan -0,068): sentuhan di dalam jendela
killzone berkinerja lebih BURUK, bukan lebih baik, dan itu arah yang
berlawanan dengan klaim sumbernya. Kedua, **`Q3` - jendela unggulan sumbernya
sendiri, "Q3 of Q3" - adalah nomor kuarter dengan delta paling negatif dari
ketiganya**, dan tanda paruhnya berbalik (-0,172 lalu +0,004), yang justru
tanda ketidakstabilan.

Tidak ada walk-forward yang dijalankan: aturan di bawah menyatakan walk-forward
diberikan kepada baris yang LULUS, dan tidak ada yang lulus.

### S2 Premium/discount berbasis waktu: null, dan kalah dari pembanding

| Kolom | Nilai | n | exp R | delta | t |
|---|---|---|---|---|---|
| `tpd_outside` | di dalam band | 318 | -0,051 | +0,100 | **+1,53** |
| `tpd_outside` | di atas band | 324 | -0,181 | -0,088 | -1,41 |
| `tpd_outside` | di bawah band | 304 | -0,142 | -0,030 | -0,43 |
| `tpd_band` | premium | 409 | -0,166 | -0,075 | -1,22 |
| `tpd_band` | equilibrium | 150 | -0,050 | +0,083 | +0,99 |
| `tpd_band` | discount | 387 | -0,111 | +0,016 | +0,25 |

**Gagal.** |t| terbesar 1,53 lawan 3,53.

Dan pembandingnya, `range_band` (dealing range berbasis swing, yang sudah ada):

| Kolom | Nilai | n | exp R | delta | t |
|---|---|---|---|---|---|
| `range_band` | discount | 105 | -0,268 | -0,163 | -1,83 |
| `range_band` | equilibrium | 362 | -0,192 | -0,109 | -1,82 |
| `range_band` | premium | 132 | -0,048 | +0,083 | +0,93 |

Keduanya null, dan yang lama |t|-nya sedikit lebih besar (1,83 lawan 1,53).
Jadi **pembacaan tanpa parameter tidak menggantikan yang ber-knob**, dan
`dealing_range.py` tetap satu-satunya yang terpasang.

> [!WARNING]
> **Ini BUKAN uji berpasangan yang diminta praregistrasi.** Bagian S2 di atas
> menuntut delta per-event antara `tpd_pos` dan `range_pos`; yang dijalankan
> adalah dua kolom berdampingan pada populasi yang sama di run yang sama. Itu
> cukup untuk menjawab "apakah yang baru mengalahkan yang lama secara mencolok"
> - tidak - dan TIDAK cukup untuk mengukur selisihnya. Uji berpasangannya masih
> terbuka, dan tidak akan diberi prioritas selama keduanya null.

### Replikasi di instrumen kedua, dan di sini hasilnya BERUBAH

Kolom yang sama, rig yang sama, `mt5:BTCUSD` 1h 50.000 bar. **n = 1.420, exp R
populasi -0,140, 129 grup, |t| kritis 3,55.**

| Kolom | Nilai | n | exp R | delta | t | Paruh |
|---|---|---|---|---|---|---|
| `tpd_outside` | di dalam band | 417 | **+0,075** | **+0,304** | **+5,38** | +0,256 / +0,348 |
| `tpd_outside` | di atas band | 507 | -0,225 | -0,132 | -2,44 | -0,066 / -0,195 |
| `tpd_outside` | di bawah band | 481 | -0,237 | -0,147 | -2,56 | -0,160 / -0,134 |
| `tpd_band` | equilibrium | 208 | +0,078 | +0,255 | **+3,71** | +0,140 / +0,359 |
| `kz_depth` | selaras | 412 | -0,189 | -0,069 | -1,20 | -0,032 / -0,103 |

`tpd_outside = inside` **menyeberang ambang** (5,38 lawan 3,55), kedua paruhnya
sepakat, dan n-nya jauh di atas minimum. Itu baris pertama di seluruh adopsi ini
yang melewati satu pun gerbang praregistrasi, jadi ia dikenai dua gerbang
berikutnya.

**Walk-forward, `tools/qtaz_walkforward.py`, delapan fold kronologis:**

| Fold | n (inside/lainnya) | delta | t | Sepakat |
|---|---|---|---|---|
| 1 | 44 / 133 | +0,354 | +2,40 | ya |
| 2 | 54 / 124 | +0,237 | +1,23 | ya |
| 3 | 54 / 123 | -0,013 | -0,09 | **tidak** |
| 4 | 41 / 137 | +0,471 | +3,38 | ya |
| 5 | 51 / 126 | +0,268 | +1,87 | ya |
| 6 | 62 / 116 | +0,305 | +2,05 | ya |
| 7 | 55 / 122 | +0,518 | +2,86 | ya |
| 8 | 56 / 122 | +0,294 | +2,01 | ya |

**7 dari 8**, ambangnya 6. Lolos.

**Kontrol tumpang tindih, dan ini yang paling penting.** Sebuah klausa yang
SUDAH ADA, `discount_or_premium` (dealing range berbasis swing), juga memisahkan
di BTC dengan arah yang sama: t = -3,82 untuk sisi ekstremnya. Jadi pertanyaannya
bukan lagi "apakah memisahkan" melainkan "apakah menambah apa pun di atas yang
sudah kita punya". Dipisah menurut klausa lama:

| Strata `discount_or_premium` | n (inside/lainnya) | delta | t | Tumpang tindih |
|---|---|---|---|---|
| False | 312 / 591 | +0,185 | +2,82 | 312 dari 903 |
| True | 104 / 407 | +0,509 | +4,26 | 104 dari 511 |

Kolom baru tetap memisahkan **di dalam kedua strata**, dengan tanda yang sama,
dan partisinya jelas berbeda dari yang lama. Jadi ia bukan pembacaan lama yang
diberi nama baru.

> [!IMPORTANT]
> **Dan tetap BUKAN temuan, karena XAU mengatakan tidak.** Kolom yang sama di
> XAUUSD memberi t = +1,53 lawan ambang 3,53 - gagal. Dan klausa lama
> `discount_or_premium` juga gagal di XAU (t = -0,88). Jadi yang ditemukan bukan
> "kolom baru bekerja", melainkan: **di BTC, berada di luar range sesi
> sebelumnya sangat merugikan, dan pembacaan tanpa parameter atas fakta itu
> lebih tajam daripada yang ber-knob; di XAU tidak satu pun dari keduanya
> membaca apa pun.** Satu instrumen dari dua.
>
> Kontrol tambahan yang menutup satu penjelasan alternatif: `adx_band` dan
> `bb_width_regime` TIDAK memisahkan di BTC (|t| <= 1,68), jadi ini bukan bacaan
> volatilitas yang sudah kita punya dengan label lain.
>
> **Tidak ada gerbang yang dinyalakan.** Aturan 6 di bawah berlaku apa adanya.
> Yang berubah cuma satu: `tpd_outside` sekarang punya angka, dan angkanya
> terbelah antar instrumen.

### S3 dan S4 belum dijalankan

`Hidden SSMT` dan `SMT Fill` membutuhkan rig outcome-nya sendiri
(`ssmt_outcomes` dengan lengan ketiga, dan bracket baru untuk fill), bukan
kolom pengkondisi. Keduanya masih persis seperti yang ditulis di atas: mati by
default, nol gerbang, nol angka.

## Aturan yang berlaku untuk keempatnya

1. **Kontrol placebo di setiap studi.** Objek berukuran sama dipindah ke waktu
   atau harga acak, aturan yang sama dengan rig detektor. Kalah dari placebo
   adalah gagal, bukan "hampir".
2. **Walk-forward 8 fold.** Ambang dipilih di fold luar sampel, bukan di seluruh
   sampel. Enam dari delapan minimum.
3. **Bonferroni atas jumlah sel yang benar-benar dijalankan**, dihitung setelah
   selnya ditetapkan di dokumen ini dan tidak setelah melihat hasil.
4. **Rig harus dibuktikan bisa hijau.** Setiap tool membawa lengan `--oracle`
   yang melihat masa depan dan karena itu wajib lulus. Nol pemenang tanpa oracle
   yang lulus adalah laporan tentang diamnya rig, bukan diamnya pasar - aturan
   yang sama dipakai `tools/phase_targets.py`.
5. **Angka mentah bergerak antar hari** karena feed-nya hidup. Yang dibandingkan
   vonisnya, bukan hitungan objeknya.
6. **Tidak ada gerbang yang menyala sebelum semua ini lulus.** Sampai saat itu
   keempatnya adalah gambar, dan `evidence` masing-masing berbunyi "belum
   diukur".

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

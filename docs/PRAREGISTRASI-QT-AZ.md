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
- [Aturan yang berlaku untuk keempatnya](#aturan-yang-berlaku-untuk-keempatnya)

## Yang sudah terpasang

| Studi | Objek | Kode | Saklar | Terukur |
|---|---|---|---|---|
| S1 | QT Killzone | `app/sequence.py:killzones` | `session.killzones` | belum |
| S2 | Premium/discount waktu | `app/quarterly.py:time_premium_discount` | `session.premium_discount` | belum |
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

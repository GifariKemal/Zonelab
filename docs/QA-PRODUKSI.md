# QA/QC Zonelab menuju produksi

Catatan kerja yang ditulis sambil jalan, bukan laporan yang dirapikan setelah
selesai. Setiap angka di sini berasal dari perintah yang benar-benar dijalankan di
mesin ini, dan bila sebuah klaim belum terukur, kalimatnya mengatakan begitu.

> [!NOTE]
> Tanggal kerja: 19-20 Agustus 2026. Mesin: Windows 11 Pro, Node 22.22.2,
> Python 3.13 di `backend/.venv`, terminal MT5 aktif sebagai sumber harga.

## Daftar Isi

Enam belas bagian, dan urutannya adalah urutan pengerjaannya - bukan urutan
kepentingannya. Kalau hanya ada waktu untuk tiga: bagian 3 adalah celah gambar
terbesar yang ditemukan, bagian 11 adalah keadaan akhir yang terukur, dan bagian 7
adalah cerita tentang bagaimana memperbaiki peringatan yang paling murah justru
merusak dua hal.

| | Bagian | Isinya sebaris |
|---|---|---|
| 1 | [Kemutakhiran tech stack](#1-kemutakhiran-tech-stack) | TypeScript 6, dan kenapa TS 7 serta ESLint 10 ditolak |
| 2 | [Multi timeframe](#2-multi-timeframe-htf-hanya-bekerja-untuk-satu-layer) | HTF diam untuk empat detektor, dan bar mingguan salah empat hari |
| 3 | [Dealing range](#3-dealing-range-dihitung-distempel-tidak-pernah-digambar) | dihitung selama ini, tidak pernah sampai ke kanvas |
| 4 | [Korelasi lintas instrumen](#4-korelasi-lintas-instrumen-yang-sebelumnya-tidak-ada-sama-sekali) | nol perhitungan korelasi di repo, sekarang terukur per pasangan |
| 5 | [Instrumen tak terjangkau](#5-instrumen-yang-jalan-tapi-tidak-terjangkau) | `US30` dan `GBPJPY` jalan tapi tidak ada di picker |
| 6 | [Stress test](#6-stress-test) | draw terberat, konkurensi, churn, memori |
| 7 | [Peringatan lint](#7-peringatan-lint-dan-kerusakan-yang-saya-buat-sendiri-saat-memperbaikinya) | 13 peringatan sepele ditukar dengan 2 kerusakan sunyi |
| 8 | [Kalibrasi lawan open source](#8-kalibrasi-lawan-implementasi-open-source) | tidak ada jawaban kanonik untuk hampir setiap aturan |
| 9 | [Benchmark](#9-benchmark-di-mana-kita-berdiri) | kalimat anti-repaint sudah ditempati, artefaknya kosong |
| 10 | [Uji visual](#10-uji-visual-apa-yang-hanya-bisa-ditemukan-dengan-melihat) | tiga cacat yang tidak bisa ditemukan asersi piksel |
| 11 | [Keadaan akhir](#11-keadaan-akhir-terukur) | setiap gate, dan apa yang masih terbuka |
| 12 | [Siklus hidup zona](#12-siklus-hidup-zona-auditor-benar-kalimatnya-salah) | isian 1,03:1 lawan border 3,20:1 |
| 13 | [Equal high dan equal low](#13-equal-high-dan-equal-low-dibangun) | dibangun, plus cacat desain saya yang dibuktikan dulu |
| 14 | [Label berimpit](#14-label-level-yang-berimpit-dibuang-bukan-ditumpuk) | digabung `PDL/PDH` alih-alih dibuang |
| 15 | [Cleanup](#15-cleanup-dan-satu-repaint-yang-ditemukan-saat-merapikan) | apa yang dihapus, apa yang hampir dihapus padahal bukti |
| 16 | [Launcher sekali klik](#16-launcher-sekali-klik-dan-insiden-desktop) | start.bat dan stop.bat, plus insiden desktop yang saya sebabkan |

> [!TIP]
> Setiap bagian berisi angka dan perintah yang menghasilkannya. Kalau sebuah klaim
> di sini tidak punya angka, kalimatnya mengatakan bahwa ia belum terukur.

## 1. Kemutakhiran tech stack

Diperiksa lawan rilis terbaru di registry, bukan lawan ingatan.

### Yang sudah di rilis terbaru

| Paket | Terpasang | Terbaru | Catatan |
|---|---|---|---|
| next | 16.3.1 | 16.3.1 | Turbopack |
| react, react-dom | 19.2.8 | 19.2.8 | |
| lightweight-charts | 5.2.1 | 5.2.1 | |
| tailwindcss | 4.3.3 | 4.3.3 | |
| playwright | 1.62.1 | 1.62.1 | |
| fastapi | 0.141.1 | 0.141.1 | |
| pydantic | 2.13.4 | 2.13.4 | |
| numpy | 2.5.2 | 2.5.2 | |
| starlette | 1.6.0 | 1.6.0 | |
| pytest | 9.1.1 | 9.1.1 | |
| MetaTrader5 | 5.0.6090 | 5.0.6090 | |

### Yang dinaikkan

**TypeScript 5.9.3 ke 6.0.3.** Typecheck penuh selesai dalam 1,1 detik. Gate-nya
dibuktikan tidak kosong: sebuah file dengan `const n: number = "..."` membuat
`tsc --noEmit` keluar dengan kode 2 dan pesan TS2322, lalu hijau kembali setelah
file itu dibuang.

**`@types/node` 20.19.43 ke 22.20.1.** Ini kalibrasi:
harness e2e benar-benar berjalan di Node 22.22.2, sementara definisi tipenya
menggambarkan Node 20. Versi terbaru di registry adalah 26, dan itu justru salah
untuk kita, karena akan memberi tipe pada API yang tidak ada di runtime kita.
Tipe harus setara runtime, bukan lebih tua dan bukan lebih baru.

### Yang ditolak, dengan alasannya

**TypeScript 7.0.2 ditolak.** TS 7 adalah port native ke Go dan typecheck-nya
memang lebih cepat lagi, tetapi `typescript-eslint` 8.67.0 menolaknya secara
eksplisit di `dist/index.js:45-52`:

```
typescript-eslint does not support TS 7.0.
```

Rentang peer-nya `typescript: >=4.8.4 <6.1.0`. Artinya memasang TS 7 menukar
gate lint dengan kecepatan compile, dan itu pertukaran yang salah arah. TS 6.0.3
adalah titik tertinggi yang tidak mematikan apa pun.

`tsconfig.json` kita sudah bersih dari semua opsi yang TS 7 hapus (`baseUrl`,
target ES5, `moduleResolution` node10 atau classic, `outFile`, `downlevelIteration`,
`esModuleInterop: false`, modul AMD/UMD/System). Jadi begitu `typescript-eslint`
mendukung TS 7, kenaikannya hanya satu perintah.

**ESLint 10.8.1 ditolak.** Memutus `eslint-plugin-react` yang dibundel
`eslint-config-next` 16.3.1:

```
TypeError: Error while loading rule 'react/display-name':
contextOrFilename.getFilename is not a function
```

ESLint 10 membuang API konteks lama yang masih dipakai plugin itu. Tetap di 9.39.5.

### Cacat yang lebih penting daripada nomor versinya

**Gate lint bisa crash total dan terbaca bersih.** Saat TS 7 terpasang, `eslint`
mati sebelum memeriksa satu file pun, tetapi ringkasan yang saya baca berbunyi
`ESLint: No issues found`. Dua hal menyebabkannya: proxy RTK meringkas output
eslint dan tidak membedakan crash dari nol temuan, dan saya sendiri menyalurkan
output-nya lewat `tail` sehingga kode keluarnya hilang.

Perbaikannya sebuah skrip yang tidak bisa berbohong:

```json
"typecheck": "tsc --noEmit",
"check": "npm run typecheck && npm run lint"
```

Dibuktikan gagal di kedua arah, bukan hanya diasumsikan:

| Keadaan | `npm run check` |
|---|---|
| Kesalahan tipe disuntikkan | keluar 2 |
| Pelanggaran lint disuntikkan | keluar 1 |
| Bersih | keluar 0 |

> [!WARNING]
> Jangan menilai gate dari ringkasan yang tersalur lewat `tail` atau lewat
> proxy yang memformat ulang. Baca kode keluarnya. Pola ini sudah tiga kali
> menipu proyek ini, dan dua kali di antaranya yang tertipu adalah instrumennya
> sendiri, bukan kodenya.

### Catatan pemaparan jaringan

`next dev` mengikat ke `0.0.0.0:3100`, jadi ia terjangkau dari LAN
(`http://192.168.1.3:3100`). API mengikat ke `127.0.0.1:8100` saja, dan itu benar.
Untuk pemakaian produksi, server web perlu berada di belakang proksi, bukan
terpapar langsung.

## 2. Multi timeframe: HTF hanya bekerja untuk satu layer

Diperiksa lewat panggilan API langsung, bukan lewat kode.

### HTF diam-diam tidak melakukan apa pun

Picker HTF ada di header halaman, selalu aktif, dan tidak pernah dikaitkan ke
layer mana pun. Proyeksi HTF hidup di dalam handler `supply_demand` saja, jadi:

| Permintaan | Hasil sebelum perbaikan |
|---|---|
| `htf=4h`, layer `supply_demand` | `meta.htf` terisi, zona 4h tergambar |
| `htf=4h`, layer `fvg` dan `order_block` | HTTP 200, `meta.htf` **tidak ada**, semua zona 15m, tanpa peringatan |

Pembaca menyalakan HTF, tidak melihat perubahan apa pun, dan tidak punya apa pun
untuk dibaca. Sesudah perbaikan, lima detektor box (`HTF_LAYERS`) melewati jalur
yang sama, dan yang tidak bisa memakai HTF **berkata**:

```
HTF 4h is selected but none of the layers that are on can be read on a higher
timeframe. The five box detectors can: breaker, fvg, ifvg, order_block, supply_demand
```

Terukur sesudahnya, XAUUSD 15m 2000 bar, `htf=4h`, layer `fvg`, `order_block`,
`ifvg`, `breaker`: 134 bar 4h, dan 24 zona 4h di samping 34 zona lokal.

Bentuk `meta["htf"]` berubah jadi bersarang, `{interval, note, layers:{...}}`,
karena lima layer kini bisa menjawab dan satu ember rata akan membuat yang
terakhir menimpa empat sebelumnya.

Refinement tetap milik `supply_demand` sendiri, dan itu bukan kelalaian:
`refine.py` mengecilkan box ke jeda **di dalamnya**, dan sebuah fair value gap
tidak punya basis untuk dikecilkan.

### Bar mingguan salah empat hari

`resample` menjangkar bucket ke epoch Unix. 1 Januari 1970 hari **Kamis**, jadi
`time // 604800` menaruh setiap batas mingguan di hari Kamis. Diminta instrumen
yang sama pada saat yang sama, seri W1 broker sendiri mulai **Minggu 00:00**.

Sebelum diperbaiki, permintaan 1w di chart emas harian mengembalikan empat zona
yang mulai 2024-08-22, 2025-02-06, 2025-04-03 dan 2025-09-11, semuanya Kamis.

`session_offset_hours` tidak bisa memperbaikinya: knob itu dibatasi plus minus 12
jam karena memang untuk hari broker yang mulai 22:00, bukan untuk selisih empat
hari.

Sesudah `WEEK_PHASE = 3 * 86400`:

| Perbandingan lawan seri W1 asli MT5 | Hasil |
|---|---|
| Timestamp bersama | 49 |
| Bar dengan OHLC berbeda | **0** |

Dan yang harian ternyata sudah benar sejak awal, jadi tidak disentuh: agregasi
seri 1h broker jadi 1d mereproduksi bar D1 aslinya dengan **0 dari 39** bar
berbeda, dan tidak mengarang satu bucket pun. Dugaan awal saya bahwa ada bucket
Minggu palsu ternyata hanya artefak rentang window; dengan window asli yang lebih
lebar, selisihnya nol.

Gate repaint diperluas: tes baru memeriksa box HTF untuk kelima detektor,
membekukan kedua harga, bar pembuka dan sisinya. Edge KANAN sengaja tidak diuji,
karena zona hidup memang dibawa maju ke bar terakhir chart supaya tidak tampak
berhenti lebih awal.

## 3. Dealing range: dihitung, distempel, tidak pernah digambar

Ini celah gambar terbesar yang ditemukan.

Mesin sudah lama menghitung dealing range dengan benar dan anti-lookahead
(`knowable_at` adalah yang **terakhir** dari dua konfirmasi swing), menstempel
setiap box dengan posisinya, dan panel zona mencetak posisi itu sebagai persen.
Tetapi rangenya sendiri tidak pernah sampai ke kanvas. Ia hanya jadi dua angka di
panel samping.

Premium dan discount adalah kerangka yang paling sering dipakai metode ini. Dari
51 chart referensi, garis putus 50 persen di dalam sebuah range muncul di **36**,
dan salah satunya menggambar tangga 0,25 / 0,5 / 0,75 secara eksplisit. Jadi
kerangka yang dipakai untuk menilai setiap box pembaca adalah satu-satunya hal
yang tidak bisa ia lihat.

Sekarang toggle `Range frame` menggambar lima garis:

| Label | Isi | Gaya |
|---|---|---|
| `RNG H` | ekstrem atas range | solid |
| `PREM 75` | batas premium | putus |
| `EQ 50` | ekuilibrium | putus |
| `DISC 25` | batas discount | putus |
| `RNG L` | ekstrem bawah range | solid |

Solid lawan putus bukan selera: `RNG H` dan `RNG L` adalah harga yang benar-benar
tercetak pasar, tiga yang di tengah adalah aritmetika atas keduanya. Itu konvensi
referensi, dan dibawa oleh field `derived` sendiri, bukan dengan membebani
`boundary` - versi pertama menguji `boundary == "range"` dan itu salah, karena
ekstrem range juga berlabel `range` sementara keduanya harga tercetak.

Yang membuat ini kalibrasi dan bukan hiasan: ambangnya **diimpor** dari
`app/dealing_range.py`, konstanta yang sama yang diuji `app/deduce.py`. Jadi garis
0,75 di layar dan batas 0,75 di dalam putusan tidak bisa berpisah.

### Tujuh dari tiga belas nama level terpotong sunyi

Ditemukan dengan melihat screenshot, lalu diukur. Kolom label lebarnya
`LABEL_GUTTER = 46` piksel dan labelnya digambar rata kiri dari situ tanpa klem,
jadi nama yang lebih lebar dipotong edge kanvas. Fontnya `10px ui-monospace`, yang
majunya tepat **5,5 piksel per karakter**, jadi anggarannya 8 karakter.

| Nama lama | Karakter | Piksel | Status |
|---|---|---|---|
| `FRIDAY_HIGH` | 11 | 60,5 | terpotong, sudah lama terkirim |
| `MONDAY_HIGH` | 11 | 60,5 | terpotong, sudah lama terkirim |
| `FRIDAY_LOW` | 10 | 55,0 | terpotong, sudah lama terkirim |
| `MONDAY_LOW` | 10 | 55,0 | terpotong, sudah lama terkirim |
| `range_high` | 10 | 55,0 | tampil sebagai `range_hi` |
| `range_low` | 9 | 49,5 | terpotong |
| `PREM 0.75` | 9 | 49,5 | tampil sebagai `PREM 0.7` |

Empat yang pertama bukan bawaan perubahan ini. Mereka sudah menggambar terpotong
di setiap chart yang pembacanya memilih periode friday atau monday, dan tidak ada
apa pun yang memperingatkan. Nama yang terpotong lebih buruk daripada nama yang
hilang, karena `FRIDAY_HI` masih terlihat seperti label yang memang ditulis orang.

Sekarang: `FRI H`, `FRI L`, `MON H`, `MON L`, `RNG H`, `RNG L`, `PREM 75`,
`DISC 25`, `EQ 50`. Semuanya di bawah anggaran.

`test_every_level_name_fits_the_canvas_label_column` membaca `LABEL_GUTTER`
langsung dari sumber TypeScript, jadi kedua sisi tidak bisa berpisah. Dibuktikan
tidak kosong: mengembalikan satu nama ke `FRIDAY_HIGH` membuatnya gagal dengan
menyebut nama dan pikselnya.

### Ekuilibrium kehilangan namanya

Terlihat di screenshot: garis putus di 4428 tanpa nama sama sekali. Kolom
label adalah peta tabrakan bersama dan klaim pertama yang menang, dan kerangka
ditambahkan paling belakang, jadi ia kalah di setiap seri - dan yang kalah adalah
**ekuilibrium**, karena sebuah previous day high duduk enam poin di atasnya dan
sudah mengklaim barisnya.

Sekarang kerangka mengklaim namanya lebih dulu. Lima garis yang membingkai seluruh
window mengalahkan sampai enam belas ekstrem periode, dan ekuilibrium adalah
garis yang justru dipakai pembaca untuk membaca premium dan discount.

Diverifikasi dengan mata pada screenshot sesudahnya: kelima label terbaca
utuh, dan PDH, PDL serta PWL di sekitarnya tetap berlabel.

## 4. Korelasi lintas instrumen, yang sebelumnya tidak ada sama sekali

Zonelab dibangun untuk membaca divergensi **antar instrumen berkorelasi**, dan
docstring `ssmt.py` sendiri menyatakan tingkat temuannya "melacak korelasi": emas
lawan perak berbeda arah di 14,9 persen bacaan, lawan DXY di 59,5 persen. Tetapi
tidak ada satu pun perhitungan korelasi di repo. `grep` untuk `corrcoef`, `.corr(`,
`np.cov`, `polyfit`, `linregress` di seluruh backend, tools dan frontend
mengembalikan nol.

Satu-satunya yang berdiri antara pembaca dan pasangan yang tak bermakna adalah
daftar tiga ticker yang di-hardcode di `toolbox.tsx`:

```ts
const INVERSE = ["DXY", "US10Y", "US30Y"];
```

Daftar itu salah di dua arah. Dua dari tiganya tidak terjangkau di terminal ini,
dan ia tidak menyebut WTI maupun USDJPY, yang keduanya terukur negatif.

### Yang terukur

`app/correlation.py`, Pearson atas **log return** dan bukan atas harga, di grid
terselaraskan yang sama tempat divergensinya dihitung. XAUUSD 1h, 1067 pasang
return:

| Pasangan | Seluruh window | Kuartal terakhir |
|---|---|---|
| XAGUSD | +0,856 | +0,825 |
| DXY | -0,588 | -0,525 |
| COPPER | +0,536 | +0,467 |
| NAS100 | +0,397 | +0,208 |
| WTI | -0,332 | -0,265 |
| BTCUSD | +0,277 | +0,156 |
| USDJPY | -0,275 | -0,235 |

Log return, bukan harga, dan itu bukan detail: dua deret yang sama-sama menanjak
berkorelasi mendekati +1 tanpa alasan selain sama-sama menanjak. Tesnya memasang
justru kasus itu - satu deret zigzag naik lawan satu tanjakan mulus - dan
menuntut hasilnya di bawah 0,35.

Dua window, karena korelasi adalah sifat sebuah pasangan **atas suatu periode**,
bukan sifat pasangannya. Kalau keduanya berbeda tanda, ketidaksepakatan itulah
temuannya, dan panel mengatakannya.

Yang tidak diklaim: tidak ada arah, tidak ada ramalan, tidak ada penilaian pasangan
bagus atau buruk. Korelasi tinggi tidak membuat sebuah divergensi bermakna, ia
membuatnya **jarang**, dan itu pernyataan yang berbeda.

### Satu pasangan gugur membunuh seluruh keranjang

`asyncio.gather` dipanggil tanpa `return_exceptions`, jadi satu fetch gagal
membatalkan seluruh saudaranya. Terukur langsung: meminta emas lawan perak, dolar,
minyak, Nasdaq, bitcoin, yen **dan** US10Y mengembalikan

```json
{"drawn": 0, "error": "mt5 does not carry US10Y"}
```

Tujuh pasangan valid hilang karena satu instrumen yang broker ini memang tidak
punya kontraknya - kondisi permanen, bukan sesaat.

Sekarang simbol pertama wajib dan sisanya tidak, karena setiap caller menaruh
simbol chart-nya di depan. Yang gugur dilaporkan dengan kalimat providernya
sendiri, bukan sebagai hitungan: "1 dilewati" memaksa pembaca menebak instrumen
mana yang hilang, padahal providernya sudah mengatakan.

Diverifikasi di UI: dengan `US10Y` diminta bersama tiga pasangan lain, panel
menampilkan `Not loaded: US10Y: mt5 does not carry US10Y` dan ketiga korelasi lain
tetap terhitung dari 1915 pasang bar.

### Satu duplikat konstanta lagi

Blok SSMT di `main.py` menulis `>= 0.75` dan `<= 0.25` langsung di tempat -
salinan ketiga dari ambang yang juga hidup di `deduce.py` dan sekarang digambar di
kanvas oleh range frame. Jadi blok itu bisa melabeli sebuah divergensi
"premium" sementara garis di sebelahnya berkata lain. Ketiganya sekarang mengimpor
dari `app/dealing_range.py`.

### Bahaya unit lintas venue

Diukur saat smoke test 20 simbol: `COPPER` di MT5 tutup di **13968,59** sementara
di Yahoo **6,44**. Itu bukan selisih basis seperti emas spot lawan COMEX (sekitar
64 dolar), itu unit yang sama sekali berbeda, faktor sekitar dua ribu. Korelasi
return kebal terhadap itu secara konstruksi, dan `aligned.py` memang diberi satu
provider saja. Tetapi apa pun yang membandingkan **harga** lintas venue akan jadi
omong kosong, dan sekarang tertulis.

## 5. Instrumen yang jalan tapi tidak terjangkau

`US30` dan `GBPJPY` mengembalikan bar MT5 nyata selama ini lewat jalur
pass-through, dan keduanya tidak ada di tabel `SYMBOLS` - jadi tidak muncul di
picker simbol, yang dibuat dari kunci tabel itu. Keduanya hanya terjangkau dengan
menyunting URL. `DE40` dicoba dan broker ini tidak punya simbol itu; DAX di sini
bernama `DE30`, yang tidak diketahui apa pun.

Ditambahkan lima, masing-masing diukur dulu:

| Id | MT5 | Yahoo | Alasan |
|---|---|---|---|
| `US30` | `US30` | `YM=F` | melengkapi kompleks indeks AS di samping NAS100 dan SPX500 |
| `USDJPY` | `USDJPY` | `USDJPY=X` | pasangan FX paling relevan ke emas setelah indeks dolar |
| `GBPJPY` | `GBPJPY` | `GBPJPY=X` | |
| `NGAS` | `XNGUSD` | `NG=F` | kaki energi di samping WTI dan BRENT |
| `DE30` | `DE30` | tidak ada | Yahoo tidak menerbitkan future DAX |

`YM=F` memberi 90 bar di window 5 hari 1h sementara `^DJI` hanya 31, jadi future
lagi, sesuai aturan tabel itu sendiri. Untuk DAX, `FDAX=F` menjawab 404 dan
`DAX=F` menjawab 200 dengan nol bar; indeks kas `^GDAXI` ada dengan 45 bar, dan
aturan tabel ini adalah indeks kas ditinggalkan daripada ditawarkan sebagai
jebakan. Satu provider adalah fakta tentang venue, bentuk yang sama dengan
`US10Y` dan `US30Y` secara terbalik.

Smoke test seluruh matriks sesudahnya: **37 dari 37** pasangan simbol-provider
mengembalikan bar, 20 simbol, MT5 dan Yahoo.

## 6. Stress test

`backend/tools/stress.py`, dijalankan lawan server yang hidup. Tidak ada satu pun
ambang yang ditegaskan di sana, dan itu sengaja: belum ada baseline terukur untuk
apa yang "seharusnya" dicapai mesin ini, jadi memasang gate tanpa bukti akan
jadi gate tanpa dasar. Ia mencetak angka dan menyebut kegagalan; yang menilai
manusia. Satu hal yang tetap dinilai adalah error, karena HTTP 500 salah pada
kecepatan berapa pun.

### Draw terberat yang jujur

Enam belas layer nyala, setiap display cap diangkat ke 0 - konfigurasi yang
dipakai setiap pengukuran, jadi ini bukan kasus terburuk buatan.

| Bar | Waktu | Objek | Objek per detik |
|---|---|---|---|
| 500 | 0,10 s | 772 | 7.953 |
| 1000 | 0,18 s | 1.510 | 8.435 |
| 2000 | 0,43 s | 2.972 | 6.859 |
| 5000 | 1,19 s | 7.353 | 6.203 |

Sedikit di atas linear, dan itu wajar: beberapa pass adalah O(n log n) atas
jumlah objek, bukan atas jumlah bar.

### Semua parameter numerik di batasnya, sekaligus

44 parameter ke minimum sekaligus: 0,13 detik, 1.853 objek. 43 ke maksimum: 0,08
detik, 265 objek. Tidak ada crash, tidak ada pembagian dengan range selebar nol.

### Konkurensi, dan ini plafon yang perlu dinyatakan

| Serentak | Wall | Median | vs sendirian |
|---|---|---|---|
| 1 | 0,39 s | 0,17 s | x1,0 |
| 2 | 0,69 s | 0,34 s | x2,0 |
| 4 | 1,09 s | 0,63 s | x3,7 |
| 8 | 1,94 s | 1,23 s | x7,3 |

Praktisnya **terserialisasi**: delapan permintaan serentak masing-masing tujuh kali
lebih lambat. Itu bukan kejutan dan bukan cacat pada pemakaian yang dituju - jalur
draw adalah kerja sinkron yang diserahkan ke thread pool, dan MT5 adalah pustaka C
satu-utas di belakang satu lock seluruh proses, jadi GIL dan lock itu keduanya
menyerialisasi. Throughput draw terberat sekitar 4 permintaan per detik.

> [!IMPORTANT]
> Untuk satu pengguna di desktop, ini cukup dengan margin besar. Untuk banyak
> pengguna, ini plafonnya, dan angkanya ada di sini supaya tidak ditemukan lewat
> keluhan.

### Churn

30 permintaan dibatalkan di tengah jalan (timeout 150 ms, lebih pendek dari draw
mana pun di sini, jadi setiap satunya benar-benar dibatalkan saat server masih
bekerja - yang persis dilakukan slider yang digeser). Sesudahnya satu draw jujur
selesai dalam 0,22 detik dengan 1.510 objek. Tidak ada worker yang tertahan.

### Memori, dan instrumen saya sendiri yang berbohong lebih dulu

Versi pertama pengukurnya mengidentifikasi prosesnya sebagai "python.exe terbesar".
Atas 300 draw berat ia melaporkan +24,9, +164,1, +46,7, **-138,5** lalu +236,7 MB.
Delta negatif 138 MB bukan perilaku memori, itu proses berbeda yang terukur setiap
kali: tool ini sendiri python.exe, begitu juga setiap tool lain di direktori itu,
dan dua agen sedang jalan saat itu.

Diukur terhadap proses yang benar-benar memegang port 8100, 300 draw berat yang
sama menggerakkan RSS **+0,2 MB**, berayun dalam 6 MB dan berakhir di tempat ia
mulai:

| Draw | RSS | Delta |
|---|---|---|
| 0 | 151,3 MB | |
| 25 | 150,8 MB | -0,4 |
| 50 | 146,1 MB | -4,7 |
| 100 | 146,2 MB | +0,1 |
| 200 | 151,9 MB | +5,6 |
| 300 | 151,5 MB | -0,4 |

Tidak ada kebocoran. Tool-nya sekarang mengidentifikasi proses lewat port, dan
alasannya tertulis di docstring-nya supaya tidak diulang.

### Satu 422 yang ternyata kesalahan saya

Jalan pertama tool ini melaporkan dua puluh HTTP 422. Semuanya salah saya:
`fvg`, `order_block`, `ifvg` dan `breaker` **berbagi satu blok** `imbalance`, dan
`DrawRequest` melarang kunci tambahan, jadi `{"fvg": {...}}` adalah 422 dan bukan
no-op sunyi. Modelnya bekerja seperti seharusnya. Nama bloknya sekarang diambil
dari skema yang disajikan, bukan diketik ulang.

## 7. Peringatan lint, dan kerusakan yang saya buat sendiri saat memperbaikinya

pyflakes melaporkan 13 peringatan di `tools/`, semuanya satu jenis:
`f-string is missing placeholders` - sebuah `f"..."` tanpa `{}` di dalamnya.
Sepele, dan perbaikannya mekanis: buang awalan `f`.

Saya menulis sweep regex yang menyentuh baris yang dilaporkan **dan empat baris
sesudahnya**, karena literal yang dirangkai bisa membentang beberapa baris.
pyflakes lalu melaporkan nol, pytest hijau, dan semuanya tampak selesai.

**Dua f-string yang sah kehilangan awalannya.**

| File | Yang tercetak sesudahnya |
|---|---|
| `tools/blind_gate.py:120` | `SECOND HALF at the blindly chosen {gate:.1f} ATR` |
| `tools/mss.py:425` | `{k.split(',')[0]} {np.mean([r['leg_atr'] for r in v]):.2f}` |

Keduanya masuk ke **laporan pengukuran**. Pembaca akan melihat kurung kurawal di
tempat sebuah ambang seharusnya berada, dan tidak punya cara tahu angka mana yang
sebenarnya dipilih run itu.

Tidak ada yang menangkapnya. Ia meng-compile, lolos setiap pemeriksaan tipe,
pyflakes diam karena string biasa berisi kurung kurawal itu sah sempurna, dan
suite hijau karena tidak ada tes yang membaca baris output itu. Hanya laporan
tercetaknya yang salah.

Jadi sekarang ada penjaganya:
`test_no_string_literal_looks_like_an_f_string_that_lost_its_prefix` menyusuri
AST setiap file Python dan menolak literal biasa yang berisi sesuatu berbentuk
field format. Docstring dilewati **berdasarkan identitas, bukan panjang** - satu
docstring di repo ini berbunyi `"""{multiple: price} for the standard range..."""`
dan itu memang menjelaskan bentuk dict, persis hal yang dicari pola ini, dan tidak
ada aturan panjang yang bisa memisahkan keduanya. Path route FastAPI seperti
`/api/snapshots/{snapshot_id}` juga dikecualikan, karena di sana kurung kurawalnya
memang maksudnya.

Dibuktikan tidak kosong: mengembalikan satu awalan `f` membuatnya gagal dengan
menyebut file, baris, dan literalnya.

> [!CAUTION]
> Peringatan yang paling murah untuk dibetulkan adalah yang paling berbahaya untuk
> dibetulkan secara mekanis. Sweep ini menukar 13 peringatan tak berbahaya dengan
> 2 kerusakan sunyi, dan kalau tesnya tidak ditulis, dua-duanya akan terkirim.

## 8. Kalibrasi lawan implementasi open source

Diperiksa lawan 17 sumber yang benar-benar terbuka: satu pustaka Python MIT
(`joshyattridge/smart-money-concepts`), sebelas skrip komunitas LuxAlgo
(CC BY-NC-SA, jadi **aturannya boleh diukur, kodenya tidak boleh dipakai**), dan
lima skrip MPL-2.0. Korpus `deepentropy/lightweight-charts-indicators`, 867 skrip.

Toolkit LuxAlgo berbayar dan invite-only **tidak disentuh**, dan tidak ada yang
di-decode. Yang dibaca hanya yang memang diterbitkan terbuka.

> [!IMPORTANT]
> Temuan terbesarnya bukan bahwa kita berbeda dari mereka. Temuan terbesarnya
> adalah **tidak ada jawaban kanonik** untuk hampir setiap aturan, jadi setiap
> pilihan harus diukur, bukan disalin.

### Tidak ada yang sepakat, dan ini daftarnya

| Aturan | Berapa jawaban beredar |
|---|---|
| Kapan sebuah FVG dianggap terisi | **enam** definisi berbeda, dari yang paling awal sampai paling akhir memicu |
| Apa itu order block | **tiga** aliran, menghasilkan himpunan objek yang hampir tidak beririsan |
| Lebar setengah swing | **2, 5, 7, 10, 50** - rentang 25 kali, tanpa alasan di mana pun |
| BOS lawan CHoCH | mesin keadaan bias-sebelumnya lawan urutan empat level, dua aturan tak sepadan |
| Toleransi equal high | `0.1 x ATR(200)` lawan `0.01 x (tinggi-rendah seluruh data` |
| Killzone New York | tiga sesi berbeda, tiga kebijakan DST |

`MSS` ternyata **bukan konsep ketiga**: satu sumber melabelinya persis di tempat
sumber lain melabeli CHoCH.

Dan dua hal yang absen sama sekali dari 867 skrip itu: **ambang displacement
berbasis ATR** (aturan ICT tertulis itu tidak terimplementasi di mana pun), dan
**Quarterly Theory** (nol kemunculan).

### Premium dan discount: tiga bacaan, dan kita bukan salah satu yang kanonik

Diverifikasi langsung di sumbernya, bukan lewat laporan:

```
Smart Money Concepts (SMC) [LuxAlgo], baris 756-761
  Premium      0.95*top + 0.05*bottom  ..  top
  Equilibrium  0.525/0.475 di sekitar tengah
  Discount     bottom  ..  0.95*bottom + 0.05*top
```

Itu **pita 5 persen di ujung**, bukan kuartil. Jadi tiga bacaan beredar: di atas
0,50 (buku teks ICT), di atas 0,95 (LuxAlgo), di atas 0,75 (kita). Tidak ada satu
pun implementasi open source yang menggambar tangga 0,25 / 0,5 / 0,75; satu chart
referensi menggambarnya, dan itulah dasar kita - satu chart praktisi, bukan
standar.

Karena itu range frame menggambar **kedua** batas yang mungkin dimaksud
pembaca: `EQ 50` adalah garis buku teks, `PREM 75` adalah garis kita yang lebih
ketat. Alasannya sekarang tertulis di `app/dealing_range.py` supaya pembaca yang
membandingkan chart kita dengan chart LuxAlgo tahu kenapa pitanya di tempat
berbeda.

### Repaint: bukti tingkat kode, bukan keluhan forum

Ini pembeda utama Zonelab, dan sekarang ada sitasinya. Dihitung sendiri di klon
repo-repo itu:

```
barmerge.lookahead_on  ->  204 kemunculan di 148 file
```

Termasuk `Smart Money Concepts (SMC) [LuxAlgo]` - indikator SMC terbuka paling
banyak dipasang - pada FVG dan pada level harian, mingguan, bulanannya.

Pola kedua yang lebih telanjang: **hapus semua lalu gambar ulang dari bar
terakhir**, `for bx in box.all -> bx.delete()` diikuti `if barstate.islast ->
draw`. Indikator seperti itu **tidak menyimpan catatan historis sama sekali**, jadi
membandingkannya secara adil menuntut replay bar demi bar, bukan membaca chart
akhirnya.

Dan pustaka Python MIT dengan 1.945 bintang itu, `swing_highs_lows()` melakukan
`swing_length *= 2` lalu `shift(-(swing_length//2))`, sehingga **konfigurasi
defaultnya membaca 50 bar ke depan**. Issue-nya sendiri melaporkan win rate
81,4 persen jatuh ke 52,8 persen ketika bias itu dibuang.

> [!NOTE]
> Garis yang tepat untuk klaim kita, dan ini pembatasan penting supaya tidak
> berlebihan: detektor rumahan LuxAlgo `high[len] > ta.highest(len)` dan
> `ta.pivothigh(high,7,7)` **tidak** repaint - keduanya hanya membaca bar lampau.
> Biayanya **jeda konfirmasi**, bukan repaint. Jadi implementasi yang jujur itu
> *terlambat*, yang tidak jujur itu *terlalu awal*. Zonelab terlambat, dengan
> sengaja, dan tesnya membuktikan itu.

### Bug di sumber lain yang kita periksa tidak ada di kita

Sumber-sumber itu berbagi satu bug transkripsi: seed tertukar,
`minima = max[1]` dan `maxima = min[1]`, muncul di tiga file termasuk port
Python MIT-nya.

Kode kita **bebas dari kelas bug itu secara konstruksi**: `app/detect/structure.py`
`swings()` tidak punya variabel seed sama sekali, ia membandingkan `high[i]`
langsung terhadap window kiri dan kanannya, dan pemutus serinya eksplisit -
maksimum ketat di kiri, tidak terlampaui di kanan.

## 9. Benchmark: di mana kita berdiri

Dibandingkan dengan LuxAlgo Price Action Concepts, suite komunitas TradingView,
TradeZella, TrendSpider, delapan platform order flow, pustaka open source
terbesar, dan gelombang produk "AI chart analysis".

### Yang mereka punya dan kita tidak, dan itu nyata

Alert dengan webhook adalah celah tunggal terbesar - LuxAlgo mengapalkan builder
sekuens sembilan langkah dengan All/Invalidate/OR, dan itu palangnya. Lalu bar
replay, screener, multi-chart tersinkron simbol (prasyarat supaya SSMT bisa
**dibaca**, bukan cuma dihitung), builder spread sintetis, matriks korelasi,
alat gambar manual, cloud dan mobile, mesin backtest, sisi kanan jurnal, **equal
high dan equal low**, OTE, dua killzone yang belum ada, dan Silver Bullet.

### Yang mereka punya dan sengaja tidak kita ambil

Volume profile dan POC: sudah komoditas, dan changelog salah satu vendornya
sendiri menunjukkan levelnya bergerak saat reload - jadi ia **tidak bisa memenuhi
invariant anti-repaint kita**. Order flow, footprint dan DOM: produk yang berbeda,
terkunci feed, dan vendornya sendiri mengakui hasilnya tidak reproducible.

### Yang ternyata kemasan, bukan kemampuan

"AI chart analysis": tidak ada satu pun anggota kelompok itu menerbitkan akurasi
terhadap korpus berlabel, dan satu di antaranya mengiklankan "82,5 persen akurasi
atas 11.220 chart" terhadap acuan yang tidak mungkin ada.

Skor confluence dan sentimen: **Zonelab pernah membangunnya, mengukur AUC 0,46
sampai 0,48 - yaitu perankingan terbalik - dan menghapusnya.** Tidak ada
kompetitor yang mengukur milik mereka.

Dan "non-repainting" sebagai butir pemasaran. Klaimnya sudah diambil semua orang;
artefaknya kosong.

### Kalimatnya sudah ditempati, buktinya tidak

Ini temuan paling berguna dari seluruh survei: **tidak ada satu pun dalam set itu
mengapalkan verifikasi yang bisa dijalankan ulang.**

| Sumber | Kata-katanya sendiri |
|---|---|
| LuxAlgo FAQ | "Nothing in our premium algo suites repaints" |
| LuxAlgo halaman produk | "some constructions are inherently retrospective: swing high/low labels, equal highs/lows, and liquidity trendlines" |
| Sierra Chart | "the most recent Swing High or Swing Low could change as the latest bar in the chart changes" |
| Bookmap | "SI indicators may become unpredictable (lose detections, show fake detections)" |
| TrendSpider | "a Chart Pattern which used to be there might go away" |
| Dokumentasi Pine TradingView | dengan `lookahead_off` default, "On realtime bars, it returns current unconfirmed values regardless of the lookahead setting" |

Bar Replay TradingView sendiri punya cacat lookahead yang cukup serius sampai
komunitasnya mengapalkan **dua** skrip penambal.

### TradeZella: klaimnya benar, isinya tidak diungkap

Daftar objeknya nyata dan merupakan **superset** milik kita - termasuk equal
high/low, mitigation block, OTE dan SMT. Tetapi tidak ada ambang yang diumumkan,
tidak ada pernyataan close-confirmed lawan intrabar, tidak ada logika fill, tidak
ada model biaya.

Pemasarannya bertentangan dengan dokumennya sendiri: "Tick-level accuracy...
actual historical bid/ask data... No future data leakage" berhadapan dengan
resolusi minimum **1 detik** yang terdokumentasi, pada **CFD Dukascopy dan bukan
broker Anda**.

Dan temuan terburuk dalam survei ini: **"Smooth Candles... automatically fills in
gaps in your chart data"**, metodenya tidak diungkap. Harga sintetis disuntikkan
diam-diam ke dalam sebuah backtest. Itu persis yang ditolak `app/resample.py`
aturan ketiga dengan menyebut namanya. Backtest-nya juga tidak memodelkan spread,
komisi, slippage maupun swap, sementara pemasarannya berbunyi "Prove your edge
before risking a dollar."

### Yang kita punya dan mereka tidak

Anti-repaint yang dibuktikan tes bar demi bar yang bisa dijalankan. Pra-registrasi
dengan dua belas hipotesis arah yang gagal dan diterbitkan. Mengukur artefak yang
benar-benar dikapalkan lalu menerbitkan kerugiannya. Pemilihan ambang secara buta
di mana separasi out-of-sample justru **melebihi** in-sample. Biaya dalam basis
point dari satu tabel yang dibaca produk dan harness sekaligus. Walk-forward
dengan purging yang melaporkan kegagalan 4 dari 8 fold-nya. SSMT dengan grid yang
**ditolak** kalau tidak selaras, dan laju divergensi terukur per pasangan -
sementara skrip SMT arus utama memasukkan DXY ke tiga triad default dan tidak
menerbitkan base rate apa pun.

Ditambah satu yang baru hari ini: korelasi log-return terukur per pasangan, dua
window, dengan tanda yang dilaporkan dan tidak dinilai.

Dan invariant produk yang tidak dimiliki siapa pun: **"tidak menemukan apa-apa"
dan "menyaring habis semuanya" tidak boleh terlihat sama.**

### Yang diadopsi, ditunda, dan ditolak

Kandidat teratas yang murah dan terukur: **equal high dan equal low**, dan Pine
memberi konstantanya sekaligus peringatannya - `0.1 x ATR(200)` di satu sumber,
lawan `0.01 x (tinggi-rendah seluruh data)` di sumber lain. Yang kedua **berubah
kalau pembaca memuat lebih banyak bar**, yaitu ketergantungan prefiks yang tidak
akan pernah kita kapalkan.

Ditunda dengan alasan, bukan dilupakan: alert dengan webhook, bar replay,
multi-chart tersinkron, matriks korelasi sebagai tampilan tersendiri, OTE.

Ditolak: geometri box baru (lima detektor sudah memakai 31,6 persen ink chart,
dan dua varian geometri yang ada terukur **negatif** signifikan), volume profile,
order flow, skor confluence, dan eksekusi order.

Satu saran yang **tidak** diambil: mengganti nama `imbalance.py` karena di delapan
platform order flow kata itu berarti rasio bid/ask footprint. Itu keberatan
posisi, bukan kebenaran, dan `imbalance` adalah nama blok param yang menghadap
pengguna - menggantinya adalah perubahan API yang memecahkan klien demi
menghindari salah paham yang bisa diselesaikan satu kalimat dokumentasi.

## 10. Uji visual: apa yang hanya bisa ditemukan dengan melihat

`e2e/chart-audit.mjs` menggambar chart, memotret kanvasnya, dan menyerahkan
gambarnya beserta daftar bentuk yang benar-benar dikirim mesin ke sebuah model
yang boleh melihat dan boleh menjelaskan, tetapi **tidak boleh menambah angka**.
Gate grounding menolak balasan yang memuat angka yang tidak diproduksi mesin.

Harness ini menemukan tiga hal yang tidak bisa ditemukan cara lain, karena setiap
asersi piksel di suite ini memeriksa di mana sebuah **box** berada, dan
ketiganya soal di mana **namanya** berada.

### Harness-nya sendiri mati sebelum bisa berguna

`FileNotFoundError` menyebut file yang baru saja ia tulis. Screenshot ditulis
relatif terhadap cwd harness (`frontend`), lalu diserahkan ke `app.llm` yang
di-spawn dengan `cwd: backend` - jadi `.playwright-shots/chart-audit-...png`
diselesaikan terhadap direktori backend, di mana tidak ada apa pun bernama itu.
Ia menggambar chart, mendaftar empat zona, menulis kedua file, mencetak
path-nya, lalu mati. Path-nya sekarang di-resolve jadi absolut karena ia
menyeberangi batas proses.

### Caption zona terpotong di edge kanan

Klemnya hanya ada di kiri, `Math.max(..., 0)`, dan tidak ada apa pun yang menahan
ujung kanan. Sebuah caption di box dekat edge kanan berlari keluar plot masuk ke
skala harga dan kehilangan karakter terakhirnya - `RBR unsettled` tampil sebagai
`RBR unsettle`, yang terbaca seperti kata yang salah tulis, bukan plate yang tidak
cukup ruang. Sekarang plate-nya digeser ke kiri agar pas, bukan teksnya
dipotong, dan ia berhenti di `LABEL_GUTTER` yang sama yang dijaga setiap primitive
lain.

### Caption menimpa logo, dan klaimnya salah dua kali

Tanda atribusi library itu anchor DOM yang duduk **di atas** kanvas, jadi ia menang
di setiap tumpang tindih dan tidak ada apa pun di renderer yang bisa melihatnya.
Cycle grid mengklaim persegi itu di peta label bersama supaya caption tidak
mendarat di sana. Klaim itu salah dua kali:

1. **Satuannya.** `claimedLabels` seluruhnya piksel bitmap - plate zona dibangun di
   `box.left * kx`, tag level di `bitmapSize.width - LABEL_GUTTER * kx` - dan satu
   entri ini didorong dalam piksel CSS, dibagi `ky` di suku y dan tidak diskalakan
   di tiga suku lainnya. Pada devicePixelRatio 1 kedua ruang berimpit dan klaimnya
   benar secara kebetulan; pada 2 ia menutupi CSS 6 sampai 25,5 dari tanda yang
   membentang 10 sampai 45, **kurang dari separuhnya**.
2. **Tandanya tidak rata dasar**, yang justru diklaim komentar lamanya. Ia duduk 10
   piksel CSS di atas dasar kanvas, jadi persegi yang dijangkarkan ke dasar juga
   melewatkannya ke arah atas.

Diukur di browser, di lima viewport dan dua pixel ratio, karena konstanta library
yang bergerak mengikuti pane akan membuat semua ini sia-sia:

| Viewport | Kanvas | x | w | h | Jarak dasar |
|---|---|---|---|---|---|
| 1600x900@1 | 950x768 | 10 | 35 | 19 | 10 |
| 1600x900@2 | 950x768 | 10 | 35 | 19 | 10 |
| 1280x720@1 | 630x562 | 10 | 35 | 19 | 10 |
| 1920x1200@1 | 1270x1078 | 10 | 35 | 19 | 10 |
| 1024x768@1 | 474x552 | 10 | 35 | 19 | 10 |

Identik di kelimanya, jadi itu konstanta tetap tata letak library-nya.

`e2e/labels.mjs` sekarang memeriksanya **terhadap DOM**, bukan terhadap
konstantanya, supaya asersinya gagal kalau library memindahkan tandanya sendiri -
kasus yang tidak bisa dilindungi komentar apa pun. Dibuktikan tidak kosong:
mengembalikan bug jarak-dasar membuat harness turun dari 9/9 ke 7/9 dengan
menyebut tanda dan jumlah klaimnya.

### Yang dilaporkan audit dan BUKAN cacat

Dua hal, dan membedakannya penting supaya laporan visual tetap bisa dipercaya:

- **Zona terbawah terpotong dasar pane.** Itu memang zona di luar rentang harga di
  layar, dan aplikasinya sudah mengatakannya sendiri di banner: "1 of 7 drawn
  zones are outside the price range on screen". Diumumkan, bukan disembunyikan.
- **Garis proximal tidak terlihat terpisah.** Untuk kelima zona itu proximal sama
  dengan top-nya, karena untuk zona demand proximal **memang** top-nya. Itu
  aritmetika, bukan cacat gambar. Yang keliru adalah legendanya, yang menjanjikan
  "garis lebih terang di dalam box" - kalimat itu benar hanya ketika zonanya
  sudah diperhalus atau ketika sisinya supply.

Dan satu keterbatasan gate-nya sendiri: model membaca "12:00" dari sumbu waktu,
lalu gate grounding menghitungnya sebagai angka yang tidak diproduksi mesin dan
menandai balasan itu UNUSABLE. Itu positif palsu pada **waktu** yang terbaca dari
sumbu, bukan pada harga. Gate-nya tetap benar arahnya: lebih baik menolak
balasan yang sah daripada meloloskan angka karangan.

## 11. Keadaan akhir, terukur

Semua angka di bawah dari jalan terakhir pada 20 Agustus 2026, bukan dari ingatan
tentang jalan sebelumnya.

| Gate | Hasil |
|---|---|
| pytest | 584 lulus |
| pyright, cakupan `app/` | 0 error, 0 warning |
| pyflakes atas `app`, `tools`, `tests` | 0 |
| `npm run check` | keluar 0 |
| Build produksi Next | keluar 0 |
| `tools.validate_api` | 120/120 |
| `tools.stress` | tanpa error, setiap permintaan 200 |
| `e2e` sweep | 148/148 |
| `e2e:clicks` | 195/195 |
| `e2e:wiring` | 63/63 |
| `e2e:labels` | 9/9, stabil pada tiga jalan berturut |
| `e2e:clock` | 42/42 |
| `e2e:ribbon` | 8/8 |
| `e2e:pixels` | 6/6 |
| `e2e:viewports` | 25/25 |
| `e2e:offscreen` | 3/3 |
| `e2e:resilience` | 12/12 |
| `e2e:chart` | jalan bersih, audit visual terbaca |
| `e2e:zones` | keluar 0 |

Tiga gate baru ditambahkan pada sesi ini, dan **ketiganya dibuktikan tidak
kosong** dengan cara menyuntikkan kembali cacat yang mereka tulis untuk ditangkap:

| Gate baru | Menangkap |
|---|---|
| `test_a_weekly_bucket_opens_on_sunday_not_on_the_epochs_thursday` | anchor mingguan yang salah fase |
| `test_a_projected_higher_timeframe_box_never_moves` | repaint box HTF, lima detektor |
| `test_every_level_name_fits_the_canvas_label_column` | nama level yang terpotong sunyi |
| `test_no_string_literal_looks_like_an_f_string_that_lost_its_prefix` | f-string yang kehilangan awalannya |
| `e2e/labels.mjs`, klaim persegi logo | caption yang bisa mendarat di atas tanda atribusi |
| `test_an_equal_high_shelf_never_moves` | toleransi yang bergantung jumlah bar dimuat |
| `test_a_lower_high_in_between_does_not_break_the_shelf` | pengelompokan berbasis run yang melewatkan sebagian besar rak |

### Apa yang masih terbuka, dinyatakan bukan disembunyikan

1. Alert dengan webhook, bar replay, multi-chart tersinkron simbol, OTE - ditunda
   dengan alasan di bagian 9. Alert adalah celah tunggal terbesar lawan
   kompetitor.
2. Konkurensi praktis terserialisasi, sekitar 4 permintaan per detik untuk draw
   terberat. Cukup untuk satu pengguna dengan margin besar; itu plafonnya untuk
   banyak pengguna.
3. Server web mengikat ke `0.0.0.0`. Untuk produksi ia perlu berada di belakang
   proksi.
4. Toleransi equal high `0.1 x ATR` diadopsi dengan asal-usulnya, **bukan diukur**.
   Tidak ada di sini yang menguji apakah 0,1 memisahkan rak yang berarti dari yang tidak,
   dan `EQUAL_LOOKBACK = 10` juga pilihan tanpa sumber. Keduanya punya slider dan
   keduanya dinyatakan sebagai pilihan di tempatnya.
5. Objek referensi yang masih absen dan **sudah ditimbang**: `tCISD` (penolakan
   tertulis di `cisd.py`), Inducement High (penolakan tertulis di `liquidity.py`),
   failure-swing hollow triangle, `Psp`, Silver Bullet window, tabel
   `EV/Top/Bot/Dist`, dan tata letak triad tiga panel - yang terakhir bentuk
   produk, bukan layer.

### Yang selesai sejak tabel ini pertama ditulis

Empat item yang tadinya di daftar terbuka sudah ditutup dalam sesi yang sama:
equal high dan equal low dibangun (bagian 13), legibilitas siklus hidup diukur dan
kalimatnya dibetulkan (bagian 12), label berimpit digabung alih-alih dibuang
(bagian 14), dan kalimat legenda soal garis proximal dibetulkan di kedua brief
harness - `chart-audit.mjs` dan `visual-audit.mjs` - karena di situlah ia hidup,
bukan di UI produk. Proximal **selalu** edge box: top untuk demand, bottom untuk
supply, per `supply_demand.py:401`. Menyuruh auditor mencari garis di dalam box
membuatnya melaporkan garis hilang pada lima chart yang benar.

## 12. Siklus hidup zona: auditor benar, kalimatnya salah

Audit visual melaporkan ia tidak bisa membedakan box mitigated dari box fresh
dengan mata, padahal legendanya menjanjikan opasitas isian yang menyandikan
kesegaran. Daripada memperdebatkannya, kedua kanal diukur terhadap latar `--bg`
`#0b0d10`.

**Isian**, pada `--zone-fill-near` 0,16 dikali tabel `LIFECYCLE`:

| Perbandingan | Demand | Supply |
|---|---|---|
| fresh lawan tested | 1,064:1 | 1,103:1 |
| tested lawan mitigated | 1,046:1 | 1,072:1 |
| mitigated lawan broken | 1,028:1 | 1,042:1 |
| fresh lawan broken, tiga langkah | **1,144:1** | 1,232:1 |

**Border**, pada tabel `EDGE_ALPHA`:

| Perbandingan | Demand | Supply |
|---|---|---|
| fresh lawan tested | 1,62:1 | 1,82:1 |
| tested lawan mitigated | 1,48:1 | 1,70:1 |
| mitigated lawan broken | 1,33:1 | 1,54:1 |
| fresh lawan broken | **3,20:1** | 4,75:1 |

Dua puluh sampai enam puluh kali lebih terpisah. Jadi sinyalnya nyata dan ia ada
**di garis edge, bukan di isian** - dan komentar di `zone-primitive.ts` menyatakan
isian selama ini.

Yang diperbaiki adalah kalimatnya, bukan pikselnya. Isian memang bertugas
mengatakan "ada level di sini" pada pandangan sekilas dan ia melakukan itu; yang
salah adalah menyuruh pembaca membaca siklus hidup dari sana. Anggaran ink juga
sudah terukur dan terbatas - mengisi setiap box mengecat 57,9 persen pane pada
15m - jadi menaikkan alpha isian untuk memperbesar separasi akan membayar dengan
hal yang sudah diukur mahal.

> [!NOTE]
> Ini contoh terbaik dari kenapa uji visual ada di suite ini. Tidak ada asersi
> piksel yang bisa menemukannya, karena semua asersi piksel memeriksa apakah
> sebuah box ada **di tempat yang benar**, dan ini soal apakah pembaca bisa
> **membedakan** dua box yang keduanya di tempat yang benar. Auditor membaca
> legenda, melihat isiannya, dan melaporkan ketidaksesuaiannya. Ia benar.

## 13. Equal high dan equal low, dibangun

Ini kandidat adopsi teratas dari benchmark, dan alasannya lebih kuat dari sekadar
kompetitor punya: **checklist kita sendiri sudah mengutip aturan tentangnya.**
Di `app/models/cycle.py` ada kutipan praktisi, "FVG/OB/REQL/REQH/CISD semuanya
harus dalam premium kalo mau sell, harus dalam discount kalo mau buy" - jadi mesin
menyebut REQL dan REQH sebagai syarat sementara tidak ada apa pun yang
menggambarnya.

Sekarang toggle `Equal highs and lows` di layer Named levels menggambarnya sebagai
`REQH 3x` dan `REQL 2x`, dengan hitungan sentuhannya.

### Toleransinya, dan versi yang ditolak

Survei open source menemukan tepat dua aturan yang beredar:

| Aturan | Sifatnya |
|---|---|
| `0.1 x ATR(200)` | bebas skala, ikut volatilitas |
| `0.01 x (tinggi - rendah seluruh data)` | fraksi **window yang dimuat** |

Yang kedua tidak bisa dikapalkan di sini, dan bukan karena rata-ratanya salah: ia
membuat toleransinya jadi fungsi dari **berapa bar yang kebetulan dimuat pembaca**.
Ubah picker Bars dari 500 ke 5000 dan dua swing yang sama berhenti jadi setara,
atau mulai jadi setara, tanpa satu candle pun bergerak. Kedua chart tetap terlihat
benar.

Itu bukan argumen, itu terukur: menukar toleransinya ke aturan kedua membuat
`test_an_equal_high_shelf_never_moves` **gagal** dengan menyebut rak mana yang
bergerak. Jadi pilihan ATR terbukti bebas-prefiks, bukan cuma diyakini.

### Satu cacat desain saya sendiri, dibuktikan sebelum diperbaiki

Versi pertama mengelompokkan swing yang **berurutan** dan memutus deretnya begitu
satu jatuh di luar band. Itu melewatkan kasus paling biasa: high di 100,00, lalu
high **lebih rendah** di 95,00, lalu 100,05. Pembaca melihat satu rak dua sentuhan
di 100 dan akan bertindak atasnya.

Diuji pada seri buatan sebelum ditulis ulang: versi itu menemukan **nol**. Pada
3000 bar emas nyata, versi run menemukan 4 rak sementara versi klaster menemukan
**20**, jadi ia melewatkan sebagian besarnya.

Sekarang ia mengelompokkan berdasarkan harga, bukan kedekatan urutan, dengan batas
`EQUAL_LOOKBACK = 10` swing sesisi - dan batas itu dinyatakan sebagai pilihan,
karena tidak ada sumber yang menerbitkannya. Tanpa batas, level yang dikunjungi
setahun kemudian ikut bergabung: geometrinya tetap diam jadi bukan repaint, tetapi
hitungan sentuhannya berhenti menggambarkan likuiditas dan mulai menggambarkan
berapa banyak riwayat yang dimuat pembaca.

### Yang membuatnya tidak repaint

Harganya dijangkarkan ke anggota **pertama**, bukan ke rata-rata berjalan. Sebuah
rata-rata bergerak setiap kali swing lain bergabung, dan itu garis yang menggeser
diri di bawah pembaca. Band-nya memakai ATR **anchor**, bukan ATR swing yang
bergabung, jadi sebuah pasangan dinilai sama kapan pun ia dievaluasi.

Yang boleh berubah hanya hitungan sentuhan dan `taken_at`, keduanya hanya maju -
aturan yang sama dengan siklus hidup zona.

### Lebar fraktal adalah yang menentukan berapa banyak terlihat

Diambil dari layer Market structure, bukan knob kedua, supaya sebuah rak tidak
bisa duduk di antara dua swing yang overlay itu sendiri tidak anggap swing.
Konsekuensinya perlu dinyatakan, karena satu garis meredup di setelan bawaan
terbaca seperti layer rusak. Terukur pada 2000 bar emas 15m:

| `swing_n` | Rak | Masih berdiri |
|---|---|---|
| 3 | 53 | 5 |
| 5 | 25 | 3 |
| 10 | 12 | 3 |
| 20 | 4 | 1 |
| 50 (bawaan) | 1 | 0 |

Angka itu sekarang ada di panelnya, jadi pembaca tahu yang jarang itu fraktalnya
yang kasar, bukan mesinnya yang mati.

### Apa yang tidak diklaim

Tidak ada yang diukur terhadap hasil. Ini kesetiaan pada metode, pijakan yang sama
dengan overlay struktur: metodenya membaca rak seperti ini, jadi chart yang tidak
bisa menunjukkannya tidak bisa menunjukkan metodenya. Tidak ada arah, dan tidak ada
field skor untuk disalahbaca sebagai arah.

## 14. Label level yang berimpit: dibuang, bukan ditumpuk

Referensi menggabungkan level yang berimpit jadi satu label dengan garis miring.
Saya menduga kita menumpuknya. Diperiksa di kode: kita **membuangnya**. Kalau
persegi label kalah di peta tabrakan, labelnya tidak digambar sama sekali -
garisnya tetap digambar.

Di file yang docstring-nya sendiri berkata "label adalah satu-satunya yang
menandai objek-objek ini", itu meninggalkan ray yang tidak bisa diidentifikasi
pembaca. Dan sebuah ray tanpa nama tidak bisa dibedakan dari ray yang seharusnya
tidak ada di situ - invariant yang sama yang dijaga seluruh mesin ini.

Sekarang nama yang berimpit digabung: `PDL/PDH` kalau keduanya muat, `PDH+2` kalau
tidak. Satu baris ink untuk dua fakta, dan tidak ada nama yang hilang.

### Dua kesalahan saya sendiri di sini, ditemukan dengan melihat

**Anggaran yang salah.** Saya memberi fungsi penggabungnya `gutter - 4 * kx`, yang
adalah lebar seluruh chart sampai kolom label, bukan lebar kolomnya - beberapa
ratus piksel alih-alih empat puluh. Jadi penggabungannya menerima nama yang jauh
terlalu lebar dan edge kanvas memotongnya di tengah kata: `RNG H/PD`, `PDH/MON`,
`AS L/RNG`. Ketahuan dari screenshot, bukan dari tes.

**Dan aritmetika gate saya sendiri salah satu karakter.** Persegi klaimnya
`{x: gutter, w: measureText(tag) + pad}` dan harus muat di dalam `LABEL_GUTTER`,
jadi teksnya boleh memakai `46 - 4 = 42` piksel, yaitu **7** karakter pada font
5,5 piksel per karakter. Tes Python saya memakai `pad / 2` alih-alih `pad`, jadi
ia menghitung anggaran **8** - dan nama 8 karakter mengukur 44 piksel terhadap
jatah 42, menghasilkan persegi yang berakhir 2 piksel di luar pane.

`e2e/labels.mjs` menangkapnya sebagai klaim yang dipotong edge, turun dari 9/9 ke
8/9. Semua nama yang dikapalkan panjangnya 7 atau kurang, jadi tidak ada yang
perlu diganti nama - gate-nya cuma sedang meloloskan yang berikutnya.

Sekarang `pad` adalah satu konstanta bernama di sisi TypeScript, dipakai oleh
persegi maupun anggaran penggabungan, dan sisi Python membaca `LABEL_GUTTER`
langsung dari sumbernya. Dua sisi, satu angka, tidak bisa berpisah.

> [!NOTE]
> Ini kesalahan kedua dalam sesi ini yang bentuknya sama: sebuah konstanta yang
> hidup di dua tempat. Yang pertama ambang premium dan discount, di tiga tempat.
> Pola perbaikannya juga sama, dan sekarang tertulis dua kali supaya tidak
> terulang ketiga.

### Dan yang gagal ternyata edge BAWAH, bukan kanan

Harness label tetap gagal sesudah anggarannya dibetulkan, dengan klaim yang sama:
`{x: 984, w: 42.49}`. Saya menghabiskan beberapa putaran menduga itu edge kanan -
menduga pane menyusut, menduga repaint yang tidak terjadi, menduga `paneSize`
berbeda dari kanvas. Semuanya salah, dan cara menyelesaikannya adalah berhenti
menduga: harness-nya diinstrumentasi untuk mencetak **klausa mana** yang menyala.

```
DIAG pane=1030x724 widest canvas=1104
DIAG straddles bottom :: {"x":984,"y":723.5,"w":42.49,"h":12}
```

Edge **bawah**. Sebuah level yang harganya jatuh dalam setengah baris dari dasar
pane menggambar namanya separuh di bawahnya. Klem horizontal sudah ada di file
itu sejak lama; klem vertikalnya tidak.

Sekarang labelnya yang bergeser, bukan garisnya - nama yang duduk setengah baris di
atas ray-nya masih menamai ray itu, sementara nama yang dipotong pane tidak
menamai apa pun. Pertukaran yang sama yang sudah dipakai caption zona ketika
box-nya mulai di luar layar sebelah kiri. Diverifikasi stabil: 9/9 pada tiga
jalan berturut-turut.

> [!TIP]
> Pelajaran prosesnya lebih berguna daripada perbaikannya. Saya punya nomor baris
> predikatnya sejak awal dan tetap menduga selama empat putaran. Mencetak klausa
> mana yang menyala butuh satu menit dan langsung menjawabnya.

## 15. Cleanup, dan satu repaint yang ditemukan saat merapikan

Diminta merapikan. Yang benar-benar sampah ternyata sedikit, dan dua kandidat
besar yang tampak sampah justru **bukti** yang tidak boleh disentuh.

### Yang dihapus

| Apa | Kenapa |
|---|---|
| `backend/app/routes/` | direktori kosong, tidak dilacak git, tidak diimpor apa pun - dan ia memberi sinyal palsu bahwa endpoint hidup di situ padahal semuanya di `main.py` |
| 22 screenshot probe sekali-pakai | tidak dikutip apa pun dan tidak ada harness yang menulisnya ulang |
| 49 `zone-*.png` plus `tqo.png` | output skema penamaan lama; `visual-audit.mjs` sekarang menulis ke `visual/` dengan 102 file |

Direktori screenshot turun 23 MB ke 16 MB, dan yang tersisa hanya output
harness plus dua set `*-before/` yang dikutip.

### Dua hal yang TIDAK dihapus, dan pemeriksaan yang menyelamatkannya

**Tujuh tool tampak tak terpakai.** Grep untuk `tools.<nama>` di seluruh kode
melaporkan `alignment`, `base_quality`, `continuation`, `drift_gate_impact`,
`inversion`, `structure_bias` dan `true_day_open` sebagai tak tereferensi. Itu tes
yang salah: tool pengukuran dipanggil **manusia**, bukan kode. Lima di antaranya
menghasilkan file bukti yang diterbitkan, dan `base_quality.py` adalah asal-usul
`base_drift` serta `base_overlap` - dua field yang dikirim di **setiap** zona.
Tidak ada yang dihapus.

**`colour-before/` dan `pixel-before/` dikutip di tiga primitive** sebagai keadaan
yang memotivasi sebuah perubahan. Keduanya bukti, bukan sampah.

Pola yang sama dua kali: sebuah grep yang mudah dijalankan menghasilkan daftar
yang tampak seperti temuan, dan bertindak atasnya akan memutus provenance klaim
yang sudah diterbitkan.

### Ditambahkan: peta direktori docs

27 file di `docs/` tanpa indeks. [docs/README.md](README.md) sekarang memetakan
enam dokumen prosa ke pertanyaan yang dijawabnya, dan ke-21 file bukti ke tool
yang menghasilkannya. Diperiksa: **semuanya punya tool yang cocok**, tidak ada yang
orphan, dan tanda hubung lawan garis bawah cuma artefak sejarah.

Ditambahkan juga daftar isi di dokumen ini, dan setiap tautan internal di kedua
dokumen diverifikasi resolve dengan menurunkan anchor dari headingnya seperti
GitHub - 14 tautan di sini, 15 di README akar, nol rusak.

### Dan satu repaint nyata, ditemukan karena suite dijalankan ulang

`test_an_opening_gap_and_its_stack_never_move` mulai gagal, konsisten, pada arah
**tumbuh ke kiri** - arah yang docstring file itu sebut sebagai tempat setiap
cacat sebelumnya hidup. Sebuah NWOG bergerak.

Diukur, dan mesinnya ternyata **benar**: `top`, `bottom` dan `ce` identik di setiap
window. Yang berubah cuma `approximate`, False jadi True pada satu window yang
bar pertamanya justru bar penutup gap itu sendiri. Kalau bar penutup adalah bar
pertama, tidak ada apa pun sebelumnya yang membuktikan sesi benar-benar berjalan
sampai ke situ, jadi edge-nya adalah harga terbaik yang bisa ditawarkan feed dan
bukan harga terakhir yang benar-benar berdagang. Itu persis yang dikatakan
`approximate`.

Jadi invariant yang jujur **berarah**, dan arahnya diukur sebelum diizinkan:

| Atas 261 gap dan delapan window | Kejadian |
|---|---|
| harga atau midpoint bergerak | 0 |
| melunak dengan riwayat lebih sedikit (boleh) | 1 |
| mengklaim EKSAK dengan riwayat lebih sedikit (dilarang) | **0** |

Arah yang berbahaya adalah yang terakhir: pita digambar presisi di window pendek
lalu dilunakkan ketika bar bertambah berarti klaim keyakinan yang **menyusut** di
bawah pembaca. Itu tidak pernah terjadi, dan tesnya sekarang gagal kalau mulai
terjadi, sambil berhenti gagal pada kehati-hatian. Dibuktikan tidak kosong dengan
membalik penjaganya.

> [!CAUTION]
> Tes yang gagal bukan otomatis kode yang salah. Yang salah di sini adalah tesnya,
> karena ia membekukan sebuah flag keyakinan seolah ia geometri. Tetapi
> membetulkannya hanya sah **setelah** mengukur bahwa arah yang berbahaya tidak
> pernah terjadi - tanpa itu, saya cuma melemahkan gate supaya kegagalannya
> hilang.

## 16. Launcher sekali klik, dan insiden desktop

`start.ps1` diganti `start.bat` plus `stop.bat`, dobel-klik, tanpa PowerShell.

### Kenapa .bat, dan ini terukur bukan selera

| Perintah | Jawabannya di mesin ini |
|---|---|
| `assoc .ps1` | `File association not found for extension .ps1` |
| `assoc .bat` | `.bat=batfile` |

Sebuah `.ps1` **tidak bisa** dijalankan dengan dobel-klik; ia hanya membuka dialog
"Open with". Jadi untuk syarat "sekali klik", `.ps1` gagal secara desain, bukan
karena preferensi.

PowerShell tetap **bahasa** yang lebih baik untuk pekerjaan ini:
`Get-NetTCPConnection` memberi PID socket owner sebagai objek alih-alih teks
`netstat` yang harus diurai, dan penanganan errornya sungguhan. Tetapi ia bukan
launcher. Dan dokumentasi Microsoft menambah satu alasan lagi: kalau tidak ada
execution policy yang diset di scope mana pun, policy efektif di klien Windows
adalah **Restricted**, yang *"prevents running of all script files"*. Di mesin
ini `CurrentUser` sudah `RemoteSigned` jadi tidak kena, tetapi mesin baru bisa.

### Satu window, bukan dua

Versi pertama membuka satu console per server. Itu lebih sulit dibaca, bukan lebih
mudah: dua window untuk dicari, dan begitu satu permintaan menyentuh keduanya,
pembaca menelusuri dua log berdampingan untuk mengikuti satu peristiwa. Sekarang
`start /b` menahan kedua anak di console yang sama, jadi kedua log mendarat di satu
tempat dalam urutan kejadiannya.

### INSIDEN: stop.bat mematikan desktop pengguna

Ini kesalahan saya, dan ia sampai ke pengguna.

`stop.bat` menutup window launcher dengan
`taskkill /F /FI "WINDOWTITLE eq Zonelab*"`. Sebuah window File Explorer mengambil
judulnya dari **folder yang sedang ia tampilkan** - dan siapa pun yang menjalankan
file ini, menurut definisi, sedang berada di folder Zonelab. Jadi ada window
berjudul `Zonelab - File Explorer`, wildcard-nya mencocokkannya, dan `/F`
mengakhiri `explorer.exe`. Desktop, taskbar, dan setiap folder yang terbuka ikut
hilang.

Diukur sesudahnya: `Get-Process explorer` mengembalikan **0**.

Dibuktikan sebagai penyebabnya, bukan diduga:

```
-- filter LAMA, judul saja --
explorer.exe    21376 Console    3    235.804 K
-- filter BARU, cmd.exe DAN judul --
INFO: No tasks are running which match the specified criteria.
```

Perbaikannya dua filter yang harus keduanya cocok, sehingga hanya sebuah console
yang bisa terkena:

```bat
taskkill /F /FI "IMAGENAME eq cmd.exe" /FI "WINDOWTITLE eq Zonelab*"
```

Diverifikasi ujung ke ujung dengan jebakannya sengaja dipasang: window Explorer
di folder Zonelab dibiarkan terbuka, server dinyalakan, `stop.bat` dijalankan.
Sesudahnya explorer **2 proses dan window-nya masih terbuka**, nol proses server,
nol listener.

> [!CAUTION]
> **Judul window adalah label yang bisa dipakai siapa saja. Jangan pernah
> membunuh berdasarkan judul saja.** Itu pelajaran umumnya, dan biayanya adalah
> desktop seseorang.

### Risiko sisa yang ikut ditutup

Audit ulang seluruh baris yang membunuh menemukan satu lagi:
`Name='python.exe' and CommandLine like '%uvicorn%'` akan mengakhiri **uvicorn apa
pun** di mesin ini, termasuk API proyek lain. Kedua aturan sekarang mensyaratkan
`Zonelab` ada di command line juga. Tidak ada apa pun tentang file ini yang
memberinya hak menjangkau ke luar foldernya sendiri.

Dan aturan yang **tidak** dipakai, karena diuji baca-saja lebih dulu: "proses apa
pun yang command line-nya menyebut Zonelab" mencocokkan **empat belas** proses,
termasuk `WindowsTerminal.exe`, tiga `bash.exe`, dan `WMIC.exe` itu sendiri.
`wmic delete` atas filter itu akan menutup terminal tempat pengguna berdiri.

### Tiga cacat lain di file itu sendiri, ditemukan dengan menjalankannya

1. **`stop.bat` melaporkan menutup dua window padahal tidak ada yang jalan.**
   `taskkill /FI` keluar dengan kode **0** meski filternya tidak cocok apa pun,
   dan saya menyimpulkan dari kode keluar alih-alih memeriksa. Sekarang `tasklist`
   ditanya lebih dulu.
2. **Port dikirim dua kali.** `package.json` sudah berisi `next dev -p 3100` dan
   `start.bat` menambah `-- --port 3100`, menghasilkan
   `next dev -p 3100 --port 3100` di log. Dua ejaan untuk satu nilai.
3. **WQL lewat argumen `call` tidak bekerja.** `%%` di argumen batch diperluas di
   jalan masuk, jadi kueri yang diterima wmic bertanda `%` tunggal dan tidak
   cocok apa pun - ia mencetak nol sisa sementara verifikasi di bawahnya, yang
   klausanya inline, menghitung dua. Ditulis dua kali secara eksplisit sekarang.

Plus satu alarm palsu: verifikasi berlomba dengan OS. `taskkill /F` kembali begitu
kill disinyalkan, bukan setelah prosesnya hilang, jadi ia melaporkan "2 server
process(es) survived" pada jalan yang sebenarnya sudah bersih total. Alarm palsu
sama buruknya dengan lolos palsu, karena pembaca belajar mengabaikan barisnya.

### Duplikasi antar-jalan: diukur, nol

`start.bat` memanggil `stop.bat /q` lebih dulu, jadi ada **satu** implementasi
sweep yang dipakai keduanya - bukan dua salinan yang akan berpisah.

| Langkah | Proses server | Listener | API | Web |
|---|---|---|---|---|
| bersih | 0 | 0 | - | - |
| start #1 | 4 | 3 | 200 | 200 |
| start #2 | 4 | 3 | 200 | 200 |
| start #3 | 4 | 3 | 200 | 200 |
| start #4 | 4 | 3 | 200 | 200 |
| stop | **0** | **0** | mati | mati |

Empat kali start berturut tanpa stop di antaranya, dan angkanya identik setiap
kali. Komposisinya stabil: dua python (launcher uvicorn plus socket owner), satu
shim npm, satu server Next.

Audit sisa terakhir di seluruh mesin: **nol** proses python, nol proses menyebut
Zonelab atau uvicorn setelah shell yang mencocokkan dirinya sendiri dikecualikan,
nol build browser Playwright, dan `explorer.exe` hidup.

> [!NOTE]
> Kecualikan shell-nya. Audit pertama melaporkan "uvicorn anywhere: 14" dan
> "turbopack: 4" pada mesin yang benar-benar bersih, karena perintah PowerShell
> yang menghitung memuat kata-kata itu di command line-nya sendiri. Itu jebakan
> yang sama, ketiga kalinya dalam satu sesi.

### Lanjutan: flicker, dan tiga percobaan gagal untuk membereskannya

Pengguna melaporkan "terkadang ada proses cmd yang tiba-tiba muncul terus
hilang". Diukur, bukan didiagnosis dari deskripsi:

```
distinct cmd.exe seen in 20s: 15
   x12  C:\Windows\system32\cmd.exe /c ...\Zonelab\start.bat
```

**Dua belas `start.bat` yatim**, satu per uji coba yang saya jalankan, semuanya
terjebak di loop hold loop:

```bat
:hold
ping -n 3600 127.0.0.1 >nul
goto :hold
```

Loop itu **memunculkan `ping.exe` sungguhan setiap jam, per instance**. Terhitung
saat itu: 12 `ping.exe` hidup, satu per yatim, saling bergilir. Itu flicker-nya.

`ping` diganti `pause >nul`, sebuah perintah **internal** cmd yang tidak
memunculkan proses apa pun. Sesudahnya, dengan server jalan: `ping.exe` = 0.

Lalu tiga percobaan menutup celahnya, dan dua gagal dengan bentuk yang sama:

1. **Sapuan wmic untuk `cmd.exe` yang menyebut `start.bat`.** `call` tidak
   memunculkan proses baru, jadi ketika `start.bat` memanggil `stop.bat /q`,
   sweep itu berjalan **di dalam** cmd.exe yang command line-nya memuat
   `start.bat`. Ia membunuh `start.bat` di tengah pembersihannya sendiri,
   sebelum satu server pun menyala.
2. **Digerbangi `/q`.** Itu memperbaiki nomor 1 dan membuka nomor 2: proses
   **wrapper** yang menjalankan uji yang memanggil `stop.bat` juga menyebut
   `start.bat` di command line-nya. Mesin yang benar-benar bersih melaporkan
   "Stopping a start.bat launcher" lalu "something is STILL running".
3. **Dibuang.** `:bytitle` dengan dua filter, `IMAGENAME eq cmd.exe` **dan**
   judulnya, sudah menangani kasus nyata dengan presisi. Yang tidak tercakup
   adalah `start.bat` yang diluncurkan skrip lain, dan itu pola pengujian saya,
   bukan cara siapa pun memakainya.

Ditambah satu suntingan saya yang **merusak file-nya**: `s.index(":freeport")`
menemukan **call site**-nya, bukan definisi labelnya, jadi blok baru tersisip di
tengah dan menghapus kata `call`. Ketahuan dari `grep -n "^call :\|^:[a-z]"` yang
menampilkan `:freeport %API_PORT% "API"` tanpa `call`.

### Siklus akhir, terukur

| Langkah | Server | `ping.exe` | API | Web | Warning di log |
|---|---|---|---|---|---|
| bersih | 0 | 0 | - | - | - |
| start #1 | 4 | **0** | 200 | 200 | 0 |
| start #2 | 4 | **0** | 200 | 200 | 0 |
| start #3 | 4 | **0** | 200 | 200 | 0 |
| stop | **0** | **0** | mati | mati | - |
| stop lagi | 0 | 0 | - | - | "Nothing was running" |

> [!CAUTION]
> Empat kali dalam satu sesi sebuah filter mencocokkan perintah yang sedang
> memfilter. Dua kali itu cuma alarm palsu; sekali itu hampir membunuh
> `start.bat` sendiri; dan sekali - lewat judul window - benar-benar menutup
> desktop pengguna. **Sebelum mempercayai hitungan proses, kecualikan shell-nya
> lebih dulu.**

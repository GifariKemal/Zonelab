# Gerbang departure breaker block, diukur 6 September 2026

Detector keempat lewat rig yang sama, dan yang terakhir yang masih memakai
ambang yang tidak pernah diukur untuknya. Tiga commit terakhir menyebut lantai
2,0 milik BRK sebagai satu-satunya yang tersisa. Dokumen ini menutupnya.

> [!NOTE]
> **Breaker BUKAN teknik breakout**, dan registry ini memisahkan keduanya
> secara eksplisit. Layer `wyckoff` yang membawa note "This is also the
> BREAKOUT layer". Breaker adalah objek INVERSI: break-nya cuma melahirkan
> kotaknya, dan trade-nya terjadi saat harga KEMBALI ke kotak yang sudah
> berbalik peran. Breakout masuk saat level jebol; breaker menunggu retest
> sesudahnya.

## Apa yang sudah diketahui sebelum ini

| pertanyaan | jawaban | sumber |
|---|---|---|
| klaim arah | negatif signifikan, n=38.058 | H8, `docs/CALIBRATION.md` |
| waktu-ke-sentuh | terbalik juga, +1,24 bar LEBIH LAMBAT, t=+5,83 | `docs/gap_outcomes.json` |
| lantai 2,0 miliknya sendiri | **belum pernah diukur** | - |

## Populasi, dan satu dugaan yang gugur

**97,4 persen order block akhirnya jadi breaker**, 2.733 dari 2.805 pada 20.000
bar XAUUSD 30m. Cuma 72 yang tidak pernah ditembus sebuah close. Jadi BRK bukan
objek langka, ia hampir seluruh populasi OB dibaca dari sisi seberang -
sebanding dengan IFVG yang 95,2 persen.

Detector induknya dibangun ulang pada hari yang sama (kotak dari badan lilin,
impuls diukur ke close), jadi BRK mewarisi rectangle yang berbeda dari minggu
lalu. Dugaannya: kotak badan yang lebih pendek lebih mudah ditembus close, jadi
tingkat inversinya naik. **Terukur, dugaan itu SALAH:**

| aturan induk | OB | BRK | tingkat | tinggi median |
|---|---|---|---|---|
| sekarang, badan plus close | 2.805 | 2.733 | **97,4%** | 1,268 |
| lama, rentang penuh plus wick | 4.041 | 3.934 | **97,4%** | 2,846 |
| hanya badan | 4.041 | 3.953 | 97,8% | 1,223 |
| hanya close | 2.805 | 2.720 | 97,0% | 2,900 |

Tingkatnya 97,0 sampai 97,8 persen apa pun aturannya. Di angka setinggi itu
tidak ada ruang untuk bergerak: hampir setiap order block ditembus close kalau
diberi cukup bar. Yang berubah populasinya, turun 31 persen, dan tinggi
kotaknya, turun 55 persen.

## Hasil

Baseline tanpa gerbang: n=7.410, exp_r **+0,2618**, t = **+12,60**,
profit factor **1,557**.

| lantai | n | exp_r | win rate | PF | wf | verdict |
|---|---|---|---|---|---|---|
| 1,0 dan 1,5 | 7.410 | +0,2618 | 46,28% | 1,557 | - | tidak mengikat, tak ada populasi di bawahnya |
| 2,0 **terpasang** | 4.391 | +0,2790 | 47,01% | 1,603 | 8/8 | **tidak memisahkan** |
| 2,5 | 2.671 | +0,2855 | 47,55% | 1,617 | 8/8 | **tidak memisahkan** |
| 3,0 | 1.706 | +0,3128 | 48,59% | 1,688 | 8/8 | **tidak memisahkan** |
| 4,0 | 737 | +0,3146 | 47,35% | 1,673 | 8/8 | **tidak memisahkan** |
| 6,0 | 169 | +0,2738 | 48,52% | 1,566 | 5/5 | **tidak memisahkan** |

> [!IMPORTANT]
> **Tidak satu ambang pun memisahkan.** Setiap lantai menaikkan exp_r sedikit
> dan menaikkan PF sedikit, tetapi tidak satu pun selisihnya melewati ambang
> Bonferroni 2,9137 - jadi kenaikan itu tidak bisa dibedakan dari memangkas
> populasi secara acak. Walk-forward 8 dari 8 di mana-mana, yang di sini
> berarti tandanya konsisten, bukan bahwa gerbangnya bekerja.
>
> Kesimpulannya: **BRK tidak butuh gerbang.** Populasi mentahnya sudah membawa
> angkanya.

## Per timeframe

| tf | n | baseline exp_r | PF pada lantai 2,0 |
|---|---|---|---|
| 15m | 1.359 | +0,1863 | 1,456 |
| 30m | 3.119 | **+0,3535** | **1,715** |
| 1h | 1.557 | +0,2210 | 1,481 |
| 4h | 1.008 | +0,1914 | 1,625 |
| 1d | 362 | +0,1331 | 1,853 |
| 1w | 5 | -0,1723 | tidak terukur |

**Lima dari enam timeframe positif**, dan itu lebih merata daripada order block
yang baselinenya negatif di empat dari enam sebelum diperbaiki.

## Dua tersangka yang diuji dan gugur

BRK memakai **rectangle yang sama** dengan OB, cuma dibaca dari sisi seberang,
dan OB memberi +0,1600. Sebuah kotak yang menguntungkan long DAN short adalah
tanda ada mekanisme, bukan edge, jadi dua penjelasan mekanis diuji lebih dulu.

| tersangka | OB | BRK | verdict |
|---|---|---|---|
| jalan ke target lebih lapang | `profit_zone_rr` median 13,57 | 14,04 | **gugur**, praktis sama |
| kotak lebih rapat, stop lebih dekat | tinggi median 4,871 | 4,796 | **gugur**, praktis sama |

Jadi bukan geometri reward maupun geometri stop.

## Angkanya tidak outlier, dan itu yang membuatnya layak dipercaya

| detector | baseline exp_r | t |
|---|---|---|
| IFVG, inversi dari FVG | +0,2348 | +14,60 |
| **BRK, inversi dari OB** | **+0,2618** | **+12,60** |
| OB, induknya | +0,1600 | +8,49 |

**Kedua objek inversi mengukur lebih baik daripada induknya, di dua keluarga
yang independen.** Itu pola yang konsisten, bukan satu angka aneh yang berdiri
sendiri.

> [!WARNING]
> **Ini BUKAN klaim arah, dan H8 tetap berdiri.** H8 mengukur apakah tahu
> sebuah kotak terbalik memperbaiki tebakan ARAH, dan jawabannya negatif
> signifikan di n=38.058. Dokumen ini menanyakan hal lain: sebuah trade di
> proximal dengan bracket yang sudah ditentukan. Keduanya bisa benar
> bersamaan, dan menggabungkannya akan menghasilkan klaim yang tidak satu pun
> pengukuran ini dukung.

## Dua keluarga definisi, dan kita mengimplementasi satu

Riset sumber luar menemukan bahwa breaker punya **dua keluarga definisi yang
bukan varian satu sama lain**:

| | Keluarga 1 | Keluarga 2 |
|---|---|---|
| definisi | order block yang gagal, dibaca terbalik | raid likuiditas lalu displacement |
| sweep sebelumnya | opsional, confluence | **wajib, konstitutif** |
| rectangle | dari order block induk | dari lilin di swing yang menyapu |
| sumber | FluxCharts, innercircletraders.net | LuxAlgo, Trading Strategy Guides |

**Kita mengimplementasi Keluarga 1**, dan itu harus dinyatakan alih-alih
diasumsikan universal.

> [!NOTE]
> Repo ini menyimpan DUA pernyataan soal mitigation block di tempat berbeda,
> dan riset menemukan keduanya benar tetapi milik taksonomi yang berbeda.
> `BACKLOG.md` baris 76 menyebut pembedanya adalah ketiadaan sweep, yang cocok
> dengan separator LuxAlgo. Baris 101 menyebut tidak ada sumber yang
> memisahkannya dari order block, dan jawabannya `ZoneState.MITIGATED` - yang
> justru persis separator ictkillzone, di mana mitigation adalah zona yang
> BELUM ditembus body dan ditradingkan ke arah aslinya. Kedua separator itu
> tidak kompatibel: yang satu membuat mitigation zona yang berbalik tanpa
> sweep, yang lain membuatnya zona yang tidak berbalik sama sekali. Jadi
> membangun detector mitigation berarti memilih taksonomi satu blog lalu
> mengukurnya, tanpa cara menyatakan taksonomi mana yang gagal.

## Tidak ada angka pembanding di literatur

Pencarian tidak menemukan **satu pun** hit rate atau ekspektasi terukur untuk
breaker block, dengan sample size, di sumber mana pun. StatOasis menguji empat
konsep ICT dan breaker bukan salah satunya. IndicatorEdge tidak
mengisolasinya. Setiap halaman memberi aturan dan gambar, nol hitungan.

Jadi tidak ada target untuk direproduksi, dan angka di dokumen ini adalah yang
pertama yang punya n dan t.

## Sapuan aturan, 6 September 2026

Gerbangnya tidak memisahkan, jadi tidak ada yang bisa diperbaiki dengan
menyetel ambang. Pertanyaan berikutnya aturannya, dan permukaan aturan BRK
sangat kecil: `inversion.py` mewarisi rectangle, skala ATR dan ambang impuls
dari order block induknya, lalu menyumbang PERSIS SATU keputusan sendiri, yaitu
lifecycle mulai di `break_index + 1`. Semua yang disapu di bawah karena itu
adalah hal yang DIWARISI.

`tools/brk_variants.py`, dua sel 30m, Bonferroni 2,5758.

| lengan | n | exp_r | win rate | PF | wf | t | verdict |
|---|---|---|---|---|---|---|---|
| A baseline | 3.122 | +0,3515 | 46,57% | 1,709 | 8/8 | - | - |
| B sweep **wajib** | **499** | +0,4075 | **32,46%** | 1,640 | 8/8 | +0,40 | tidak signifikan |
| C sweep **dilarang** | 2.565 | +0,3172 | 44,83% | 1,617 | 8/8 | -0,63 | tidak lebih baik |
| D impuls diukur di break | 3.122 | +0,3515 | 46,57% | 1,709 | 8/8 | **0,0** | tidak lebih baik |
| E lantai kotak 0,05 ATR | 3.129 | +0,3446 | 46,60% | 1,695 | 8/8 | -0,13 | tidak lebih baik |
| F B+D | 499 | +0,4075 | 32,46% | 1,640 | 8/8 | +0,40 | tidak signifikan |

### Diulang di 12 sel, 6 September 2026, dan lengan E dibalik arahnya

Detector order block berubah hari itu, dan kotak BRK menyalin `zone.top,
zone.bottom` dari parent-nya, jadi seluruh tabel di atas diukur pada populasi
yang sudah tidak ada. Diulang di 12 sel. Lengan A sekarang bernama "produksi
saat ini" karena ia memang menunjuk ke `detect_order_block` yang HIDUP; kunci
cache tidak memuat kode, jadi nama lama akan menyajikan angka detector lama
untuk detector baru tanpa satu pesan pun.

| lengan | n | exp_r | win rate | PF | wf | t | verdict |
|---|---|---|---|---|---|---|---|
| **A produksi saat ini** | **7.480** | **+0,2631** | 46,70% | **1,566** | 8/8 | - | - |
| B sweep **wajib** | 1.142 | +0,2895 | **33,45%** | 1,475 | 8/8 | +0,34 | tidak signifikan |
| C sweep **dilarang** | 6.169 | +0,2367 | 45,23% | 1,493 | 8/8 | -0,87 | tidak lebih baik |
| D impuls diukur di break | 7.480 | +0,2631 | 46,70% | 1,566 | 8/8 | **0,0** | rancangan salah |
| E **TANPA** lantai kotak | 7.411 | +0,2613 | 46,26% | 1,556 | 8/8 | -0,06 | tidak lebih baik |
| F B+D | 1.142 | +0,2895 | 33,45% | 1,475 | 8/8 | +0,34 | tidak signifikan |

Kesimpulan tabel 30m bertahan di populasi enam kali lebih besar. Sweep wajib
tetap membuang 85 persen (7.480 ke 1.142) dan tetap menjatuhkan win rate, 46,70
ke 33,45 persen, untuk t=+0,34 lawan ambang 2,5758. Sweep dilarang tetap
positif. Cabang Keluarga 2 mati untuk kedua kalinya.

**Lengan E dibalik arahnya, dan itu koreksi.** Versi pertamanya MENAMBAH lantai
kotak di atas baseline, dan setelah lantainya dikirim ke `detect_order_block`
baseline sudah berlantai, jadi lengan itu mengukur nol - cacat yang sama persis
dengan lengan D. Yang menangkapnya `_selftest()` di `tools/brk_variants.py`,
bukan pembacaan angkanya. Sekarang ia MENCABUT lantainya lewat context manager
`_floor(0.0)`, jadi t=-0,06 berarti "membuang lantai tidak memperbaiki apa pun".

### Cabang Keluarga 2 mati di data ini

Sweep yang sumber-sumber Keluarga 2 sebut **konstitutif** membuang 84 persen
populasi, dari 3.122 ke 499, dan menjatuhkan win rate dari 46,57 ke 32,46
persen. exp_r-nya memang naik, tetapi t=+0,40 lawan ambang 2,5758.

Yang menutup cabangnya adalah lengan C. Populasi yang DILARANG menyapu tetap
positif, +0,3172. Kedua sisi belahan positif dan tidak ada yang memisahkan,
jadi syarat yang satu keluarga definisi sebut wajib tidak membedakan apa pun di
sini. Itu jawaban satu angka untuk sebuah cabang yang kalau tidak diuji begini
akan menuntut detector kedua.

### Satu lengan yang dirancang salah, dan tandanya t nol persis

Lengan D mengembalikan angka yang IDENTIK dengan baseline, sampai ke digit
terakhir, dengan Welch t = 0,0. Itu bukan hasil, itu cacat rancangan sapuan.

`departure_atr` untuk BRK hanya masuk ke gerbang dan ke tampilan. Ia tidak
masuk ke trade-nya sama sekali: entry di proximal, stop di luar distal, target
di zona lawan terdekat. Mengukur ulang angka itu karena itu TIDAK BISA
menggerakkan outcome, apa pun nilainya. Lengan itu tidak menguji apa pun, dan
seharusnya terlihat sebelum dijalankan.

### Lantai tinggi kotak, satu-satunya yang membeli sesuatu

Kotak badan yang diwarisi dari order block membawa ekor sangat tipis, sebagian
di bawah satu pixel di layar. Lantai 0,15 dari RENTANG LILIN, dimekarkan
simetris lalu digeser kembali ke dalam lilinnya, memperbaikinya:

| tf | n | terkecil sebelum | terkecil sesudah | jumlah di bawah 0,05 ATR |
|---|---|---|---|---|
| 30m | 7.967 | 0,0003 ATR | **0,0116** | 550 ke **113** |
| 4h | 1.152 | 0,0007 | **0,0234** | 104 ke **25** |
| 1d | 387 | 0,0002 | **0,0068** | 43 ke **20** |

Kasus terburuk membaik tiga puluh sampai tiga puluh empat kali lipat, dengan
biaya exp_r +0,0018 dan PF +0,010 - keduanya jauh dari signifikan, dan tandanya
justru positif.

> [!NOTE]
> Sisa kotak di bawah 0,05 ATR bukan lantai yang gagal. Lantainya relatif
> terhadap RENTANG LILIN ITU SENDIRI, sementara tabel ini mengukur terhadap ATR
> MEDIAN seluruh deret, jadi lilin kecil di periode tenang tetap menghasilkan
> rasio kecil. Yang menunjukkan efeknya adalah kolom terkecil.

> [!IMPORTANT]
> Versi pertama lantai ini memakai ATR dan DITOLAK `tests/test_no_repaint.py`:
> `wilder_atr` rata rata berjalan yang disemai dari bar pertama, jadi ATR di bar
> absolut yang sama berbeda antar jendela dan geometri kotaknya ikut bergeser.
> Empat dari 424 kotak bergeser ~1e-5, dan HANYA saat jendelanya tumbuh ke kiri.
> Angka 0,05 ATR di tabel lengan 30m di atas mengukur besaran yang tidak pernah
> dikirim. Rinciannya di `docs/QA-OB-GATE.md`.

### Jawabannya, untuk pertanyaan yang menyebabkan sapuan ini

**Profit factor breaker tidak bisa dinaikkan lewat lengan mana pun di sini.**
Diuji dua kali, 30m dan 12 sel, dan tidak satu lengan pun mengalahkan baseline
secara signifikan. Yang bisa diperbaiki gambarnya, dan itu terukur gratis.

Angka yang naik justru datang dari tempat lain: PF 1,566 di 12 sel lawan 1,557
sebelumnya bukan hasil sapuan ini sama sekali, melainkan warisan dari perbaikan
detector order block pada 6 September 2026. BRK menyalin kotak parent-nya, jadi
memperbaiki OB memperbaiki BRK tanpa satu baris di `inversion.py` berubah. Itu
juga peringatan: setiap kali OB berubah, tabel di halaman ini kedaluwarsa.

## Gambarnya diukur untuk pertama kali, 8 September 2026

BRK satu-satunya dari empat detektor yang autodrawing-nya belum pernah
diperiksa sama sekali - tidak ada chart-audit, tidak ada pixel-truth. Keduanya
dijalankan di XAUUSD harian, 2000 bar.

### pixel-truth: 6 dari 7, dan gagal di tempat yang PERSIS sama dengan IFVG

| pemeriksaan | hasil |
|---|---|
| zona ditemukan di canvas | 9 dari 9 |
| ada kotak berdiri sendiri dan cukup tinggi untuk diukur | 5 dari 9 terukur, 4 berbagi pita harga dengan sisinya sendiri |
| **cukup tepi terbaca untuk diukur** | **GAGAL: atas 1 dari 5, bawah 3 dari 5** |
| tepi ATAS di tempat skala harga menaruhnya | terburuk **0,5px** |
| tepi BAWAH di tempat skala harga menaruhnya | terburuk **0,5px** |
| kotak menutupi bar basis asalnya | terburuk 0,13 bar di luar kotak |

**Geometrinya akurat sampai setengah piksel. Yang gagal keterbacaannya.**

### Dan sekarang belahannya bersih: terbalik lawan tidak terbalik

Dengan BRK terukur, keempat detektor punya angka pixel-truth, dan hasilnya
membelah tepat di garis apakah kotaknya hasil inversi:

| detektor | terbalik? | pixel-truth | tepi atas terbaca |
|---|---|---|---|
| fvg | tidak | **7 dari 7** | lolos |
| order_block | tidak | **7 dari 7** | lolos |
| ifvg | ya, SETIAP kotak | 6 dari 7 | 4 dari 7 |
| **breaker** | ya, SETIAP kotak | 6 dari 7 | **1 dari 5** |

Dua lolos, dua gagal, dan pembaginya bukan timeframe, bukan instrumen, bukan
arah gerbang - melainkan inversi. Sampai hari ini diagnosis "kotak terbalik
berdesakan di tempat induknya pecah" bersandar pada SATU layer; sekarang ia
2 lawan 2 di sepanjang garis yang tepat. **Dan BRK lebih parah dari IFVG**,
1 dari 5 lawan 4 dari 7.

Sebabnya struktural dan sama untuk keduanya: kotak terbalik duduk tepat di
tempat induknya baru pecah, induk berkerumun, jadi tepinya saling menimbun.
Bukan cacat satu baris.

### chart-audit: satu klaim auditor dibantah aritmetika, satu berdiri

Grounding run ini **UNUSABLE** - auditor menyebut angka 4200 yang engine tidak
pernah keluarkan - jadi prosanya dikutip untuk dibaca, bukan dipercaya. Dua
klaimnya diperiksa sendiri:

**DIBANTAH: "caption plate terpotong di tepi kiri pane".** Legenda menyatakan
plate didorong ke kiri, bukan dipotong. Penempatannya di `zone-primitive.ts`:

```
const x = Math.min(Math.max(Math.round(box.left * kx), 0), Math.max(limit, 0)) + 5 * kx;
const plate = { x: x - 3 * kx, ... };
```

`x` selalu minimal `5*kx`, jadi `plate.x` selalu minimal `2*kx`, dan teksnya
digambar di `x` dengan padding 3*kx di kedua sisi. Plate tidak bisa mulai di
kiri pane. Yang auditor lihat border plate itu sendiri pada 2 CSS px dari tepi,
dan pada jarak itu ia memang TERBACA seperti glyph tersayat.

**BERDIRI: plate menutupi rule proximal.** Caption BRK kedua duduk tepat di
atas rule terang di 4859,61. Loop anti-tabrakan hanya menguji plate lawan
`placed`, yaitu plate lain - tidak pernah lawan rule proximal. Jadi caption
selalu boleh menimpa satu-satunya isyarat yang selamat di kotak tiga piksel.

**BERDIRI juga: dua caption identik.** Zona supply `tested` dan `mitigated`
sama-sama memajang `BRK flipped`, dan bedanya cuma opacity border 1,33 sampai
1,82 banding satu - keluhan yang sama untuk kelima kalinya di sesi ini.

## Definisinya dicek ke sumber, dan ada syarat kanon yang kita tidak punya

`inversion.py` mencatat penyimpangan BRK dari kanon: rentang lilin penuh,
ambang `impulse_atr`, tidak menuntut structure break. Daftar itu **kurang satu**,
dan yang kurang itu yang paling menentukan.

Kanon ICT menuntut **sapuan likuiditas sebelum induknya gagal**: swing yang
gagal harus lebih dulu berdagang melewati high atau low sebelumnya. Yang
membuatnya penting bukan bahwa ia menaikkan probabilitas, melainkan bahwa
**itulah yang memisahkan breaker dari mitigation block** - dan menurut kanon
yang sama, keduanya diperdagangkan ke arah BERLAWANAN (breaker melawan tren,
mitigation searah tren).

Detektor kita memakai bacaan longgar: setiap order block yang ditembus jadi
breaker. Konsekuensinya bisa dinyatakan sebagai hipotesis yang jelas:
**layer `breaker` mencampur dua populasi bertanda berlawanan ke dalam satu
kotak angka**, dan campuran begitu akan menarik edge terukur ke arah nol. Itu
konsisten dengan yang terbaca: PF di sekitar satu, dan H8 di
`docs/CALIBRATION.md` mengukur klaim arah order block terbalik di -0,274
(t = -4,22).

Ini **belum diuji**, dan disebut hipotesis karena dua alasan. Pertama, bahannya
sudah ada di repo - `structure.py` punya `mss_sweeps`, jadi menguji ini berarti
memakai ulang yang sudah ada, bukan menulis detektor sapuan baru. Kedua,
`structure.py` juga sudah mengukur konjungsi sapuan-lalu-break-berlawanan dan
mendapat null (t = -0,79 dan -0,12 pada DELTA), jadi bukti yang ada di repo ini
justru melemahkan harapan bahwa sapuan akan menyelamatkan BRK.

Yang berubah hari ini bukan angkanya, melainkan bahwa penyimpangannya sekarang
TERCATAT. Sebelum ini daftar penyimpangan di `inversion.py` terbaca lengkap
padahal tidak.

## Hipotesis sapuan likuiditas DIUJI dan NULL, 8 September 2026

Bagian di atas mencatat bahwa kanon ICT ketat menuntut sapuan likuiditas sebelum
induknya gagal, bahwa itu yang memisahkan breaker dari mitigation block, dan
menduga layer ini mencampur dua populasi bertanda berlawanan. **Dugaan itu
diuji, dan tidak bertahan.**

### Rig

`tools/gate_sweep.cell_rows` lewat `detectors_costed.resolved_as` dan
`intrabar.resolved` - rig yang SAMA yang menghasilkan angka BRK di halaman ini,
jadi hasilnya berdampingan tanpa definisi entry/stop/target/biaya kedua. Berbiaya
penuh dan diselesaikan intrabar (1h ke 5m, 1d ke 1h).

Sapuan memakai `structure.breaks(structure_n=5)` dengan `kind == "SWEEP"`, dipakai
ulang bukan ditulis ulang, dan `confirmed_at` menahan lookahead. Jangkar jendela
dinyatakan di muka: indeks sapuan di `[break - W, break]`, yaitu kaki yang gagal.
Utama W=20. Enam belahan didaftarkan lebih dulu, jadi ambang Bonferroni
**|t| >= 2,6383**.

Baris `intrabar.resolved` membawa `zone_id`, jadi satu backtest per sel dipecah
belakangan - setiap definisi belahan tambahan gratis.

### Belahan utama, exp_R sesudah biaya

| sel | SWEPT n / exp_R / PF | UNSWEPT n / exp_R / PF | Welch t |
|---|---|---|---|
| XAU 1h | 529 / **+0,1785** / 1,343 | 420 / +0,0414 / 1,076 | +1,292 |
| BTC 1h | 520 / +0,0227 / 1,041 | 523 / -0,0830 / 0,862 | +1,137 |
| XAU 1d | 137 / -0,0773 / 0,792 | 134 / -0,1251 / 0,702 | +0,458 |
| BTC 1d | 104 / -0,1097 / 0,679 | 92 / -0,0122 / 0,969 | **-0,708** |
| **gabungan** | **1.290 / +0,0653 / 1,130** | **1.169 / -0,0376 / 0,931** | **+1,744** |

Populasinya BUKAN masalah: SWEPT 52,5 persen dari gabungan di W=20, dan tidak
ada lengan yang mendekati n=30. Biaya juga bukan: sebelum biaya jaraknya sama
dan tetap tidak signifikan.

### Tak satu pun dari enam belahan lolos ambang

|t| gabungan terbesar **1,988** (W=5), jauh di bawah 2,6383. Tandanya berbalik
antar sel (+0,1371 / +0,1057 / +0,0478 / **-0,0975**) DAN antar pilihan jendela
(+1,744 di W=20, **-0,732** di W=50). |t| per sel terbesar justru **-2,720**,
dan itu di jendela berjangkar-origin milik repo ini sendiri, dengan SWEPT lebih
BURUK.

### Kontrol yang menutup ceritanya

Kalau syarat kanon itu membawa mekanisme, sapuan BERLAWANAN arah break (bentuk
breaker yang sebenarnya) harus mengalahkan sapuan SEARAH. Tidak:

| lengan | n | exp_R |
|---|---|---|
| berlawanan saja | 344 | -0,0039 |
| searah saja | 770 | +0,0278 |
| **dua sisi** | **176** | **+0,3645** |
| tidak disapu | 1.169 | -0,0376 |

Welch antara berlawanan dan searah **-0,34**. Dan seluruh positif gabungan
tinggal di zona yang disapu di DUA sisi dalam 20 bar, n=176 - penanda volatilitas
dua arah, bukan konstruk kanoniknya. Bendera sapuan itu mewakili kegaduhan, bukan
sapuan-lalu-gagal.

### Putusan

**Menuntut sapuan likuiditas tidak memisahkan hasil breaker.** Hipotesis
percampuran breaker/mitigation tidak didukung di rig ini.

Bukti di repo ini sudah menunjuk ke sana sebelum uji ini dimulai, dan itu bagian
dari hasilnya: null H9 untuk sapuan-lalu-break-berlawanan di `structure.py`
(t = -0,79 dan -0,12), plus lengan B halaman ini (sapuan diwajibkan, n=1.142,
t=+0,34) dan lengan C (sapuan dilarang, tetap positif +0,2367). Uji hari ini
mengulanginya di jangkar jendela berbeda dan sel berbeda dan mendapat jawaban
yang sama.

> [!WARNING]
> Baseline empat sel ini jauh lebih lemah dari angka utama halaman ini. Dua
> belas sel memberi exp_R +0,2631 dan PF 1,566; XAU/BTC di 1h dan 1d saja
> memberi **+0,0164, PF 1,031, t=+0,555, wf 4 dari 8**, dengan kedua sel harian
> negatif. Angka utama itu ditopang 30m. Membelah populasi yang baseline-nya tak
> bisa dibedakan dari nol memang sedikit yang bisa dipisahkan, dan itu batas
> uji ini sekaligus alasan tambahan untuk tidak membaca null-nya terlalu keras.

### Konsekuensinya untuk parity BRK

Parity BRK ditunda dengan alasan "menunggu keputusan soal sapuan". Keputusannya
sekarang ada: **sapuan tidak dipakai**, karena mewajibkannya tidak terukur
memperbaiki apa pun. Jadi detektor kita tetap di bacaan longgar secara sadar,
dan parity lawan script publik yang memakai definisi ketat akan membandingkan
dua himpunan yang memang berbeda menurut definisi. Itu bukan alasan menundanya
lagi, melainkan syarat yang harus dinyatakan saat parity-nya dibuat.

## `pixel-truth` merah dikejar sampai dua hipotesis gugur, 8 September 2026

### Diagnosis yang saya tulis pagi ini SALAH

Bagian gambar di atas menyimpulkan merahnya disebabkan "kotak terbalik yang
berdesakan di tempat induknya pecah". **Itu tidak bisa benar**, dan bantahannya
ada di keluaran harness itu sendiri: saringan `stacked` SUDAH membuang kotak
yang berdesakan, dan semua kegagalan ada di antara kotak yang TIDAK bertumpuk.
BRK: 4 bertumpuk dibuang, lalu 1 dari 5 sisanya yang gagal.

### Hipotesis kedua: tepi di luar pane. Juga gugur

chart-audit menunjukkan tepi atas dua kotak supply BRK di atas batas pane, jadi
`priceToCoordinate` bisa mengembalikan koordinat negatif dan probe mencari baris
piksel yang tak ada. Diperiksa di payload: seluruh `top_wide.at` positif dan di
dalam pane, `top_cover` 0,578 sampai 0,695. Tepinya DITEMUKAN. Gugur.

### Hipotesis ketiga: lebar kotak. Diuji, dan diuji dengan benar sehingga gugur

Nilai `top_cover` **0,5783132530120482 muncul TUJUH kali** di kotak selebar
1.019 sampai 2.203 piksel. Angka identik lintas geometri sebesar itu bukan
pengukuran per zona. Dua kontrol dijalankan di sel yang PERSIS sama (1d, 2.000
bar):

| detektor | lebar kotak | top_cover | putusan |
|---|---|---|---|
| fvg | 566 px seragam | **1,000** | lolos |
| order_block | 593 px seragam | 0,951 - 1,000 | lolos |
| ifvg | beragam | rendah | **gagal** |
| breaker | 664 - 2.203 px | 0,578 - 0,695 | **gagal** |

Dua yang lolos punya kotak pendek, yang gagal punya kotak panjang, dan isian
kotak memang dilukis DI BAWAH lilin secara sengaja - jadi tiap bar tambahan
yang dilalui sebuah zona menaruh satu lilin lagi di depan bordernya. Kelihatan
seperti jawabannya.

**Diuji dengan membatasi rentang probe ke 15 bar pertama supaya semua detektor
diukur di panjang border yang sebanding. Hasilnya MEMBURUK** - BRK bawah 3 dari
5 jadi 1 dari 5. Hipotesisnya gugur, dan patch-nya dicabut. Tidak ada perbaikan
spekulatif yang di-ship, dan ambangnya tidak dilonggarkan.

### Yang tersisa, dan file rendernya sudah menuliskannya sejak awal

`zone-primitive.ts` baris 425: alpha border adalah
`min(EDGE_ALPHA[state], near ? 0.85 : 0.38)`, dan tepat di bawahnya:
**"A FAR ZONE IS NOT DRAWN AS A BOX AT ALL. It gets the proximal stroke below
and nothing else."** Header `pixel-truth.mjs` mengatakan hal yang sama dari sisi
harness: "the far tier is a single stroke and that harness asks rectangle
questions, so it cannot score the far tier at all".

Jadi ada satu tier zona yang menurut kedua file tidak bisa dinilai harness ini,
dan harness-nya tetap menilainya. Itu kandidat terkuat yang tersisa. Ia BELUM
dibuktikan di sini: `FILLED_NEAR_PRICE` = 12 dan BRK cuma menggambar 9 zona,
jadi kalau himpunan near dihitung hanya atas zona layer ini semuanya near dan
penjelasannya tidak cukup. Yang belum diperiksa: apakah himpunan itu dihitung
atas SELURUH layer di chart.

### Yang berdiri sesudah semua ini

| pernyataan | status |
|---|---|
| penempatan akurat 0,5 px di keempat detektor | **terbukti berulang** |
| merahnya BUKAN karena berdesakan | **terbukti** |
| merahnya BUKAN karena tepi di luar pane | **terbukti** |
| merahnya BUKAN karena lebar kotak | **terbukti lewat uji yang memburuk** |
| merahnya soal tier far yang tak digambar sebagai kotak | dugaan terkuat, belum terbukti |

Nilainya bukan pada menyalakan hijau, melainkan bahwa merah ini sekarang tidak
lagi bisa dibaca sebagai "gambarnya salah". Geometrinya benar; yang belum
selesai kemampuan harness menilai satu tier tertentu.

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.gate_sweep --detector breaker
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.brk_variants --cells all
```

> [!WARNING]
> Tulis hasilnya ke file sementara dan pindahkan hanya kalau exit 0. Redirect
> langsung ke `docs/brk_variants_12cell.json` memotong file itu jadi 0 byte
> SEBELUM perintahnya jalan, dan sapuan 12 sel bisa mati di menit ke-20 karena
> otorisasi MT5 berkedip. Itu terjadi pada 6 September 2026, ke dua file
> sekaligus.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

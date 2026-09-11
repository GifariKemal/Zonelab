# Apa yang diadopsi dari `Referensi grup dan Bg Nas`

Buku besar per butir atas delapan area metodologi di folder
`Referensi grup dan Bg Nas` (89 file: 82 gambar dan 7 file teks, tersebar di
Whatsapp 63, Discord 18, Telegram 8). Folder ini menggantikan `analisis lama`
pada 26 Agustus 2026; penomoran gambarnya bertahan, jadi sitasi lama tetap
menunjuk gambar yang sama. Setiap butir punya satu dari lima status, dan tidak ada
butir yang dibiarkan tanpa status.

| Status | Artinya |
|---|---|
| **Ada** | Terpasang, ada tesnya, bisa dipanggil dari API |
| **Sebagian** | Terpasang tetapi tidak seluruh butirnya, dan bagian yang kurang disebut |
| **Belum** | Belum dibangun, dan tidak ada alasan prinsipil yang menghalangi |
| **Ditolak** | Sengaja tidak dibangun, dengan alasan yang tertulis |
| **Terukur null** | Dibangun lalu diuji, dan gagal |

> [!IMPORTANT]
> **Temuan tunggal terbesar dari putaran ini, dan ia menyentuh tiga area sekaligus.**
> Kuarter micro berdurasi **1.350 detik**, dan itu tidak habis membagi satu pun
> interval bar standar (900, 3.600, 14.400). Konsekuensinya ditemukan tiga kali
> secara terpisah oleh tiga pengukuran yang tidak saling tahu:
>
> 1. Di ribbon siklus, pada chart 15 menit **151 dari 152** kuarter micro tidak
>    punya posisi sama sekali di sumbu waktu.
> 2. Pada bar 1 jam, hanya **28 sampai 30 dari 64** rantai kuarter yang pernah
>    bisa muncul, dan **enam dari sepuluh** rantai di daftar high probability
>    miliknya (114, 141, 144, 414, 441, 444) **mustahil terjadi**, bukan jarang.
> 3. True open derajat nano menghasilkan **0 level dari 55.870** batas, karena Q2
>    nano jatuh 337 detik ke dalam siklus micro dan tidak ada bar yang membuka di
>    sana.
>
> Artinya bukan gridnya salah. Artinya **derajat micro dan nano hanya bisa
> dipakai pada timeframe yang membaginya habis**, dan setiap pengukuran atas
> rantai kuarter wajib mengambil sampel pada 22,5 menit atau lebih halus. Di atas
> itu, yang diukur adalah interval barnya, bukan pasarnya.

---

## 1. Kerangka waktu, inti Quarterly Theory

| Butir | Status | Catatan |
|---|---|---|
| Pembagian bagi 4 di setiap derajat | **Ada** | Enam derajat tervalidasi, 26 properti pada 73.956 kuarter, nol celah dan nol tumpang tindih |
| Seminggu = 4 hari, Senin sampai Kamis | **Ada** | Jumat bukan kuarter kelima, dan lubang 72 jam itu terdokumentasi, bukan cacat |
| Jumat punya profil sendiri | **Belum** | Gridnya sudah benar mengeluarkan Jumat; objek profil Jumat belum ada |
| Peran kuarter Q1 sampai Q4 | **Ada** | `sequence.nominal_role`. Q4 menyimpan **dua** bacaan sekaligus, karena catatan Anda memberi dua dan tidak menandai mana yang utama |
| Q intraday sama dengan sesi | **Sebagian** | Lihat kaveat di bawah tabel. Namanya dipasang, kesamaannya tidak benar |
| Nesting 7 tingkat di panel bawah chart | **Ada** | Ribbon siklus, satu baris per derajat, diambil dari diagram Anda sendiri |
| Derajat nano | **Ada** | Membagi induknya persis; 337, 338, 337, 338 detik, karena 337,5 bukan bilangan bulat |
| Rantai kuarter tiga angka | **Ada** | `sequence.chain`, plus distribusi kemunculannya |
| Daftar high probability sepuluh rantai | **Ada, sebagai daftar Anda** | Ditandai `in_his_list`, **tidak pernah** `high_probability`. Sepuluh dari 64 rantai adalah 15,6%, dan angka dasar itu ikut dilaporkan setiap kali flag-nya dikutip |
| Aturan gap lawan siklus (Daily Gap = Monthly SSMT, H4 = Weekly, H1 = Daily, m15 = 90m, m5 = micro) | **Belum** | Ini aturan pemetaan, bukan konstruk; murah dibangun begitu ada yang memakainya |
| Aturan ekspansi (PDA Monthly menggerakkan Weekly, dan seterusnya) | **Belum** | Ia klaim kausal antar derajat, jadi ia hipotesis terukur, bukan objek gambar |
| Killzone dan jam spesifik | **Ada** | Asia 19:00-00:00, London 02:00-05:00, NY AM 07:00-10:00, London close 10:00-12:00, NY PM 13:30-16:00 New York. Silver Bullet tiga window: `london_sb` 03-04, `silver_bullet` 10-11, `ny_pm_sb` 14-15. Diperbaiki 3 September 2026 |
| Power of 3 dikaitkan ke NFP, CPI, FOMC | **Sebagian** | Rilisnya sekarang digambar lewat layer `news`, jadi Anda bisa melihat NFP, CPI dan FOMC berdiri di fase mana. Tetapi **klaimnya tetap tidak bisa diukur**: sumbernya hanya menerbitkan minggu berjalan, jadi tidak ada riwayat untuk mengujinya |

> [!WARNING]
> **Q2 bukan London, dan ini perlu dikatakan lugas.** Kuarter harian Q2 berjalan
> 00:00 sampai 06:00 New York. Killzone London di repo ini 02:00 sampai 05:00,
> yaitu **tiga jam yang seluruhnya berada di dalam kotak enam jam dan tidak
> berbagi satu tepi pun**. Kuarternya buka dua jam sebelum London berdagang apa
> pun dan tutup satu jam sesudahnya. Asia berbentuk sama: kuarter 18:00-00:00,
> killzone 19:00-00:00. Nama sesi di kuarter adalah **julukan untuk kotak enam
> jam**, bukan sesi itu sendiri. `IntradaySession.killzone` membawa jendela
> aslinya berdampingan supaya keduanya bisa dibandingkan, dan `same_window`
> bernilai False pada setiap kuarter yang punya killzone.

---

## 2. True Opens

| Tag | Status | Catatan |
|---|---|---|
| TYO, TMO, TWO, TDO, T90mO | **Ada** | True open adalah **Q2 sebuah siklus**, bukan bar pertamanya. Itu sebabnya true day open adalah tengah malam New York dan bukan 18:00 |
| TLO | **Ada, dan ia objek yang sama dengan TDO** | Bersumber, bukan disimpulkan: `chat.txt` baris 601, "Q2 - London -- kita marking pembukaan session ini di 0000 di m15 timeframe". London adalah Q2 siklus harian. Satu instan, satu bar, satu harga. Mengirim dua objek bernama akan membuat apa pun yang menghitung level yang searah menghitungnya dua kali |
| TNYO | **Ditolak sebagai true open** | Sumber yang sama: "Q3 - NY AM - kita marking H4 candle opening di 0600". 06:00 adalah pembukaan **Q3**, dan pembukaan Q3 adalah batas kuarter, bukan true open. Levelnya tetap bisa digambar sebagai batas kuarter; menamainya true open adalah kebohongan tentang level yang nyata. Ada tes yang menegakkan ini |
| TNO | **Ada gridnya, nol hasilnya** | Q2 nano jatuh 337 detik ke dalam siklus micro. Diukur: 0 level dari 53.331 batas pada PAXGUSDT dan 0 dari 55.870 pada emas Yahoo. Grid yang benar yang tidak menggambar apa pun pada feed yang ada |
| T4Y | **Ditolak** | Nol kemunculan di sumber teks mana pun di repo. Tidak ada yang bisa dipakai untuk memuaikan singkatannya |
| "old two" | **Ditolak** | Alasan yang sama |
| Aturan minimal dua true open searah | **Ada** | `stacked_opens` melaporkan berapa yang di atas dan berapa di bawah harga, dan **tidak** mengatakan apa yang harus dilakukan |

---

## 3. Likuiditas dan PD Array

| Butir | Status | Catatan |
|---|---|---|
| Premium/Discount, dealing range | **Ada, tiga bacaan berbeda** | `curve` berbasis swing dan beku saat lahir, `dealing_range_pos` berbasis pasangan swing terakhir, dan `PremiumDiscount` berbasis **jam**. Yang ketiga bersumber tunggal, jadi ketiga anchor-nya selalu dihitung dan dilaporkan bersamaan |
| BSL dan SSL | **Ada** | Ekstrem sesi Asia dan London, lengkap dengan `taken_at` |
| Asia dan London high-low | **Ada** | |
| ERL dan IRL, DOL, PDH/PDL, PWH/PWL, Friday dan Monday high-low | **Ada** | `app/liquidity.py`. DOL sengaja melaporkan **kandidat di setiap sisi** dan tidak pernah memilih satu, karena "draw on liquidity" adalah ramalan dan dua belas hipotesis arah sudah gagal di sini. Salah satu sisi boleh kosong, dan kosongnya adalah fakta tentang apa yang sudah tersapu |
| Inducement | **Ditolak** | Setiap definisi yang bisa dipakai butuh jendela waktu, "berapa lama sesudah level diambil gerakan sebenarnya boleh datang", dan tidak ada sumber yang menerbitkan angkanya. Tanpa batas, labelnya benar untuk hampir setiap level yang tersapu, jadi ia mengukur nol sambil terlihat seperti bacaan. Definisi tersempit yang tidak butuh angka karangan, yaitu likuiditas diambil lalu struktur patah ke arah lain, **sudah ada objeknya**: `StructureEvent` berjenis MSS membawa `swept_at`. Dan ia hanya bisa dikenali pada patahan **sesudah** pengambilan, jadi ia tidak pernah tersedia saat keputusan diambil. Ada tes yang menegakkan ketiadaannya |
| Liquidity pool di trendline | **Belum** | Butuh objek trendline, yang belum ada |
| Liquidity engineering (sideways) | **Belum** | |
| Purge dan sweep | **Ada** | `SWEEP` di overlay struktur, dengan medan penolakan `reversed_within` |
| Failure swing | **Belum** | |
| Level NFP | **Ada** | Digambar sebagai penanda vertikal pada waktu rilisnya, dari kalender ekonomi. Jamnya dari offset feed sendiri, bukan diasumsikan |
| FVG, IFVG, Order Block, Breaker | **Ada** | Empat detektor, lewat rig ukur yang sama dengan supply dan demand |
| CE, isi 50 persen | **Ada** | Sebagai garis tengah putus-putus pada pita gap, dan sebagai `equilibrium` pada bacaan premium/discount |
| Gap Daily dan Weekly | **Ada** | NDOG dan NWOG |
| Volume imbalance | **Belum** | |
| "wicks = gaps" | **Belum** | Ia perluasan definisi imbalance, bukan objek baru; layak diuji sebagai varian sebelum dikirim |
| Timed OB | **Belum** | |

---

## 4. Konfirmasi dan entry

| Butir | Status | Catatan |
|---|---|---|
| CISD | **Ada** | Berjangkar ke open lilin **pertama** run berlawanan, bukan yang terakhir |
| tCISD | **Ditolak untuk sekarang** | Disebut namanya di docstring sebagai di luar lingkup, supaya ketiadaannya tidak senyap |
| Displacement, bukan hovering | **Ada** | Sebagai objek, bukan ambang: ke mana ia lari, seberapa besar, apakah menembus struktur, apakah meninggalkan gap |
| MSS dan BOS | **Ada** | Definisi MSS sudah diperbaiki agar menuntut gap di dalam leg-nya, sesuai transkrip sumbernya |
| PSP, precision swing point | **Belum** | |
| Displacement multi-timeframe sebagai syarat stage | **Belum** | |
| Proyeksi standar deviasi | **Ada** | Geometrinya direkonstruksi dari gambar Anda dan **cocok dengan dua price tag di chart Anda sendiri** sampai 0,4 USD. Rumusnya `origin - arah x kelipatan x tinggi`, dengan origin di tepi rentang searah gerak |
| Level EV/CE per timeframe | **Sebagian** | CE ada; tabel EV per timeframe belum |
| Model one-shot-one-kill, Market Maker Buy/Sell, NY Judas Swing, trading the retracement | **Belum** | Ini template diskresioner, bukan konstruk terukur. Menggambarnya berarti mesin ini menyarankan entry, yang belum pernah ia lakukan |
| Profil hari Senin sampai Kamis, HOTW/LOTW | **Belum** | Ia klaim terukur dan pantas diuji seperti backtest area 8 |

---

## 5. Divergensi antar aset

| Butir | Status | Catatan |
|---|---|---|
| SSMT dua stage | **Ada** | Stage adalah **derajat**, bukan kuarter, dan tidak ada yang memaksa dua stage karena sumber yang sama mengirim model satu SSMT di sampingnya |
| SMT reguler, tanpa syarat kuarter berurutan | **Belum** | Bedanya nyata: SMT reguler cukup satu aset HH dan satu FS |
| Hidden SSMT | **Belum** | Anda sendiri menilainya lebih lemah dari purge plus failure swing yang jelas |
| Label divergensi per siklus di chart | **Sebagian** | `SSMTHit` membawa derajat dan pasangan aset; labelnya belum digambar di chart seperti "w.c - XAG" |
| Triad korelasi | **Sebagian** | 15 instrumen sudah ada, termasuk XAU/XAG/Platinum, DXY, NAS100, SPX500, WTI, Brent, US10Y, US30Y, BTC, ETH. Pengelompokannya sebagai triad, dan aturan "cukup 2 dari 3 menyentuh 50 persen", **belum** |
| Causal logic | **Belum** | |

> [!CAUTION]
> **Laju SSMT hampir seluruhnya ditentukan oleh pilihan pasangannya**, dan itu
> terukur: emas lawan perak 14,9%, platinum 21,0%, NASDAQ 36,0%, BTC 43,3%, DXY
> 59,5% karena DXY bergerak terbalik. Angka 43% sempat hampir terbit sebagai
> temuan padahal ia diukur pada pasangan yang tidak berkorelasi. Mencari
> divergensi antara dua instrumen tak berkorelasi adalah kesalahan kategori.

---

## 6. Perangkat chart, dan gaya visualnya

Bagian ini yang Anda minta diadopsi gaya UI-nya. Yang diambil bukan selera saya,
melainkan yang terhitung paling sering muncul di 51 chart beranotasi Anda.

| Objek | Status | Dari mana |
|---|---|---|
| Ray horizontal bernama dengan label di tepi kanan | **Ada** | Muncul di **24 dari 24** chart harga Anda. Fibonacci muncul di 12%. Ia objek paling sering dipakai di seluruh praktik Anda, jadi true open, event horizon dan pool semuanya ray bernama |
| Kotak waktu berarsir dengan garis tengah putus-putus | **Ada** | Muncul di **23 dari 25**. Garis tengahnya adalah pengukurannya, bukan hiasan: 50% dari rentang **berbasis waktu** jauh lebih sering Anda baca daripada level Fibonacci mana pun |
| Ribbon kuarter multi tingkat di panel bawah | **Ada, baru** | Diambil dari diagram buatan Anda sendiri, gambar 21: pita fase penuh lebar, merah manipulation dan hijau distribution, dengan pita LTF bersarang di atasnya |
| Session box Asia, London, Mon-Thu | **Sebagian** | Kotak kuarter ada; kotak sesi bernama sebagai kotak terpisah belum, yang ada ray pool-nya |
| Garis true open otomatis | **Ada** | |
| Penanda CISD | **Ada** | Sebagai segmen sepanjang run yang mempersenjatainya, bukan ray, supaya terlihat run mana yang menjadi jangkarnya |
| Marker swing | **Ada** | Overlay struktur, dengan `confirmed_at` |
| Label SSMT otomatis per siklus | **Sebagian** | |
| Tabel range EV/Top/Bot/Dist per timeframe | **Belum** | |
| Level proyeksi deviasi | **Ada** | |
| Silver Bullet window | **Ada** | Tiga killzone: `london_sb` 03:00-04:00, `silver_bullet` 10:00-11:00, `ny_pm_sb` 14:00-15:00. Diperbaiki 3 September 2026 |
| Level fraksi 0,25 / 0,5 / 0,75 | **Sebagian** | 0,5 ada di mana-mana sebagai CE dan equilibrium; 0,25 dan 0,75 belum |
| Segitiga 3-6-9 berbasis digital root | **Ditolak sebagai sinyal, ada sebagai dial** | Sebagai sinyal tetap ditolak, bersama 369 dan 168. Sejak 29 Agustus 2026 objek yang sama ada sebagai layer `vortex`, yaitu dial navigasi yang membaca kalender dan bukan harga, dan sebuah test melarangnya menyentuh jalur order. Lihat `docs/BACKLOG.md` Bagian 7 |

**Keputusan warna, dan kenapa begitu.** Chart Anda sendiri **tidak konsisten**
dalam warna: pink berarti session box di gambar 27 dan 32-37 tetapi quarter box
di 43-51, sedangkan oranye berarti timeframe 90 menit di sebagian gambar dan isi
IFVG di sebagian lain. Karena itu engine ini membaca objek lewat **label**, bukan
warna, dan memakai satu tinta netral di kanvas harga. Palet fase Anda yang merah
dan hijau tetap diadopsi **utuh**, tetapi hanya di ribbon bawah, karena di kanvas
harga hijau dan merah sudah punya satu arti tunggal yaitu demand dan supply.
Pemisahan itulah yang membuat mengadopsi palet Anda aman, bukan sembrono.

**Amandemen 20 Agustus 2026: satu tinta netral menjadi lima, per KELUARGA.**
Keputusan di atas tetap berlaku pada intinya - warna tidak boleh menyatakan
OBJEK apa ini, label yang menyatakannya - tetapi pelaksanaannya terlalu jauh.
Setiap primitive menyimpan abu-abu kebiruannya sendiri: 95/104/116, 139/150/165,
151/166/189, 154/166/181, 159/173/194. Lima rona yang sebenarnya satu rona.
Dengan sembilan layer menyala, pembaca tidak bisa membedakan caption struktur
dari ray pool tanpa membaca labelnya, dan pada satu frame terukur ada 96 label,
sebagian besar empat karakter.

Sekarang warna menyatakan KELUARGA, bukan objek. Di dalam satu keluarga semua
objek tetap satu tinta dan namanya tetap yang mengidentifikasi - jadi
inkonsistensi pada chart Anda tidak kembali. Yang berubah: lima keluarga tidak
lagi berbagi satu tinta.

| Keluarga | Isi | Tinta | rona | L* | kontras vs latar |
|---|---|---|---|---|---|
| grid | kotak kuarter, arsir sesi, penanda jeda | `#5f6975` | 212,7 | 44,0 | 3,49:1 |
| dfr | defining range dan proyeksinya | `#767eb2` | 232,0 | 54,0 | 5,00:1 |
| structure | swing, BOS, CHoCH, MSS | `#a184c3` | 267,6 | 59,9 | 6,12:1 |
| ssmt | divergensi lintas instrumen | `#cc8db5` | 321,9 | 65,9 | 7,45:1 |
| levels | gap, event horizon, CISD, pool, true open | `#89b7cf` | 200,6 | 72,0 | 9,02:1 |

Dihitung, bukan dipilih. Setiap rona minimal **43 derajat** dari demand-hijau
(154), supply-salmon (5), dan aksen kontrol emas (39), jadi tidak ada layer yang
bisa terbaca sebagai arah atau sebagai kontrol. L* naik sekitar enam poin per
keluarga supaya kelimanya tetap terpisah dalam greyscale - kontras teredup lawan
tercerah 2,5:1 - karena kira-kira satu dari dua belas pria punya defisiensi
merah-hijau dan rona saja tidak boleh menjadi seluruh sinyalnya. Saturasi ditahan
10% sampai 42%, di bawah 64-77% yang dipakai dua warna semantik: keduanya boleh
berteriak karena keduanya berarti sesuatu.

Urutan tangga L*-nya juga sebuah pernyataan. Grid paling redup karena ia konteks
tempat candle duduk. DFR berikutnya karena ia objek dengan bukti paling lemah di
kanvas dan tidak boleh terlihat seperti level terukur. Ray harga bernama paling
cerah karena itulah harga yang dibandingkan pembaca dengan candle.

Paletnya juga **mendokumentasikan dirinya di tempat layer dinyalakan**: setiap
baris menu layer membawa sepetak warna keluarga itu, dan lima detektor kotak
membawa dua petak, hijau dan merah, karena memang itu yang mereka gambar.

---

## 7. Risiko, jurnal, psikologi

| Butir | Status | Catatan |
|---|---|---|
| Entry buy dari discount, sell dari premium | **Ada sebagai bacaan, bukan sinyal** | Engine melaporkan di mana harga duduk di dalam rentang. Ia tidak pernah menyarankan entry |
| Target CE of London range | **Belum sebagai target otomatis** | Bahannya sudah ada, tinggal disambungkan |
| Partial di 2RR | **Belum** | |
| Layered entry, layer kedua ke BE | **Belum** | |
| Pencatatan RR aktual 50 sampai 60 sampel | **Belum** | Ini jurnal, bukan mesin gambar, tetapi ia satu-satunya butir di bagian ini yang **bisa diukur** dan layak dipertimbangkan |
| Jurnal emosi, rekam video, software lockout | **Di luar lingkup** | Bukan pekerjaan mesin gambar chart |
| Sentimen grup dan riset geopolitik | **Di luar lingkup** | |

---

## 8. Backtest yang Anda usulkan sendiri

Anda menuliskannya sebelum ada hasilnya, yang membuatnya **terdaftar lebih
dulu**, dan itu sebabnya ia dijalankan lebih dahulu daripada ide mana pun yang
saya usulkan.

> Mark 00:00 NY setiap hari, mark candle H4 jam 06:00, lalu hitung berapa kali H4
> kembali ke arah 00:00, dipisah kasus open di atas vs di bawah true day open.

**Status: Terukur null.**

Klarifikasi yang muncul saat menjalankannya: 00:00 NY dan "true day open" adalah
**level yang sama**, dan candle 06:00 yang Anda maksud adalah pembukaan **Q3**
siklus harian. Jadi ujinya sebenarnya "apakah Q3 menarik kembali ke arah
pembukaan Q2".

| Definisi "kembali ke arah" | Kohort | n | Laju | Kontrol | Margin | p |
|---|---|---|---|---|---|---|
| Menyentuh | buka di atas | 320 | 0,537 | 0,500 | +0,037 | 0,37 |
| Menyentuh | buka di bawah | 272 | 0,588 | 0,562 | **+0,026** | **0,59** |
| Menutup melewati | buka di atas | 320 | 0,250 | 0,253 | -0,003 | 1,00 |
| Menutup melewati | buka di bawah | 272 | 0,324 | 0,235 | +0,088 | 0,062 |
| Separuh jarak | buka di atas | 320 | 0,753 | 0,694 | +0,059 | 0,15 |
| Separuh jarak | buka di bawah | 272 | 0,798 | 0,765 | +0,033 | 0,44 |

Kontrolnya berpasangan di dalam candle yang sama: level cermin sejauh jarak yang
persis sama di sisi seberang pembukaan candle itu. Jarak, volatilitas, hari dan
instrumen dikunci lewat konstruksi.

Yang menjatuhkan hipotesisnya bukan satu angka, melainkan tiga hal sekaligus.
Selang kepercayaannya melintasi nol. Ketiga definisi "kembali ke arah" **saling
tidak sepakat**, dan definisi menutup-melewati berganti tanda antara dua kohort
dari split Anda sendiri, yang berarti koin dan bukan tepi. Dan tandanya
**terbalik** pada instrumen lain: emas tertokenisasi mengulang positif lemah,
tetapi Bitcoin -0,033 dan Ethereum -0,058.

> Laju mentah sekitar 55% itu tidak pernah mengukur tarikan ke tengah malam. Ia
> mengukur seberapa lebar sebuah candle empat jam emas.

Satu serpih yang jujur perlu disebut: 06:00 **memang** jam terbaik untuk emas di
antara sebelas jam yang diuji (+0,026 pada kohort terlemah). Tetapi itu satu jam
memenangi perbandingan sebelas arah pada p=0,59, yang persis seperti yang
dihasilkan derau, dan pada BTC 06:00 adalah jam **ketiga terburuk**. Tidak
dikejar.

Ini hipotesis arah **kedua belas** yang terdaftar lebih dulu dan gagal di proyek
ini. Levelnya boleh tetap digambar karena alasan lain; yang tidak berdiri adalah
klaim bahwa candle empat jam kembali kepadanya lebih sering daripada kebetulan.

---

## 9. Perbandingan dengan indikator rujukan di TradingView

Indikator yang dipakai pemilik: **Event Horizon - Multi-Tier Opening Gaps**,
penulis **Tango618**.

**Source-nya tidak bisa dibaca siapa pun kecuali penulisnya.** Halamannya
menyatakan sendiri closed-source, dan pemeriksaan DOM setelah login berhasil
memberi `code element present: 0`. Langganan premium tidak mengubah itu; script
Pine yang diproteksi memang menyembunyikan kode dari semua akun. Jadi
perbandingan di bawah ini dilakukan terhadap **output** yang digambarnya, bukan
terhadap kodenya.

### Yang dibaca dari chart preview-nya sendiri

Pada NASDAQ 100 E-mini futures 1 jam, harga 28.164,00, indikatornya menggambar
tabel ini:

| EV | Top | Bot | Dist |
|---|---|---|---|
| W | 29.206,75 | 28.580,75 | -730 |
| D | 28.768,00 | 28.561,50 | -501 |

ditambah label `EV STACK W+D 91%` pada wilayah yang bertumpang tindih, dan label
tepi `EV-W-1`, `EV-D-1`, `EV-D-2`, `CE-W`, `CE-D-1`, `CE-D-2`.

### Dua definisi yang berhasil didekode dari angkanya sendiri

> [!NOTE]
> Keduanya **direkayasa balik dari output yang dirender**, bukan dibaca dari
> source. Aritmetikanya cocok, tetapi tidak ada yang pernah memverifikasinya
> terhadap kode, dan itu harus ikut dikutip setiap kali angka ini dipakai.

**`Dist` adalah jarak bertanda dari harga sekarang ke titik tengah zona**, bukan
ke tepinya:

- W: titik tengah (29.206,75 + 28.580,75) / 2 = 28.893,75, lalu 28.164,00 -
  28.893,75 = **-729,75**, ditampilkan -730.
- D: titik tengah (28.768,00 + 28.561,50) / 2 = 28.664,75, lalu 28.164,00 -
  28.664,75 = **-500,75**, ditampilkan -501.

**Persentase STACK adalah tinggi tumpang tindih dibagi tinggi zona TERKECIL:**
irisan W dan D adalah 28.580,75 sampai 28.768,00, setinggi 187,25; zona terkecil
adalah D setinggi 206,50; 187,25 / 206,50 = **90,7%**, ditampilkan 91%. Membagi
dengan gabungan atau dengan zona terbesar memberi angka lain, jadi 91% hanya
memaku satu di antara tiga kemungkinan.

### Tabrakan nama Event Horizon, sekarang terkonfirmasi

Tabel di atas melaporkan **EV sebagai zona dengan Top dan Bot**, dan
menggambar `CE` sebagai garis terpisah. Jadi bagi Tango618:

| Istilah | Artinya di script itu | Padanan di sini |
|---|---|---|
| `EV-D-1`, `EV-W` | zona gap itu sendiri, per tier | `OpeningGap.top` dan `.bottom` |
| `CE-D-1`, `CE-W` | garis 50% zona itu | `OpeningGap.ce` |
| `Dist` | jarak harga ke CE | **diadopsi**, lihat di bawah |
| `EV STACK W+D` | irisan zona dua derajat | **diadopsi** |
| - | - | `event_horizons` kita, titik tengah antara dua gap bertetangga dalam urutan HARGA, **tidak ada padanannya di script itu** |

Artinya "Event Horizon" di script rujukan dan "event horizon" bacaan ICT yang
dipakai engine ini adalah **dua objek yang berbeda**, bukan dua nama untuk hal
yang sama. Docstring `gaps.py` sudah menyatakan tabrakan nama ini sebelum
pemeriksaan; sekarang ada buktinya dari render indikatornya sendiri.

### Lima tier di script itu bukan lima geometri

Deskripsinya menyebut NDOG, NWOG, NMOG, NYOG dan NQOG.

Diukur pada **29 pergantian bulan** emas 1 jam (13.725 bar, 2024 sampai 2026):
16 di antaranya tidak punya jeda sama sekali, karena pasar berdagang menembus
tengah malam di hari kerja. 13 punya jeda, dan **ketiga belasnya adalah akhir
pekan atau hari libur**, bukan penutupan yang diciptakan oleh pergantian bulan:

| Jeda | Berapa | Apa itu |
|---|---|---|
| 1 jam | 16 | tidak ada jeda, cuma interval bar |
| 50 sampai 53 jam | 10 | akhir pekan biasa, Jumat 16:00 ke Minggu 18:00 NY |
| 25 dan 32 jam | 3 | libur: Tahun Baru dua kali, dan Labor Day 2025 |

Pada kripto yang berdagang 24/7, **0 dari 54** pergantian bulan punya jeda sama
sekali, di dua instrumen.

> [!NOTE]
> Angka pertama yang saya tulis di sini adalah "3 dari 4", diambil dari jendela
> 2.000 bar. Sampelnya terlalu kecil dan angkanya menyesatkan ke arah yang salah.
> Kesimpulannya tidak berubah, tetapi dasarnya sekarang 29 pergantian bulan dan
> bukan 4, dan koreksinya dicatat alih-alih ditimpa.

Jadi NMOG bukan gap jenis baru, melainkan **label yang memilih NWOG mana yang
merupakan gap bulanan**. Dan dengan aturan pemilik sendiri, NWOG yang dipilih
adalah yang membuka siklus bulanan, yaitu Minggu 18:00 New York di minggu penuh
kedua, persis yang dihitung `quarters.py` sebagai Q2 derajat bulan.

Penolakan sebelumnya atas NMOG/NYOG karena "bukan geometri baru" **benar sebagai
alasan tetapi salah sebagai kesimpulan**: memberi label derajat pada NWOG yang
tepat adalah informasi nyata dan hampir tanpa biaya. Diadopsi sebagai label,
bukan sebagai kind kelima.

### Yang diadopsi dari perbandingan ini

| Objek | Status | Catatan |
|---|---|---|
| `Dist` ke CE | **Ada** | Aritmetikanya bereproduksi **eksak**, bukan sekadar sampai pembulatan: -729,75 dan -500,75 persis di float biner. Dilaporkan sebagai snapshot terhadap bar terakhir, bukan field pada objek gapnya, karena pita tidak bergerak tetapi jaraknya bergerak tiap tick |
| Ordinal per jenis, `D-1`, `W-2` | **Ada** | Dihitung per jenis, bukan lintas jenis. Dan ia **posisi dalam daftar**, jadi setiap gap sejenis bernomor ulang begitu ada yang lebih baru, bahaya tidak-final-saat-lahir yang sama dengan event horizon |
| `EV STACK` lintas derajat | **Ada** | Persentase 91% bereproduksi. Dua gap sejenis yang bertumpang tindih **bukan** stack; konstruknya soal derajat rendah mendarat di derajat tinggi |
| Label derajat NWOG | **Ada** | Diukur pada emas 13.725 bar: **29 label bulanan untuk 29 bulan data**, tepat satu per bulan, semuanya jatuh di Minggu 18:00 minggu penuh kedua. Label tahunan nol, karena 1 April selalu hari kerja di rentang itu |

> [!WARNING]
> Penyebut stack adalah **rekonstruksi, bukan kutipan**. Angka 91% memaku satu
> kandidat dan tidak menyingkirkan yang lain: dua pita yang sama memberi 29% bila
> dibagi gabungan dan 30% bila dibagi pita terbesar. Ketiga angka itu disimpan di
> `tests/test_gaps.py` supaya penukaran diam-diam gagal berisik.

Satu hal yang **tidak** diadopsi: penyapuan 1990 sampai 2050 menemukan 732 label
bulanan dan 17 label tahunan, dan **nol** akhir pekan yang memicu keduanya
sekaligus. Jadi urutan "tahun menang atas bulan" di kodenya bersifat defensif dan
tidak pernah benar-benar terpakai, dan itu dicatat alih-alih diberi tes tabrakan
yang tidak punya kasus.

### Tier horizon: retensinya bersumber, reduksinya belum

Pemilik mengoreksi pembacaan awal saya: indikatornya memakai **tiga NDOG
terakhir untuk event horizon harian dan tiga NWOG terakhir untuk yang mingguan**.
Angka tiga itu **dari dia langsung**, jadi ia satu-satunya bagian konstruk ini
yang bersumber dan bukan rekayasa balik.

**Bagaimana tiga gap menjadi satu Top dan satu Bot belum ketemu.** Diuji pada
instrumen dan instan yang sama dengan chart rujukannya, dan datanya sebanding:
harga kita Senin 27 Juli 10:00 NY 28.169,25 lawan 28.164,00 di chart-nya,
selisih 5 poin.

| Reduksi | D kita | W kita |
|---|---|---|
| **Dia** | **28.561,50 - 28.768,00** | **28.580,75 - 29.206,75** |
| `envelope` | 28.700,25 - 29.310,75 | 28.282,25 - 30.032,25 |
| `ce_span` | 28.719,75 - 29.300,25 | 28.438,38 - 29.963,25 |
| `newest` | 28.700,25 - 28.739,25 | 28.282,25 - 28.594,50 |
| `eh_span` | 28.919,63 - 29.227,38 | - |

Tidak satu pun mendekati, dan **28.561,50 maupun 28.768,00 bukan tepi gap mana
pun** yang kami deteksi di jendela itu. Jadi tersisa dua kemungkinan yang tidak
bisa dipisahkan dari satu tangkapan layar: reduksinya operasi yang belum dicoba,
atau deteksi gapnya memakai batas selain 17:00 dan 18:00 New York.

Yang dikirim: retensi tiga per jenis, dengan **reduksi sebagai parameter yang
bisa dipilih di menu**, bawaan `envelope`. Bawaan itu dinyatakan sebagai bacaan
paling polos dan **diketahui tidak cocok**, yang merupakan pernyataan lebih kuat
daripada bawaan yang tidak pernah diuji. Keempat kandidat beserta angkanya
disimpan di kode dan di tes, jadi begitu aturan aslinya datang, yang salah sudah
tercatat sebagai pernah dicoba.

### Papan waktu pemilik, divalidasi baris demi baris

Papan `POSKO 618` miliknya dibandingkan dengan grid engine. **Setiap baris cocok,
di kedua keadaan DST, sampai ke menit**: Monthly Minggu 18:00, Weekly Senin 18:00,
Daily 00:00, dan keempat sesi di 19:30, 01:30, 07:30, 13:30 New York. Konversi
+11 dan +12 jam ke WIB juga dicek langsung ke tzdata dan benar.

Baris `News/NFP 08:30` kini juga ada, lewat kalender ekonomi. Diperiksa terhadap
feed: setiap rilis USD pukul 08:30 New York jatuh tepat di 19:30 WIB, sesuai
papan Anda.

### Kalender ekonomi, dan apa yang tidak bisa dibelinya

Sumber yang dipakai: feed CDN ForexFactory, `nfs.faireconomy.media`. **Tanpa API
key, tanpa akun.** `robots.txt` host itu `Disallow:` kosong, jadi seluruhnya
diizinkan; situs `forexfactory.com` sendiri di balik Cloudflare challenge dan
tidak disentuh sama sekali.

| Sumber | Hasil uji | Kesimpulan |
|---|---|---|
| ForexFactory CDN | HTTP 200, 98 baris, tanpa key | **Dipakai** |
| Trading Economics guest | HTTP 410, akun guest dihentikan | Mati |
| FMP, kunci pemilik | `quote` 200, `treasury-rates` 200, tetapi kalender **403 dan 402** | Kuncinya valid, kalendernya berbayar |

Kunci FMP pemilik diuji dan **valid** - endpoint gratisnya menjawab 200 - tetapi
kalender ekonominya khusus dikunci: v3 menjawab 403 "Legacy Endpoint" dan stable
menjawab 402 "Restricted Endpoint". Kuncinya tidak disimpan di repo, karena
menyimpan kredensial yang tidak dipakai adalah risiko tanpa imbalan.

**Konsekuensi yang menentukan:** hanya minggu berjalan yang terbit. `nextweek`,
`lastweek`, `thismonth` dan `thisyear` semuanya 404. Jadi kalender ini cukup
untuk anotasi chart hidup dan **mustahil untuk backtest**, dan klaim "NFP kecil,
CPI manipulation, FOMC distribution" tetap belum bisa diuji. Itu batas yang
ditulis di kodenya, bukan disembunyikan: tidak ada parameter `history` yang tidak
bisa dipenuhi.

Dua sifat feed yang justru menguntungkan, keduanya diperiksa pada payload asli:
timestamp membawa offset UTC-nya sendiri, jadi tidak ada tebakan zona waktu; dan
**tidak ada field `actual` sama sekali**, jadi ia tidak bisa membocorkan hasil
mundur ke sebuah bar.

Dua hal terukur saat membangunnya. Host-nya **membatasi laju**: tiga sampai empat
permintaan dalam sekitar dua menit sudah menjawab HTTP 429, ditemukan dengan
melewatinya sekali, bukan dengan menyelidiki batasnya. Dan jendela yang tercakup
hari itu **4,65 hari, bukan tujuh**, jadi membaca jendela dari datanya sendiri
bukan kehati-hatian teoretis.

### Cacat yang hanya kelihatan dari chart-nya

Panel melaporkan lima rilis, chart menggambar dua. Yang hilang adalah tiga baris
CAD pukul 08:30 New York, yaitu 12:30 UTC: **tidak ada bar 1 jam yang dibuka pada
menit itu**, jadi `timeToCoordinate` menjawab null tiga kali tanpa bersuara. Ini
tidak tertangkap oleh satu pun angka; ia tertangkap karena garisnya dicari di
gambar.

Perbaikannya: penempatan dihitung di backend, tempat waktu bar-nya memang ada.
Setiap rilis membawa `bar`, yaitu bar tempat ia terjadi, dan `offset`, seberapa
jauh ke dalam bar itu. Chart mengalikan `offset` dengan jarak antar-bar, jadi
08:30 mendarat **di antara** candle 12:00 dan 13:00, bukan hilang. Diverifikasi
dengan crosshair, bukan dengan menaksir posisi label: tiga garis pada 17 Agustus
19:00 WIB, 18 Agustus 12:00 dan 19 Agustus 12:00, ketiganya tepat pada bar yang
seharusnya.

Rilis yang jatuh saat pasar tutup - baris akhir pekan, baris hari libur - tidak
punya bar untuk ditempati. Ia **dibuang dan dihitung** (`news_market_shut`),
karena menempelkannya ke bar terakhir sebelum lubang berarti menandai waktu yang
bar itu tidak pernah cakup.

## Three Drives, ditanya lalu diukur, dan ditolak dengan angka

Ditanya langsung: apakah pola **Three Drives** sudah ada, dan kalau belum apakah
harus dibangun. Jawabannya tidak, dan alasannya bukan selera.

**Tidak ada jejaknya di metode ini.** Seluruh folder disisir, dan disisir ulang
pada 26 Agustus 2026 setelah ia tumbuh: 3.261 baris di `Whatsapp/chat.md` dan
`Whatsapp/chat.txt`, empat file teks Discord, `Telegram/chat.txt`, dan 82 gambar
dibaca satu per satu. Nol
kemunculan untuk three drive, harmonic, ABCD, Gartley, butterfly, crab, bat,
Elliott, Wolfe, 0,618, 1,272, maupun 1,618. Tidak ada satu chart pun yang
memasang alat retracement Fibonacci. Angka yang terlihat seperti rasio di sana
adalah **setengah dan seperempat**: kelipatan deviasi standar 0 / -0,5 / -1 /
-1,5 / 2 / 2,5 pada gambar 25, 27, 30, dan kuartil dealing range 0,25 / 0,5 /
0,75 pada gambar 23 dan 42. Kosakata chart-nya seluruhnya ICT dan Daye.

**Bukan bagian ICT, SMC, atau Quarterly Theory.** Glosarium ICT lengkap tidak
memuatnya; satu-satunya entri Fibonacci di sana adalah OTE. Pustaka konsep SMC
menempatkan seluruh harmonic di kategori terpisah dari SMC. Quarterly Theory
tidak punya pola geometri harga bernama sama sekali. "ICT Power of Three" adalah
tabrakan nama, bukan pola yang sama.

**Sumbernya sendiri sedang meninggalkannya.** Daftar pola resmi di
harmonictrader.com hari ini memuat sepuluh pola dan Three Drives **tidak ada di
dalamnya**; halamannya masih hidup tetapi sudah lepas dari daftar. Teks penuh
Harmonic Trading Vol.3 milik Carney: **nol** kemunculan (kalibrasi: AB=CD 144
kali, Gartley 52, Shark 48). Vol.2: satu kemunculan, dan itu bukan definisi.
Slide CMT APAC 2021 miliknya: tidak ada.

**Angka pusatnya tidak pernah diterbitkan.** Titik sengketanya bukan hiasan.
Buku Carney 1999 mengukur ekstensi dari **drive sebelumnya** ("the 1.27 of the
prior drive"); Pesavento dan hampir semua implementasi mengukurnya dari
**retracement sebelumnya**. Dengan retracement 0,618, kedua bacaan itu meletakkan
target sekitar dua pertiga panjang leg berjauhan, jadi detektor yang memakai satu
bacaan menolak pola yang diterima bacaan lain. Tidak ada satu sumber pun yang
menerbitkan **toleransi** numerik: Carney menulis "usually not be exact" di
bukunya dan "precisely" di situsnya, dan contoh kerjanya sendiri melenceng 3%,
4%, dan 8,5% sambil tetap disebut valid. Satu-satunya implementasi yang
mengoperasionalkannya menjadikan toleransi sebagai **slider pengguna**. Tidak ada
sumber yang menerbitkan hit rate, ukuran sampel, atau backtest; Bulkowski tidak
memasukkannya ke katalog sama sekali.

### Lalu bentuknya diukur, tanpa mengadopsi satu rasio pun

Rasio boleh tidak diterbitkan, tetapi **klaimnya** bisa diuji. Tiga dorongan
searah dengan ekstrem yang terus memanjang: apakah setelah itu pasar berbalik
lebih sering daripada pivot biasa? Pertanyaan itu tidak butuh angka Fibonacci,
tidak butuh toleransi, dan tidak butuh kode baru selain `swings()` yang sudah
ada. `tools/three_pushes.py`, 235.158 bar, lima deret:

```
python -m tools.three_pushes --bars 50000   --series "mt5:XAUUSD@15m,mt5:XAUUSD@1h,PAXGUSDT@1h,BTCUSDT@1h,ETHUSDT@1h"
```

| Deret | n pola | balik setelah tiga dorongan | n dasar | balik pada pivot mana pun | lift |
|---|---|---|---|---|---|
| mt5:XAUUSD 15m | 1730 | 35,5% | 7796 | 48,3% | **-12,8%** |
| mt5:XAUUSD 1h | 1096 | 33,5% | 5271 | 48,0% | **-14,6%** |
| PAXGUSDT 1h | 1518 | 33,5% | 7935 | 45,5% | **-12,0%** |
| BTCUSDT 1h | 1534 | 31,6% | 8173 | 45,9% | **-14,3%** |
| ETHUSDT 1h | 1550 | 33,0% | 8156 | 46,1% | **-13,1%** |
| **gabungan** | **7428** | **33,5%** | **37331** | **46,7%** | **-13,2%** |

Lima dari lima negatif, p di bawah 0,0001.

> [!IMPORTANT]
> Hasilnya bukan null, dan itu justru **lebih keras** daripada null. Tiga
> dorongan yang memanjang diikuti pembalikan **lebih jarang** daripada pivot
> rata-rata, selisih 13,2 poin. Bentuk itu menyeleksi pasar yang sedang tren,
> jadi yang menyusulnya lebih banyak kelanjutan. Detektor yang menggambarnya
> sebagai sinyal pembalikan akan menunjuk **arah yang salah**, dan tidak ada
> pilihan toleransi yang bisa membetulkan sebuah tanda.

Satu koreksi atas pengukuran ini sendiri, karena ia bagian dari catatannya:
versi pertama `three_pushes.py` memasang polaritasnya terbalik. Ia menanyakan
apakah high berikutnya gagal melampaui high sebelumnya, bukan apakah low
berikutnya jebol, dan melaporkan +13,7% yang terlihat seperti temuan kuat. Dua
bacaan itu menghasilkan lift besar yang sama-sama signifikan; hanya satu yang
menyangkut klaim polanya. `tests/test_three_pushes.py` memaku polaritas itu pada
zigzag buatan tangan yang jawabannya aritmetika, termasuk kasus cerminnya, karena
tanda yang salah dengan percaya diri lebih buruk daripada tidak ada angka.

### Kenapa tetap tidak dibangun walau angkanya kuat

Karena arahnya berlawanan dengan polanya. Yang terukur di sini adalah bahwa tiga
dorongan memanjang adalah petunjuk **kelanjutan**, dan itu bukan objek baru: gerbang
`departure` dan momentum 20 bar yang sudah lolos walk-forward mengukur hal yang
sama dan mengukurnya lebih awal. Menggambar kotak Three Drives untuk menyampaikan
"tren sedang berjalan" berarti menambah tinta untuk informasi yang sudah ada di
kanvas, dengan nama yang menyuruh pembaca melakukan kebalikannya.

| Butir | Status | Catatan |
|---|---|---|
| Pola Three Drives | **Ditolak, terukur** | Tidak ada di metode pemilik, bukan ICT/SMC/Daye, toleransinya tidak pernah diterbitkan, dan bentuknya terukur berlawanan arah pada lima deret (lift -13,2%, p<0,0001) |

---

## Koreksi dari Bang Nas ICT, 20 Agustus 2026

Dua koreksi, dari praktisi dan bukan dari model bahasa. Keduanya diverifikasi
terhadap kode sebelum dikerjakan, dan satu di antaranya ternyata bukan yang
disangka.

### 1. "True open masih missing quartery cycle sm quadrennial cycle"

Aturannya, kata beliau sendiri:

> Quarterly cycle: Q1 jan hingga maret, Q2 april hingga june, Q3 juli hingga sep,
> Q4 october hingga december.
>
> Quadrennial: 1 taun = satu cycle. Paling gampang ingat, q2 = PILPRES Amerika.

**Siklus kuartalan sudah ada, dan namanya `year`.** Derajat `year` memotong di 1
Januari, 1 April, 1 Juli, dan 1 Oktober, jadi Q1 Jan-Mar sampai Q4 Okt-Des sudah
persis seperti yang dimaksud. Yang hilang cuma satu tingkat di atasnya.

**Siklus empat tahunan memang tidak ada, dan sekarang ada.** Pemilu presiden AS
selalu jatuh di tahun yang habis dibagi empat, jadi jangkarnya fakta dan bukan
parameter yang dicocokkan: `year % 4 == 0` menamai Q2, Q1 setahun sebelumnya, Q3
setahun sesudahnya, Q4 dua tahun sesudahnya. Siklus yang memuat 2026 adalah Q1
2023, Q2 2024, Q3 2025, Q4 2026. Terverifikasi juga untuk 2028.

Derajat ini masuk `ALL_DEGREES` dan **sengaja tidak** ke `DEGREES`, alasan yang
sama seperti `nano` tetapi terbalik arahnya: `pools.py` membaca `DEGREES` sebagai
rantai induk berurutan dan menganggap `DEGREES[0]` akar tanpa induk, jadi
menyisipkan di depan akan diam-diam memberi derajat `year` sebuah induk dan
mengubah perilaku file itu dari dalam file ini.

**Dan true open-nya ternyata tidak bisa ada sama sekali.** Ini temuan yang lahir
dari mengerjakannya. Q2 kuadrennial dibuka **1 Januari**, dan pasar tutup 1
Januari setiap tahun. Aturan ketat proyek ini - sebuah level hanya ada bila ada
bar yang dibuka **tepat** di batasnya - terukur menghasilkan **nol** level
kuadrennial pada sepuluh tahun bar 1 jam emas broker. Ketiga batas Q2 di jendela
itu (2016, 2020, 2024) tidak punya bar. Bukan kelalaian, melainkan mustahil
secara konstruksi.

Jadi ada `approximate_true_opens`, **mati secara bawaan**, yang mengambil bar
pertama **di atau setelah** batas dan menandainya. Jangkauannya dibatasi 120 jam,
diukur dari penutupan nyata terpanjang di feed ini: 96 jam, minggu Natal dan Tahun
Baru 2016 dan 2017 plus Paskah 2019, dengan Paskah biasa 74 jam dan akhir pekan
biasa 65 jam. Dengan itu menyala, derajat kuadrennial menghasilkan dua level, 19
dan 18 jam setelah batasnya. Derajat `year` naik dari 5 ke 10 dari 10.

| | ketat | dengan approximate |
|---|---|---|
| quadrennial, 10 tahun emas 1 jam | **0** level | 2 level, lag 19 dan 18 jam |
| year, jendela yang sama | 5 level | 10 level, 5 di antaranya ditandai |

Level approximate digambar **putus-putus, lebih redam, dan diberi `~`** - konvensi
yang sama yang sudah dipakai band gap yang tepinya tidak bisa diberikan bar.
Alasannya bukan kerapian: level perkiraan dan level terukur tidak boleh terlihat
sama.

Dua cacat lahir dari pekerjaan ini dan keduanya ditemukan dengan melihat chart,
bukan angka:

- Pengaman "batas harus di dalam jendela" yang saya tulis sendiri ternyata
  **berlebihan sekaligus salah**: ia menolak justru kasus yang fitur ini dibuat
  untuk melayani, batas 1 Januari dengan bar pertama 2 Januari. Batas jangkauan
  120 jam sudah menolak kasus yang mestinya ditolak.
- Ray-nya **tidak tergambar sama sekali**. Skala waktu diindeks per BAR, jadi ia
  menjawab null untuk instan yang tidak ada bar-nya - dan batas level approximate
  memang instan tanpa bar. Delapan level kembali dari API dan pane harga
  menggambar nol. Ini kelas cacat yang sama dengan penempatan rilis berita yang
  sudah pernah diperbaiki di repo ini, dan perbaikannya sama: backend yang punya
  waktu bar menyebut bar mana lewat field `bar`, kanvas tidak menurunkannya
  sendiri.

### 2. SSMT harus dibaca terhadap premium/discount, dan itu belum terwire

Pesan beliau:

> Yup, dan FVG/OB/REQL/REQH/CISD semuanya harus dalam premium kalo mau sell,
> harus dalam discount kalo mau buy.
>
> Kalo ssmt terjadi di luar premium/discount, itu bisa kita pake buat tentuin DOL.
>
> Kalo DOL di premium, dan SSMT terjadi di discount, itu kita bisa gunain sebagai
> continuation ke arah DOL kita. Walaupun ssmt itu bearish misalkata ya, ada
> konfirmasinya segala, tapi kita bisa ekspektasi ssmt bearish itu fail untuk
> menjadi "inversed" ke arah dol kita.
>
> Entry di SSMT, exit di SSMT.

Zonelab punya ketiganya - premium/discount lewat `dealing_range.py`, likuiditas
tegak lewat `liquidity.dol_candidates`, dan SSMT - dan **tidak menyilangkan satu
pun**. `grep premium app/ssmt.py` mengembalikan nol.

Sekarang setiap divergensi membawa `range_pos`: posisi ekstremnya sendiri di
dealing range yang **bisa diketahui pada bar tempat ia tercetak**, 0 di dasar
rentang dan 1 di puncaknya. Dibaca di `time_to`, bar ekstrem yang bersangkutan,
dan bukan di `knowable_at` yang bisa satu kuartal lebih lambat - itu dua
pertanyaan berbeda dengan rentang yang sudah bergeser. Tag di kanvas membawa satu
huruf: `P`, `D`, atau `EQ` untuk dua kuartil tengah, dan **tidak ada** ketika
rentangnya belum terkonfirmasi. Terukur pada 2000 bar 1 jam emas lawan perak di
derajat hari: 88 dari 99 divergensi membawa posisi, 11 pertama tidak, dan itu
persis warm-up-nya.

Bacaannya juga sampai ke panel, bukan cuma ke kanvas: tiga hitungan premium /
equilibrium / discount plus `unknown` yang dipisah dan tidak dilipat ke
equilibrium, karena `unknown` itu warm-up rentangnya. Terukur pada seri yang sama:
24 premium, 33 equilibrium, 31 discount, 11 unknown.

Mengerjakan itu membongkar satu celah lagi: **`meta["ssmt"]` sudah diisi backend
sejak layer ini dikirim dan frontend tidak pernah mendeklarasikan bentuknya.**
Kunci JSON tambahan tidak merusak TypeScript, jadi satu-satunya overlay yang bisa
gagal karena alasan eksternal - partner yang tidak dibawa provider - justru satu-
satunya overlay yang kegagalannya tidak bisa ditampilkan panel. Sekarang
`found`, `drawn`, `grid`, `source`, dan `error` semuanya tampil.

> [!WARNING]
> **Dilaporkan, tidak pernah diskor, dan tidak ada field verdict di sebelahnya.**
> Peringatan yang sama yang sudah dibawa `mark_dealing_range` berlaku kata per
> kata di sini: posisi rentang mentah tampak seperti temuan terkuat di proyek ini
> (AUC 0,648 dan 0,581) sampai dipisah per sisi, dan ternyata itu drift naik di
> sampel. Bagian "continuation ke arah DOL" dari pesan di atas **tidak** dibangun
> sebagai klaim arah, karena dua belas hipotesis arah pre-registered sudah gagal
> di sini dan `dol_candidates` sendiri menolak menamai satu sisi sebagai draw.
> Yang dibangun adalah bacaannya; kesimpulannya tetap milik pembaca.

### Yang TIDAK dikerjakan dari percakapan itu, dan kenapa

Komentar Gemini di percakapan yang sama sebagian besar prosa retail generik dan
memuat satu kekeliruan tentang produk ini: ia menduga "SSMT" adalah nama kustom
script pihak ketiga di TradingView. Itu Zonelab, dan indikator di gambar itu
punya pemilik repo ini sendiri. Aritmetika zona waktunya benar (WIB UTC+7 lawan
New York EDT UTC-4 memang 11 jam, dan 00:00 New York memang 11:00 WIB), dan
aritmetika kuadrennialnya juga benar. Yang tidak diadopsi adalah bingkai
"win rate tinggi", "konfirmasi absolut", dan "probabilitas di atas rata-rata":
tidak satu pun angka itu diukur di mana pun, dan menuliskannya ke dalam UI
proyek ini akan melanggar hal yang paling dijaga di sini.

`REQH` dan `REQL` yang beliau sebut sebagai objek kelas satu **sudah dibangun**
pada 21 Agustus 2026. Dua aturan terbitan yang bertentangan itu tidak
diselesaikan dengan jalan tengah karangan: yang memakai
`0.01 x (tinggi - rendah seluruh data)` ditolak karena membuat toleransi jadi
fungsi dari jumlah bar yang dimuat pembaca, dan penolakannya terukur lewat
`test_an_equal_high_shelf_never_moves` yang gagal begitu aturan itu dipasang.
Uraiannya di `docs/QA-PRODUKSI.md` bagian 13.

---

## Referensi Quarterly Theory kedua, dan aturan DFR fase yang diukur lalu gagal

Diserahkan 2 September 2026: sebuah tool di `quarter-sequence.vercel.app` plus
dua baris aturan, dengan bukti satu chart TradingView (BTC 1h Binance,
Tango618).

    Accumulation/Consolidation DFR  ->  Manipulation Targets
    Manipulation DFR                ->  Distribution Targets

### Apa isi referensinya

Bukan dokumen. Satu file HTML 91 KB dengan logika inline, judul "QT Sequence
Timeline". Yang bisa diambil darinya tabel degree dan tabel penamaan true open,
plus satu konsep yang kita tidak punya.

**Sebelas degree lawan delapan milik kita.** Panjang quarter-nya cocok satu per
satu di tempat keduanya punya:

| Milik kita | Panjang quarter | Referensi | Panjang quarter | True open kita | Milik mereka |
|---|---|---|---|---|---|
| `quadrennial` | 1 tahun | QUADRENNIAL | 365 d | **TQO** | **T4YO** |
| `year` | 92,04 d | YEARLY | 91 d | TYO | TYO |
| tidak ada | - | **QUARTERLY** | 22,75 d | - | **TQO** |
| `month` | 7,0 d | MONTHLY | 7 d | TMO | TMO |
| `week` | 1,0 d | WEEKLY | 1 d | TWO | TWO |
| `day` | 6 h | DAILY | 6 h | TDO | TDO |
| `session` | 90 min | 90MIN | 90 min | TSO | TSO |
| `micro` | 22,5 min | MICRO | 22,5 min | T90mO | TMSO |
| `nano` | 5,625 min | NANO | 5,625 min | TnO | TNO |
| tidak ada | - | **PICO** | 1,40625 min | - | TPO |
| tidak ada | - | **FEMTO** | 21,09375 s | - | TFO |

> [!WARNING]
> **`TQO` berarti dua hal yang berlawanan.** Di engine ini ia quadrennian,
> empat tahun. Di referensi ia QUARTERLY, cycle 91 hari, dan yang empat tahun
> dinamai `T4YO`. Komentar di `frontend/src/components/session-primitive.ts`
> sudah mengantisipasi tabrakan ini sebelum referensi ini ada; sekarang ada
> sumber luar yang menyelesaikannya.

Tiga degree tidak ada di kita: satu di tengah (QUARTERLY) dan dua terdalam
(PICO, FEMTO). Satu konsep juga tidak ada: referensinya mengelompokkan kuarter
ke **tiga tipe**, `Q4/1`, `Q2`, `Q3` (Q4 dan Q1 satu tipe), lalu menamai
runtun kuarter bersarang lintas degree yang tipenya sama sebagai
**N-stage sequence**.

### Aturan DFR-nya tidak setuju dengan kode kita

`app/quarterly.py:defining_range` mengambil DFR dari **Q1 selalu**. Tapi profil
menentukan fase mana yang Q1:

| Profil | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| AMDX | akumulasi | manipulasi | distribusi | X |
| XAMD | X | akumulasi | manipulasi | distribusi |

Jadi di bawah XAMD, "Accumulation DFR" menurut aturan itu adalah DFR Q2 dan
kita memberikan DFR Q1. Bukan kasus pinggiran: di populasi yang diukur,
**XAMD 1021 cycle lawan AMDX 474** di degree day, jadi ia mengenai dua pertiga
cycle.

### Diukur, dan gagal di keenam sel

Praregistrasi `tools/phase_targets.py`, hasil `docs/phase_targets.json`.
Populasi disalin dari `dfr_outcomes.py`: mt5 XAUUSD, BTCUSD, ETHUSD, EURUSD,
1 jam, 20.000 bar, degree day dan week. 22.550 level dari 1.284 cycle. Outcome:
apakah level itu tersentuh **di dalam jendela kuarter targetnya**, bukan dalam
96 bar. Kontrol per-event jitter, tanpa shuffling. Critical t ber-Bonferroni
2,638 atas 6 grup, ambang efek +3,0pp.

| Arm | Degree | Cycle | Delta | t | Walk-forward |
|---|---|---|---|---|---|
| `q1_to_manip` | day | 1109 | -0,443pp | -1,42 | 4/8 |
| `q1_to_manip` | week | 173 | -0,169pp | -0,28 | 2/8 |
| `accum_to_manip` | day | 1109 | -0,278pp | -0,77 | 2/8 |
| `accum_to_manip` | week | 175 | -0,929pp | -1,15 | 2/8 |
| `manip_to_distrib` | day | 1109 | **-1,864pp** | **-4,35** | **0/8** |
| `manip_to_distrib` | week | 175 | -0,643pp | -0,67 | 3/8 |

**Nol lulus, dan keenamnya bertanda negatif.** Satu di antaranya menyeberang
ambang Bonferroni ke arah negatif: `manip_to_distrib` di degree day, t = -4,35
dengan delapan dari delapan fold negatif (-0,899 sampai -3,231). Ekstrem DFR
kuarter manipulasi tersentuh **lebih jarang** di kuarter distribusi daripada
level placebo di jarak sebanding. Itu temuan terbalik, bukan nol.

### Dan penyempurnaan fase-nya justru lebih buruk

Perbandingan berpasangan cycle demi cycle antara membaca DFR dari kuarter
akumulasi dan membacanya dari Q1 selalu:

| Degree | Cycle | Delta | t | Berbeda di |
|---|---|---|---|---|
| day | 1109 | **-2,705pp** | **-3,90** | 310 level |
| week | 173 | -2,601pp | -1,32 | 65 level |

Negatif berarti membaca dari kuarter akumulasi **kalah** dari membaca dari Q1
selalu, dan di degree day itu menyeberang ambang. Jadi ketidaksesuaian di atas
terjawab: implementasi kita yang sekarang bukan yang salah.

### Rig-nya dibuktikan bisa hijau

Nol pemenang tanpa pernah menunjukkan pemenang seperti apa yang bisa dilihat
adalah laporan tentang diamnya rig, bukan diamnya pasar. `--oracle` menambahkan
arm yang mengambil levelnya dari ekstrem kuarter target itu sendiri, yang
berarti ia melihat masa depan: **+32,856pp, t = +29,33, 8 dari 8 fold**, dan ia
mendarat di `passes`.

### Yang belum dijawab

- Arah tidak diuji. Tercapai adalah tercapai; siapa yang lebih dulu tersentuh
  antara high dan low tidak ditanyakan, karena aturannya tidak menyatakannya.
- Level ekstensi 0,5 dan 1,0 tinggi DFR bukan pertanyaan studi ini; itu punya
  `dfr_outcomes.py`, sudah dijalankan.
- **Aturan pertiga itu sendiri masih single-sourced.** `app/quarterly.py`
  mencatatnya: satu fetch yang merangkum, dikuatkan hanya oleh situs penulisnya,
  satu suara dua kali. Mengukur konsekuensi sebuah aturan tidak memperbaiki
  provenance aturannya.
- Tiga degree yang tidak kita punya dan konsep N-stage sequence belum diport,
  dan tidak ada angka apa pun untuk keduanya di sini.

## Referensi Quarterly Theory ketiga, dan grid 90 menit yang akhirnya terjawab

Diserahkan 11 September 2026: `quarterly-theory-a-z-guide-v1-1.pdf`, 80 halaman,
Oracle Insights (Bucko), disebut v1 dan diposisikan sebagai "Daye's Framework"
di Bagian Satu plus lapisan penulisnya sendiri di Bagian Dua sampai Sembilan.

> [!IMPORTANT]
> **Nol angka di 80 halaman.** Dokumen ini memakai "very high probability",
> "rarely fails" dan "holds up remarkably well" tanpa satu pun n, t, atau
> tingkat dasar. Ia juga dokumen penjualan: lima indikator berbayar, satu prop
> firm, satu jurnal AI, satu membership. Itu tidak membuat konsepnya salah, dan
> tidak boleh membuat satu pun di antaranya lewat gerbang tanpa diukur di sini.
> Nilainya ada di dua tempat lain: ia **sumber kedua** untuk aturan yang selama
> ini bersuara satu, dan ia menyelesaikan satu perselisihan yang sudah tercatat
> di repo ini.

### Temuan tunggal terbesar: grid 90 menit itu bukan perselisihan

`docs/QT-CHECKLIST.md` bagian 2.1 mencatat "enam divergensi", dan menyebut yang
pertama sebagai yang terbesar: batas kuarter repo ini berbeda 90 menit dari
grid sumbernya. Konsekuensinya mahal, dan masih berjalan sampai hari ini: kolom
`qt_sequence` dan `qt_sequence_src` dihitung dua-duanya, dan sisi MQL5 sengaja
memakai grid yang lain supaya kedua venue mengukur objek yang sama.

Dokumen ini menyelesaikannya, dan aritmetikanya bisa diperiksa siapa pun:

| Sesi | Batas kuarter repo | "Grid sumbernya" di QT-CHECKLIST | Selisih |
|---|---|---|---|
| Q1 Asia | 18:00 NY | 19:30 NY | +90 menit |
| Q2 London | 00:00 NY | 01:30 NY | +90 menit |
| Q3 NY AM | 06:00 NY | 07:30 NY | +90 menit |
| Q4 NY PM | 12:00 NY | 13:30 NY | +90 menit |

Keempatnya tepat +90 menit, dan 90 menit adalah panjang satu kuarter dari sesi
6 jam yang dibagi empat. Jadi keempat angka itu bukan batas sesi, melainkan
**Q2 dari tiap sesi**, yaitu true open sesi itu. Halaman 9 dokumen ini
menyatakannya langsung: Asia 19:30 EST "(Q2 of Asia)", London 01:30 "(Q2 of
London)", NY AM 07:30 "(Q2 of AM session)", dan true open harian 00:00 NY. True
open harian di 00:00 hanya mungkin kalau Q1 harian berjalan 18:00 sampai 00:00,
yang persis grid repo ini.

Dan repo sudah menggambar keempatnya. Diukur 11 September 2026 lewat
`/api/draw` dengan `session.true_opens: ["day","session"]` pada XAUUSD 15m:

| Degree | True open, waktu New York |
|---|---|
| `day` | 00:00 |
| `session` | 01:30, 07:30, 13:30, 19:30 |

Baris kedua itu daftar yang sama persis dengan kolom "grid sumbernya". Jadi
kedua kolom itu tidak pernah mengukur dua grid; mereka mengukur satu grid dan
satu set true open di atasnya, dengan satu di antaranya salah nama.

> [!WARNING]
> Ini BELUM boleh dibaca sebagai "hapus `qt_sequence_src`". Yang terbukti di
> sini soal penamaan dan aritmetika, bukan soal hasil: kalau kedua kolom itu
> sudah pernah memberi angka yang berbeda, perbedaannya harus dijelaskan dulu.
> Yang berubah cuma statusnya: dari "dua grid yang bersaing, pilih setelah
> mengukur" menjadi "satu grid, plus lapisan true open yang sudah kita punya".

### Aturan pertiga DFR TETAP bersuara satu, dan saya sempat salah menyebutnya

> [!CAUTION]
> **Koreksi, ditulis di tempat kesalahannya dibuat.** Bacaan pertama saya atas
> dokumen ini menyebut provenance aturan pertiga naik "dari satu suara jadi
> dua". Itu salah. Dokumen ini karya **Bucko / Oracle Insights**, dan
> `app/quarterly.py` sudah menamai persis penulis itu sebagai sumber aturan
> pertiga, lengkap dengan `oracleinsights.io`. Jadi ini suara yang sama untuk
> ketiga kalinya, bukan sumber kedua. Butir terbuka di bagian sebelumnya, "satu
> fetch yang merangkum, dikuatkan hanya oleh situs penulisnya, satu suara dua
> kali", **masih terbuka** dan sekarang berbunyi satu suara TIGA kali.

Yang dokumen ini benar-benar tambahkan adalah presisi implementasi, bukan
independensi: tabel durasi per cycle yang sebelumnya harus disimpulkan.

| Cycle | Panjang Q1 | Buang sepertiga pertama | Tandai dari |
|---|---|---|---|
| Daily (Asia) | 6 jam | 2 jam | jam ke-2 sampai tengah malam |
| 90-Min | 90 menit | 30 menit | menit ke-30 sampai habis |
| Micro | 22,5 menit | 7,5 menit | menit ke-7,5 sampai habis |

Angka-angka itu cocok dengan `app/quarterly.py:defining_range` baris per baris,
jadi implementasi kita memang membaca aturannya dengan benar. Provenance-nya
tidak bergerak. Hasil pengukurannya juga tidak berubah: DFR tetap `Terukur null`
di enam sel, dan `manip_to_distrib` di degree day tetap terbalik pada t = -4,35.

Satu hal yang tetap berguna meski suaranya sama: soal jangkar, dokumen ini
berbunyi "Q1 is always the first choice. Q2 is the fallback", dipakai hanya
kalau Q1 ekspansi bukan akumulasi. Repo sudah mengukur jangkar akumulasi KALAH
dari Q1-selalu (-2,705pp, t = -3,90 di degree day). Jadi penulis aturan dan
angka kita sepakat, dan referensi KEDUA (`quarter-sequence`, Tango618) yang
mengusulkan jangkar akumulasi adalah pihak yang tidak didukung keduanya.

### Satu hal yang sudah punya primitifnya dan tinggal satu predikat

Dokumen ini menamai **QT Killzone**: jendela waktu di mana dua kuarter atau
lebih dari cycle berbeda tumpang tindih DAN bernomor sama. Contoh yang dipakai
penulisnya: 09:00-10:30 NY adalah Q3 daily sekaligus Q3 dari cycle 90 menit di
dalamnya, jadi "Q3 of Q3".

Itu konsep yang sama dengan "N-stage sequence" milik referensi kedua, yang
dicatat sesi lalu sebagai belum diport. Referensi kedua datang dari
`quarter-sequence.vercel.app` (Tango618), penulis yang berbeda, jadi **untuk
butir ini** dua suara yang berbeda memang menamai hal yang sama - tidak seperti
aturan pertiga di atas. Dan primitifnya **sudah ada**: `app/sequence.py:chain()`
mengembalikan nomor kuarter tiap degree ("2-1-3"), dan `occurrences()` sudah
menghitung frekuensi tiap rantai plus tingkat dasarnya. Yang belum ada cuma
predikat "semua digit sama" dan pengukurannya.

Ini kandidat termurah di halaman ini: satu fungsi di atas primitif yang sudah
diuji, dan rig pengukurnya sudah berdiri.

### Buku besar per butir

| # | Butir | Status | Catatan |
|---|---|---|---|
| 1 | Cycle stack fraktal, quadrennial sampai micro | **Ada** | `app/quarters.py`, 9 degree lawan 8 di dokumen ini |
| 2 | Fungsi kuarter AMDX dan XAMD | **Ada** | `quarterly.profile`, manipulasi Q2 di AMDX dan Q3 di XAMD, cocok baris per baris |
| 3 | Weekly cycle Senin sampai Kamis, Jumat bukan Q5 | **Ada** | degree `week` panjang kuarter 1,0 hari |
| 4 | Fungsi Jumat sebagai rebalancing ke true week open | **Belum** | tidak ada aturan Jumat di mana pun |
| 5 | Distortion week sebagai Q0 | **Belum** | `quarters.py` hanya melabeli Q1 sampai Q4 |
| 6 | True open sebagai open Q2 | **Ada** | terukur di 00:00 dan 01:30/07:30/13:30/19:30 NY |
| 7 | Stacked true opens | **Ada** | `qt.py`, `quarters.py`, `checklist.py`, `models/plan.py` |
| 8 | SSMT, dua kuarter berurutan, ekstrem, berbasis wick | **Ada** | `app/ssmt.py` |
| 9 | Triad, termasuk triad minyak CL/RBOB/ULSD | **Ada** | `app/triad.py`; ketiga simbol minyak ada di registry |
| 10 | Filter true open pada SSMT | **Ada** | `qt.true_opens_agree` |
| 11 | Multi-stage SSMT | **Ada** | `ssmt.two_stage` |
| 12 | PSP | **Terukur null** | `app/psp.py`; 48 sel nol di `docs/psp_outcomes.json`, termasuk lengan yang mengisolasi kontribusi SSMT-nya |
| 13 | DFR, aturan pertiga | **Terukur null** | provenance TIDAK naik: dokumen ini penulis yang sama; hasilnya tidak berubah |
| 14 | tCISD | **Sebagian** | `app/tcisd.py` ada dan cocok dengan aturan dokumen ini; klaim di register pernah salah label baseline, jadi angkanya belum berdiri |
| 15 | Pita deviasi standar DFR, manipulasi -0,5 dan distribusi +2,0 sampai +2,5 | **Belum** | `dfr_outcomes.py` mengukur ekstensi 0,5 dan 1,0; pita +2,0/+2,5 belum pernah diuji |
| 16 | QT Killzone, kuarter senomor bertumpuk lintas degree | **Ada** | `sequence.killzones()`, param `session.killzones`. Tingkat dasar 0,25 dan 0,0625 dikunci di selftest. BELUM diukur lawan outcome |
| 17 | Time-based premium/discount dari range kuarter HTF sebelumnya | **Ada** | `quarterly.time_premium_discount()`, param `session.premium_discount`. Tanpa parameter sama sekali, jadi bisa diadu langsung lawan `dealing_range.py`. BELUM diukur |
| 18 | Daily bias dari tanda tangan closure, continuation/reversal/inside | **Belum** | `olhc.py` menjawab pertanyaan lain (struktur rejection satu candle) dan sudah terukur identitas |
| 19 | Draw on liquidity, empat sumber | **Ada** | `draw_on_liquidity` di `/api/draw` |
| 20 | Hidden SSMT berbasis body | **Ada** | `ssmt(basis="body")`, param `checklist.ssmt_hidden`. Event di-stamp `basis` dan digambar bertitik supaya tak pernah jadi satu populasi dengan wick. BELUM diukur |
| 21 | SMT Fill, tiga varian | **Ada** | layer `smt_fill`, `app/smt_fill.py`. Menumpang basket aligned yang sudah di-fetch `ssmt`, jadi nol fetch tambahan. BELUM diukur |
| 22 | itCISD | **Belum** | |
| 23 | True Order Block | **Belum** | butuh turun satu timeframe di dalam candle PSP |
| 24 | RTO, revolving true open | **Belum** | true open hanya dari Q2; kuarter tempat SSMT lahir tidak diberi level |
| 25 | SMT Market Structure Shift | **Belum** | |
| 26 | First presented FVG setelah SSMT | **Belum** | gap sudah ada, urutan "pertama setelah SSMT" belum |
| 27 | PSP soup dan aturan aset lebih lemah | **Belum** | `psp.polarity` dan `in_same_candle` ada, pemilihan aset belum |
| 28 | PSP 6 jam | **Ditolak** | 6h bukan interval yang ditawarkan aplikasi ini, dan menambah satu interval untuk satu bacaan bukan tukar yang sepadan |
| 29 | Anticipating the 9:30 open | **Belum** | `judas.py` menjawab pertanyaan tetangga, bukan yang ini |
| 30 | Intermarket rotation, forex konsolidasi lawan indeks ekspansi | **Sebagian** | `triad.truth_asset` sudah menskor konsolidasi; aturan rotasi antar pasar belum |
| 31 | Model M1 sampai M7 | **Belum** | ketujuhnya komposisi butir di atas; tidak ada yang baru selain urutannya |
| 32 | Lima indikator TradingView milik penulisnya | **Ditolak** | produk berbayar pihak ketiga; konsepnya sudah dipetakan di baris-baris di atas |
| 33 | Aturan tidak-trading, no SSMT no trade, chop berita, hari libur tipis | **Sebagian** | layer `news` dan gerbang autotrade ada; aturan jendela dan hari libur belum |
| 34 | Psikologi, prop firm, roadmap 90 hari | **Ditolak** | di luar lingkup engine pengukuran |

### Keempatnya dibangun, 11 September 2026

Empat teratas dari daftar di bawah dikerjakan pada hari yang sama dokumen ini
dibedah. Semuanya MATI secara default, tidak satu pun punya gerbang, dan
praregistrasi pengukurannya ada di `docs/PRAREGISTRASI-QT-AZ.md` - ditulis
sebelum satu angka pun dihitung.

| Butir | Kode | Saklar | Fetch tambahan |
|---|---|---|---|
| QT Killzone | `sequence.killzones()` | `session.killzones` | nol, aritmetika jam |
| Premium/discount waktu | `quarterly.time_premium_discount()` | `session.premium_discount` | nol, dari bar yang sudah ada |
| Hidden SSMT | `ssmt(basis="body")` | `checklist.ssmt_hidden` | nol, basket yang sama |
| SMT Fill | layer `smt_fill` | layer sendiri | nol, menumpang basket `ssmt` |

Nol fetch tambahan untuk keempatnya, dan itu bukan kebetulan: tiga di antaranya
membaca jam atau bar yang sudah ada, dan yang keempat sengaja ditempelkan ke
blok async yang sudah membayar basket-nya.

<details><summary>Tiga cacat yang ketahuan saat membangunnya</summary>

1. **Varian `full` tidak pernah bisa menyala.** `depth` di-clamp ke 1,0, dan
   aturan seragam "sisi dalam harus MELEBIHI ambang" membuat ambang 1,0 mustahil
   dicapai. Gejalanya nol yang bersih - 17 entered, 23 half, 0 full - di jendela
   yang penuh gap terisi tembus. Varian yang tak pernah bisa menyala lebih buruk
   daripada varian yang tidak ada, karena nolnya terbaca sebagai pengukuran.
   Sekarang 38 dari 99.
2. **Label `basis` ada di model dan tidak pernah diisi.** Enam divergensi
   tersembunyi sampai ke chart berlabel `wick`, dihitung benar di `meta` dan
   salah di objeknya. Label yang ada tapi tak pernah diisi lebih buruk daripada
   tidak ada label, karena ia terbaca sebagai jaminan.
3. **Kalimat "kenapa layer ini kosong" jadi bohong.** Rail melaporkan "pilih
   minimal satu degree" sementara 52 objek ada di kanvas. `e2e/rails.mjs`
   membaca kalimat itu DARI API lalu memeriksa ia muncul di DOM, jadi kalimat
   yang salah tidak merah di mana pun - ia cuma bohong.
4. **`smt_fill` ter-gate oleh derajat yang tidak dipakainya.** Ia menumpang
   blok `_draw_ssmt`, dan blok itu keluar lebih awal kecuali `ssmt_degrees`
   terisi - padahal gap-fill divergence membandingkan gap di bar yang SAMA dan
   tidak punya derajat kuarter sama sekali. Menyalakan layer itu sendirian
   mengharuskan pembaca memilih SSMT stage yang tidak berpengaruh apa-apa.
   Sekarang partner yang wajib, derajat tidak.
5. **Menyalakan `smt_fill` sendirian tidak memberi satu pun kontrol partner.**
   Panel knob hanya muncul untuk layer yang menyala, dan partner-nya hidup di
   blok `checklist` milik layer lain. Picker partner sekarang dirender di panel
   `smt_fill` juga: satu state, dua tampilan.

Nomor 4 dan 5 ditemukan `e2e/qt-az-ink.mjs`, probe piksel yang ditulis untuk
pertanyaan yang tidak ditanyakan harness mana pun. `wiring.mjs` membuktikan
layer mengisi array-nya dan punya swatch serta knob; `ink-budget.mjs` mengukur
tinta HANYA pada params default, dan tiga dari empat adopsi ini memang kosong
pada default. Di antara keduanya sebuah layer bisa dilaporkan tersambung penuh
sambil tidak mengecat apa pun. Terukur sekarang: killzone 6.864 piksel,
premium/discount 1.776, SMT fill 2.550, hidden SSMT 39.077.

> [!WARNING]
> **Versi pertama probe itu sendiri yang salah, dan ia merah untuk keempatnya -
> termasuk `ssmt` yang jelas mengecat.** Ia menembak `/api/draw` lewat `fetch`
> di dalam halaman, jadi React tidak pernah tahu dan chart tidak pernah
> di-render ulang: nol piksel bergerak, empat kali. Alat ukurnya, bukan
> layernya. Versi yang benar menggerakkan kontrol di rail.

</details>

### Urutan yang saya sarankan, kalau ada yang mau diadopsi

Diurutkan menurut biaya bangun dibagi nilai bukti, bukan menurut seberapa
meyakinkan dokumennya.

1. **QT Killzone** (butir 16). Primitif sudah ada, rig sudah ada, dan dua sumber
   independen menamainya. Bisa diukur sebelum digambar.
2. **Time-based premium/discount mekanis** (butir 17). Ia MENGHAPUS sebuah knob
   (`swing_n`) dan menggantinya dengan aturan tanpa parameter, jadi ia bisa
   diadu langsung lawan dealing range yang sekarang di rig yang sudah ada.
3. **Hidden SSMT** (butir 20). Perubahan satu baris di dalam `ssmt()`: baca
   `open`/`close` sebagai ekstrem kedua di samping `high`/`low`. Populasinya
   naik, dan pertanyaannya persis pertanyaan yang sudah pernah diukur.
4. **SMT Fill** (butir 21). Paling banyak kode baru dari empat teratas, tapi ia
   satu-satunya konsep di dokumen ini yang benar-benar tidak punya tetangga di
   repo, dan ia mekanis penuh.
5. Sisanya menunggu. **itCISD, TOB, RTO, SMTMSS, first-FVG** semuanya bergantung
   pada tCISD atau SSMT yang angkanya sendiri belum berdiri (butir 12 dan 14),
   jadi membangunnya sekarang berarti menumpuk lapisan di atas lantai yang belum
   diukur.

> [!CAUTION]
> Butir 12 sudah terukur null dan butir 14 belum punya angka yang berdiri.
> Dokumen ini menyebut SSMT "the base of every setup" dan tCISD "the single most
> reliable confirmation in the system". Keduanya klaim tanpa angka, dan salah
> satunya sudah kita ukur nol di 48 sel. Membangun tujuh model di atas keduanya
> karena sebuah PDF meyakinkan adalah persis cara sebuah checklist berubah jadi
> keyakinan.

## Ringkasan hitungan

| Status | Sebelum 11 Sep | Referensi QT ketiga | Total |
|---|---|---|---|
| Ada | 29 | +14 | 43 |
| Sebagian | 9 | +3 | 12 |
| Belum | 25 | +12 | 37 |
| Ditolak | 8 | +3 | 11 |
| Terukur null | 1 | +2 | 3 |

Naik dua dari koreksi 20 Agustus: derajat `quadrennial` dengan true open-nya, dan
bacaan premium/discount pada setiap divergensi SSMT.

Butir "Ditolak" naik dari 7 ke 8 dengan masuknya Three Drives, dan itu satu-satunya
penolakan di halaman ini yang **punya angkanya sendiri** daripada berhenti di
provenance.

Kolom ketiga adalah 34 butir dari `quarterly-theory-a-z-guide-v1-1.pdf`. Sepuluh
di antaranya sudah terpasang sebelum dokumen itu dibaca, yang berarti dokumen ini
lebih banyak MENYELESAIKAN daripada menambah pekerjaan: satu perselisihan grid
yang dibawa sebagai dua kolom sejak 5 September ternyata satu grid dengan satu
kolom salah nama. Provenance aturan pertiga TIDAK naik, karena dokumen ini
penulis yang sama dengan yang sudah dikutip `app/quarterly.py`.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

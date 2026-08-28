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
| Killzone dan jam spesifik | **Sebagian** | Asia 19:00-00:00 dan London 02:00-05:00 New York **ada**. Jam 00:00 ada sebagai true day open, 06:00 ada sebagai Q3. Silver Bullet, 04:00, 09:30 dan 10:30 **belum** |
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
| Silver Bullet window | **Belum** | |
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

## Ringkasan hitungan

| Status | Jumlah butir |
|---|---|
| Ada | 29 |
| Sebagian | 9 |
| Belum | 25 |
| Ditolak | 8 |
| Terukur null | 1 |

Naik dua dari koreksi 20 Agustus: derajat `quadrennial` dengan true open-nya, dan
bacaan premium/discount pada setiap divergensi SSMT.

Butir "Ditolak" naik dari 7 ke 8 dengan masuknya Three Drives, dan itu satu-satunya
penolakan di halaman ini yang **punya angkanya sendiri** daripada berhenti di
provenance.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

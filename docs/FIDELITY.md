# Kesetiaan pada metode

Kalibrasi menjawab "apakah zona ini membedakan hasil". Dokumen ini menjawab
pertanyaan yang berbeda dan sama pentingnya: **apakah kotaknya digambar di tempat
yang benar menurut metodenya sendiri.** Sebuah detektor bisa lolos uji statistik
sambil menggambar sesuatu yang akan ditolak seorang praktisi begitu melihatnya.

Sumber doktrin: materi Sam Seiden (FXStreet, MoneyShow), panduan resmi Online
Trading Academy, dan turunan yang mengutip aturan aslinya. Diaudit 2026-08-13.

> [!IMPORTANT]
> Doktrinnya sendiri **tidak lengkap dan tidak konsisten**. Seiden hanya
> menerbitkan satu angka keras (aturan 1:3). Hampir setiap angka presisi yang
> beredar berasal dari materi kelas atau kodifikasi pihak ketiga, dan ada tiga
> tabel skor terbit yang saling bertentangan (maksimum 10, 12, dan 13). Di mana
> doktrinnya kabur, dokumen ini mengatakan kabur, bukan mengarang angka.

## Cacat yang ditemukan dan diperbaiki

### 1. Distal digambar di tempat yang salah

**Aturan doktrin, tidak ambigu di semua sumber:** garis **distal selalu wick**.
Untuk demand ia harus menutup low terendah base; untuk supply, high tertinggi.
Alasannya mekanis: stop diletakkan **di luar** distal, jadi distal yang digambar
di body menaruh stop **di dalam base yang seharusnya ia lindungi**. Hanya garis
**proximal** yang berpindah antara varian agresif (wick) dan konservatif (body),
dan doktrinnya sendiri tidak pernah memutuskan mana yang benar.

**Yang saya lakukan sebelumnya:** parameter `zone_basis` menggeser **kedua** tepi
sekaligus. Jadi mode "body" saya bukan varian konservatif, bukan pula agresif; ia
varian yang tidak ada dalam metode mana pun, dan stop-nya jatuh di dalam base.

**Perbaikan:** parameter diganti nama menjadi `proximal_basis`, karena itulah
satu-satunya yang berpindah. Distal sekarang selalu ekstrem wick. Diverifikasi
pada 200 zona nyata di kedua varian: **0 pelanggaran**. Dijaga oleh
`test_the_distal_is_always_the_wick_extreme`, diparametrikan atas keempat formasi
dan kedua varian.

### 2. Pelebaran zona tipis ikut menggeser stop

Zona setinggi nol tidak akan pernah bisa tersentuh, jadi zona tipis ditumbuhkan ke
tinggi minimum. Sebelumnya pertumbuhannya **simetris terhadap titik tengah**, yang
mendorong distal melewati ekstrem base. Itu cacat yang sama dengan nomor 1, hanya
tiba lewat jalan lain.

**Perbaikan:** pelebaran sekarang hanya dari sisi **proximal**. Dijaga oleh
`test_the_minimum_height_grows_the_proximal_not_the_distal`.

### 3. "Base" yang sebenarnya tangga menanjak

Audit visual per zona menemukan sebuah RBR yang base-nya berjalan 4341, 4343,
4340, 4342, 4344, 4345. Itu bukan jeda, itu tangga. Klasifikator menerimanya
karena tidak ada satu pun candle di dalamnya yang cukup besar untuk disebut
impuls, dan **"tidak ada candle besar" bukan uji yang sama dengan "harga berhenti
bergerak"**.

Doktrinnya memperingatkan hal ini dari sisi lain: garis tidak boleh memotong
kumpulan body, dan area seimbang menurut definisi bukan ketidakseimbangan.

**Yang diukur, 800 zona di 4 deret:**

| Besaran | Median | Ekor |
|---|---|---|
| `base_drift`, perjalanan searah dibagi tinggi base | 0.34 | 13.2% di atas 0.7 |
| `base_overlap`, rerata irisan antar bar base | 0.54 | 16.2% di bawah 0.35 |
| Keduanya sepakat "ini tangga" | | **3.8%** |

**Diperiksa ulang lewat audit visual 96 zona di 8 timeframe**, empat peninjau
independen, masing-masing dua timeframe, masing-masing menilai tiap zona dengan
daftar periksa tujuh poin. Keempatnya menamai cacat yang sama sebagai yang
**paling sering muncul**, dan keempatnya membaca ambang pemisah yang sama dari
`base_drift` milik engine sendiri:

| Peninjau | Zona tangga | Base yang mereka luluskan |
|---|---|---|
| 1m dan 5m | "drift >= 0.7 atau overlap <= 0.35" | - |
| 1h dan 4h | 0.42 sampai 0.80 | 0.034 sampai 0.128 |
| 1d dan 1w | 0.63 sampai 0.86 | 0.02 sampai 0.34 |

Empat penilaian mata yang terpisah menyatu pada satu angka. Itu bukti yang
tepat untuk pertanyaan kesetiaan, dan jauh lebih kuat daripada pengukuran hasil
yang tidak konklusif.

**Konsekuensi pada kode:** `max_base_drift` menyala secara bawaan di **0.6**.
Ia membuang 16.2% kandidat (1956 dari 12057) dan rasio demand:supply tetap
0.96-0.98 di **setiap** ambang yang diuji, jadi ia membuang cacat, bukan salah
satu bentuk. Dijaga oleh `test_a_drifting_base_is_rejected_as_a_staircase` dan
pasangannya yang memastikan base datar tetap lolos.

> [!IMPORTANT]
> Gerbang ini dibenarkan atas dasar **kesetiaan**, bukan kinerja. Kalibrasi
> tidak menemukan perbedaan hasil yang terukur untuk `base_drift`, dan itu tetap
> berlaku. Dua standar yang berbeda: sebuah gambar yang ditolak praktisi begitu
> melihatnya adalah gambar yang salah, terlepas dari apakah ia memprediksi.

### 4. Kotak digambar dari titik tengah bar, bukan dari tepinya

Semua uji yang ada sebelum ini membandingkan **angka dengan angka**. Uji kontrak
membandingkan catatan zona terhadap aritmetika pada candle, `zone-audit.mjs`
membandingkannya lagi di dalam browser terhadap candle yang diambil halaman.
Tidak satu pun melihat satu piksel pun, jadi bug penggambaran yang menempatkan
zona yang benar di tempat yang salah akan lolos semuanya.

`e2e/pixel-truth.mjs` membaca kembali kanvasnya. Untuk tiap zona ia mencari
garis batas yang benar-benar tercat, mengubah baris piksel itu kembali menjadi
harga lewat skala chart, lalu membandingkannya dengan catatan zona.

**Penempatannya sudah tepat.** Tepi atas jatuh dalam 1.3 piksel dari tempat
skala harga menaruh `zone.top`, tepi bawah dalam 1.9 piksel. Selisih satu sampai
dua piksel itu rasteriser, bukan cacat: `strokeRect(x+0.5, y+0.5, w-1, h-1)`
menaruh baris tercat terakhir di `y+h-1`, satu piksel di dalam tinggi kotaknya.

**Yang salah adalah tepi kirinya.** `timeToCoordinate` mengembalikan **titik
tengah** sebuah bar, dan kotaknya ditambatkan langsung ke koordinat itu. Akibatnya
dua hal sekaligus:

- separuh bar base pertama berada **di luar** kotak yang justru dipotong darinya;
- garis batas kiri mendarat tepat di posisi x candle itu sendiri, dan karena
  badan zona sengaja digambar **di bawah** candle, candle-nya menutupi garis itu.

| Timeframe | Tepi kiri terbaca, sebelum | Sesudah |
|---|---|---|
| 15m | 2 dari 8 | 8 dari 8 |
| 1h | 2 dari 9 | 9 dari 9 |
| 1d | 8 dari 14 | 14 dari 14 |

**Perbaikan:** kotak dilebarkan setengah jarak bar ke kiri dan ke kanan, jadi ia
menutup bar utuh. Diverifikasi ulang pada **72 zona di 8 timeframe** (1m sampai
1w): seluruh tepi kiri terbaca, dan bagian bar base pertama yang tersisa di luar
kotak paling buruk 0.01 bar.

> [!IMPORTANT]
> Ini juga menutup pertanyaan mengapa empat peninjau visual menyatu pada klaim
> yang salah. Mereka melaporkan kotak melar ke candle impuls tetangga; aritmetika
> mengatakan padding-nya 0.0% dan klaim itu ditolak. Keduanya benar tentang apa
> yang mereka ukur. Angkanya memang tepat, tetapi tepi kirinya tidak bisa dilihat,
> jadi tidak ada cara bagi mata untuk memisahkan "kotaknya melar" dari "kotaknya
> pas tetapi tertimbun candle". Mata tidak bisa menjawabnya, dan sampai sekarang
> tidak ada uji yang bisa.

Dua kesalahan alat ukurnya sendiri layak dicatat, karena keduanya menghasilkan
angka yang tampak masuk akal:

1. Kanvas lapisan atas seluruhnya transparan, dan piksel transparan terbaca
   sebagai rgb(0,0,0), yaitu **lebih jauh** dari warna latar daripada cat chart
   yang sesungguhnya. Probe yang hanya menguji warna memilih lapisan kosong itu
   sebagai yang paling ramai, lalu melaporkan nol di mana-mana, yang terlihat
   persis seperti gambar yang hilang.
2. Rata-rata warna per baris dibatalkan oleh candle berlawanan warna. Harga
   kembali masuk ke zona, jadi sebagian besar lebar kotak adalah candle, dan satu
   badan candle merah cukup untuk menarik rata-rata baris batas yang **asli** ke
   bawah rata-rata baris kosong. Menghitung piksel yang mencapai kekuatan warna
   batasnya kebal terhadap itu.

## Akurasi dan presisi, diukur pada 28.476 zona

Dua pertanyaan berbeda yang sering dicampur, dan sebuah gambar bisa lolos satu
sambil gagal yang lain:

- **Akurasi**, apakah kotaknya duduk di tempat base-nya secara rata-rata, tanpa
  bias sistematis ke atas atau ke bawah.
- **Presisi**, apakah ia duduk di sana pada **setiap** zona, tanpa sebaran dan
  tanpa pencilan sesekali yang tertutup oleh rata-rata.

Uji yang ada sebelumnya tidak menjawab keduanya pada skala. `tests/` memeriksa
geometri persis pada fixture buatan tangan, `validate_api` memeriksanya pada
beberapa puluh zona nyata, `e2e/pixel-truth.mjs` membaca piksel untuk tujuh zona
yang kebetulan masuk satu tangkapan layar. Tidak satu pun mengatakan apa yang
terjadi pada ribuan zona di setiap timeframe, dan "benar pada yang kami lihat"
justru klaim tempat cacat langka bertahan hidup.

`tools/drawing_accuracy.py` melaporkan **kasus terburuk, bukan rata-rata**.
Rata-rata nol juga yang dilaporkan gambar dengan dua bug bertanda berlawanan.

| Besaran | Hasil |
|---|---|
| Zona diperiksa | 28.476, tujuh deret x dua varian proximal |
| Galat tepi atas terburuk | **0,000** dari tinggi zona |
| Galat tepi bawah terburuk | **0,000** dari tinggi zona |
| Pelanggaran aturan | **0** |
| Zona dilebarkan melewati base | **0** |
| Distal bukan ekstrem wick | **0** |
| Zona ditumbuhkan ke tinggi minimum | 479 dari 28.476, semuanya dari sisi proximal |

Nol di sini berarti nol, bukan pembulatan: perbandingannya persis, dengan
toleransi 1e-9 pada harga.

> [!NOTE]
> Ada 1485 zona yang punya satu atau dua bar tetangga yang **seluruh rentangnya
> kebetulan muat di dalam kotak**. Itu fakta tentang bar tersebut, bukan tentang
> kotaknya: tepi kotaknya persis ekstrem base, sebagaimana tabel di atas. Inilah
> yang dulu dibaca empat peninjau visual sebagai "kotaknya melar".

**Dua kekeliruan alat ukurnya sendiri, dicatat karena keduanya lebih dulu
menghasilkan temuan palsu yang tampak meyakinkan.** Versi pertama file ini
melaporkan galat tepi sebesar 18 kali tinggi zona dan 33 pelanggaran proximal.
Keduanya milik auditornya:

1. Ia membandingkan terhadap rentang **wick** pada kedua varian, padahal mode
   body memakai badan candle, lalu melaporkan pertumbuhan tinggi minimum yang
   bekerja sebagaimana mestinya sebagai cacat. Auditor yang tidak mereproduksi
   aturan yang diauditnya akan mengarang temuan.
2. Ia menghitung padding mundur dari `base_from`, padahal ketika konsolidasi
   panjang dipotong, bar sebelum `base_from` adalah sisa jeda yang sama dan tentu
   saja duduk di dalam rentang harga kotaknya. Itu melaporkan 4325 zona melar
   yang sama sekali bukan.

Angka yang tampak masuk akal keluar lebih dulu, sebelum angka yang jelas-jelas
salah. Itu pola yang sudah tiga kali terjadi di proyek ini.

## Yang sengaja TIDAK saya ubah

### Aturan 1:3 tidak dipasang sebagai default

Ini satu-satunya angka keras dalam doktrin: "sebuah level baru menjadi level bila
rally awal dari level itu setidaknya tiga kali level itu sendiri". Sekarang
dihitung untuk setiap zona sebagai `profit_margin` dan tersedia sebagai gerbang,
tetapi **mati secara bawaan**, karena diukur ia tidak bertahan.

Tingkat bertahan menurut bucket, seluruh populasi termasuk yang ditolak gerbang:

| profit_margin | @0.5 ATR | @1.0 ATR | @2.0 ATR |
|---|---|---|---|
| 0 sampai 1 | 82.7% | 66.9% | 49.1% |
| 1 sampai 2 | 92.5% | 74.7% | 56.0% |
| **2 sampai 3** | **98.9%** | **84.2%** | 53.2% |
| 3 sampai 4 | 95.8% | 79.2% | 47.9% |
| 4 sampai 6 | 97.6% | 85.7% | 56.1% |
| 6 ke atas | 97.7% | 84.1% | 67.4% |

Lututnya ada di sekitar **2, bukan 3**, dan di atas itu datar bahkan turun. AUC-nya
0.485 dan 0.484 pada dua geometri yang sampelnya memadai, dengan tanda berbalik
antar paruh. Ia juga mengukur kaki yang sama dengan `departure_atr`, hanya dengan
penyebut berbeda, jadi ia tidak menambah apa pun di atas gerbang yang sudah
tervalidasi.

> [!NOTE]
> "Tidak didukung di sini" bukan "salah". Sampel kalibrasi ini condong ke kripto
> dan emasnya diwakili PAXG, sedangkan doktrinnya diajarkan pada saham dan futures.
> Knob-nya tersedia justru supaya klaim ini bisa diuji ulang di pasar lain.

### `base_drift` tidak dijadikan filter

Sempat terbaca kuat dan terbalik pada reward 0.5 (AUC 0.206), lalu ketahuan bahwa
geometri itu hanya punya **5 kegagalan dari 234** sehingga angkanya tak berarti.
Pada dua geometri dengan sampel nyata: 0.508 dan 0.505.

Jadi ada dua standar yang berbeda dan zona melayang gagal pada satu, tidak
terbukti pada yang lain:

- **Kesetiaan:** tangga bukan base. Doktrinnya jelas.
- **Kinerja:** tidak ada bukti ia berkinerja lebih buruk.

Menyalakan filter atas dasar kesetiaan saja berarti membuang zona tanpa bukti
bahwa itu memperbaiki apa pun. Melaporkannya membiarkan penggunanya memutuskan,
dan angkanya tampil di inspektur. Bila kelak ada sampel lebih besar dan efeknya
bertahan, gerbangnya tinggal dipasang.

### Seluruh enhancer, dan hasil pengukurannya

| Enhancer | Status | Hasil |
|---|---|---|
| Strength of departure | Ada | **Satu-satunya yang tervalidasi.** Lutut di 2 ATR, +16.3 pp lawan kontrol keras, p<0.0001 |
| Profit zone (mundur, aturan 1:3) | Ada, gerbangnya mati | Lutut di 2 bukan 3, datar di atasnya, AUC 0.485 |
| Profit zone (maju, ke zona lawan) | Ada | AUC 0.540 dan 0.539, CI melintasi 0.5 di keduanya. Tanda sama antar paruh, jadi marginal bukan nol, tetapi tidak terbukti |
| The Curve | Ada | Versi doktrinnya (`curve_favourable`) **tidak terbukti**: 0.547 dan 0.518. Lihat catatan drift di bawah |
| Arrival | Ada | 0.450 dan 0.470, tanda berbalik antar paruh. **Perselisihan sumbernya tidak terselesaikan karena tidak ada efeknya** |
| Nesting HTF | Ada | Tidak ada manfaat, sedikit negatif di ketiga geometri |
| Time at level | Ada | `compactness`, dihukum bertahap. AUC 0.529-0.546, tidak terbukti |
| Freshness | Ada | `state` dan `touches`. Konstan pada sentuhan pertama, jadi tak terukur di sana |
| Big picture / tren | **Sengaja tidak** | Doktrinnya tidak pernah mendefinisikan cara mengukur tren. Tidak ada yang bisa diimplementasikan tanpa mengarang |
| Skor gabungan dan gerbang 7/8/9 | **Sengaja tidak** | Tiga tabel terbit yang saling bertentangan, tanpa validasi di belakang satu pun, dan komposit di sini sudah terbukti tidak memeringkat apa pun |

### The Curve, dan artefak yang hampir saya laporkan sebagai temuan

Nilai mentah `curve_position` tampak sebagai **faktor pertama yang lolos**: AUC
0.648 dan 0.581, CI bersih dari 0.5 di kedua geometri yang sampelnya memadai, dan
tanda yang sama di kedua paruh. Itu hasil terkuat dari semua yang saya ukur.

Ia palsu, dan cara membuktikannya adalah memisahkan per sisi. Doktrinnya menuntut
demand kuat **di bawah** rentang dan supply kuat **di atas**, jadi efek curve yang
nyata harus menunjuk **arah berlawanan** untuk kedua sisi.

| Reward | Demand | Supply | Putusan |
|---|---|---|---|
| 0.5 ATR | 0.604, high better | 0.927, high better | searah |
| 1.0 ATR | 0.587, high better | 0.731, high better | searah |
| 2.0 ATR | 0.531, high better | 0.636, high better | searah |

**Kedua sisi menunjuk arah yang sama di ketiga geometri.** Yang diukur variabel itu
adalah drift harga di sampel yang sedang menanjak, bukan posisi pada kurva: di
tren naik, zona yang lebih tinggi dalam rentang adalah zona yang lebih baru, dan
harga terus menjauh ke arah yang menguntungkan. Sisi demand bahkan **berlawanan
dengan doktrinnya**.

Harness sekarang mencetak pemisahan ini setiap kali, dengan verdict eksplisit,
supaya artefak yang sama tidak lolos lagi.

## Multi-timeframe

Doktrinnya top-down: zona milik timeframe lebih tinggi, entri milik yang lebih
rendah. Zona HTF sekarang dihitung dari bar hasil agregasi dan diproyeksikan ke
chart, dengan tiga aturan yang membuatnya benar dan bukan sekadar masuk akal.

1. **Bucket ditambatkan ke epoch, bukan ke bar pertama di jendela.** Bila
   ditambatkan ke jendela, setiap zona HTF akan bergeser ketika pengguna mengubah
   jumlah bar, dan itu terlihat persis seperti bug detektor.
2. **Bar HTF terakhir dibuang bila belum selesai.** Bar yang masih terbentuk
   high dan low-nya masih bergerak; zona di atasnya akan berpindah sendiri.
3. **Bucket kosong tidak diciptakan.** Akhir pekan meninggalkan lubang pada emas
   dan FX. Mengisinya dengan bar datar akan mengarang justru bentuk konsolidasi
   yang dicari detektor ini.

Siklus hidup zona HTF dievaluasi pada bar HTF-nya sendiri, bukan pada bar chart.
Zona demand H4 tidak boleh mati hanya karena satu candle M15 menutup beberapa sen
di bawahnya.

Semua ini dijaga oleh lima pengujian resample dan sebelas asersi kontrak API,
termasuk bahwa setiap zona 4h jatuh tepat di grid 4 jam.

### Jam sesi broker

Grid HTF sekarang bisa digeser dari tengah malam UTC lewat `session_offset_hours`.
Ini bukan kenyamanan: broker yang harinya mulai pukul 22:00 atau 01:00 menaruh
candle H4 dan D1-nya di grid yang berbeda dari agregat berbasis UTC, dan hasilnya
zona tergambar **satu candle meleset** dari zona yang sama di terminalnya.
Penyebab paling umum keluhan "zona H4-nya geser satu", dan tidak terlihat kecuali
kedua chart dibandingkan berdampingan. Picker-nya muncul di header begitu HTF
dinyalakan.

### Aturan MTF yang disepakati semua aliran, diuji

"Zona timeframe rendah yang berada di dalam zona timeframe tinggi lebih mungkin
menang." Seiden, ICT, dan literatur SMC sama-sama menyatakannya. Menurut penelusuran
sumber, **belum ada yang pernah menerbitkan angkanya.**

Kondisi bersarang harus ketat, dan ini bagian pentingnya. Percobaan pertama saya
memakai sekadar *tumpang tindih* harga dan menandai **226 dari 234** zona sebagai
bersarang. Syarat yang dipenuhi 97% kasus tidak bisa membedakan apa pun. Definisi
final: minimal 80% tinggi zona lokal berada di dalam zona HTF, sisi sama, zona HTF
lahir lebih dulu, dan zona HTF masih hidup saat zona lokal terbentuk.

| Reward | Bersarang | Berdiri sendiri | Selisih | Uji |
|---|---|---|---|---|
| 0.5 ATR | 97.2% (n=141) | 98.9% (n=93) | -1.8 pp | z=-0.91, p=0.36 |
| 1.0 ATR | 83.7% (n=141) | 86.0% (n=93) | -2.3 pp | z=-0.48, p=0.63 |
| 2.0 ATR | 59.4% (n=138) | 63.4% (n=93) | -4.0 pp | z=-0.61, p=0.54 |

**Tidak ada manfaat terukur**, dan titik estimasinya sedikit negatif di ketiga
geometri. Tidak satu pun signifikan, jadi efek positif kecil belum bisa
disingkirkan; yang bisa dikatakan adalah efek besar yang tersirat dalam doktrinnya
tidak muncul di sini.

Batasannya jujur: langkah naiknya hanya 4x (15m ke 1h, 1h ke 4h) sedangkan praktisi
sering memakai lompatan jauh lebih besar, detektor yang sama dipakai di kedua
timeframe, dan n=234 tidak akan pernah bisa menyelesaikan efek 2 poin persen.
Karena itu hasilnya **dilaporkan lewat medan `nested_in`, tidak dijadikan skor.**

## Audit visual: satu klaim terkonfirmasi, satu terbantah

Selain zona tangga, keempat peninjau melaporkan dua hal lagi. Keduanya
bertabrakan dengan asersi kontrak yang lulus, jadi paling banyak satu pihak
benar, dan menebak bukan pilihan. `tools/verify_claims.py` menyelesaikannya
dengan aritmetika atas data candle, bukan atas piksel.

### Terkonfirmasi: leg-in terlepas dari base

Dua peninjau melaporkan marker leg-in berdiri 1 sampai 9 bar dari base dengan
candle tak bertanda di antaranya, dan keduanya mencatat itu selalu terjadi pada
zona `base 6`. Salah satu menyebutnya "berbentuk aritmetika, bukan berbentuk
data", dan itu tepat.

Penyebabnya pemotongan base: ketika konsolidasi lebih panjang dari
`base_max_bars`, kotaknya digambar pada ekor bar yang benar-benar ditinggalkan
gerakan, tetapi `leg_in_to` tetap menunjuk ke batas run aslinya. Terukur: 12.5%
zona punya celah.

**Perbaikan:** medan `base_run_from` melaporkan awal konsolidasi utuh. Formasinya
kini selalu terbaca sebagai satu urutan yang bersambung (**100% dari 30 zona**,
naik dari 87.5%), sementara kotaknya tetap dipotong ke bar yang relevan. Audit
visual menandai selisihnya dengan `c`.

### Terbantah: kotak dipadding melewati base

Keempat peninjau melaporkan bahwa kotaknya 2-3 kali lebih tinggi dari base-nya,
dengan tepi menempel ke badan candle leg-in atau leg-out. Satu menyebutnya "isu
bervolume paling tinggi di sini".

Diukur pada empat deret: padding **0.0% di setiap zona**. Kotaknya selalu persis
ekstrem base-nya, sebagaimana dijamin asersi kontrak.

Peninjau keempat sebenarnya sudah menandai kaveatnya sendiri: garis tepi kotak
digambar tepat di posisi-x candle base, jadi wick panjang dan border bertumpang
piksel dan tidak bisa dipisahkan dengan mata pada zoom itu.

> [!NOTE]
> Empat penilai independen menyatu pada satu kesimpulan yang keliru.
> **Konvergensi bukan bukti.** Itu berlaku dua arah di dokumen ini: konvergensi
> mereka pada ambang drift dipercaya karena aritmetika mendukungnya, dan
> konvergensi mereka pada padding ditolak karena aritmetika membantahnya.

## Penyempurnaan zona, dan angka yang belum pernah diterbitkan siapa pun

Praktisi mengecilkan zona HTF dengan melihat candle LTF di dalamnya. `app/refine.py`
melakukannya memakai **bar chart yang sudah ada**: zona HTF dibangun dari agregasi
candle chart itu sendiri, jadi detail LTF di dalam tiap base HTF sudah ada di
permintaan yang sama. Tidak ada fetch kedua, dan tidak ada cara kotak hasilnya
dihitung dari bar yang tidak sedang ditampilkan chart.

### Sumbernya lemah, dan itu harus dikatakan

Ditelusuri 2026-08-13. **Tidak ada satu pun sumber primer dalam garis keturunan
ini yang menerbitkan prosedur refinement.** Kolom Seiden di FXStreet dan MoneyShow,
panduan pengguna Online Trading Academy, dan paten OTA (US8650115B1, Seiden
tercantum sebagai inventor) semuanya bekerja pada satu timeframe tanpa langkah
turun. Refinement adalah kodifikasi pihak ketiga yang dinisbatkan ke garis itu.
Tidak adanya aturan terbitan bukan berarti tidak ada aturan, materi kursus
berbayarnya memang tidak pernah publik, tetapi artinya tidak ada yang bisa
dikutip. Jadi pilihannya dinyatakan, bukan disandarkan pada otoritas:

| Pilihan | Dasarnya |
|---|---|
| Kedua tepi bergeser, stop pindah ke distal hasil refinement | Bacaan pihak ketiga yang dominan. Satu panduan SMC menyebut memakai stop HTF di bawah entri LTF sebagai kesalahan. Tidak ada yang membela posisi ketiga (entri LTF, distal HTF dipertahankan) |
| Jeda **terakhir** yang dipilih, bukan yang tersempit | Kubu "cluster" menggambarkannya sebagai mencari sumber tempat pergerakan berangkat, dan itu yang terakhir. **Aturan "cluster tersempit" tidak ada di sumber mana pun**; mengarangnya lalu menyebutnya doktrin persis yang dihindari proyek ini |
| Timeframe bawahnya adalah chart itu sendiri | Tidak ada rasio yang diterbitkan. Triplet "daily ke H1, H4 ke H1, M15 ke M5" yang beredar hanya bisa dilacak ke satu blog sekunder dan isinya lantai, bukan pembagi |

> [!WARNING]
> Refinement sub-candle milik ICT (mean threshold, entri di 50% badan, stop tetap
> di luar wick penuh) melakukan **kebalikannya**: ia mempertahankan distal yang
> lebih lebar. Tidak ada sumber yang mendamaikan dua konvensi ini. Modul ini
> mengimplementasikan versi turun-timeframe.

### Diukur, berpasangan

Klaim yang beredar untuk refinement adalah aritmetika, bukan bukti: kotak 40 pip
berisi kotak 5 pip, jadi target yang sama menjadi kelipatan risiko 8 kali lipat.
Pembagian itu benar dan ia **mengandaikan hal yang sedang dipersoalkan**, yaitu
bahwa stop yang lebih ketat bertahan sesering yang lebar.

Setiap zona muncul dua kali, sebagaimana digambar detektor dan setelah
disempurnakan, pada bar yang sama dan dinilai dengan aturan yang sama.
`tools/refinement.py`, uji McNemar eksak pada pasangan yang berbeda pendapat.

| Reward | n pasangan | Digambar | Disempurnakan | Selisih | Uji eksak |
|---|---|---|---|---|---|
| 0,5 ATR | 2336 | 84,2% | 80,1% | **-4,2 pp** | p<0,0001 |
| 1,0 ATR | 2317 | 68,4% | 62,6% | **-5,8 pp** | p<0,0001 |
| 2,0 ATR | 2329 | 47,7% | 37,9% | **-9,9 pp** | p<0,0001 |

Jarak stop menyusut ke **48,6% dari aslinya** (median 45,6%), jadi reward per
satuan risiko naik ke 2,19 kali (median).

**Jawabannya: refinement memang membeli reward per risiko, dan ia membayarnya
dengan tingkat bertahan, secara signifikan, di setiap geometri.** Kolom leverage
adalah aritmetika dan bukan temuan; satu-satunya besaran yang diukur di sini
adalah tingkat bertahan, dan ia turun. Apakah pertukarannya sepadan bergantung
pada biaya transaksi trader, yang tidak dimodelkan proyek ini sama sekali.

> [!IMPORTANT]
> Penurunan itu **bukan tanda zonanya jadi lebih buruk**, dan pengukuran
> terpisah menunjukkan mengapa. Kalibrasi menemukan tinggi kotak sendiri
> meramalkan hasil: kuartil terpendek bertahan 52,4% dan tertinggi 61,4% di
> reward 2,0, semata karena stop yang jauh lebih jarang tersentuh. Refinement
> memotong tinggi ke 48,6%, yaitu memindahkan zona ke kuartil terpendek. Jadi
> yang dibeli refinement adalah stop yang lebih dekat, dan yang dibayarnya
> adalah konsekuensi aritmetis dari stop yang lebih dekat.
> Rinciannya di [`CALIBRATION.md`](CALIBRATION.md) bagian konfon jarak stop.
>
> **Dikoreksi.** Versi sebelumnya paragraf ini menambahkan bahwa selisih 9,9 poin
> persen itu "hampir persis" sebaran kuartil 9,0 pp. Bacaan besaran itu
> **terbantah oleh langkah kedua**, dan koreksinya di bawah. Yang selamat adalah
> bagian geometrinya; aritmetika besarannya tidak.

Karena itu `refine` **mati secara bawaan** dan muncul sebagai pilihan di header
begitu HTF menyala. Dijaga oleh enam pengujian unit dan enam asersi kontrak API,
termasuk bahwa kotak hasilnya tidak pernah keluar dari kotak asalnya, karena
distal yang melar keluar akan **melonggarkan** stop yang justru ingin diketatkan
refinement.

> [!IMPORTANT]
> Siklus hidup dihitung ulang setelah kotaknya bergeser. Distal yang lebih sempit
> adalah pertanyaan berbeda atas bar yang sama: harga yang tidak pernah menutup
> melewati tepi lebar bisa saja sudah menutup melewati tepi sempit. Zona yang
> membawa `state` lamanya akan digambar segar di chart yang jelas-jelas
> menunjukkannya sudah jebol. Dijaga oleh
> `test_refinement_recomputes_the_lifecycle_it_invalidated`.

### Langkah kedua, dan separuh mana dari penjelasan itu yang selamat

Penjelasan geometri bracket di atas membuat sebuah ramalan, dan ramalan itu bisa
dijatuhkan: kalau seluruh kerugian refinement adalah konsekuensi aritmetis dari
stop yang lebih dekat, maka mengecilkan sekali lagi harus memungut kerugian
sebesar itu lagi. Diukur pada zona yang sama, bar yang sama, tiga lengan
berdampingan (sebagaimana digambar, disempurnakan sekali, disempurnakan dua kali),
dengan 536, 530, dan 530 zona menembus ketiganya.

| Reward | Langkah dua lawan langkah satu | Kumulatif lawan sebagaimana digambar |
|---|---|---|
| 0,5 ATR | **-7,5 pp** | -13,4 pp |
| 1,0 ATR | **-6,0 pp** | -10,9 pp |
| 2,0 ATR | **-3,0 pp** | -12,3 pp |

Ketiga selisih langkah dua signifikan. Jarak stop turun ke **48,8%** dari aslinya
setelah satu langkah dan **20,7%** setelah dua.

**Separuh yang bisa difalsifikasi bertahan.** Di setiap bin jarak stop yang kedua
lengannya punya 30 zona atau lebih, lengan yang disempurnakan dua kali bertahan
**sama tinggi atau lebih tinggi, tidak pernah lebih rendah**. Pada jarak stop yang
sama, zona yang disempurnakan dua kali bukan zona yang lebih buruk. Itu pernyataan
yang bisa gagal, dan ia tidak gagal.

**Bacaan besarannya yang gagal.** Aritmetika yang sama, dipakai pada penyusutan
kedua, meramalkan kira-kira 9 pp lagi di reward 2,0; yang terukur **-3,0**.
Ketergantungan pada geometrinya bahkan **berbalik**: langkah satu paling mahal di
reward 2,0 dan paling murah di 0,5, sedangkan langkah dua paling mahal di 0,5 dan
paling murah di 2,0. Jadi "hampir persis" pada angka 9,9 pp itu kebetulan yang
tampak meyakinkan, bukan mekanisme yang terbukti.

Dua kaveat yang harus ikut tercetak, karena keduanya membatasi kepada siapa angka
di atas berlaku:

- **192 dari 733 zona ditolak di langkah dua**, didominasi oleh penjaga
  containment yang memang dikirim. Yang selamat adalah **separuh yang lebih
  jinak**: penyusutan langkah satu mereka bermedian 45,9% dari jarak stop asal,
  lawan 28,1% pada zona yang gugur. Jadi angka dua langkah menggambarkan separuh
  yang lebih jinak dari zona yang sudah disempurnakan sekali, bukan populasinya.
- **Tidak ada apa pun di sini yang menemukan lantai.** Dua langkah terukur
  mengatakan berapa harga dua langkah, bukan di mana turun lagi berhenti masuk
  akal.

## Invalidasi karena zona lawan baru

Sebuah zona berhenti layak ketika jalan di depannya tertutup, dan jalan bisa
tertutup **tanpa harga bergerak sama sekali**: cukup ada zona lawan baru terbentuk
di jalurnya. Artinya validitas harus dievaluasi ulang pada peristiwa yang belum
pernah didengarkan kode ini, yaitu **zona lain lahir**.

`crowded_at` mencatat kapan itu pertama kali terjadi.

### Ini formalisasi saya, bukan doktrin

Penelusuran yang sama menemukan hal yang harus dinyatakan terang-terangan:

- **Tidak ada sumber primer yang menyatakan sebuah zona menjadi tidak valid
  ketika zona lawan baru terbentuk.** Paten OTA, yang merupakan kodifikasi
  algoritmik penuh dari metode ini, tidak memuat logika diskualifikasi berbasis
  zona lawan dan tidak memuat konstanta ambang reward:risk sama sekali.
- Prosa Seiden bersifat **monotonik tanpa titik potong**: "abaikan sebagian besar
  level dan fokus hanya pada yang jaraknya besar". Itu memilih yang lapang, bukan
  mematikan yang sempit.
- Lembar kerja OTA sendiri memberi skor 0 sampai 2 untuk reward:risk di dalam
  komposit, sehingga jalan yang buruk **tidak bisa membatalkan zona sendirian**.
  Itu bertentangan langsung dengan aturan invalidasi yang keras.
- Setiap kriteria invalidasi yang diterbitkan dalam literatur ini digerakkan
  **harga**: penutupan menembus zona, jumlah sentuhan, kedalaman penetrasi.
  Evaluasi ulang saat zona lain terbentuk tidak ada di mana pun.

> [!CAUTION]
> **Tabrakan istilah yang harus diketahui siapa pun yang membaca sumber sekunder
> metode ini.** "Profit margin" dipakai untuk dua hal yang berlawanan arah waktu.
> Seiden memakai aturan 3:1 untuk **perjalanan awal menjauh dari zona saat zona
> itu terbentuk** (mundur), sedangkan kompilasi pihak ketiga mengutipnya sebagai
> **jarak ke target pertama** (maju). Seiden sendiri menyumbang ambiguitasnya
> dengan menyebut uji mundur itu "1:3 risk/reward". Kode ini memakai dua nama
> berbeda dan tidak pernah mencampurnya: `profit_margin` mundur, `profit_zone_rr`
> maju.

### Karena itu ia sumbu terpisah, bukan `state`

`state` seluruhnya digerakkan harga: tersentuh, termakan, jebol. `crowded_at`
tidak. Zona yang dimakan harga dan zona yang terkurung pendatang baru adalah dua
situasi berbeda yang kebetulan sama-sama tidak bisa didagangkan, dan menggabungkan
keduanya ke satu enum akan membuang satu-satunya informasi yang membedakannya.

`crowded_at` adalah fakta historis dan tidak kedaluwarsa. Bila zona lawannya
kemudian jebol, jalannya terbuka lagi dan `profit_zone_rr` yang berlaku
mengatakannya; stempelnya tetap mencatat bahwa jalan itu pernah tertutup. Filter
opsional di API membuang zona yang jalannya tertutup **sekarang**, karena itu
pertanyaan yang sebenarnya sedang ditanyakan trader.

### Dan hasilnya diukur

Ini juga angka yang belum pernah diterbitkan siapa pun. Hasilnya ada di
[`CALIBRATION.md`](CALIBRATION.md) dan patut diringkas di sini karena ia
menentukan bawaannya: **jalan di depan adalah faktor peringkat pertama yang pernah
lolos di proyek ini** (AUC 0,565 sampai 0,584, CI bersih dari 0,5, dan bertahan di
kedua sisi sehingga drift tidak bisa memalsukannya). Meski begitu, sebagai gerbang
ia hanya sepakat 7 dari 8 potongan waktu di luar sampel, sementara gerbang
departure sepakat 8 dari 8 di ketiga geometri.

Jadi `min_profit_zone_rr` **mati secara bawaan**. Memeringkat di dalam sampel dan
bertahan sebagai gerbang di luar sampel adalah dua hal berbeda, dan hanya yang
kedua yang cukup untuk menyalakan sesuatu.

## Kanvas dibaca balik untuk kedua detektor baru

Selama beberapa hari klaim bahwa FVG dan order block tergambar di tempat yang
benar bersandar pada "keduanya lewat primitif gambar yang sama yang sudah
diverifikasi 0,5 piksel". Itu **penalaran, bukan pengukuran**, dan proyek ini
sudah empat kali keliru soal hal yang dinalar alih-alih diukur.
`e2e/pixel-truth.mjs` sekarang menerima nama detektor.

| Detektor | Kotak terukur | Tepi atas terburuk | Tepi bawah terburuk | Hasil |
|---|---|---|---|---|
| supply_demand | 9 | 0,5 px | 1,8 px | 6 dari 6 |
| fvg | 13 | 0,5 px | 1,7 px | **6 dari 6** |
| order_block | 12 | 0,5 px | 1,8 px | **6 dari 6** |

**Baris order block dikoreksi.** Versi sebelumnya file ini melaporkan 24 kotak
dan **5 dari 6** asersi, dengan tepi kiri terbaca pada 23 dari 24 kotak. Kotak
order block adalah **rentang satu candle**, jadi tepi kirinya duduk setengah bar
dari candle-nya sendiri, dan satu kotak kalah oleh candle tetangganya.
Pengukuran itu diambil ketika display cap masih 12, yang mengizinkan 24 kotak di
layar. Pada cap yang benar-benar dikirim, yaitu 6, maksimumnya 12 kotak dan
**seluruh 12 lulus**.

Cap yang lebih kecil hanya memperkecil kesempatan cacatnya muncul, jadi
penyebabnya dikejar sampai ketemu dan dihapus lewat konstruksi, bukan lewat
keberuntungan. Seluruh badan zona dicat pada z-order kanvas "bottom", yaitu
**sebelum** candle, sehingga garis batas kotak selebar satu candle duduk di bawah
candle-nya sendiri. Sekarang isiannya tetap di bawah candle sementara garis batas
dan garis proximal dicat **di atasnya**. Cakupan garis batas terburuk naik dari
0,909 ke **1,000**, dan cakupan tepi atas terburuk dari 0,845 ke **0,998**.

## Cacat yang tidak bisa dilihat oleh harness mana pun di repo ini

Ini entri keempat dari tema berulang file ini, **"gambarnya benar dan
presentasinya berbohong"**, dan ia layak mendapat bagian sendiri karena tidak
satu pun uji di repo ini yang bisa menangkapnya. Bukan karena ujinya kurang
teliti, melainkan karena bentuk cacatnya berada di luar apa yang mereka ukur.

Auditor chart di `app/llm.py` akhirnya bisa dijalankan, dijembatani ke CLI lokal
sehingga tidak butuh kunci API. Diberi tangkapan layar hasil render plus daftar
bentuk milik engine sendiri, ia melaporkan: engine menggambar **enam** zona,
sementara kanvasnya menampilkan **satu kotak utuh dan sepotong tipis kotak
kedua**. Empat sisanya duduk di bawah rentang harga yang dirender dan lenyap
bersama keterangannya.

Sebabnya: skala harga menskala otomatis ke **candle**, jadi zona mana pun yang
berada di luar rentang candle terpotong tanpa suara. Diperiksa ulang terhadap
tangkapan layarnya sesudah itu: sumbunya berhenti di 4360,00 sementara zona
memanjang sampai 4184,3.

Mengapa tidak ada harness yang bisa melihatnya: `e2e/pixel-truth.mjs` dan
`e2e/zone-audit.mjs` sama-sama mengukur zona yang **dikandung** kanvas. Cacat ini
justru zona yang **tidak** dikandung kanvas, jadi keduanya buta secara
struktural terhadapnya, bukan sekadar kebetulan tidak menemukannya.

**Perbaikannya memberi tahu pembacanya, bukan menskala ulang.** Menskala ulang
supaya zona yang jauh ikut masuk akan memampatkan candle-nya, dan itu persis
cacat tinta yang diukur proyek ini. Jadi yang dipasang adalah spanduk yang
menyebut berapa zona berada di luar layar dan ke arah mana, plus hitungan panel
yang berbunyi "N terlihat dari M", bukan "M digambar". Uji baru
`e2e/offscreen-zones.mjs` mereproduksi kasusnya dan lulus.

### Legendanya salah menggambarkan garis proximal

Legenda menyebut garis proximal sebagai "garis horizontal yang lebih terang **di
dalam** kotak". Diperiksa pada 34 zona di ketujuh jenis detektor: `proximal` sama
dengan `top` pada **setiap** zona demand dan sama dengan `bottom` pada **setiap**
zona supply, nol pengecualian. Ia berimpit dengan garis batas secara konstruksi
dan tidak pernah menjadi garis di dalam kotak. Yang salah teksnya, bukan garisnya.

## Apakah kita sudah mengadopsi ICT dengan benar

Jawaban singkatnya: **sebagian, dan bagian yang belum jauh lebih penting
daripada bagian yang sudah.**

Satu hal harus dikatakan lebih dulu supaya tabelnya tidak disalahbaca:
`supply_demand.py` **bukan ICT sama sekali.** Ia garis keturunan Sam Seiden dan
Online Trading Academy. Menilainya dengan penggaris ICT adalah salah kategori,
kecuali di satu tempat kosakatanya bertabrakan (`curve` lawan premium/discount).

Dan satu catatan provenans yang menentukan bobot seluruh bagian ini, **dan yang
versi sebelumnya file ini salah menyatakannya.** Dulu tertulis di sini bahwa
materi primer ICT tidak ada dalam bentuk yang bisa diambil. Itu keliru:
materinya **bisa** diambil. 35 transkrip SRT dari mentorship 2022, **211.989
kata**, sudah diunduh dan di-grep, dan kutipan di bagian MSS di bawah berasal
dari sana.

Sisa klaim lamanya tetap berlaku dan tidak dilunakkan. Tetap tidak ada buku,
tidak ada makalah, tidak ada glosarium kanonik, dan tidak satu pun sumber
peer-reviewed di seluruh garis keturunan ini. Transkripnya sendiri dihasilkan
mesin dan rusak secara kasatmata: "fear value gap" dan "fair Vega" untuk fair
value gap, "buys thoughts" untuk buy stops. Jadi tingkat sumbernya adalah
**transkrip otomatis atas video**, satu tingkat di atas blog dan jauh di bawah
sebuah dokumen. Selebihnya tetap kodifikasi vendor (LuxAlgo, yang menjadi
standar de facto karena skrip TradingView-nya paling banyak dipasang) dan blog
afiliasi yang sebagian terbaca seperti hasil generator.

> [!NOTE]
> Koreksi ini membuat dua pilihan yang sudah terpasang **lebih kuat dasarnya**,
> bukan lebih lemah. Kotak order block sebagai seluruh rentang lilin kini punya
> dukungan tier-a, bukan sekadar konvensi mayoritas. Dan "2 sampai 3 kali
> rentangnya" untuk displacement ternyata angka ICT sendiri, bukan karangan
> pihak ketiga.

### Yang sudah setia

| Konsep | Status |
|---|---|
| Geometri FVG (3 bar, wick ke wick, `<` ketat) | Setia, satu-satunya detektor tanpa diskresi |
| Kapan FVG bisa diketahui (lilin tengah tidak menguji gap buatannya sendiri) | Setia, dan ini properti anti-lookahead terpenting di file itu |
| Kotak order block = seluruh rentang lilin | Setia, dan sejak transkrip primer bisa diambil, ini didukung sumber tier-a, bukan sekadar konvensi mayoritas |
| Invalidasi lewat penutupan menembus tepi jauh | Setia, dan versi yang lebih ketat dari yang beredar |
| Swing fractal, tunda konfirmasi `confirmed_at = i + right` | Setia, dan rekayasa terbaik di repo ini |
| BOS lawan CHoCH lewat penutupan, break pertama selalu BOS | Setia, dan kehalusan yang kebanyakan implementasi salah |
| ATR ditunda satu bar di setiap ambang | **Lebih ketat daripada sumbernya.** Kebanyakan skrip SMC tidak melakukannya |

### Yang menyimpang

| Konsep | Penyimpangan |
|---|---|
| Order block "terakhir" | **Dulu salah, diperbaiki 2026-08-16.** Lihat CALIBRATION.md |
| Displacement pada FVG | Lebarnya gap dipakai sebagai proksi lilin displacement. Objek yang berbeda: gap lebar dari lilin lembut lolos, lilin agresif bergap 0,09 ATR dibuang |
| Displacement pada order block | Sekarang sebuah objek, `Zone.displacement`, bukan lagi ambang skalar telanjang. Ambang 1,5 ATR dalam 5 bar tetap angka repo sendiri; ICT menyebut 2 sampai 3 kali rentangnya. Uji strukturalnya dilaporkan lewat `broke_structure` |
| Order block tidak menuntut break of structure | **Sekarang tersedia lewat `require_structure_break`, tetapi mati secara bawaan.** Lihat angkanya di bawah |
| **Breaker block** | **IMPLEMENTED_DEVIATES, dan ini harus dinyatakan.** Definisi ketatnya menuntut liquidity run, dan justru itu yang memisahkan breaker dari mitigation block. Materi tier-a juga menandai lilin **searah** sebelum raid, bukan lilin lawannya. Yang dikirim repo ini adalah bacaan yang oleh kodifikasi terpasang-terbanyak sendiri disebut versi ritel yang lebih longgar |
| Liquidity sweep | Yang dikode adalah "wick melewati swing dan penutupannya tidak". Pembalikan kini **dilaporkan** lewat `reversed_within`, tetapi tetap bukan syarat; tetap tanpa displacement, tetap tanpa equal highs. Karena levelnya tetap terpasang, satu level bisa memancarkan sweep tanpa batas: 8.725 sweep lawan 9.210 break |
| `curve` bukan premium/discount ICT | Tetap benar tentang `curve`, dan sengaja dibiarkan begitu: rentangnya 200 bar bergulir, dibagi tiga, dibekukan saat zona lahir. Bacaan ICT sekarang berdiri sebagai medan terpisah, `dealing_range_pos`, bukan menimpa bacaan Seiden |

### Yang diadopsi, dan dengan syarat apa

Kelima butir yang dulu berdiri di sini sebagai "belum ada sama sekali" sudah
dikerjakan, dan tabel ini menggantikan daftarnya. Market Structure Shift, yang
dulu butir nomor satu, mendapat bagiannya sendiri di bawah karena definisi yang
dipakai engine ini ternyata ikut salah. Satu baris tambahan datang dari tabel
penyimpangan, yaitu order block yang menuntut break of structure.

| Konstruk | Status | Bentuk yang dikirim |
|---|---|---|
| Inversion FVG dan breaker block | **Dikirim**, detektor `ifvg` dan `breaker` | Geometrinya persegi induk yang dimasuki lagi **dari sisi berlawanan**. `break_index`, yang selama ini dihitung `replay_lifecycle` lalu dibuang setiap pemanggil, ternyata peristiwanya |
| Premium/discount pada dealing range ICT | **Dikirim**, `Zone.dealing_range_pos` | Dibaca pada **sentuhan pertama**, di rentang swing ke swing. Terpisah dari `curve` |
| Displacement sebagai objek | **Dikirim**, `Zone.displacement` | `time_from`, `time_to`, `atr`, `broke_structure`, `left_gap` |
| Order block menuntut break of structure | **Tersedia, mati secara bawaan** | `require_structure_break` |
| Struktur internal lawan swing sebagai konjungsi | **Dikirim** sebagai overlay struktur pasar | `swings` dan `structure` masuk amplop gambar; dua skala fraktal disilangkan untuk pertama kalinya lewat `aligned_with_swing`; penolakan sweep dilaporkan lewat `reversed_within`; MSS menjadi objeknya sendiri |

Overlay strukturnya **digambar untuk kesetiaan, tidak pernah sebagai sinyal**.
Begitu pula `ifvg` dan `breaker`: keduanya digambar dan **tidak** dijual sebagai
pembawa arah, karena H8 mengukur sentuhan pasca-inversi sebagai **negatif
signifikan** dibanding kontrol yang hanya tahu gerak berjalan.

> [!IMPORTANT]
> `broke_structure` bernilai None ketika struktur tidak dihitung, dan **None
> bukan False**. Siapa pun yang menyaring dengan `not broke_structure` akan
> membuang zona yang statusnya tidak diketahui bersama zona yang benar-benar
> gagal menembus struktur, lalu melaporkannya sebagai satu populasi.

#### Cacat tepi kiri pada kotak terinversi

Ditemukan dan diperbaiki di hari yang sama, dan dicatat karena ia **yang keempat
dari jenisnya di file ini**: kotak hasil inversi digambar dengan tepi kirinya di
bar asal **induknya**, sehingga ia mengklaim ada sepanjang jendela ketika pita
yang sama justru sisi lawannya. Terukur, bukan dinalar: **9 dari 9** breaker pada
satu deret 500 bar dimulai sebelum ia terinversi. Tepi kirinya sekarang
`inverted_at`.

Yang **tidak** diperbaiki oleh itu, dan harus dikatakan supaya perbaikannya tidak
dikreditkan lebih dari haknya: tabrakan sisi berlawanan tidak berubah, 100
menjadi 99, dan **nol** di antaranya ternyata kotak yang berdiri di sebelah
induknya sendiri. Inversi menuntut induknya jebol lebih dulu, dan `show_broken`
dikirim dalam keadaan mati, jadi induknya memang tidak pernah ada di layar pada
saat yang sama.

#### `dealing_range_pos` bukan `curve` yang diganti nama

Korelasi keduanya 0,842 dan 0,848 pada dua deret, jadi godaan untuk
memperlakukannya sebagai satu medan itu nyata. Tetapi keduanya **identik secara
numerik** hanya pada 43 dari 1835 dan 37 dari 2077 zona.

Anti-lookahead diverifikasi pada skala, bukan pada contoh: deret dipotong di bar
15.000 lalu ditandai ulang, dan **0 dari 1409** serta **0 dari 1568** nilai
berubah.

> [!WARNING]
> Pada PAXG 1h **kedua sisi terbaca tinggi**, demand 0,603 dan supply 0,560. Itu
> pola searah yang sama persis dengan yang dulu membongkar `curve` mentah sebagai
> drift, bukan sebagai posisi pada kurva. Tidak ada yang boleh menyekor medan ini
> tanpa memisahkan per sisi lebih dulu.

#### Order block dengan break of structure: angkanya ada, pembelaannya tidak

Dengan gerbangnya menyala, order block tinggal **26,5%** pada PAXGUSDT 1h (3536
menjadi 936), **29,9%** pada BTCUSDT 1h, dan **27,7%** pada XAUUSD 1h dari Yahoo.
Membuang tiga perempat populasi adalah keputusan yang butuh bukti, dan bukti itu
tidak ada: angka yang biasa dikutip untuk membenarkan syarat ini (52% lawan
65-68% pada 2.400 setup) **tidak bisa dilacak ke sumber mana pun**. Jadi tidak
ada kubu yang punya bukti, bukan hanya satu kubu, dan gerbangnya dikirim mati.

Perilaku bawaannya dibuktikan tidak berubah, bukan diasumsikan: modul versi
sebelumnya dimuat di proses yang sama, lalu setiap medan setiap zona
dibandingkan. Identik.

### Definisi MSS yang dipakai engine ini salah, dan sekarang diperbaiki

Engine ini memasangkan MSS sebagai "sebuah sweep, lalu break ke arah lawan". Itu
**dua pertiga** definisinya. Transkrip 2022 menolak bacaan dua bagian itu dengan
menyebut namanya:

> "It's not that it goes above this old, relative equal high, and then goes down
> below that - that's not it, folks, that's not it. You have to see it go below
> that in displacement with energetic move, take out a short term low."
> (Episode 24, 2022-05-06)

Dan displacement ia operasionalkan **bukan** sebagai ukuran lilin atau kelipatan
ATR, melainkan sebagai ketidakefisienan di dalam kakinya, dipakai sebagai
gerbang:

> "you don't have a trade entry yet, until you determine if it has a fair value
> gap. Where does that reside? Between the displacement high and the displacement
> low ... if there isn't one there, you don't have a trade."
> (Episode 6, 2022-02-04)

Karena itu sebuah MSS sekarang menuntut adanya fair value gap di dalam kaki dari
sweep sampai break, diuji dengan predikat `_gap` **yang sama** dengan yang dipakai
detektor FVG. Tidak ada angka yang dikarang di sini. Akibatnya: **52 menjadi 38**
MSS pada PAXGUSDT 15m, dan **58 menjadi 31** pada BTCUSDT 1h.

Dua penyimpangan tersisa, dan keduanya disebut terang-terangan:

- ICT **tidak** menuntut penutupan melewati levelnya ("we traded above it, it does
  not need to close above that. Okay, real important", Episode 3; "preferably
  close below that", Episode 6), sedangkan break di sini selalu menuntutnya. Jadi
  MSS engine ini adalah **subset ketat** dari MSS miliknya, bukan bacaan yang
  lebih longgar.
- ICT mengonfirmasi gap-nya pada bar **setelah** break. Membaca bar itu berarti
  memasukkan masa depan ke dalam peristiwa yang digambar pada bar break, jadi
  kakinya hanya dipindai sampai `break - 1`, dan sebuah MSS yang satu-satunya
  gap-nya justru mengangkangi bar break akan terlewat. Menutupnya butuh
  `confirmed_at` pada `StructureEvent`.

> [!IMPORTANT]
> Dua konstruk ICT yang benar-benar membawa klaim arah sudah **diuji dan
> keduanya gagal** pada 2026-08-16. Sentuhan pasca-inversi (H8) menambah
> **negatif signifikan** di ketiga detektor dibanding kontrol yang cuma tahu
> gerak 20 bar terakhir. Konjungsi sweep lalu MSS (H9) tidak pernah mendekati
> ambangnya, tandanya berbalik antar paruh, dan pada struktur besar konjungsinya
> **terlalu langka untuk diuji sama sekali** (7 dan 43 peristiwa). Rinciannya di
> [CALIBRATION.md](CALIBRATION.md).
>
> Satu kaveat yang harus dibawa ke mana pun hasil H9 dikutip: H9 memakai definisi
> MSS dua bagian yang baru saja dibantah di atas. Ia menguji sesuatu, dan yang
> diujinya bukan MSS menurut sumbernya.

### Klaim "sudah habis" yang berdiri di sini, dan mengapa ia salah

Dari dua kegagalan di atas, versi sebelumnya file ini menyimpulkan bahwa daftar
konstruk ICT yang membawa klaim arah **dan** bisa diuji dengan primitif yang ada
sudah habis, sehingga pertanyaan arah dari gambar bisa ditutup. **Kesimpulan itu
salah, dan salahnya empat kali.**

1. **Tiga konstruk yang dilabeli terhalang oleh file ini sendiri ternyata tidak
   terhalang apa pun.** Equal highs/lows, mitigation block, dan OTE seluruhnya
   OHLCV murni di atas `swings()` yang sudah ada. Tidak butuh instrumen kedua,
   tidak butuh jam. Yang pertama dibangun pada 21 Agustus 2026 sebagai
   `REQH`/`REQL`, yang menyelesaikan perdebatannya dengan cara paling murah:
   labelnya salah, dan dua sisanya masih belum dibangun dengan alasan yang sama
   salahnya.
2. **Alasan "kripto tidak punya sesi" tidak berlaku di repo ini.** Sudah ada
   Dukascopy XAUUSD dan EURUSD, waktu candle sudah epoch UTC, `resample.py` sudah
   punya `session_offset_hours`, dan `tools/costed.py` sudah mengerjakan
   aritmetika jam sesi. Satu-satunya yang kripto-saja adalah daftar `SERIES` di
   `tools/detectors.py`. Yang dilaporkan sebagai keterbatasan instrumen ternyata
   keterbatasan satu daftar.
3. **Enumerasinya tidak pernah ditutup sejak awal.** Konstruk bernama yang tidak
   muncul di dokumen mana pun di repo ini, baik di sini maupun di CALIBRATION.md:
   CISD, unicorn, turtle soup, SFP, IPDA data ranges, CRT, Model 2022, BPR,
   propulsion block, rejection block, implied FVG, immediate rebalance, SCOB,
   standard deviation projections, STH/ITH/LTH, IRL/ERL, quasimodo, weekly
   profiles, quarterly theory. Sebuah daftar tidak bisa dinyatakan habis kalau ia
   tidak pernah lengkap.
4. **H9 tidak menguji definisi yang diberikan sumbernya.** Ia menguji MSS dua
   bagian, dan sumbernya menolak bacaan itu dengan menyebut namanya. Lihat bagian
   MSS di atas.

Versi yang bisa dipertahankan, dan yang menggantikan klaim lama: **setiap
konstruk ICT berarah yang levelnya adalah ekstrem swing sudah diuji di sini, dan
semuanya gagal.** Itu klaim yang jauh lebih sempit, dan hanya itu yang benar-benar
diukur.

## Konstruk waktu, dan batas yang jujur untuk masing-masing

Semua yang di atas berpijak pada harga. Bagian ini berpijak pada **jam**, dan itu
kelas kesalahan yang berbeda: sebuah zona yang salah gambar terlihat salah, sebuah
kuarter yang salah jam terlihat benar sampai ada yang mengeceknya di hari
pergantian DST. Karena itu tidak ada satu pun angka di bagian ini yang diambil
dari contoh; semuanya properti yang diuji `tools/session_accuracy.py`, dan
hasilnya **26/26 lolos pada 3 deret, rentang 873 hari, 73.956 kuarter**.

### Gridnya menutup waktu, dan lubangnya adalah lubang yang diakui

| Derajat | Kuarter diuji | Lubang | Celah tak terduga | Tumpang tindih |
|---|---|---|---|---|
| year | 11 | 0 | 0 | 0s |
| month | 115 | 10 x 604.800s | 0 | 0s |
| week | 500 | 124 x 255.600 / 259.200 / 262.800s | 0 | 0s |
| day | 3.492 | 0 | 0 | 0s |
| session | 13.968 | 0 | 0 | 0s |
| micro | 55.870 | 0 | 0 | 0s |

Dua lubang itu bukan bug, dan sebab keduanya berasal dari doktrinnya sendiri.
**Jumat bukan kuarter kelima**: kuarter mingguannya adalah Senin sampai Kamis, jadi
gridnya menutup Minggu 18:00 sampai Kamis 18:00 New York, tepat 96 jam, dan
menyisakan Jumat plus akhir pekan. Nominalnya 72 jam, yaitu 259.200s; dua
ukuran lainnya, 71 dan 73 jam, **adalah tanda tangan DST** dan justru bukti bahwa
tidak ada offset UTC yang dipatok mati di mana pun.

Di derajat bulan sebabnya berbeda dan lebih rapi daripada yang terlihat. Kuarter
bulanan adalah empat siklus minggu dari **Senin pertama** bulan itu, jadi kedua
tepi setiap lubang jatuh pada Senin 18:00 New York, dan konsekuensinya lubangnya
selalu **kelipatan bulat satu minggu**. Di rentang ini ia selalu tepat satu
minggu, 604.800s, dan hanya muncul di 10 dari sekitar 28 pergantian bulan; di
sisanya minggu keempat bulan lama bersambung langsung ke Senin pertama bulan baru
tanpa lubang sama sekali. Bukan lubang di setiap bulan, dan bukan lubang berukuran
sembarang.

Uji itu menolak lolos secara kebetulan dengan dua cara. Ia memisahkan "lubang yang
didokumentasikan" dari "celah lain", dan yang kedua harus nol. Dan ia memeriksa
bahwa jendelanya **benar-benar memuat pergantian DST** sebelum menyatakan apa pun
tentang DST: 2 offset UTC berbeda terlihat pada 3.492 kuarter harian, 0 di luar
jam 18, 00, 06 dan 12 New York. Sebuah uji zona waktu yang dijalankan pada jendela
tanpa transisi hanya mengukur keberuntungan.

Untuk true open, aturannya "tidak ada bar, tidak ada level" dan itu diuji dua
arah: 953 true open pada PAXGUSDT dan BTCUSDT, **0 yang bukan harga open bar itu
sendiri**. Pada yahoo:XAUUSD, 873 batas harian menghasilkan 595 level dan 278
absen, dengan **0 yang absen tanpa alasan**. Emas COMEX tutup; grid tidak
mengarang harga untuk menutupinya.

### DFR memenuhi aturannya, dan sumbernya tetap belum diverifikasi

Empat properti lolos di ketiga instrumen: rentangnya mulai sepertiga masuk ke Q1
dan berakhir di penutupan Q1, high dan low-nya memang ekstrem bar di jendela itu,
dan yang paling penting, **sebuah defining range tidak berubah ketika masa
depannya dibuang** (40 dihitung ulang pada penutupan Q1 masing-masing, 0 bergeser).
Itu asersi anti-lookahead, bukan pernyataan gaya.

Yang lolos di situ adalah **konsistensi implementasi**, bukan kebenaran aturannya.
DFR di sini bersumber tunggal, belum diverifikasi terhadap materi kursus tempat ia
berasal, dan tidak ada seorang pun, di dalam maupun di luar repo ini, yang pernah
menerbitkan statistik terukur atasnya. Verdict saya atas DFR pernah saya balik
sendiri di sesi pengukuran ketika bukti baru masuk, dan itu sebabnya kaveat ini
berdiri di sini alih-alih di catatan kaki.

### SSMT: angkanya nyaris seluruhnya ditentukan oleh pilihan pasangannya

| Pasangan | Laju divergensi | Hubungan |
|---|---|---|
| emas vs perak | 14,9% | berkorelasi, jenis pasangan yang dimaksud doktrinnya |
| emas vs platinum | 21,0% | berkorelasi |
| emas vs NASDAQ | 36,0% | berhubungan lemah |
| emas vs BTC | 43,3% | tidak berhubungan |
| emas vs DXY | 59,5% | berkorelasi **terbalik** |

Lajunya melacak korelasi dengan rapi, dan itu justru pemeriksaan kewajaran yang
membuat modul ini bisa dipercaya. Ia juga jebakan tafsir yang hampir terbit:
angka 43% pertama kali dilaporkan sebagai temuan, padahal ia diukur pada
gold-vs-BTC. **Mencari divergensi antara dua instrumen yang tidak berkorelasi
adalah kesalahan kategori, bukan sumber setup yang kaya.**

Satu cacat alat lagi yang layak dicatat karena bentuknya akan berulang: provider
sintetis **mengarang instrumen**. Ia dengan senang hati mengembalikan 76
divergensi terhadap simbol yang tidak ada. Sekarang responsnya membawa peringatan,
dan uji isolasinya memakai provider yang menolak, bukan yang mengarang.

### Bias top-down dan checklist: aturan pemiliknya, dihitung, tidak diukur

Bias membaca empat timeframe dan mensyaratkan **semuanya** sejalan, sesuai
prosedur pemiliknya. Bacaan yang tidak diketahui dan "belum ada break" sama-sama
**tidak** dihitung sebagai sejalan, dan field `disagreeing` menyebut timeframe yang
mematahkannya, karena verdict tanpa nama menyembunyikan satu-satunya hal yang bisa
ditindaklanjuti.

`ChecklistReport` sengaja **tidak membawa pass atau fail**. Kelima itemnya punya
provenance dan tingkat keyakinan berbeda: DFR bersumber tunggal, manipulation
adalah konjungsi bersih antara fase waktu dan sweep, dan laju SSMT bergantung penuh
pada tabel di atas. Satu centang hijau akan menyembunyikan item mana yang memikul
bebannya, dan akan menyajikan checklist yang dicentang **dengan tangan** oleh
pemiliknya sebagai sesuatu yang sudah divalidasi engine ini. Belum ada satu pun
dari kelimanya yang diukur terhadap hasil.

### Empat konstruk berikutnya, dan apa yang masing-masing tidak bisa dijanjikan

NDOG, NWOG, Event Horizon, CISD, liquidity pool, dan premium/discount berbasis
waktu sekarang ada kodenya. Tidak ada satu pun dari mereka yang punya statistik
terukur, dari siapa pun: pencarian tidak menemukan padanan dari dua studi fair
value gap yang sudah dipakai repo ini. Semuanya aturan gambar, dan yang berikut
ini adalah hal-hal yang ditemukan saat membangunnya, bukan saat mengukurnya.

**Event Horizon adalah satu-satunya objek di engine ini yang nilainya tidak
final saat lahir.** Setiap zona di sini selesai begitu ia terbentuk; tepinya
adalah harga yang sudah tercetak dan tidak pernah bergerak lagi. Sebuah level
Event Horizon tidak begitu: kedekatan diukur dalam ruang HARGA, bukan waktu, jadi
gap baru yang muncul di antara dua gap lama akan mengurutkan ulang pasangannya
dan **memindahkan level yang sudah ada di chart tanpa satu harga pun berubah**.
Seluruh harness pengukuran di repo ini dibangun di atas asumsi objek final saat
lahir, jadi apa pun yang mengukur level ini harus bertanya "berapa levelnya pada
bar N", bukan "berapa levelnya sekarang". Itu sebabnya `event_horizons` punya
parameter `as_of`, dan sebabnya jumlah gap yang disimpan bukan sekadar batas
tampilan: menjatuhkan satu gap **menghapus** sebuah level dan memasangkan ulang
tetangganya, sehingga dua nilai `keep` memberi dua himpunan level yang berbeda,
bukan yang satu himpunan bagian dari yang lain.

**CISD memindahkan ketergantungan ke medan yang belum pernah dipakai repo ini.**
Ia konstruk pertama di sini yang berpatokan pada harga OPEN sebuah lilin; order
block, FVG, sweep, dan BOS semuanya berpatokan pada high dan low. Dugaan awal
saya, dan saya tulis di brief-nya, adalah bahwa open lebih rawan berbeda antar
provider daripada ekstrem. **Dugaan itu tidak didukung datanya.** Pada 495 bar
15m yang dimiliki dua feed emas sekaligus:

| Medan | Beda tanda per bar |
|---|---|
| open lawan close, yang dipakai CISD | 3,84% |
| high lawan high sebelumnya | 3,04% |
| low lawan low sebelumnya | 4,45% |
| close lawan close sebelumnya | 3,44% |

Open duduk di tengah rombongan. Yang nyata bukan itu, melainkan
**pelipatgandaannya**: satu tanda yang terbalik memecah atau menyatukan satu
*run* utuh, sehingga beda input 3,84% per bar menjadi **beda 29% tentang bar mana
yang membawa CISD**, kira-kira delapan kali lipat. Ketika kedua feed sepakat soal
barnya, mereka hampir selalu sepakat soal jangkarnya (47 dari 49). Jadi mode
kegagalannya adalah peristiwa utuh yang hanya ada di satu feed, bukan level yang
melenceng. Kaveatnya: kedua feed itu instrumen berbeda, spot Dukascopy lawan
futures COMEX Yahoo, jadi angka di atas batas atas ketidaksepakatan, bukan
jawaban bersih.

**Killzone London dibuka pada satu-satunya jam yang bisa tidak ada.** Jendelanya
02:00 sampai 05:00 New York, dan transisi DST Amerika terjadi tepat pukul 02:00.
`clock.py` sempat menyatakan bahwa tidak ada batas kuarter yang pernah jatuh
antara 02:00 dan 03:00, sehingga pertanyaan ini tidak pernah muncul di sana. Di
sini ia muncul. Pada 9 Maret 2025 pukul 02:00 tidak ada; dengan `fold=0` ia
dipetakan ke 03:00 EDT dan killzone hari itu berdurasi dua jam nyata. Tidak ada
sumber yang menyatakan apa itu killzone 02:00 pada hari tanpa 02:00, jadi itu
**konsekuensi dari sebuah pilihan**, bukan kutipan, dan diuji langsung alih-alih
ditunggu muncul di chart. Jendela Asia tidak terpengaruh di kedua hari transisi.

**"In discount" bisa menjawab dirinya sendiri tiga cara sekaligus, dan pada
pembacaan langsung pertama ia melakukannya.** Anchor-nya bersumber tunggal, jadi
ketiga kandidat selalu dihitung dan dilaporkan. Pada emas 1h, 17 Agustus 2026:

| Anchor | Rentang | Posisi | Bacaan |
|---|---|---|---|
| parent_cycle | 4430,9 sampai 4493,1 | 0,365 | discount |
| parent_previous | 4422,3 sampai 4486,5 | 0,488 | discount |
| previous_quarter | 4441,4 sampai 4459,5 | 0,674 | **premium** |

Satu boolean akan mengatakan "in discount" dan menyembunyikan bahwa salah satu
anchor mengatakan sebaliknya. Karena itu ketidaksepakatan naik ke `notes`, bukan
disimpan di field yang tidak dibuka orang.

**Tiga batas tampilan baru, dan alasannya diukur.** Pada 1200 bar emas 1h: 53
gap, 212 pool, 131 CISD. Semua digambar apa adanya akan menghasilkan 53 pita yang
masing-masing memanjang ke tepi kanan, 212 ray bernama, dan satu peristiwa di
setiap bar kesembilan. Batasnya mengikuti preseden yang sudah ada, `max_quarters`
dan `max_events`, dan seperti keduanya: nol berarti tanpa batas, dan setiap
pengukuran wajib melewatkan nol. Untuk gap, batasnya juga memangkas **pita**, bukan
hanya level, karena 53 pita di samping 4 level yang berasal dari lima di antaranya
adalah gambar yang tidak bisa dibaca balik ke masukannya sendiri.

## Yang belum diuji

- **Premis mekaniknya sendiri.** Cerita "order institusional yang belum terisi"
  diperdebatkan dan tidak bisa diverifikasi dari data harga. Yang bisa diuji hanya
  apakah zonanya informatif, dan itulah yang diuji di `CALIBRATION.md`.
- **Konstruk ICT yang tidak pernah masuk enumerasi mana pun di repo ini.**
  Unicorn, turtle soup, SFP, IPDA data ranges, CRT, Model 2022, BPR, propulsion
  block, rejection block, implied FVG, immediate rebalance, SCOB, standard
  deviation projections, STH/ITH/LTH, IRL/ERL, quasimodo, weekly profiles.
  Ditambah dua yang salah dilabeli terhalang, yaitu mitigation block dan OTE,
  yang sebenarnya OHLCV murni di atas `swings()`. Yang ketiga, equal highs/lows,
  sudah dibangun pada 21 Agustus 2026 sebagai `REQH`/`REQL` dan pindah ke
  kategori di bawah ini: ada kodenya, ada properti yang menjaganya, belum diukur.
- **Dibangun, diuji sebagai properti, tetap tidak diukur.** Quarterly theory dan
  CISD keluar dari daftar "tidak pernah dienumerasi" di atas, bersama NDOG, NWOG,
  Event Horizon, liquidity pool, dan premium/discount berbasis waktu: sekarang ada
  kodenya dan ada properti yang menjaganya, lihat bagian konstruk waktu. Yang
  belum ada tetap yang paling penting, dan berlaku untuk ketujuhnya: tidak ada
  satu pun angka yang menghubungkan mereka dengan hasil trade. **Dibangun bukan
  diukur**, dan dua kata itu tidak boleh saling dipinjam.
- **`tCISD`, varian berbasis waktu dari CISD.** Disebut namanya di sumber yang
  sama, sengaja tidak dibangun, dan tidak ada yang mendekatinya di sini.
- **Varian NWOG yang mengukur ke Senin 09:30.** ICT mengirim dua bacaan; yang
  dipakai di sini bacaan "actual", yang juga dipakai setiap kodifikasi pihak
  ketiga. Yang satunya jalan yang tidak diambil, dan menambahkannya nanti berarti
  `kind` kedua, bukan menyunting yang ini.
- **`confirmed_at` pada `StructureEvent`.** Tanpa itu, MSS yang satu-satunya
  gap-nya mengangkangi bar break tetap terlewat, dan itu penyimpangan yang
  diketahui, bukan yang dicurigai.
- **Keterbacaan chart lima detektor.** Sekarang terukur lebih sulit dibaca: 198
  zona, tinta 31,6%, dan pada deret terburuk 42,3%. Belum ada yang mengukur pada
  angka berapa gambarnya berhenti bisa dipakai.

> [!NOTE]
> Dua butir yang dulu berdiri di daftar ini sudah dicoret karena sudah diukur,
> bukan karena ditinggalkan. **Sentuhan kedua dan seterusnya**: keunggulan
> gerbang departure ternyata gejala sentuhan pertama, tinggal -0,2 / -2,5 / -4,3
> pp pada sentuhan kedua dan seterusnya, lihat [`CALIBRATION.md`](CALIBRATION.md).
> **Refinement bertingkat**: langkah keduanya sudah diukur, lihat bagian langkah
> kedua di atas.

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
> memotong tinggi ke 48,6%, yaitu memindahkan zona ke kuartil terpendek, dan
> selisih 9,9 poin persen yang terukur di sini **hampir persis** rentang yang
> dijelaskan geometri bracket itu. Jadi yang dibeli refinement adalah stop yang
> lebih dekat, dan yang dibayarnya adalah konsekuensi aritmetis dari stop yang
> lebih dekat. Tidak ada informasi yang hilang, hanya risiko yang dipindahkan.
> Rinciannya di [`CALIBRATION.md`](CALIBRATION.md) bagian konfon jarak stop.

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
| order_block | 24 | 0,5 px | 1,8 px | **5 dari 6** |

**Order block gagal satu asersi, dan itu dicatat apa adanya:** tepi kiri terbaca
pada 23 dari 24 kotak, sementara asersinya menuntut seluruhnya. Kotak order block
adalah **rentang satu candle**, jadi tepi kirinya duduk setengah bar dari
candle-nya sendiri - kasus yang secara geometris lebih sempit daripada base
berbilang bar milik supply and demand. Satu kotak dari 24 kalah oleh candle
tetangganya.

Ini cacat kecil pada keterbacaan, bukan pada penempatan: penempatan vertikalnya
tetap 0,5 dan 1,8 piksel, sama dengan detektor lama. Dilaporkan sebagai gagal
karena memang gagal.

## Apakah kita sudah mengadopsi ICT dengan benar

Jawaban singkatnya: **sebagian, dan bagian yang belum jauh lebih penting
daripada bagian yang sudah.**

Satu hal harus dikatakan lebih dulu supaya tabelnya tidak disalahbaca:
`supply_demand.py` **bukan ICT sama sekali.** Ia garis keturunan Sam Seiden dan
Online Trading Academy. Menilainya dengan penggaris ICT adalah salah kategori,
kecuali di satu tempat kosakatanya bertabrakan (`curve` lawan premium/discount).

Dan satu catatan provenans yang menentukan bobot seluruh bagian ini: **materi
primer ICT tidak ada dalam bentuk yang bisa diambil.** Tidak ada buku, tidak ada
makalah, tidak ada glosarium kanonik; primernya sebuah kanal YouTube. Yang
tersedia hanyalah kodifikasi vendor (LuxAlgo, yang menjadi standar de facto
karena skrip TradingView-nya paling banyak dipasang) dan blog afiliasi yang
sebagian terbaca seperti hasil generator. Tidak satu pun angka di bawah ini
berasal dari sumber peer-reviewed, karena tidak ada.

### Yang sudah setia

| Konsep | Status |
|---|---|
| Geometri FVG (3 bar, wick ke wick, `<` ketat) | Setia, satu-satunya detektor tanpa diskresi |
| Kapan FVG bisa diketahui (lilin tengah tidak menguji gap buatannya sendiri) | Setia, dan ini properti anti-lookahead terpenting di file itu |
| Kotak order block = seluruh rentang lilin | Setia pada konvensi mayoritas |
| Invalidasi lewat penutupan menembus tepi jauh | Setia, dan versi yang lebih ketat dari yang beredar |
| Swing fractal, tunda konfirmasi `confirmed_at = i + right` | Setia, dan rekayasa terbaik di repo ini |
| BOS lawan CHoCH lewat penutupan, break pertama selalu BOS | Setia, dan kehalusan yang kebanyakan implementasi salah |
| ATR ditunda satu bar di setiap ambang | **Lebih ketat daripada sumbernya.** Kebanyakan skrip SMC tidak melakukannya |

### Yang menyimpang

| Konsep | Penyimpangan |
|---|---|
| Order block "terakhir" | **Dulu salah, diperbaiki 2026-08-16.** Lihat CALIBRATION.md |
| Displacement pada FVG | Lebarnya gap dipakai sebagai proksi lilin displacement. Objek yang berbeda: gap lebar dari lilin lembut lolos, lilin agresif bergap 0,09 ATR dibuang |
| Displacement pada order block | 1,5 ATR dalam 5 bar adalah angka karangan sendiri, dan sudah dinyatakan begitu. ICT menuntut uji **struktural**, bukan uji besaran |
| Order block tidak menuntut break of structure | Penyimpangan ICT terbesar yang tersisa. Dulu beralasan `structure.py` belum ada; **alasan itu sudah kedaluwarsa** |
| Liquidity sweep | Yang dikode adalah "wick melewati swing dan penutupannya tidak". Tanpa syarat pembalikan, tanpa displacement, tanpa equal highs. Karena levelnya tetap terpasang, satu level bisa memancarkan sweep tanpa batas: 8.725 sweep lawan 9.210 break |
| `curve` bukan premium/discount ICT | Rentangnya 200 bar bergulir, bukan dealing range swing ke swing; dibagi tiga, bukan kuartil di sekitar ekuilibrium 50%; dibekukan saat zona lahir, padahal ICT membacanya saat sentuhan |

### Yang belum ada sama sekali, diurutkan menurut sentralitasnya bagi arah

1. **Market Structure Shift** (sweep lalu penutupan menembus struktur lawan).
   Inilah yang ICT klaim membawa arah, bukan CHoCH. H6 menguji BOS, CHoCH, dan
   SWEEP sebagai tiga kelompok terpisah dan **tidak pernah menguji
   konjungsinya.** Menguji bagian-bagiannya lalu menyatakan keseluruhannya mati
   adalah celah logika yang nyata. Primitifnya sudah lengkap.
2. **Inversion FVG dan breaker block.** Gap yang ditembus lalu berbalik peran.
   `replay_lifecycle` sudah menghitung `break_index` lalu **membuangnya**. Ini
   detektor termurah yang belum ada, dan CALIBRATION.md sudah menyebut celahnya
   sendiri: seluruh 11.469 sentuhan pertama datang dari sisi dekat, nol menembus
   kotak, jadi subsampel yang memisahkan penerusan dari pembalikan memang belum
   pernah ada.
3. **Premium/discount pada dealing range ICT**, dibaca saat sentuhan.
4. **Displacement sebagai objek**, bukan sekadar ambang skalar.
5. **Struktur internal lawan swing sebagai konjungsi.** Dua nilai N dijalankan
   berdampingan bukan berarti keduanya disilangkan; tidak ada yang pernah
   mengondisikan yang kecil pada yang besar.

Sisanya (equal highs/lows, mitigation block, OTE, killzone, SMT divergence,
Power of 3) entah butuh primitif lintas simbol yang tidak ada, atau butuh
instrumen ber-sesi yang bukan kripto, atau bersandar pada sumber tier terendah.

> [!IMPORTANT]
> Dua konstruk ICT tersisa yang benar-benar membawa klaim arah dan benar-benar
> murah diuji: **sentuhan pasca-inversi** dan **konjungsi sweep lalu MSS.**
> Selebihnya sudah terbantah, atau merupakan penyebutan ulang momentum, atau
> cacat kesetiaan yang harus diperbaiki sebelum diukur.

## Yang belum diuji

- **Premis mekaniknya sendiri.** Cerita "order institusional yang belum terisi"
  diperdebatkan dan tidak bisa diverifikasi dari data harga. Yang bisa diuji hanya
  apakah zonanya informatif, dan itulah yang diuji di `CALIBRATION.md`.
- **Sentuhan kedua dan seterusnya.** Semua pengukuran hasil di sini berhenti pada
  sentuhan pertama, termasuk yang baru.
- **Refinement bertingkat.** Turun satu timeframe diuji; turun dua tidak, dan
  tidak ada sumber yang menerbitkan lantai di mana turun lagi berhenti masuk akal.

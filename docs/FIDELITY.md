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

**Yang saya lakukan:** keduanya **dilaporkan**, tidak difilter. Alasannya di
bagian berikutnya.

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

### Enhancer yang belum ada, dan alasannya

| Enhancer | Status | Alasan |
|---|---|---|
| Strength of departure | **Ada**, tervalidasi | `departure_atr`, lutut di 2 ATR |
| Time at level | **Ada** | `compactness`, dihukum bertahap bukan dipotong keras |
| Freshness | **Ada** | `state` dan `touches` |
| Profit zone (mundur) | **Ada**, mati | `profit_margin`, lihat di atas |
| Profit zone (maju) | Belum | Perlu jarak ke zona lawan **segar** terdekat, artinya validitas zona bergantung pada pasangan zona, bukan pada zona sendiri |
| The Curve | Belum | Perlu rentang timeframe lebih tinggi sebagai acuan. Mesin MTF-nya baru ada; batas sepertiganya tidak pernah diterbitkan doktrinnya |
| Big picture / tren | Belum | Doktrinnya tidak pernah mendefinisikan cara mengukur tren |
| Arrival | **Sengaja tidak** | Sumber-sumbernya **saling bertentangan soal arahnya**. Memasangnya berarti menebak tanda |
| Skor gabungan dan gerbang 7/8/9 | **Sengaja tidak** | Tiga tabel terbit yang saling bertentangan, tanpa validasi di belakang satu pun. Kalibrasi di sini sudah menunjukkan skor gabungan tidak memeringkat apa pun |

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

## Yang belum diuji

- **Penyempurnaan zona (zone refinement).** Praktisi mengecilkan zona HTF dengan
  melihat candle LTF di dalamnya. Belum diimplementasikan.
- **Invalidasi karena zona lawan baru.** Panduan OTA menyebut sebuah zona berhenti
  layak ketika profit zone-nya jatuh di bawah minimum karena zona lawan baru
  terbentuk. Artinya validitas harus dievaluasi ulang saat **zona lain lahir**,
  bukan hanya saat harga bergerak. Belum ada.
- **Premis mekaniknya sendiri.** Cerita "order institusional yang belum terisi"
  diperdebatkan dan tidak bisa diverifikasi dari data harga. Yang bisa diuji hanya
  apakah zonanya informatif, dan itulah yang diuji di `CALIBRATION.md`.

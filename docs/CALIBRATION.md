# Kalibrasi

Diukur ulang 2026-08-13 dengan `python -m tools.calibrate --bars 20000`,
`python -m tools.walkforward`, dan `python -m tools.reaction`. Angka mentahnya ada
di [`calibration.json`](calibration.json), [`walkforward.json`](walkforward.json),
dan [`reaction.json`](reaction.json).

> [!CAUTION]
> **Seluruh angka pada versi sebelumnya dokumen ini salah populasi.** Bacalah
> bagian pertama sebelum membandingkan dengan catatan lama. Kesimpulan pokoknya
> bertahan dan menguat, tetapi setiap n, setiap AUC, dan setiap selisih berubah.

> [!IMPORTANT]
> Ringkasan satu kalimat: **deteksi zonanya tervalidasi dan kini bertahan di luar
> sampel, tetapi zonanya tidak meramalkan arah.** Zona yang digambar bertahan
> jauh lebih sering daripada formasi yang ditolak gerbang, di 8 dari 8 potongan
> waktu yang belum pernah dilihat. Namun ketika harga tiba, ia tidak berbalik
> lebih sering daripada di kotak acak, dan 40 bar kemudian perpindahannya nol.
>
> Dua batasan ditemukan belakangan dan berlaku ke seluruh angka judul itu:
> keunggulan gerbangnya **hanya ada di sentuhan pertama**, dan setelah seleksi
> kohort dibebankan ia adalah **selang +15,1 sampai +21,3 pp**, bukan satu angka.

## Cacat yang membatalkan pengukuran sebelumnya

`tools/calibrate.py` menyetel `max_zones_per_side=100` dan menyebutnya
"semua batas tampilan dimatikan". Seratus adalah **nilai maksimum skema**, bukan
mati. Batas itu memilih **berdasarkan waktu**: detektor mengurutkan zona dari yang
terbaru lalu memotong.

Akibatnya pada `PAXGUSDT` 1h, 20.000 bar:

| | Sebelum | Sesudah |
|---|---|---|
| Zona ditemukan | 2030 | 2030 |
| Zona masuk sampel | 200 | 2030 |
| Rentang posisi dalam riwayat | 0,904 sampai 1,000 | 0,001 sampai 1,000 |
| Median posisi | 0,953 | 0,526 |

Jadi dokumen ini dulu mengklaim 20.000 bar per deret sementara sampelnya hidup di
**9,6% terakhir** riwayat setiap deret. Lima deret yang disebut independen
sebenarnya adalah satu periode pasar yang sama, baru saja lewat, pada aset kripto
yang berkorelasi. Ukuran sampelnya juga bukan 234 melainkan 2707.

Ini adalah **kali keempat** batas tampilan diam-diam merusak sebuah pengukuran di
proyek ini. Karena itu perbaikannya bukan menaikkan angkanya:

- `max_zones_per_side = 0` sekarang berarti **tanpa batas**, dan hanya nol yang
  berarti mati. Dijaga oleh `test_zero_disables_the_per_side_cap` dan satu asersi
  kontrak API.
- Dua pass lintas-zona (`profit_zone_rr` dan `crowded_at`) dipindahkan **ke dalam
  detektor, sebelum batas tampilan**. Sebelumnya keduanya dihitung di `main.py`
  terhadap 12 zona per sisi yang lolos tampil, jadi tembok yang tidak muat
  digambar menjadi tak terlihat dan jalan di depan zona terbaca lebih panjang
  daripada yang sebenarnya, persis sebesar yang dibuang batas itu.

Satu cacat kecil ikut ketahuan di jalan yang sama: nilai `profit_zone_rr` untuk
zona yang jalannya **kosong sama sekali** dipetakan ke 0,0 lewat `forward or 0.0`.
Nol adalah nilai terburuk pada skala itu, jadi kasus terbaik ditulis sebagai kasus
terburuk. Sekarang dipetakan ke batas atas.

## Pertanyaan yang diukur

Ketika harga kembali ke sebuah zona untuk pertama kali, apakah zona itu bertahan?
Apakah ada faktor yang bisa memisahkan yang bertahan dari yang jebol? Dan, sejak
pengukuran ini, dua pertanyaan baru: apakah harga benar-benar **berbalik** di
sana, dan apakah gerbangnya bertahan di bar yang belum pernah dilihat.

Bukan pertanyaan tentang untung-rugi. Tidak ada biaya, spread, maupun slippage di
mana pun dalam proyek ini.

## Tiga aturan yang membuat jawabannya jujur

1. **Skor dibaca pada saat sentuhan, bukan sesudahnya.** Skor pada chart jadi
   sudah tahu berapa kali harga kembali dan sedalam apa. Memakai angka itu untuk
   memeringkat hasil sentuhan pertama adalah penalaran melingkar.
2. **Pembandingnya base rate, bukan angka nol.** Hasilnya berbentuk bracket, dan
   geometri bracket saja sudah menetapkan tingkat kemenangan untuk deret tanpa
   drift.
3. **Ada dua kontrol, satu ringan satu berat.** *Placebo*: zona palsu berukuran,
   bersisi, dan berumur sama, dipindah ke harga acak. *Ditolak gerbang*: formasi
   asli yang gagal lolos `departure_min_atr`. Yang kedua adalah kontrol yang
   sesungguhnya, karena kedua kelompok sama-sama konsolidasi sungguhan dan
   satu-satunya beda adalah filternya.

Data: 20.000 bar per deret, lima deret (`PAXGUSDT` 15m dan 1h, `BTCUSDT` 15m dan
1h, `ETHUSDT` 1h).

**Definisi hasil.** Pada bar sentuhan pertama: BERTAHAN bila harga bergerak
`reward` ATR menjauh dari garis proksimal sebelum ada bar yang menutup melewati
garis distal. JEBOL bila sebaliknya. Bila satu bar mencapai keduanya, dihitung
JEBOL.

## Hasil, tiga geometri

| Kelompok | reward 0,5 ATR | reward 1,0 ATR | reward 2,0 ATR |
|---|---|---|---|
| **Zona digambar** (n=2707-2719) | **97,9%** | **85,8%** | **57,0%** |
| Placebo, harga acak | 63,4% | 55,2% | 38,1% |
| Ditolak gerbang (n=7488-7561) | 83,1% | 64,4% | 45,3% |
| Selisih vs placebo | +34,5 pp | +30,6 pp | +18,9 pp |
| **Selisih vs ditolak** | **+14,8 pp** | **+21,4 pp** | **+11,7 pp** |
| Uji dua proporsi vs ditolak | z=+19,64 | z=+20,82 | z=+10,47 |

Ketiganya p<0,0001. **Deteksinya nyata**, dan sekarang diukur pada sampel 11 kali
lebih besar yang mencakup seluruh riwayat, bukan ekornya.

### Seleksi yang belum pernah diungkap, dan ia menggeser angka judulnya

Baris tebal di tabel itu punya satu kebocoran yang tidak pernah dinyatakan di
mana pun pada halaman ini, dan arahnya **menyanjung gerbangnya**.

`replay_lifecycle` menguji jebol **sebelum** ia menguji apakah bar itu berada di
dalam zona, lalu keluar dari loop (`app/detect/supply_demand.py` baris 145-151).
Jadi bar yang **masuk ke zona sekaligus menutup melewati distal** tercatat
sebagai jebol dan **tidak pernah** tercatat sebagai sentuhan, dan zona itu keluar
dari seluruh sampel hasil.

Kalau kebocoran itu mengenai kedua kohort dengan porsi yang sama, ia tidak
menggeser selisih apa pun. Terukur, porsinya tidak sama:

| Kohort | Jebol tanpa pernah tercatat menyentuh | Porsi |
|---|---|---|
| **Lolos gerbang** (departure >= 2) | 366 dari 3611 zona | **10,14%** |
| Ditolak gerbang (departure < 2) | 406 dari 9052 zona | **4,49%** |

Zona yang lolos gerbang lebih dari dua kali lipat lebih sering hilang lewat pintu
itu, dan yang hilang adalah zona yang **jebol**. Batas bawahnya dihitung secara
konservatif: setiap zona semacam itu dinilai **gagal** pada sebuah sentuhan
pertama nosional. Pada reward 1,0 ATR angka judulnya bergerak dari **+21,30 pp ke
+15,08 pp**, dengan kohort lolos 76,7% pada n=3450 dan kohort ditolak 61,6% pada
n=9038.

> [!IMPORTANT]
> **Pernyataan judul yang jujur adalah sebuah selang, bukan satu angka: +15,1
> sampai +21,3 poin persen.** Ujung atasnya mengabaikan seleksi ini sepenuhnya,
> ujung bawahnya membebankan seluruhnya ke kohort yang lolos.

Perhatikan di mana ujung bawah itu mendarat: **+15,08 pp praktis berimpit dengan
+15,3 pp**, yaitu selisih di dalam pita umur yang diukur lewat jalur yang sama
sekali berbeda di [bagian umur dan gerbang](#umur-dan-gerbang-dan-klaim-yang-saya-bantah-sendiri).
Dua koreksi yang tidak berbagi satu pun langkah perhitungan berhenti di tempat
yang sama.

Ini **belum pernah diungkap di dokumen mana pun di sini**. Daftar "Yang tidak
diukur" hanya menyebut bahwa zona yang tidak pernah disentuh tidak punya hasil;
ia tidak pernah memecah seleksi itu menurut kohort, dan justru pemecahan itulah
yang mengubah angkanya.

## Bertahan di luar sampel

Ini pengukuran yang belum pernah ada di sini. Riwayat dibelah menjadi sembilan
potongan berurutan; delapan dinilai. Peristiwa latih yang labelnya masih dalam
proses ketika potongan uji dibuka **dibuang** (purging), karena label itu sudah
melihat sebagian periode yang akan menilainya.

Tidak ada embargo, dan itu struktural bukan kelalaian: tata letaknya maju
sepenuhnya, latih selalu lebih awal daripada uji, jadi tidak ada data latih yang
bisa jatuh sesudah potongan uji.

**A. Gerbang 2,0 ATR yang dikirim, diterapkan apa adanya ke tiap potongan:**

| Reward | Selisih per potongan | Sepakat | Sign test |
|---|---|---|---|
| 0,5 ATR | +11,9 sampai +17,8 pp | 8 dari 8 | p=0,0078 |
| 1,0 ATR | +17,6 sampai +26,3 pp | 8 dari 8 | p=0,0078 |
| 2,0 ATR | +5,1 sampai +19,6 pp | 8 dari 8 | p=0,0078 |

**B. Ambang yang dipilih hanya dari potongan sebelumnya, dinilai di potongan
berikutnya:** juga 8 dari 8 di ketiga geometri, p=0,0078.

Ambang yang dipilih masa lalu tidak menyatu ke 2,0: ia memilih 0,5 pada geometri
ketat dan 4,0 pada geometri lebar. Selisih out-of-sample-nya tetap sebanding
dengan gerbang yang dikirim. Itu konsisten dengan temuan lama bahwa `departure`
adalah **ambang dengan dataran luas**: punya gerbang penting, letak persisnya
tidak.

> [!NOTE]
> p=0,0078 adalah **nilai terkecil yang mungkin** untuk sign test atas 8
> potongan. Karena itu jumlah potongannya sembilan dan bukan enam: dengan lima
> potongan yang dinilai, nilai terkecilnya 0,0625, dan uji yang jawaban
> terbaiknya "tidak signifikan" bukan uji.

## Sentuhan kedua dan seterusnya, dan gerbangnya tidak ikut ke sana

Daftar "Yang tidak diukur" di halaman ini selalu dibuka dengan baris yang sama:
semua pengukuran berhenti di sentuhan pertama. `tools/later_touches.py`
mengakhirinya, dan jawabannya tidak menyenangkan.

Populasi: enam deret (`PAXGUSDT` 15m dan 1j, `BTCUSDT` 15m dan 1j, `ETHUSDT` 1j,
`XAUUSD` 1j dari Yahoo), parameter POPULATION, `max_zones_per_side=0`, sekitar
27.000 peristiwa sentuhan, sekitar 15.600 di antaranya pada sentuhan kedua atau
lebih. Yang diterapkan adalah gerbang yang **benar-benar dikirim** (lolos berarti
`departure >= 2,0` ATR), pada tiap nomor sentuhan, dan angkanya selisih kohort
lolos dikurangi kohort ditolak.

| Sentuhan | reward 0,5 ATR | reward 1,0 ATR | reward 2,0 ATR |
|---|---|---|---|
| **1** | **+14,5 pp** | **+21,3 pp** | **+11,5 pp** |
| 2 | +0,2 | -0,5 | -3,2 |
| 3 | +0,3 | -2,5 | -4,7 |
| 4 | -1,0 | -4,7 | -5,9 |
| 5 | -1,7 | -6,7 | -5,2 |
| **Gabungan 2 ke atas** | -0,2, tidak signifikan | **-2,5** (z=-3,44, p=0,0006) | **-4,3** (z=-4,78, p<0,0001) |

Di sentuhan pertama pada reward 0,5, kohort lolos berisi 3086 peristiwa lawan
8641 yang ditolak. Sesudah sentuhan pertama keunggulannya **hilang seluruhnya**,
dan pada dua geometri ia menyeberang ke negatif dengan signifikansi.

**Bracket setara-R, dan ia mengubah bacaannya.** Bracket kedua (target 2,0 kali
tinggi zona) dijalankan **setelah** tabel di atas dilihat, jadi ia ditandai **post
hoc dan dikeluarkan dari putusan**. Hasilnya: sentuhan 1 **+16,4 pp**, gabungan 2
ke atas **+0,7 pp** dan tidak signifikan. **Tandanya berbalik antar bracket**, dan
halaman ini sudah punya diagnostik untuk persis itu: besaran yang berbalik tanda
antara dua bracket yang menilai tinggi zona secara berlawanan adalah tinggi zona.

> [!WARNING]
> Jadi negatif di sentuhan 2 ke atas adalah **tinggi zona, bukan gerbang yang
> bekerja terbalik**. Bedanya menentukan: "gerbangnya berhenti bekerja" dan
> "gerbangnya bekerja terbalik" adalah dua klaim yang berbeda, dan hanya yang
> pertama didukung data ini. Tidak ada gerbang kontrarian yang boleh dibaca dari
> tabel itu.

Per sisi pada sentuhan 2 ke atas, reward 1,0: **demand -4,3 pp** (signifikan),
**supply -0,6 pp** (tidak). Gerbangnya **buta sisi secara konstruksi**, jadi hasil
yang hanya muncul di satu sisi adalah peringatan tentang pengukurannya, bukan
temuan tentang pasarnya.

> [!IMPORTANT]
> **Nilai terukur gerbang departure adalah gejala SENTUHAN PERTAMA.** Setiap zona
> sentuhan kedua dan seterusnya yang digambar chart ini melewati **tidak satu pun
> filter yang pernah divalidasi proyek ini.**

Empat kaveat, dan semuanya dicetak karena tabel di atas tidak berdiri tanpa
mereka:

1. **Tautologi distal menggigit tabel sekundernya.** Bar yang menutup melewati
   distal sekaligus menggagalkan sentuhan itu **dan** mematikan zonanya, jadi
   sebagian dari "sentuhan belakangan lebih sering gagal" mengulang "sentuhan
   terdekat ke kematian adalah yang mati". Ini konfon yang sama yang sudah
   dibuang sekali di H1, dan di sini ia belum dibuang.
2. **Pita umurnya lebar.** Pita tertua membentang dari 34 sampai 15.650 bar, jadi
   pengendalian umurnya kasar.
3. **Satu deret menanggung sebagian besar negatifnya.** `PAXGUSDT` 1j sendirian
   memberi -8,7 pp di reward 2,0.
4. **Peristiwa yang bertumpuk tidak diberi bobot keunikan**, jadi n efektifnya
   lebih kecil daripada n nominal, sebagaimana berlaku di seluruh halaman ini.

## `departure` adalah ambang, bukan gradien

Dihitung atas seluruh populasi, termasuk yang ditolak.

| Departure (ATR) | n | held @0,5 | held @1,0 | held @2,0 |
|---|---|---|---|---|
| 0 sampai 1 | 5547-5604 | 78,8% | 61,1% | 44,6% |
| 1 sampai 2 | 1941-1957 | 95,4% | 73,8% | 47,1% |
| **2 sampai 3** | 908-914 | **97,7%** | **84,0%** | **53,5%** |
| 3 sampai 4 | 566-567 | 97,4% | 83,6% | 52,7% |
| 4 sampai 5 | 387-389 | 99,2% | 86,3% | 64,1% |
| 5 ke atas | 846-849 | 97,8% | 88,9% | 60,4% |

Polanya sama seperti sebelumnya dan kini jauh lebih tegas: naik tajam sampai 2-3
ATR lalu mendatar. Gerbang di 2,0 berada di tempat yang benar.

## Jalan di depan zona: faktor pertama yang benar-benar memeringkat

`profit_zone_rr` mengukur jarak dari garis proksimal zona ke zona lawan hidup
terdekat, dalam satuan tinggi zona itu sendiri. Ini satu-satunya faktor yang
pernah lolos di proyek ini.

| Reward | AUC | CI 95% | Paruh 1 / paruh 2 | Putusan |
|---|---|---|---|---|
| 0,5 ATR | 0,584 | [0,512, 0,658] | 0,617 / 0,548 | membedakan |
| 1,0 ATR | 0,571 | [0,541, 0,603] | 0,553 / 0,590 | membedakan |
| 2,0 ATR | 0,565 | [0,543, 0,588] | 0,538 / 0,592 | membedakan |

CI bersih dari 0,5 di ketiganya dan tandanya sama di kedua paruh.

**Uji konfon yang menentukan.** Jalan panjang untuk zona **demand** berarti tidak
ada supply di atasnya, yang pada sampel menanjak hanyalah cara lain mengatakan
"harga sedang di puncaknya". Itu deskripsi drift. Karena jalan panjang untuk
**supply** berarti lokasi yang berlawanan, efek mekanis harus muncul di **kedua
sisi**, sedangkan artefak drift hanya muncul di satu sisi.

| Reward | Demand | Supply |
|---|---|---|
| 0,5 ATR | 0,535 [0,421, 0,656] | 0,620 [0,520, 0,714] |
| 1,0 ATR | 0,617 [0,565, 0,663] | 0,530 [0,486, 0,577] |
| **2,0 ATR** | **0,576 [0,546, 0,607]** | **0,553 [0,520, 0,582]** |

Pada geometri dengan tenaga uji terbesar, **kedua sisi bersih dari 0,5**. Drift
sendirian tidak bisa menghasilkan itu.

### Tetap tidak dijadikan gerbang bawaan

Sebagai penyaring, dampaknya diukur pada zona yang digambar saja, di reward 2,0:

| Gerbang | Zona tersisa | Held tersisa | Held terbuang |
|---|---|---|---|
| >= 0,5 | 80,3% | 59,0% | 48,7% |
| >= 1,0 | 60,5% | 61,1% | 50,7% |
| >= 2,0 | 36,1% | 63,4% | 53,4% |
| >= 3,0 | 23,7% | 64,0% | 54,8% |

Semua signifikan pada reward 1,0 dan 2,0. Lalu ia dijalankan lewat mesin yang
sama dengan gerbang departure:

| Reward | Sepakat out-of-sample | Sign test |
|---|---|---|
| 0,5 ATR | 6 dari 8 | p=0,29 |
| 1,0 ATR | 7 dari 8 | p=0,07 |
| 2,0 ATR | 6 dari 8 | p=0,29 |

**Ia tidak lolos.** Di mana gerbang departure sepakat 8 dari 8 di ketiga
geometri, jalan di depan paling bagus 7 dari 8. `min_profit_zone_rr` karena itu
tetap **mati secara bawaan** dan hanya dilaporkan. Bahwa ia memeringkat di dalam
sampel dan tidak bertahan sebagai gerbang di luar sampel adalah dua fakta yang
berbeda, dan keduanya dicetak.

## Konfon jarak stop, dan apa yang tersisa setelahnya

Ini pengukuran terpenting di halaman ini, karena setiap AUC lain bergantung
padanya.

Hasilnya adalah bracket dengan kaki reward sejauh `reward` ATR dari proksimal
tetapi kaki risiko sebesar **tinggi zona itu sendiri**. Jadi zona tidak dinilai
pada bracket yang sama satu sama lain: zona tinggi punya stop yang jauh dan lebih
sulit jebol **karena geometri saja**.

Terukur, di reward 2,0:

| Tinggi zona | n | Bertahan |
|---|---|---|
| 0,05 sampai 0,94 ATR | 677 | 52,4% |
| 0,94 sampai 1,23 ATR | 676 | 55,9% |
| 1,23 sampai 1,59 ATR | 677 | 58,2% |
| 1,59 sampai 2,50 ATR | 677 | **61,4%** |

Sembilan poin persen dari tinggi kotak saja. `zone_height_atr` sebagai faktor
memberi AUC 0,537 dan 0,540 dengan CI bersih dari 0,5. **Artinya apa pun yang
berkorelasi dengan tinggi zona akan tampak meramalkan, gratis, tanpa mengatakan
apa-apa tentang supply atau demand.**

Ujinya: apakah sebuah faktor tetap memeringkat **di dalam** pita tinggi yang sama.

| Faktor | AUC keseluruhan | Di dalam tiap kuartil tinggi (reward 2,0) |
|---|---|---|
| `profit_zone_rr` | 0,565 | 0,596, 0,583, 0,563, 0,583 |
| `tightness` | 0,463 | 0,510, 0,495, 0,511, 0,494 |
| `zone_height_atr` | 0,537 | 0,549, 0,522, 0,494, 0,516 |

**`tightness` runtuh ke 0,5 di dalam setiap pita.** Ia terbaca terbalik
(0,460 dan 0,463) sepanjang waktu bukan karena base yang rapat berkinerja buruk,
melainkan karena `tightness` hampir merupakan negatif dari tinggi zona menurut
definisinya. Ia memeringkat jarak stop, bukan mutu base. Satu temuan-tampak
dibatalkan.

**`profit_zone_rr` bertahan, dan justru menguat**: 0,596 / 0,583 / 0,563 / 0,583
di dalam pita, melawan 0,565 keseluruhan. Arah konfonnya memang sudah bisa
diduga dan ia bekerja **melawan** faktor ini: `profit_zone_rr` adalah jarak
dibagi tinggi, jadi zona pendek menaikkan nilainya sekaligus menurunkan tingkat
bertahannya. Efek sesungguhnya lebih besar daripada yang terbaca mentah.

`zone_height_atr` sendiri melemah di dalam pita, sebagaimana seharusnya, karena
di dalam satu pita tingginya hampir tidak berubah. Itu cek waras bahwa
stratifikasinya bekerja dan bukan sekadar meratakan segalanya.

> [!IMPORTANT]
> Konfon yang sama menjelaskan hasil refinement di
> [`FIDELITY.md`](FIDELITY.md) tanpa perlu penjelasan tambahan. Menyempurnakan
> zona memotong tingginya menjadi 48,6%, yaitu memindahkannya ke kuartil tinggi
> terbawah, dan kuartil itu bertahan 52,4% lawan 61,4%. Penurunan 9,9 poin
> persen yang terukur di sana **hampir persis** rentang yang dijelaskan geometri
> bracket. Refinement tidak membuat zonanya lebih buruk; ia memindahkan stop
> lebih dekat, dan itu memang konsekuensi yang diminta.

Kaveat metodologis yang mengikutinya, dan ia berlaku ke belakang: **peringkat di
dalam kelompok zona yang digambar tidak pernah membandingkan bracket yang sama.**
Perbandingan antar kelompok tidak terkena, karena placebo mempertahankan tinggi
zona aslinya dan kelompok ditolak gerbang punya sebaran tinggi yang sama. Jadi
+11 sampai +21 poin persen terhadap kelompok ditolak tetap berdiri; yang harus
dibaca dengan hati-hati adalah tabel AUC.

## Dua bracket, dan uji yang lahir dari perbedaannya

Konfon di atas punya obat, dan obatnya sekaligus jadi alat uji terbaik di
halaman ini.

Bracket kedua ditambahkan: target sejauh `reward` **kali tinggi zona itu
sendiri**, bukan `reward` ATR. Sekarang kedua kaki bracket berskala bersama dan
setiap zona dinilai pada reward-to-risk yang **sama persis**.

Yang terjadi berikutnya adalah kuncinya. Tinggi zona mengonfon kedua mode, tetapi
ke **arah berlawanan**:

| | Target ATR | Target setara-R |
|---|---|---|
| `zone_height_atr` | 0,534 (tinggi lebih baik) | 0,385 (tinggi lebih buruk) |

Di bawah target ATR, zona tinggi punya stop jauh dan jarang jebol. Di bawah
target setara-R, zona tinggi menuntut harga menempuh jarak absolut yang besar.
Keduanya benar dan keduanya geometri.

Karena kedua mode menilai tinggi secara berlawanan, muncul diagnostik gratis:
**faktor yang sebenarnya adalah tinggi zona berbaju lain HARUS berbalik tanda
antar mode. Yang tidak berbalik, bukan.** Tidak ada satu hubungan dengan tinggi
yang bisa menunjuk arah sama di bawah dua bracket yang menilai tinggi secara
berlawanan.

| Faktor | AUC target ATR | AUC setara-R | Putusan |
|---|---|---|---|
| **`profit_zone_rr`** | **0,574** | **0,655** | **LOLOS dua bracket** |
| **`age_bars`** | **0,569** | **0,538** | **LOLOS dua bracket** |
| `curve_position` | 0,539 | 0,518 | lemah di satu, belum terbukti |
| `profit_margin` | 0,507 | 0,642 | lemah di satu, belum terbukti |
| `arrival_atr` | 0,515 | 0,501 | tidak ada efek di kedua bracket |
| `base_drift` | 0,506 | 0,500 | tidak ada efek di kedua bracket |
| `road_is_clear` | 0,504 | 0,503 | tidak ada efek di kedua bracket |
| `tightness` | 0,466 | 0,615 | **berbalik: ini tinggi zona** |
| `compactness` | 0,456 | 0,548 | **berbalik: ini tinggi zona** |
| `base_overlap` | 0,477 | 0,555 | **berbalik: ini tinggi zona** |
| `volume` | 0,507 | 0,480 | **berbalik: ini tinggi zona** |
| `curve_favourable` | 0,520 | 0,483 | **berbalik: ini tinggi zona** |
| `vol_regime` | 0,505 | 0,447 | **berbalik: ini tinggi zona** |
| `with_trend_atr` | 0,487 | 0,525 | **berbalik: ini tinggi zona** |
| `formation_score` | 0,458 | 0,554 | **berbalik: ini tinggi zona** |

Hampir seluruh daftar odds enhancer doktrin yang bisa diukur di sini -
kerapatan base, kepadatannya, irisan antar bar, volume kaki keluar, posisi
kurva - ternyata **tinggi kotak dengan nama lain**. Termasuk skor komposit yang
menampung tiga di antaranya.

> [!NOTE]
> `tightness` adalah kasus paling telanjang. Ia hampir merupakan negatif dari
> tinggi zona menurut definisinya, terbaca 0,466 di satu bracket dan 0,615 di
> bracket lain, dan runtuh ke sekitar 0,5 di dalam pita tinggi yang sama pada
> bracket yang dikirim. Tiga bukti terpisah, satu kesimpulan.

### `age_bars`, dan mengapa walk-forward saja tidak cukup

Dua faktor lolos uji lintas-bracket. Yang kedua, `age_bars`, mengukur berapa lama
zona menunggu sebelum harga kembali, dan hasilnya sempat lebih meyakinkan
daripada apa pun yang pernah ada di sini:

- lolos uji lintas-bracket, 0,569 dan 0,538;
- lolos walk-forward **8 dari 8 potongan di ketiga geometri**, part A dan part B,
  p=0,0078, dengan ambang terpilih nyaris bulat.

Proyek yang menyalakan gerbang atas dasar bukti out-of-sample saja **akan
mengirimkannya**.

Ia gerbang departure yang menyamar. `departure` diukur dari kaki keluar sampai
**bar sentuhan**, jadi zona yang disentuh setelah dua bar punya departure yang
diukur pada dua bar dan kecil karena aritmetika, bukan karena lemah. Umur dan
departure karena itu terikat secara konstruksi. Di dalam pita departure yang
sama, efek umurnya lenyap dan berbalik:

| Bracket | AUC keseluruhan | Di dalam tiap kuartil departure |
|---|---|---|
| target ATR 2,0 | 0,543 | 0,532, 0,552, 0,525, **0,491** |
| setara-R 2,0 | 0,536 | **0,469, 0,508, 0,494, 0,457** |

**Walk-forward membuktikan sebuah efek STABIL. Ia tidak bisa membuktikan efek itu
bukan sesuatu yang sudah kita punya.** Dua uji itu menjawab pertanyaan berbeda
dan sebuah faktor harus lewat keduanya. `age_bars` dipertahankan di dalam
`tools/walkforward.py` sebagai negatif terdokumentasi, bukan dihapus.

### Umur dan gerbang, dan klaim yang saya bantah sendiri

Bacaan pertama atas harness sentuhan-lanjut di atas menghasilkan klaim yang
tampak masuk akal dan keluar lebih dulu: karena jendela departure **dipotong di
sentuhan pertama**, departure dan umur-saat-sentuhan-pertama terikat, sehingga
+21,3 pp di judul itu "sebenarnya" +7,6 pp dan sebagian besar sisanya adalah umur
atau pemotongannya.

Klaim itu diperiksa ulang secara adversarial, dan hasilnya terbelah rapi:
**mekanismenya benar, inferensinya salah.** Keduanya dilaporkan, dan bantahannya
yang jadi kesimpulan.

Harness pemeriksanya divalidasi lebih dulu terhadap angka yang sudah terbit: ia
mereproduksi `docs/calibration.json` **persis**, n=2710 lolos dan 7488 ditolak,
+21,37 pp, z=+20,82.

**DIKONFIRMASI, mekanismenya.** Pada deret sintetis dengan base yang identik
bita-per-bita dan kaki keluar yang juga identik bita-per-bita, `departure_atr`
terbaca sebagai berikut ketika sentuhan pertama digeser menjauh:

| Jarak sentuhan pertama (bar) | 1 | 3 | 5 | 9 | 17 | 19 | 21 ke atas |
|---|---|---|---|---|---|---|---|
| `departure_atr` | 8,037 | 8,901 | 9,765 | 11,494 | 14,951 | 15,383 | **datar** |

Ia **fungsi tangga yang monoton tidak menurun terhadap umur**, naik ketat hanya
selama sentuhannya jatuh di dalam `departure_lookahead` 20 bar, lalu berhenti.
Lantainya adalah seluruh ekskursi kaki keluar, jadi pemotongan itu **tidak pernah
mengecilkan pengukuran kaki keluarnya sendiri**.

**DIBANTAH, "dua dari tiga pita tidak terukur".** Hanya **satu** yang tidak.
Pita yang dipakai adalah tersil dari **seluruh** peristiwa sentuhan, lalu
diterapkan ke subhimpunan sentuhan pertama, padahal **54,4% sentuhan pertama
terjadi pada umur tepat 1 bar**. Titik potong 5 dan 34 karena itu adalah
persentil ke-75 dan ke-90 populasi itu, bukan tersil. Tersil sesungguhnya dari
populasi sentuhan pertama adalah 1 / 2-3 / 4 ke atas, dan gerbangnya
**signifikan di ketiganya**:

| Pita umur sentuhan pertama | Selisih gerbang | p |
|---|---|---|
| tepat 1 bar | **+35,8 pp** | <0,0001 |
| 2 sampai 3 bar | **+14,3 pp** | <0,0001 |
| 4 bar ke atas | **+13,1 pp** | <0,0001 |

**DIBANTAH, "keunggulannya sebenarnya +7,6 pp".** Angka +7,6 adalah yang
**terlemah dari tiga pita**, dibaca sebagai kalau ia mewakili semuanya. Selisih
di dalam umur yang dibobot strata (Mantel-Haenszel) pada pita yang sama itu
adalah **+15,3 pp**, dan ia berkisar **+13,3 sampai +17,6 pp** di delapan
pembagian pita yang berbeda. Angka pita tengahnya sendiri bergerak dari +2,5 ke
+14,8 pp tergantung pembagiannya, dan **angka yang berubah enam kali lipat
mengikuti pilihan sembarang bukan temuan**.

**Sel yang menentukan.** Pada umur **tepat 1 bar** tidak ada sisa ragam umur yang
mungkin tersisa untuk menjelaskan apa pun. Di sana, pada 5549 sentuhan pertama
atau 54% populasinya, selisihnya **+35,8 pp**: kohort lolos 98,0% pada n=51
lawan kohort ditolak 62,3% pada n=5498, z=+5,25. **Selisih terbesar di seluruh
tabel duduk persis di tempat umur tidak bisa menjelaskan apa-apa.**

**DIBANTAH, "pemotongannya yang jadi sebab".** Departure dihitung ulang **tanpa
pemotongan**, dan gerbangnya justru terbaca **lebih baik**, bukan lebih buruk:
gabungan +41,46 pp lawan +21,37, di dalam umur +40,2 pp, dan **setiap** pita umur
membaik. Korelasi Spearman antara umur dan departure turun dari +0,776 ke +0,389.

> [!CAUTION]
> Jendela yang tidak dipotong **membaca bar sesudah sentuhan**, jadi ia bukan
> gerbang yang bisa didagangkan dan angka +41,46 itu **tidak boleh dikutip
> sebagai kinerja**. Ia diagnostik mekanisme saja. Halaman ini sudah menetapkan
> bahwa jendela tak terpotong **over-admisi 34%**, dan itu tetap berlaku.

Pemisahannya juga tidak seluruhnya milik pemotongan. Setengahnya iya, setengahnya
tidak:

| Pita umur | Terpotong (lolos / ditolak) | Tanpa potong (lolos / ditolak) |
|---|---|---|
| muda | 51 / 5498 | **2468 / 3081** |
| tua | 994 / 20 | 994 / 20 |

Pita tua **tidak bergerak sama sekali**, dan sebabnya geometri: disentuh 34 bar
atau lebih setelah lahir dengan departure di bawah 2 ATR nyaris mustahil terjadi.

> [!IMPORTANT]
> Yang perlu dinyatakan dengan jujur: **halaman ini sudah mengungkap
> mekanismenya**, di bagian `age_bars` di atas ("Ia gerbang departure yang
> menyamar ... Umur dan departure karena itu terikat secara konstruksi"), dan
> sudah menjalankan pengondisiannya ke arah sebaliknya. Yang **baru** hanyalah
> tabel ke arah kebalikannya dan angka +15,3 pp itu.
>
> Dan inilah lubang yang sesungguhnya. Halaman ini secara eksplisit mengasuransi
> angka judulnya terhadap konfon **tinggi zona** ("placebo mempertahankan tinggi
> zona aslinya"), dan **tidak punya satu kalimat pun yang setara untuk UMUR**.
> **+15,3 pp adalah angka yang masuk ke lubang itu.**

### `profit_zone_rr` lolos semuanya

Satu-satunya faktor yang bertahan di setiap uji yang dilempar padanya:

| Uji | Hasil |
|---|---|
| AUC mentah, dua bracket | 0,574 dan 0,655, CI bersih dari 0,5 |
| Paruh pertama vs kedua | tanda sama di ketiga geometri |
| Per sisi demand dan supply | keduanya di atas 0,5, CI bersih di geometri terkuat |
| Di dalam pita tinggi zona | 0,596, 0,583, 0,563, 0,583 |
| Di dalam pita departure | 0,530, 0,546, 0,582, 0,565 |
| Uji lintas-bracket | tidak berbalik, dan justru menguat |
| **Walk-forward sebagai gerbang** | **7 dari 8, p=0,07. TIDAK lolos** |

Ia memeringkat, dan itu bertahan terhadap setiap konfon yang bisa saya pikirkan.
Ia tetap **tidak menjadi gerbang bawaan**, karena memeringkat dan menyaring
adalah dua klaim berbeda dan hanya yang kedua yang menentukan default.

### Sesi, dilaporkan sebagai tabel bukan peringkat

| Jam sentuhan (UTC) | n | Bertahan | vs base |
|---|---|---|---|
| 00:00-04:00 | 449 | 55,2% | -1,1% |
| 04:00-08:00 | 305 | 46,9% | -9,5% |
| 08:00-12:00 | 361 | 50,7% | -5,7% |
| 12:00-16:00 | 750 | 58,8% | +2,4% |
| 16:00-20:00 | 451 | 57,2% | +0,8% |
| 20:00-24:00 | 365 | 65,2% | +8,8% |

Rentang 18 poin persen, dan **tidak dijadikan apa pun**. Enam blok diuji tanpa
koreksi, sampelnya kripto yang berdagang 24 jam sehingga "sesi" di sini bukan
sesi bursa mana pun, dan tidak ada mekanisme yang diajukan lebih dulu. Dilaporkan
supaya bisa diperiksa ulang di instrumen yang benar-benar punya jam bursa.

> [!IMPORTANT]
> Jam sentuhan sempat masuk tabel AUC dan terbaca 0,540 sampai 0,545, tampak
> seperti temuan. Itu tidak berarti apa-apa: **AUC pada variabel siklik adalah
> omong kosong**, karena statistik peringkat menaruh jam 23 dan jam 0 di ujung
> yang berlawanan padahal keduanya bersebelahan. Sekarang ia hanya boleh muncul
> sebagai tabel, dijaga oleh konvensi nama berawalan garis bawah yang membuatnya
> tidak bisa masuk uji peringkat.

## Skor komposit masih tidak lolos, dan sekarang lebih buruk

| Faktor | AUC @1,0 | AUC @2,0 | Putusan |
|---|---|---|---|
| tightness | 0,460 [0,428, 0,491] | 0,463 [0,441, 0,485] | terbalik, dan **itu jarak stop**, lihat bagian di atas |
| compactness | 0,454 [0,424, 0,484] | 0,487 | terbalik di satu |
| volume | 0,526 | 0,504 | tidak terbedakan |
| base_drift | 0,497 | 0,499 | tidak terbedakan |
| profit_margin | 0,517 | 0,508 | tidak terbedakan |
| curve_position | 0,533 | 0,512 | lihat catatan |
| **formation_score** | **0,464** | **0,477** | **terbalik**, bukan sekadar tak berguna |

`volume`, yang dulu satu-satunya yang CI-nya pernah lepas dari 0,5, sekarang
0,526 dan 0,504 dengan CI melintasi 0,5. Efek lamanya adalah artefak sampel kecil
yang terkurung di ekor riwayat.

Yang lebih penting: `formation_score` bukan hanya gagal memeringkat, ia
**memeringkat terbalik**. Kuintil teratas bertahan lebih jarang daripada kuintil
terbawah. Karena itu keputusan lama, yaitu mengeluarkan angkanya dari label chart
dan tidak memasang bobot ke data, kini didukung bukti yang jauh lebih kuat.

`curve_position` lolos ambang mentah di reward 1,0 (0,533, CI [0,500, 0,566]),
dan pemisahan per sisi membantahnya lagi: **kedua sisi menunjuk arah yang sama**
di ketiga geometri, sedangkan doktrin menuntut arah berlawanan. Itu drift, bukan
kurva. Uji yang sama yang menangkapnya dulu menangkapnya lagi pada sampel 11 kali
lebih besar.

## Zona bersarang: hasil nol yang jauh lebih kuat

| Reward | Bersarang | Berdiri sendiri | Selisih | Uji |
|---|---|---|---|---|
| 0,5 ATR | 98,0% | 97,8% | +0,2 pp | p=0,73 |
| 1,0 ATR | 86,2% | 85,3% | +0,9 pp | p=0,53 |
| 2,0 ATR | 57,1% | 56,8% | +0,3 pp | p=0,88 |

n naik dari 234 ke 2707 dan jawabannya tidak bergerak. Ini satu-satunya aturan
multi-timeframe yang disepakati semua aliran, dan pada sampel ini **tidak ada
manfaat terukur sama sekali**. Titik estimasinya sekarang sedikit positif, bukan
sedikit negatif seperti pada sampel kecil, yang justru memperkuat pembacaannya:
efeknya nol, dan tanda pada sampel kecil adalah derau.

## Apakah harganya benar-benar berbalik di sana?

`tools/reaction.py`. Pertanyaan yang berbeda dari bracket: bukan "apakah stop
tersentuh lebih dulu", melainkan "apakah lintasan harga berubah".

Estimand utamanya adalah **selisih demand dikurangi supply**. Tulis rata-rata
gerakan setelah sentuhan sebagai `mu + delta` untuk demand dan `mu - delta` untuk
supply: drift masuk ke keduanya dengan tanda **sama**, efek zona dengan tanda
**berlawanan**, jadi selisihnya membatalkan drift tanpa model apa pun.

Empat kelompok, dua di antaranya baru:

| Kelompok | Mengendalikan |
|---|---|
| digambar | - |
| placebo, harga acak | **di mana** |
| tercocokkan, waktu acak | **kapan**, yaitu drift |
| ditolak gerbang | filternya |

### Lintasan rata-rata, zona digambar

| tau | Demand | Supply | Selisih |
|---|---|---|---|
| -20 | +1,423 | -1,363 | 2,786 |
| -5 | +1,800 | -1,652 | **3,452** |
| -1 | +1,081 | -0,964 | 2,044 |
| 0 | 0 | 0 | 0 |
| +1 | +0,009 | +0,047 | -0,038 |
| +10 | +0,070 | -0,081 | 0,151 |
| +40 | -0,075 | +0,130 | **-0,205** |

Selisih 3,45 ATR sebelum sentuhan runtuh menjadi nol sesudahnya. Yang besar itu
**pendekatan**, dan ia besar karena konstruksi: sebuah zona demand disentuh
ketika harga turun ke sana. Itu bukan bukti apa-apa. Yang bisa diklaim zona hanya
bagian yang terbuka setelah tau = 0, dan bagian itu nol.

### Pembalikan, dan siapa lagi yang melakukannya

Nilai bertanda sehingga positif berarti "zona bekerja":

| Kelompok | n | Perubahan kemiringan | vs digambar |
|---|---|---|---|
| digambar | 2711 | +0,0097 | - |
| placebo, harga acak | 9836 | +0,0114 | p=0,73, **tak terbedakan** |
| tercocokkan, waktu acak | 2711 | -0,0069 | p=0,0054 |
| ditolak gerbang | 7569 | -0,0259 | p=0,0001 |

Bacaannya, dan ini temuan pokoknya:

1. Harga **memang** berbalik di sentuhan pertama, dan kedua sisi menunjuk arah
   yang benar (selisih +0,019, p=0,029).
2. Harga berbalik **sama banyaknya di kotak yang ditaruh acak**. Placebo tidak
   bisa dibedakan dari zona yang digambar.
3. Harga **tidak** berbalik pada saat acak. Jadi efeknya nyata, tetapi ia milik
   peristiwa "tiba di sebuah level setelah sebuah lari", bukan milik level itu
   supply atau demand.
4. Pada formasi yang **ditolak gerbang**, harga justru menembus terus: kedua sisi
   menunjuk arah yang salah, p=0,0001.

Jadi yang sebenarnya dilakukan gerbang departure bukan memilih zona yang bekerja,
melainkan **membuang formasi yang aktif gagal**. Itu konsisten dengan +11 sampai
+21 pp terhadap kelompok ditolak, dan menjelaskan mekanismenya.

### Kaveat placebo, ditutup

Zona placebo digeser 1,5 sampai 5 ATR, jadi sentuhannya menyusul lari yang lebih
besar, dan pembalikan setelah lari besar memang lebih besar. Kalau itu yang
sebenarnya diukur, maka "digambar tak terbedakan dari placebo" bukan temuan
tentang zona sama sekali, melainkan artefak cara kontrolnya dibangun.

Cara menutupnya: bandingkan keduanya **di dalam pita besar-lari yang sama**. Di
dalam satu pita, kedua kelompok tiba dari jarak yang setara, jadi apa pun yang
memisahkan mereka adalah kotaknya.

| Lari masuk (ATR) | n digambar | Digambar | n placebo | Placebo | Selisih | p |
|---|---|---|---|---|---|---|
| -8,36 sampai -0,87 | 678 | -0,1708 | 3966 | -0,1293 | -0,0415 | 0,0001 |
| -0,87 sampai 1,19 | 677 | -0,0511 | 1250 | +0,0040 | -0,0551 | 0,0001 |
| 1,19 sampai 3,55 | 678 | +0,0564 | 1984 | +0,0689 | -0,0125 | 0,09 |
| 3,55 sampai 13,35 | 678 | +0,2042 | 2493 | +0,2053 | -0,0011 | 0,90 |

**Kotaknya mengalahkan level pada jarak yang sama di 0 dari 4 pita**, dan dua pita
yang signifikan justru berlawanan arah. Perhatikan ke mana risikonya menunjuk:
uji ini hanya bisa **melemahkan** kesimpulan sebelumnya, jadi hasil nol di sini
membuatnya kokoh, bukan sekadar bertahan dengan kaveat.

Yang juga terlihat di kolom itu adalah mekanismenya. Pembalikan naik monoton
mengikuti besar lari masuk (-0,17, -0,05, +0,06, +0,20) dan naik **sama
persisnya** untuk kotak acak. Jadi pembalikan di sentuhan pertama nyaris
seluruhnya fungsi dari seberapa jauh harga berlari masuk, bukan fungsi dari apa
yang ada di titik itu.

Perpindahan bersih 40 bar sesudahnya: **nol di semua kelompok**, p>0,3 di
mana-mana. Tidak ada ramalan arah pada horizon itu.

### Bisakah jalan di depan meramalkan arah?

Pertanyaan yang berbeda dari semua di atas, dan pertanyaan yang dibutuhkan
sebuah panah di chart. `profit_zone_rr` lolos setiap uji di halaman ini, tetapi
setiap uji itu menanyakan apakah zonanya **bertahan**, yaitu pertanyaan bracket
yang sebagian besar ditentukan oleh apakah stop tersentuh. Itu bukan pertanyaan
ke mana harga bergerak.

Diukur pada zona digambar saja, bertanda sehingga positif berarti harga pergi ke
arah zonanya:

| Jalan di depan | n | Perpindahan (ATR) | Pembalikan | Berakhir positif |
|---|---|---|---|---|
| 0,00 sampai 0,61x | 677 | -0,088 | -0,0153 | 51,8% |
| 0,61 sampai 1,33x | 675 | -0,160 | -0,0068 | 47,6% |
| 1,33 sampai 2,86x | 679 | -0,128 | +0,0188 | 48,5% |
| 2,86 sampai 30,0x | 680 | -0,035 | +0,0420 | 47,9% |

Jalan terpanjang dikurangi terpendek: **+0,053 ATR, p=0,88**. Kolom terakhirnya
berkisar 47,6% sampai 51,8%, yaitu lemparan koin di setiap pita.

**Faktor ini meramalkan KETAHANAN, bukan ARAH.** Tidak ada panah yang bisa
digambar darinya.

Satu hal yang menarik dan sengaja tidak dikejar: pembalikan awalnya naik monoton
mengikuti panjang jalan (-0,015 sampai +0,042) sementara perpindahan bersihnya
tidak. Zona berjalan panjang memantul lebih keras di awal lalu berakhir di tempat
yang sama. Mengubah itu menjadi klaim membutuhkan uji tersendiri dengan horizon
yang ditetapkan sebelumnya, bukan dibaca dari tabel yang sudah dilihat.

14 uji dijalankan di berkas itu; ambang Bonferroni 0,0036. Angka p=0,029 untuk
pembalikan zona digambar **tidak lolos** koreksi itu; p=0,0001 untuk kelompok
ditolak lolos.

## Perburuan arah: empat hipotesis, didaftarkan lebih dulu

Diminta membuat panah arah di chart. Empat hipotesis didaftarkan sebelum diukur,
dengan aturan berhenti yang juga ditetapkan di depan: kalau semuanya gagal,
kesimpulannya adalah gambar ini tidak meramalkan arah, bukan "coba hipotesis
kelima sampai ada yang lolos".

### H3, pembalikan awal pada horizon 5 dan 10 bar

Horizonnya ditetapkan **sebelum melihat hasilnya**, karena memilih horizon
setelah melihat mana yang menyanjung adalah cara menyelundupkan parameter bebas
sebagai temuan. Zona digambar saja, bertanda:

| Jalan di depan | n | move@5 | move@10 | move@40 |
|---|---|---|---|---|
| 0,00 sampai 0,61x | 677 | +0,061 | +0,093 | -0,088 |
| 0,61 sampai 1,33x | 675 | +0,015 | +0,115 | -0,160 |
| 1,33 sampai 2,86x | 679 | -0,029 | +0,014 | -0,128 |
| 2,86 sampai 30,0x | 680 | +0,180 | +0,081 | -0,035 |

Tidak monoton pada horizon mana pun. Angka +0,180 di pita teratas berdiri
sendiri dan tidak didukung pada horizon 10. **Gagal.**

### H2, kesejajaran HTF sebagai variabel arah

Nesting sudah diukur terhadap bertahan-atau-jebol dan hasilnya nol. Terhadap
arah:

| | n | move@5 | move@10 | move@40 |
|---|---|---|---|---|
| Bersarang | 1511 | +0,036 | +0,043 | +0,001 |
| Berdiri sendiri | 1200 | +0,083 | +0,117 | -0,233 |

p=0,33, dan tandanya justru terbalik pada horizon pendek. **Gagal.**

> [!NOTE]
> Penelusuran sumber menemukan sesuatu yang layak dicatat: **tidak ada satu pun
> sumber yang mengklaim zona bersarang meramalkan arah.** Yang diklaim adalah
> keandalan, dan itu sudah dibantah pada 2707 zona. Doktrin ICT dan SMC menaruh
> bias arah pada **struktur** timeframe tinggi (BOS, CHoCH), bukan pada
> bersarangnya zona. Jadi H2 menguji hipotesis yang sebenarnya tidak pernah
> diajukan siapa pun.

### H1, peluruhan menurut jumlah sentuhan

Celah terbesar yang terdokumentasi di sini, dan hasilnya paling berliku.

**Terlihat besar sekali.** Dengan definisi bracket biasa, dipasangkan pada zona
yang sama: sentuhan 1 ke sentuhan 2 turun 27,1 poin persen, ke sentuhan 5 turun
42,2 poin persen, semuanya p<0,0001. Hazard naik 28,7% ke 44,9%.

**Tautologi pertama, dibuang.** `resolve` menggagalkan sebuah sentuhan ketika ada
bar menutup melewati **distal**, dan distal itu juga yang mengakhiri zonanya.
Jadi sentuhan terakhir sebelum zona mati dijamin tercatat gagal, dan "sentuhan
belakangan lebih sering gagal" sebagian hanya mengulang "sentuhan terdekat ke
kematian adalah yang mati". Diukur ulang dengan hasil yang **tidak pernah
menyebut distal** - hanya apakah harga menempuh `reward` ATR menjauh dari
proksimal dalam `horizon` bar, tanpa stop:

| Sentuhan | Berhasil | Hazard |
|---|---|---|
| 1 | 88,2% | 11,8% |
| 2 | 79,0% | 21,0% |
| 3 | 75,5% | 24,5% |
| 4 | 74,2% | 25,8% |

Bertahan. Dan arah seleksinya justru menguntungkan: zona lemah mati lebih dulu,
jadi penyintas di sentuhan 3 seharusnya **lebih kuat**, yang akan menurunkan
hazard. Hazard tetap naik, melawan seleksi.

**Konfon kedua, dan ini yang mematikannya.** Literatur akademik mengukur
peluruhan level dalam **waktu**, bukan dalam sentuhan. Sentuhan kelima terjadi
lebih lama setelah zona lahir, jadi keduanya bergerak bersama. Dipisah ke dalam
pita umur yang sama, reward 2,0 ATR:

| Umur saat sentuhan | Sentuhan 1 | Sentuhan 2 | Sentuhan 3 |
|---|---|---|---|
| 1 sampai 10 bar | 93,6% | 86,6% | 82,7% |
| 10 sampai 59 bar | 75,8% | 76,5% | 73,5% |
| 59 bar ke atas | **77,2%** | **77,2%** | **77,1%** |

Di pita tertua, nomor sentuhan **tidak mengubah apa pun sama sekali**. Yang
tersisa hanyalah pita termuda, dan di sana sentuhan 3 cuma 104 peristiwa.

Bandingkan ke bawah kolom pertama: 93,6% ke 77,2% **pada sentuhan yang sama**.
Itu 16 poin persen dari umur saja.

**Jadi peluruhannya ada di WAKTU, bukan di SENTUHAN.** Dan itu persis yang
dikatakan literatur peer-reviewed, sekaligus kebalikan dari doktrin ritel.

> [!IMPORTANT]
> Dua studi yang benar-benar menghitung sentuhan sebelumnya menemukan tanda yang
> **berlawanan** dengan doktrin: Garzarelli dkk. (Scientific Reports, 2014) dan
> Chung dan Bellotti (arXiv 2101.07410, 2021) sama-sama menemukan peluang mantul
> **naik** monoton mengikuti jumlah mantulan sebelumnya, dengan kontrol deret
> teracak datar di 0,5. Keduanya mengukur peluruhan terhadap **waktu**, bukan
> terhadap sentuhan.
>
> Sementara doktrinnya sendiri lemah di titik ini. Paten OTA, kodifikasi
> algoritmik penuh metode ini, **tidak memuat konsep kesegaran sama sekali**.
> Panduan pengguna OTA hanya punya satu kalimat tanpa angka: "Fresh levels are
> preferred since they offer greater probability for profit." Angka "dua sampai
> tiga sentuhan" yang beredar tidak punya sumber primer, dan sebagian
> penyebarannya adalah **nilai bawaan parameter indikator** yang lama-lama
> dikira aturan.

**Putusan: tidak dikonfirmasi.** Efek mentahnya besar dan bertahan terhadap satu
konfon, lalu runtuh pada konfon kedua. Dilaporkan, tidak dikirim.

### H4, dua detektor baru lewat rig yang sama

Fair value gap dan order block, dibangun lalu **langsung dimasukkan ke mesin yang
sudah membunuh empat temuan sebelumnya**. Menambah detektor itu mudah dan tidak
membuktikan apa pun; satu-satunya cara jujur adalah menguji keduanya dengan
standar yang sama, bukan yang lebih longgar.

`tools/detectors.py`, kontrol placebo, dua bracket:

| Reward | Detektor | n | Bertahan | Placebo | Selisih |
|---|---|---|---|---|---|
| 1,0 ATR | supply_demand | 10198 | 70,1% | 50,8% | +19,3 pp |
| | fvg | 12745 | 67,0% | 47,6% | +19,5 pp |
| | order_block | 16194 | 72,1% | 51,3% | +20,8 pp |
| 2,0 ATR | supply_demand | 10239 | 48,4% | 35,5% | +12,9 pp |
| | fvg | 12741 | 42,6% | 33,7% | +8,9 pp |
| | order_block | 16229 | 49,1% | 35,8% | +13,3 pp |
| 2,0 setara-R | supply_demand | 10075 | 43,8% | 33,0% | +10,8 pp |
| | fvg | 12710 | 71,0% | 46,1% | **+24,9 pp** |
| | order_block | 16002 | 53,8% | 39,1% | +14,7 pp |

> [!IMPORTANT]
> Angka `order_block` dihitung ulang pada 2026-08-16 karena **detektornya salah
> selama ini**. Definisinya berbunyi "lilin berlawanan **terakhir** sebelum
> gerakan impulsif", tetapi kodenya menandai *setiap* lilin berlawanan yang
> jendela majunya lolos ambang. Tiga lilin turun beruntun sebelum satu reli
> menghasilkan tiga order block bertumpuk, semuanya berbagi impuls yang sama.
> Docstring-nya menulis "terakhir", kodenya melakukan "mana pun".
>
> Akibatnya bukan kosmetik: n-nya menggelembung ke 21.565 lawan 12.745 FVG di
> bar yang sama, dan kelebihannya adalah observasi yang sama dihitung berkali
> kali, yang mengembungkan n sekaligus mengorelasikan hasil. Setelah kata
> "terakhir" ditegakkan (lilin berikutnya wajib menutup ke arah sebaliknya,
> karena lilin itulah awal impulsnya), 6.915 kandidat ditolak dan n turun ke
> 16.194.
>
> **Kesimpulannya tidak berubah.** Ketiganya tetap mengalahkan placebo di
> ketiga geometri dengan p<0,0001. Memperbaiki penghitungan gandanya tidak
> menjatuhkan temuan lokasinya, dan itu justru menguatkannya.

Ketiganya mengalahkan placebo di **ketiga geometri**, semuanya p<0,0001, dengan n
antara 10.000 dan 16.200. Jadi ketiganya menandai tempat yang berperilaku
berbeda dari kotak sembarangan di harga sembarangan.

> [!WARNING]
> Ini **standar yang lebih rendah** daripada yang sudah dilewati supply and
> demand, dan bedanya harus dinyatakan. Mengalahkan placebo berarti mengalahkan
> level sembarangan. Kontrol yang berat - formasi asli yang ditolak gerbang -
> hanya ada untuk supply and demand, karena hanya ia yang punya gerbang. FVG dan
> order block belum punya pembanding sekelas itu, dan belum lewat walk-forward.
>
> Dan tidak satu pun dari ini menyentuh **arah**. Itu diukur terpisah, dan
> jawabannya tetap tidak.

### Sumber kedua detektor itu lemah, dan itu harus dinyatakan

Ditelusuri 2026-08-15. **Sumber primer untuk keduanya adalah kanal YouTube.**
Tidak ada buku, tidak ada makalah, tidak ada kanon. Setiap definisi tertulis yang
beredar adalah kodifikasi pihak ketiga atas sebuah video. Karena itu penyimpangan
implementasi didaftar, bukan diperdebatkan, dan dua di antaranya diselesaikan
dengan pengukuran:

| Pilihan | Status |
|---|---|
| Geometri FVG wick ke wick | **Tidak menyimpang.** Konsensus, dan persis yang diuji dua studi terukur. Versi badan-ke-badan adalah **pola bernama lain** (volume imbalance), bukan varian |
| Tanpa uji arah candle tengah | Sebagian kodifikasi menuntutnya. **Diukur pada 16.693 gap: uji itu hanya menolak 12, yaitu 0,1%.** Penyimpangannya nyata dan dapat diabaikan, dan sekarang berupa angka bukan pendapat |
| `min_gap_atr` 0,1 | **Milik kami.** Tidak ada sumber primer yang punya minimum; bawaan indikator berkisar 0 sampai 0,25 ATR. Disapu, hasilnya di bawah. Hasil di sini tetap tidak sebanding dengan statistik FVG terbitan yang tidak menyaring apa pun |
| Level 50% (consequent encroachment) | **Sudah ada, dengan nama lain.** `penetration_pct >= 0.5` persis berarti harga menyentuh titik tengah, dan ambang mitigasi dikirim di 0,5. Kotak berstatus `mitigated` menurut definisi sudah mencapainya |
| Kotak order block = seluruh rentang candle | Konvensi paling umum, dan **paling lebar** dari tiga yang ada. Itu menaikkan tingkat sentuhan secara mekanis dibanding detektor badan-saja, jadi perbandingan lintas studi tidak sah |
| Tanpa syarat break of structure | **Penyimpangan terbesar**, dan aturannya diperdebatkan. Yang patut diketahui: angka yang biasa dipakai membenarkan syarat itu (52% lawan 65-68% pada 2400 setup) **tidak bisa dilacak** - halaman yang dirujuk sama sekali tidak memuat statistik. Kedua kubu sama-sama tanpa bukti |
| Impuls 1,5 ATR dalam 5 bar | **Sepenuhnya milik kami.** Tidak ada kelipatan ATR terbitan untuk "impulsif" |
| "Warna berlawanan" dibaca `close < open` | Sebagian kodifikasi membacanya `close < close[1]`, yang memilih candle berbeda pada inside dan outside bar. Tidak ada yang menyelesaikannya |

Dua studi yang mengungkap metodenya patut dicatat karena bentuk temuannya **sama
dengan yang terus kami temukan sendiri**: satu menguji reaksi FVG terhadap
placebo acak pada empat futures selama tujuh tahun dan menemukan reaksinya nyata
(unggul di 34 dari 36 sel, sekitar 5 poin) tetapi keunggulan dagangnya habis oleh
biaya di 17 dari 18 konfigurasi. Satu lagi menjalankan 54 variasi aturan SMC pada
2,55 juta bar EURUSD dan menemukan **tidak satu pun untung** setelah setengah pip.

### Ambang yang kami karang, disapu

Dua dari tiga ambang di `ImbalanceParams` sama sekali tidak punya sumber. Menyebut
keduanya "parameter yang disapu" di dokumentasi tanpa pernah menyapunya adalah
kelas klaim yang sama dengan yang proyek ini ada untuk menangkap, jadi ini
sapuannya. `python -m tools.detectors --sweep`.

| `min_gap_atr` | n | Bertahan | Placebo | Selisih |
|---|---|---|---|---|
| 0,00 (mati) | 15235 | 75,6% | 46,4% | **+29,1 pp** |
| 0,05 | 14012 | 73,5% | 46,1% | +27,4 pp |
| **0,10 (dikirim)** | 12710 | 71,0% | 45,8% | +25,2 pp |
| 0,25 | 9401 | 63,5% | 43,6% | +19,8 pp |
| 0,50 | 5522 | 55,5% | 40,3% | +15,3 pp |
| 1,00 | 2166 | 49,1% | 32,5% | +16,6 pp |

| Impuls order block | n | Bertahan | Placebo | Selisih |
|---|---|---|---|---|
| 0,5 ATR / 5 bar | 46868 | 46,7% | 38,4% | +8,3 pp |
| 1,0 ATR / 5 bar | 33163 | 50,7% | 38,4% | +12,3 pp |
| **1,5 ATR / 5 bar (dikirim)** | 21337 | 54,2% | 38,7% | +15,5 pp |
| 2,5 ATR / 5 bar | 8758 | 60,0% | 41,1% | +18,9 pp |
| 1,5 ATR / 3 bar | 14065 | 53,5% | 37,4% | +16,1 pp |
| 1,5 ATR / 10 bar | 31093 | 55,5% | 40,1% | +15,4 pp |

Tiga bacaan, dan yang pertama yang paling penting:

1. **Tidak ada satu pun ambang yang membalik tanda.** Selisihnya positif di
   setiap nilai yang diuji. Jadi efeknya bukan milik knob-nya. Itulah yang
   sebenarnya diuji sapuan ini; sisanya detail.

2. **`min_gap_atr` justru MEMBAYAR, bukan membeli.** Selisih terbesar ada di
   0,00, yaitu tanpa saringan sama sekali (+29,1 pp), dan turun terus seiring
   ambangnya dinaikkan. Ambang yang dikirim membeli **keterbacaan chart**, bukan
   kinerja, dan itu harus dikatakan begitu alih-alih dibiarkan terlihat seperti
   penyaring mutu.

3. **`displacement_bars` nyaris tidak berpengaruh** (+16,1 / +15,5 / +15,4 untuk
   3, 5, dan 10 bar). Parameter yang tidak menanggung beban, dan itu kabar baik:
   satu angka karangan yang ternyata tidak menentukan apa-apa.

`displacement_atr` berperilaku seperti `departure_min_atr` pada detektor lama:
makin ketat makin besar selisihnya, dengan harga jumlah kotak yang jatuh dari
46.868 ke 8.758. Pertukaran yang sama, dan dibiarkan pada nilai yang dikirim
karena tidak ada bukti out-of-sample yang membenarkan memindahkannya.

Satu kontrol ditulis lalu **dibuang**, dan alasannya layak dicatat. Kontrol
"waktu acak" memulai bracket di harga bar acak itu; kalau harga sudah melewati
target, bracket-nya selesai menang di bar pertama. Ia mencetak 50 sampai 52
persen untuk setiap detektor di setiap geometri, yang adalah tanda tangan
lemparan koin, bukan kontrol. Ia bekerja di `tools/reaction.py` hanya karena di
sana hasilnya adalah perpindahan dari harga sentuhan, yang tidak punya makna
tanpa sentuhan.

### Kedua detektor baru lewat walk-forward

Sebelumnya keduanya hanya punya kontrol placebo, dan itu dinyatakan sebagai bar
rendah. Sekarang keduanya lewat mesin yang sama dengan gerbang departure, dengan
populasi dikumpulkan pada gerbang **nol** supaya kohort yang ditolak benar-benar
ada.

| Detektor | Reward | Part A, ambang dikirim | Part B, ambang dipilih masa lalu |
|---|---|---|---|
| fvg | 1,0 ATR | 8 dari 8, p=0,0078 | 8 dari 8, p=0,0078 |
| fvg | 2,0 ATR | 8 dari 8, p=0,0078 | 8 dari 8, p=0,0078 |
| order_block | 1,0 ATR | 8 dari 8, p=0,0078 | 8 dari 8, p=0,0078 |
| order_block | 2,0 ATR | 8 dari 8, p=0,0078 | 8 dari 8, p=0,0078 |

> [!WARNING]
> **Koreksi terhadap harness ini sendiri, dan ia berlaku surut ke seluruh
> bagian B di halaman ini.** Ambang yang dipilih masa lalu untuk `order_block`
> adalah **4,0 di kedelapan potongan, yaitu nilai tertinggi di gridnya**. Untuk
> `fvg` ia memilih 2,0, juga mendekati ujung. Itu bukan berarti ambangnya
> seharusnya 4,0.
>
> Kriteria pemilihannya adalah "maksimalkan selisih", dan kriteria itu **tidak
> punya biaya untuk membuang kotak**. Pada besaran mana pun yang monoton -
> dan sapuan parameter menunjukkan `displacement_atr` memang monoton, +8,3
> sampai +18,9 - pengoptimal akan selalu hanyut ke ujung grid. Gerbang
> departure melakukan hal yang sama pada reward 2,0 dan memilih 4,0.
>
> Jadi bagian B menjawab "apakah ambang bisa ditemukan dari masa lalu", bukan
> "berapa ambangnya". Yang bermakna adalah **bagian A**: selisihnya bertahan di
> potongan yang belum pernah dilihat, pada ambang yang benar-benar dikirim.

### H5, penerusan searah, dan koreksi atas premis saya sendiri

Semua uji arah sebelumnya memperlakukan kotak sebagai objek **pembalikan**:
harga tiba, apakah ia berbalik. FVG adalah objek **penerusan** - ia lahir dari
perpindahan berarah - dan pertanyaan itu belum pernah diajukan.

**Hipotesis ini diajukan atas premis yang ternyata salah, dan koreksinya dicatat
di sini alih-alih dibuang diam-diam.** Saya menyatakan literatur gap
peer-reviewed mendukung penerusan. Diperiksa dengan benar, tidak, bukan dalam
bentuk yang dibutuhkan:

- Plastun dkk. (NAJEF 2020) dan Caporale & Plastun (IAJ 2017) meneliti gap
  **semalam** dari penutupan ke pembukaan, pada bar **harian**. **96% gap FX
  mereka jatuh di hari Senin** - objeknya sebagian besar artefak akhir pekan.
  Milik kita ketidakseimbangan tiga bar intraday tempat perdagangan **terjadi di
  setiap harga**. Tidak ada informasi tertahan yang perlu diserap, jadi
  mekanismenya tidak berpindah.
- Efek penerusan mereka **satu sesi saja**, secara eksplisit mengecualikan
  lompatan gap-nya sendiri, nol pada 1 sampai 3 hari, dan meluruh setelah 1990-an.
- Hasil FX Caporale & Plastun justru **peluruhan hari yang sama**, bukan
  penerusan.
- Yang bertahan hanya satu: keduanya membantah bahwa gap cenderung tertutup.

Dan yang melawannya:

- Struktur suku bunga autokorelasi return intraday **negatif** di seluruh rentang
  5 sampai 60 menit, dengan minimum globalnya dekat 15 menit. Penerusan hanya
  muncul di horizon di bawah satu menit.
- Analog terukur terdekat - "bar ekspansi" pada 72.604 bar lima menit - kembali
  dengan tanda **berlawanan secara signifikan**, t = -10,96, dengan diagnosis
  yang persis konfon di sini: ledakannya habis di dalam bar yang membuatnya.
- Penerusan angka bulat milik Osler adalah satu-satunya mekanisme bersih di
  literatur. Nilainya **0,7 basis poin**, mati dalam dua jam, dan bekerja karena
  angka bulat adalah titik fokus tanpa koordinasi. Tepi kotak hasil detektor
  bukan: ia bergantung pada interval bar, ambang, dan wick-lawan-badan, jadi dua
  trader menggambar kotak berbeda dan gugusan order-nya tidak pernah terbentuk.

Jadi prior-nya **rendah**, dan itu menaikkan bar bukan menurunkannya. Ditulis
sebelum angkanya ada.

**Konfon yang punya nama.** Menyeleksi peristiwa berdasarkan return sebelum
peristiwa memproduksi return abnormal dari ketiadaan (Ahern, *Sample Selection
and Event Study Estimation*), dan biasnya **paling besar justru ketika efek
sebenarnya kecil** - yaitu rezim di sini. Dua pemisahan dipakai: **dormansi**,
hanya sentuhan yang terjadi minimal 10 bar setelah kotak lahir, sehingga
perpindahannya seluruhnya di luar jendela ukur; dan **bucket momentum sebelumnya**.

Horizon utama **12 bar, ditetapkan sebelum melihat apa pun**.

| Detektor | n sentuhan dorman | Rerata di 12 bar | t | Berakhir positif |
|---|---|---|---|---|
| fvg | 2727 | +0,0755 ATR | 1,01 | 52,7% |
| order_block | 6761 | +0,0058 ATR | 0,13 | 52,6% |
| supply_demand | 1981 | +0,0218 ATR | 0,27 | 51,5% |

Kriteria konfirmasi menuntut **t >= 3,0** setelah koreksi atas seluruh keluarga
uji yang sudah dijalankan pada data ini. Tidak satu pun mendekati.

Pada FVG, t naik ke 2,30 di horizon 48 bar - di luar horizon utama, dan bucket
momentum sebelumnya menunjukkan efeknya terbesar justru di bucket teratas
(+0,1723 lawan +0,0161 di terbawah). Itu momentum yang ditemukan ulang dengan
langkah tambahan, bukan kotaknya.

> [!NOTE]
> Subsampel pembeda yang paling tajam **tidak ada di konstruksi ini**. Sentuhan
> pertama menurut definisi terjadi ketika harga tiba dari luar kotak, jadi
> seluruh 11.469 peristiwa mendekat dari sisi dekat dan **nol** menembus kotak.
> Uji yang akan memisahkan penerusan dari pembalikan membutuhkan sentuhan
> pasca-inversi, dan itu detektor yang berbeda lagi.

**Putusan: nol.** Empat hipotesis arah didaftarkan, empat nol.

### H6, struktur pasar: satu-satunya objek yang doktrinnya klaim membawa arah

Semua yang diuji sebelum ini adalah objek **lokasi**. Zona, gap, dan order block
menjawab *di mana*, dan keduanya mengalahkan placebo 10 sampai 25 poin persen.
Tidak satu pun membawa arah. Doktrinnya sendiri mengatakan sebabnya: **ICT dan
SMC menaruh bias arah pada STRUKTUR pasar - BOS dan CHoCH - dan memakai zona
hanya untuk memperhalus titik masuk.** Struktur memutuskan ke mana; zona
memutuskan di mana.

Jadi selama ini keluarga objek yang diuji untuk pertanyaan arah memang keliru.

`app/detect/structure.py`, dan satu aturan yang menentukan seluruhnya: **swing
di bar ke-i baru bisa diketahui di bar ke-i+right.** Detektor yang bereaksi pada
swing begitu ia terbentuk sedang membaca bar yang belum terjadi, dan ia akan
menghasilkan keunggulan arah yang indah dan seluruhnya terbuat dari masa depan.
Setiap swing membawa `confirmed_at`, setiap break hanya diuji terhadap swing yang
sudah terkonfirmasi, dan itu **diasersikan di pengujian**, bukan dipercaya.

> [!IMPORTANT]
> **Koreksi atas laporan pertama saya sendiri.** Saya melaporkan BOS dan CHoCH
> sebagai dua hipotesis. Keduanya **satu predikat yang sama** - penutupan
> menembus swing terkonfirmasi - dan nama yang didapat hanya bergantung ke mana
> bias sudah menunjuk. Mereka rincian, bukan dua uji bebas, dan memperlakukannya
> sebagai dua adalah menghitung ganda.

Tidak ada aturan terbitan yang memberi nilai N untuk swing point. Setiap angka
yang beredar adalah bawaan indikator, termasuk 5 yang di-hardcode satu skrip
populer dan 50 yang dikirim skrip lain sebagai slider. Jadi **N adalah permukaan
data-snooping**, dan menyapunya berarti memilih jawaban. Dua nilai ditetapkan di
depan dan keduanya dilaporkan apa pun katanya.

Estimandnya selisih **setelah break naik dikurangi setelah break turun**, yang
membatalkan drift sampel secara persis.

| N | Kelompok | n | DELTA @12 bar | t |
|---|---|---|---|---|
| 2 | Semua break | 9210 | +0,072 | 0,99 |
| 2 | BOS | 4581 | +0,112 | 1,09 |
| 2 | CHoCH | 4629 | +0,027 | 0,26 |
| 2 | SWEEP | 8725 | +0,043 | 0,63 |
| **25** | **Semua break** | **1100** | **+0,549** | **2,27** |
| 25 | BOS | 556 | +0,608 | 1,59 |
| 25 | CHoCH | 544 | +0,499 | 1,69 |
| 25 | SWEEP | 1053 | +0,428 | 1,89 |
| 25 | **Paruh pertama** | 550 | **+1,021** | **3,07** |
| 25 | **Paruh kedua** | 550 | **+0,076** | **0,22** |

Pada struktur besar efeknya **delapan kali lebih besar** daripada di struktur
kecil, dan t naik ke 2,27. Itu hasil terkuat yang pernah dihasilkan proyek ini
untuk pertanyaan arah.

**Dan paruhnya membunuhnya.** Paruh pertama +1,02 dengan t=3,07; paruh kedua
+0,08 dengan t=0,22. Tandanya memang sama, jadi kriteria "tanda sama di kedua
paruh" lolos secara harfiah - tetapi besarannya runtuh **tiga belas kali lipat**.
Itu tanda tangan window fit, bukan efek.

**Putusan: tidak dikonfirmasi.** Bar utamanya t >= 3,0 pada seluruh sampel, dan
2,27 tidak sampai. Memilih N=25 karena ia terlihat lebih baik justru snooping
yang aturan dua-nilai itu ada untuk mencegah.

### Yang membuat nol ini berbeda: literatur memperkirakannya

Empat nol sebelumnya berdiri sendiri. Yang ini punya rekaman peer-reviewed yang
memperkirakannya, dan itu mengubah statusnya dari "kami tidak menemukan apa-apa"
menjadi "kami menemukan apa yang sudah diketahui".

- **Huddart, Lang & Yetman (Management Science, 2009)** meneliti perilaku harga
  di sekitar tertinggi dan terendah 52 minggu. Menembus batas **bawah**
  menghasilkan lonjakan volume yang sama dan **return berikutnya yang sama
  positifnya** dengan menembus batas atas. **Peristiwanya punya besaran, tetapi
  tidak punya tanda.** Itu persis hasil kami pada zona, gap, order block, dan
  sekarang struktur - sudah ditegakkan pada sampel ekuitas besar.
- **Brock, Lakonishok & LeBaron (JF, 1992)** adalah analog akademik BOS: beli
  saat harga menembus maksimum lokal 50, 150, atau 200 hari. Hasil in-sample
  kuat pada DJI 1897-1986. Lalu **Sullivan, Timmermann & White (JF, 1999)**
  menjalankannya out-of-sample 1987-1996: p=0,154, dan penulisnya menulis
  "hasilnya sepenuhnya terbalik". Lalu **Bajgrowicz & Scaillet (JFE, 2012)**
  pada 1962-2011: **nol aturan yang unggul, pada biaya transaksi nol.**
- Mekanisme jujur satu-satunya di level seperti ini, gugusan stop milik Osler,
  bernilai sekitar **0,0014% pada 30 menit** - kira-kira 0,14 basis poin, dua
  orde besaran di bawah spread ritel.

Jadi struktur yang tidak membawa arah bukan kejutan. Ia hasil yang paling
mapan di seluruh literatur perdagangan teknikal, dan kami menemukannya ulang
dari nol pada instrumen dan dekade yang berbeda.

> [!NOTE]
> **Sweep membawa kira-kira sebanyak break** (+0,428 lawan +0,549 di N=25).
> Kalau menembus level dan gagal menembus level memberi hasil yang serupa,
> yang diukur adalah peristiwanya, bukan arahnya. Itu pengamatan Huddart lagi,
> dari arah yang berbeda.

**Lima hipotesis arah, lima kali tidak lolos.**

### H7, zona searah bias struktur lawan yang melawan

Ini klaim doktrin yang **sebenarnya**, dan satu-satunya yang belum pernah diukur
siapa pun. Bukan "zona meramalkan arah" - enam hipotesis sudah gagal di situ.
Melainkan yang dikatakan hampir setiap sumber ICT dan SMC: **timeframe tinggi
menetapkan BIAS, timeframe rendah menetapkan ENTRI.** Zona demand yang disentuh
saat struktur bullish seharusnya objek yang berbeda dari zona yang sama saat
struktur bearish.

Estimandnya **di dalam sisi**, bukan sejajar-lawan-melawan. Sebabnya: sampel ini
lebih sering bullish daripada bearish, jadi kelompok "sejajar" memuat lebih
banyak zona demand daripada kelompok "melawan", dan di sampel yang menanjak
selisih itu sendiri sudah menghasilkan efek. Dengan menahan sisi zona tetap dan
hanya mengubah biasnya, drift-nya batal.

**Dan ia lolos ketiga kriteria yang ditetapkan di depan.** FVG pada N=25:

| Sisi | Sejajar | Melawan | Selisih | t |
|---|---|---|---|---|
| demand | +0,224 | -0,181 | **+0,405** | **4,63** |
| supply | +0,181 | -0,086 | **+0,266** | **3,06** |
| bertahan | 44,4% | 40,5% | **+4,0 pp** | z=4,49 |

Kedua sisi positif. Kedua paruh positif. Besarannya tidak runtuh - ia justru
tumbuh di paruh kedua. Setelah enam nol, ini hasil pertama yang lolos.

**Lalu satu kontrol membatalkannya.**

"Zona demand saat struktur bullish" juga berarti "koreksi di dalam tren naik",
dan membeli itu adalah **momentum deret waktu** - efek nyata, mapan, dan
peer-reviewed yang tidak ada hubungannya dengan kotak mana pun. Jadi kontrasnya
dihitung ulang pada **bar acak** yang hanya membawa bias, dengan sisi palsu yang
diundi terpisah:

| | Sejajar | Melawan | Selisih | t |
|---|---|---|---|---|
| demand, bar acak | +0,143 | -0,129 | **+0,271** | 4,36 |
| supply, bar acak | +0,056 | -0,129 | **+0,184** | 3,11 |

Bar acak tanpa kotak apa pun sudah menghasilkan sebagian besarnya. Selisih dari
selisih - apa yang benar-benar **ditambahkan zonanya** di atas biasnya:

| Detektor | Sisi | Zona | Kontrol | Zona menambah | t |
|---|---|---|---|---|---|
| fvg | demand | +0,405 | +0,271 | +0,134 | 1,25 |
| fvg | supply | +0,266 | +0,184 | +0,082 | 0,78 |
| supply_demand | demand | +0,182 | +0,271 | **-0,089** | -0,80 |
| supply_demand | supply | +0,134 | +0,184 | **-0,050** | -0,47 |
| order_block | demand | +0,219 | +0,271 | **-0,052** | -0,59 |
| order_block | supply | -0,004 | +0,184 | **-0,188** | -2,14 |

**Zonanya tidak menambah apa pun yang terukur, dan pada dua dari tiga detektor
ia menambah sedikit negatif.** Yang diukur H7 adalah biasnya, dan biasnya adalah
momentum.

Pada swing kecil (N=2) tidak ada satu pun sumbangan zona yang positif dan
signifikan, dan supply/demand justru **-0,246 dengan t = -2,20**. Dari dua belas
pembacaan selisih-dari-selisih, nol positif signifikan dan dua negatif
signifikan.

Ada satu temuan lagi di N=2 yang harus dilaporkan justru karena arahnya
memalukan bagi doktrinnya: zona yang searah bias **lebih jarang** bertahan,
46,4% lawan 50,8% (z = -4,42) untuk supply/demand, 46,9% lawan 50,3% (z = -4,98)
untuk order block. Kebalikan dari yang diajarkan.

> [!NOTE]
> t pada kontrol itu sendiri **terlalu optimistis**: 4000 bar acak per deret pada
> 20.000 bar berarti jendela-jendelanya bertumpang tindih besar-besaran. Itu
> justru memperkuat nolnya - selisih-dari-selisih yang tidak signifikan meski
> galat bakunya diremehkan adalah nol yang kokoh.

**Putusan: tidak dikonfirmasi.** Tujuh hipotesis arah, tujuh kali sumbangan
gambarnya nol.

Satu hal positif yang jujur untuk dikatakan: **biasnya sendiri memisahkan
return** (+0,271 dan +0,184, keduanya t di atas 3). Itu bukan temuan baru - itu
momentum deret waktu, yang sudah lama mapan - tetapi ia satu-satunya hal di
proyek ini yang pernah memisahkan arah sama sekali. Dan ia sama sekali tidak
membutuhkan gambar apa pun.

### H8, sentuhan pasca-inversi (breaker block dan inversion FVG)

Tujuh hipotesis arah gagal, dan ketujuhnya menanyakan **pertanyaan berbeda pada
sampel yang sama**: variabel pengkondisinya diganti, populasinya tetap. H8 yang
pertama mengganti **populasinya**, dan itulah alasan ia layak dijalankan setelah
tujuh nol.

Dokumen ini sendiri sudah menyebut celahnya sebelum tool-nya ada: seluruh 11.469
sentuhan pertama mendekat dari sisi dekat dan **nol** menembus kotak, jadi
subsampel yang bisa memisahkan penerusan dari pembalikan memang belum pernah ada
di sampel mana pun di sini. Ia harus dibangun.

Kotak yang sama dibaca dari sisi seberang: zona demand yang ditutup ke bawah kini
jadi resistance, tepi yang ditemui lebih dulu adalah bekas **bawah**-nya, dan
tepi pelindungnya bekas **atas**-nya. Tidak ada geometri baru yang dikarang;
`replay_lifecycle` dipanggil ulang dengan `is_demand` dibalik. `break_index` yang
selama ini dihitung lalu dibuang akhirnya terpakai.

| Kohort | Kini demand | Kini supply | DELTA | t | n |
|---|---|---|---|---|---|
| **Kontrol: gerak 20 bar saja, tanpa kotak** | +0,082 | -0,082 | **+0,164** | **3,83** | 19953 |
| supply_demand | +0,021 | +0,036 | -0,015 | -0,25 | 9762 |
| fvg | -0,022 | -0,020 | -0,002 | -0,03 | 11670 |
| order_block | -0,081 | +0,029 | **-0,110** | **-2,25** | 16626 |

Dan yang menentukan, apa yang **ditambahkan kotaknya** di atas kontrol:

| Detektor | Zona menambah | t |
|---|---|---|
| supply_demand | **-0,179** | **-2,40** |
| fvg | **-0,165** | **-2,23** |
| order_block | **-0,274** | **-4,22** |

**Ketiganya signifikan negatif.** Mengetahui kotaknya terbalik membuat tebakan
arahnya lebih buruk daripada sekadar mengetahui ke mana harga baru saja bergerak.
Order block bahkan negatif berdiri sendiri, yaitu **berlawanan dengan doktrin
breaker block**, bukan sekadar nol.

n-nya besar dan paruhnya tidak menyelamatkan apa pun. Ini nol yang bertenaga,
bukan nol karena kurang sampel.

### H9, konjungsi sweep lalu Market Structure Shift

Ini menutup celah logika saya sendiri. H6 menguji BOS, CHoCH, dan SWEEP sebagai
tiga kohort terpisah, tidak menemukan yang selamat, lalu menyimpulkan struktur
pasar tidak membawa arah. Tetapi yang ICT klaim membawa arah **bukan** salah satu
dari ketiganya sendirian, melainkan **konjungsinya**: likuiditas disapu dulu,
baru harga menutup menembus struktur lawan. Menguji bagian lalu memvonis
keseluruhan bukan inferensi yang sah.

Kontrol utamanya bukan bar acak melainkan **break biasa tanpa sweep di
depannya**, karena itulah yang mengisolasi persis apa yang ditambahkan sweep-nya.

| Konfigurasi | Kohort | DELTA | t | n |
|---|---|---|---|---|
| N=2, jendela 5 | MSS | -0,161 | -0,79 | 1385 |
| | break biasa | +0,119 | 1,22 | 5128 |
| | **sweep menambah** | **-0,280** | **-1,24** | |
| N=2, jendela 20 | MSS | -0,013 | -0,12 | 4576 |
| | break biasa | +0,207 | 1,24 | 1753 |
| | **sweep menambah** | **-0,220** | **-1,11** | |

Paruhnya berbalik tanda di kedua jendela (-0,436 lalu +0,106; -0,034 lalu
+0,017). Tidak ada satu pun t yang mendekati 3,0.

> [!IMPORTANT]
> Pada N=25 konjungsinya **terlalu langka untuk diuji sama sekali**: 7 peristiwa
> di jendela 5 dan 43 di jendela 20. Jadi konstruk yang paling ditekankan ICT
> praktis tidak terjadi pada skala struktur besar di data ini. Itu temuan
> tersendiri, dan harus dilaporkan sebagai ketidakmampuan mengukur, bukan
> disamarkan jadi nol.

Empat sel dilaporkan dan keempatnya harus dibaca. Memilih yang terbaik setelah
melihat hasilnya adalah cara sebuah nol berubah jadi klaim.

### Sembilan hipotesis arah, sembilan kali nol

Yang tersisa berdiri setelah semuanya justru kontrolnya: **gerak 20 bar terakhir
saja** memisahkan return +0,164 dengan t=3,83, lebih kuat daripada apa pun yang
pernah dihasilkan gambar mana pun di sini. Itu momentum deret waktu. Ia sudah
lama mapan, ia peer-reviewed, dan **ia tidak membutuhkan satu kotak pun.**

Pertanyaan arah dari gambar ditutup di sini. Bukan karena kehabisan ide,
melainkan karena dua konstruk ICT terakhir yang benar-benar membawa klaim arah
sudah diuji dan keduanya gagal, satu di antaranya signifikan ke arah sebaliknya.

### H10, momentum, dan angka yang selama ini menggelembung

Sembilan hipotesis gagal mengeluarkan arah dari gambar. Yang selalu muncul
sebagai gantinya, setiap kali dipakai sebagai **kontrol**, adalah gerak
sebelumnya: bar yang tidak membawa apa pun selain "harga sedang naik" memisahkan
return lebih baik daripada kotak mana pun. Kontrol H8 memberi +0,164 dengan
t=3,83. Itu momentum deret waktu, mapan dan peer-reviewed, dan sama sekali tidak
membutuhkan gambar - jadi ia kandidat paling jujur untuk satu komponen yang
hilang dari Zonelab.

Ia juga kandidat yang paling mungkin artefak, karena setiap angka kontrol itu
diukur dengan cara yang proyek ini kritik di tempat lain: 4000 bar acak dari
20.000, masing-masing dengan jendela maju 48 bar. Jendela-jendela itu bertumpang
tindih besar-besaran, jadi pengamatannya jauh dari independen dan galat bakunya
diremehkan.

`tools/momentum.py` mengambil sampel **tidak bertumpang tindih**: sampel
berurutan berjarak lookback ditambah horizon, sehingga tidak ada bar yang berada
di dua lookback atau dua jendela maju. Itu membuang sebagian besar sampelnya
dengan sengaja. n kecil itu kelihatan; t yang digelembungkan tidak.

| Lookback | DELTA | t | Paruh pertama | Paruh kedua | t versi tumpang tindih |
|---|---|---|---|---|---|
| 20 bar | +0,308 | 2,17 | +0,582 | **+0,032** | **5,46** |
| 60 bar | +0,377 | 2,00 | +0,566 | +0,201 | **13,54** |
| 120 bar | +0,043 | 0,18 | -0,271 | +0,312 | **10,26** |

Tidak satu pun mencapai t=3,0 yang ditetapkan di depan. Ketiganya meluruh antar
paruh, dan yang 20 bar runtuh dari t=3,02 ke t=0,15. Yang 120 bar berbalik tanda.

**Putusan: tidak dikonfirmasi.**

> [!CAUTION]
> Perhatikan kolom terakhirnya. Efeknya hampir sama besar, tetapi t-nya
> menggelembung sampai **hampir tujuh kali lipat** semata karena jendelanya
> bertumpang tindih. Angka-angka itulah yang dilaporkan setiap kontrol
> sebelumnya di proyek ini, termasuk t=3,83 yang membuat momentum tampak seperti
> jawabannya.
>
> Ini **tidak** membatalkan H7. Kontrol yang digelembungkan membuat sebuah nol
> jadi **lebih kuat**, bukan lebih lemah: selisih yang gagal signifikan bahkan
> ketika galat bakunya diremehkan adalah nol yang kokoh. Yang dibatalkan adalah
> membaca kontrol itu sebagai temuan positif, dan itulah yang hampir saya
> lakukan.

Sepuluh hipotesis arah, sepuluh kali nol. Yang tersisa bukan lagi "momentum
bekerja tapi bukan milik kita" - melainkan bahwa pada data ini, dengan
pengukuran yang jujur, **arah tidak terpisahkan sama sekali**.

### H11, konjungsi tiga bagian, dan sumber yang membatalkan pembacaan H9

H9 menguji "sweep lalu break berlawanan" dan menyebutnya Market Structure Shift.
Itu **dua pertiga definisinya**. Bagian ketiga, displacement, tidak pernah masuk,
dan H9 menutup kasus atas konstruk yang belum lengkap.

Transkrip mentorship ICT 2022 diambil sebagai berkas SRT (35 episode, 211.989
kata) dan menolak pembacaan dua bagian itu dengan nama:

> "It's not that it goes above this old, relative equal high, and then goes down
> below that - that's not it, folks, that's not it. You have to see it go below
> that in displacement with energetic move, take out a short term low."
> (Episode 24, 2022-05-06)

Dan displacement-nya dioperasionalkan **bukan sebagai ukuran** melainkan sebagai
ketidakefisienan di dalam kaki itu sendiri:

> "you don't have a trade entry yet, until you determine if it has a fair value
> gap ... if there isn't one there, you don't have a trade."
> (Episode 6, 2022-02-04)

**Tidak ada sumber di tingkat mana pun yang memberi kelipatan ATR.** Jadi
displacement diuji sebagai FVG di dalam kaki break, sebagaimana sumbernya
mendefinisikannya, bukan sebagai ambang karangan.

H9 direproduksi lebih dulu dan cocok bita-per-bita: t = -0,79 (n=1385) dan -0,12
(n=4576), paruh -0,436 / +0,106 dan -0,034 / +0,017, serta kelangkaan 7 dan 43 di
N=25. **Tidak ada satu pun angka terbit yang bergerak.**

H11 memakai pin yang sama persis dengan H9, didaftarkan sebelum diukur: lebar
swing 2 dan 25, jendela 5 dan 20, horizon 1/3/6/12/24/48 dengan **12 sebagai
horizon utama**, dan bar konfirmasi t >= 3,0 **ditambah** tanda sama di kedua
paruh **ditambah** ia harus mengalahkan **keduanya**, break biasa dan sel sweep
tanpa gap.

| Konfigurasi | Kohort | DELTA @12 bar | t | n |
|---|---|---|---|---|
| N=2, jendela 5 | **sweep + gap** | **-0,8272** | **-2,66** | 593 |
| | sweep tanpa gap | +0,3581 | 1,36 | 792 |
| | gap tanpa sweep | +0,2294 | 1,65 | 2801 |
| | break biasa | -0,0099 | -0,07 | 2327 |
| | **displacement menambah** | **-1,1853** | **-2,91** | |
| N=2, jendela 20 | sweep + gap | -0,0297 | -0,24 | 3233 |
| N=25, jendela 5 | sweep + gap | 7 peristiwa, tidak bisa diuji | | |
| N=25, jendela 20 | sweep + gap | 39 peristiwa, tidak bisa diuji | | |
| Kontrol, gerak sebelumnya saja | | **+0,1636** | **3,83** | |

Paruh N=2 jendela 5: -1,0116 lalu -0,6784. Paruh N=2 jendela 20: +0,0622 lalu
-0,1111.

**Putusan: gagal menembus bar di keempat konfigurasi.** Kontrol yang tidak
membawa gambar apa pun tetap mengalahkan setiap sel di tabel itu, seperti di
setiap uji arah sebelumnya, dan seperti sebelumnya t=3,83 itu sendiri
digelembungkan oleh jendela yang bertumpang tindih, jadi ia pembanding bukan
temuan.

> [!WARNING]
> Sel yang menggoda adalah N=2 jendela 5: tandanya konsisten di kedua paruh dan
> displacement-nya menambah -1,19 dengan t=-2,91. **Ia tidak boleh diubah menjadi
> klaim kontrarian.** Pada jendela terpin yang satunya, paruhnya berbalik tanda.
> **Satu dari dua jendela yang dipin bukan hasil**, dan memilih yang lebih menarik
> setelah melihat keduanya persis cara sebuah nol berubah jadi temuan.

#### Sensitivitas pivot: satu kecurigaan yang gugur setelah diukur

Kelangkaan 7 dan 43 di H9 dicurigai artefak definisi kami sendiri: fraktal
simetris di repo ini jauh lebih selektif daripada pivot satu sisi yang dipakai
kodifikasi publik dengan pemasangan terbanyak. Kalau benar, "terlalu langka untuk
diuji" akan jadi pernyataan tentang kode kami, bukan tentang pasar.

Diukur: pada tingkat swing, definisi kami hanya sekitar **20% lebih selektif**
(sekitar 0,8 kali jumlah swing di N=25 maupun N=50), **bukan dua kali**. Faktor
dua itu baru muncul di **konjungsinya**, yang menuntut sweep dan break terjadi
bersamaan sehingga jumlahnya berskala kira-kira sebagai perkalian: 7 lawan 14,
dan 43 lawan 84.

Bahkan setelah digandakan, N=25 jendela 5 tetap tidak terukur. **Jadi kelangkaan
H9 adalah pasarnya, bukan definisi kami**, dan tidak ada yang ditukar: fraktal
simetris dengan `confirmed_at = i + right` justru yang membuat setiap angka
terbit di halaman ini bebas lookahead.

### Setelah biaya dibebankan, pada emas sungguhan

Setiap angka sebelum bagian ini **tanpa gesekan**. Itu wajar selama pertanyaannya
"apakah kotaknya menandai tempat nyata", dan berhenti wajar begitu ada yang
bertanya berapa nilainya. Keunggulan beberapa poin persen persis seukuran yang
dimakan biaya transaksi, jadi keunggulan tanpa biaya bukan hampiran kasar dari
keunggulan berbiaya - tandanya bisa berlawanan.

`tools/costed.py` yang pertama membebankan apa pun, dan itu baru mungkin karena
Dukascopy menerbitkan kedua sisi buku. Spread-nya **diukur per bar**, bukan
diasumsikan: XAUUSD 15m, 1 Juni sampai 14 Agustus 2026, 5000 bar, spread minimum
0,289, rata-rata 0,668, maksimum 4,361.

Aturannya pesimistis di setiap tempat bar-nya ambigu: bar sentuhan ikut dihitung,
kalau satu bar memuat stop **dan** target maka **stop** yang diambil, dan spread
dibebankan di kedua kaki karena stop di bawah posisi long dieksekusi di sisi buku
yang berlawanan dengan entry-nya.

| Kohort (setelah biaya) | n | Menang | Ekspektasi R | t |
|---|---|---|---|---|
| supply_demand, semua | 529 | 62,2% | +0,059 | 1,37 |
| **supply_demand lolos gerbang** | 307 | 72,0% | **+0,285** | **4,87** |
| supply_demand di bawah gerbang | 222 | 48,6% | **-0,252** | -4,36 |
| **supply_demand PLACEBO** | 882 | 47,6% | **-0,120** | -3,25 |
| fvg | 566 | 54,6% | +0,227 | 3,64 |
| **fvg PLACEBO** | 1368 | 32,2% | **-0,300** | -9,10 |
| order_block | 779 | 68,4% | +0,130 | 3,74 |
| **order_block PLACEBO** | 1413 | 46,1% | **-0,182** | -6,71 |

Gerbang departure memisahkan **+0,285 lawan -0,252**, rentang 0,54R, setelah
biaya. Uji paruhnya stabil di ketiga detektor (supply_demand +0,056 lalu +0,062;
fvg +0,168 lalu +0,285).

> [!CAUTION]
> **Dua kesalahan saya sendiri ditemukan di sini, dan keduanya mengubah
> jawabannya.**
>
> Pertama, versi awal tool ini memakai `zone.profit_zone_rr` apa adanya. Nilai
> itu distempel dengan waktu bar **terakhir**, yang benar untuk "apa yang dilihat
> trader sekarang" dan **lookahead** untuk "apa yang bisa dilihat trader saat
> itu": zona lawan yang menetapkan targetnya bisa belum ada. Docstring
> `profit_zone_at` sudah mengatakannya persis, dan saya tetap memakai nilai
> stempelnya. Setiap target di run pertama terkontaminasi.
>
> Kedua, placebo pertama saya memakai bar sentuhan zona **asli** sebagai bar
> masuk kotak yang digeser. Kotak yang duduk jauh di atas harga karena itu
> "kena stop" di bar yang belum pernah ia masuki. Setelah placebo dimasuki
> sebagaimana zona asli dimasuki - pada bar harga pertama kali menyentuh
> proksimalnya - angkanya berayun dari **+0,284 ke -0,120**. Satu keputusan
> desain menggeser jawaban 0,4R.

#### Keberatan tautologi, dan kontrol yang menjawabnya

Keberatan itu saya ajukan sendiri terhadap hasil saya sendiri: distal zona asli
adalah **ekstrem sumbu**, yaitu harga yang sudah terbukti membalikkan harga,
sedangkan distal kotak acak adalah level sembarang yang ditembus derau. Sebagian
keunggulannya bisa jadi tidak lebih dari "stop di ekstrem nyata adalah stop yang
lebih baik" - yang memang klaim doktrinnya, tetapi juga dekat tautologi.

Placebo **berjangkar** mempertahankan sifat itu dan mematahkan sisanya: kotaknya
dibangun mengelilingi **swing terkonfirmasi** yang tidak ada hubungannya dengan
zona itu. Tinggi sama, sisi sama, stop di ekstrem nyata, tempat salah.

| Detektor | Zona asli | Placebo acak | Placebo berjangkar |
|---|---|---|---|
| supply_demand, lolos gerbang | **+0,285** | -0,120 | **-0,094** |
| fvg | +0,227 | -0,300 | -0,286 |
| order_block | +0,130 | -0,182 | -0,117 |

Placebo berjangkar memang sedikit lebih baik daripada yang acak (-0,094 lawan
-0,120), yang konsisten dengan ekstrem nyata jadi stop yang sedikit lebih baik.
Tapi selisih 0,026 itu tidak menjelaskan apa-apa dari 0,379 jarak ke zona
aslinya. **Keberatannya terjawab: keunggulannya bukan sekadar letak stopnya.**

#### Walk-forward, dan apa yang masih belum dibuktikannya

Standar proyek ini sendiri: gerbang tidak dinyalakan sebelum selisihnya menunjuk
arah yang benar di potongan waktu yang belum dilihat.

| Fold | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Ekspektasi R | +0,174 | +0,099 | +0,494 | +0,145 | +0,446 | +0,193 | +0,439 | +0,246 |

**8 dari 8 positif, sign test p=0,0078**, ambang yang sama dengan setiap
walk-forward lain di halaman ini.

> [!WARNING]
> Baca 8 dari 8 itu apa adanya, jangan lebih. Kedelapan fold berada **di dalam
> 2,5 bulan yang sama pada satu instrumen**, dengan n antara 28 dan 48 per fold.
> Itu membuktikan efeknya stabil sepanjang riwayat ini; ia tidak bisa
> membuktikan efeknya bertahan melintasi rezim, tahun, atau instrumen lain -
> dan pelajaran termahal di halaman ini adalah bahwa `age_bars` pernah lolos 8
> dari 8 di tiga geometri dan tetap ternyata gerbang departure yang menyamar.
>
> Yang bisa dikatakan: ini **satu-satunya hal di proyek ini yang lolos semua
> ujiannya sendiri setelah biaya dibebankan**. Yang belum: bukti bahwa ia
> berlaku di luar emas dan di luar musim panas 2026.

### Apa yang literatur sebenarnya katakan, putaran dua

Riset literatur kedua mencari bukti untuk konstruk yang dipakai di sini, dan
temuan terbesarnya adalah **ketiadaan**.

| Konstruk | Literatur peer-reviewed |
|---|---|
| **Stop hunting** | **Nol.** Pencarian judul dan abstrak OpenAlex, semua tahun: 58 hasil, **100% ekologi satwa liar** - rusa, simpanse, daging hutan. Mekanisme terdekat yang pernah terbit, kaskade Osler, menggambarkan harga **menembus terus** melewati level. **Kaki pembalikannya - bagian yang membuat setup ini bisa didagangkan - tidak pernah diuji siapa pun** |
| **Fair value gap** | **Satu artikel jurnal**, dan ia memakai frasa itu untuk arti lain sama sekali (harga pasar lawan nilai intrinsik) |
| **Volume profile, point of control, value area** | **Nol artikel empiris**, di OpenAlex maupun Crossref |
| Time-series momentum | Huang dkk. 2020: t gabungannya **gagal nilai kritis bootstrap**, dan labanya **disamai strategi yang memakai rata-rata sampel historis dan tidak mengasumsikan keterprediksian sama sekali** |

> [!WARNING]
> OpenAlex dan Zenodo kini tercemar makalah semu ber-DOI hasil generator pada
> istilah pencarian yang persis sama - satu pihak menyetor massal item berjudul
> seperti *"LAB #1050 HARMFUL: VIDEO SCOUT: ICT Gems - What to do when a Fair
> Value Gap fails?"*. Keberadaannya jangan dibaca sebagai minat akademik.

#### Angka yang harus dipakai menakar seluruh program ini

Dua hasil peer-reviewed memberi tolok ukur yang lebih keras daripada apa pun di
halaman ini:

- **Novy-Marx dan Velikov (RFS 2016)**: anomali dengan perputaran **di bawah 50%
  per bulan** umumnya menghasilkan spread bersih signifikan; **yang di atasnya
  jarang**.
- **Chen dan Velikov (JFQA 2023)**: 204 anomali dengan biaya realistis,
  rata-ratanya bersih **4 basis poin per bulan**, yang terkuat sekitar 10.

Perputaran Zonelab, diukur: **55 round trip per bulan** pada emas 15 menit dan
**11,8** pada emas 1 jam. Keduanya jauh di atas garis 50% itu, karena satu round
trip penuh sudah 100% perputaran.

Ada dua cara membaca ini dan keduanya harus dikatakan. Yang memberatkan:
strategi berperputaran tinggi adalah kelas yang paling sering mati setelah
biaya, dan literatur mengatakannya dengan tegas. Yang meringankan: pengukuran di
halaman ini **sudah membebankan biaya** - spread diukur per bar, komisi dari
jadwal terbitan, slippage dari tick. Yang membunuh anomali di Novy-Marx adalah
diukur kotor lalu dibiayai belakangan; ini dibiayai sejak awal.

Dan satu peringatan yang berlaku ke semuanya, dari **Brogaard dan Zareei (JFQA
2022)**: profitabilitas aturan teknikal di luar sampel **menurun sepanjang
waktu**. Setiap besaran efek historis di dokumen ini adalah **batas atas, bukan
perkiraan**.

#### Satu kontrol yang belum kita jalankan, dan seharusnya

Huang dkk. menunjukkan laba momentum **disamai oleh baseline yang tidak memakai
sinyal apa pun**. Digeneralisasi: **sistem apa pun yang labanya bisa direproduksi
baseline bebas-sinyal belum membuktikan keunggulan.** Placebo acak dan placebo
berjangkar di sini menguji "kotak di tempat salah", bukan "tanpa kotak sama
sekali dengan frekuensi dan geometri bracket yang sama". Itu kontrol berikutnya
yang layak dibangun.

#### KOREKSI 2026-08-17: gerbangnya diukur dengan lookahead, dan angkanya turun

Setiap angka gerbang departure di halaman ini sebelum tanggal ini **dihitung
dengan lookahead**, dan koreksinya besar. Ini temuan terpenting di proyek ini,
dan ia ditemukan dengan mengaudit jalur live, bukan dengan mengukur ulang.

`tools/calibrate.py` selalu memotong jendela departure di sentuhan pertama -
docstring `score_as_of` menyatakannya sendiri: "nilai chart yang sudah jadi tahu
lebih banyak daripada trader saat itu". **Detektor produknya tidak pernah
memotong.** Jadi harness dan produk menjalankan dua gerbang berbeda, dan hanya
satu yang jujur.

Diukur di 24.000 bar, tiga deret:

| | BTCUSDT 15m | BTCUSDT 1h | ETHUSDT 1h |
|---|---|---|---|
| Sentuhan pertama jatuh **di dalam** jendela lookahead | 87,4% | 85,1% | 85,9% |
| Lolos gerbang lama, **gagal** gerbang jujur | **34,0%** | 33,2% | 29,5% |
| Gagal gerbang lama, lolos gerbang jujur | **0,0%** | 0,0% | 0,0% |

Nol ke arah sebaliknya, karena jendela yang tidak dipotong adalah superset. Itu
**over-admisi sistematis satu arah**, bukan derau. Sepertiga zona yang digambar
tidak pernah memenuhi syarat pada saat ia bisa ditindaklanjuti.

**Apa yang berubah setelah dipotong:**

| | Sebelum (lookahead) | Sesudah (jujur) |
|---|---|---|
| **Emas 1 jam, dua tahun** | | |
| n kohort gerbang | 748 | **342** |
| Ekspektasi | +0,299 (t=7,59) | **+0,235 (t=3,76)** |
| Di bawah gerbang | -0,369 | **-0,056** |
| Pemisahan | 0,668 | **0,291** |
| Walk-forward | 8/8 | **8/8, p=0,0078** |
| **Emas 15 menit, 5000 bar** | | |
| Ekspektasi | +0,248 (t=4,32) | **+0,205 (t=2,09)** |
| Walk-forward | 8/8 | tidak bisa dibaca, n terlalu kecil |

**Bacaan yang jujur, dalam tiga kalimat.** Gerbangnya masih nyata pada sampel
besar: t=3,76 melewati ambang yang ditetapkan di depan, walk-forward tetap 8
dari 8, dan ia tetap mengalahkan kedua placebo. Pada sampel kecil ia **tidak**
lagi melewati ambangnya. Dan kekuatannya selama ini **dilebih-lebihkan kira-kira
dua kali lipat** - sebagian besar dari "kohort di bawah gerbang itu buruk sekali"
ternyata zona yang hanya tampak lemah karena departure-nya diukur dengan
pengetahuan belakangan.

> [!CAUTION]
> Yang membuat ini pelajaran, bukan sekadar bug: harness-nya **benar sejak
> awal** dan menyatakan alasannya di docstring-nya sendiri. Yang gagal adalah
> mengasumsikan produk mewarisi kedisiplinan harness-nya. Dua gerbang berbeda
> dengan nama yang sama hidup berdampingan selama berbulan-bulan, dan tidak satu
> pun tes menangkapnya karena tidak ada tes yang membandingkan keduanya.

#### Uji ambang buta, diulang di enam deret pada populasi jujur

Hasil uji buta pertama dijalankan **sebelum** gerbangnya dipotong, jadi ia
memakai departure yang terkontaminasi lookahead - dan ia hanya satu deret. Ini
pengulangannya: enam deret, populasi jujur, aturan pemilihan sama persis.

| Deret | Pilihan buta | Pemisahan di luar sampel | Pada 2,0 yang dikirim |
|---|---|---|---|
| XAUUSD 15m | 0,5 | +0,276 (t=2,35) | **+0,413 (t=2,58)** |
| XAUUSD 1j, dua tahun | 1,5 | +0,244 (t=2,67) | **+0,297 (t=2,93)** |
| BTCUSDT 15m | 5,0 | +0,138 (t=1,35) | **+0,222 (t=4,60)** |
| BTCUSDT 1j | **2,0** | +0,261 (t=3,73) | +0,261 (t=3,73) |
| ETHUSDT 1j | 3,0 | +0,389 (t=4,11) | +0,336 (**t=4,64**) |
| PAXGUSDT 1j | 4,5 | +0,417 (t=2,93) | +0,298 (**t=4,27**) |

**Pilihan butanya berhamburan dari 0,5 sampai 5,0 tanpa kesepakatan.** Itu tanda
tangan derau: kalau ada ambang optimal yang nyata, enam deret independen akan
berkumpul di sekitarnya. Yang terjadi justru sebaliknya - tiap deret memilih
tempat berbeda, dan satu-satunya yang memilih 2,0 melakukannya karena 2,0 memang
menang di sana.

Sementara **2,0 punya t tertinggi di lima dari enam deret**, dan pemisahan positif
di keenamnya.

> [!IMPORTANT]
> Hasil uji buta pertama **tidak bereproduksi**. Ia memilih 1,0 ATR dan memberi
> pemisahan +0,878 di luar sampel, dan dilaporkan sebagai bukti kuat bahwa 2,0
> terlalu konservatif dan membuang lebih banyak daripada perlu. Pada populasi
> jujur, deret yang sama memilih 1,5 dan memberi +0,244.
>
> Dua sebabnya, dan keduanya sudah tercatat di halaman ini sebagai pelajaran:
> angkanya dihitung pada departure berlookahead, dan ia satu deret. Menariknya,
> pengulangan ini **membenarkan keputusan untuk tidak mengubah default** yang
> diambil saat itu justru karena satu pembelahan bukan bukti - dan itu ternyata
> tepat.

#### Ambangnya dipilih buta, dan gerbangnya bertahan

Setiap uji gerbang di halaman ini membawa cacat yang sama diam-diam: **ambang 2
ATR-nya dipilih pada data yang lebih awal.** Jadi semuanya menguji apakah ambang
itu bertahan, bukan apakah gerbangnya nyata. Angka yang dipilih dengan
pengetahuan belakangan bisa lolos banyak uji luar-sampel dan tetap merupakan
pengetahuan belakangan.

`tools/blind_gate.py` menutupnya satu-satunya cara yang mungkin. Deretnya dibelah
menurut waktu, ambangnya dipilih pada paruh **pertama saja** dengan aturan yang
ditetapkan lebih dulu, dan paruh kedua bukan sekadar tidak dipakai melainkan
tidak dibaca. Lalu dievaluasi sekali di paruh kedua. Hasilnya adalah apa yang
benar-benar didapat orang yang berdiri di titik tengah tanpa tahu masa depan.

Aturan pemilihannya: ambang dengan **pemisahan** terlebar antara kohort yang
lolos dan yang tidak, dengan syarat kedua kohort menyisakan minimal 50 trade.
Pemisahan, bukan ekspektasi mentah, karena tugas gerbang adalah memilah - dan
memaksimalkan ekspektasi saja akan melayang ke ambang yang menyisakan kelompok
terkecil dan paling beruntung di atasnya.

| Dipilih buta di paruh pertama | Diuji di paruh kedua |
|---|---|
| **1,0 ATR**, pemisahan +0,854 | pemisahan **+0,878**, t=12,57 |
| (ambang yang dikirim: 2,0) | pemisahan +0,670, t=9,38 |

**Pemisahan di luar sampel MELEBIHI yang di dalam sampel.** Itu kebalikan dari
tanda tangan overfitting, yang selalu meluruh keluar sampel. Gerbangnya nyata.

Dan ada bacaan kedua yang lebih berguna daripada angka utamanya. Setiap ambang
dari 1,0 sampai 6,0 memberi pemisahan positif di paruh pertama, antara +0,41 dan
+0,85, jadi efeknya **bukan pisau di satu nilai**. Pemisahan justru paling lebar
di ambang paling rendah, karena kohort di bawah 1,0 ATR sangat buruk (-0,773)
sementara menaikkan ambang di atas 2,0 hampir tidak menambah apa pun ke kohort
atasnya.

> [!IMPORTANT]
> Artinya gerbang ini bekerja dengan **membuang yang terburuk, bukan memilih yang
> terbaik**. Itu konsisten dengan temuan lama di halaman ini bahwa di atas 2 ATR
> tambahan departure tidak membeli apa-apa, dan itu mengubah cara memakainya:
> 2,0 yang dikirim bersifat konservatif, ia membuang lebih banyak daripada perlu.
> Pada 1,0 ATR jumlah trade naik dari 373 ke 521 di paruh kedua dengan pemisahan
> yang lebih lebar.
>
> Batasnya: kohort bawah pada 1,0 ATR kecil, 100 trade di dalam sampel dan 119 di
> luar. Cukup untuk dibaca, tidak cukup untuk dijadikan presisi.

#### Lintas tahun, dan pada instrumen yang berbeda

Delapan fold walk-forward emas kemarin semuanya di dalam 2,5 bulan yang sama.
Batasan itu dinyatakan terbuka, dan inilah pengujiannya. Dukascopy terlalu lambat
untuk mengunduh bertahun-tahun (satu request per jam tick), jadi ujiannya jalan
di **Yahoo GC=F**, yang memberi 730 hari dalam satu request.

Perlu ditegaskan apa yang berubah dan apa yang tidak. Yang berubah: instrumennya
(**futures COMEX**, bukan spot), timeframe-nya (1 jam, bukan 15 menit), dan
periodenya (dua tahun, bukan 2,5 bulan). Yang **tidak** berubah: detektornya,
parameternya, dan ambang gerbang 2 ATR-nya. Tidak ada yang difit ulang.

| Kohort, 13.725 bar, biaya Exness Zero | n | Menang | Ekspektasi | t |
|---|---|---|---|---|
| **Lolos gerbang** | 748 | 72,9% | **+0,299** | **7,59** |
| Di bawah gerbang | 532 | 47,4% | **-0,369** | -11,97 |
| Placebo acak | 2064 | 46,2% | -0,135 | -5,45 |
| Placebo berjangkar | 394 | 48,0% | -0,055 | -0,92 |

**Walk-forward: 8 dari 8 fold positif, p=0,0078**, dari +0,184 sampai +0,416,
dan trennya justru menanjak bukan meluruh.

##### Keberatan roll kontrak, diukur lalu gugur

`GC=F` adalah deret front-month kontinu yang **melompat saat roll kontrak**, dan
lompatan itu akan dibaca setiap detektor di sini sebagai lilin impuls raksasa
lalu digambari zona. Dua tahun memuat sekitar delapan roll, jadi keberatan ini
harus diukur, bukan diasumsikan kecil.

Diukur: **2 bar dari 13.725** punya lompatan semalam di atas 5 ATR, dan **nol
dari 831 zona gerbang** terbentuk melintasi salah satunya. Roll-nya tidak
mengontaminasi hasil.

> [!IMPORTANT]
> Ini koroborasi terkuat yang pernah ada di proyek ini. Gerbangnya bereproduksi
> di **instrumen berbeda, timeframe berbeda, dan periode delapan kali lebih
> panjang**, tanpa satu pun parameter disentuh, dan pemisahan lolos-lawan-tidak
> justru melebar jadi 0,67 R.
>
> Yang masih belum: ambang 2 ATR itu **dipilih dari data yang lebih awal**, jadi
> ini bukan uji independen atas ambangnya sendiri, melainkan uji apakah ambang
> itu bertahan. Dan placebo berjangkar di sini t=-0,92, tidak signifikan pada
> n=394, jadi batas bawah marginnya lebih longgar daripada di emas 15 menit.

#### Diharga di broker sungguhan: Exness

Selisih antara kolom sentral dan konservatif seluruhnya jadwal komisi broker,
jadi satu-satunya cara tahu kolom mana yang berlaku adalah mengharga broker yang
benar-benar dipakai. Terverifikasi dari Help Center Exness sendiri, 2026-08-16.

Satu lot XAUUSD adalah 100 ons troy, jadi pada emas 4400 nosionalnya 440.000 dan
1 bp sama dengan 44 USD.

| Akun | Komisi | Per putaran | bp |
|---|---|---|---|
| Zero | 5,50 USD/lot per sisi | 11,00 | **0,250** |
| Raw Spread | 3,50 USD/lot per sisi | 7,00 | **0,159** |
| Standard, Cent, Pro | tanpa komisi | - | 0 |

Angka 0,159 itu praktis persis asumsi "murah" 0,16 bp yang sudah dipakai di
halaman ini. Jadi +0,234 R ternyata sudah dihitung pada jadwal biaya Exness
tanpa disengaja.

Yang dimodelkan adalah **Zero**, meski komisinya lebih tinggi, karena ia
satu-satunya akun yang biaya totalnya bisa diketahui dari sumber publik: Exness
tidak menerbitkan spread XAUUSD untuk tipe akun mana pun, dan hanya Zero yang
berkomitmen spread nol pada instrumen top-30 selama 95% hari.

**Swap benar-benar nol**, dan itu terverifikasi bukan diasumsikan: Indonesia ada
di daftar negara swap-free Islami Exness, di mana statusnya otomatis, seluruh
akun, dan mencakup semua instrumen.

##### Biaya yang hampir mematikannya, dan dua bug yang menyanjung

Exness mengenakan **200 USD per lot per malam** pada XAUUSD yang masih terbuka
lewat 21:00 UTC. Itu **4,545 bp**, lebih mahal daripada tiga belas komisi
putaran, dan pemicunya ditulis sebagai trading yang tidak "sebagian besar di
dalam hari perdagangan" - deskripsi persis strategi ini.

Pertanyaannya jadi empiris: **berapa persen trade yang benar-benar
menyeberanginya?** Menghitungnya memunculkan dua bug, keduanya menyanjung.

1. Deteksi rollover mencari bar berstempel 21:00 UTC. **Emas tidak punya bar
   21:00 sama sekali** - jam itu adalah jeda sesi hariannya, dan diukur pada
   deret ini setiap jam lain punya sekitar 216 bar sementara 21:00 punya nol.
   Uji berbasis kehadiran bar karena itu melaporkan "tidak pernah kena", yang
   kebetulan adalah jawaban yang menguntungkan. Diperbaiki dengan menghitung
   dari **jam dinding**, bukan dari bar.
2. Aturan tutup-sebelum-rollover punya bug yang sama di tempat kedua, jadi ia
   tampak tidak berpengaruh apa-apa padahal sebenarnya tidak pernah jalan.

Jawabannya: **7,2%**, bukan sekitar 83% yang saya asumsikan dari batas 80 bar.
Sebagian besar trade selesai jauh sebelum batas itu. Biaya adminnya karena itu
rata-rata cuma 0,33 bp.

| Emas 15m, kohort gerbang, Exness Zero | Ekspektasi | t | Walk-forward |
|---|---|---|---|
| Tahan seperti biasa | **+0,248** | **4,32** | **8 dari 8** |
| Tutup sebelum rollover | +0,222 | 4,30 | - |

> [!IMPORTANT]
> Aturan tutup-sebelum-rollover **merugikan**, dan itu berlawanan dengan intuisi
> yang wajar. Hanya 7,2% trade yang membayar biaya adminnya, tetapi aturan itu
> memotong **semuanya**. Menambahkannya untuk menghindari biaya yang jarang
> muncul membuang lebih banyak daripada yang dihemat.

Di Exness, biaya broker bukan yang menentukan strategi ini. Yang menentukan
tetap sama seperti sebelumnya: apakah gerbang departure-nya nyata di luar sampel
ini.

#### Di luar emas, dan koreksi biaya yang harus didahulukan

Sebelum uji itu bisa dijalankan, model biayanya harus diperbaiki. Versi pertama
memakai 0,07 dan 0,02 dalam **satuan harga absolut**, yaitu angka emas. Dipakai
apa adanya di BTC seharga 100.000, keduanya kira-kira 0,00009 bp - kolom
"berbiaya" akan jadi perdagangan gratis yang memakai label berbiaya. Biaya
sekarang dinyatakan dalam **basis poin nosional**, per instrumen.

Konversi pertamanya juga salah dan ketahuan sebelum dipakai: 0,07 USD per ons
pada emas 4400 adalah **0,16 bp, bukan 1,6**. Sepuluh kali terlalu keras, dan
itu memotong 0,07R dari jawabannya.

| Deret | Zona lolos gerbang | Placebo berjangkar | Margin | Walk-forward |
|---|---|---|---|---|
| XAUUSD 15m | **+0,285** | -0,094 | **+0,379** | 8/8 |
| ETHUSDT 1h | **+0,108** | -0,242 | **+0,350** | 8/8 |
| BTCUSDT 1h | **+0,103** | -0,237 | **+0,340** | 7/8 |
| BTCUSDT 15m | -0,122 | -0,435 | +0,313 | 1/8 |
| PAXGUSDT 1h | -0,103 | -0,378 | +0,275 | 2/8 |
| PAXGUSDT 15m | -0,296 | -0,443 | +0,147 | 0/8 |

**Dua hal yang selama ini saya campur, dan ternyata terpisah rapi.**

Yang **menyeberang**: margin zona di atas placebo berjangkar positif di **enam
dari enam deret**, dari +0,147 sampai +0,379. Kalau margin itu hanya muncul di
emas, ia patut dicurigai sebagai artefak satu instrumen. Ia muncul di semuanya,
termasuk instrumen yang secara absolut rugi. **Gambarnya membawa informasi
nyata, dan itu kini terbukti lintas instrumen, bukan cuma lintas waktu.**

Yang **tidak menyeberang**: keuntungan absolutnya. Positif setelah biaya cuma
pada emas 15m, BTC 1 jam, dan ETH 1 jam. Sebabnya struktural dan bukan tentang
gambarnya sama sekali - komisi Binance 20 bp per putaran melawan emas 0,16 bp,
sekitar **125 kali lipat**.

Dan pola timeframe-nya konsisten: **15 menit rugi, 1 jam menang**, kecuali pada
emas yang biayanya terlalu kecil untuk mengganggu. Sebabnya aritmetika, bukan
pasar: biaya adalah pecahan tetap dari **harga**, sedangkan R adalah jarak
stop - dan jarak stop mengecil di timeframe rendah. Biaya bp yang sama karena
itu memakan porsi R yang jauh lebih besar di 15 menit.

> [!IMPORTANT]
> Kesimpulan yang bisa dipertanggungjawabkan sekarang bukan "zona menghasilkan
> uang" dan bukan "zona tidak berguna". Melainkan: **zona membawa informasi yang
> terukur di enam dari enam deret, dan apakah informasi itu terbayar ditentukan
> oleh struktur biaya instrumen dan timeframe-nya.** Pada biaya kripto di 15
> menit, informasi senilai +0,31 R tetap tenggelam.

#### Biayanya sendiri diriset, dan dua angkanya ternyata salah

Konstanta biaya sebelumnya "dinyatakan, bukan difit" - jujur, tetapi tidak
bersumber. Riset terhadap sumber primer (jadwal biaya Binance, jadwal komisi
IBKR, tick Dukascopy yang diunduh dan diukur sendiri, order book Binance yang
diambil langsung) mengoreksi dua di antaranya dan menemukan satu yang hilang.

| Konstanta | Sebelum | Sesudah | Sebab |
|---|---|---|---|
| Slippage XAUUSD | 0,05 bp | **0,5 bp** | Diukur pada tick: mid bergerak 0,17 bp dalam 250 ms dan 0,79 bp di p90. 0,05 bukan optimistis, melainkan **salah** |
| Swap XAUUSD | tidak ada | **1,0 bp per rollover** | 80 bar 15 menit adalah 20 jam melawan rollover 21:00 UTC, jadi hampir setiap trade menyeberanginya. Rabu dikenakan tiga kali lipat |
| Komisi XAUUSD | 0,16 bp | 0,16 bp sentral, **3,0 bp konservatif** | Premisnya tidak terverifikasi. Satu-satunya jadwal komisi emas yang bisa diambil adalah IBKR, 1,5 bp per sisi, **19 kali lebih tinggi** |

Satu klaim laporan itu saya **tolak setelah diperiksa**: ia menyebut spread
dibebankan dua kali. Aritmetiknya tidak begitu - `plan.build` menaikkan fill
entry satu spread penuh dan membiarkan stopnya, yang identik dengan membayar
setengah spread di tiap kaki. Nama tesnya yang menyesatkan, bukan perilakunya.

**Dan inilah angka yang menentukan keputusan.**

| Emas 15m, kohort gerbang | Biaya sentral | Biaya konservatif (jadwal IBKR) |
|---|---|---|
| Ekspektasi | **+0,234** (t=4,18) | **+0,082** (t=1,67) |
| Placebo berjangkar | -0,127 | -0,231 |
| Margin | +0,361 | +0,313 |
| Biaya sebagai porsi R | 9,4% | **20,5%** |
| Walk-forward | 8 dari 8 | **4 dari 8** |

> [!CAUTION]
> Pada tingkat biaya yang **benar-benar bisa diverifikasi**, keunggulan emasnya
> **tidak bertahan**: t turun ke 1,67 dan walk-forward-nya jadi 4 dari 8.
> Marginnya atas placebo tetap +0,313, jadi informasinya masih ada - yang hilang
> adalah kemampuannya melewati biaya.
>
> Selisih antara kedua kolom itu **seluruhnya jadwal biaya broker**, bukan
> sinyalnya. Artinya kelayakan sistem ini bergantung pada mendapat komisi di
> bawah kira-kira 1 bp per putaran - dan angka retail yang beredar (3,50 USD per
> sisi per lot) diulang di mana-mana tanpa pernah diterbitkan dalam jadwal resmi
> mana pun yang bisa diambil.

Satu hal yang tidak bisa diukur dan sebabnya struktural: FVG dan order block
tidak punya konsep zona lawan, jadi targetnya dihitung terhadap zona lawan
sejenisnya sendiri. Menerapkan aturan jalan milik supply/demand ke gambar metode
lain adalah hal yang `main.py` tolak secara eksplisit, jadi angkanya dilaporkan
dengan batasan itu terpampang.

### Apakah kotaknya saling bertabrakan

Semua uji kesetiaan sebelumnya menanyakan hal yang sama: apakah kotak **ini**
ada di tempat yang benar. `drawing_accuracy` membandingkan tiap zona dengan
lilin base-nya sendiri, audit piksel membandingkan persegi yang tercat dengan
skala harga. Keduanya per-zona. **Tidak ada yang pernah melihat dua zona
sekaligus**, jadi satu kelas cacat tidak pernah terukur, dan justru kelas itulah
yang dilihat pengguna.

`tools/collisions.py` mengukurnya pada default yang dikirim, bukan pada populasi
pengukuran. Ini disengaja dan kebalikan dari tool lain: pertanyaannya bukan "apa
yang ditemukan detektor" melainkan "apa yang dilihat pengguna", jadi display cap
adalah bagian dari jawaban, bukan bias yang harus dihindari.

Empat besaran, dan dua di antaranya cacat:

- **Tumpang tindih sesisi antar detektor** bukan cacat. FVG di dalam zona demand
  adalah dua metode yang sepakat, dan itu justru alasan menjalankan keduanya.
- **Redundansi di dalam satu detektor** adalah cacat: observasi yang sama
  digambar dua kali.
- **Tumpang tindih berlawanan sisi** adalah kontradiksi. Satu harga tidak bisa
  sekaligus tempat pembeli mengalahkan penjual dan tempat penjual mengalahkan
  pembeli pada saat yang sama.
- **Tinta**, yaitu persen chart yang tercat, adalah angka keterbacaan.

| | Awal | Sesudah perbaikan |
|---|---|---|
| Zona tergambar | 201 | **131** |
| Tumpang tindih sesisi | 483 | **195** |
| Redundansi satu detektor | 258 | **80** |
| Tumpang tindih berlawanan | 31 | **20** |
| Tinta rata-rata | 39,6% | **26,7%** |
| Tinta terburuk (ETH 1j) | 52,4% | 32,6% |
| Tumpukan terdalam | 9 | **7** |

Dua perubahan menghasilkannya, dan hanya satu yang soal gambar:

1. **Aturan "terakhir" pada order block ditegakkan.** Ini perbaikan kesetiaan,
   bukan kosmetik, dan kebetulan membuang sebagian besar redundansinya.
2. **Display cap diturunkan 12 ke 6.** Cap berlaku per detektor **dan** per
   sisi, jadi 12 mengizinkan 3 x 2 x 12 = 72 kotak dalam satu chart. Pada 12,
   rata-rata 39,6% chart tercat dan satu deret mencapai 52,4%; itu bukan anotasi
   lagi, itu latar belakang. Keterbacaan adalah keputusan tampilan, jadi
   diputuskan dengan mengukur tinta, bukan dengan selera. Dan tidak seperti
   gerbang, menurunkannya tidak bisa membiaskan ramalan apa pun, karena tidak
   ada ramalan yang bisa dibiaskan.

> [!WARNING]
> Satu jalan buntu dicatat karena angkanya justru lebih bagus. Meminjam
> `_dedupe` milik supply/demand untuk FVG dan order block memotong tumpang
> tindih sesisi 74% dan menyisakan hanya 3 kontradiksi, jauh lebih rapi daripada
> hasil akhir di atas. Itu dibuang di jam yang sama. `_dedupe` memilih penyintas
> lewat `formation_score`, yang bernilai 0,0 untuk **setiap** zona imbalance,
> jadi pemenangnya adalah apa pun yang kebetulan tersortir duluan: pada satu tes
> ia menyimpan serpihan selebar 0,3 dan membuang gap selebar 4,5 yang memuatnya.
> Dua gap di bar berbeda adalah dua peristiwa, bukan satu yang digambar dua
> kali. **Angka bagus yang diperoleh dengan aturan yang tidak bisa dibenarkan
> lebih berbahaya daripada angka sedang yang benar.**

#### Diukur ulang dengan lima detektor, dan tinta itu naik lagi

Tabel di atas diukur dengan **tiga** detektor. Sekarang ada **lima**, `ifvg` dan
`breaker` menyusul, dan `tools/collisions.py` menuliskan ketiga nama itu secara
hardcode. Jadi satu-satunya pengukuran di repo ini yang menanyakan **apa yang
dilihat pengguna** justru buta terhadap dua kotak yang benar-benar digambar
untuknya. Sekarang ia dijalankan dari registry, bukan dari daftar nama.

Diukur ulang pada 500 bar, seluruh detektor menyala, cap seperti yang dikirim:

| | Tiga detektor | **Lima detektor** |
|---|---|---|
| Zona tergambar | 131 | **198** |
| Pasangan diperiksa | - | 3866 |
| Tumpang tindih sesisi | 195 | **465** |
| Tumpang tindih berlawanan | 20 | **99** |
| Tinta rata-rata | 26,7% | **31,6%** |
| Tumpukan terdalam | 7 | **11** |

Tinta per deret: `PAXGUSDT` 15m 36,2%, `PAXGUSDT` 1j 22,8%, `BTCUSDT` 15m 26,4%,
`BTCUSDT` 1j 30,3%, `ETHUSDT` 1j 42,3%.

Ini **regresi keterbacaan yang nyata**, dan baris yang dipakai halaman ini
sendiri berlaku apa adanya: lewat kira-kira sepertiga chart, kotaknya berhenti
menganotasi harga dan menjadi latar belakangnya.

| Display cap | Kotak | Tinta rata-rata | Tumpang tindih berlawanan |
|---|---|---|---|
| 3 | 120 | 19,6% | 65 |
| 4 | 150 | 24,6% | 78 |
| **6 (dikirim)** | **198** | **31,6%** | **99** |
| 8 | 238 | 40,1% | 104 |
| 12 | 291 | 46,1% | 104 |

Seluruh baris di atas diukur **sesudah** tepi kiri kotak inversi diperbaiki, jadi
tabel ini dan `docs/collisions.json` berasal dari satu jalannya yang sama.
Sebelum perbaikan itu, cap yang dikirim membaca 33,6% dan cap 12 membaca 49,8%:
kotak inversi dulu digambar sejak bar induknya, jadi ia mengecat rentang waktu
yang bukan miliknya. Selisihnya kecil dan arahnya satu, dan ia disebut di sini
supaya angka lama yang beredar bisa dikenali sebagai angka lama.

**Bacaan pertama atas lonjakan sisi-berlawanan itu salah, dan salahnya diperiksa
bukan didiamkan.** Saya menduga penyebabnya kotak induk yang digambar
berdampingan dengan inversinya sendiri. Terukur: **nol** dari 99 tumpang tindih
berlawanan adalah kotak melawan induknya sendiri. Sebabnya struktural, dan
seharusnya bisa saya duga dari kodenya: menginversi menuntut induknya **jebol**
lebih dulu, sementara `show_broken` dikirim dalam keadaan mati, jadi induknya
tidak pernah ada di chart pada saat yang sama.

Yang benar-benar terjadi: **79 dari 99** melibatkan kotak inversi melawan persegi
**lain**. Itu bukan artefak, itu **ongkos sesungguhnya dari menambahkan dua
detektor ini**, dan ia harus dibayar dengan cap atau tidak dibayar sama sekali.

### Aturan berhentinya berlaku

Setiap hipotesis arah yang didaftarkan di halaman ini gagal, dan hitungannya
tidak ditulis ulang di sini justru karena ia terus bertambah: yang berlaku adalah
daftar H1 sampai H11 di atas, bukan sebuah angka yang basi setiap kali satu
hipotesis baru dijalankan. H4 menambah dua detektor yang terbukti menandai
sesuatu, H11 menambah konjungsi tiga bagian yang sumbernya benar-benar jelaskan,
dan tidak satu pun dari mereka mengubah jawaban soal arah.

**Tidak ada panah yang bisa digambar dari apa pun yang diukur di sini.** Yang
bisa dikatakan, dan ini bukan hasil kosong: umur zona memisahkan hasil sebesar
16 poin persen pada sentuhan pertama, dan itu sejalan dengan satu-satunya
literatur yang pernah mengukurnya.

## Kekuatan uji

Dengan 2707 zona terselesaikan dan kelas minoritas 1164 di reward 2,0, efek AUC
sebesar 0,53 kini dapat dibedakan dari 0,50. Untuk uji reaksi, kelompok terkecil
2711 peristiwa mendeteksi efek sekitar 0,08 simpangan baku pada tenaga 80%. Untuk
selisih proporsi per potongan walk-forward, satu potongan hanya bisa menyelesaikan
selisih sekitar 10 pp, dan karena itulah statistiknya adalah sign test lintas
potongan dan bukan p per potongan.

## Yang tidak diukur

> [!NOTE]
> **Satu baris dicoret dari daftar ini.** "Sentuhan kedua dan seterusnya" sudah
> diukur, dan hasilnya ada di [bagian sentuhan
> lanjut](#sentuhan-kedua-dan-seterusnya-dan-gerbangnya-tidak-ikut-ke-sana):
> keunggulan gerbang departure adalah **gejala sentuhan pertama**, +14,5 sampai
> +21,3 pp di sana dan nol sampai negatif sesudahnya, sehingga setiap zona
> sentuhan lanjut yang digambar chart melewati filter yang belum tervalidasi.

- **Zona yang tidak pernah disentuh** tidak punya hasil, jadi tidak masuk sampel.
- **Kontrol placebo hanya menguji level sembarangan**, bukan level struktural
  lain seperti swing high biasa atau angka bulat.
- **Emas hanya diwakili PAXG.** Tiga dari lima deret adalah kripto.
- **Tabel utama di halaman ini tanpa biaya transaksi, spread, atau slippage.**
  Itu tetap berlaku untuk tabel bertahan/gagal di atas, dan TIDAK lagi berlaku
  untuk seluruh halaman: bagian biaya di atas menjalankan ulang kohort gerbang
  dengan komisi, slippage, spread dan carry yang diriset, dan justru di situlah
  keunggulan emasnya berhenti melewati biayanya pada jadwal komisi yang benar
  benar bisa diambil. Baca dua-duanya, jangan salah satu.
- **Satu riwayat adalah satu lintasan.** Walk-forward menunjukkan efeknya stabil
  di seluruh riwayat ini; ia tidak bisa menunjukkan efeknya bertahan ke depan.
- **Peristiwa yang bertumpuk tidak diberi bobot keunikan.** Beberapa zona lahir
  pada ayunan yang sama dan disentuh berdekatan, jadi n efektifnya lebih kecil
  daripada n nominal. Bootstrap blok pada uji reaksi menanganinya; uji dua
  proporsi pada tabel utama tidak.
- **Walk-forward belum distratifikasi menurut umur.** Delapan potongan itu
  menguji apakah gerbangnya bertahan lintas waktu, bukan apakah ia bertahan di
  dalam pita umur yang sama pada tiap potongan. Selisih +15,3 pp di dalam umur
  diukur pada seluruh riwayat sekaligus.
- **Selang +15,1 sampai +21,3 pp belum bisa dipersempit.** Menutupnya menuntut
  hasil bebas-distal seperti yang sudah dibangun di H1, dijalankan pada kohort
  yang jebol tanpa pernah tercatat menyentuh. Sampai itu ada, angka judulnya
  adalah selang dan bukan titik.
- **Koreksi umur dan koreksi seleksi hanya dijalankan di reward 1,0 ATR.** Kedua
  angka itu belum punya pasangan di geometri 0,5 dan 2,0, jadi belum diketahui
  apakah selangnya bergerak bersama geometri bracket-nya.

## SSMT lawan volatilitas, 20 Agustus 2026: klaim tidak terbukti, dan ambangnya nyaris tidak pernah menyala

Klaim yang diajukan ke proyek ini: *"SMT Divergence pada pasar dengan volatilitas
rendah sangat akurat, tapi pada pasar dengan volatilitas ekstrem, SMT sering kali
menjadi false signal"*, disertai usulan gerbang **ATR > 2,5x rata-rata 30 hari**.

Angka 2,5 datang tanpa pengukuran, dan proyek ini tidak mengirim ambang yang
belum diukur. Tetapi klaim di bawahnya empiris dan murah diuji, jadi diuji lebih
dulu.

```
python -m tools.smt_volatility --bars 50000 --interval 1h --degree day \
  --provider mt5 --pairs "XAUUSD|XAGUSD,XAUUSD|DXY,XAUUSD|XPTUSD,XAUUSD|BTCUSD" \
  --json ../docs/smt-volatility.json
```

**Bracketnya simetris**, `k` ATR ke dua arah dari close di `knowable_at`. Simetris
dengan sengaja: di bawah random walk ia selesai di 50% secara konstruksi, jadi
50% ITU null-nya dan tidak butuh estimasi terpisah. Bracket asimetris akan butuh
baseline sendiri dan membiarkan geometri bracket menyamar sebagai temuan, yaitu
kesalahan yang sudah didokumentasikan panjang di `calibrate.resolve` soal tinggi
zona. Seri yang menyentuh kedua sisi dalam satu bar **dibuang**, bukan diskor:
data bar tidak bisa mengatakan mana yang lebih dulu, dan menghitungnya sebagai
gagal akan memberatkan klaim sementara sebagai berhasil akan memanjakannya.

### Gabungan empat pasangan

| bracket | n | seluruh sampel | Q1 tenang | Q4 paling liar | rentang |
|---|---|---|---|---|---|
| 0,5 ATR | 3324 | 51,1% | 50,0% | 54,0% | **+4,0** |
| 1,0 ATR | 3452 | 50,9% | 49,9% | 53,2% | **+3,3** |
| 2,0 ATR | 3439 | 47,1% | 49,5% | 45,8% | **-3,7** |

**Klaimnya tidak terbukti.** Selisih kuartil tertenang lawan terliar di bawah 5
poin di ketiga lebar bracket, dan galat baku satu proporsi pada n sekitar 830 per
keranjang adalah 1,7 poin, jadi selisih 4 poin itu sekitar 1,6 sigma. Lebih
menentukan daripada besarnya: **tandanya berbalik**. Pasar liar terbaca lebih baik
pada bracket 0,5 dan 1,0 ATR, dan lebih buruk pada 2,0. Efek yang nyata tidak
berbalik tanda mengikuti lebar bracket; artefak bracket melakukannya.

### Temuan kedua, dan ini yang menutup usulannya

**Ambang yang diusulkan nyaris tidak pernah menyala.** ATR > 2,5x rata-rata 30
hari terjadi **12 sampai 13 kali dari sekitar 3.400 divergensi**, yaitu 0,4%.
Andai efeknya nyata, filter yang menyala pada empat dari seribu peristiwa tidak
bisa mengubah apa pun. Usulannya bukan hanya tidak terdukung, ia juga tidak
relevan pada skala yang diusulkan.

### Temuan ketiga, tidak diminta tetapi penting

**Seluruh sampel berada di null.** 51,1% / 50,9% / 47,1% terhadap null 50%. Jadi
SSMT bearish - simbol chart mengambil high kuarter sebelumnya sementara
partnernya gagal - **tidak punya keunggulan arah yang terukur** di sampel ini,
volatilitas atau bukan.

> [!IMPORTANT]
> Ini konsisten dengan dua belas hipotesis arah pre-registered yang sudah gagal
> di proyek ini, dan ia **tidak** membatalkan layer SSMT: layer itu menggambar di
> mana divergensi terjadi, dan tidak pernah mengklaim arah. Yang dibatalkan
> adalah membaca satu divergensi sebagai sinyal jual. Aturan konjungsi tiga
> syarat di `app/deduce.py` boleh saja berperilaku lain, dan itu pertanyaan
> terbuka yang hanya bisa dijawab log shadow trading - tetapi satu dari tiga
> premisnya sekarang terukur berada di null, dan itu justru gunanya
> pre-registration.

**Yang dihemat:** satu modul Regime Detection, satu ambang karangan, dan satu
filter yang akan membuang peristiwa tanpa imbalan terukur.

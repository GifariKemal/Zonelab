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

Tiga besaran, dan hanya satu di antaranya cacat:

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

### Aturan berhentinya berlaku

Tiga hipotesis arah dijalankan, tiga gagal. H4 menambah dua detektor yang
terbukti menandai sesuatu, dan tidak satu pun dari mereka mengubah jawaban soal
arah.

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

- **Sentuhan kedua dan seterusnya.** Semua di atas hanya sentuhan pertama.
- **Zona yang tidak pernah disentuh** tidak punya hasil, jadi tidak masuk sampel.
- **Kontrol placebo hanya menguji level sembarangan**, bukan level struktural
  lain seperti swing high biasa atau angka bulat.
- **Emas hanya diwakili PAXG.** Tiga dari lima deret adalah kripto.
- **Tidak ada biaya transaksi, spread, atau slippage.** Ini bukan hasil dagang.
- **Satu riwayat adalah satu lintasan.** Walk-forward menunjukkan efeknya stabil
  di seluruh riwayat ini; ia tidak bisa menunjukkan efeknya bertahan ke depan.
- **Peristiwa yang bertumpuk tidak diberi bobot keunikan.** Beberapa zona lahir
  pada ayunan yang sama dan disentuh berdekatan, jadi n efektifnya lebih kecil
  daripada n nominal. Bootstrap blok pada uji reaksi menanganinya; uji dua
  proporsi pada tabel utama tidak.

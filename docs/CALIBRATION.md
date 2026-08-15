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

### Aturan berhentinya berlaku

Tiga hipotesis dijalankan, tiga gagal. H4 adalah detektor baru, yaitu pekerjaan
membangun dan bukan pengukuran, jadi ia menunggu keputusan terpisah.

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

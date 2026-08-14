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

14 uji dijalankan di berkas itu; ambang Bonferroni 0,0036. Angka p=0,029 untuk
pembalikan zona digambar **tidak lolos** koreksi itu; p=0,0001 untuk kelompok
ditolak lolos.

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

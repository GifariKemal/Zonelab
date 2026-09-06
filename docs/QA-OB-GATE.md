# Gerbang departure order block, diukur 6 September 2026

Detector ketiga yang lewat rig yang sama, dan yang pertama di antaranya yang
**bisa mengirim order**. Itu yang membedakan dokumen ini dari
`QA-IFVG-GATE.md`: temuan di sini menyentuh uang, bukan teks panel.

> [!CAUTION]
> `order_block` adalah layer `orderable` dengan gerbang `floor`, dan ia
> **tidak punya `measured_intervals`**. `tools/execute.py:384` menolak sebuah
> layer di timeframe yang tidak terukur dengan `ValueError`, tetapi penolakan
> itu hanya menyala kalau daftarnya ada. `fvg` punya `("30m",)`.
> `order_block` punya `None`, jadi executor menerimanya di timeframe mana pun.
> Pengukuran di bawah menemukan profit factor **di bawah 1** di 4h dan 1d
> bahkan setelah gerbangnya lolos.

## Apa yang sudah diukur sebelumnya, dan apa yang belum

`docs/detectors_costed.json` menguji H2 pada 18 sel, XAUUSD sampai USOIL di 1h
dan 4h, dan hasilnya PASS:

| | n | exp_r |
|---|---|---|
| di atas 2,0 ATR | 15.156 | -0,0429 |
| di bawah 2,0 ATR | 8.132 | -0,1192 |
| selisih | | +0,0764, Welch t = +6,95 |

Perhatikan **kedua kohortnya negatif**. Gerbangnya memisahkan; yang
dipertahankannya tetap rugi di rig itu.

Yang belum pernah dilakukan: **sweep ambang** dan **pengujian arah**. H2 menguji
satu hipotesis lantai di satu angka. Dokumen ini menyapu tujuh ambang di kedua
arah, di enam timeframe.

## Populasi

12 sel, XAUUSD dan BTCUSD kali enam timeframe, tiap sel diadili bar halus.
Total **n = 13.309**.

Sebaran `departure_atr` berbeda tajam dari FVG, dan sebabnya struktural:
`displacement_atr` default 1,5 adalah syarat MASUK detector ini, jadi tidak ada
satu pun order block di bawah 1,5.

| | nilai |
|---|---|
| minimum di seluruh 12 sel | 1,500 |
| median | 2,14 sampai 2,31 |
| persentil 95 | 4,32 sampai 5,55 |
| pangsa di bawah 0,25 | **0,0000 di setiap sel** |
| pangsa di atas 2,0 | 0,586 sampai 0,655 |

> [!NOTE]
> Arah plafon karena itu **tidak bisa diuji** untuk order block. Tidak ada
> populasi di bawah 0,25 ATR, jadi ambang plafon di angka itu bukan gerbang, ia
> saklar mati. Grid untuk detector ini dinaikkan ke 1,0 sampai 6,0 dan setiap
> baris plafonnya keluar negatif, yang memang harusnya begitu kalau lantainya
> benar.

## Hasil gabungan

Baseline tanpa gerbang: n=13.309, exp_r **-0,0050**, t = **-0,64**. Populasi
order block secara keseluruhan datar dan tidak berbeda dari nol.

| lantai | n | exp_r | win rate | PF | mean win | mean loss | Welch t | wf | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 2,0 **terpasang** | 8.499 | +0,0281 | 55,17% | 1,086 | 0,6463 | -0,7328 | +5,79 | **7/8** | **gagal walk-forward** |
| **2,5** | 5.311 | +0,0551 | 55,66% | 1,166 | 0,6971 | -0,7507 | +6,06 | **8/8** | **lolos** |
| 3,0 | 3.391 | +0,0722 | 55,71% | 1,210 | 0,7462 | -0,7756 | +5,24 | 6/8 | gagal walk-forward |
| 4,0 | 1.511 | +0,0646 | 54,60% | 1,176 | 0,7920 | -0,8102 | +2,77 | 6/8 | tidak memisahkan |
| 6,0 | 365 | +0,1095 | 54,79% | 1,280 | 0,9140 | -0,8657 | +1,92 | 6/8 | tidak memisahkan |

Kohort di bawah gerbang, sebagai pembanding: di bawah 2,0 exp_r -0,0635 dengan
PF 0,816; di bawah 2,5 exp_r -0,0449 dengan PF 0,866.

> [!IMPORTANT]
> **Ambang 2,0 yang sedang dikirim tidak lolos aturan praregistrasi project ini
> sendiri.** Aturan itu, dari `docs/detectors_costed.json`, berbunyi "difference
> > 0 AND |welch t| > 2.24 AND cells positive >= 14 AND walk-forward 8 of 8".
> Di rig ini 2,0 memberi 7 dari 8. Hanya 2,5 yang memberi 8 dari 8.
>
> 2,5 BUKAN argmax: 3,0 punya exp_r lebih tinggi (+0,0722) dan gagal
> walk-forward 6 dari 8, dan 6,0 lebih tinggi lagi (+0,1095) dengan t di bawah
> ambang. 2,5 adalah satu-satunya yang selamat dari aturan yang ditulis
> sebelum angkanya dilihat.
>
> Ini TIDAK membatalkan pengukuran 18 sel yang lama. Rig itu memakai 12
> instrumen di 1h dan 4h; rig ini memakai 2 instrumen di enam timeframe.
> Keduanya bacaan yang berbeda, dan yang kedua menemukan 2,0 tidak selamat.

## Hasil per timeframe, dan di sinilah temuannya

| tf | n | baseline | lantai 2,0 exp_r | WR | **PF** | t | wf |
|---|---|---|---|---|---|---|---|
| 15m | 2.184 | -0,0200 | -0,0004 | 56,51% | **0,999** | +1,22 | 4/8 |
| 30m | 5.467 | +0,0439 | **+0,0854** | 59,05% | **1,255** | +4,42 | **8/8** |
| 1h | 2.714 | -0,0018 | +0,0316 | 55,96% | 1,092 | +2,58 | 6/8 |
| 4h | 2.037 | -0,0704 | **-0,0553** | 49,74% | **0,813** | +1,37 | 1/8 |
| 1d | 873 | -0,1095 | **-0,0636** | 38,76% | **0,720** | +3,18 | 1/8 |
| 1w | 34 | -0,5612 | -0,6061 | 0% | 0,000 | tidak terukur | - |

Dan pada lantai 2,5:

| tf | n kohort | exp_r | WR | PF | t | wf |
|---|---|---|---|---|---|---|
| 15m | 865 | +0,0252 | 57,11% | 1,068 | +1,76 | 4/8 |
| 30m | 2.212 | **+0,1215** | 60,17% | **1,365** | +4,69 | **8/8** |
| 1h | 1.096 | +0,0464 | 54,84% | 1,127 | +2,15 | 6/8 |
| 4h | 817 | -0,0335 | 49,57% | 0,887 | +1,89 | 3/8 |
| 1d | 317 | -0,0606 | 39,43% | 0,725 | +1,96 | 3/8 |
| 1w | 4 | -0,5462 | 0% | 0,000 | tidak terukur | - |

**Satu timeframe yang bekerja, dan itu 30m.** Di 4h dan 1d profit factor kohort
yang LOLOS gerbang tetap di bawah 1, yaitu 0,813 dan 0,720 pada lantai 2,0.
Gerbang di sana tidak menyelamatkan apa pun; ia menyaring populasi rugi menjadi
populasi rugi yang lebih kecil. Di 15m PF 0,999 adalah impas.

Ini pola yang sudah tercatat berulang di repo ini: edge yang ada berkumpul di
30m. `fvg` juga hanya terukur di 30m dan sudah membawa `measured_intervals`
untuk itu.

## Yang membedakan order block dari FVG dan IFVG

Pada gerbang plafon FVG dan IFVG, win rate **turun** saat gerbang diperketat,
karena gerbangnya menyortir kerapatan stop. Di sini kebalikannya:

| lantai | win rate |
|---|---|
| tanpa gerbang | 53,68% |
| 2,0 | 55,17% |
| 2,5 | 55,66% |
| 3,0 | 55,71% |

Win rate naik bersama gerbang, dan mean win ikut naik. Jadi gerbang order block
bukan artefak geometri stop: `departure_atr` di sini adalah impuls lima bar
yang sesungguhnya, jarak yang ditempuh harga, bukan tinggi sebuah celah.
Praregistrasi `detectors_costed.json` sudah menyatakan perbedaan besaran itu
sebelum ada yang mengukurnya.

Yang tetap harus dibaca: efeknya KECIL. exp_r +0,055 pada lantai 2,5 lawan
+0,345 milik IFVG, dengan baseline yang negatif alih-alih positif.

## Parity geometri

Dua perbandingan berbeda, dan keduanya perlu karena membuktikan hal berbeda.

**Cermin Pine lawan Python kita.** `Zonelab OB` di Pine ditulis sebagai cermin
`detect_order_block`, lalu jejak filternya dibandingkan. Ini menguji seluruh
jalur keputusan, bukan cuma koordinat kotak:

| filter | Python, MT5, 61.222 kandidat | Pine, FXCM, 31.635 kandidat |
|---|---|---|
| ditolak impuls lemah | 72,8% | 72,9% |
| ditolak bukan yang terakhir | 7,0% | 6,7% |
| digambar | 20,2% | 20,4% |

Tiga filter, dua feed, selisih di bawah 0,3 poin persen. Cerminnya setia.

**Lawan script komunitas, dan di sini hasilnya berbeda dari IFVG.** Pada
FX:XAUUSD 30m yang sama, `Order Block Detector [LuxAlgo]` memegang **6** kotak
sementara detector kita menemukan **6.440** sepanjang riwayat yang dimuat. Satu
zona beririsan di jendela harga kita, 4472,63, dan top-nya cocok persis
sementara bottom-nya tidak.

> [!WARNING]
> **KEDUA ANGKA ITU BUKAN BESARAN YANG SAMA, dan versi pertama dokumen ini
> menyajikannya seolah begitu.** 6.440 adalah jumlah yang detector kita
> DETEKSI; 6 adalah jumlah yang LuxAlgo TAMPILKAN. Script-nya protected,
> input-nya terenkripsi, dan ia tidak mengekspos tabel maupun label, jadi
> populasi yang ia deteksi tidak bisa dibaca dari luar. Pine kita sendiri
> menampilkan 40 dari 6.440 yang ia deteksi, jadi selisih tampilan sebesar itu
> memang lumrah.
>
> Yang tetap berdiri: definisinya berbeda. **Tetapi versi pertama dokumen ini
> salah menyebut BAGAIMANA ia berbeda**, dan itu dikoreksi di sini. Saya
> menulis bahwa LuxAlgo memakai order block berbasis swing. Ia tidak.
> `Order Block Detector [LuxAlgo]` memakai **volume pivot**, yaitu `ta.pivot`
> pada seri volume, tanpa syarat struktur dan tanpa syarat impuls sama sekali,
> dan box-nya digambar dari low ke median price, bukan rentang lilin. Yang
> benar benar swing-anchored adalah script LuxAlgo yang BERBEDA,
> `Smart Money Concepts (SMC)`, yang di dalamnya order block hanya bisa lahir
> di dalam blok BOS atau CHoCH.
>
> Yang kita pakai adalah definisi ICT yang diperdebatkan apa adanya: rentang
> lilin penuh plus ambang `impulse_atr`, tanpa syarat struktur, dan
> `app/detect/imbalance.py` sudah menyebut sendiri bahwa ia mewarisi definisi
> itu wholesale.
>
> Yang TIDAK bisa dijawab dari sini: mana yang lebih baik. Outcome LuxAlgo
> belum pernah diukur di rig ini, dan membandingkan PF yang ada dengan PF yang
> tidak ada bukan perbandingan. Untuk menjawabnya, definisi swing-based itu
> harus ditulis ulang di Python dan dijalankan lewat `tools/gate_sweep.py`
> seperti detector lain.

`Order Blocks Finder [TradingFinder]` tidak menggambar box yang bisa dibaca,
sama seperti versi IFVG-nya.

> [!NOTE]
> Bandingkan dengan IFVG, yang cocok 5 dari 5 persis dengan LuxAlgo. Gap adalah
> objek yang definisinya tidak punya kebebasan; order block punya, dan
> `app/detect/imbalance.py` sudah menyebut sendiri bahwa ia mewarisi definisi
> yang diperdebatkan itu wholesale. Jadi ketidakcocokan ini bukan cacat yang
> ditemukan, ia perbedaan yang sudah dinyatakan dan sekarang terukur besarnya.

## Apa yang diterapkan, dan apa yang sengaja tidak

**Lantai order block naik dari 2,0 ke 2,5.** `FLOOR_GATE_ATR` di
`app/models/zone.py` sekarang per kind: keempat formasi supply/demand tetap di
2,0 karena itu angka yang diukur untuk mereka, OB naik ke 2,5, dan BRK
mengikuti OB karena ia mewarisi `departure_atr` dari order block induknya -
membiarkannya di 2,0 akan menilainya dengan angka yang bukan milik siapa pun.

Jalur order ikut berubah, dan itu memang inti perubahannya. `tools/execute.py`
menghitung ambangnya sendiri dari dua konstanta modul sampai hari ini, jadi
lantai per kind tidak akan pernah sampai ke sana. Ia sekarang membaca
`zone.gate_cleared`, yang sudah menyandi arah dan ambang per kind.

> [!NOTE]
> Efeknya pada populasi: sebuah order block di 2,2 ATR dulu diterima dan
> sekarang ditolak. Dari 13.309 zona terukur, kohort yang bisa diorder menyusut
> dari 8.499 ke 5.311, yaitu 3.188 zona.

**Batas timeframe TIDAK dipasang.** `order_block` tetap tanpa
`measured_intervals`, jadi executor masih menerimanya di timeframe mana pun,
termasuk 4h dan 1d yang tabel di atas ukur PF 0,813 dan 0,720. Ini keputusan
pemiliknya, diambil setelah angkanya disodorkan, dan dicatat di sini supaya
tidak terbaca sebagai kelalaian. Daemon saat ini berjalan di `15m,30m`, jadi
kedua timeframe rugi itu tidak tersentuh oleh konfigurasi yang sedang jalan -
tetapi tidak ada apa pun di kode yang menahannya kalau konfigurasinya berubah.

## PF 0,985 bukan cacat kita sendirian

Dua pengukuran publik yang metodologinya bisa diperiksa mengukur konstruk yang
sama dan sampai di tempat yang sama. Dicatat di sini karena keduanya mengubah
arti angka kita: kalau seluruh keluarga ini datar, "tuning detector" punya
plafon yang harus diketahui sebelum waktu dihabiskan untuknya.

| sumber | sampel | hasil |
|---|---|---|
| StatOasis, 648 backtest SPY/QQQ/DIA/IWM | aturan OB-nya **nyaris identik dengan kita**: down-close bar dikonfirmasi impuls M x ATR20 dalam K bar, rentang bar jadi zona | OB adalah keluarga ICT terkuat di sana, mengalahkan random di 81,5 persen varian SPY, tetapi **t = +1,22** dan **0 dari 648 backtest** mengalahkan buy-and-hold |
| IndicatorEdge, EURUSD 2019-2025 | **2.553.973 bar 1 menit**, 54 varian sweep plus structure shift plus gap | win rate terbaik 56,3 persen, tetapi setelah biaya 0,5 pip **0 dari 54 varian profitable**, profit factor **0,42 sampai 0,89** |

Sumber: `statoasis.com/overfit/research/ict-backtest-what-survives`,
`indicatoredge.io/smart-money-research`.

Dua hal yang layak dibaca dari situ. Pertama, PF 0,985 kita **konsisten** dengan
satu satunya pengukuran publik yang transparan, jadi ia bukan bug implementasi.
Kedua, PF kita setelah gerbang, 1,166, ada di ATAS seluruh rentang 54 varian
IndicatorEdge. Itu bukan alasan untuk berpuas diri, karena instrumen dan
biayanya berbeda, tetapi ia menempatkan angka kita.

> [!NOTE]
> Yang TIDAK dipakai: klaim 2.600 trade dengan win rate 61 persen dan PF 2,17
> yang beredar di halaman agregator, angka "5 sampai 50 persen ROI", dan
> "62 persen win rate dengan confluence". Tidak satu pun mempublikasi kode
> maupun data. Sebuah klaim tanpa cara memeriksanya bukan pembanding.

## Dua cacat presisi, diukur pada 4.041 order block

Audit kode menyusun keduanya sebagai konstruksi; keduanya lalu diukur pada
20.000 bar XAUUSD 30m sebelum ditulis di sini.

**Impuls yang lolos hanya karena sumbu: 1.236 dari 4.041, yaitu 30,6 persen.**
Ambangnya dibaca dari `high[window].max()`, jadi satu wick di mana pun dalam
lima bar sudah cukup dan close tidak pernah harus bertahan di sana. Diuji ulang
dengan `close[window].max()`: 30,6 persen populasinya gugur.

Dan berkas itu sudah tidak konsisten dengan dirinya sendiri soal ini. Jalur
`require_structure_break` MEMBUANG event `SWEEP` dengan alasan tertulis bahwa
sumbu yang menembus level lalu ditutup kembali di dalam adalah peristiwa yang
BERLAWANAN dengan struktur yang jebol. Jalur impuls default menerima bentuk
yang persis sama sebagai bukti displacement.

**Satu impuls dilaporkan sebagai beberapa kotak: 1.196 pasangan, 29,6 persen,
dan 853 di antaranya, 21,1 persen, box-nya tumpang tindih.** Tes "LAST" hanya
memeriksa lilin BERIKUTNYA, jadi satu lilin penyela memutus jaminannya:
bearish, bearish, satu bullish kecil, bearish, lalu rally, dan kedua bearish
pertama lolos sendiri sendiri. `_present` tidak menjalankan pemeriksaan overlap
sesama family untuk detector ini.

> [!IMPORTANT]
> Konsekuensinya pada angka di dokumen ini: **n=13.309 bukan 13.309 peristiwa
> independen.** Sekitar seperlima di antaranya berbagi displacement dengan
> tetangga sesisi, jadi outcome-nya berkorelasi dan setiap interval kepercayaan
> di atas lebih sempit dari yang seharusnya. Tandanya tidak berubah; presisinya
> yang dilebih-lebihkan.

**Look-ahead: dicari dan TIDAK ditemukan.** `born = i + displacement_bars`
adalah persis bar terakhir yang `move` bergantung padanya, `scale = atr[i-1]`
kausal, dan `_finish` memulai `replay_lifecycle` di `born + 1`. Dicatat karena
riset luar menyebut ini cacat paling umum di seluruh kategori indikator SMC,
jadi ketiadaannya di sini adalah temuan, bukan kekosongan.

## Cacat yang ditemukan saat memeriksa panel

`TradePlan.departure_held_rate` tampil di UI sebagai "Departure cohort". Untuk
kind lantai ia diisi `HELD_CLEARED_GATE` 0,430 atau `HELD_BELOW_GATE` 0,402,
dan kedua angka itu diukur pada **supply/demand**, di 5 instrumen 1 jam. Sebuah
zona OB atau BRK karena itu memajang angka kohort milik detector lain, persis
bentuk cacat yang ditemukan pada IFVG sehari sebelumnya di sisi plafon.

Peringatan teks di `plan.py` membawa angka yang sama: sebuah OB antara 1,5 dan
2,0 ATR mencetak "cuma bertahan 40,2%, lawan 43,0% yang melewatinya".

Dan cacatnya lebih dalam dari itu. Field yang sama membawa **besaran yang
berbeda** tergantung kind: survival rate untuk kind lantai, dan EKSPEKTASI
DALAM R untuk kind plafon sejak recalibration FVG menaruh
`EXP_R_CLEARED_CEILING` di sana. Panel merendernya lewat `pct()` di bawah label
"Departure cohort", jadi ekspektasi +0,190 R tampil sebagai **"19,0%"
bertahan**. Dua besaran, satu label, satu satuan.

`departure_held_rate` sekarang berarti satu hal saja, yaitu survival rate, dan
`None` di setiap kind yang tidak punya survival rate-nya sendiri: FVG, IFVG, OB
dan BRK. Panel menghilangkan barisnya di situ. Angka kohort keempatnya tetap
ada di peringatan PLAN, lengkap dengan satuan R-nya.

## Satu harness yang merah karena mesin, bukan karena kode

`e2e/clickthrough.mjs` gagal pada 6 September 2026 di baris "nol request API
yang gagal", dengan dua `net::ERR_ABORTED` pada `POST /api/draw`. Setiap check
fungsional lainnya lolos: 21 dari 21 saklar layer, 41 disclosure, 16 slider,
4 select, nol pageerror.

`ERR_ABORTED` bukan request yang gagal, ia request yang aplikasi ini SENDIRI
batalkan. Harness itu mengklik 21 saklar berturut-turut dan tiap klik memicu
satu draw; fetch yang tersalip dibatalkan, dan itu perilaku yang benar. Apakah
pembatalannya sempat terjadi bergantung pada beban mesin.

Dibuktikan bukan regresi dengan `git stash`: harness yang sama merah di HEAD,
yaitu kode yang tiga jam sebelumnya hijau. Handler `requestfailed` sekarang
mengecualikan `net::ERR_ABORTED` saja, dengan alasannya ditulis di tempat.
Dibuktikan tetap mengikat dengan menyuntikkan `RuntimeError` ke `/api/draw`:
harness menangkapnya sebagai `net::ERR_FAILED` dan gagal.

## Sapuan aturan deteksi, 6 September 2026

Gerbang menaikkan profit factor dari 0,985 ke 1,166, jadi detector-nya sendiri
tidak menghasilkan edge dan penyaringnya yang menghasilkan. Pertanyaan
berikutnya karena itu bukan "ambang mana" melainkan **aturan deteksinya yang
mana yang salah**, dan itu belum pernah disapu satu kali pun.

`tools/ob_variants.py`, dua sel 30m yang sama dengan `tools/fvg_filter_compare.py`.
Dipatok di 30m karena tabel di atas menunjukkan hanya di situ baseline OB ada di
atas PF 1; menyapu varian di timeframe yang baselinenya rugi berarti mengukur
mana yang paling sedikit rugi.

Aturan lulus ditulis sebelum angkanya dilihat: exp_r lebih tinggi dari baseline
DAN walk-forward 8 dari 8 DAN `|t|` Welch melewati Bonferroni 2,8653.

| varian | n | exp_r | win rate | PF | wf | t | verdict |
|---|---|---|---|---|---|---|---|
| A baseline | 5.468 | +0,0437 | 57,81% | 1,128 | 7/8 | - | - |
| B1 `displacement_atr` 1,0 | 8.326 | -0,0370 | 55,56% | **0,889** | 1/8 | -4,96 | merusak |
| B2 `displacement_atr` 2,0 | 3.504 | +0,0887 | 54,91% | 1,232 | 8/8 | +1,94 | tidak signifikan |
| B3 `displacement_atr` 2,5 | 2.199 | +0,1033 | 50,34% | 1,235 | 8/8 | +1,94 | tidak signifikan |
| B4 `displacement_atr` 3,0 | 1.422 | +0,1306 | 47,33% | 1,273 | 6/8 | +2,12 | gagal wf |
| C1 `displacement_bars` 3 | 3.931 | +0,0317 | 55,00% | 1,084 | 6/8 | -0,56 | tidak lebih baik |
| C2 `displacement_bars` 8 | 6.778 | +0,0405 | 57,49% | 1,121 | 6/8 | -0,18 | tidak lebih baik |
| D `require_structure_break` | 1.531 | +0,0039 | 39,39% | **1,007** | 4/8 | -0,99 | tidak lebih baik |
| E body-box | 4.644 | +0,1678 | 48,00% | 1,351 | 8/8 | **+4,66** | **LOLOS** |
| E+D body-box + structure | 1.263 | +0,2394 | 30,72% | 1,354 | 8/8 | +2,72 | tidak signifikan |
| F impuls dari close | 3.769 | +0,1115 | 57,12% | 1,306 | 8/8 | **+3,04** | **LOLOS** |
| G satu block per impuls | 2.972 | -0,0843 | 47,14% | **0,813** | 1/8 | -5,43 | **merusak** |
| H E+F+G | 2.087 | +0,0996 | 39,29% | 1,174 | 7/8 | +1,37 | gagal |
| **I E+F** | **3.228** | **+0,2057** | 44,21% | **1,392** | **8/8** | **+4,85** | **LOLOS, terbaik** |
| J midpoint entry + F | 3.382 | +0,1522 | 40,39% | 1,266 | 8/8 | - | kalah dari I |

### Dugaan yang gugur, dan itu bagian paling berharga

**G merusak, padahal ia dibangun DI ATAS cacat terukur.** 21,1 persen box
tumpang tindih dengan tetangga sesisi dari impuls yang sama, jadi menyimpan
satu saja terdengar jelas benar. Terukur: PF 0,813, walk-forward 1 dari 8,
t=-5,43. Sebabnya bisa dinamai. "Lilin berlawanan TERAKHIR" adalah yang paling
dekat ke impuls, jadi entry-nya paling dangkal; block yang lebih awal punya
harga masuk yang lebih baik. **Aturan doktrin itu, diterapkan ketat, membuang
kotak yang lebih baik**, dan perilaku longgar engine ini tidak sengaja
menyimpan yang benar.

Dan H gagal KARENA membawa G, bukan karena E+F buruk. Sapuan pertama tidak
pernah menguji E+F berpasangan - hanya E+F+G - jadi selnya hilang. Itu cacat di
rancangan sapuan, dan I ditambahkan untuk menutupnya.

**`require_structure_break` diukur lawan outcome untuk pertama kalinya, dan ia
tidak membeli apa-apa.** PF 1,007, walk-forward 4 dari 8, win rate ambruk ke
39,39 persen. Ditambahkan ke body-box ia menaikkan PF dari 1,351 ke 1,354
sambil memangkas populasi 73 persen. Ini aturan yang paling banyak
diperdebatkan di literatur ICT dan satu satunya yang LuxAlgo SMC jadikan wajib
secara struktural.

**Menurunkan ambang masuk merusak.** `displacement_atr` 1,0 memberi PF 0,889
dengan walk-forward 1 dari 8, jadi 1,5 yang sekarang bukan angka sembarangan.

**Jendela impuls tidak mengikat.** 3 dan 8 bar memberi PF 1,084 dan 1,121 lawan
baseline 1,128, keduanya gagal walk-forward.

### E dan F membaik lewat mekanisme yang BERBEDA

Ini yang menentukan cara membacanya, dan angkanya memisahkan keduanya dengan
bersih:

| | win rate | PF |
|---|---|---|
| baseline | 57,81% | 1,128 |
| F impuls dari close | **57,12%** | 1,306 |
| E body-box | **48,00%** | 1,351 |

**F hampir tidak menggerakkan win rate sambil menaikkan PF.** Itu tanda tangan
filter yang sungguhan: ia membuang trade yang memang rugi tanpa merusak hit
rate. F adalah temuan yang lebih bermakna dari keduanya.

**E menaikkan PF lewat win rate yang TURUN 9,8 poin.** Box lebih pendek berarti
stop lebih rapat, jadi harga lebih sering menyentuhnya sementara tiap
kemenangan bernilai R jauh lebih besar. Mekanisme yang sama persis dengan
gerbang plafon FVG dan IFVG. Ini perbaikan geometri risiko, bukan prediksi yang
lebih benar.

**Dan J memisahkan keduanya lebih jauh.** Entry di tengah badan dengan stop
tetap di luar sumbu memberi PF 1,266, di bawah I. Jadi keuntungan body-box
datang dari STOP yang menyempit, bukan dari entry yang lebih dalam. Riset luar
menyebut perbandingan geometri box ini tidak pernah diukur satu sumber pun; ini
angkanya.

### Yang belum diputuskan

Varian I belum diterapkan. Ia diukur di dua sel 30m, sementara gerbang di
dokumen ini diukur di dua belas. Run 12 sel untuk A, E, F dan I sedang berjalan
supaya keduanya sebanding dan supaya terlihat apakah body-box menyelamatkan 4h
dan 1d yang PF-nya 0,813 dan 0,720. Tidak ada kode detector yang berubah sampai
angka itu masuk.

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.gate_sweep --detector order_block
```

Baris hasil resolusi bar halus di-cache per detector di
`docs/order_block_rows_cache.json`, jadi run kedua menjawab dalam hitungan
detik.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

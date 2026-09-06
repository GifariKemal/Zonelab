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
> Yang tetap berdiri: definisinya berbeda, dan itu dinyatakan bukan
> disimpulkan. LuxAlgo memakai order block berbasis swing; kita memakai
> definisi ICT yang diperdebatkan apa adanya, yaitu rentang lilin penuh plus
> ambang `impulse_atr` tanpa syarat struktur, dan
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

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.gate_sweep --detector order_block
```

Baris hasil resolusi bar halus di-cache per detector di
`docs/order_block_rows_cache.json`, jadi run kedua menjawab dalam hitungan
detik.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

# Breakout di MT5, dan dua rig yang akhirnya sepakat

Ditulis 3 September 2026. Isinya pengukuran breakout di MT5 Strategy Tester
dengan real tick, plus drawing-nya yang sebelumnya cuma satu huruf.

> [!IMPORTANT]
> Semua angka di file ini dari run yang benar benar dijalankan, `History
> Quality: 100% real ticks`, periode 2026.01.01 sampai 2026.08.31, deposit
> 10.000. Yang belum diukur ditulis belum diukur.

## Ringkasan

| Yang diminta | Status |
|---|---|
| Drawing breakout | Sebelumnya satu huruf. Sekarang empat bentuk |
| Backtest MT5 | 7 sel arm 0, plus 3 arm varian, total 7.847 trade |
| Kesepakatan lintas-rig | Dump parity: 654 event, nol mismatch di lima kolom |
| Verdict | Null, dan tiap varian yang metodenya resepkan MEMPERBURUK |

## Drawing: satu bentuk jadi empat

`wyckoff-primitive.ts` sebelumnya menggambar **hanya tag** di bar tempat fase
tercetak: `SOS`, `SOW`, `SPR`, `UT`. Range yang dipecah tidak digambar, level
yang dipecah tidak diperpanjang, retest tidak ada. Seorang pembaca yang melihat
`SOS` tidak bisa melihat range APA yang ditembus.

Empat bentuk sekarang, dan tiap satu dibatasi:

1. **Range yang sedang berjalan**, satu box, putus putus, tanpa fill. SATU,
   bukan satu per fase: pada lookback 20 sebuah deret 500 bar menghasilkan
   ratusan fase, dan catatan ink budget di `globals.css` mengukur bahwa melewati
   sekitar sepertiga chart box berhenti menganotasi harga dan jadi
   background-nya. Terukur di API: 117 fase di 400 bar synthetic.
2. **Level yang dipecah**, diperpanjang ke depan dari bar event, berhenti di
   retest-nya. Ray yang berjalan selamanya menumpuk sampai chart jadi kisi.
3. **Tag**-nya, seperti sebelumnya.
4. **Retest**, tick vertikal terpisah di bar yang menyentuh level itu kembali.

Dua field baru dari backend supaya frontend tidak menghitung ulang: `tr_from`
(awal window range) dan `retested_at`. Menghitung retest di frontend akan
menaruh analisis kedua di tempat yang tidak punya deretnya.

### Kenapa retest digambar TERPISAH

Bukan pilihan tata letak. Bulkowski mengukur 8.765 pattern breakout turun:
pullback terjadi 58 persen dari waktu, dan sesudah harga balik ke breakout price
hasilnya 53 lawan 47. Lebih tajam, **97 persen tipe pattern dengan breakout naik
perform LEBIH BAIK TANPA throwback**. Konfirmasi independen: ORB pullback entry
di MNQ stop-out 80,7 persen, n=83.

Jadi menggambar retest sebagai bagian dari breakout akan menyandikan asumsi yang
datanya tolak. Ia objek sendiri yang kebetulan sering hadir: 109 dari 117 fase di
run synthetic punya retest.

## Volume: tidak ada di sumber ini

Kedua deskripsi metode breakout menuntut konfirmasi volume sebagai bukti
partisipasi institusi. Volume itu **tidak ada**.

Diukur langsung dari terminal, `real_volume` per 200 bar M30:

| simbol | real_volume total | tick_volume median |
|---|---|---|
| XAUUSD | 0 | 5.909 |
| XAGUSD | 0 | 1.574 |
| EURUSD | 0 | 703 |
| GBPUSD | 0 | 1.050 |
| USDJPY | 0 | 1.073 |
| US30 | 0 | 2.412 |
| USOIL | 0 | 3.700 |
| BTCUSD | 0 | 2.340 |

Nol di kedelapan instrumen yang broker ini layani, karena broker tidak punya
book untuk dilaporkan. Yang tersisa hitungan tick, yaitu seberapa sering feed
broker memperbarui, dan itu besaran berbeda serta berbeda antar broker.

Arm filternya tetap dibuat supaya bisa diukur, tapi namanya `InpTickMult` dan
counter-nya `skipped tick`. Ia tidak menyebut volume, karena ia tidak menghitung
volume.

## Port MQL5, dan apakah ia setia

`WyckoffDetector.mqh` port setia dari `app/wyckoff.py`. Urutan pemeriksaannya
disalin apa adanya: sweep yang ditolak diperiksa LEBIH DULU, karena close yang
balik ke dalam range bukan break atas range itu. Membalik urutannya akan
mengklasifikasikan setiap spring sebagai `sow`.

Diperiksa lawan Python di periode dan simbol yang sama, XAUUSD M30:

| | Python | MT5 |
|---|---|---|
| bar di jendela | 7.839 | 7.793 detect call |
| event fade, spring plus upthrust | **895** | **892** armed |
| event break, sos plus sow | **774** | 764 order ditempatkan |

Selisih 0,34 persen di sisi fade dan 1,3 persen di sisi break. Sisanya
terjelaskan: EA butuh warm-up `InpBars` jadi tester mulai sesudah jendela
dibuka, dan fase di bar terakhir run tidak dapat order sebelum test berakhir.

**Ini kesepakatan lintas-rig pertama di repo ini.** Sebelumnya
`docs/mt5_python_parity.json` mencatat kedua rig tidak sepakat TANDANYA di 6
dari 8 sel. Itu sebabnya port ini dikerjakan meski rig Python sudah null: null
di Python pada resolusi bar tidak menyelesaikan apa yang MT5 katakan dengan real
tick dan biaya terminal, dan rig Python tidak menguji EKSEKUSI sama sekali.

Yang BELUM diukur: perbandingan baris demi baris nilai `level`, `tr_low`,
`tr_high` per event. Yang di atas mencocokkan JUMLAH, bukan tiap harga.

## Arm 0, breakout agresif, tujuh sel

Entry market di bar sesudah close menembus tepi range. Stop di level yang
ditembus dikurangi 0,25 ATR. Target 2R. Risk 1 persen ekuitas.

| sel | PF | trade | payoff | win% | max DD |
|---|---|---|---|---|---|
| XAUUSD H4 | **1,34** | 129 | +20,36 | 41,86% | 25,3% |
| BTCUSD H1 | 1,03 | 503 | +2,20 | 34,99% | 27,2% |
| BTCUSD H4 | 1,01 | 130 | +0,46 | 34,62% | - |
| XAUUSD M30 | 1,00 | 764 | +0,25 | 34,29% | 30,6% |
| XAUUSD M15 | 0,99 | 1.630 | -0,65 | 33,62% | 51,2% |
| XAUUSD H1 | 0,98 | 402 | -1,38 | 33,33% | 25,3% |
| BTCUSD M15 | **0,79** | 2.042 | -4,70 | 28,99% | **96,5%** |

**5.600 trade.** Tanda PF-nya 3 naik, 3 turun, 1 rata di 1,00. Lempar koin.

Yang paling bersih dibaca kolom win rate. Target 2R berarti breakeven di 33,33
persen, dan lima dari tujuh sel mendarat di 33,33 sampai 34,99 persen, yaitu
**tepat di garis breakeven-nya sendiri**. Sistem ini membayar spread untuk
berdiri di tempat.

### Sel 1,34 itu tidak bereplikasi

XAUUSD H4 keluar PF 1,34 dengan 41,86 persen win di 129 trade. Dihitung: standard
error pada base rate 33,33 persen di n=129 adalah 4,15 persen, jadi 41,86 persen
itu **2,06 standard error** di atas breakeven. Tidak terkoreksi p sekitar 0,04
satu sisi; dengan tujuh sel bar Bonferroni-nya sekitar 2,6 sampai 2,9 SE, jadi
ia **tidak lolos**.

Dan uji replikasinya langsung: BTCUSD di timeframe yang SAMA keluar **1,01**
dengan 34,62 persen di 130 trade. Sel H4 XAUUSD tidak bereplikasi.

### BTCUSD M15 didominasi biaya

PF 0,79 dengan drawdown 96,5 persen di 2.042 trade adalah sel dengan trade
terbanyak di instrumen berspread tertinggi pada timeframe terhalus. Itu konsisten
dengan catatan biaya yang sudah ada: profit absolut ditentukan biaya instrumen,
bukan margin atas placebo.

## Tiga varian, dan ketiganya memperburuk

Semua di XAUUSD M30, sel yang sama dengan arm 0 supaya perbandingannya bersih.

| arm | apa | PF | trade | payoff | win% | Sharpe | max DD |
|---|---|---|---|---|---|---|---|
| 0 agresif | masuk di break | **1,00** | 764 | +0,25 | 34,29% | 0,09 | 30,6% |
| 1 retest | limit di level yang ditembus | **0,96** | 591 | -2,79 | 32,66% | **-4,06** | 37,6% |
| 2 tick | break plus tick >= 1,5x median | **0,99** | 372 | -0,87 | 33,87% | -0,27 | 21,9% |
| 3 fade | spring dibeli, upthrust dijual | **0,89** | 883 | -5,78 | 31,71% | -2,74 | **64,3%** |

Ketiganya lebih buruk dari arm 0, dan ketiganya adalah hal yang metodenya
resepkan:

**Retest, varian "konservatif".** 0,96 lawan 1,00, dan Sharpe -4,06 yang
terburuk dari keempatnya. Ini mereproduksi dua pengukuran independen di
literatur: Bulkowski 97 persen tipe pattern lebih baik tanpa throwback, dan ORB
pullback entry stop-out 80,7 persen.

**Filter hitungan tick.** 0,99 lawan 1,00, dan ia memotong trade dari 764 ke
372. Jadi separuh sinyalnya dibuang untuk hasil yang sedikit lebih buruk.
Konsisten arah dengan Bulkowski: volume tinggi di bar break membuat failure
TRIPLE dan pullback 66 persen lawan baseline 58 persen.

**Fade the fakeout.** 0,89, terburuk, dengan drawdown 64,3 persen di 883 trade.
Ini arm yang framing ICT prediksi paling kuat: institusi mendorong harga
melewati batas untuk menyapu stop lalu membalikkannya. Diukur, ia arm terburuk
dari keempatnya. Konsisten dengan Mesfin (2026) di MNQ: liquidity grab, fade
T=-14,12 dan follow T=-13,24 di 6.442 event, kedua arah signifikan negatif.

## Dump parity: presisi deteksi, baris demi baris

Bagian sebelumnya mencocokkan JUMLAH event, 895 lawan 892 atas 7.839 bar. Itu
menjawab "apakah detektornya menyala sebanyak yang sama", bukan "apakah ia
menyala di bar yang sama dengan harga yang sama".

Yang menutup itu `zonelab_parity_wyckoff.csv`, ditulis `ZonelabParityDump.mq5`
di dalam terminal bersama BAR yang dipakainya, jadi Python tidak menebak
window-nya. Selisih apa pun sesudah itu murni logika detektor.

Terukur, XAUUSD M30, 3000 bar:

| | Python | MQL5 |
|---|---|---|
| event total | 654 | 654 |
| spring | 198 | 198 |
| upthrust | 151 | 151 |
| sos | 165 | 165 |
| sow | 140 | 140 |

Nol mismatch pada `index`, `kind`, `level`, `tr_low`, `tr_high`, plus invarian
lebar window. Seluruh run `mqh_parity` keluar `TOTAL MISMATCH: 0`.

### Keempat angka dibandingkan, dan itu bukan kelengkapan

`level` selalu SALAH SATU dari kedua tepi range. Jadi membandingkan `level`
saja akan lolos secara hampa kalau MQL5 menghitung window range-nya dari bar
yang berbeda: kedua sisi sepakat soal `level` sementara `tr_low` dan
`tr_high`-nya berasal dari jendela yang tidak sama.

Dibuktikan dengan suntikan. Loop window di `WyckoffDetector.mqh` diubah
berhenti satu bar lebih awal, lalu dump-nya dijalankan ulang:

```
Python  : 654
MQL5    : 724
  spring    py   198  mq   157   MISMATCH
  upthrust  py   151  mq   107   MISMATCH
  sos       py   165  mq   235   MISMATCH
  sow       py   140  mq   225   MISMATCH
MISMATCH #2 bar 40:
  level 4522.585 != 4520.896
  tr_high 4522.585 != 4520.896
MISMATCH #3 bar 46:
  kind upthrust != sos
TOTAL MISMATCH: 650
```

Bar 40 itu buktinya: `index` dan `kind` SAMA di kedua sisi, dan yang berbeda
`level` plus `tr_high`. Sebuah pemeriksaan jumlah-saja akan melewatkannya. Dan
bar 46 memperlihatkan konsekuensi yang lebih buruk: window yang bergeser satu
bar mengubah KLASIFIKASINYA, upthrust jadi sos, yaitu false breakout terbaca
sebagai breakout.

### Dua kolom yang sengaja TIDAK dibandingkan

`ticks` tidak dibandingkan. Python membaca `volume` lewat provider yang memilih
`real_volume or tick_volume`; MQL5 membaca `iVolume` langsung dari terminal.
Keduanya boleh berbeda tanpa ada yang salah, dan menuntutnya sama akan membuat
komparator merah karena dua definisi yang keduanya benar. Ia ditulis supaya arm
filter di `ZonelabWYK.mq5` bisa diaudit.

`tr_from` tidak dibandingkan sebagai indeks absolut, karena kedua sisi
menurunkannya dari `at - lookback`. Ia diperiksa sebagai INVARIAN lebar
window, bukan sebagai nilai yang dicocokkan.

### `wyckoff` keluar dari UNPORTED

`tools/mqh_parity.py` mencatatnya UNPORTED sampai 3 September 2026 dengan
alasan "measured null, bukan family ICT". Kedua bagian alasan itu benar; yang
salah kesimpulannya. Null di rig Python pada resolusi bar tidak menyelesaikan
apa yang MT5 katakan dengan real tick, dan rig Python tidak menguji eksekusi
sama sekali.

Sekarang ia di `PORTED_WYCKOFF`, bentuk kedelapan, dan satu satunya layer yang
punya EA Strategy Tester DAN dump parity.

## Total yang diukur

7 sel arm 0 (5.600 trade) plus 3 arm varian di M30 (1.846 trade) plus arm 0 M30
yang dihitung di keduanya. **7.847 trade real tick.**

Ditambah rig Python yang sudah ada: `docs/wyckoff_outcomes.json`, keempat fase
lawan drift instrumennya sendiri di sembilan instrumen, `sos` n=19.667 t=-0,95
dengan 13 dari 36 fold positif, di bawah kebetulan.

## Cacat tool yang ikut ketemu

`read_counters` di `tools/mt5_backtest.py` mengembalikan `{}` untuk keempat arm
pertama. Counter-nya ADA di log agent, diperiksa langsung: `phases armed: 892`,
`orders placed: 883`.

Sebabnya decode. Log MT5 UTF-16LE, dua byte per karakter, dan `read_counters`
membaca DELTA dari offset ukuran sebelumnya. Sebuah delta yang mulai di offset
**ganjil** menggeser setiap karakter satu byte, decode-nya mengembalikan sampah
tanpa error, lalu fallback UTF-8 juga tidak menemukan nama apa pun. Hasilnya
terbaca "EA tidak mencetak apa pun".

Konsekuensinya bukan kosmetik: sebuah sel yang detektornya MATI dan sebuah sel
yang detektornya bekerja lalu tidak menemukan apa pun terlihat sama di report
Strategy Tester, dan counter itu satu satunya yang membedakan keduanya.

Diperbaiki dengan menggenapkan offset ke bawah, plus enam nama counter baru
didaftarkan. Terverifikasi di sel berikutnya: keduabelas counter kembali,
`phases_armed 129` sama dengan `orders_placed 129`.

## Yang belum diukur

- **Perbandingan parity di timeframe dan simbol LAIN.** Dump-nya dijalankan di
  XAUUSD M30 saja, 654 event. Detektornya tidak punya cabang per simbol, jadi
  tidak ada alasan menduga ia berbeda di tempat lain, tapi itu dugaan dan belum
  diukur.
- **Walk-forward per sel.** `--forward` ada di tool-nya dan belum dipakai untuk
  EA ini.
- **Compression gate.** Masih arah yang belum tersentuh dan punya sisi bukti;
  lihat `docs/BACKLOG.md` bagian 3d.
- **Arm 1 dengan umur limit selain 10 bar.** `InpRetestBars` belum disapu.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

# Praregistrasi eksekusi, 22 Agustus 2026

Ditulis **sebelum** satu angka pun dihitung untuk dua aturan di bawah. Itu
satu-satunya hal yang membuat hasilnya layak dipercaya nanti.

## 1. Kenapa pertanyaannya soal eksekusi, bukan soal sinyal

`QA-QUANT.md` bagian 6 menemukan bahwa gerbang departure **menyortir** dengan
selisih +0,124 R (Welch t = +4,82, positif di 7 dari 7 sel) sementara sisi
atasnya cuma break-even, +0,0214 R dengan CI95 [-0,024, +0,067].

`blind_gate` dengan objektif ekspektasi lalu memeriksa apakah ambang yang lebih
ketat memperbaikinya. Tidak. Dipilih blind di paruh pertama ia mendarat di 2,5
ATR, dan kohort atas di seluruh grid 0,5 sampai 6,0 ATR bergerak antara -0,070
dan +0,016 R; mulai 3,5 ATR ia negatif. Jadi sinyalnya sudah dipakai habis.

Yang belum dipakai habis adalah **eksekusinya**, dan dua angka menunjukkan ke
mana:

1. Entry terisi setelah median 4 sampai 8 bar halus dari awal bar besar, jadi
   harga masuk bukan harga di awal bar. Limit yang lebih dalam mengubah harga itu.
2. 35,9% trade yang KALAH pernah di atas +1 R sebelum berbalik (27,1% di EURUSD,
   42,6% di BTCUSD 4 jam).

## 2. Dua aturan, dan hanya dua

> [!IMPORTANT]
> Satu nilai per aturan, bukan sapuan. Menguji banyak nilai di data yang sama
> adalah cara tercepat menemukan yang palsu, dan project ini sudah pernah
> mengirim satu komposit yang memeringkat terbalik dengan AUC 0,464.

### Aturan A: entry di ekuilibrium zona

Entry dipindah dari proximal ke **50% tinggi zona**, yaitu titik tengah antara
proximal dan distal. Stop tetap di distal plus buffer 0,25 ATR.

Nilai 0,5 dipilih karena ia konsep bernama di metodenya sendiri (ekuilibrium
zona), bukan karena ia terlihat bagus di data. Tidak ada 0,25 dan tidak ada 0,75
yang ikut diuji.

Konsekuensi yang harus ikut diukur, bukan disembunyikan:

- **Fill rate turun.** Harga bisa menyentuh proximal dan berbalik tanpa pernah
  mencapai titik tengah. Limit yang tidak terisi BUKAN trade, dan menghitungnya
  sebagai nol adalah cara backtest mencuri. Yang dilaporkan: berapa persen zona
  yang tersentuh proximal-nya benar-benar mengisi entry yang lebih dalam.
- **Risk per unit menyusut**, jadi satuan R berubah. Perbandingan dilakukan pada
  ekspektasi R dan juga pada total R, karena R yang lebih kecil bisa menaikkan
  ekspektasi tanpa menaikkan uang.

### Aturan B: stop ke breakeven setelah +1 R

Begitu excursion menguntungkan mencapai +1,0 R, stop dipindah ke harga entry.
Ambang 1,0 R dipilih karena ia satuan alaminya, bukan karena disetel.

Konsekuensi yang harus ikut diukur:

- **Pemenang bisa berubah jadi scratch.** Trade yang menyentuh +1 R, mundur ke
  entry, lalu naik lagi ke target akan berakhir nol alih-alih menang.
- Yang dilaporkan: berapa banyak yang kalah berubah jadi scratch, dan berapa
  banyak yang menang berubah jadi scratch. Selisih keduanya yang menentukan.

## 3. Populasi, tidak berubah

Sama dengan `QA-QUANT.md` bagian 6, karena kalau populasinya berubah maka
perbandingannya tidak sah:

| Hal | Nilai |
|---|---|
| Instrumen | XAUUSD, EURUSD, GBPUSD, AUDUSD, BTCUSD |
| Timeframe zona | 1 jam |
| Penyelesaian | bar 5 menit, entry diisi di bar halus |
| Populasi | first touch zona yang `departure_atr >= 2.0` |
| Biaya | `exness_raw`, per instrumen, dari terminal |
| Exit | flat di rollover 21:00 UTC |
| Baseline | entry di proximal, tanpa breakeven |

## 4. Ambang, ditetapkan sekarang

Sebuah aturan hanya dilaporkan sebagai perbaikan kalau **ketiganya** lolos:

1. **Ukuran sampel.** Minimal 300 trade terisi. Di bawah itu dicetak dengan
   n-nya dan tidak dinilai.
2. **Signifikansi berpasangan.** Selisih ekspektasi terhadap baseline harus
   melewati `|t| > 2,24`, yaitu alpha 0,05 dibagi 2 aturan (Bonferroni), diuji
   pada trade yang SAMA sehingga variansi antar-trade tidak ikut dihitung.
3. **Tanda konsisten.** Selisihnya bertanda sama di minimal 4 dari 5 instrumen.

Aturan yang lolos ketiganya mendapat walk-forward pada subpopulasinya. Ia tidak
langsung mendapat tempat di `app/plan.py`.

## 5. Yang tidak akan dilakukan

- **Tidak menggabungkan A dan B** sebelum keduanya dinilai sendiri. Kalau
  gabungannya diuji lebih dulu, dua aturan yang saling menutupi kelemahan akan
  terbaca sebagai satu penemuan.
- **Tidak menambah nilai** setelah melihat hasil. Nilai baru berarti
  praregistrasi baru dengan tanggal baru.
- **Tidak membuang limit yang tidak terisi.** Fill rate dilaporkan apa adanya.
- **Tidak mengklaim arah.** Kedua aturan mengubah eksekusi pada populasi yang
  arahnya sudah ditentukan sisi zona.

---

## 6. Hasil, 22 Agustus 2026

Kedua aturan **ditolak**, dan alasannya berbeda.

### Aturan B ditolak di ambangnya sendiri

| Sel | n | baseline | aturan B | selisih | t berpasangan |
|---|---|---|---|---|---|
| XAUUSD | 224 | +0,156 | +0,139 | -0,017 | -0,52 |
| EURUSD | 234 | -0,073 | -0,089 | -0,015 | -0,67 |
| GBPUSD | 261 | +0,122 | +0,110 | -0,012 | -0,48 |
| AUDUSD | 258 | -0,044 | -0,027 | +0,016 | +1,13 |
| BTCUSD | 214 | -0,003 | -0,052 | -0,049 | -1,24 |
| **Gabung** | **1191** | **+0,032** | **+0,018** | **-0,014** | **-1,15** |

Ambang 2: `|t| > 2,24` **gagal**. Ambang 3: tanda positif hanya di 1 dari 5 sel,
**gagal**.

Mekanismenya terlihat, dan ia menjelaskan kenapa. Hanya 17,0% trade yang stop-nya
benar-benar sampai dipindah, dan di antara yang dipindah: **12 yang kalah berubah
jadi scratch, 8 yang menang berubah jadi scratch.** Hampir seimbang dalam
hitungan, dan yang menang lebih besar nilainya dari yang kalah, jadi tukarannya
merugikan. Angka 35,9% yang kalah pernah di atas +1 R itu benar; yang salah adalah
kesimpulan bahwa memindah stop bisa menangkapnya tanpa membayar.

### Aturan A lolos ketiga ambang dan tetap ditolak

| Sel | n terisi | fill rate | baseline pada yang terisi | aturan A | selisih | t berpasangan |
|---|---|---|---|---|---|---|
| XAUUSD | 156 | 69,6% | -0,137 | +0,056 | +0,193 | +3,13 |
| EURUSD | 180 | 76,9% | -0,240 | -0,128 | +0,112 | +2,02 |
| GBPUSD | 185 | 70,9% | -0,102 | +0,037 | +0,139 | +2,12 |
| AUDUSD | 208 | 80,6% | -0,223 | -0,042 | +0,181 | +3,43 |
| BTCUSD | 160 | 74,8% | -0,206 | +0,056 | +0,262 | +4,14 |
| **Gabung** | **889** | **74,6%** | **-0,183** | **-0,008** | **+0,175** | **+6,56** |

Ketiga ambang lolos: n=889, `|t|`=6,56, dan tanda positif di 5 dari 5 sel.

**Dan ia tetap ditolak, karena ambang 2 mengukur populasi yang salah.** Uji
berpasangan hanya melihat trade yang TERISI. Keputusan yang sebenarnya dibuat per
PELUANG, dan limit yang tidak terisi tetap peluang yang dilewatkan:

| Sel | peluang | baseline per peluang | aturan A per peluang |
|---|---|---|---|
| XAUUSD | 224 | +0,1564 | +0,0390 |
| EURUSD | 234 | -0,0732 | -0,0985 |
| GBPUSD | 261 | +0,1217 | +0,0262 |
| AUDUSD | 258 | -0,0438 | -0,0340 |
| BTCUSD | 214 | -0,0033 | +0,0422 |
| **Gabung** | **1191** | **+0,0316** | **-0,0061** |

Total R: baseline +37,7 dan aturan A -7,2 atas peluang yang sama.

Sebabnya bisa dinyatakan: zona yang mengisi limit 50% adalah zona yang harganya
bergerak **lebih jauh melawan**. Baseline pada subset itu -0,183 R sementara
baseline pada seluruh populasi +0,032 R. Jadi aturan A memperbaiki subset yang
buruk dan kehilangan 25,4% peluang yang justru lebih baik. Memperbaiki sesuatu
yang buruk bukan hal yang sama dengan menghasilkan uang.

> [!IMPORTANT]
> Ambang 2 di bagian 4 dokumen ini **salah dirancang**, dan itu dicatat di sini
> alih-alih diperbaiki di atas. Uji berpasangan pada trade yang terisi adalah uji
> yang benar untuk pertanyaan "apakah harga entry-nya lebih baik" dan uji yang
> salah untuk pertanyaan "apakah saya harus memakainya". Praregistrasi berikutnya
> yang mengubah fill rate harus menetapkan ambangnya PER PELUANG.

### Yang tersisa

Sinyalnya sudah dipakai habis (gerbang tidak bisa diperketat), dan dua perbaikan
eksekusi yang paling jelas sudah diuji dan ditolak. Ekspektasi jujurnya tetap
+0,032 R per peluang pada sampel ini, dengan CI95 yang memuat nol.

---

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

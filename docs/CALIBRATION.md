# Kalibrasi

Diukur 2026-08-13 dengan `python -m tools.calibrate --bars 20000`. Angka mentahnya
ada di [`calibration.json`](calibration.json). Jalankan ulang untuk mereproduksi;
riwayat di-cache ke disk sehingga hasilnya sama pada setiap kali jalan.

> [!IMPORTANT]
> Ringkasan satu kalimat: **deteksi zonanya tervalidasi, peringkat kualitasnya
> tidak.** Zona yang digambar bertahan jauh lebih sering daripada level acak dan
> lebih sering daripada formasi yang ditolak gerbang, tetapi di antara zona yang
> lolos, tidak ada faktor yang bisa membedakan mana yang akan bertahan.

## Pertanyaan yang diukur

Ketika harga kembali ke sebuah zona untuk pertama kali, apakah zona itu bertahan?
Dan apakah skor bisa memisahkan yang bertahan dari yang jebol?

Bukan pertanyaan tentang untung-rugi. Ini mengukur apakah gambarnya informatif,
dan hanya itu yang diklaim aplikasi ini.

## Tiga aturan yang membuat jawabannya jujur

1. **Skor dibaca pada saat sentuhan, bukan sesudahnya.** Skor yang tertera pada
   chart jadi sudah tahu berapa kali harga kembali dan sedalam apa. Memakai angka
   itu untuk memeringkat hasil sentuhan pertama adalah penalaran melingkar. Pada
   sentuhan pertama sebuah zona pasti masih `fresh`, dan `departure`-nya hanya
   diketahui sampai bar tersebut, jadi keduanya dihitung ulang.
2. **Pembandingnya base rate, bukan angka nol.** Hasilnya berbentuk bracket, dan
   geometri bracket saja sudah menetapkan tingkat kemenangan untuk deret tanpa
   drift. "68% zona bertahan" tidak berarti apa-apa sebelum diketahui berapa skor
   koin yang dilempar pada geometri yang sama.
3. **Ada dua kontrol, satu ringan satu berat.**
   - *Placebo*: zona palsu berukuran, bersisi, dan berumur sama, dipindah ke harga
     acak. Mengalahkan ini hanya membuktikan zona lebih baik daripada level
     sembarangan.
   - *Ditolak gerbang*: formasi asli yang gagal lolos `departure_min_atr`. Kedua
     kelompok sama-sama konsolidasi sungguhan pada struktur sungguhan, dan satu-
     satunya beda adalah filternya. Ini kontrol yang sesungguhnya.

Data: 20.000 bar per deret, lima deret (`PAXGUSDT` 15m dan 1h, `BTCUSDT` 15m dan
1h, `ETHUSDT` 1h). Semua batas tampilan dimatikan agar populasinya terdefinisi.

**Definisi hasil.** Pada bar sentuhan pertama: BERTAHAN bila harga bergerak
`reward` ATR menjauh dari garis proksimal sebelum ada bar yang menutup melewati
garis distal. JEBOL bila sebaliknya. Bila satu bar mencapai keduanya, dihitung
JEBOL, karena data bar tidak bisa memastikan mana yang lebih dulu dan menebak ke
arah yang menguntungkan adalah cara backtest membohongi dirinya sendiri.

## Hasil, tiga geometri

| Kelompok | reward 0.5 ATR | reward 1.0 ATR | reward 2.0 ATR |
|---|---|---|---|
| **Zona digambar** (n=231-234) | **97.9%** | **84.6%** | **61.0%** |
| Placebo, harga acak (n=210-211) | 61.1% | 46.9% | 31.9% |
| Ditolak gerbang (n=643-650) | 84.9% | 68.3% | 48.7% |
| Selisih vs placebo | +36.7 pp | +37.7 pp | +29.1 pp |
| **Selisih vs ditolak** | **+12.9 pp** | **+16.3 pp** | **+12.4 pp** |
| Uji dua proporsi vs ditolak | z=+5.29, p<0.0001 | z=+4.80, p<0.0001 | z=+3.23, p=0.0013 |

> [!NOTE]
> Tingkat absolut yang tinggi pada reward 0.5 ATR bukan prestasi, itu geometri.
> Dari garis proksimal, 0.5 ATR jauhnya lebih dekat daripada garis distal.
> Yang bermakna adalah selisih antar kelompok pada geometri yang sama.

**Signifikan di ketiga geometri terhadap kontrol yang berat.** Deteksinya nyata.

## `departure` adalah ambang, bukan gradien

Dihitung atas seluruh populasi, termasuk yang ditolak.

| Departure (ATR) | n | held @0.5 | held @1.0 | held @2.0 |
|---|---|---|---|---|
| 0 sampai 1 | 455-459 | 80.8% | 64.5% | 49.0% |
| 1 sampai 2 | 189-191 | 94.8% | 77.2% | 47.9% |
| **2 sampai 3** | 77-78 | **98.7%** | **87.2%** | **64.9%** |
| 3 sampai 4 | 53 | 98.1% | 83.0% | 54.7% |
| 4 sampai 5 | 35 | 97.1% | 85.7% | 57.1% |
| 5 ke atas | 66-68 | 97.1% | 82.4% | 63.6% |

Polanya sama di ketiga geometri: naik tajam sampai 2-3 ATR, lalu **datar**. Jadi
gerbang di 2.0 ATR berada di tempat yang benar, dan menaikkannya lebih jauh hanya
membuang zona tanpa menambah apa pun.

**Konsekuensi pada kode:** `departure` dikeluarkan dari skor komposit. Ia dulu
menyumbang 35% sebagai gradien, padahal datanya bilang ia ambang. Sekarang ia
hanya menjadi gerbang, sebagaimana mestinya.

## Skor komposit tidak lolos

AUC peringkat pada zona yang digambar. 0.5 berarti tidak membedakan sama sekali.

> [!WARNING]
> **Kolom reward 0.5 ATR tidak bisa dipakai untuk memeringkat apa pun.** Di
> geometri itu tingkat bertahan 97.9%, artinya hanya **5 kegagalan dari 234**.
> AUC yang dihitung dari 5 titik negatif tidak stabil, dan bootstrap-nya tetap
> melaporkan selang yang tampak sempit. Harness sekarang mencetak ukuran kelas
> minoritas di atas tabel dan menandai seluruh kolomnya `unusable` bila di bawah
> 30. Perbandingan antar kelompok di atas tetap sah, karena itu uji dua proporsi
> antara dua kelompok besar, bukan peringkat di dalam satu kelompok.

| Faktor | AUC @0.5 | AUC @1.0 | AUC @2.0 | Putusan |
|---|---|---|---|---|
| | *(5 negatif, tak terpakai)* | *(36 negatif)* | *(90 negatif)* | |
| tightness | 0.447 | 0.534 | 0.484 | tidak terbedakan, tanda berbalik antar paruh |
| compactness | 0.520 | 0.546 | 0.529 | tidak terbedakan, tanda berbalik antar paruh |
| volume | 0.705 | **0.610** | 0.519 | satu CI lolos di satu geometri, efeknya terkonsentrasi |
| base_drift | 0.206 | 0.508 | 0.505 | tidak terbukti, lihat catatan di bawah |
| base_overlap | 0.495 | 0.544 | 0.525 | tidak terbedakan |
| **formation_score** | 0.592 | 0.588 | 0.527 | **CI melintasi 0.5 di ketiganya** |

CI 95% untuk `formation_score` pada reward 1.0 adalah [0.482, 0.691]. Melintasi
0.5, jadi tidak terbukti.

`volume` adalah satu-satunya yang CI-nya pernah lepas dari 0.5 pada kolom yang
terpakai (reward 1.0: [0.517, 0.704]). Tetapi ia gagal pada reward 2.0, dan paruh
pertama versus paruh kedua adalah 0.710 lawan 0.504. Efeknya terkonsentrasi di
satu bagian data. **Tidak dijadikan dasar pembobotan.**

`base_drift` sempat terbaca kuat dan terbalik pada reward 0.5 (AUC 0.206), dan
itulah persis jebakan yang diperingatkan di atas: angka itu lahir dari 5
kegagalan. Pada dua geometri dengan sampel nyata ia 0.508 dan 0.505, dan tandanya
berbalik antar paruh pada reward 1.0. **Tidak ada bukti bahwa base yang melayang
berkinerja lebih buruk.** Alasan untuk mempersoalkannya bersifat kesetiaan pada
metode, bukan kinerja, dan keduanya harus dibedakan.

**Konsekuensi pada kode:**
- Bobot **tidak dipaskan ke data**. Tiga faktor, sepertiga masing-masing. Tidak
  ada di data ini yang membenarkan pemasangan bobot; memaskannya berarti memaskan
  derau. Dengan n=234, lebar CI AUC saja sudah sekitar plus-minus 0.10.
- `freshness` dikeluarkan dari komposit. Pada saat sentuhan pertama sebuah zona
  pasti `fresh`, jadi suku ini **konstan tepat ketika ia dibaca**. Informasi siklus
  hidup sekarang hanya hidup di `state`, `touches`, dan `penetration_pct`, tempat
  ia tidak dihitung dua kali.
- Angka skor **dihapus dari label chart**. Di atas chart, angka terbaca sebagai
  peringkat mutu, dan itu klaim yang tidak bisa didukung angka tersebut.
- Nama medannya diubah dari `strength` menjadi `formation_score`. "Strength"
  menjanjikan sesuatu yang tidak dimilikinya.

## Yang tidak diukur

- **Sentuhan kedua dan seterusnya.** Semua di atas hanya sentuhan pertama. Klaim
  bahwa zona segar lebih baik daripada zona yang sudah diuji **belum diuji di
  sini**, dan `freshness` dikeluarkan karena konstan pada sentuhan pertama, bukan
  karena terbukti tidak berguna.
- **Zona yang tidak pernah disentuh** tidak punya hasil, jadi tidak masuk sampel.
  Ini seleksi yang disengaja dan disebutkan terbuka.
- **Kontrol placebo hanya menguji "level sembarangan".** Ia tidak menguji zona
  melawan level struktural lain seperti swing high biasa atau angka bulat. Klaim
  yang sah: zona mengalahkan harga acak, dan mengalahkan formasi yang ditolak
  gerbang. Bukan: zona mengalahkan semua metode penandaan level.
- **Emas hanya diwakili PAXG.** Tiga dari lima deret adalah kripto. Struktur
  memang lintas instrumen, tetapi ini bukan sampel XAU spot murni.
- **Tidak ada biaya transaksi, tidak ada spread, tidak ada slippage.** Ini bukan
  hasil dagang dan tidak boleh dibaca demikian.

## Kekuatan uji

Dengan n=234 zona terselesaikan, efek AUC sebesar 0.55 tidak dapat dibedakan dari
0.50. Untuk memastikan efek sekecil itu dibutuhkan sampel beberapa kali lipat.
Karena itu jawaban yang benar untuk `formation_score` bukan "tidak berguna",
melainkan **"belum terbukti pada data sebanyak ini"**, dan cara memperlakukannya
adalah tidak mengklaim apa pun sampai ada bukti.

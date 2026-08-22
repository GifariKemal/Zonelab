# Walk-forward di emas broker sungguhan, 19 Agustus 2026, diukur ulang 20 Agustus 2026

> [!CAUTION]
> **Setiap ekspektasi R di dokumen ini diukur dengan konvensi yang, per 22
> Agustus 2026, diketahui melebihkan.** Target yang tersentuh di bar entry
> sendiri dihitung sebagai kemenangan, dan itu mengasumsikan urutan di dalam bar
> yang OHLC tidak bisa membuktikan. Diadili dengan bar 5 menit dan 15 menit pada
> 1.569 trade di 7 sel: ekspektasi sebenarnya +0,0214 R dengan CI95
> [-0,024, +0,067], bukan +0,20 R. Lihat [QA-QUANT.md](QA-QUANT.md) bagian 6.
>
> Yang bertahan: gerbang departure tetap memisahkan, +0,124 R dengan Welch
> t = +4,82 di 7 dari 7 sel. Yang tidak bertahan: tingkat absolutnya.

Pengukuran terpisah, bukan pembaruan angka yang sudah terbit di
`docs/CALIBRATION.md`. Deret bawaan `tools/walkforward.py` tidak diubah.

> [!CAUTION]
> **Koreksi, 20 Agustus 2026. Lima baris pada terbitan pertama halaman ini salah
> label instrumen.** `tools/walkforward.py` menyimpan dua salinan daftar deret:
> satu konstanta modul yang dihormati `--series`, dan satu literal yang
> ditulis ulang di dalam `gather()`. Baris `departure`, `age bars`, dan
> `profit zone rr` melewati `gather()`, jadi run 19 Agustus mencetak
> `Series overridden: [('mt5:XAUUSD', ...)]` lalu tetap mengukur PAXG, BTC, dan
> ETH. Hanya `fvg displacement` dan `order block displacement` yang benar-benar
> memakai emas broker. Salinan itu sudah dihapus, seluruh tabel diukur ulang,
> dan angka di bawah adalah hasil run baru. Perubahan terbesarnya bukan sekadar
> angka: **`profit zone rr` tidak bertahan di emas broker.**

```
python -m tools.walkforward --bars 50000 \
  --series "mt5:XAUUSD@15m,mt5:XAUUSD@1h" \
  --json ../docs/walkforward-mt5.json
```

## Kenapa run ini ada

`docs/CALIBRATION.md` mencantumkan keterbatasannya sendiri: tiga dari lima deret
adalah kripto, dan emas hanya diwakili PAXG, yaitu emas tersekuritisasi di
Binance. Terminal MetaTrader 5 di mesin ini membawa **emas CFD spot broker**,
100.000 bar (dua deret kali 50.000), Juli 2024 sampai Agustus 2026, tanpa page
cap dan tanpa rate limit.

> [!IMPORTANT]
> Ini instrumen yang berbeda dari yang lain, bukan pengganti. Terukur pada menit
> yang sama 19 Agustus 2026: spot MT5 tutup di 4459,6 sementara `GC=F` COMEX di
> 4515,8, selisih basis 56 dolar. Angka di bawah berlaku untuk emas broker, dan
> tidak boleh dikutip sebagai angka PAXG atau COMEX.

## Hasil

Delapan irisan dinilai. `A` adalah gerbang yang dikirim, diterapkan apa adanya
per irisan. `B` adalah ambang yang **dipilih hanya dari irisan sebelumnya** lalu
dinilai pada irisan berikutnya. Sign test dasarnya 0,0078 pada delapan irisan.

| Kuantitas | reward | gap median | rentang | n terima/tolak | A | B |
|---|---|---|---|---|---|---|
| departure | 0.5 | +0,143 | +0,126 .. +0,158 | 2178 / 6341 | 8/8 | 8/8 |
| departure | 1.0 | **+0,192** | +0,167 .. +0,215 | 2176 / 6316 | 8/8 | 8/8 |
| departure | 2.0 | +0,095 | +0,069 .. +0,109 | 2175 / 6335 | 8/8 | 8/8 |
| order block displacement | 0.5 | +0,207 | +0,186 .. +0,216 | 12616 / 12909 | 8/8 | 8/8 |
| order block displacement | 1.0 | +0,190 | +0,180 .. +0,203 | 12580 / 12887 | 8/8 | 8/8 |
| order block displacement | 2.0 | +0,104 | +0,099 .. +0,136 | 12618 / 12897 | 8/8 | 8/8 |
| age bars | 0.5 | +0,131 | +0,102 .. +0,143 | 1089 / 7430 | 8/8 | 8/8 |
| age bars | 1.0 | +0,199 | +0,149 .. +0,223 | 1089 / 7403 | 8/8 | 8/8 |
| age bars | 2.0 | +0,122 | +0,058 .. +0,155 | 1087 / 7423 | 8/8 | 8/8 |
| fvg displacement | 0.5 | +0,014 | **-0,014** .. +0,063 | 9432 / 1991 | **5/8** | 8/8 |
| fvg displacement | 1.0 | +0,050 | +0,016 .. +0,112 | 9421 / 1991 | 8/8 | 8/8 |
| fvg displacement | 2.0 | +0,048 | +0,011 .. +0,086 | 9421 / 1991 | 8/8 | 8/8 |
| profit zone rr | 0.5 | +0,012 | **-0,007** .. +0,045 | 4069 / 4450 | **6/8** | **5/8** |
| profit zone rr | 1.0 | +0,012 | **-0,019** .. +0,037 | 4061 / 4431 | **5/8** | **6/8** |
| profit zone rr | 2.0 | +0,022 | **-0,010** .. +0,039 | 4068 / 4442 | **5/8** | 8/8 |

Baris `age bars` dan `profit zone rr` sekarang muncul di ketiga level reward.
Terbitan pertama hanya memuat satu baris masing-masing, dan itu pun deret yang
salah.

## Yang bisa dibaca dari tabel ini

**Gerbang departure bertahan, dan sekarang benar-benar di emas broker.**
Delapan dari delapan irisan, di ketiga level reward, pada bagian A maupun B.
Sampelnya jauh lebih kecil daripada yang tercetak sebelumnya (2178 diterima
lawan 6341, bukan 5812 lawan 16743) karena ini dua deret satu instrumen, bukan
lima deret campuran. Rasio terima/tolaknya nyaris identik, 25,6%
diterima lawan 25,8% pada campuran, jadi gerbangnya menyaring seketat itu juga
di sini walaupun populasi yang disaringnya instrumen yang berbeda.

**Displacement order block sama kuatnya**, dan pada reward 0,5 tetap gap
terbesar di tabel. Baris ini tidak berubah maknanya, karena baris ini yang
memang sudah memakai emas broker sejak terbitan pertama.

**Umur zona bertahan paling meyakinkan setelah departure.** 8/8 di kedua bagian
di ketiga reward, dengan gap median +0,199 pada reward 1,0. Ini pertama kalinya
kuantitas ini diukur di emas broker sama sekali.

**`profit zone rr` gugur.** Inilah temuan yang lahir dari koreksi label. Di
campuran PAXG/BTC/ETH kuantitas ini mencetak 8/8 pada bagian A; di emas broker
ia hanya sepakat 5 sampai 6 dari 8 irisan di ketiga level reward, dengan
irisan negatif di ketiganya dan gap median +0,012 sampai +0,022, yaitu setipis
`fvg displacement` pada level terlemahnya. Sign test 5/8 tidak signifikan pada
lantai apa pun.

> [!NOTE]
> Tidak ada yang perlu ditarik dari produk karena ini. `min_profit_zone_rr`
> dikirim dengan nilai **0**, artinya gerbangnya mati dan angkanya hanya
> dilaporkan. `params.py` sudah menyatakan alasannya: "nobody has published a
> measured number for it and this project does not ship gates it has not
> measured". Pengukuran ini adalah alasan kedua untuk membiarkannya mati.

**Displacement FVG tetap yang terlemah di antara yang menyala.** Pada reward 0,5
gap medianya +0,014, salah satu irisan **negatif** (-0,014), dan bagian A hanya
sepakat 5 dari 8. Sampelnya juga paling timpang: 9432 diterima lawan 1991
ditolak, artinya gerbangnya hampir tidak menyaring apa pun pada deret ini.

## Yang tabel ini tidak tunjukkan

- **Bukan profitabilitas.** Tidak ada biaya, spread, maupun slippage di angka
  mana pun di atas. `docs/CALIBRATION.md` bagian biaya adalah tempat gerbang emas
  berhenti melewati skedul komisi sungguhan; keduanya harus dibaca bersama.
- **Bukan persistensi ke depan.** Satu riwayat adalah satu jalur.
- **Bukan optimalitas ambang.** Hanya bahwa ambangnya tidak jelas-jelas terfit.
- Signifikansi per irisan tidak diklaim. Sign test lintas irisan adalah
  statistiknya.
- **Bukan perbandingan langsung dengan `docs/CALIBRATION.md`.** Angka di sana
  diukur pada lima deret campuran; angka di sini pada dua deret satu instrumen.
  Yang bisa dibandingkan adalah ARAH gerbangnya, bukan besar gap-nya.

## Berbiaya, dengan spread broker yang diukur per bar

```
python -m tools.costed --symbol "mt5:XAUUSD" --interval 15m --bars 50000
python -m tools.costed --symbol "mt5:XAUUSD" --interval 15m --bars 50000 --broker exness_raw
```

Ini pertama kalinya biaya emas di proyek ini dihitung dengan **spread yang
benar-benar diukur**, bukan diasumsikan. Semua angka berbiaya sebelumnya memakai
feed yang tidak menerbitkan spread, sehingga jatuh ke konstanta tabel 1,6 bp
yang berasal dari tick Dukascopy.

Spread Exness terukur pada 49.997 bar: median **0,131 bp**, p90 0,215 bp, p99
0,267 bp. Diverifikasi bukan artefak: satu bar 1 menit diperiksa tick per tick,
seluruh 128 tick di dalamnya berspread 130 point dan field bar juga menulis 130.

| Arm | n | tanpa biaya | biaya generik | biaya Exness Zero |
|---|---|---|---|---|
| **supply_demand di atas gerbang** | 1444 | +0.289 | **+0.198** | **+0.199** |
| supply_demand seluruhnya | 5585 | +0.053 | -0.019 | -0.024 |
| supply_demand di bawah gerbang | 4141 | -0.030 | -0.095 | -0.102 |
| PLACEBO | 9197 | -0.076 | -0.141 | -0.128 |
| PLACEBO BERJANGKAR | 909 | -0.041 | -0.109 | -0.187 |
| fvg di atas gerbang | 186 | +0.168 | +0.129 | +0.125 |
| order block di atas gerbang | 5231 | +0.223 | +0.119 | +0.122 |

Walk-forward berbiaya, supply_demand di atas gerbang: **8 dari 8 fold positif**
pada kedua profil biaya.

> [!IMPORTANT]
> Hasilnya **kokoh terhadap pilihan profil biaya**, dan itu yang membuatnya
> layak dipercaya. Baris generik memakai komisi yang komentarnya sendiri sebut
> belum terverifikasi; `exness_raw` memakai komisi terbitan Exness plus biaya
> administrasi 4,545 bp per malam yang lebih besar dari seluruh biaya lain
> digabung. Keduanya menghasilkan angka yang praktis sama, +0.198 lawan +0.199.

Semua yang di bawah gerbang, dan kedua plasebo, tetap negatif setelah biaya.

## Swap ternyata milik SISI, bukan milik instrumen

Dibaca dari terminal yang tersambung, 20 Agustus 2026, XAUUSD:

```
swap_mode           1   (point)
swap_long      -541.4   point = -54,14 USD per lot 100 ons per malam = 1,20 bp
swap_short        0.0   point = tidak ada sama sekali
swap_rollover3days  3   (Rabu tiga kali lipat, jadi 3,61 bp sekali jalan)
```

Model biaya menagih satu angka ke kedua sisi, jadi setiap short ditagih biaya
yang tidak pernah dibayarnya. Kesalahannya condong ke arah yang sama dengan
gambarnya: zona demand itu long.

> [!WARNING]
> **Belum tuntas dan butuh konfirmasi pemilik.** Profil `exness_raw` semula
> menulis `swap_bp: 0.0` dengan alasan Indonesia masuk daftar swap-free Islamic
> Exness. Terminal yang tersambung menagih long 1,20 bp per malam. Keduanya
> tidak bisa sama-sama benar tentang akun ini, dan terminal adalah pihak yang
> akan mendebit. Tetapi ini server **Trial**; akun live dengan status Islamic
> mungkin memang nol. Angka terukur yang dipakai karena ia yang lebih keras dan
> satu-satunya yang bisa diverifikasi dari sini.

Arah asimetrinya milik venue, bukan milik emas: IBKR, yang benar-benar
meminjamkan, menagih 1,29 bp per hari untuk short dan 0,028 bp untuk long, yaitu
kebalikannya.

## Koreksi 21 Agustus 2026: 1.338 bar tertua bukan bar satu jam

Permintaan 50.000 bar 1 jam dijawab terminal dengan **35.192** bar, kembali
sampai 9 Agustus 2016. Yang tidak terlihat sampai hari ini: **1.338 bar tertua
berjarak satu hari, bukan satu jam**, karena terminal tidak punya riwayat
intraday sedalam itu dan mengirim apa yang ada. Detektor membaca bar berurutan
sebagai bersebelahan, jadi ATR, swing, dan setiap zona di rentang itu dihitung
melintasi langkah yang salah.

Ditemukan lewat gejala yang tampak tidak berhubungan: satu trade melaporkan
**42 malam** ditahan pada horizon 80 bar. Mustahil pada satu bar per jam, biasa
pada satu bar per hari.

**Arah dampaknya penting, dan ini keberuntungan bukan desain:**

| Wilayah | n | exp R | t |
|---|---|---|---|
| 1.338 bar tertua, spasi harian | 43 | **-0,192** | -1,15 |
| 33.854 bar sisanya, spasi jam | 910 | **+0,216** | +5,44 |
| Digabung, angka yang terbit | 953 | +0,198 | +5,10 |

Wilayah kotor itu **mengencerkan** hasilnya, jadi +0,198 R yang sudah terbit
konservatif dan bukan tersanjung. Instrumen berikutnya belum tentu seberuntung
itu.

Deret **15 menit tidak terpengaruh**: 50.000 bar diminta, 50.000 diterima, nol
prefix tidak beraturan. Jadi +0,201 R di 15 menit bersih sejak awal.

`tools/history.irregular_prefix` sekarang menghitungnya dan `tools/costed.py`
mencetak peringatan saat prefix itu bukan nol. Tidak dipangkas otomatis: tool
yang butuh window bersih bisa memotong sendiri, sementara tool yang diam-diam
membuang sepersepuluh deret akan menjawab pertanyaan yang tidak ditanyakan
siapa pun.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

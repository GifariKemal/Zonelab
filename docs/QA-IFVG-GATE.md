# Gerbang departure IFVG, diukur 5 September 2026

Sebuah asumsi yang dipakai kode selama satu commit, lalu diukur. Dokumen ini
mencatat angkanya, keputusannya, dan satu hal yang membalik cara gerbang ini
harus dibaca.

> [!IMPORTANT]
> Gerbang ini **tidak menyentuh satu order pun**. Layer `ifvg` dan `breaker`
> tidak `orderable` dan `tools/execute.py` tidak pernah memanggil keduanya.
> Yang dipengaruhi arah gerbang di sini adalah teks panel PLAN, teks ADVISOR,
> dan badge verdict di zone card. Sensusnya:
>
> | layer | orderable | gerbang | timeframe terukur |
> |---|---|---|---|
> | `supply_demand` | ya | floor 2,0 ATR | semua |
> | `fvg` | ya | ceiling 0,25 ATR | 30m |
> | `order_block` | ya | floor 2,0 ATR | semua |
> | `ifvg` | **tidak** | ceiling 0,25 ATR | 15m sampai 4h, dokumen ini |
> | `breaker` | **tidak** | floor 2,0 ATR | **belum pernah** |

## Kenapa diukur

Plafon 0,25 ATR lahir dari sweep FVG di commit `44196e2`. Sweep itu menyuntik
`detect_fvg` ke `DETECTORS` dan tidak menyentuh satu zona inversi pun, tetapi
commit yang sama memasukkan `ZoneKind.IFVG` ke `CEILING_KINDS`. Jadi selama satu
commit, IFVG dinilai dengan ambang yang tidak pernah diukur untuknya.

Ada alasan spesifik untuk meragukan analogi itu, bukan sekadar ketiadaan angka.
`app/detect/inversion.py:130` **membawa** `departure_atr` milik parent alih-alih
menghitungnya ulang, dengan alasannya sendiri: sebuah inversi dibuat oleh close
yang menembus level, dan close tidak punya kaki yang bisa diukur.

```mermaid
flowchart LR
  A[FVG parent] -->|gap height dalam ATR| B[departure_atr]
  A -->|close menembus distal| C[IFVG]
  B -.->|diwarisi apa adanya| C
  C --> D{gerbang 0,25 ATR}
  D -->|angka milik peristiwa SEBELUM inversi| E[verdict]
```

## Praregistrasi

Ditulis sebelum angkanya dilihat, ada di docstring `tools/ifvg_gate.py`:

- [x] Sel, ambang dan geometri sama dengan sweep FVG supaya sebanding
- [x] **Kedua arah** diuji untuk setiap ambang, karena menguji satu arah saja
      adalah cara paling mudah menemukan gerbang yang tidak ada
- [x] Ambang `|t|` Bonferroni atas seluruh sel grid, 14 sel, jadi 2,914
- [x] Gerbang dinyatakan ada hanya bila lolos `|t|` **dan** walk-forward 8 dari 8
- [x] `MIN_GROUP` 30, karena `BACKLOG.md` bagian 3c mencatat satu t=+2,92 yang
      lolos Bonferroni di atas tujuh trade

## Populasi

12 sel, XAUUSD dan BTCUSD kali enam timeframe, diadili bar halus:
15m lewat 1m, 30m dan 1h lewat 5m, 4h lewat 15m, 1d lewat 1h, 1w lewat 4h.

> [!NOTE]
> 1m dan 5m **tidak ada** dan tidak bisa ditambahkan. Tidak ada deret lebih
> halus dari keduanya di provider ini, jadi urutan stop lawan target di dalam
> satu bar cuma bisa diasumsikan. Asumsi itu pernah memakan +0,2 R jadi
> -0,0153 R begitu resolusinya dihaluskan, jadi mengukur di 1m tanpa pengadil
> bukan versi kasar dari pengukuran ini, ia pengukuran yang berbeda.

Total n = 11.068. Sebaran `departure_atr` stabil di semua timeframe: median
0,30 sampai 0,41 dan 30 sampai 43 persen populasi di bawah 0,25. Jadi plafon
0,25 adalah gerbang yang hidup, bukan saklar mati.

## Hasil, gabungan

Baseline tanpa gerbang: n=11.068, exp_r **+0,2348**, t=+14,60.

| ambang | n | exp_r | win rate | PF | mean win | mean loss | Welch t | wf |
|---|---|---|---|---|---|---|---|---|
| 0,1 ceiling | 1.989 | +0,4018 | 0,3967 | 1,725 | 2,4106 | -0,9189 | +3,68 | 8/8 |
| **0,25 ceiling** | **4.484** | **+0,3450** | **0,4208** | **1,652** | 2,0781 | -0,9142 | **+5,18** | **8/8** |
| 0,5 ceiling | 7.300 | +0,2944 | 0,4460 | 1,596 | 1,7672 | -0,8915 | +6,09 | 8/8 |
| 1,0 ceiling | 9.683 | +0,2598 | 0,4662 | 1,559 | 1,5539 | -0,8702 | +6,88 | 8/8 |
| 1,5 ceiling | 10.436 | +0,2494 | 0,4738 | 1,552 | 1,4801 | -0,8589 | +7,62 | 8/8 |
| 3,0 ceiling | 10.964 | +0,2374 | 0,4777 | 1,535 | 1,4256 | -0,8491 | +4,97 | 8/8 |

Arah plafon menang di **setiap** ambang, dan lawan arah lantai selisihnya
signifikan sampai t=+7,62. Jadi keanggotaan IFVG di `CEILING_KINDS` sekarang
terukur.

## Yang membalik cara membacanya

Perhatikan kolom win rate. Ia **turun** secara monoton saat gerbang diperketat,
0,4777 di 3,0 menjadi 0,3967 di 0,1, sementara mean win naik dari 1,43 R ke
2,41 R dan mean loss hampir tidak bergerak di sekitar -0,9 R.

Itu tanda tangan mekanis, dan mekanismenya bisa dinamai. `app/plan.py:190`
menaruh target di zona lawan terdekat sementara stop duduk di luar distal, jadi
reward adalah jarak **absolut** ke zona lawan dan risk adalah tinggi box plus
buffer. Untuk FVG, `departure_atr` **adalah tinggi gap dalam ATR**
(`imbalance.py:359`, `size = (top - bottom) / scale`), bukan jarak kaki keluar.
Jadi plafon yang lebih ketat menyimpan gap yang lebih kecil, gap yang lebih
kecil memberi stop yang lebih rapat, dan R dinormalisasi terhadap risk.

> [!WARNING]
> Gerbang ini menyortir **kerapatan stop**, bukan kemungkinan berhasil. Harga
> justru lebih sering kena stop pada kohort yang dipertahankannya. exp_r dan
> PF tetap naik karena keduanya dinormalisasi risiko, dan itu membuatnya tetap
> berguna sebagai penyortir, tetapi siapa pun yang membaca plafon ini sebagai
> "setup yang lebih sering benar" membacanya terbalik.
>
> **Ini berlaku sama untuk gerbang FVG yang sudah dikirim**, karena field dan
> mekanismenya identik. Kalimat itu ditambahkan ke sisi FVG di commit yang
> sama dengan dokumen ini.

## Hasil, per timeframe

| tf | n | baseline exp_r | ambang terbaik | exp_r terbaik | verdict |
|---|---|---|---|---|---|
| 15m | 1.903 | +0,3037 | 1,0 ceiling | +0,3292 | lolos |
| 30m | 4.635 | +0,2703 | 0,1 ceiling | +0,5324 | lolos |
| 1h | 2.171 | +0,2209 | 1,5 ceiling | +0,2392 | lolos |
| 4h | 1.632 | +0,1505 | 1,0 ceiling | +0,1773 | lolos |
| 1d | 711 | +0,0679 | tidak ada | - | **tidak memisahkan** |
| 1w | 16 | -0,3657 | tidak ada | - | **tidak terukur, n=16** |

Di 1d tanda semua ambang positif tetapi `|t|` tertinggi cuma 2,909 di ambang
0,5, di bawah Bonferroni 2,914, dan walk-forward-nya 6 dari 8. Jadi 1d
konsisten arah tapi tidak signifikan. Di 1w populasinya 16 trade.

Baseline juga meluruh dengan timeframe, +0,3037 di 15m menjadi +0,0679 di 1d
dan negatif di 1w. Itu pola yang sama yang sudah tercatat untuk detector lain
di repo ini.

### Rincian per timeframe, plafon 0,25 dan 1,0

Plafon 0,25 adalah yang dikirim; 1,0 disertakan karena ia ambang yang paling
sering jadi optimum per timeframe, jadi pembaca bisa melihat pilihannya.

| tf | n | baseline | plafon | n kohort | exp_r | win rate | PF | Welch t | wf |
|---|---|---|---|---|---|---|---|---|---|
| 15m | 1.903 | +0,3037 | 0,25 | 766 | +0,3818 | 0,3995 | 1,677 | +1,34 | 8/8 |
| 15m | | | 1,0 | 1.691 | +0,3292 | 0,4589 | 1,656 | +2,92 | 8/8 |
| 30m | 4.635 | +0,2703 | 0,25 | 1.975 | +0,4150 | 0,4182 | 1,745 | **+4,30** | 8/8 |
| 30m | | | 1,0 | 4.088 | +0,2944 | 0,4628 | 1,587 | +3,99 | 8/8 |
| 1h | 2.171 | +0,2209 | 0,25 | 872 | +0,3045 | 0,4048 | 1,550 | +1,76 | 7/8 |
| 1h | | | 1,0 | 1.892 | +0,2449 | 0,4582 | 1,500 | +2,91 | 8/8 |
| 4h | 1.632 | +0,1505 | 0,25 | 623 | +0,2031 | 0,4462 | 1,449 | +1,26 | 8/8 |
| 4h | | | 1,0 | 1.381 | +0,1773 | 0,4989 | 1,487 | +3,39 | 8/8 |
| 1d | 711 | +0,0679 | 0,25 | 240 | +0,1951 | 0,5083 | 1,641 | +2,48 | 7/8 |
| 1d | | | 1,0 | 618 | +0,0849 | 0,4644 | 1,317 | +1,91 | 6/8 |
| 1w | 16 | -0,3657 | 0,25 | 8 | -0,4806 | 0,250 | 0,053 | tidak terukur | - |
| 1w | | | 1,0 | 13 | -0,3908 | 0,2308 | 0,059 | tidak terukur | - |

> [!IMPORTANT]
> **Di plafon 0,25 hanya 30m yang lolos Bonferroni sendirian**, t=+4,30 lawan
> ambang 2,914. Lima timeframe lain berada di bawahnya jika diuji terpisah.
> Signifikansi gabungan t=+5,18 karena itu datang dari 30m ditambah tanda yang
> konsisten di seluruh sel, bukan dari enam timeframe yang masing-masing kuat.
> Di plafon 1,0 sebarannya lebih merata, empat dari enam melewati 2,914, dan
> itulah kenapa optimum per timeframe cenderung berkumpul di sana.
>
> Ambang Bonferroni 2,914 dihitung untuk 14 sel grid gabungan. Menguji enam
> timeframe secara terpisah berarti 84 sel, jadi ambang yang benar-benar adil
> per sel lebih ketat lagi. Angka per timeframe di atas layak dibaca sebagai
> deskripsi, bukan sebagai enam pengujian yang masing-masing lulus.

Win rate juga naik dengan timeframe pada plafon yang sama (0,3995 di 15m
menjadi 0,5083 di 1d pada 0,25), sementara exp_r turun. Itu konsisten dengan
mekanisme kerapatan stop di bagian sebelumnya: bar yang lebih besar memberi
box yang lebih besar relatif terhadap buffer, jadi stopnya lebih longgar,
lebih jarang kena, dan tiap kemenangan berharga R lebih kecil.

## Kenapa ambangnya TETAP 0,25

Gabungan memberi exp_r tertinggi di 0,1, dan ambang itu **tidak** diambil. Tiga
alasan, semuanya bisa dicek:

1. **Total R.** 0,1 menangkap 1.989 x 0,4018 = 799 R. 0,25 menangkap
   4.484 x 0,3450 = 1.547 R, hampir dua kali lipat, walau ekspektasi per
   trade-nya lebih rendah.
2. **Optimum per timeframe berkeliaran**: 1,0 di 15m, 0,1 di 30m, 1,5 di 1h,
   1,0 di 4h. Sebuah ambang yang benar-benar struktural tidak berpindah
   sejauh itu. Mengambil argmax grid gabungan berarti memilih satu titik dari
   14 dan menyebutnya temuan, dan itu persis yang praregistrasi di atas
   ditulis untuk mencegah.
3. **Satu angka untuk dua kind.** FVG sudah memakai 0,25 dan diukur pada
   ambang itu. Dua ambang plafon yang berbeda berarti dua angka yang bisa
   melenceng, dan `layers.py:100-106` sudah mencatat bentuk kegagalan itu.

## Parity geometri lawan tiga script komunitas

Sebelum outcome-nya diukur, geometrinya diperiksa. `Zonelab IFVG` ditulis di
Pine sebagai cermin baris per baris `app/detect/inversion.py`, dijalankan pada
feed yang **sama** dengan pembandingnya di FX:XAUUSD 30m. Feed-nya harus sama:
Zonelab membaca terminal MT5 dan TradingView membaca FXCM, jadi perbandingan
lintas feed tidak bisa membedakan "aturan berbeda" dari "data berbeda".

Toleransi satu sen, dihitung di `tools/ifvg_parity.py`, hanya di dalam jendela
harga kotak kita:

| pembanding | cocok persis | catatan |
|---|---|---|
| Inversion Fair Value Gaps (IFVG) [LuxAlgo] | **5/5, 100%** | definisi identik |
| Inversion Fair Value Gaps (IFVG) [ChartPrime] | 2/7, 28,6% | lima kotaknya lebih lebar, aturan gap berbeda |
| Inversion Fair Value Gaps [TradingFinder] | tidak bisa dibandingkan | menandai dengan garis dan label, bukan box |

Pine kita di 30m, sepanjang riwayat yang dimuat: 6.356 parent gap, 6.050
ter-inversi, 306 masih terbuka. Jadi **95,2 persen** FVG akhirnya ditembus
sebuah close, yang membuat IFVG hampir sama umum dengan induknya.

## Yang tidak ditanyakan di sini

Arah. `docs/CALIBRATION.md` bagian H8 sudah mengukur sentuhan pasca-inversi
sebagai klaim arah pada n=38.058 dan hasilnya negatif signifikan: kotak
menambah -0,179 / -0,165 / -0,274 dengan t sampai -4,22 di atas kontrol yang
hanya tahu gerak 20 bar terakhir. Dokumen ini menanyakan pertanyaan
penyortiran, bukan pertanyaan arah, dan keduanya bisa punya jawaban berbeda
tanpa saling bertentangan.

## Yang belum diukur, dan sengaja disebut

`breaker` (BRK) memakai lantai 2,0 ATR dan **tidak pernah diukur untuk itu**.
Ia mewarisi `departure_atr` dari order block induknya lewat mekanisme yang
persis sama dengan IFVG, jadi ia membawa bentuk keraguan yang sama. Tidak
diukur di sesi ini supaya lingkupnya tetap satu pertanyaan, dan dicatat di
sini supaya tidak dilupakan.

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.ifvg_gate
```

Baris hasil resolusi bar halus di-cache per sel di `docs/ifvg_rows_cache.json`,
jadi run kedua menjawab dalam hitungan detik. Hapus file itu untuk mengukur
ulang dari nol.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

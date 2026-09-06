# Gerbang departure breaker block, diukur 6 September 2026

Detector keempat lewat rig yang sama, dan yang terakhir yang masih memakai
ambang yang tidak pernah diukur untuknya. Tiga commit terakhir menyebut lantai
2,0 milik BRK sebagai satu-satunya yang tersisa. Dokumen ini menutupnya.

> [!NOTE]
> **Breaker BUKAN teknik breakout**, dan registry ini memisahkan keduanya
> secara eksplisit. Layer `wyckoff` yang membawa note "This is also the
> BREAKOUT layer". Breaker adalah objek INVERSI: break-nya cuma melahirkan
> kotaknya, dan trade-nya terjadi saat harga KEMBALI ke kotak yang sudah
> berbalik peran. Breakout masuk saat level jebol; breaker menunggu retest
> sesudahnya.

## Apa yang sudah diketahui sebelum ini

| pertanyaan | jawaban | sumber |
|---|---|---|
| klaim arah | negatif signifikan, n=38.058 | H8, `docs/CALIBRATION.md` |
| waktu-ke-sentuh | terbalik juga, +1,24 bar LEBIH LAMBAT, t=+5,83 | `docs/gap_outcomes.json` |
| lantai 2,0 miliknya sendiri | **belum pernah diukur** | - |

## Populasi, dan satu dugaan yang gugur

**97,4 persen order block akhirnya jadi breaker**, 2.733 dari 2.805 pada 20.000
bar XAUUSD 30m. Cuma 72 yang tidak pernah ditembus sebuah close. Jadi BRK bukan
objek langka, ia hampir seluruh populasi OB dibaca dari sisi seberang -
sebanding dengan IFVG yang 95,2 persen.

Detector induknya dibangun ulang pada hari yang sama (kotak dari badan lilin,
impuls diukur ke close), jadi BRK mewarisi rectangle yang berbeda dari minggu
lalu. Dugaannya: kotak badan yang lebih pendek lebih mudah ditembus close, jadi
tingkat inversinya naik. **Terukur, dugaan itu SALAH:**

| aturan induk | OB | BRK | tingkat | tinggi median |
|---|---|---|---|---|
| sekarang, badan plus close | 2.805 | 2.733 | **97,4%** | 1,268 |
| lama, rentang penuh plus wick | 4.041 | 3.934 | **97,4%** | 2,846 |
| hanya badan | 4.041 | 3.953 | 97,8% | 1,223 |
| hanya close | 2.805 | 2.720 | 97,0% | 2,900 |

Tingkatnya 97,0 sampai 97,8 persen apa pun aturannya. Di angka setinggi itu
tidak ada ruang untuk bergerak: hampir setiap order block ditembus close kalau
diberi cukup bar. Yang berubah populasinya, turun 31 persen, dan tinggi
kotaknya, turun 55 persen.

## Hasil

Baseline tanpa gerbang: n=7.410, exp_r **+0,2618**, t = **+12,60**,
profit factor **1,557**.

| lantai | n | exp_r | win rate | PF | wf | verdict |
|---|---|---|---|---|---|---|
| 1,0 dan 1,5 | 7.410 | +0,2618 | 46,28% | 1,557 | - | tidak mengikat, tak ada populasi di bawahnya |
| 2,0 **terpasang** | 4.391 | +0,2790 | 47,01% | 1,603 | 8/8 | **tidak memisahkan** |
| 2,5 | 2.671 | +0,2855 | 47,55% | 1,617 | 8/8 | **tidak memisahkan** |
| 3,0 | 1.706 | +0,3128 | 48,59% | 1,688 | 8/8 | **tidak memisahkan** |
| 4,0 | 737 | +0,3146 | 47,35% | 1,673 | 8/8 | **tidak memisahkan** |
| 6,0 | 169 | +0,2738 | 48,52% | 1,566 | 5/5 | **tidak memisahkan** |

> [!IMPORTANT]
> **Tidak satu ambang pun memisahkan.** Setiap lantai menaikkan exp_r sedikit
> dan menaikkan PF sedikit, tetapi tidak satu pun selisihnya melewati ambang
> Bonferroni 2,9137 - jadi kenaikan itu tidak bisa dibedakan dari memangkas
> populasi secara acak. Walk-forward 8 dari 8 di mana-mana, yang di sini
> berarti tandanya konsisten, bukan bahwa gerbangnya bekerja.
>
> Kesimpulannya: **BRK tidak butuh gerbang.** Populasi mentahnya sudah membawa
> angkanya.

## Per timeframe

| tf | n | baseline exp_r | PF pada lantai 2,0 |
|---|---|---|---|
| 15m | 1.359 | +0,1863 | 1,456 |
| 30m | 3.119 | **+0,3535** | **1,715** |
| 1h | 1.557 | +0,2210 | 1,481 |
| 4h | 1.008 | +0,1914 | 1,625 |
| 1d | 362 | +0,1331 | 1,853 |
| 1w | 5 | -0,1723 | tidak terukur |

**Lima dari enam timeframe positif**, dan itu lebih merata daripada order block
yang baselinenya negatif di empat dari enam sebelum diperbaiki.

## Dua tersangka yang diuji dan gugur

BRK memakai **rectangle yang sama** dengan OB, cuma dibaca dari sisi seberang,
dan OB memberi +0,1600. Sebuah kotak yang menguntungkan long DAN short adalah
tanda ada mekanisme, bukan edge, jadi dua penjelasan mekanis diuji lebih dulu.

| tersangka | OB | BRK | verdict |
|---|---|---|---|
| jalan ke target lebih lapang | `profit_zone_rr` median 13,57 | 14,04 | **gugur**, praktis sama |
| kotak lebih rapat, stop lebih dekat | tinggi median 4,871 | 4,796 | **gugur**, praktis sama |

Jadi bukan geometri reward maupun geometri stop.

## Angkanya tidak outlier, dan itu yang membuatnya layak dipercaya

| detector | baseline exp_r | t |
|---|---|---|
| IFVG, inversi dari FVG | +0,2348 | +14,60 |
| **BRK, inversi dari OB** | **+0,2618** | **+12,60** |
| OB, induknya | +0,1600 | +8,49 |

**Kedua objek inversi mengukur lebih baik daripada induknya, di dua keluarga
yang independen.** Itu pola yang konsisten, bukan satu angka aneh yang berdiri
sendiri.

> [!WARNING]
> **Ini BUKAN klaim arah, dan H8 tetap berdiri.** H8 mengukur apakah tahu
> sebuah kotak terbalik memperbaiki tebakan ARAH, dan jawabannya negatif
> signifikan di n=38.058. Dokumen ini menanyakan hal lain: sebuah trade di
> proximal dengan bracket yang sudah ditentukan. Keduanya bisa benar
> bersamaan, dan menggabungkannya akan menghasilkan klaim yang tidak satu pun
> pengukuran ini dukung.

## Dua keluarga definisi, dan kita mengimplementasi satu

Riset sumber luar menemukan bahwa breaker punya **dua keluarga definisi yang
bukan varian satu sama lain**:

| | Keluarga 1 | Keluarga 2 |
|---|---|---|
| definisi | order block yang gagal, dibaca terbalik | raid likuiditas lalu displacement |
| sweep sebelumnya | opsional, confluence | **wajib, konstitutif** |
| rectangle | dari order block induk | dari lilin di swing yang menyapu |
| sumber | FluxCharts, innercircletraders.net | LuxAlgo, Trading Strategy Guides |

**Kita mengimplementasi Keluarga 1**, dan itu harus dinyatakan alih-alih
diasumsikan universal.

> [!NOTE]
> Repo ini menyimpan DUA pernyataan soal mitigation block di tempat berbeda,
> dan riset menemukan keduanya benar tetapi milik taksonomi yang berbeda.
> `BACKLOG.md` baris 76 menyebut pembedanya adalah ketiadaan sweep, yang cocok
> dengan separator LuxAlgo. Baris 101 menyebut tidak ada sumber yang
> memisahkannya dari order block, dan jawabannya `ZoneState.MITIGATED` - yang
> justru persis separator ictkillzone, di mana mitigation adalah zona yang
> BELUM ditembus body dan ditradingkan ke arah aslinya. Kedua separator itu
> tidak kompatibel: yang satu membuat mitigation zona yang berbalik tanpa
> sweep, yang lain membuatnya zona yang tidak berbalik sama sekali. Jadi
> membangun detector mitigation berarti memilih taksonomi satu blog lalu
> mengukurnya, tanpa cara menyatakan taksonomi mana yang gagal.

## Tidak ada angka pembanding di literatur

Pencarian tidak menemukan **satu pun** hit rate atau ekspektasi terukur untuk
breaker block, dengan sample size, di sumber mana pun. StatOasis menguji empat
konsep ICT dan breaker bukan salah satunya. IndicatorEdge tidak
mengisolasinya. Setiap halaman memberi aturan dan gambar, nol hitungan.

Jadi tidak ada target untuk direproduksi, dan angka di dokumen ini adalah yang
pertama yang punya n dan t.

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.gate_sweep --detector breaker
```

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

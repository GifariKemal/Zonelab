# Triage 94 item failed/null/rejected, 4 September 2026

Inventaris lengkap tiap item di Zonelab yang gagal, null, ditolak, atau blocked,
dengan putusan per item dan referensi akademis yang mendukung putusan itu.

Empat riset paralel dijalankan (FVG/imbalance, conditioning/filtering,
session/time patterns, departure/touch optimization) terhadap jurnal, GitHub,
dan library. Hasilnya konsisten: **literatur setuju dengan hasil null Zonelab.**

## Referensi utama

| Kode | Sumber | Temuan kunci |
|---|---|---|
| HLZ16 | Harvey, Liu & Zhu (2016), "...and the Cross-Section of Expected Returns" | Mayoritas factor adalah false discovery. t-stat threshold harus 3,0+, bukan 2,0 |
| MP16 | McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?" | 26% OOS decay, 58% post-publication decay |
| MES26 | Mesfin (2026), arXiv 2605.04004, MNQ 5m, 947 hari | 14 signal families (termasuk OB, FVG, structure break), **nol** yang lolos walk-forward setelah biaya |
| OSL03 | Osler (2003), "Currency Orders and Exchange Rate Dynamics", Journal of Finance | Order clustering di S/R level; first touch depletes resting liquidity |
| CB21 | Chung & Bellotti (2021), arXiv 2101.07410 | Bounce probability di S/R meningkat dengan prior bounce count tapi decay over time |
| LDP18 | Lopez de Prado (2018), "Advances in Financial Machine Learning" | Meta-labeling, combinatorial purged CV. Mayoritas feature tetap wash out |
| KON26 | Kondapally (2026), SSRN 6032676 | FVG degree (formation speed): slower-forming FVG bereaksi 3,2x lebih kuat, p < 0,001. Tidak walk-forward validated |
| DEE25 | Deep et al. (2025), arXiv 2512.12924 | Walk-forward microstructure signals: Sharpe 0,33, p=0,34. Regime-dependent, tidak signifikan |
| LM15 | Lucca & Moench (2015), pre-FOMC drift | 49 bps pre-FOMC drift 1994-2011, **hilang post-2015** (Kurov 2020) |
| PIR05 | Park & Irwin (2005), replikasi breakout | 1985-2003: nol sistem net positif untuk portfolio 12 market |
| ZBA24 | Zarattini, Barbon & Aziz (2024), SSRN 4729284 | ORB tanpa filter: IRR 3,2%, Sharpe 0,48, **kalah dari buy-and-hold** |

---

## Kategori A: 12 hipotesis arah yang gagal

Semua pre-registered, semua diukur, semua gagal. Literatur setuju: ICT/SMC
directional claims tidak survive walk-forward (MES26, HLZ16).

**Putusan: ACCEPT NULL. Tidak ada yang diubah, tidak ada yang dihapus.**
Hipotesis yang gagal adalah HASIL, bukan bug. Menghapus hasilnya berarti
menghapus pengetahuan.

| # | Hipotesis | n | t | Hasil | Referensi |
|---|---|---|---|---|---|
| H1 | SSMT divergence predicts direction | 24 sel | null | 0/24 sel lolos | HLZ16, LDP18 |
| H2 | DFR extension levels reached more than placebo | 10 grup | null | 0/10 lolos, 1 negatif | HLZ16 |
| H3 | ICT checklist score separates R | 17 clause | null | 0/17 lolos, `dfr_side` inverted | HLZ16, MES26 |
| H4 | PSP after SSMT separates outcome | 48 sel | null | 48/48 null | HLZ16 |
| H5 | CISD inside OB predicts direction (bar-level) | - | null | Verdict empty | MES26 |
| H6 | BOS/CHoCH predicts direction | 9.210 | t=2,27 | Magnitudo runtuh 13x antar paruh | MES26 |
| H7 | Wyckoff phases predict directional move | 4 fase | null | Semua empty setelah clustering | PIR05 |
| H8 | OLHC rejection shape predicts direction | - | null | H_ORDER confounded, H_DIRECTION null | HLZ16 |
| H9 | Break tanpa sweep predicts direction | 5.128 | t=1,22 | Tidak signifikan | MES26 |
| H10 | Gap objects separate direction | - | mixed | ifvg/breaker TANDA TERBALIK | MES26 |
| H11 | Structure bias predicts direction | - | null | Tiga kali gagal (H6, H9, H11) | MES26 |
| H12 | Phase targets (DFR accum -> manip) | 22.550 level | null | 6/6 sel `passes: false`, `manip_to_distrib` t=-4,35 | HLZ16 |

---

## Kategori B: 16 layer terukur null/negatif

Layer yang sudah diukur dan hasilnya null atau negatif sebagai prediktor arah.
Sebagian tetap berguna sebagai **display** (menggambar objek di chart untuk
pembacaan visual), bukan sebagai sinyal.

**Putusan: ACCEPT NULL sebagai prediktor. Pertahankan sebagai display layer.**
Menghapus layer-nya berarti menghapus gambar yang user pakai untuk reading
manual.

| # | Layer | Ukuran | Hasil | Display value | Putusan |
|---|---|---|---|---|---|
| 1 | ifvg | inverted FVG | Tanda TERBALIK dari hipotesis | Ya, gambar FVG yang sudah di-close-through | Accept, display |
| 2 | breaker | breaker block | Tanda TERBALIK | Ya, gambar bekas OB yang di-break | Accept, display |
| 3 | structure | BOS/CHoCH/SWEEP | H6 t=2,27 tapi runtuh 13x | Ya, gambar swing structure | Accept, display |
| 4 | gaps | NDOG/NWOG | Return -0,58 ATR (continuation, bukan reversal) | Ya, gambar gap akhir pekan | Accept, display |
| 5 | chart_gaps | chart gap overlay | Null | Ya, visual reference | Accept, display |
| 6 | cisd | CISD event | Tanda terbalik, wf 8/8 tapi sebagai INVERTED signal | Ya, CISD inverted berguna | Accept, inverted |
| 7 | dfr | defining range | Gate `floor` bekerja, targeting gagal | Ya, range reference | Accept, display |
| 8 | ssmt | sequential SMT | 48/48 sel null, 0/24 eligible | Ya, user membaca divergence manual | Accept, display |
| 9 | pools | liquidity pool | Null sebagai prediktor arah | Ya, gambar PDH/PDL/PWH/PWL | Accept, display |
| 10 | liquidity | REQH/REQL | Null sebagai arah, berguna sebagai level | Ya, equal highs/lows | Accept, display |
| 11 | projections | range projection | Kelipatan range sesi: null | Ya, level referensi | Accept, display |
| 12 | wyckoff | spring/sos/sow/upthrust | 4 fase null, t < 1,0 | Ya, range phases visual | Accept, display |
| 13 | psp | precision swing point | 48/48 sel null | Ya, detects correlation cracks | Accept, display |
| 14 | news | economic calendar | Hanya minggu ini (blocked dari pengukuran) | Ya, warning layer | Accept, display |
| 15 | vortex | 3-6-9 dial | Bukan prediktor (by design) | Ya, navigasi visual | Accept, display |
| 16 | checklist aggregate | checklist sebagai scoring | 0/17 clause separates | Ya, manual reading aid | Accept, display |

---

## Kategori C: 6 studi conditioning (semua nol)

Conditioning variables diuji lawan zone expectancy. Nol yang lolos setelah
koreksi multiple testing. **Literatur setuju**: HLZ16 membuktikan mayoritas
factor false discovery; LDP18 melaporkan mayoritas feature wash out setelah
proper purging.

**Putusan: ACCEPT NULL. Conditioning tidak menambah edge di atas base rate.**

| # | Studi | Kolom diuji | Lolos | Referensi |
|---|---|---|---|---|
| 1 | conditioned_structure.json | 5 kolom structure + projections | 0/5 | HLZ16, LDP18 |
| 2 | conditioned_gaps.json | 7 kolom gaps/liquidity | 0/7 | HLZ16 |
| 3 | reality_check.json | White's RC, Hansen SPA, Romano-Wolf | 0 rule passes | HLZ16, LDP18 |
| 4 | Kondisi 1h, 12 kolom | 52 grup | 0/52 | HLZ16 |
| 5 | Kondisi 15m replication | 58 grup | 0/58 | HLZ16 |
| 6 | ICT 10 clauses, 15m replication | 89 grup | 0/89 | HLZ16, MES26 |

---

## Kategori D: 7 JSON result files (semua passes:false)

File hasil pengukuran yang merekam kegagalan. Ini **data**, bukan code yang
perlu diperbaiki.

**Putusan: ACCEPT. Pertahankan sebagai dokumentasi.**

| # | File | Apa yang diuji | Hasil |
|---|---|---|---|
| 1 | phase_targets.json | DFR targeting logic | 6/6 sel fails, termasuk t=-4,35 |
| 2 | volume_imbalance.json | Volume imbalance separates | H1 tidak lolos, n=18, t=+0,32 |
| 3 | shelf_conditioned.json | Shelf conditioning | 0/8 sel separates |
| 4 | shelf_proximity.json | Shelf proximity | Semua sel tidak separates |
| 5 | order_key.json | 21 ordering keys | Semua passes:false |
| 6 | event_backtest.json | Event-driven arms | 0 arm lolos |
| 7 | checklist_outcomes.json | Checklist scoring | 0 clause separates |

---

## Kategori E: 16 calibration factor gagal/confounded

Faktor kalibrasi yang terukur confounded oleh zone height atau departure
distance, atau tandanya terbalik.

**Putusan: ACCEPT. Faktor ini bukan sinyal independen - mereka proxy dari
variabel yang sudah diukur (zone height, departure ATR).**

| # | Factor | Masalah | Referensi |
|---|---|---|---|
| 1 | formation_score (volume) | Confounded: dinormalisasi terhadap jendela seluruhnya (diperbaiki ke trailing 200) | - |
| 2 | age_when_touched | Confounded oleh zone height | HLZ16 |
| 3 | displacement_atr | Confounded oleh departure distance | HLZ16 |
| 4 | body_ratio | Indistinguishable | HLZ16 |
| 5 | gap_ratio | Indistinguishable | HLZ16 |
| 6 | candle_count | Indistinguishable | HLZ16 |
| 7 | wick_ratio | Indistinguishable | HLZ16 |
| 8 | overlap_count | Indistinguishable | HLZ16 |
| 9 | nested_htf | Indistinguishable | HLZ16 |
| 10 | in_premium | Indistinguishable | HLZ16 |
| 11 | session_quarter | AUC meaningless on cyclic variable | MES26 |
| 12 | zone_height_atr | FLIPS: artifact, bukan sinyal | HLZ16 |
| 13 | trend_alignment | Indistinguishable | HLZ16 |
| 14 | htf_bias | Indistinguishable | HLZ16 |
| 15 | range_position | Indistinguishable | HLZ16 |
| 16 | touch_count (sebagai kualitas) | Confounded: lebih banyak touch = zona sudah lama, bukan lebih kuat | OSL03 |

---

## Kategori F: 5 modul not-wired (revisi: hanya 2 benar-benar mati)

Dari 5 modul yang dilaporkan not-wired, 3 sudah terwire.

| # | Modul | Status sebenarnya | Putusan |
|---|---|---|---|
| 1 | ladder.py | **Benar mati.** Nol caller. Intentionally excluded | **DELETE** (Task 4) |
| 2 | judas.py | **Sudah wired** via checklist.py | Accept, sudah jalan |
| 3 | m4.py | **Sudah wired** via tools/conditioned.py, tools/quant.py | Accept, measurement path |
| 4 | psp.py | **Sudah wired** via main.py draw endpoint | Accept, fully integrated |
| 5 | zscore.py | **Measurement-only.** Dipakai tools/quant.py, tidak di jalur API | Accept, measurement tool |

---

## Kategori G: 11 konsep rejected

Ditolak dengan alasan terukur. Referensi akademis mendukung.

**Putusan: ACCEPT REJECTION. Tidak perlu dibangun.**

| # | Konsep | Alasan penolakan | Referensi |
|---|---|---|---|
| 1 | Segitiga 3-6-9 sebagai sinyal | Aritmetika konsisten, tidak mengatakan apa pun tentang harga | - |
| 2 | Gambar jalur forecast | Engine tidak meramal, keputusan desain | - |
| 3 | Varian NWOG Senin 09:30 | Jalan tidak diambil | - |
| 4 | BPR (Balanced Price Range) | poi.confluence() sudah cover overlap FVG+OB | - |
| 5 | Weekly Pre-Planning system | Workflow, bukan objek harga | - |
| 6 | "1 Set-Up For Life" / "Consolidate Snap" | Template komposit, primitif sudah ada semua | - |
| 7 | IDX triad (IHSG) | Timezone WIB tidak overlap NY | - |
| 8 | Kill zone visual band | Redundan dengan session + pools layer | - |
| 9 | Crypto triad (BTC/ETH/XRP) | XRP tidak ada di sources, gold-centric framework | - |
| 10 | News execution rules | Disiplin trader, bukan kondisi harga | - |
| 11 | DFR targeting logic | Diukur 22.550 level, 6/6 sel gagal | HLZ16 |

---

## Kategori H: 3 item blocked

Constraint eksternal yang tidak bisa diperbaiki dari sisi kode.

**Putusan: ACCEPT BLOCK. Dokumentasikan constraint.**

| # | Item | Constraint | Bisa diatasi? |
|---|---|---|---|
| 1 | News calendar history | ForexFactory CDN hanya menyediakan minggu ini | Tidak, kecuali scrape historical (melanggar ToS) |
| 2 | Monthly candle | Provider MT5 tidak punya kontrak bulanan langsung | Bisa di-resample dari daily, tapi belum prioritas |
| 3 | Breakaway gaps | flat_atr 2,0 di bawah minimum yang pernah terjadi (2,085) | Populasinya nol. Gap fisik sudah diklasifikasi measuring |

---

## Kategori I: 7 kegagalan pengukuran spesifik

| # | Item | Hasil | Putusan |
|---|---|---|---|
| 1 | MT5-Python parity | 6/8 sel tidak sepakat | **DIPERBAIKI** 3 Sep 2026, breakout parity 0,34% |
| 2 | Volume imbalance | n=18, t=+0,32 | ACCEPT NULL, terlalu sedikit sampel |
| 3 | Three pushes reversal | Diukur tanpa Fibonacci ratio | ACCEPT, bukan reversal signal |
| 4 | Continuation ke arah DOL | Klaim arah, 12 hipotesis arah gagal | ACCEPT, sengaja tidak dibangun |
| 5 | Entry probability (2/3 features) | `ob_departure` dan `sd_zone_height` tidak lolos OOS | ACCEPT NULL untuk 2 feature |
| 6 | FVG costed detector | Verdict FAIL, selisih negatif dan signifikan | ACCEPT, OB detector lolos tapi FVG tidak |
| 7 | REQH/REQL tolerance | 0,1 ATR adopted, belum diukur optimal | **OPEN** - bisa diukur, tapi low priority |

---

## Kategori J: 5 implementasi parsial

| # | Item | Status | Putusan |
|---|---|---|---|
| 1 | Consequent encroachment | imbalance.py `penetration_pct` ada tapi bukan harga level | ACCEPT, 50% CE sudah dihitung |
| 2 | Unicorn model (FVG in breaker) | poi.confluence() menghitung overlap | ACCEPT, sudah tercakup |
| 3 | Opening Range Gap | gaps.py hanya 17:00/18:00 boundary | ACCEPT, ORB tanpa filter kalah buy-and-hold (ZBA24) |
| 4 | IPDA 20/40/60 day range | Tidak ada | LOW PRIORITY, hanya rolling high/low |
| 5 | Rejection block (wick-based OB) | OB defined on body, rejection on wick | ACCEPT, definisi berbeda tapi populasinya overlap |

---

## Ringkasan putusan

| Putusan | Jumlah | Aksi |
|---|---|---|
| ACCEPT NULL (literatur setuju) | 74 | Dokumentasi saja, tidak ada kode yang diubah |
| ACCEPT REJECTION | 11 | Dokumentasi saja |
| ACCEPT BLOCK | 3 | Dokumentasi constraint |
| DELETE | 1 | ladder.py dihapus |
| DIPERBAIKI (sebelum sesi ini) | 1 | MT5-Python parity |
| OPEN (bisa diukur, low priority) | 2 | REQH tolerance, IPDA range |
| NOT APPLICABLE (butuh tick data) | 1 | FVG degree metric (Kondapally) |
| SUDAH TERIMPLEMENTASI | 1 | Touch-count expiry (execute.py:504) |

Total: 94 item. Nol item yang tertinggal tanpa putusan.

---

## Dua improvement yang diimplementasikan sesi ini

### 1. FVG degree metric (formation speed filter) - TIDAK DIIMPLEMENTASI

Berdasarkan Kondapally (SSRN 6032676, Januari 2026): slower-forming FVG
bereaksi 3,2x lebih kuat (p < 0,001, 32.202 event, 4 asset class).

**Tidak bisa diimplementasi pada OHLCV.** Kondapally mengukur regression
slope per-second dari tick data selama gap formation. Pada OHLCV semua bar
punya durasi identik, jadi "speed" degenerasi ke gap size (sudah ada sebagai
`departure_atr`) atau body ratio (sudah terukur confounded oleh zone height
di calibration.json, status FLIPS). Menambahkan field yang redundan dengan
yang sudah gagal bukan improvement. Memerlukan akses tick data, yang Zonelab
tidak punya.

### 2. Touch-count expiry - SUDAH TERIMPLEMENTASI

Berdasarkan Osler (2003) dan Chung & Bellotti (2021): resting liquidity
habis di first touch, subsequent touch menemukan order book yang lebih tipis.

Data Zonelab sendiri sudah menunjukkan: departure gate +14,5 sampai +21,3 pp
di touch 1, lalu nol atau negatif dari touch 2.

**Sudah ada di kode.** `tools/execute.py:504` memfilter
`if zone.first_test_time is not None: continue` - zona yang sudah pernah
disentuh di-skip. Hanya fresh zones (belum pernah di-touch) yang menjadi
kandidat order. Literatur mendukung keputusan yang sudah ada di kode.
Tidak ada perubahan yang diperlukan.

---

## Satu hal yang TIDAK dilakukan dan alasannya

**Meta-labeling (Lopez de Prado).** Framework-nya dirancang untuk kasus ini:
classifier ML di atas entry yang sudah ada untuk memutuskan apakah trade
diambil. Tapi LDP18 sendiri melaporkan mayoritas feature tetap wash out
setelah proper purging, dan Zonelab sudah membuktikan 0/52 kolom lolos
koreksi. Membangun pipeline ML untuk conditioning yang sudah terbukti nol
adalah engineering tanpa hipotesis yang mendukungnya. Kalau suatu saat ada
feature baru yang lolos praregistrasi, meta-labeling jadi relevan.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).

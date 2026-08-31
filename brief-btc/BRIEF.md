# Brief Zonelab: mt5:BTCUSD

Dibuat 2026-08-30 03:43 NY. Pasar tutup: **False**. Harga acuan 78134.490 pada timeframe 4h.

> [!CAUTION]
> **Yang TIDAK boleh disimpulkan dari dokumen ini.** Zonelab menggambar
> struktur, bukan sinyal dagang, dan itu kalimat repo-nya sendiri di
> `README.md`. Dua belas hipotesis arah yang dipraregistrasi sudah gagal
> semua. Setelah resolusi intrabar yang jujur tidak ada satu pun bagian
> sistem ini yang punya ekspektansi positif, tereplikasi, dan di luar
> sampel.
> 
> Yang bertahan satu: gerbang departure 2,0 ATR memisahkan populasi
> (+0,1105 R, Welch t=+7,19, positif di 17 dari 18 sel), dan kohort yang
> lolos gerbang mengalahkan baseline bebas sinyal (+0,125 R, t=+4,28, 8
> dari 8 sel). Tapi ekspektansi kohort itu sendiri +0,0294 R dengan
> t=+1,22, tidak bisa dibedakan dari nol.
> 
> Ringkasnya: **box mengalahkan tanpa-box, dan belum mengalahkan
> tidak-trading.** Kutip ketiganya atau jangan kutip satu pun.

## Ringkasan per timeframe

| TF | bar | close | lag feed | basi untuk eksekusi | zona | struktur |
|---|---:|---:|---:|---|---:|---:|
| 4h | 2000 | 78134.490 | 13381s | False | 68 | 40 |
| 1h | 2000 | 78270.810 | 2581s | False | 48 | 40 |
| 15m | 2000 | 78225.690 | 781s | False | 62 | 40 |

**4h, layer yang menggambar nol dan sebabnya:**

- `ssmt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `smt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `news`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `gap_stacks`: nol digambar, dan layer ini tidak melaporkan stats apa pun

**1h, layer yang menggambar nol dan sebabnya:**

- `ssmt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `smt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `gaps`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `news`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `tier_horizons`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `gap_stacks`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `event_horizons`: nol digambar, dan layer ini tidak melaporkan stats apa pun

**15m, layer yang menggambar nol dan sebabnya:**

- `ssmt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `smt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `gaps`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `news`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `tier_horizons`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `gap_stacks`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `event_horizons`: nol digambar, dan layer ini tidak melaporkan stats apa pun

## Siklus, jam New York

| Kunci | Nilai |
|---|---|
| `amd_profile` | None |
| `quarter_day` | Q1 |
| `quarter_session` | Q2 |
| `in_manipulation_quarter` | None |
| `manipulation_done` | None |
| `range_band` | at_or_above_high |
| `range_pos` | 1.0 |
| `dfr_pos` | None |
| `hour_utc` | 0 |

Bias per derajat: `bias_15m`=None, `bias_1d`=1, `bias_1h`=None, `bias_4h`=-1

> H7 mengukur kontribusi zona DI ATAS bias dan hasilnya nol, jadi
> bias di sini konteks, bukan sinyal yang berdiri sendiri.

### Dial 3-6-9

| Ring | Sector | Root | Menyala |
|---|---:|---:|---|
| Session | 4/9 | 4 | tidak |
| Daily | 1/9 | 2 | tidak |
| Weekly | 8/9 | 6 | ya |
| Monthly | 7/9 | 1 | tidak |
| Quarterly | 6/9 | 3 | ya |
| Yearly | 6/9 | 9 | ya |

Navigasi murni. Ia membaca kalender dan bukan harga, dan sebuah test
melarangnya menyentuh jalur keputusan.

## Fibonacci dan OTE

Swing 62448.130 ke 65442.240, rentang 2994.110. Harga di retracement **5.2391**.

| Level | Harga |
|---|---:|
| 1.000_invalidasi | 65442.240 |
| 0.786_ote | 64801.500 |
| 0.705_ote | 64558.978 |
| 0.618_ote | 64298.490 |
| 0.500_equilibrium | 63945.185 |
| 0.382_batas_atas_ote_demand | 63591.880 |
| 0.214_batas_bawah_ote_demand | 63088.870 |
| 0.000 | 62448.130 |
| -0.27_ekstensi | 61639.720 |
| -0.618_ekstensi | 60597.770 |
| -1.000_ekstensi | 59454.020 |

> pita OTE arah-sadar: demand 0,214-0,382, supply 0,618-0,786. Klausa ote diukur di 12 instrumen dan NOL lolos, |t| tertinggi 2,04 lawan kritis 3,20

## Kandidat dengan target

| TF | jarak | sisi | kind | state | entry | stop | target | RR | departure |
|---|---:|---|---|---|---:|---:|---:|---:|---:|
| 15m | 31.0 | supply | DBD | mitigated | 78165.480 | 78348.538 | 77751.491 | 2.26 | 2.00 |
| 15m | 379.8 | demand | RBR | fresh | 77754.740 | 77604.322 | 78168.648 | 2.75 | 5.80 |
| 15m | 959.2 | supply | RBD | fresh | 79093.660 | 79898.808 | 77751.783 | 1.67 | 6.20 |
| 15m | 994.9 | demand | DBR | mitigated | 77139.590 | 76866.452 | 78168.307 | 3.77 | 8.47 |
| 15m | 1837.8 | demand | RBR | fresh | 76296.650 | 76149.852 | 78168.498 | 12.75 | 5.49 |
| 4h | 2157.9 | supply | RBD | mitigated | 80292.380 | 82263.709 | 73409.581 | 3.49 | 4.69 |
| 1h | 2301.2 | supply | RBD | fresh | 80435.680 | 81573.378 | 73405.052 | 6.18 | 7.16 |
| 15m | 2425.3 | demand | RBR | tested | 75709.140 | 75002.712 | 78165.334 | 3.48 | 10.37 |
| 4h | 3599.1 | supply | DBD | tested | 81733.540 | 84733.479 | 73423.222 | 2.77 | 6.25 |
| 15m | 4150.6 | demand | RBR | fresh | 73983.880 | 73296.092 | 78166.850 | 6.08 | 6.13 |
| 4h | 4722.0 | demand | RBR | fresh | 73412.450 | 70854.851 | 80287.230 | 2.69 | 5.95 |
| 1h | 4722.0 | demand | RBR | fresh | 73412.450 | 72232.402 | 80440.599 | 5.96 | 8.79 |
| 15m | 5264.6 | demand | RBR | fresh | 72869.900 | 72627.372 | 78168.147 | 21.85 | 10.83 |
| 15m | 6451.5 | demand | DBR | fresh | 71682.960 | 71335.992 | 78167.989 | 18.69 | 3.21 |
| 4h | 8150.1 | demand | RBR | fresh | 69984.420 | 68636.441 | 80300.246 | 7.65 | 10.73 |

Rencana TANPA target: **136**. rencana tanpa target berarti tidak ada zona lawan hidup di depan harga, dan gerbang keenam di tools/execute.py menolaknya. Itu penolakan yang bisa disebut, bukan ketiadaan setup.

## Checklist ICT untuk kandidat terdekat

### `DBD-1788048900`, met 6 dari 17

POI stack: supports `{'fvg': 0, 'order_block': 2, 'ifvg': 0, 'breaker': 0}`, conflicts 1, families 1

| Klausa | Terpenuhi | Sumber | Keterangan |
|---|---|---|---|
| `killzone` | ya | doctrine | in ('london', 'london_sb') |
| `day_of_week` | ya | doctrine | Sunday: instrumen ini dagang saat minggu CME tutup, jadi kalender akhir pekan tidak berlak |
| `discount_or_premium` | tidak | doctrine | band equilibrium, wanted one of ('premium', 'at_or_above_high') |
| `ote` | tidak diketahui | doctrine | no dealing range, no OTE reading |
| `manipulation_quarter` | ya | doctrine | profile AMDX, quarter Q2 |
| `manipulation_seen` | tidak | doctrine | conjunction incomplete: either the quarter has not arrived or no sweep took the level |
| `manipulation_after_accumulation` | tidak | doctrine | profile AMDX has accumulation but no manipulation yet — setup is a trap until the sweep ha |
| `poi_families` | tidak | doctrine | 1 of 4 families stack, wanted 2: {'order_block': 2} |
| `poi_clean` | tidak | doctrine | 1 opposite-side boxes in the band, tolerated 0 |
| `cisd_in_band` | tidak | doctrine | 0 CISD levels inside the box |
| `dfr_side` | ya | doctrine | position 0.7125 in the defining range |
| `htf_nested` | tidak | measured | no same-side zone one degree up contains this one. H2 measured nesting at p=0.33 |
| `bias_agrees` | ya | measured | bias_4h=-1, wanted -1. H7 measured the zone's contribution over bias at zero |
| `ssmt` | tidak diketahui | measured | no partner series supplied to this call |
| `two_stage_confirmed` | tidak | doctrine | no 2-stage SSMT confirmation on this timeframe |
| `min_rr` | ya | doctrine | reward 2.3R against the stop, wanted >= 2.0 |
| `draw_agrees` | tidak diketahui | nominated | no draw nominated; Zonelab does not infer one |

### `RBR-1788009300`, met 6 dari 17

POI stack: supports `{'fvg': 1, 'order_block': 1, 'ifvg': 1, 'breaker': 0}`, conflicts 0, families 3

| Klausa | Terpenuhi | Sumber | Keterangan |
|---|---|---|---|
| `killzone` | ya | doctrine | in ('london', 'london_sb') |
| `day_of_week` | ya | doctrine | Sunday: instrumen ini dagang saat minggu CME tutup, jadi kalender akhir pekan tidak berlak |
| `discount_or_premium` | tidak | doctrine | band equilibrium, wanted one of ('discount', 'at_or_below_low') |
| `ote` | tidak diketahui | doctrine | no dealing range, no OTE reading |
| `manipulation_quarter` | ya | doctrine | profile AMDX, quarter Q2 |
| `manipulation_seen` | tidak | doctrine | conjunction incomplete: either the quarter has not arrived or no sweep took the level |
| `manipulation_after_accumulation` | tidak | doctrine | profile AMDX has accumulation but no manipulation yet — setup is a trap until the sweep ha |
| `poi_families` | ya | doctrine | 3 of 4 families stack, wanted 2: {'fvg': 1, 'order_block': 1, 'ifvg': 1} |
| `poi_clean` | ya | doctrine | 0 opposite-side boxes in the band, tolerated 0 |
| `cisd_in_band` | tidak | doctrine | 0 CISD levels inside the box |
| `dfr_side` | tidak | doctrine | position 0.7125 in the defining range |
| `htf_nested` | tidak | measured | no same-side zone one degree up contains this one. H2 measured nesting at p=0.33 |
| `bias_agrees` | tidak | measured | bias_4h=-1, wanted 1. H7 measured the zone's contribution over bias at zero |
| `ssmt` | tidak diketahui | measured | no partner series supplied to this call |
| `two_stage_confirmed` | tidak | doctrine | no 2-stage SSMT confirmation on this timeframe |
| `min_rr` | ya | doctrine | reward 2.8R against the stop, wanted >= 2.0 |
| `draw_agrees` | tidak diketahui | nominated | no draw nominated; Zonelab does not infer one |

### `RBD-1787928300`, met 6 dari 17

POI stack: supports `{'fvg': 1, 'order_block': 2, 'ifvg': 1, 'breaker': 3}`, conflicts 2, families 4

| Klausa | Terpenuhi | Sumber | Keterangan |
|---|---|---|---|
| `killzone` | ya | doctrine | in ('london', 'london_sb') |
| `day_of_week` | ya | doctrine | Sunday: instrumen ini dagang saat minggu CME tutup, jadi kalender akhir pekan tidak berlak |
| `discount_or_premium` | tidak | doctrine | band equilibrium, wanted one of ('premium', 'at_or_above_high') |
| `ote` | tidak diketahui | doctrine | no dealing range, no OTE reading |
| `manipulation_quarter` | ya | doctrine | profile AMDX, quarter Q2 |
| `manipulation_seen` | tidak | doctrine | conjunction incomplete: either the quarter has not arrived or no sweep took the level |
| `manipulation_after_accumulation` | tidak | doctrine | profile AMDX has accumulation but no manipulation yet — setup is a trap until the sweep ha |
| `poi_families` | ya | doctrine | 4 of 4 families stack, wanted 2: {'fvg': 1, 'order_block': 2, 'ifvg': 1, 'breaker': 3} |
| `poi_clean` | tidak | doctrine | 2 opposite-side boxes in the band, tolerated 0 |
| `cisd_in_band` | tidak | doctrine | 0 CISD levels inside the box |
| `dfr_side` | ya | doctrine | position 0.7125 in the defining range |
| `htf_nested` | tidak | measured | no same-side zone one degree up contains this one. H2 measured nesting at p=0.33 |
| `bias_agrees` | ya | measured | bias_4h=-1, wanted -1. H7 measured the zone's contribution over bias at zero |
| `ssmt` | tidak diketahui | measured | no partner series supplied to this call |
| `two_stage_confirmed` | tidak | doctrine | no 2-stage SSMT confirmation on this timeframe |
| `min_rr` | tidak | doctrine | reward 1.7R against the stop, below 2.0 minimum |
| `draw_agrees` | tidak diketahui | nominated | no draw nominated; Zonelab does not infer one |

## Provenance klausa

> doctrine berarti sumbernya menyatakan dan project ini belum punya angka. measured_against berarti ADA angkanya dan ia menunjuk ke arah lain.

**Doktrin, belum ada angkanya:** `cisd_in_band`, `day_of_week`, `dfr_side`, `discount_or_premium`, `killzone`, `manipulation_after_accumulation`, `manipulation_quarter`, `manipulation_seen`, `min_rr`, `ote`, `poi_clean`, `poi_families`, `two_stage_confirmed`

**`ote` sudah diukur dan hasilnya berlawanan:** direplikasi di 12 instrumen 1h: NOL sel lolos, |t| tertinggi 2,04 lawan kritis 3,20. Negatif di 10 dari 12 sel tapi tidak signifikan di satu pun, jadi ia tidak punya edge DAN tidak terbukti merugikan

## Bukti per layer, disalin dari registry

| Layer | Jenis | Bukti |
|---|---|---|
| `supply_demand` | detector | The departure gate SORTS, and that is the whole claim: 43.0% against 40.2% held on the instrument actually traded, measured on 5-minute bars. The pair this line used to show, 85.8% against 64.4%, belongs to another marke |
| `fvg` | detector | +10 to +25 points against placebo, and it passed walk-forward 8 of 8 on two geometries. |
| `order_block` | detector | Measured through the same rig as the fair value gap, same result. |
| `ifvg` | detector | H8 measured it as a direction claim and it came out SIGNIFICANTLY NEGATIVE: knowing a box had inverted made a directional guess worse. Drawn for fidelity, never as a reading. |
| `breaker` | detector | Same as the inverted gap, and the same H8 negative result. |
| `structure` | overlay | H6 and H9 measured these exact objects for direction and both came out null. Drawn so the method can be seen, never as a bias. The sweep rule was CORRECTED 2026-08-20: a level now emits ONE sweep instead of re-arming, wh |
| `session` | overlay | The grid itself passes 26 property checks on 73,956 quarters, with no gap and no overlap. That is CONSISTENCY, not predictive value: nothing connects a quarter to an outcome.  The eighth degree is `quadrennial`, four yea |
| `vortex` | overlay | NONE, and this layer is EXEMPT from the measurement standard rather than failing it - there is nothing here to measure. The dial is digital_root(r * k), which is arithmetic on the calendar: a cell lands in {3, 6, 9} exac |
| `gaps` | overlay | No disclosed study exists by anyone. MEASURED HERE 2026-08-20 and NULL: respect at the first touch of the consequent encroachment, n=1955 touches from 1971 bands over four instruments, came out -0.58 ATR - price CONTINUE |
| `cisd` | overlay | No published hit rate exists. MEASURED NULL 2026-08-20: forward move at 12 bars, bullish minus bearish so drift cancels, n=23270 over four instruments, DELTA -0.0195 ATR at t=-0.53 - wrong sign and six times under the ba |
| `dfr` | overlay | SINGLE-SOURCED AND UNVERIFIED, which is the whole of what is known. The thirds rule reached this project from one description of a closed-source indicator and has never been checked against the course material it came fr |
| `ssmt` | overlay | The RATE is almost entirely the pair you choose, measured 14.9% against silver and 59.5% against DXY at day degree - an inversely correlated partner disagrees by construction. Nothing connects a divergence to an outcome, |
| `pools` | overlay | MEASURED NULL, 2026-08-20. Pre-registered: an untaken session extreme is traded through within 96 bars more often than a placebo. n=7552 over four instruments, reach 72.03%. Against a SHUFFLED placebo +2.90pp, p=9.2e-05  |
| `liquidity` | overlay | MEASURED NULL and the point estimate is NEGATIVE, 2026-08-20. Reach within 96 bars against a placebo at the same offset: PDH/PDL n=4152, -1.59pp [-3.28, +0.10], walk-forward 3 of 8; PWH/PWL n=747, -0.94pp, walk-forward 3 |
| `projections` | overlay | MEASURED NULL 2026-08-20, and it is the largest non-zero thing in this group: reach within 96 bars off the Asian box, n=6320 levels from 2122 boxes, +0.46pp against a per-event jitter control [+0.08, +0.85] - which is 6. |
| `news` | overlay | None, and it cannot be measured from this source: only the CURRENT WEEK is published - nextweek, lastweek, thismonth and thisyear all return 404 - so there is no history to test anything against. `impact` is the feed's o |
| `checklist` | report | None of the items has been measured against outcomes, and the report deliberately carries no overall pass or fail. It fetches per bias timeframe and per SSMT instrument, and it is not alone in fetching: gaps and ssmt do  |

---

Dihasilkan `python -m tools.brief`. Setiap angka di sini berasal dari
engine yang dipanggil langsung, bukan dari API, supaya brief tidak ikut
mati saat server mati.

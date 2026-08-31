# Brief Zonelab: mt5:XAUUSD

Dibuat 2026-08-30 03:43 NY. Pasar tutup: **True**. Harga acuan 4456.219 pada timeframe 1h.

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
| 1h | 2000 | 4456.219 | 124988s | True | 61 | 40 |

**1h, layer yang menggambar nol dan sebabnya:**

- `ssmt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `smt`: nol digambar, dan layer ini tidak melaporkan stats apa pun
- `news`: nol digambar, dan layer ini tidak melaporkan stats apa pun

## Siklus, jam New York

| Kunci | Nilai |
|---|---|
| `amd_profile` | XAMD |
| `quarter_day` | Q4 |
| `quarter_session` | Q3 |
| `in_manipulation_quarter` | False |
| `manipulation_done` | True |
| `range_band` | equilibrium |
| `range_pos` | 0.354 |
| `dfr_pos` | -4.3104 |
| `hour_utc` | 20 |

Bias per derajat: `bias_15m`=None, `bias_1d`=1, `bias_1h`=-1, `bias_4h`=-1

> H7 mengukur kontribusi zona DI ATAS bias dan hasilnya nol, jadi
> bias di sini konteks, bukan sinyal yang berdiri sendiri.

### Dial 3-6-9

| Ring | Sector | Root | Menyala |
|---|---:|---:|---|
| Session | 7/9 | 7 | tidak |
| Daily | 9/9 | 9 | ya |
| Weekly | 7/9 | 3 | ya |
| Monthly | 7/9 | 1 | tidak |
| Quarterly | 6/9 | 3 | ya |
| Yearly | 6/9 | 9 | ya |

Navigasi murni. Ia membaca kalender dan bukan harga, dan sebuah test
melarangnya menyentuh jalur keputusan.

## Fibonacci dan OTE

Swing 4324.467 ke 4697.152, rentang 372.685. Harga di retracement **0.3535**.

| Level | Harga |
|---|---:|
| 1.000_invalidasi | 4697.152 |
| 0.786_ote | 4617.397 |
| 0.705_ote | 4587.210 |
| 0.618_ote | 4554.786 |
| 0.500_equilibrium | 4510.809 |
| 0.382_batas_atas_ote_demand | 4466.833 |
| 0.214_batas_bawah_ote_demand | 4404.222 |
| 0.000 | 4324.467 |
| -0.27_ekstensi | 4223.842 |
| -0.618_ekstensi | 4094.148 |
| -1.000_ekstensi | 3951.782 |

> pita OTE arah-sadar: demand 0,214-0,382, supply 0,618-0,786. Klausa ote diukur di 12 instrumen dan NOL lolos, |t| tertinggi 2,04 lawan kritis 3,20

## Kandidat dengan target

| TF | jarak | sisi | kind | state | entry | stop | target | RR | departure |
|---|---:|---|---|---|---:|---:|---:|---:|---:|
| 1h | 10.3 | demand | RBR | tested | 4466.547 | 4417.623 | 4666.878 | 4.09 | 3.23 |
| 1h | 33.4 | demand | DBR | mitigated | 4489.624 | 4443.924 | 4666.862 | 3.88 | 6.55 |
| 1h | 128.2 | demand | RBR | mitigated | 4328.023 | 4295.624 | 4666.908 | 10.46 | 2.31 |
| 1h | 158.2 | demand | RBR | fresh | 4297.977 | 4276.282 | 4667.011 | 17.01 | 3.97 |
| 1h | 186.8 | demand | RBR | fresh | 4269.456 | 4240.468 | 4666.919 | 13.71 | 5.17 |
| 1h | 210.7 | supply | DBD | mitigated | 4666.914 | 4707.601 | 4489.624 | 4.36 | 8.01 |
| 1h | 242.6 | demand | RBR | fresh | 4213.651 | 4176.601 | 4666.959 | 12.24 | 5.07 |
| 1h | 276.4 | demand | RBR | fresh | 4179.796 | 4143.526 | 4667.103 | 13.44 | 7.04 |
| 1h | 314.5 | demand | RBR | fresh | 4141.676 | 4120.298 | 4666.960 | 24.57 | 9.64 |
| 1h | 366.9 | demand | RBR | fresh | 4089.295 | 4058.896 | 4667.000 | 19.00 | 11.10 |
| 1h | 395.3 | demand | DBR | fresh | 4060.897 | 4039.015 | 4666.942 | 27.70 | 9.15 |
| 1h | 442.1 | demand | DBR | fresh | 4014.113 | 3989.365 | 4666.961 | 26.38 | 7.69 |
| 1h | 470.0 | demand | DBR | mitigated | 3986.266 | 3953.516 | 4667.099 | 20.79 | 7.51 |

Rencana TANPA target: **48**. rencana tanpa target berarti tidak ada zona lawan hidup di depan harga, dan gerbang keenam di tools/execute.py menolaknya. Itu penolakan yang bisa disebut, bukan ketiadaan setup.

## Checklist ICT untuk kandidat terdekat

### `RBR-1787144400`, met 7 dari 17

POI stack: supports `{'fvg': 1, 'order_block': 0, 'ifvg': 1, 'breaker': 4}`, conflicts 0, families 3

| Klausa | Terpenuhi | Sumber | Keterangan |
|---|---|---|---|
| `killzone` | tidak | doctrine | outside; clock says none |
| `day_of_week` | ya | doctrine | Friday: Friday own profile — medium |
| `discount_or_premium` | tidak | doctrine | band equilibrium, wanted one of ('discount', 'at_or_below_low') |
| `ote` | tidak diketahui | doctrine | no dealing range, no OTE reading |
| `manipulation_quarter` | tidak | doctrine | profile XAMD, quarter Q4 |
| `manipulation_seen` | ya | doctrine | a sweep took the previous quarter's extreme inside the manipulation quarter |
| `manipulation_after_accumulation` | ya | doctrine | profile XAMD, manipulation done |
| `poi_families` | ya | doctrine | 3 of 4 families stack, wanted 2: {'fvg': 1, 'ifvg': 1, 'breaker': 4} |
| `poi_clean` | ya | doctrine | 0 opposite-side boxes in the band, tolerated 0 |
| `cisd_in_band` | tidak | doctrine | 0 CISD levels inside the box |
| `dfr_side` | ya | doctrine | position -4.3104 in the defining range |
| `htf_nested` | tidak | measured | no same-side zone one degree up contains this one. H2 measured nesting at p=0.33 |
| `bias_agrees` | tidak | measured | bias_4h=-1, wanted 1. H7 measured the zone's contribution over bias at zero |
| `ssmt` | tidak diketahui | measured | no partner series supplied to this call |
| `two_stage_confirmed` | tidak | doctrine | no 2-stage SSMT confirmation on this timeframe |
| `min_rr` | ya | doctrine | reward 4.1R against the stop, wanted >= 2.0 |
| `draw_agrees` | tidak diketahui | nominated | no draw nominated; Zonelab does not infer one |

### `DBR-1787227200`, met 6 dari 17

POI stack: supports `{'fvg': 1, 'order_block': 2, 'ifvg': 1, 'breaker': 1}`, conflicts 2, families 4

| Klausa | Terpenuhi | Sumber | Keterangan |
|---|---|---|---|
| `killzone` | tidak | doctrine | outside; clock says none |
| `day_of_week` | ya | doctrine | Friday: Friday own profile — medium |
| `discount_or_premium` | tidak | doctrine | band equilibrium, wanted one of ('discount', 'at_or_below_low') |
| `ote` | tidak diketahui | doctrine | no dealing range, no OTE reading |
| `manipulation_quarter` | tidak | doctrine | profile XAMD, quarter Q4 |
| `manipulation_seen` | ya | doctrine | a sweep took the previous quarter's extreme inside the manipulation quarter |
| `manipulation_after_accumulation` | ya | doctrine | profile XAMD, manipulation done |
| `poi_families` | ya | doctrine | 4 of 4 families stack, wanted 2: {'fvg': 1, 'order_block': 2, 'ifvg': 1, 'breaker': 1} |
| `poi_clean` | tidak | doctrine | 2 opposite-side boxes in the band, tolerated 0 |
| `cisd_in_band` | tidak | doctrine | 0 CISD levels inside the box |
| `dfr_side` | ya | doctrine | position -4.3104 in the defining range |
| `htf_nested` | tidak | measured | no same-side zone one degree up contains this one. H2 measured nesting at p=0.33 |
| `bias_agrees` | tidak | measured | bias_4h=-1, wanted 1. H7 measured the zone's contribution over bias at zero |
| `ssmt` | tidak diketahui | measured | no partner series supplied to this call |
| `two_stage_confirmed` | tidak | doctrine | no 2-stage SSMT confirmation on this timeframe |
| `min_rr` | ya | doctrine | reward 3.9R against the stop, wanted >= 2.0 |
| `draw_agrees` | tidak diketahui | nominated | no draw nominated; Zonelab does not infer one |

### `RBR-1786093200`, met 6 dari 17

POI stack: supports `{'fvg': 0, 'order_block': 0, 'ifvg': 1, 'breaker': 1}`, conflicts 1, families 2

| Klausa | Terpenuhi | Sumber | Keterangan |
|---|---|---|---|
| `killzone` | tidak | doctrine | outside; clock says none |
| `day_of_week` | ya | doctrine | Friday: Friday own profile — medium |
| `discount_or_premium` | tidak | doctrine | band equilibrium, wanted one of ('discount', 'at_or_below_low') |
| `ote` | tidak diketahui | doctrine | no dealing range, no OTE reading |
| `manipulation_quarter` | tidak | doctrine | profile XAMD, quarter Q4 |
| `manipulation_seen` | ya | doctrine | a sweep took the previous quarter's extreme inside the manipulation quarter |
| `manipulation_after_accumulation` | ya | doctrine | profile XAMD, manipulation done |
| `poi_families` | ya | doctrine | 2 of 4 families stack, wanted 2: {'ifvg': 1, 'breaker': 1} |
| `poi_clean` | tidak | doctrine | 1 opposite-side boxes in the band, tolerated 0 |
| `cisd_in_band` | tidak | doctrine | 0 CISD levels inside the box |
| `dfr_side` | ya | doctrine | position -4.3104 in the defining range |
| `htf_nested` | tidak | measured | no same-side zone one degree up contains this one. H2 measured nesting at p=0.33 |
| `bias_agrees` | tidak | measured | bias_4h=-1, wanted 1. H7 measured the zone's contribution over bias at zero |
| `ssmt` | tidak diketahui | measured | no partner series supplied to this call |
| `two_stage_confirmed` | tidak | doctrine | no 2-stage SSMT confirmation on this timeframe |
| `min_rr` | ya | doctrine | reward 10.5R against the stop, wanted >= 2.0 |
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

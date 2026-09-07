"""Every drawable thing in one registry, in the order it is drawn.

WHY THIS FILE EXISTS. Before it, turning something on took two different
mechanisms depending on what it was: box detectors were named in a `detectors`
list, and each of the seven overlays carried its own `enabled` boolean inside its
own params block. Same intent, two spellings, and a UI that had to know which was
which. The registry collapses both into one list of names, and `main._build`
became a loop over it instead of a chain of thirteen `if` statements.

THE ORDER IS LOAD-BEARING and is the tuple's own order, not a sort:

- `supply_demand` runs FIRST because it owns two passes nothing else has: the
  higher-timeframe nesting, and the road-ahead filter. Both must see only its own
  zones. A fair value gap has no opposing zone and no profit zone, so sweeping it
  through the road filter would apply one method's rule to another's drawing.
- The other box detectors APPEND rather than replace. A chart showing a supply
  zone and a fair value gap at the same price is showing two different claims
  about that price, and collapsing them would hide one.
- `structure` and everything after it draw no boxes, so they cannot be capped per
  side and must never be mistaken for detectors.
- `checklist` is not a drawing at all, and it is not the only entry that fetches.
  THREE blocks make extra provider calls, and saying otherwise sent one reader
  looking for a no-network guard in the wrong place: `gaps` when the window is
  too short to hold its own history, `checklist` per bias timeframe and per
  SSMT instrument, and `ssmt` through the aligned partner series. In `main.py`
  the real order is news, then checklist, then SSMT - so checklist is not last
  either. What IS true: every one of them fetches in the async handler, never
  inside the synchronous `_build` loop.

WHAT A LAYER IS NOT. It is not a claim that the thing works. `evidence` is a
required field precisely so that the UI cannot show a toggle without showing what
is known about it, and for most of these the honest answer is that nothing has
been measured. Twelve pre-registered directional hypotheses have failed in this
project; a menu that made every entry look equal would be the most misleading
thing on the screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LayerKind = Literal["detector", "overlay", "report"]


@dataclass(frozen=True)
class Layer:
    """One thing the engine can draw, and what is known about it."""

    id: str
    label: str
    kind: LayerKind
    #: Attribute on `DrawRequest` holding this layer's knobs. Several detectors
    #: share `imbalance` on purpose: an IFVG is an FVG plus one more event, and
    #: giving them separate gap thresholds would let the two populations drift.
    params: str
    note: str
    #: What has been MEASURED about it. "Nothing" is a valid and common answer,
    #: and saying so is the point of the field.
    evidence: str
    #: Which body of doctrine this layer comes from, or None for the ones that
    #: come from somewhere else entirely. It is a HEADING and nothing more: the
    #: toggle stays on each layer, so a family cannot switch anything on or off
    #: as a bloc.
    #:
    #: It lives on the Layer and not in a dict beside LAYERS, for the reason
    #: written at the bottom of `app/detect/__init__.py`: a second list of layer
    #: ids drifts from the first one silently, and a layer filed under the wrong
    #: heading still draws, still returns 200, and looks correct.
    #:
    #: `docs/ADOPSI.md` is the authority on which is which, and it separates ICT
    #: from SMC from Quarterly Theory explicitly - Quarterly Theory is Daye's,
    #: and its own section says harmonics are "bukan bagian ICT, SMC, atau
    #: Quarterly Theory". Supply and demand is the Seiden lineage, the trend
    #: gaps are Edwards-Magee, Wyckoff is Wyckoff, and the dial reads no price
    #: at all. None of those five belong under an ICT heading, so none of them
    #: carry one.
    family: str | None = None
    #: PERAN dalam sebuah keputusan, dan ini yang mengelompokkan menu.
    #:
    #: `family` menjawab "dari doktrin siapa" dan itu tetap berguna sebagai
    #: label per baris. Ia BURUK sebagai heading menu, dan itu terlihat: 7 dari
    #: 21 layer tidak punya family sama sekali, jadi mereka jatuh ke heading
    #: TIPE (`detectors`, `overlays`, `reports`) dan menu jadi campuran dua
    #: sumbu yang berbeda. `supply_demand` berakhir sendirian di bawah
    #: "detectors" padahal ia satu satunya yang menyala secara default dan box
    #: dengan bukti terkuat.
    #:
    #: Seorang trader yang memilih layer bertanya "benda ini menjawab apa",
    #: bukan "ini bukunya siapa". Jadi `role` yang jadi heading dan `family`
    #: turun jadi keterangan.
    #:
    #: BUKAN "bisa diorder". Itu fakta per layer yang hidup di
    #: `tools/execute.py:ORDERABLE_LAYERS`, dan ia dikirim sebagai bendera per
    #: baris supaya ia duduk bersama peluang terukurnya alih-alih memecah menu
    #: jadi dua kolom yang harus dibaca bersamaan.
    role: str = "Lainnya"
    #: Boleh dipasangi order, dan angka yang membatasi daftarnya.
    #:
    #: SEBELUMNYA INI DAFTAR KEDUA. `tools/execute.py` memegang
    #: `ORDERABLE_LAYERS`, `GATE_DIRECTION` dan `MEASURED_INTERVALS` sebagai tiga
    #: struktur berisi id layer, dan komentar di atas menjelaskan persis kenapa
    #: itu berbahaya: sebuah daftar kedua berisi id layer melenceng dari yang
    #: pertama tanpa suara. Faktanya sekarang hidup di sini dan `execute.py`
    #: menurunkannya, jadi menambah layer di satu tempat tidak bisa lagi
    #: meninggalkan tempat yang lain.
    #:
    #: `gate` adalah ARAH gerbang departure. `floor` membuang yang di bawah 2,0
    #: ATR; `ceiling` membuang yang di atas, dan itu benar untuk `fvg` karena
    #: gerbangnya terukur TERBALIK.
    orderable: bool = False
    gate: str | None = None
    #: Timeframe yang punya pengukuran. `None` berarti tidak dibatasi.
    measured_intervals: tuple[str, ...] | None = None


LAYERS: tuple[Layer, ...] = (
    Layer(
        id="supply_demand",
        orderable=True,
        gate="floor",
        role="Zona",
        label="Supply and demand",
        kind="detector",
        params="supply_demand",
        note="Impulse, base, impulse. The only detector shipped on by default.",
        evidence=(
            "The departure gate SORTS, and that is the whole claim: 43.0% against "
            "40.2% held on the instrument actually traded, measured on 5-minute "
            "bars. The pair this line used to show, 85.8% against 64.4%, belongs "
            "to another market - it was measured on PAXG, BTC and ETH from "
            "Binance while the executor printed it as the reason for every gold "
            "order. What still separates is the EXPECTANCY, +0.124 R at t=+4.82. "
            "The edge is a FIRST-TOUCH phenomenon; on later touches it is -0.2 to "
            "-4.3 points."
        ),
    ),
    Layer(
        id="fvg",
        # DIMATIKAN 7 September 2026, dan yang dicabut adalah klaimnya, bukan
        # detektornya - ia tetap digambar, tetap punya gerbang, tetap punya
        # angka. Yang tidak ia punya adalah satu pun interval, bracket, atau
        # varian filter yang lolos aturan walk-forward 8 dari 8 yang jadi syarat
        # proyek ini. Baris `evidence` di bawah memuat angkanya penuh; ringkasnya
        # 30m yang dulu membenarkannya (+0,2188 R, 8/8) berasal dari lifecycle
        # yang memeriksa pecah sebelum sentuh, dan setelah diperbaiki ia +0,0919 R
        # dengan t=+1,88 - di bawah ambang Bonferroni sweep-nya sendiri.
        #
        # `measured_intervals` DIPERTAHANKAN meski tidak lagi menggerbangi apa
        # pun, bentuk yang sama dengan `ifvg`: ia mencatat dari mana angkanya
        # berasal. Yang menolak order sekarang `ORDERABLE_LAYERS`, satu langkah
        # lebih awal.
        orderable=False,
        gate="ceiling",
        # 30m DICABUT 6 September 2026 dan diganti 1h plus 4h, dan itu
        # PENYEMPITAN, bukan perluasan. Angka 30m yang dulu membenarkannya
        # diukur lewat `replay_lifecycle` yang memeriksa pecah sebelum sentuh;
        # setelah urutannya benar, 30m mengukur PF 0,985 di TradingView dengan
        # biaya, di bawah satu. Lihat `docs/QA-FVG-TV.md`.
        measured_intervals=("1h", "4h"),
        role="Zona",
        family="ICT",
        label="Fair value gap",
        kind="detector",
        params="imbalance",
        note="The unfilled gap between the first and third of three candles.",
        evidence=(
            "RE-MEASURED 6 September 2026 after the lifecycle ordering defect, "
            "docs/QA-FVG-TV.md. Every earlier figure on this line was taken "
            "through `replay_lifecycle` checking the break BEFORE the touch, "
            "which dropped every zone price sliced through in one bar - and a "
            "resting limit at the proximal fills on exactly those bars. The "
            "old '+10 to +25 points against placebo, walk-forward 8 of 8' "
            "belongs to that population. Corrected, the same rig reads "
            "+0.0919 R at t=+1.88, below the Bonferroni threshold its own "
            "sweep used. "
            "WHAT STANDS NOW is narrower and is stated as such: XAUUSD only, "
            "1h and 4h only, tuned on 2013-2019 and reported on 2020-2026. "
            "4h out-of-sample PF 1.348 and +0.1838 R against a displaced-box "
            "control at +0.1337, so the detector's own share is +0.050 R and "
            "the rest is the period. 1h holds both halves, 1.027 then 1.338. "
            "IT DOES NOT TRANSFER TO BTCUSD: PF 0.938 there against a control "
            "at 1.028, which is the control WINNING, and 15m and 30m stay "
            "below one on both instruments because commission outruns the "
            "edge. "
            "THE CEILING SORTS BY STOP TIGHTNESS, NOT BY HIT RATE: "
            "`departure_atr` here is the GAP HEIGHT in ATR, so a tighter "
            "ceiling keeps smaller gaps and a smaller gap is a tighter stop. "
            "READ THIS LAST PARAGRAPH BEFORE ORDERING ANYTHING HERE. The 1h "
            "and 4h figures above come from a TradingView harness whose "
            "bracket is NOT the one `execute.py` trades: stop 1.0 ATR against "
            "production's 0.25, and a fixed 4R target against production's "
            "opposing zone. Re-measured in the production bracket on the same "
            "two intervals, pooled XAUUSD and BTCUSD, every arm sits at or "
            "below break-even - baseline PF 0.954 at -0.0271 R, the shipped "
            "filter pair 0.969 at -0.0181 R, and the best of six arms 1.032 "
            "at +0.0183 R with walk-forward 3 of 8. NO INTERVAL AND NO ARM "
            "PASSES THE 8-OF-8 RULE THIS PROJECT GATES ON, which is also true "
            "of the 30m entry this line used to carry. Stop width alone moves "
            "4h across 1.0 (0.959 at 0.25, 1.116 at 1.0), so the TradingView "
            "result is the bracket's geometry as much as the detector's - the "
            "exact reading `detect/__init__.py` says disqualifies a finding. "
            "`orderable=True` therefore stands on nothing measured, and the "
            "consistent action is to turn it off; it is left on because that "
            "is a trading decision, not a detector one. "
            "HARNESS ALIGNED 7 September 2026, docs/QA-FVG-TV.md section 17, "
            "which retires the bracket objection in the paragraph above. The "
            "TradingView harness now trades what `execute.py` trades: target "
            "from the opposing zone, chosen at the TOUCH like "
            "`profit_zone_at(zone, zones, time[touch])`, with EVERY detected "
            "zone eligible as a wall rather than only gate-passers. The best "
            "cell is XAUUSD 4h at PF 1.091 on 1,709 trades over 13.7 years, "
            "win 50.56%, broker cost in, bar magnifier on; a box displaced 1 "
            "ATR gives 1.014 at win 38.72%, so 11.8 points of win rate are "
            "the box's location. It still fails the rule: 6 of 8 consecutive "
            "periods above 1.0, with the two failures adjacent in 2016-2019. "
            "AND THE PRODUCTION NUMBERS THIS LINE ONCE LEANED ON ARE SHORTER "
            "THAN THEY LOOK: `intrabar.resolved` skips any zone touched "
            "before the fine-bar history begins, and MT5 5m history here "
            "starts 2025-09-24 for BTCUSD, so its PF 1.210 is a ONE-YEAR "
            "figure on n=695, not a 2.7-year one. On the full window the same "
            "bracket reads 0.995. "
            "KNOBS EXHAUSTED 7 September 2026, section 23. Every remaining "
            "parameter was swept at XAUUSD 4h in the aligned harness and every "
            "one is flat: horizon 20/80/300 gives 1.088/1.091/1.091 (it never "
            "binds - trades resolve long before 20 bars), atr_period 7/14/50 "
            "gives 1.080/1.091/1.097, filter_mother off/on 1.061/1.091, "
            "min_body_ratio 0.0/0.3 1.085/1.091, min_gap_atr 0.10 gives 1.075 "
            "on half the sample, and wall_memory is SATURATED at 300 (1000 "
            "returns the identical figure). Only two knobs move the result, the "
            "gate ceiling and the stop width, and both are swept. "
            "Purged walk-forward confirms 6 of 8 - shortening each period by 80 "
            "bars changes nothing and the two failures stay adjacent in "
            "2016-2019. THAT REGIME IS NOT A DETECTOR FAILURE: the displaced-box "
            "control loses there by 12.4 points of win rate, the same margin as "
            "the full sample, so the detector sorted as well as ever while the "
            "whole population lost. Read the 6 of 8 that way. "
            "BTCUSD controls: 1h sorts (0.995 against 0.890) but cost pins it at "
            "break-even; 4h and 1d LOSE to their own controls, and 4h loses "
            "while WINNING 11.5 points of win rate."
        ),
    ),
    Layer(
        id="order_block",
        # DIMATIKAN 7 September 2026, dan ia yang paling jelas dari tiga layer
        # yang diperiksa hari itu. Diukur di bracket yang `execute.py` benar
        # benar jalankan, bukan di harness: XAUUSD 4h memberi PF 0,495 dan
        # exp_r -0,2897 R pada t = -5,07, dan itu SATU-SATUNYA |t| di atas 2 di
        # seluruh sapuan tiga layer kali tiga sel - arahnya salah. Negatif juga
        # di XAUUSD 1h (-0,1412 R) dan cuma +0,0099 R di BTCUSD 1h. Melebarkan
        # stop ke 1,0 ATR mengurangi kerugiannya, tidak membalikkannya.
        #
        # `evidence` di bawah masih memuat PF 1,330 dengan walk-forward 8 dari 8
        # dan angka itu TIDAK dicabut, karena ia benar untuk apa yang diukurnya:
        # ia diukur lewat `replay_lifecycle` yang memeriksa pecah SEBELUM
        # sentuh, yaitu populasi yang jalur order tidak akan pernah dapat.
        # Membiarkannya berdampingan dengan paragraf ini adalah rekamannya.
        #
        # Sama seperti `fvg`: yang dicabut klaimnya, bukan detektornya. Ia tetap
        # digambar, tetap punya gerbang lantai, tetap punya angka.
        orderable=False,
        gate="floor",
        role="Zona",
        family="ICT",
        label="Order block",
        kind="detector",
        params="imbalance",
        note="The LAST opposing candle before the impulse.",
        evidence=(
            "REBUILT AND RE-MEASURED 6 September 2026, docs/QA-OB-GATE.md, "
            "12 cells and n=7,777. This line used to read 'measured through the "
            "same rig as the fair value gap, same result', which pointed at "
            "another detector's result and at a version of this one that no "
            "longer exists. Its own numbers: profit factor 0.984 to 1.320, "
            "expectancy -0.0053 to +0.1600, Welch t=+8.10 against the old rule, "
            "walk-forward 8 of 8. Four of six timeframes now clear PF 1, "
            "including 4h which was 0.761 at walk-forward 0 of 8. "
            "TWO CHANGES DID IT. The box is the candle BODY rather than its "
            "whole range, because the stop sits beyond the distal and risk is "
            "therefore box height - which the whole range hands to wick length, "
            "a quantity unrelated to the signal being tested. And the impulse is "
            "measured to the extreme CLOSE rather than the extreme wick, because "
            "30.6% of blocks qualified on a wick no close ever confirmed. "
            "READ IT AS GEOMETRY, NOT AS A BETTER GUESS: the win rate FELL, "
            "53.7% to 43.1%, and what rose is R per win. Only the close-impulse "
            "half is a true filter, and that half barely moves the win rate. "
            "1d still measures PF 0.975, below one, and this layer carries no "
            "measured_intervals - so the executor accepts it there. "
            "RE-MEASURED IN BOTH RIGS 7 September 2026, docs/QA-OB-GATE.md final "
            "section, and NONE of the numbers above survive. They were taken "
            "through the lifecycle that checked the break BEFORE the touch. This "
            "document called 30m the only timeframe where the detector works, at "
            "PF 1.255 and walk-forward 8 of 8, with the shipped variant at "
            "expectancy +0.2057 and t=+4.85; in the bracket `execute.py` trades, "
            "30m now reads +0.0077 at t=+0.26 and walk-forward 4 of 8. The 4h "
            "figure that disabled this layer is NOT an artefact - it reproduces "
            "at t=-4.98 against the -5.07 on record. "
            "THE TRADINGVIEW HARNESS DISAGREES AT 4h, and the disagreement is not "
            "resolved: over 13.7 years with the production bracket and bar "
            "magnifier it reads PF 1.019, against 0.663 on the production rig's "
            "4.2-year window. Above one, but by 0.019, and the gate floor has no "
            "stable value - select 3.0 on the first half (1.312 against 2.0's "
            "0.912) and out-of-sample it gives 0.822 while the shipped 2.0 gives "
            "1.131. The two arms cross. "
            "IT DOES SORT, and that is worth separating from the verdict: a box "
            "displaced 1 ATR reads 0.922 against 1.019. But it sorts by PAYOFF "
            "SIZE, not hit rate - the displaced arm has the HIGHER win rate, "
            "41.04 against 39.10, which is the opposite channel from fvg in the "
            "same cell. "
            "BENCHMARKED THROUGH IDENTICAL BRACKET CODE, fvg wins every measurable "
            "cell: 1.112/0.985 at XAU 1d, 1.091/1.019 at 4h, 1.006/0.737 at 1h, "
            "0.995/0.887 at BTC 1h, 0.900/0.840 at BTC 4h. BTC 1d is discarded "
            "for both - its own displaced-box control returns 2.010 against the "
            "real arm's 1.200, so what is measured there is the instrument's "
            "drift and the correctly-placed box earns LESS of it. "
            "30m AND 15m ARE UNMEASURED in the TradingView harness: the desktop "
            "chart dies whenever either timeframe is selected, on both feeds, "
            "including straight after a clean restart. "
            "CORRECTED THE SAME DAY, and the correction is mine: the Pine harness "
            "used ONE ATR series for both detectors while this file uses two on "
            "purpose - `mean_true_range` for fvg at line 365, `wilder_atr` for "
            "order block at line 465. The impulse AND the gate floor are both "
            "ratios to ATR, so the wrong family moves which blocks qualify at "
            "all, not just the stop width. With `ta.atr` (which IS Wilder) the "
            "4h figure goes 1.019 -> 0.926 and expectancy +0.0149 -> -0.0579, "
            "BTC 1d goes 1.200 -> 0.939, and NO cell sits above one: XAU "
            "0.972/0.926/0.798 at 1d/4h/1h, BTC 0.939/0.859/0.872. That also "
            "closes the open question above - harness and production rig now "
            "AGREE at 4h, both negative, so there was no regime to explain, only "
            "a parity defect in the harness. The gate sweep, placebo and hold-out "
            "recorded before this were run on the wrong ATR and do not stand. "
            "AGAINST THE RANKED PUBLIC PINE, geometry only: every one of the 25 "
            "search hits is an indicator with no bracket, so there is no PnL to "
            "compare without re-implementing someone else's protected source. "
            "`Order Block Detector [LuxAlgo]` on XAUUSD 4h draws boxes 16.56 to "
            "85.20 USD tall; the gate-passing Zonelab box is 3.96 median and "
            "16.68 at the 90th percentile, so their SMALLEST box sits at our p90 "
            "- five to ten times apart. Since risk per unit IS box height, those "
            "are brackets an order of magnitude apart and a PnL comparison would "
            "measure stop width as much as zone location."
        ),
    ),
    Layer(
        id="ifvg",
        # DICATAT, TIDAK DIPAKAI UNTUK MENG-ORDER. `execute.py` menurunkan
        # `GATE_DIRECTION` dengan penyaring `if layer.orderable`, jadi baris ini
        # tidak menyentuh satu order pun; ia menyatakan arah yang diukur
        # 5 September 2026 supaya registry tidak diam soal gerbang yang panel
        # PLAN dan ADVISOR sudah pakai.
        gate="ceiling",
        measured_intervals=("15m", "30m", "1h", "4h"),
        role="Zona",
        family="ICT",
        label="Inverted fair value gap",
        kind="detector",
        params="imbalance",
        note="A gap price has closed through, read from the other side.",
        evidence=(
            "H8 measured it as a direction claim and it came out SIGNIFICANTLY "
            "NEGATIVE: knowing a box had inverted made a directional guess worse. "
            "Measured again 1 September 2026 on a different question and "
            "inverted again: docs/gap_outcomes.json finds the band reached "
            "+0,65 bars LATER than a band matched on distance, height and side "
            "at a gap-free bar, t=+3,63, positive on eight of nine instruments. "
            "Price leaves an inverted gap and comes back slower than to an "
            "arbitrary level the same distance away. "
            "Drawn for fidelity, never as a reading. "
            "Its departure gate WAS measured, 5 September 2026, and the "
            "ceiling direction held: exp_r +0.3450 below 0.25 ATR against a "
            "+0.2348 baseline, Welch t=+5.18, walk-forward 8 of 8 on n=11,068 "
            "over 15m to 4h. At 1d the sign agrees but no threshold clears "
            "Bonferroni, and 1w has 16 trades. Read that as a SORTER and not "
            "as a hit rate: the win rate FALLS as the ceiling tightens, 47.8% "
            "to 39.7%, because the gate is keeping smaller gaps and a smaller "
            "gap is a tighter stop. docs/QA-IFVG-GATE.md. "
            "RE-MEASURED 7 September 2026 through the same bracket as the "
            "other three, docs/QA-OB-GATE.md final section. Every figure "
            "above predates the lifecycle ordering fix. On XAUUSD 4h over "
            "13.7 years with the production bracket and bar magnifier it "
            "reads PF 0.965 on n=1,613 at win 53.69% - BELOW ONE - while a "
            "box displaced 1 ATR reads 0.811 at 45.20%. "
            "IT IS THE SHARPEST SORTER OF THE FOUR and still loses money: "
            "+0.154 PF and +8.49 points of win rate over its own control, "
            "against fvg's +0.077, and fvg is the only one of the four "
            "above one. Sorting and paying are not the same property, and "
            "this line is where they separate. "
            "In the production rig its only positive cell is 30m (1.081 at "
            "t=+1.16, walk-forward 4 of 8) and 30m is exactly the timeframe "
            "the TradingView chart refuses to load, so that number has no "
            "long-window check."
        ),
    ),
    Layer(
        id="breaker",
        role="Zona",
        family="ICT",
        label="Breaker block",
        kind="detector",
        params="imbalance",
        note="An order block that suffered the same event.",
        evidence="Same as the inverted gap, and the same H8 negative result. "
            "Inverted again on time-to-touch, harder: docs/gap_outcomes.json "
            "finds it reached +1,24 bars LATER than a matched band at a "
            "gap-free bar, t=+5,83, positive on eight of nine instruments.",
    ),
    Layer(
        id="structure",
        role="Struktur dan momentum",
        family="ICT",
        label="Market structure",
        kind="overlay",
        params="structure",
        note="Swings, BOS, CHoCH, sweeps and MSS, at two fractal scales.",
        evidence=(
            "H6 and H9 measured these exact objects for direction and both came "
            "out null. Drawn so the method can be seen, never as a bias. The "
            "sweep rule was CORRECTED 2026-08-20: a level now emits ONE sweep "
            "instead of re-arming, which is what the most-used open-source "
            "implementation of the identical predicate does. Measured on 3000 "
            "bars of XAUUSD 15m, 147 sweeps from 88 levels became 88 from 88 - "
            "one level had been swept seven times - and the BREAK count did not "
            "move. Any figure quoting 8,725 sweeps predates this. "
            "MEASURED FOR ITSELF 7 September 2026 for the first time, "
            "docs/QA-OB-GATE.md final section, and read the gate caveat "
            "first: this layer has NO gate of its own. It inherits the "
            "parent order block's departure and is judged against the 2.0 "
            "ATR floor calibrated for that parent - GATE_UNMEASURED_KINDS "
            "says so and gate_measured returns False here for that reason. "
            "So every number below measures a BORROWED gate. "
            "THE PRODUCTION RIG MAKES IT LOOK LIKE THE BEST DETECTOR IN THE "
            "REPO: XAUUSD 1h gives expectancy +0.2163 at t=+4.74, PF 1.697, "
            "walk-forward 7 of 8, and all four cells measured come out "
            "positive. IT DOES NOT SURVIVE THE WINDOW. That figure sits on "
            "the 1.4 years of 5m history MT5 holds here; over the "
            "TradingView harness's full 3.7 years the same cell reads "
            "0.939, and cutting the harness to the production window lifts "
            "it to 1.128 on n=620 against production's 552 - so the window "
            "alone is worth 0.189 and the rest is feed plus intrabar "
            "resolution. Same shape as fvg's BTC 1h, now proven twice. "
            "AND AT 4h ITS OWN CONTROL WINS: over 13.7 years it reads 0.958 "
            "while a box displaced 1 ATR reads 1.010. At 1h it beats its "
            "control narrowly, 0.939 against 0.888, and stays below one."
        ),
    ),
    Layer(
        id="session",
        role="Waktu",
        family="Quarterly Theory",
        label="Cycle grid",
        kind="overlay",
        params="session",
        note="New York quarters and true opens, at eight nesting degrees.",
        evidence=(
            "The grid itself passes 26 property checks on 73,956 quarters, with "
            "no gap and no overlap. That is CONSISTENCY, not predictive value: "
            "nothing connects a quarter to an outcome.\n\n"
            "The eighth degree is `quadrennial`, four years with the US "
            "presidential election year as Q2, so 2024 and 2028 are Q2 and 2026 "
            "is Q4. Its anchor is a fact rather than a fitted number, which is "
            "the only reason it could be built at all. Its true open needs the "
            "approximate rule: Q2 opens on 1 January, the market is shut on 1 "
            "January every year, and under the strict rule the level measured "
            "zero times on ten years of hourly gold."
        ),
    ),
    Layer(
        id="vortex",
        role="Bacaan, bukan objek pasar",
        label="3-6-9 dial",
        kind="overlay",
        params="session",
        note=(
            "Digital roots of ring x sector on six cycles, and which ninth of "
            "each the newest bar sits in. Navigation only: it reads no price."
        ),
        evidence=(
            "NONE, and this layer is EXEMPT from the measurement standard "
            "rather than failing it - there is nothing here to measure. The "
            "dial is digital_root(r * k), which is arithmetic on the calendar: "
            "a cell lands in {3, 6, 9} exactly when 3 divides r * k, so rings "
            "1, 2, 4 and 5 light k = 3, 6 and 9 and rings 3 and 6 light every "
            "sector. That is a fact about multiples of three, not about this "
            "market. It carries no price, no level and no direction, and "
            "nothing downstream of the renderer reads it: `tests/test_vortex.py` "
            "asserts that seam against the execution modules by name. Twelve "
            "pre-registered directional hypotheses have failed in this project, "
            "so an unmeasured geometric construct does not get on the decision "
            "path for looking convincing."
        ),
    ),
    Layer(
        id="gaps",
        role="Celah harga",
        family="ICT",
        label="Opening gaps",
        kind="overlay",
        params="gaps",
        note="NDOG and NWOG bands, and the event horizons between them.",
        evidence=(
            "No disclosed study exists by anyone. MEASURED HERE 2026-08-20 and "
            "NULL: respect at the first touch of the consequent encroachment, "
            "n=1955 touches from 1971 bands over four instruments, came out "
            "-0.58 ATR - price CONTINUES through it - at t=-2.54, which fails "
            "the Bonferroni bar of 0.01, and walk-forward 2 of 8. Not reliable "
            "in either direction. The median first touch is 3 bars after the "
            "18:00 bar, so half of all touches are the gap simply being filled. "
            "Doctrine, drawn as doctrine."
        ),
    ),
    Layer(
        id="chart_gaps",
        role="Celah harga",
        label="Breakaway and measuring gaps",
        kind="overlay",
        params="chart_gaps",
        note=(
            "Trend gaps (Edwards-Magee): a bar that opens past the last bar's "
            "extreme, with its halfway projection target."
        ),
        evidence=(
            "MEASURED 1 September 2026, docs/gap_outcomes.json, and the "
            "classification is the headline: NOT ONE breakaway gap exists on "
            "nine instruments over their full history. flat_atr is 2,0 and a "
            "20-bar window's range never gets that small - minimum observed "
            "2,085, median near 4,7 - so every gap this engine has drawn is a "
            "measuring gap and the BK tag has never appeared. Of the rest: the "
            "continuation direction does not beat the instrument's own drift "
            "(t=-0,56 clustered, bar 2,73) and the halfway target is not "
            "reached more than the same bracket one horizon earlier (t=-1,16). "
            "The band IS reached sooner than the equidistant level on the "
            "other side, -2,70 bars at t=-3,65, negative on all nine - and "
            "that result DID NOT SURVIVE its own control. Against a band "
            "matched on distance, height and SIDE at a gap-free bar the gap is "
            "reached -0,69 bars sooner at t=-1,06, null, and the nine-of-nine "
            "consistency falls to seven. The mirror was measuring which side "
            "of price the band sat on. Nothing here separates. A reading, "
            "never a bias."
        ),
    ),
    Layer(
        id="psp",
        role="Divergensi lintas instrumen",
        family="ICT",
        label="Precision swing point",
        kind="overlay",
        params="psp",
        note=(
            "A sweep of the open three bars back, rejected in the same bar, "
            "inside the three bars after an SSMT settles. Needs the SSMT "
            "partners, so it draws nothing when they cannot be loaded."
        ),
        evidence=(
            "MEASURED NULL, and both halves of the claim were asked. "
            "docs/psp_outcomes.json graded 48 cells - four pairs, three bracket "
            "widths, both directions, two hypotheses - and not one separated. "
            "The largest |z| seen was 2,10 against a Bonferroni bar of 3,28, "
            "and the run is powered to about 10,6 points of hit rate at these "
            "n. H1 asked whether a PSP after an SSMT beats a bar with no PSP; "
            "H2 asked whether the SSMT in front of it adds anything over a PSP "
            "standing alone. Both null. The triad crack rate is identical in "
            "both arms (0,2644 against 0,2644 on gold against silver), so the "
            "SSMT window does not select for the crack either. Drawn as a "
            "reading, and barred from the decision path by "
            "tests/test_psp_not_wired_to_decisions.py."
        ),
    ),
    Layer(
        id="wyckoff",
        role="Struktur dan momentum",
        label="Wyckoff phases",
        kind="overlay",
        params="wyckoff",
        note=(
            "Spring, upthrust, sign of strength and weakness over a rolling "
            "trading range. This is also the BREAKOUT layer: sos and sow are "
            "a range breakout confirmed by close, spring and upthrust are a "
            "false breakout on either side."
        ),
        evidence=(
            "MEASURED NULL TWICE, in two independent rigs. "
            "docs/QA-BREAKOUT.md: MT5 Strategy Tester at 100% real ticks, "
            "7 cells and 5.600 trades for the aggressive arm, median profit "
            "factor 1,00 and the sign 3 up 3 down 1 flat. Five of seven cells "
            "land at 33,33 to 34,99 percent win against a 2R breakeven of "
            "33,33 percent - the system pays spread to stand still. And all "
            "three variants the method prescribes make it WORSE: retest 0,96, "
            "tick-count filter 0,99, fading the fakeout 0,89 with 64 percent "
            "drawdown. "
            "docs/wyckoff_outcomes.json: four phases against "
            "the instrument's own drift over nine instruments, clustered t "
            "between -0,95 and +0,27 against a Bonferroni bar of 2,50, and "
            "13 to 20 of 36 per-symbol folds positive. The determinable "
            "subset of the Wyckoff schematic - the "
            "full schematic needs volume and discretion, see "
            "docs/specs/2026-08-31-wyckoff-design.md. These four "
            "readings map onto the structure primitives (sweep, break) that H6 "
            "and H9 already measured null, so this is a reading, never a bias."
        ),
    ),
    Layer(
        id="cisd",
        role="Struktur dan momentum",
        family="ICT",
        label="Change in state of delivery",
        kind="overlay",
        params="cisd",
        note="A close beyond the OPEN of the last opposing run.",
        evidence=(
            "No published hit rate exists. MEASURED NULL 2026-08-20: forward "
            "move at 12 bars, bullish minus bearish so drift cancels, n=23270 "
            "over four instruments, DELTA -0.0195 ATR at t=-0.53 - wrong sign "
            "and six times under the bar - and the halves flip sign in 3 of the "
            "4 series. The charged spread is 13x the (negative) edge. Also "
            "measured: two gold feeds disagree about which bars carry a CISD 29% "
            "of the time, because one flipped candle open splits or merges a "
            "whole run."
        ),
    ),
    Layer(
        id="dfr",
        role="Waktu",
        family="Quarterly Theory",
        label="Defining range",
        kind="overlay",
        params="dfr",
        note="Q1's final two thirds, its 50% equilibrium and its projections.",
        evidence=(
            "MEASURED 2026-08-30 AND NULL, after shipping single-sourced and "
            "unverified. Reach of the -0.5 and -1 extension levels within 96 "
            "bars against a per-event jitter control at the same distance: "
            "n=3358 bands over four instruments, pooled -0.06pp at m=0.5 and "
            "+0.00pp at m=1.0, 0 of 10 groups pass, best cell +1.02pp at |t| "
            "2.39 against a Bonferroni bar of 2.807 and walk-forward 6 of 8. "
            "Real reach is high everywhere, 77.89% against a placebo 77.95%, "
            "and that is distance rather than the thirds rule. Evidence in "
            "docs/dfr_outcomes.json. SEPARATELY the `dfr_side` CLAUSE does "
            "separate, with its sign INVERTED - see MEASURED_AGAINST in "
            "app/ict.py. What follows is what was known before those runs. "
            "The thirds rule reached this project from one description of a "
            "closed-source indicator and has never been checked against the "
            "course material it came from, let alone against outcomes. Four "
            "property tests pass on three instruments, which is implementation "
            "CONSISTENCY. The source gives the -0.5 and -1 extensions no "
            "direction, so both sides are drawn rather than one being chosen."
        ),
    ),
    Layer(
        id="ssmt",
        role="Divergensi lintas instrumen",
        family="ICT",
        label="SSMT divergence",
        kind="overlay",
        # SHARES THE CHECKLIST'S BLOCK rather than duplicating three fields, the
        # same way four detectors share `imbalance`. `ssmt_symbols`,
        # `ssmt_degrees` and `ssmt_provider` already exist there and already
        # drive the same computation; a second copy would be two places to set
        # one basket and two chances for them to disagree.
        params="checklist",
        note="The cross-instrument divergence, drawn on this symbol's own price.",
        evidence=(
            "The RATE is almost entirely the pair you choose, measured 14.9% "
            "against silver and 59.5% against DXY at day degree - an inversely "
            "correlated partner disagrees by construction. MEASURED 2026-08-30 "
            "AND NULL: bracket resolution on the bar a divergence becomes "
            "knowable, against non-divergence bars of the same instrument, "
            "same bracket, same ATR unit - an empirical control rather than "
            "the 50% a symmetric bracket assumes. 24 cells over four pairs, "
            "three bracket widths and two sides, n_event 338 to 555 per cell: "
            "0 pass, largest |z| 2.070 against a Bonferroni bar of 3.078, and "
            "the sign splits 12 positive to 12 negative. Pair correlations "
            "spanned -0.45 to +0.82. Evidence in docs/ssmt_outcomes.json. "
            "Drawn because it is the most "
            "frequent annotation in the reference charts, 33 of 51, and it was "
            "computed here for months while being visible only as a count."
        ),
    ),
    Layer(
        id="pools",
        role="Likuiditas dan level",
        family="ICT",
        label="Liquidity pools",
        kind="overlay",
        params="pools",
        note="Asian and London session extremes, as candidate targets.",
        evidence=(
            "MEASURED NULL, 2026-08-20. Pre-registered: an untaken session "
            "extreme is traded through within 96 bars more often than a "
            "placebo. n=7552 over four instruments, reach 72.03%. Against a "
            "SHUFFLED placebo +2.90pp, p=9.2e-05 - and that control was then "
            "shown to be defective: shuffling un-pairs a level's distance from "
            "its bar's volatility, and inside matched distance bands the gap is "
            "-0.68pp. The per-event JITTER control, which keeps the pairing, "
            "says +0.15pp. Walk-forward 4 of 8, sign test p=1.00. A taken pool "
            "is still drawn, dimmed."
        ),
    ),
    Layer(
        id="liquidity",
        role="Likuiditas dan level",
        family="ICT",
        label="Named levels",
        kind="overlay",
        params="liquidity",
        note="PDH, PDL, PWH, PWL and the named day extremes, plus ERL and IRL.",
        evidence=(
            "MEASURED NULL and the point estimate is NEGATIVE, 2026-08-20. "
            "Reach within 96 bars against a placebo at the same offset: "
            "PDH/PDL n=4152, -1.59pp [-3.28, +0.10], walk-forward 3 of 8; "
            "PWH/PWL n=747, -0.94pp, walk-forward 3 of 8. Negative on all four "
            "instruments, and the control used carries a tailwind in the "
            "overlay's favour, so the honest figure is at or below these. The "
            "draw-on-liquidity candidates are reported on each side and never "
            "resolved to one, because naming the draw is a forecast."
        ),
    ),
    Layer(
        id="projections",
        role="Likuiditas dan level",
        family="ICT",
        label="Deviation projections",
        kind="overlay",
        params="projections",
        note="Multiples of a session range projected past it.",
        evidence=(
            "MEASURED NULL 2026-08-20, and it is the largest non-zero thing in "
            "this group: reach within 96 bars off the Asian box, n=6320 levels "
            "from 2122 boxes, +0.46pp against a per-event jitter control "
            "[+0.08, +0.85] - which is 6.5x BELOW the pre-registered threshold "
            "and fails walk-forward at 6 of 8, p=0.29. The -0.5 multiple is "
            "reached 74.2% of the time and the jittered one 73.5%. Only ONE "
            "anchor and one direction rule were tested. The geometry itself was "
            "recovered from the reference chart and agrees with its price tags "
            "to 0.4 USD, which validates the TRANSCRIPTION and nothing else."
        ),
    ),
    Layer(
        id="expectation",
        role="Bacaan, bukan objek pasar",
        label="Expectation fan",
        kind="overlay",
        params="expectation",
        note=(
            "The measured distribution of resolved R for this symbol, conditioned "
            "on dfr_side, drawn as a fan at the right edge."
        ),
        evidence=(
            "A MEASUREMENT DISPLAY, never a prediction, and it shows exactly "
            "that: the only separator in the seventeen-clause checklist is "
            "dfr_side, and its sign is INVERTED - clause met -0.0660 R on n=1141, "
            "clause failed +0.1481 R on n=341 (docs/checklist_outcomes.json). "
            "So the base-rate fan is the honest centre, and where the conditioned "
            "fan departs from it, the departure is a warning, not an edge. The "
            "fan maps R to price through one R equals one ATR, the plan's own "
            "stop scale, stated rather than fitted."
        ),
    ),
    Layer(
        id="news",
        role="Waktu",
        label="Economic calendar",
        kind="overlay",
        params="news",
        note="Scheduled releases on the New York clock, from the ForexFactory feed.",
        evidence=(
            "None, and it cannot be measured from this source: only the CURRENT "
            "WEEK is published - nextweek, lastweek, thismonth and thisyear all "
            "return 404 - so there is no history to test anything against. "
            "`impact` is the feed's own label for how much attention an event "
            "gets, not a measured effect on price. What the source DOES give "
            "safely is that it publishes no `actual` value at all, so it cannot "
            "leak an outcome backwards onto a bar."
        ),
    ),
    Layer(
        id="checklist",
        role="Bacaan, bukan objek pasar",
        label="Checklist",
        kind="report",
        params="checklist",
        note="The owner's own pre-trade items, answered with their evidence.",
        evidence=(
            "MEASURED 2026-08-30. Seventeen clauses against outcomes, n=1855 "
            "over eight instruments, 1h zones resolved on 5-minute bars: ONE "
            "separates, and it is `dfr_side` with the sign INVERTED (clause "
            "met -0.0660 R on n=1141, clause failed +0.1481 R on n=341, t "
            "-3.54 and +3.41 against a Bonferroni bar of 3.267). The AGGREGATE "
            "`met` score, which tools/execute.py sorts candidates by, is NULL "
            "and points slightly the wrong way: Spearman rho -0.0268, "
            "monotonicity fails at 5 of 7 neighbouring pairs, walk-forward 5 "
            "of 8. Evidence in docs/checklist_outcomes.json. The report still "
            "deliberately carries no overall pass or fail. It fetches per bias "
            "timeframe and per SSMT instrument, and it is not alone in fetching: "
            "gaps and ssmt do too."
        ),
    ),
)

LAYER_IDS: frozenset[str] = frozenset(layer.id for layer in LAYERS)

#: Which params block on the request each layer reads, derived rather than
#: restated. `app/detect/__init__.py` used to carry its own `PARAMS_FOR` dict
#: saying the same thing for the five detectors, which is two sources for one
#: fact and the kind that drifts quietly: a detector pointed at the wrong
#: block still returns a 200 and still draws, just from the wrong knobs.
PARAMS_BY_ID: dict[str, str] = {layer.id: layer.params for layer in LAYERS}

#: The layers that draw boxes, so they can be checked against the detector
#: registry. A detector present in one and absent from the other is a control
#: wired to nothing, or a drawing nobody can switch off.
DETECTOR_IDS: frozenset[str] = frozenset(
    layer.id for layer in LAYERS if layer.kind == "detector"
)

#: The default chart: one detector, nothing else. Everything is opt-in because
#: chart ink is a measured quantity here - five detectors alone paint 31.6% of
#: it, and past roughly a third the boxes stop annotating price and become its
#: background.
DEFAULT_LAYERS: tuple[str, ...] = ("supply_demand",)


def catalogue() -> list[dict[str, object]]:
    """The registry as the API serves it, so the UI has ONE source of truth.

    The frontend used to hardcode which ids were detectors, which were overlays,
    and what each did. Every one of those lists could drift from the backend
    without anything failing, which is how a control ends up wired to nothing.
    """
    return [
        {
            "id": layer.id,
            "label": layer.label,
            "kind": layer.kind,
            "params": layer.params,
            "note": layer.note,
            "evidence": layer.evidence,
            "family": layer.family,
            "role": layer.role,
            "orderable": layer.orderable,
            "gate": layer.gate,
            "measured_intervals": (list(layer.measured_intervals)
                                   if layer.measured_intervals else None),
        }
        for layer in LAYERS
    ]

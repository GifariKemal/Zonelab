"""Turn a drawn zone into a trade plan, without inventing a direction.

Twelve pre-registered hypotheses have now failed to get DIRECTION out of these
drawings, and the last two failed in the direction opposite to their doctrine.
So this module does not decide whether to buy. It answers the questions that
were actually validated, and the split matters enough to state plainly:

    ANSWERED HERE, with measured backing
      where to enter          the proximal line, drawn to within 1.8 pixels
      where the stop goes     beyond the distal, which is the doctrine's own stop
      where the target is     the nearest live opposing zone, the "road ahead"
      how much to risk        arithmetic, once the stop distance is known
      what it costs           the researched table in app/costs.py, charged here
      how much to trust it    the two factors that survived walk-forward

    NOT ANSWERED HERE, and no field pretends otherwise
      whether price will come to this zone at all
      whether to be long or short

`direction_evidence` is therefore always None, and that is a finding rather than
a placeholder. A plan on a demand zone is what a long WOULD look like if you
already had a reason to be long. The reason has to come from you, or from
something outside this drawing.

THE CONFIDENCE FIELDS ARE COHORT RATES, NOT PROBABILITIES
`departure_held_rate` and `age_held_rate` are the measured survival rates of the
group this zone belongs to, taken from docs/CALIBRATION.md. They say how often
zones LIKE this one survived being tested at a 2 ATR bracket. They are not the
probability this trade wins, they do not include costs, and multiplying them
together would be wrong because the two factors are not independent - age and
departure were shown to be entangled when `age_bars` turned out to be the
departure gate in disguise.

`formation_score` is deliberately absent. It ranks BACKWARDS (AUC 0.464 and
0.477), so putting it in a trade plan would be worse than leaving it out.
"""

from __future__ import annotations

import math

from .models import CostSpec, LotSpec, TradePlan, Zone, ZoneSide

# Measured cohort survival at reward 2.0 ATR. Held as named constants so a doc
# edit and a code edit cannot silently disagree.
#
# DIUKUR ULANG 22 AGUSTUS 2026, DAN ANGKA LAMANYA MILIK PASAR LAIN. 0,858 dan
# 0,644 berasal dari `docs/CALIBRATION.md` tabel reliabilitas, yang diukur pada
# PAXGUSDT, BTCUSDT dan ETHUSDT dari Binance. Eksekutor mencetak keduanya sebagai
# alasan setiap order gold Exness, jadi selama ini ia mengutip survival pasar
# crypto untuk membenarkan trade CFD logam. Itu ketidakcocokan POPULASI, bukan
# soal konvensi.
#
# Angka di bawah diukur pada instrumen yang benar-benar ditradingkan, di bar 5
# menit, bracket yang sama (target 2,0 ATR dari proximal, gagal kalau sebuah bar
# CLOSE melewati distal), 5 instrumen 1 jam, n=1196 di atas gerbang dan 3428 di
# bawahnya. Dekomposisinya, supaya jelas apa yang menyebabkan apa:
#
#     kasar, mulai di bar touch (definisi calibrate)   54,3%  lawan  46,0%
#     kasar, mulai setelah bar touch                   49,2%  lawan  45,8%
#     halus 5m, mulai di bar fill                      43,0%  lawan  40,2%
#
# Jadi konvensi intrabar memakan 5,1 poin dan resolusi halus 6,2 poin lagi;
# sisanya, dari 85,8% ke 54,3%, adalah pasar yang berbeda.
#
# SELISIHNYA TIDAK SIGNIFIKAN pada sampel ini: +2,8 poin dengan t = +1,69. Yang
# masih signifikan adalah selisih EKSPEKTASI-nya, +0,124 R dengan Welch t =
# +4,82 di `docs/QA-QUANT.md` bagian 6, dan itulah angka yang layak dikutip
# sebagai alasan sebuah order.
DEPARTURE_GATE_ATR = 2.0
HELD_CLEARED_GATE = 0.430
HELD_BELOW_GATE = 0.402
#: Hold rate by AGE at touch 1, reward 2.0 ATR, from `docs/CALIBRATION.md`
#: lines 858-861: 93,6% at 1-10 bars, 75,8% at 10-59, 77,2% at 59 and up.
#:
#: THE MIDDLE BAND HELD THE WRONG NUMBER UNTIL 3 SEPTEMBER 2026. The table was
#: written as two entries with the loop falling through to the last one, so a
#: zone aged 10 to 58 bars reported 0,772 - the rate measured for the band ABOVE
#: it - instead of its own 0,758. The mistake is easy to make because the rates
#: are NOT monotone: they fall 93,6 to 75,8 and then rise slightly to 77,2, so
#: 0,772 reads like a floor and is not one. `tests/test_plan.py` asserted the
#: wrong value with the comment `# the 10-59 band` next to it, so the fixture
#: encoded the defect and the suite stayed green over it.
AGE_BANDS = ((10, 0.936), (59, 0.758))  # (upper bound in bars, held rate)

#: 59 bars and up. A SEPARATE CONSTANT, and that is a reversal of the note this
#: line replaced, which said the fallback read `AGE_BANDS[-1][1]` so there would
#: not be "a second constant holding the same 0.772". The two numbers are not the
#: same and never were; reading one off the other is what hid the error.
AGE_HELD_OLDEST = 0.772

# No published source gives a stop buffer. Seiden and the ICT material both say
# "beyond the distal" and stop there. This is stated, not swept: a swept buffer
# would be a parameter fitted to this sample, and that is the mistake this
# project has already made once with the display cap.
DEFAULT_STOP_BUFFER_ATR = 0.25


def pct(value: float) -> str:
    """Indonesian decimal comma, so a measured rate reads the same in the advisor
    as it does in docs/CALIBRATION.md. Prices keep their point: they are
    instrument quotes, not prose."""
    return f"{value:.1%}".replace(".", ",")


def _age_held_rate(age_bars: int) -> float:
    for upper, rate in AGE_BANDS:
        if age_bars < upper:
            return rate
    # The open-ended band, named rather than borrowed from the last bounded one.
    # `AGE_BANDS[-1][0]` is still the age at which that band starts, and the
    # warning in `build` reads it from there.
    return AGE_HELD_OLDEST


def build(
    zone: Zone,
    atr: float,
    now: int,
    interval_seconds: int,
    stop_buffer_atr: float = DEFAULT_STOP_BUFFER_ATR,
    equity: float | None = None,
    risk_pct: float = 0.01,
    lot: LotSpec | None = None,
    spread: float | None = None,
    costs: CostSpec | None = None,
) -> TradePlan | None:
    """The geometry of a trade at this zone, or None if it has no geometry.

    `atr` is the volatility at the zone, used only to size the stop buffer.
    `now` is the last bar's time, which fixes the zone's age. `spread`, when the
    feed supplies it, is charged to the entry and to the stop, because a stop
    is hit on the other side of the book from the entry and ignoring that
    flatters every reward figure by exactly one spread.

    `costs` is the rest of the friction - commission, slippage, the spread when
    the feed publishes none, and carry per night - from the researched table in
    app/costs.py. None means no schedule could be established for this symbol,
    and the plan then says the reward is frictionless rather than implying the
    trade is free. Nothing in `costs` moves the stop or the target: the spread
    is charged once, to the fill, and the rest is reported.
    """
    height = zone.top - zone.bottom
    if height <= 0 or atr <= 0:
        return None

    long_side = zone.side is ZoneSide.DEMAND
    way = 1.0 if long_side else -1.0
    buffer = stop_buffer_atr * atr

    entry = zone.proximal
    stop = zone.distal - way * buffer
    # A MEASURED spread always wins over the table's constant, and the order is
    # not a preference: the table's own figure is a median borrowed from the one
    # feed that publishes both sides, so this bar's actual book beats another
    # feed's typical bar every time it exists.
    assumed_spread = (
        entry * costs.spread_bp / 10_000
        if spread is None and costs is not None and costs.spread_bp is not None
        else None
    )
    cost = spread if spread is not None else (assumed_spread or 0.0)
    # Both legs pay. Entering long lifts the fill to the ask; the stop below is
    # hit on the bid. Charging one side only is the commonest way a backtest
    # quietly beats the market it was run on.
    entry_filled = entry + way * cost
    risk = abs(entry_filled - stop)
    if risk <= 0:
        return None

    target = None
    if zone.profit_zone_rr is not None:
        target = entry + way * zone.profit_zone_rr * height
    reward = abs(target - entry_filled) if target is not None else None
    reward_r = reward / risk if reward is not None else None

    # Commission, slippage and carry. None of it moves the geometry: the spread
    # above is charged ONCE, by lifting the fill a full spread and leaving the
    # stop, which is arithmetically identical to paying half a spread on each
    # leg. A review read that shape as a 2x overcharge and the arithmetic
    # refuted it, so the spread is reported inside `cost_charged` as the
    # component it already is rather than added a second time.
    cost_charged = cost_share = carry_per_night = None
    unmeasured: list[str] = []
    if costs is not None:
        if costs.carry_bp_per_night is not None:
            carry_per_night = entry * costs.carry_bp_per_night / 10_000
        for bp, label in ((costs.commission_bp, "komisi"),
                          (costs.slippage_bp, "slippage"),
                          (costs.carry_bp_per_night, "biaya menginap")):
            if bp is None:
                unmeasured.append(label)
        # Basis points of notional at the entry price, which is how every figure
        # in the table is quoted: a flat per-lot fee set when gold traded at 1200
        # is a different cost entirely at 4400, and only the relative form
        # transfers between an instrument priced at 4400 and one at 100000.
        per_turn = (costs.commission_bp or 0.0) + (costs.slippage_bp or 0.0)
        cost_charged = (
            cost + entry * per_turn / 10_000 + (carry_per_night or 0.0) * costs.nights
        )
        # No target means no reward, so there is no share to take. Not 0.0, and
        # not the cost over some conventional R multiple - the convention would
        # be the reading this project refuses to invent.
        if reward:
            cost_share = cost_charged / reward

    age_bars = max(0, (now - zone.time_from) // max(interval_seconds, 1))
    cleared = zone.departure_atr >= DEPARTURE_GATE_ATR

    # Indonesian, because these are surfaced by the advisor and the advisor is
    # the teaching surface. Mixing languages inside one panel is a defect the
    # first end-to-end run showed immediately.
    warnings: list[str] = []
    if not cleared:
        warnings.append(
            f"Kaki keluarnya {zone.departure_atr:.2f} ATR, di BAWAH gerbang "
            f"{DEPARTURE_GATE_ATR} ATR. Formasi seperti ini cuma bertahan "
            f"{pct(HELD_BELOW_GATE)}, lawan {pct(HELD_CLEARED_GATE)} yang "
            f"melewatinya."
        )
    if age_bars >= AGE_BANDS[-1][0]:
        warnings.append(
            f"Zona ini sudah berumur {age_bars} bar. Yang meluruh adalah WAKTU, "
            f"bukan jumlah sentuhan - pembacaan jumlah sentuhan ternyata perancu."
        )
    if zone.crowded_at is not None:
        warnings.append(
            "Ada zona lawan yang masuk di depannya sejak ia terbentuk, jadi jalan "
            "yang dulu jadi dasar penggambarannya sudah tidak ada lagi."
        )
    if target is None:
        warnings.append(
            "Tidak ada zona lawan hidup di depannya, jadi tidak ada target yang "
            "terukur. Angka apa pun di situ akan jadi konvensi, bukan bacaan chart."
        )
    # Spelled out rather than reusing `assumed_spread is not None`, which means
    # the same thing only because of an invariant set eighty lines above. The
    # reader here had to go and find it, and the type checker could not find it
    # at all - it flagged `costs.spread_bp` as an access on None, which was a
    # false alarm about correct code and is exactly how a checker teaches people
    # to ignore it.
    if spread is None and costs is not None and costs.spread_bp is not None:
        warnings.append(
            f"Feed ini tidak menerbitkan spread, jadi yang dibebankan adalah "
            f"konstanta {costs.spread_bp:g} bp".replace(".", ",")
            + f" dari tabel biaya ({costs.source}), bukan spread bar ini sendiri."
        )
    elif spread is None:
        warnings.append(
            "Feed ini tidak menerbitkan spread dan tabel biaya tidak punya angka "
            "penggantinya, jadi entry dan stop di sini tanpa gesekan spread sama "
            "sekali. Pada XAUUSD dari Dukascopy spreadnya nyata: mediannya 1,6 bp "
            "dan melebar lewat 2,0 USD menjelang tutup Jumat."
        )
    if costs is None:
        warnings.append(
            "Tidak ada jadwal biaya untuk simbol ini, jadi reward di atas adalah "
            "reward TANPA GESEKAN. Bukan berarti gratis, berarti belum diukur. "
            "Pada emas biaya memakan 9,4% R di jadwal sentral dan 20,5% di "
            "satu-satunya jadwal komisi yang benar-benar bisa diambil, dan di "
            "angka kedua walk-forward-nya jatuh dari 8 dari 8 ke 4 dari 8."
        )
    else:
        if costs.nights == 0:
            warnings.append(
                "Biaya di atas MENGASUMSIKAN posisi ditutup di hari yang sama "
                "(nights=0), padahal entry di zona bisa menggantung berhari-hari."
                + (
                    f" Tiap rollover yang dilewati menambah {carry_per_night:g} "
                    f"per unit, jadi kalikan sendiri dengan malam yang Anda tahan."
                    if carry_per_night else ""
                )
            )
        if unmeasured:
            warnings.append(
                f"Tabel biaya ini tidak mengukur {', '.join(unmeasured)}, jadi "
                f"komponen itu TIDAK ADA di dalam biaya yang dibebankan - hilang, "
                f"bukan nol."
            )

    lots = placeable = realised = realised_pct = margin = None
    if equity is not None and lot is not None:
        # Exness's own PnL formula: loss = volume x contractSize x price move.
        # Commission is charged on BOTH sides at OPEN, so it belongs in the
        # risk per lot rather than being netted off the result later.
        per_lot = lot.contract_size * risk + lot.commission_round_turn
        raw = (equity * risk_pct) / per_lot if per_lot > 0 else 0.0
        # FLOOR, never round to nearest. Rounding up would let realised risk
        # exceed the budget, and a risk limit that can be exceeded by rounding
        # is not a limit.
        stepped = math.floor(raw / lot.volume_step) * lot.volume_step
        stepped = min(round(stepped, 8), lot.volume_max)

        if stepped < lot.volume_min:
            # A REJECT, not a clamp up to the minimum. The minimum lot risks
            # more than the budget by construction here, so clamping would
            # silently break the very limit the caller asked for. A small
            # account with a wide stop simply cannot take this trade, and
            # saying so is the whole point.
            placeable = False
            warnings.append(
                f"Ukuran minimum {lot.volume_min:g} lot akan mempertaruhkan "
                f"{lot.volume_min * per_lot:,.2f}, di atas anggaran risiko "
                f"{equity * risk_pct:,.2f}. Akun sebesar ini tidak bisa "
                f"mengambil trade dengan stop selebar ini - dinaikkan ke lot "
                f"minimum justru melanggar batas risikonya sendiri."
            )
        else:
            lots, placeable = stepped, True
            realised = stepped * per_lot
            realised_pct = realised / equity
            margin = (
                stepped * lot.contract_size * entry_filled / lot.leverage
                if lot.leverage > 0 else 0.0
            )
            # One step is a large slice of a small account's budget, so the
            # nominal risk fraction and the real one part company exactly where
            # the user can least afford the difference.
            if abs(realised_pct - risk_pct) > 0.1 * risk_pct:
                warnings.append(
                    f"Setelah dibulatkan ke bawah ke {stepped:g} lot, risiko "
                    f"sebenarnya {realised_pct:.2%}, bukan {risk_pct:.2%} yang "
                    f"diminta. Satu langkah lot adalah bagian besar dari "
                    f"anggaran akun sekecil ini."
                )

    return TradePlan(
        zone_id=zone.id,
        side=zone.side,
        entry=round(entry_filled, 6),
        stop=round(stop, 6),
        target=round(target, 6) if target is not None else None,
        risk_per_unit=round(risk, 6),
        reward_r=round(reward_r, 2) if reward_r is not None else None,
        units=(
            round(equity * risk_pct / risk, 4)
            if equity is not None and risk > 0
            else None
        ),
        lots=lots,
        placeable=True if placeable is None else placeable,
        realised_risk=round(realised, 2) if realised is not None else None,
        realised_risk_pct=round(realised_pct, 6) if realised_pct is not None else None,
        margin_required=round(margin, 2) if margin is not None else None,
        age_bars=int(age_bars),
        departure_held_rate=HELD_CLEARED_GATE if cleared else HELD_BELOW_GATE,
        age_held_rate=_age_held_rate(int(age_bars)),
        spread_charged=(
            round(cost, 6) if spread is not None or assumed_spread is not None else None
        ),
        cost_charged=round(cost_charged, 6) if cost_charged is not None else None,
        cost_share_of_reward=round(cost_share, 6) if cost_share is not None else None,
        carry_per_night=(
            round(carry_per_night, 6) if carry_per_night is not None else None
        ),
        direction_evidence=None,
        partial_2r=(
            round(entry_filled + way * 2 * risk, 6)
            if entry_filled is not None and risk > 0
            else None
        ),
        breakeven_stop=(
            round(entry_filled, 6)
            if entry_filled is not None
            else None
        ),
        warnings=warnings,
    )

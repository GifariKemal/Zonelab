"""Turn a drawn zone into a trade plan, without inventing a direction.

Nine pre-registered hypotheses have now failed to get DIRECTION out of these
drawings, and the last two failed in the direction opposite to their doctrine.
So this module does not decide whether to buy. It answers the questions that
were actually validated, and the split matters enough to state plainly:

    ANSWERED HERE, with measured backing
      where to enter          the proximal line, drawn to within 1.8 pixels
      where the stop goes     beyond the distal, which is the doctrine's own stop
      where the target is     the nearest live opposing zone, the "road ahead"
      how much to risk        arithmetic, once the stop distance is known
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

from .models import TradePlan, Zone, ZoneSide

# Measured cohort survival at reward 2.0 ATR, from docs/CALIBRATION.md. Held as
# named constants so a doc edit and a code edit cannot silently disagree.
DEPARTURE_GATE_ATR = 2.0
HELD_CLEARED_GATE = 0.858
HELD_BELOW_GATE = 0.644
AGE_BANDS = ((10, 0.936), (59, 0.772))  # (upper bound in bars, held rate)
HELD_OLDEST = 0.772

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
    return HELD_OLDEST


def build(
    zone: Zone,
    atr: float,
    now: int,
    interval_seconds: int,
    stop_buffer_atr: float = DEFAULT_STOP_BUFFER_ATR,
    equity: float | None = None,
    risk_pct: float = 0.01,
    spread: float | None = None,
) -> TradePlan | None:
    """The geometry of a trade at this zone, or None if it has no geometry.

    `atr` is the volatility at the zone, used only to size the stop buffer.
    `now` is the last bar's time, which fixes the zone's age. `spread`, when the
    feed supplies it, is charged to the entry and to the stop, because a stop
    is hit on the other side of the book from the entry and ignoring that
    flatters every reward figure by exactly one spread.
    """
    height = zone.top - zone.bottom
    if height <= 0 or atr <= 0:
        return None

    long_side = zone.side is ZoneSide.DEMAND
    way = 1.0 if long_side else -1.0
    buffer = stop_buffer_atr * atr

    entry = zone.proximal
    stop = zone.distal - way * buffer
    cost = spread or 0.0
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
    reward_r = abs(target - entry_filled) / risk if target is not None else None

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
    if spread is None:
        warnings.append(
            "Feed ini tidak menerbitkan spread, jadi entry dan stop di sini tanpa "
            "gesekan. Tidak ada satu pun angka di proyek ini yang menyertakan "
            "biaya; pada XAUUSD dari Dukascopy biayanya nyata dan dibebankan."
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
        age_bars=int(age_bars),
        departure_held_rate=HELD_CLEARED_GATE if cleared else HELD_BELOW_GATE,
        age_held_rate=_age_held_rate(int(age_bars)),
        spread_charged=round(cost, 6) if spread is not None else None,
        direction_evidence=None,
        warnings=warnings,
    )

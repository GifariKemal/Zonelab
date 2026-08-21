"""The one cost table, so the product and the harness cannot drift apart.

Every number below was researched against a primary source and two of them
corrected an earlier figure. Until this module existed they lived exclusively in
tools/costed.py, which is how the shipped trade plan came to charge the SPREAD
ONLY: the measurement knew that costs take 9.4% of R on gold at the central
schedule and 20.5% at the only one that could actually be retrieved, and the
screen knew none of it. tools/costed.py and app/plan.py now read this file, so a
correction to a cost lands in both or in neither.

The comments ARE the table. A bp figure here without the source that produced it
is the unverified retail number this project keeps catching, so they travel with
the numbers rather than being summarised.

Layout, and it is deliberately not flattened: `COSTS` is the central estimate per
instrument, `CONSERVATIVE` is the pessimistic sourced end of the same lines, and
`BROKERS` prices one named broker whose schedule was verified. The difference
between the central and the conservative column is ENTIRELY a commission
schedule, which is why all three are reported rather than one being chosen.
"""

from __future__ import annotations

from .models import CostSpec

# COSTS ARE IN BASIS POINTS OF NOTIONAL, not in price units, and that is a
# correction rather than a preference. The first version of this table used
# 0.07 and 0.02 in absolute USD, which are gold numbers: applied unchanged to
# BTC near 100000 they are roughly 0.00009 bp, so the "costed" column would
# have been free trading wearing a costed label. Any figure meant to transfer
# between an instrument priced at 4400 and one priced at 100000 has to be
# relative to price.
#
# Per instrument, because a gold CFD and a Binance spot pair are not charged
# the same way. `spread_bp` is used ONLY where the feed publishes no spread:
# Dukascopy XAUUSD carries a measured one per bar and that always wins over an
# assumption.
COSTS = {
    # 7 USD round turn per 100oz lot is 0.07 per ounce, which at gold near 4400
    # is 0.16bp - not 1.6bp, an arithmetic slip that made the first conversion
    # ten times too harsh and knocked 0.07R off the answer before it was caught.
    #
    # That 0.16bp is honest arithmetic on an UNVERIFIED premise. The only gold
    # commission schedule that could actually be retrieved is IBKR's, at 1.5bp
    # per side, so 3.0bp round turn - nineteen times higher. The retail "3.50
    # USD per side per lot" figure is repeated everywhere and published nowhere.
    # Part of why it looks so cheap in bp is real: retail per-lot commissions
    # are flat USD amounts set when gold traded at 1200 to 1800, and gold has
    # since tripled, so the same fee has quietly fallen from about 0.4bp to
    # 0.16bp. Run --conservative to see the answer at IBKR's published rate.
    #
    # Slippage was 0.05bp and that was simply wrong, not merely optimistic.
    # Measured on Dukascopy ticks: the mid moves 0.17bp in a 250ms retail round
    # trip at the median and 0.79bp at p90. A stop is a market order once
    # triggered AND is fired by a directional move, so the true figure is
    # adverse-biased above that unsigned floor. 0.5bp is the central estimate.
    "XAUUSD": {
        "commission_bp": 0.16, "slippage_bp": 0.5,
        # Used only where the feed publishes no spread, which is every gold
        # source here except Dukascopy. 1.6bp is the MEASURED median on
        # Dukascopy ticks at the London/NY overlap, so it is a real number
        # borrowed rather than an assumption invented.
        "spread_bp": 1.6,
        # Overnight financing, which was missing entirely and is not a footnote:
        # 80 bars of 15m is 20 hours against a 21:00 UTC rollover, so nearly
        # every trade crosses exactly one. IBKR publishes 1.29bp/day to borrow
        # gold short and 0.028bp/day storage long; a CFD adds an unpublished
        # markup on both sides. 1.0bp per rollover is the central estimate, and
        # Wednesday is charged triple at most venues, which can cost more than
        # the entire round turn.
        "swap_bp": 1.0,
    },
    # Binance spot: 0.1% per side and - the detail that matters here - maker
    # and taker are IDENTICAL at VIP 0, so a resting limit entry saves nothing.
    # 20bp round turn without the BNB discount, which a conservative backtest
    # should not assume. Spot ownership has no financing, unlike a gold CFD.
    #
    # 2.0bp slippage and 1.0bp spread are roughly 20x harsher than the measured
    # book for BTC (0.0016bp quoted, 0.00bp slip on a 10k order) and about right
    # for PAXG at size (2.53bp on 100k). Kept as a stated conservative
    # assumption rather than tuned per pair, and labelled as an assumption
    # because on crypto the fee is three orders of magnitude larger than the
    # spread - the fee IS the cost model and everything else is rounding.
    "_default": {
        "commission_bp": 20.0, "slippage_bp": 2.0, "spread_bp": 1.0,
        "swap_bp": 0.0,
    },
}
# Conservative alternates, run with --conservative. Not a sweep to pick from:
# both columns get reported and a decision is made on the pessimistic one.
CONSERVATIVE = {
    "XAUUSD": {"commission_bp": 3.0, "slippage_bp": 1.5, "swap_bp": 2.0},
}

# Broker profiles, run with --broker. The gap between the central and the
# conservative column above is ENTIRELY a commission schedule, so the only way
# to know which one applies to a given trader is to price their actual broker.
# A profile here must cite where its numbers came from; an uncited profile is
# the same unverified retail figure this file already warns about.
BROKERS: dict[str, dict[str, dict[str, float]]] = {
    # Verified from Exness's own Help Center, 2026-08-16. Commission is quoted
    # PER LOT PER SIDE and a XAUUSD lot is 100 troy ounces, so at gold 4400 the
    # notional is 440,000 and 1bp is 44 USD.
    #
    #   Zero        5.50/side -> 11.00 round turn -> 0.250bp
    #   Raw Spread  3.50/side ->  7.00 round turn -> 0.159bp
    #
    # Zero is the profile modelled even though Raw Spread's commission is lower,
    # because Zero is the only account whose ALL-IN cost is knowable: Exness
    # publishes no XAUUSD spread for any account type, and Zero is the one that
    # contractually commits to zero spread on its top-30 instruments for 95% of
    # the day. Raw Spread's total is commission plus an unpublished number.
    #
    # SWAP WAS 0.0 HERE AND THE TERMINAL DISAGREES. The claim was that Indonesia
    # is on Exness's Islamic swap-free country list, where the status is
    # automatic and account-wide. Read straight off the connected terminal on
    # 2026-08-20, a trial account on Exness-MT5Trial7, XAUUSD:
    #
    #     swap_mode           1  (points)
    #     swap_long      -541.4  points = -54.14 USD per 100oz lot per night
    #                            = 1.20bp at gold 4500
    #     swap_short        0.0  points = nothing at all
    #     swap_rollover3days  3  (Wednesday charged triple, so 3.61bp in one go)
    #
    # So on the account this machine is actually connected to, a LONG pays and a
    # SHORT does not. The help-centre page and the terminal cannot both be right
    # about this account, and the terminal is the one that will debit it.
    #
    # UNRESOLVED AND IT NEEDS THE OWNER: this is a TRIAL server. A live Indonesian
    # account with Islamic status may well charge nothing, in which case 0.0 was
    # right for it and wrong for this one. The measured pair is used because it
    # is the harsher of the two and because it is the only one anything here can
    # verify - but nobody should read it as a statement about a live account.
    #
    # The direction of the asymmetry is a property of the VENUE, not of gold: the
    # generic row above cites IBKR at 1.29bp a day to borrow gold short against
    # 0.028bp to store it long, which is the other way round. A CFD and a real
    # borrow charge opposite sides.
    #
    # `admin_bp` is the line that actually decides this strategy. Exness charges
    # 200 USD per lot per night on XAUUSD held past 21:00 UTC, which is 4.545bp
    # - more than THIRTEEN round-turn commissions, per rollover crossed. It is
    # discretionary, can be applied to already-open positions, and its stated
    # trigger is trading that is not "primarily within the trading day", which
    # describes this strategy exactly.
    "exness_zero": {
        "XAUUSD": {
            "commission_bp": 0.25, "slippage_bp": 0.5,
            # NOT None. A measured spread from the feed still wins, but a
            # broker profile must never blank the fallback: on a feed that
            # ships one price per bar (Yahoo, and every gold source here except
            # Dukascopy) None means no spread is charged at all, and the run
            # silently becomes spread-free. 0.15bp is the top of the range
            # Exness's own zero-spread commitment implies for its top-30
            # instruments outside the 95% window.
            "spread_bp": 0.15,
            # Measured, not cited. `swap_bp` is the LONG side; `swap_bp_short`
            # is present, so `spec()` reads it as a side-aware row and a plan on
            # a supply zone stops being charged a swap it never pays.
            "swap_bp": 1.20, "swap_bp_short": 0.0, "admin_bp": 4.545,
        },
    },
}


def row_for(symbol: str) -> str:
    """Which row of the table `symbol` resolves to, for printing.

    Exists because the fallback is invisible in the numbers alone. A costed run
    on gold that has silently landed on `_default` prints "commission 20.0bp",
    which looks like a cost rather than like a mistake unless the reader happens
    to know that 20bp is a Binance spot schedule and gold's own row is 0.16bp.
    That happened: a run invoked as `dukascopy-XAUUSD` - a string that is not a
    route, but which matched a cache file by name - was priced as crypto, and
    every expectancy in it came out deeply negative for a reason that had
    nothing to do with the market. Naming the row makes the fallback loud.
    """
    name = symbol.split(":")[-1]
    return name if name in COSTS else "_default"


def schedule(
    symbol: str, conservative: bool = False, broker: str = ""
) -> dict[str, float]:
    """The merged bp figures for `symbol`, in the harness's own dict shape.

    Falls back to `_default`, which is what the measurement arms rely on: the
    crypto series have no row of their own and the Binance schedule above is the
    stated assumption for them. `spec` deliberately does NOT fall back - see
    there for why the product cannot.

    The routing prefix is stripped because it is about WHERE the bars came from,
    not about what the instrument costs to trade. Without stripping it,
    `yahoo:XAUUSD` falls through to the crypto default and gets charged 20bp - a
    Binance fee schedule applied to a gold CFD, which would have made the
    cross-year run look catastrophic for a reason that has nothing to do with
    gold.
    """
    name = symbol.split(":")[-1]
    out = {**COSTS.get(name, COSTS["_default"])}
    if conservative:
        out.update(CONSERVATIVE.get(name, {}))
    if broker:
        # A broker profile REPLACES the generic assumption rather than layering
        # on it, because the whole point is to stop guessing what this trader
        # actually pays.
        out.update(BROKERS.get(broker, {}).get(name, {}))
    return out


def spec(
    symbol: str,
    conservative: bool = False,
    broker: str = "",
    long_side: bool = True,
) -> CostSpec | None:
    """The schedule for `symbol` as a `CostSpec`, or None if there is no row.

    None, not a zero-filled spec, and not `_default` either. `_default` is a
    Binance spot fee schedule - 20bp round turn, no financing - and charging it
    to whatever symbol a user happened to type would be fiction with a citation
    attached: it is right for the crypto series the harness names and wrong for
    any CFD, where the fee is a third of the size and the overnight line is the
    one that decides the trade. A symbol nobody measured is reported as not
    measured, the same rule `Candle.spread` follows.

    `swap_bp` and `admin_bp` are summed into `carry_bp_per_night`, because both
    are charged per rollover crossed and the plan charges them the same way. The
    two are kept apart in the table above only because the harness prices them
    differently: swap against the horizon it might hold, admin against the
    rollovers it actually crossed.
    """
    name = symbol.split(":")[-1]
    if name == "_default" or name not in COSTS:
        return None
    row = schedule(name, conservative, broker)

    # SWAP IS A SIDE, NOT AN INSTRUMENT. Measured on the connected Exness
    # terminal 2026-08-20: XAUUSD `swap_long` is -541.4 points, which on a 100
    # ounce lot is -54.14 USD a night and 1.20bp at gold 4500, while
    # `swap_short` is exactly 0.0. Summing one number for both sides charged
    # every short for a cost it never pays and let every long off one it does,
    # and that error leans the same way as the drawing: on the day it was found
    # every zone near price was a demand zone.
    #
    # `swap_bp_short` absent means the row was never measured per side, and the
    # single figure then applies to both - which is the old behaviour, kept for
    # every row nobody has taken a side-by-side reading on.
    swap = row.get("swap_bp")
    if not long_side and "swap_bp_short" in row:
        swap = row.get("swap_bp_short")
    carry = [swap, row.get("admin_bp")]
    used = [f"app/costs.py COSTS[{name}]"]
    if conservative and name in CONSERVATIVE:
        used.append("CONSERVATIVE")
    if broker and name in BROKERS.get(broker, {}):
        used.append(f"BROKERS[{broker}]")

    return CostSpec(
        commission_bp=row.get("commission_bp"),
        slippage_bp=row.get("slippage_bp"),
        spread_bp=row.get("spread_bp"),
        carry_bp_per_night=(
            None if all(v is None for v in carry) else sum(v or 0.0 for v in carry)
        ),
        carry_asymmetric="swap_bp_short" in row,
        source=" + ".join(used),
    )

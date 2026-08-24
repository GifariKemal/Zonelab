"""Place the plan the engine already produced, on a demo account, with a reason.

    python -m tools.execute --symbol mt5:XAUUSD --interval 1h            # dry run
    python -m tools.execute --symbol mt5:XAUUSD --interval 1h --send     # for real

IN `tools/` AND NOT IN `app/`, AND THAT IS THE SAFETY PROPERTY. `app/` is a
read-only drawing engine reachable from a web server; if order placement lived
there, an HTTP request could trade. Here it is an operator-run program, and the
API keeps its inability to send anything by construction rather than by review.

WHAT IT WILL NOT DO
  - trade a live account. `trade_mode` must be 0. There is no flag for this, and
    the day someone wants one, the change should be visible in a diff instead of
    reachable from a shell history;
  - place a second order for a zone the journal already shows a `placed` for -
    the zone id is now a stable key rather than a price (see `supply_demand.py`),
    which is what makes that check trustworthy;
  - act on a drawing `actionable.blockers` objects to;
  - size past the plan's own risk budget. `plan.placeable` is respected, and a
    refusal is journalled with the plan's own warning text rather than summarised.

WHAT IT DOES NOT DECIDE. Which side to trade. Both live zones qualify or neither
does; the rule is the first touch of a zone whose departure clears the gate, both
sides pooled, because that is the population every measured number in
`docs/CALIBRATION.md` and `docs/WALKFORWARD-MT5.md` was computed on. Twelve
pre-registered directional hypotheses failed in this project and this file is not
the place to add a thirteenth.
"""

from __future__ import annotations

import argparse

import numpy as np

from app import journal
from app.actionable import blockers
from app.conditions import at_bar
from app.confluence import mark_nesting
from app.costs import COST_TO_RISK_MAX, cost_to_risk, schedule, spec
from app.detect import DETECTORS
from app.ict import DOCTRINE_CLAUSES, Rules, setup as ict_setup
from app.indicators import wilder_atr
from app.models import LotSpec, SupplyDemandParams, ZoneSide
from app.plan import DEPARTURE_GATE_ATR, build
from app.portfolio import Book, Held, admits, aligned
from app.poi import confluence, other_boxes
from app.providers.base import INTERVALS
from app.resample import STEP_UP, resample
from app.ssmt import ssmt as ssmt_read
from tools import history
from tools.costed import HORIZON

#: Bars either side of a zone's own formation that still count as the SAME
#: displacement for the POI stack. Three, because a fair value gap left by the
#: leg out prints one to two bars after the base and a breaker can lag the
#: structure break by one more. Not fitted - measured against nothing, and stated
#: so a reader who disagrees has one number to change.
POI_SLACK_BARS = 3

#: MetaTrader truncates silently past this and `order_check` answers
#: `Invalid "comment" argument` without saying which argument or why. Measured on
#: the connected terminal 2026-08-21: 31 characters is accepted, 32 is not.
COMMENT_MAX = 31

#: What decision procedure produced a record. Stored on every journal line, so a
#: review months later can tell a change of market from a change of rule.
RULE = {
    "population": "first touch of a gate-clearing supply_demand zone, both sides",
    "gate": f"departure_atr >= {DEPARTURE_GATE_ATR}",
    "entry": "proximal, spread charged to the fill",
    "stop": "distal plus 0.25 ATR buffer",
    "target": "nearest live opposing zone (plan.target)",
    "exit_rule": "flat at the 21:00 UTC rollover",
    "horizon_bars": HORIZON,
}


def grounds(zone, plan) -> list[str]:
    """The measured reasons this zone is being traded, each with its number.

    Every figure here is read from code rather than retyped from a document:
    the gate and the two cohort rates are the constants `app/plan.py` holds
    precisely so a doc edit and a code edit cannot drift apart.
    """
    return [
        f"departure {zone.departure_atr} ATR clears the {DEPARTURE_GATE_ATR} gate",
        "gate margin +0.124 R, Welch t=+4.82 on 14,813 trades across 18 cells, "
        "positive in 17 of 18, walk-forward 8/8",
        f"age {plan.age_bars} bars, cohort held {plan.age_held_rate:.1%}",
        f"target is the nearest live opposing zone at {plan.target}, "
        f"{plan.reward_r}R from the entry",
    ]


def candidates(
    symbol: str,
    interval: str,
    bars: int,
    equity: float | None = None,
    risk_pct: float = 0.01,
    lot: LotSpec | None = None,
    rules: Rules | None = None,
    partners: dict[str, list] | None = None,
):
    """Every untouched gate-clearing zone with a readable target and its checklist.

    Returns triples of `(zone, plan, setup)`. Ordering is BY CHECKLIST FIRST and
    distance second: a candidate that satisfies more of the method outranks a
    nearer one that satisfies less. That is a change of behaviour from ordering by
    distance alone, and it is the point of the checklist existing.

    Untouched is the whole point: the measured population is a FIRST touch, so a
    zone price has already visited is not a member of it and its number does not
    apply.

    `equity` AND `lot` TOGETHER OR NOT AT ALL, and this is the argument that fixes
    a hole in the first version of this file. `plan.build` only sizes when it has
    both; with neither it returns `placeable=True` and `lots=None`, because a plan
    that was never asked to size cannot refuse on size. The first version read
    that True as permission and sent a hardcoded 0.01 lot, so the risk gate this
    module's docstring promised was decorative. Caught on 2026-08-21 while writing
    up the workflow.
    """
    candles = history.load(symbol, interval, bars)
    high = np.array([c.high for c in candles])
    low = np.array([c.low for c in candles])
    close = np.array([c.close for c in candles])
    params = SupplyDemandParams(max_zones_per_side=0)
    atr = float(wilder_atr(high, low, close, params.atr_period)[-1])
    zones, _ = DETECTORS["supply_demand"](candles, params)
    last = candles[-1]
    step = INTERVALS[interval]
    times = [c.time for c in candles]

    # THE REST OF THE TOOLKIT, computed once for the bar rather than once per
    # zone. `at_bar` is 16 ms and the four extra detectors are the expensive part;
    # both answer for the bar, not for the candidate, so paying per candidate
    # would buy fourteen copies of one answer.
    state = at_bar(candles, len(candles) - 1, interval)
    others = other_boxes(candles)
    rules = rules or Rules()
    # Sekali per bar, bukan sekali per zona: keduanya adalah properti instrumen
    # dan horizon, bukan properti kandidat.
    fees = schedule(symbol, False, "exness_raw")
    nights = (HORIZON * step) / 86_400
    too_costly: list[tuple[str, float]] = []

    # ONE DEGREE UP, and the zones are detected THERE rather than on these bars.
    # An H4 demand zone must not die because one M15 candle closed under it: the
    # zone belongs to its own timeframe and is judged there, which is the same
    # rule `drawing._htf_zones` follows for the chart. `mark_nesting` then stamps
    # `nested_in` on the local zones, so the checklist reads a field instead of
    # carrying a second definition of what nesting means.
    higher_name = STEP_UP.get(interval)
    if higher_name:
        higher_bars = resample(candles, higher_name, interval)
        if len(higher_bars) >= params.atr_period + 3:
            higher_zones, _ = DETECTORS["supply_demand"](higher_bars, params)
            for hz in higher_zones:
                hz.timeframe = higher_name
            mark_nesting(zones, higher_zones)

    # SSMT FROM THE BASKET ITSELF, which is the same "against" the SSMT panel has
    # always meant: a divergence needs a second instrument, and in a multi-pair
    # scan the second instrument is already loaded. Before this the clause read
    # `unknown` on every candidate because nobody handed it a partner, while the
    # partner sat in the caller's own dict.
    #
    # Aligned first, because `ssmt` compares quarter extremes and two series on
    # different grids would be compared at instants one of them never had. The
    # newest KNOWABLE event wins, and `knowable_at` is what makes that honest.
    ssmt_side: str | None = None
    bare = symbol.split(":")[-1]
    if partners and len(partners) > 1:
        grid = aligned({s: c for s, c in partners.items() if c})
        if bare in grid and len(grid) > 1:
            events, _ = ssmt_read(grid, "day")
            mine = [e for e in events
                    if bare in (e.took, e.failed) and e.knowable_at <= last.time]
            if mine:
                newest = max(mine, key=lambda e: e.knowable_at)
                # The side is read from THIS symbol's part in it: taking the low
                # is a bullish shape, failing to take the high is the same
                # reading from the other end.
                ssmt_side = newest.side if newest.took == bare else (
                    "low" if newest.side == "high" else "high"
                )

    # The minimal shape `actionable.blockers` reads. `app/drawing.py` builds the
    # API's copy of these four fields; this is the same four for a path that
    # never goes through HTTP.
    response = {
        "interval": interval,
        "candles": [{"time": c.time} for c in candles],
        "meta": {
            "bars_requested": bars,
            "bars_returned": len(candles),
            "truncated_by_provider": len(candles) < bars,
            "as_of": last.time,
        },
    }

    out = []
    for zone in zones:
        if zone.first_test_time is not None:
            continue
        if (zone.departure_atr or 0.0) < DEPARTURE_GATE_ATR:
            continue
        long_side = zone.side is ZoneSide.DEMAND
        plan = build(
            zone, atr, last.time, step, spread=last.spread,
            equity=equity, risk_pct=risk_pct, lot=lot,
            costs=spec(symbol.split(":")[-1], False, "exness_raw", long_side=long_side),
        )
        if plan is None or plan.target is None:
            continue

        # GERBANG BIAYA, dan ini gerbang yang paling mahal dilewatkan. Diukur 22
        # Agustus 2026 pada 24 sel instrumen kali timeframe: korelasi antara
        # biaya-terhadap-risiko dan ekspektasi adalah -0,9879 dengan R kuadrat
        # 0,976, dan tandanya berbalik di cost_r 0,2491. Setiap sel di bawah
        # 0,15 positif; setiap sel di atas 0,33 negatif, termasuk EURUSD 1 jam
        # pada -0,422 R dengan t = -28,9 di 1.019 trade.
        #
        # Ini BUKAN gerbang tentang instrumen. Ia tentang aritmetika: edge
        # kotornya +0,335 R, jadi biaya di atas 0,335/1,344 memakannya habis.
        # Instrumen yang sama bisa lolos di 4 jam dan gagal di 1 jam karena stop
        # 4 jam lebih lebar sementara biayanya sama, dan itu persis yang terukur.
        #
        # POPULASINYA, BUKAN PENOLAKAN YANG DI-JOURNAL. Sama kelasnya dengan
        # departure di bawah gerbang: zona yang biayanya melebihi ini bukan
        # anggota populasi yang setiap angka di CALIBRATION.md dan QA-QUANT.md
        # dihitung padanya, jadi angka itu tidak berlaku untuknya.
        ratio, _ = cost_to_risk(
            float(last.close), plan.risk_per_unit, last.spread or 0.0,
            fees, nights,
            swap_bp=fees.get("swap_bp_short" if not long_side else "swap_bp",
                             fees.get("swap_bp", 0.0)),
        )
        if ratio > COST_TO_RISK_MAX:
            too_costly.append((zone.id, ratio))
            continue

        anatomy = zone.anatomy
        born_from = times[max(0, anatomy.leg_in_from - POI_SLACK_BARS)]
        born_to = times[min(len(times) - 1, anatomy.leg_out_to + POI_SLACK_BARS)]
        stack = confluence(zone, others, last.time, born_from, born_to)
        out.append((zone, plan, ict_setup(zone, state, stack, rules,
                                          ssmt_side=ssmt_side)))

    # CHECKLIST FIRST, distance second. Two candidates that satisfy the method
    # equally are then ordered by which price reaches first, which is what the
    # measured population is about; between unequal ones the method wins.
    # DICETAK, TIDAK DISEMBUNYIKAN. Sebuah gerbang yang membuang kandidat tanpa
    # mengatakan berapa banyak terlihat sama dengan pasar yang sedang sepi.
    if too_costly:
        worst = max(too_costly, key=lambda x: x[1])
        print(f"  {len(too_costly)} zona ditolak gerbang biaya "
              f"(cost_r > {COST_TO_RISK_MAX}), terburuk {worst[1]:.3f} "
              f"pada {worst[0]}")
    out.sort(key=lambda t: (-t[2].met, abs(t[1].entry - float(close[-1]))))
    return out, response, float(close[-1])


def _terminal():
    """The connected terminal, or a refusal naming what is wrong.

    Imported here rather than at module scope so the rest of this file - and its
    tests - can be read on a machine with no MetaTrader installed.
    """
    import MetaTrader5 as mt5

    if not mt5.initialize():
        return None, f"cannot reach a MetaTrader 5 terminal: {mt5.last_error()}"
    account = mt5.account_info()
    if account is None:
        return None, f"terminal answered no account: {mt5.last_error()}"
    if account.trade_mode != 0:
        return None, (
            f"account {account.login} reports trade_mode={account.trade_mode}, "
            "and this tool sends orders to DEMO accounts only (0)"
        )
    if not account.trade_allowed:
        return None, f"account {account.login} has trading disabled in the terminal"
    return (mt5, account), ""


def place(mt5, zone, plan, symbol: str, volume: float) -> tuple[int | None, str]:
    """Send one pending order and return its ticket, or None and the reason."""
    long_side = plan.side is ZoneSide.DEMAND
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY_LIMIT if long_side else mt5.ORDER_TYPE_SELL_LIMIT,
        "price": round(plan.entry, 3),
        "sl": round(plan.stop, 3),
        "tp": round(plan.target, 3),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
        # Truncated here rather than at the call site: the terminal's own error
        # for an over-long comment does not mention length, and one debugging
        # session per caller is one too many.
        "comment": f"zonelab {zone.id}"[:COMMENT_MAX],
    }
    checked = mt5.order_check(request)
    if checked is None:
        return None, f"order_check refused to answer: {mt5.last_error()}"
    if checked.retcode != 0:
        return None, f"order_check retcode={checked.retcode} {checked.comment!r}"
    sent = mt5.order_send(request)
    if sent is None or sent.retcode != 0:
        code = None if sent is None else sent.retcode
        return None, f"order_send retcode={code} {getattr(sent, 'comment', '')!r}"
    return int(sent.order), ""


def sizing(mt5, account, symbol: str, risk_pct: float):
    """Equity and the symbol's real lot steps, from the terminal that owns them.

    `LotSpec`'s defaults are this broker's published figures; the broker's own
    answer beats a published figure the day it changes. Returns
    `(equity, lot, "")` or `(None, None, reason)`.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        return None, None, f"terminal carries no symbol {symbol!r}"
    lot = LotSpec(contract_size=info.trade_contract_size, volume_min=info.volume_min,
                  volume_max=info.volume_max, volume_step=info.volume_step)
    print(f"akun {account.login} {account.server} trade_mode={account.trade_mode} "
          f"(0=DEMO) equity {account.equity} risk {risk_pct:.1%} "
          f"lot min {info.volume_min} step {info.volume_step} "
          f"contract {info.trade_contract_size}")
    return float(account.equity), lot, ""


def gather(
    symbols: list[str],
    intervals: list[str],
    bars: int,
    equity: float | None,
    risk_pct: float,
    lots: dict[str, LotSpec] | None,
    rules: Rules,
) -> tuple[list[tuple], list[tuple[str, str, list[str]]], dict[str, list]]:
    """Candidates across every pair and timeframe, ranked once, globally.

    A STALE FEED ON ONE PAIR STOPS THAT PAIR AND NOTHING ELSE. The blockers are
    per series, because "gold's feed is behind" is not a reason to skip silver -
    and a scan that refused the whole basket for one bad series would be
    unusable on a Saturday, when exactly one of them is quiet.

    RANKED GLOBALLY, not per series. Scanning five pairs and taking the best two
    from each is not scanning five pairs; it is five scans that happen to run
    together. The whole point of a basket is that the best setup wins wherever it
    is, so every candidate goes into one list ordered by checklist then distance.

    Also returns the raw series per symbol, which the correlation guard needs and
    which would otherwise be fetched a second time.
    """
    found: list[tuple] = []
    blocked: list[tuple[str, str, list[str]]] = []
    series: dict[str, list] = {}
    # EVERY SERIES FIRST, because SSMT needs the partners before the first
    # candidate is scored. One pass that scored as it loaded would give the first
    # pair no partners and the last pair all of them, which is a checklist whose
    # answer depends on argument order.
    for symbol in symbols:
        series.setdefault(symbol.split(":")[-1],
                          history.load(symbol, intervals[0], bars))
    for symbol in symbols:
        for interval in intervals:
            lot = (lots or {}).get(symbol.split(":")[-1])
            pairs, response, price = candidates(
                symbol, interval, bars, equity, risk_pct, lot, rules, series
            )
            reasons = blockers(response)
            print(f"{symbol} {interval}  price {price}  "
                  f"{len(pairs)} kandidat lolos gerbang dan punya target"
                  + (f"  BLOCKED: {len(reasons)}" if reasons else ""))
            for reason in reasons:
                print(f"  BLOCKER: {reason}")
            if reasons:
                blocked.append((symbol, interval, reasons))
                continue
            found.extend(
                (symbol, interval, zone, plan, checklist)
                for zone, plan, checklist in pairs
            )
    found.sort(key=lambda t: (-t[4].met, abs(t[3].entry - t[3].target)))
    return found, blocked, series


def cycle(
    mt5,
    symbols: list[str] | str,
    intervals: list[str] | str,
    bars: int,
    risk_pct: float,
    max_orders: int,
    send: bool,
    equity: float | None = None,
    lots: dict[str, LotSpec] | LotSpec | None = None,
    rules: Rules | None = None,
    cap_pct: float = 0.06,
    corr_max: float = 0.70,
) -> dict:
    """ONE decision pass over every pair and timeframe. Returns a summary.

    Split out of `main` so `tools/autotrade.py` runs the SAME pass on a timer
    rather than a second copy of it. A daemon with its own copy of this logic is
    two engines that will disagree, and the one that disagrees is the one holding
    the account.

    `symbols` and `intervals` take a string for one or a list for a basket. The
    portfolio guards below only bind on a basket, and they are the reason a basket
    is not simply the same tool run five times: `--risk-pct` is per trade, and
    five trades at three percent is fifteen percent nobody chose.
    """
    rules = rules or Rules()
    doctrine_required = [c for c in rules.required if c in DOCTRINE_CLAUSES]
    if doctrine_required:
        print(f"PERINGATAN: --require mencantumkan klausa doctrine "
              f"(belum diukur): {', '.join(doctrine_required)}. "
              f"Klausa ini diterapkan karena metode mensyaratkannya, "
              f"bukan karena proyek ini punya angka untuknya.")
    if isinstance(symbols, str):
        symbols = [symbols]
    if isinstance(intervals, str):
        intervals = [intervals]
    if isinstance(lots, LotSpec) or lots is None:
        lots = {s.split(":")[-1]: lots for s in symbols} if lots else {}
    rule = {**RULE, "risk_pct": risk_pct, "ict_required": list(rules.required),
            "ict_killzones": list(rules.killzones),
            "ict_min_families": rules.min_families,
            "ict_max_conflicts": rules.max_conflicts,
            "portfolio_cap_pct": cap_pct, "corr_max": corr_max,
            "symbols": symbols, "intervals": intervals}

    ranked, blocked, series = gather(
        symbols, intervals, bars, equity, risk_pct, lots, rules
    )
    if equity is None:
        print("  CATATAN: tanpa equity, ukuran posisi dan batas portofolio TIDAK "
              "diperiksa. Ini hanya menunjukkan level")
    if send and blocked:
        for symbol, interval, reasons in blocked:
            journal.record("refused", why=[f"no order attempted on {symbol} {interval}"],
                           rule=rule, blockers=reasons)
    if not ranked:
        print("  tidak ada kandidat")
        return {"candidates": 0, "sent": 0, "blocked": len(blocked)}

    # OPEN POSITIONS COUNT TOWARDS THE CAP, and when they cannot be read the book
    # says so. A cap computed on half the book is a cap that does not bind, and
    # `Book.partial` is what makes that visible in the refusal text.
    book = Book(equity=equity or 0.0, cap_pct=cap_pct, corr_max=corr_max)
    if mt5 is not None:
        for position in (mt5.positions_get() or []):
            if position.sl:
                book.held.append(Held(
                    position.symbol,
                    abs(position.price_open - position.sl) * position.volume
                    * getattr(mt5.symbol_info(position.symbol),
                              "trade_contract_size", 1.0),
                ))
    else:
        book.partial = True

    sent = skipped = refused = 0
    for symbol, interval, zone, plan, checklist in ranked:
        if sent >= max_orders:
            break
        already = [e for e in journal.for_zone(zone.id) if e["event"] == "placed"]
        head = (f"  {symbol} {interval} {zone.kind.value} {zone.side.value}  "
                f"entry {plan.entry:.3f} stop {plan.stop:.3f} tp {plan.target:.3f}"
                f"  checklist {checklist.met}/{len(checklist.conditions)}")
        if already:
            print(f"{head}\n      SUDAH pernah diorder, ticket {already[0]['ticket']}")
            skipped += 1
            continue
        # THE ICT GATE, and it sits before the risk checks on purpose: a setup the
        # method rejects should not consume a slot, and its refusal should name
        # the clause rather than the account.
        missing = checklist.failed_required(rules)
        if missing:
            print(f"{head}\n      CHECKLIST menolak: {', '.join(missing)}")
            if send:
                journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                               rule=rule, zone_id=zone.id,
                               plan=plan.model_dump(mode="json"),
                               blockers=[f"required condition not met: {name}"
                                         for name in missing])
            refused += 1
            continue
        if not plan.placeable:
            print(f"{head}\n      TIDAK placeable: "
                  f"{plan.warnings[-1] if plan.warnings else 'no reason given'}")
            if send:
                journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                               rule=rule, zone_id=zone.id,
                               plan=plan.model_dump(mode="json"),
                               blockers=list(plan.warnings))
            refused += 1
            continue
        # NO VOLUME UNLESS THE PLAN SIZED ONE. `placeable` defaults to True on a
        # plan that was never given equity, so it cannot stand alone as the risk
        # gate - the missing lot is what says "nobody checked".
        if send and plan.lots is None:
            why_not = ("plan carries no lot size, so the risk budget was never "
                       "computed. Pass --risk-pct and let the terminal supply the "
                       "equity, or do not send")
            print(f"{head}\n      DITOLAK: {why_not}")
            journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                           rule=rule, zone_id=zone.id,
                           plan=plan.model_dump(mode="json"), blockers=[why_not])
            refused += 1
            continue
        # THE PORTFOLIO GUARDS, last because they are about the BOOK rather than
        # about this setup: everything above can be judged on one candidate, and
        # these two need to know what is already held.
        if plan.lots is not None and equity:
            ok, why_not = admits(book, symbol.split(":")[-1],
                                 plan.realised_risk or 0.0, series)
            if not ok:
                print(f"{head}\n      PORTOFOLIO menolak: {why_not}")
                if send:
                    journal.record("refused",
                                   why=grounds(zone, plan) + checklist.why(),
                                   rule=rule, zone_id=zone.id,
                                   plan=plan.model_dump(mode="json"),
                                   blockers=[why_not])
                refused += 1
                continue
        if not send:
            # Counted, not just printed. A dry run that walks past `max_orders`
            # reports fourteen orders where a real run would place two, and a
            # preview that disagrees with the thing it previews is worse than no
            # preview. The BOOK grows here for the same reason: without it every
            # candidate clears the portfolio cap against an empty book and the
            # preview shows five orders a real run would refuse.
            print(f"{head}\n      DRY RUN, tidak dikirim")
            book.held.append(Held(symbol.split(":")[-1], plan.realised_risk or 0.0))
            sent += 1
            continue
        ticket, why_not = place(mt5, zone, plan, symbol.split(":")[-1], plan.lots)
        if ticket is None:
            print(f"{head}\n      GAGAL: {why_not}")
            journal.record("refused", why=grounds(zone, plan) + checklist.why(),
                           rule=rule, zone_id=zone.id,
                           plan=plan.model_dump(mode="json"), blockers=[why_not])
            refused += 1
            continue
        journal.record("placed", why=grounds(zone, plan) + checklist.why(),
                       rule=rule, zone_id=zone.id,
                       ticket=ticket, plan=plan.model_dump(mode="json"),
                       extra={"volume": plan.lots, "symbol": symbol,
                              "equity_at_decision": equity,
                              "realised_risk": plan.realised_risk,
                              "realised_risk_pct": plan.realised_risk_pct})
        # THE BOOK GROWS AS THE RUN PLACES, or the cap only ever sees what was
        # held BEFORE this scan and five orders in one pass would each clear a
        # check against an empty book.
        book.held.append(Held(symbol.split(":")[-1], plan.realised_risk or 0.0))
        print(f"{head}\n      TERKIRIM ticket {ticket}, {plan.lots} lot, "
              f"risiko {plan.realised_risk} ({plan.realised_risk_pct:.2%})")
        sent += 1
    print(f"  ringkas: {len(ranked)} kandidat, {sent} dikirim, {skipped} dilewati, "
          f"{refused} ditolak, {len(blocked)} deret diblokir, "
          f"risiko terkomitmen {book.committed:,.2f}")
    return {"candidates": len(ranked), "sent": sent, "skipped": skipped,
            "refused": refused, "blocked": len(blocked),
            "committed_risk": book.committed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="mt5:XAUUSD",
                        help="one pair, or a comma list for a basket")
    parser.add_argument("--interval", default="1h",
                        help="one timeframe, or a comma list. Candidates from "
                             "every pair and timeframe are ranked in ONE list")
    parser.add_argument("--max-total-risk-pct", type=float, default=0.06,
                        help="cap on risk across the whole book, open positions "
                             "included. --risk-pct is per trade and five trades "
                             "at three percent is fifteen percent nobody chose")
    parser.add_argument("--max-correlation", type=float, default=0.70,
                        help="refuse a second pair whose measured correlation "
                             "with one already held is at or past this. Gold "
                             "against silver reads 0.848 on this feed")
    parser.add_argument("--bars", type=int, default=3000)
    parser.add_argument("--max-orders", type=int, default=2)
    parser.add_argument("--risk-pct", type=float, default=0.01,
                        help="fraction of equity risked per trade. Stated on the "
                             "command line and recorded in the journal, because a "
                             "budget hidden in a default is a budget nobody chose")
    parser.add_argument("--equity", type=float, default=None,
                        help="only for a dry run. With --send the TERMINAL is the "
                             "authority and this is ignored")
    parser.add_argument(
        "--send", action="store_true",
        help="actually place the orders. Without it nothing is sent and nothing "
             "is journalled, so a dry run cannot lie about what it did",
    )
    # THE ICT CHECKLIST'S TUNING SURFACE. Every condition is evaluated and
    # reported whatever these say; `--require` is what lets one BLOCK.
    parser.add_argument(
        "--require", default="",
        help="comma list of checklist conditions that must pass, e.g. "
             "killzone,discount_or_premium,poi_families. Empty means the "
             "checklist reports and blocks nothing",
    )
    parser.add_argument(
        "--killzones", default="",
        help="comma list of kill zones that count, e.g. ny_am,london. Empty "
             "means all of them",
    )
    parser.add_argument("--min-families", type=int, default=2,
                        help="PD array families that must stack for poi_families")
    parser.add_argument("--max-conflicts", type=int, default=0,
                        help="opposite-side boxes tolerated in the band")
    args = parser.parse_args()
    rules = Rules(
        required=tuple(x.strip() for x in args.require.split(",") if x.strip()),
        min_families=args.min_families,
        max_conflicts=args.max_conflicts,
        **({"killzones": tuple(x.strip() for x in args.killzones.split(",")
                               if x.strip())} if args.killzones else {}),
    )
    rule = {**RULE, "risk_pct": args.risk_pct}

    doctrine_required = [c for c in rules.required if c in DOCTRINE_CLAUSES]
    if doctrine_required:
        print(f"PERINGATAN: --require mencantumkan klausa doctrine "
              f"(belum diukur): {', '.join(doctrine_required)}. "
              f"Klausa ini diterapkan karena metode mensyaratkannya, "
              f"bukan karena proyek ini punya angka untuknya.")

    mt5 = None
    equity = args.equity
    lot = LotSpec() if equity is not None else None
    if args.send:
        terminal, why_not = _terminal()
        if terminal is None:
            print(f"BLOCKER: {why_not}")
            journal.record("refused", why=["no order attempted"], rule=rule,
                           blockers=[why_not])
            return
        mt5, account = terminal
        equity, lot, why_not = sizing(
            mt5, account, args.symbol.split(":")[-1], args.risk_pct
        )
        if equity is None:
            print(f"BLOCKER: {why_not}")
            journal.record("refused", why=["no order attempted"], rule=rule,
                           blockers=[why_not])
            return

    cycle(mt5,
          [s.strip() for s in args.symbol.split(",") if s.strip()],
          [i.strip() for i in args.interval.split(",") if i.strip()],
          args.bars, args.risk_pct, args.max_orders, args.send, equity,
          lot, rules, args.max_total_risk_pct, args.max_correlation)


if __name__ == "__main__":
    main()

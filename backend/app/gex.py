"""Gamma exposure from a listed option chain, and the four reasons it can only
ever be REPORTED here rather than gated on.

WHAT IT IS. Dealers who are short options hedge by trading the underlying, and
the size of that hedging per one per cent move is the gamma exposure. Where
aggregate GEX is positive the hedging leans against the move, where it is
negative it leans with it. That is the claim the source's positioning layer
makes, and this module computes the number behind it.

===========================================================================
FOUR LIMITS, ALL MEASURED FROM THIS MACHINE ON 5 SEPTEMBER 2026
===========================================================================

1. THERE IS NO HISTORY, SO THERE IS NO BACKTEST. Yahoo serves the CURRENT
   chain and nothing else; there is no free endpoint for a past chain. This is
   the same shape of blocker `app/news.py` carries, and it has the same
   consequence: nothing in this module can ever be measured against outcomes
   on this data, so nothing in it may ever become a gate. `app/qt.py` and
   `tools/qt_outcomes.py` refuse to score it for exactly that reason.

2. THERE ARE NO OPTIONS ON SPOT XAUUSD. None exist anywhere. The closest
   machine-readable proxy is GLD, the SPDR Gold Shares ETF, which trades at
   roughly a tenth of spot - a ratio that DRIFTS, because the trust sells gold
   to pay its expense ratio. So a GLD strike does not map onto an XAUUSD price
   by any fixed constant, and `RATIO_IS_APPROXIMATE` below says so in the
   output rather than in a comment nobody reads.

3. THE FEED PUBLISHES NO GREEKS. Measured: the chain returns `strike`,
   `openInterest`, `impliedVolatility`, `bid`, `ask`, `lastPrice`,
   `inTheMoney` and no gamma, delta or vega. So gamma is computed here from
   Black-Scholes on the feed's own implied volatility, which makes it a
   MODEL OUTPUT and not an observation.

4. THE CALL-POSITIVE, PUT-NEGATIVE CONVENTION IS AN ASSUMPTION, NOT OPTION
   MATHEMATICS. Long calls and long puts BOTH have positive gamma. The sign
   flip below encodes a guess about who owns what - that dealers are net long
   calls from customer overwriting and net short puts from customer hedging.
   Public open interest does not identify dealer versus customer at all. Every
   GEX product on the market rests on the same guess; this one says so.

CONSEQUENCE, STATED ONCE. This module answers "what does the public chain
imply under a stated assumption". It does not answer "where will price go",
and twelve pre-registered directional hypotheses have already failed in this
project.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import httpx

#: Underlyings this module knows how to reach, and what each is a proxy FOR.
#: The value is the instrument a Zonelab chart would actually be showing, so a
#: caller cannot silently read SPY gamma onto a gold chart.
PROXIES: dict[str, tuple[str, str]] = {
    "XAUUSD": ("GLD", "ETF proxy, ~1:10 of spot, ratio drifts with expenses"),
    "US500": ("SPY", "ETF proxy, ~1:10 of index"),
    "USTEC": ("QQQ", "ETF proxy, ~1:41 of index"),
    "US30": ("DIA", "ETF proxy, ~1:100 of index"),
}

#: Option contract multiplier for US listed equity and ETF options.
CONTRACT_SIZE = 100

#: Risk free rate used by the Black-Scholes gamma. A CONSTANT, and it is a
#: choice rather than a measurement: gamma is very insensitive to it near the
#: money, and fetching a live curve would add a second unmeasurable input to a
#: number that is already a model output. Stated so it can be argued with.
RISK_FREE = 0.04

#: Seconds a fetched chain is reused. Ten minutes, because open interest is a
#: PRIOR NIGHT snapshot that does not change intraday at all - refetching it
#: faster buys nothing and spends someone's rate limit.
CACHE_SECONDS = 600

#: The ratio between an ETF and its underlying is never exact and never fixed.
RATIO_IS_APPROXIMATE = True

_cache: dict[str, tuple[float, dict]] = {}


@dataclass
class GexRead:
    """Aggregate gamma exposure, plus everything needed to distrust it."""

    proxy: str
    spot: float
    total_gex: float
    #: Signed dollar GEX per one per cent move, by strike. Descending by
    #: absolute size, capped at `top` entries by the caller.
    by_strike: list[dict] = field(default_factory=list)
    #: The strike at which cumulative GEX crosses zero, when it crosses. None
    #: is a real answer: a chain entirely one sign has no flip.
    flip: float | None = None
    call_wall: float | None = None
    put_wall: float | None = None
    expirations: int = 0
    contracts: int = 0
    note: str = ""


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_gamma(spot: float, strike: float, years: float, vol: float,
             rate: float = RISK_FREE) -> float:
    """Black-Scholes gamma. Same for a call and a put at the same strike.

    Returns 0.0 for inputs that make gamma undefined rather than raising: an
    expired contract, a zero or negative implied volatility, a non-positive
    price. The feed publishes all three, and a chain that throws on one bad row
    is a chain that never gets read.
    """
    if spot <= 0 or strike <= 0 or years <= 0 or vol <= 0:
        return 0.0
    sigma = vol * math.sqrt(years)
    if sigma <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / sigma
    return _norm_pdf(d1) / (spot * sigma)


def _crumb(client: httpx.Client) -> str:
    """Yahoo's anti-automation crumb.

    The options endpoint answers 401 without it - measured from this machine,
    89 bytes, 0.72 seconds. The cookie call answers 404 and STILL sets the
    cookie the crumb call needs, which is why its status is ignored rather
    than checked.
    """
    client.get("https://fc.yahoo.com")
    got = client.get("https://query1.finance.yahoo.com/v1/test/getcrumb")
    crumb = got.text.strip()
    if not crumb or "<" in crumb:
        raise RuntimeError("Yahoo tidak memberi crumb; chain tidak terjangkau")
    return crumb


def fetch_chain(proxy: str, expirations: int = 3) -> dict:
    """The nearest `expirations` chains for `proxy`, cached.

    Raises rather than returning empty. An unreachable chain is a fact the
    caller has to show the user, and a silent empty dict would render as a
    gamma exposure of zero - which is a NUMBER, and a wrong one.
    """
    now = time.time()
    hit = _cache.get(proxy)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    with httpx.Client(headers=headers, timeout=25.0, follow_redirects=True) as c:
        crumb = _crumb(c)
        base = f"https://query1.finance.yahoo.com/v7/finance/options/{proxy}"
        first = c.get(base, params={"crumb": crumb})
        first.raise_for_status()
        result = first.json()["optionChain"]["result"][0]
        dates = list(result.get("expirationDates", []))[:expirations]
        chains = list(result.get("options", []))
        for date in dates[1:]:
            more = c.get(base, params={"crumb": crumb, "date": date})
            if more.status_code != 200:
                continue
            chains.extend(more.json()["optionChain"]["result"][0]["options"])

    payload = {"quote": result.get("quote", {}), "options": chains}
    _cache[proxy] = (now, payload)
    return payload


def compute(payload: dict, proxy: str, top: int = 12) -> GexRead:
    """Aggregate signed GEX from a fetched chain.

    Calls positive, puts negative - see limit 4 in the module docstring. The
    per-strike figure is dollar gamma per one per cent move:

        gamma * open_interest * 100 * spot^2 * 0.01

    A strike with zero open interest contributes nothing and is dropped rather
    than carried as a zero, so `contracts` counts what actually mattered.
    """
    spot = float(payload.get("quote", {}).get("regularMarketPrice") or 0.0)
    buckets: dict[float, float] = {}
    calls: dict[float, float] = {}
    puts: dict[float, float] = {}
    contracts = 0
    now = time.time()

    for chain in payload.get("options", []):
        for side, sign, store in (("calls", 1.0, calls), ("puts", -1.0, puts)):
            for row in chain.get(side, []):
                oi = float(row.get("openInterest") or 0.0)
                vol = float(row.get("impliedVolatility") or 0.0)
                strike = float(row.get("strike") or 0.0)
                expiry = float(row.get("expiration") or 0.0)
                if oi <= 0 or strike <= 0 or expiry <= now:
                    continue
                years = (expiry - now) / (365.25 * 86_400)
                gamma = bs_gamma(spot, strike, years, vol)
                if gamma <= 0:
                    continue
                dollars = gamma * oi * CONTRACT_SIZE * spot * spot * 0.01
                buckets[strike] = buckets.get(strike, 0.0) + sign * dollars
                store[strike] = store.get(strike, 0.0) + dollars
                contracts += 1

    ranked = sorted(buckets.items(), key=lambda kv: -abs(kv[1]))
    total = sum(buckets.values())

    # Gamma flip: walk strikes upward and find where the running sum changes
    # sign. None when it never does, which is a real answer rather than a
    # missing one - a chain that is positive at every strike has no flip.
    flip = None
    running = 0.0
    for strike in sorted(buckets):
        before = running
        running += buckets[strike]
        if before != 0.0 and (before > 0) != (running > 0):
            flip = strike
            break

    return GexRead(
        proxy=proxy,
        spot=spot,
        total_gex=total,
        by_strike=[{"strike": s, "gex": g} for s, g in ranked[:top]],
        flip=flip,
        call_wall=max(calls, key=lambda s: calls[s]) if calls else None,
        put_wall=max(puts, key=lambda s: puts[s]) if puts else None,
        expirations=len(payload.get("options", [])),
        contracts=contracts,
        note=(
            "MODEL OUTPUT, NOT A MEASUREMENT. Gamma computed from Black-Scholes "
            "on the feed's implied volatility because the feed publishes no "
            "Greeks; the call-positive/put-negative split is an assumption "
            "about dealer inventory, not option mathematics. Open interest is "
            "a prior-night snapshot. There is no historical chain, so nothing "
            "here has been or can be measured against outcomes on this source."
        ),
    )


def read(symbol: str, top: int = 12) -> tuple[GexRead | None, str]:
    """GEX for the proxy of `symbol`, plus the caveat that names the proxy.

    Returns `(None, reason)` when the symbol has no proxy or the chain could
    not be reached. Never returns a zeroed reading for an absent chain.
    """
    base = symbol.split(":")[-1].upper()
    if base not in PROXIES:
        return None, f"{base} has no listed-option proxy in PROXIES"
    proxy, caveat = PROXIES[base]
    try:
        payload = fetch_chain(proxy)
    except Exception as error:  # broad on purpose: the reason IS the product
        return None, f"{proxy} chain unreachable: {type(error).__name__}"
    return compute(payload, proxy, top), caveat


def _selftest() -> None:
    """Offline. Nothing here touches the network, so it runs in the gate."""
    # Gamma is symmetric in the log-moneyness and peaks at the money.
    atm = bs_gamma(100.0, 100.0, 0.25, 0.20)
    otm = bs_gamma(100.0, 130.0, 0.25, 0.20)
    assert atm > otm > 0

    # Undefined inputs answer zero rather than raising, because the feed
    # publishes all of them and one bad row must not lose the chain.
    assert bs_gamma(100, 100, 0, 0.2) == 0.0
    assert bs_gamma(100, 100, 0.25, 0.0) == 0.0
    assert bs_gamma(0, 100, 0.25, 0.2) == 0.0
    assert bs_gamma(100, -1, 0.25, 0.2) == 0.0

    future = time.time() + 30 * 86_400
    chain = {
        "quote": {"regularMarketPrice": 100.0},
        "options": [{
            "calls": [
                {"strike": 100.0, "openInterest": 1000,
                 "impliedVolatility": 0.2, "expiration": future},
                {"strike": 110.0, "openInterest": 5000,
                 "impliedVolatility": 0.2, "expiration": future},
                # Zero open interest contributes nothing and is not counted.
                {"strike": 120.0, "openInterest": 0,
                 "impliedVolatility": 0.2, "expiration": future},
                # Already expired, so it cannot carry gamma.
                {"strike": 105.0, "openInterest": 9999,
                 "impliedVolatility": 0.2, "expiration": time.time() - 10},
            ],
            "puts": [
                {"strike": 90.0, "openInterest": 4000,
                 "impliedVolatility": 0.2, "expiration": future},
            ],
        }],
    }
    read_out = compute(chain, "TEST")
    assert read_out.contracts == 3, read_out.contracts
    assert read_out.call_wall == 110.0
    assert read_out.put_wall == 90.0
    # Puts subtract. Flipping the put's sign would raise the total, so a total
    # that ignores the sign convention is caught here.
    only_calls = compute({**chain, "options": [
        {"calls": chain["options"][0]["calls"], "puts": []}]}, "TEST")
    assert only_calls.total_gex > read_out.total_gex

    # A symbol with no proxy is refused by name, and an empty chain is never
    # reported as a gamma exposure of zero.
    missing, reason = read("EURUSD")
    assert missing is None and "no listed-option proxy" in reason
    empty = compute({"quote": {"regularMarketPrice": 100.0}, "options": []},
                    "TEST")
    assert empty.contracts == 0 and empty.call_wall is None

    print("gex selftest ok")


if __name__ == "__main__":
    _selftest()

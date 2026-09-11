"""TradingView Desktop as a bar feed, over the session it is already logged in to.

WHY THIS EXISTS AND WHY IT LOOKS LIKE THIS. The obvious reading of "get bars
from TradingView" is wrong twice over, and both wrong readings were tried first:

  1. NOT the MCP server. `tradingview-mcp` caps `data_get_ohlcv` at
     `MAX_OHLCV_BARS = 500` - its own constant, nothing to do with TradingView -
     and reads only the bars the VISIBLE chart happens to hold, which was 304 at
     the time of writing. It is also the agent's tool; a FastAPI worker cannot
     call it. What the MCP server does have is a plain CDP connection on
     127.0.0.1:9222, and that is reusable by anyone.

  2. NOT the visible chart. Driving `chart_set_symbol` to fetch would hijack the
     user's own TradingView on every draw, and `layout_switch` was separately
     measured reporting `success: true` on pane changes that `pane_list` proved
     did not happen. A feed that fights the user for their chart is not a feed.

What this uses instead is `TradingViewApi._chartApiInstance`: the authenticated
websocket the desktop app already holds open to TradingView's data servers. A
private data session is created ON that connection - `createSession`,
`chartCreateSession`, `resolveSymbol`, `createSeries`, `requestMoreData` - so
the bars arrive with the account's own entitlements and the visible chart is
never touched. Measured 12 September 2026: COMEX:GC1! 1h, 20,010 bars back to
April 2023, in 2.7 seconds.

WHAT A PREMIUM ACCOUNT DOES NOT BUY, because it was assumed and then measured:
the `series_completed` frame for COMEX comes back `delayed_streaming_600`. That
is the exchange's ten-minute delay and it is an entitlement, not a setting - CME
real-time is a separate subscription from TradingView Premium. Crypto and FX,
whose venues do not charge for the tape, arrive live. `Feed.delay_seconds`
carries this per symbol so a caller can see it rather than infer it.

THE DEPENDENCY ON A RUNNING DESKTOP is the real cost of this provider, and it is
why `available()` probes rather than assuming. No TradingView, no bars; there is
no headless fallback, and pretending otherwise would turn "the app is closed"
into a wrong number instead of a clear error.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx
import websockets

from ..models import Candle
from .base import INTERVALS, ProviderError, normalize

#: Where the desktop app's Electron process exposes CDP. Mirrors the MCP
#: server's own default, including the reason for the literal IPv4 address:
#: on some Windows machines `localhost` resolves to ::1 first and Electron's
#: --remote-debugging-port only listens on IPv4.
CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

#: Zonelab's interval vocabulary in TradingView's dialect. Minutes as bare
#: numbers, days and up as letters, which is the protocol's own spelling.
_RESOLUTION = {
    "1m": "1", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "4h": "240", "1d": "1D", "1w": "1W",
}  # fmt: skip

#: How long to wait for one fetch, in seconds. Generous because a cold symbol
#: resolve plus a deep `request_more_data` round is seconds, not milliseconds,
#: and a timeout here surfaces as "no data" which is the worst failure to guess
#: about. The in-page routine enforces its own ceiling below this one so the
#: browser side always answers before the socket gives up.
FETCH_TIMEOUT = 90.0
_PAGE_BUDGET_MS = 60000

#: Last delay this feed reported per app symbol, so a synchronous caller can
#: ask without a fetch. Populated by `feed()` and never guessed: a symbol
#: absent from here has not been fetched yet, which is a different answer
#: from "live" and is returned as None rather than as zero.
_SEEN_DELAY: dict[str, int] = {}


def delay_of(symbol: str) -> int | None:
    """Exchange delay last seen for `symbol`, or None if never fetched."""
    return _SEEN_DELAY.get(symbol.upper())


@dataclass(frozen=True)
class Feed:
    """One symbol's bars plus what the tape said about itself.

    `delay_seconds` is READ FROM THE PROTOCOL, not from a table of exchanges:
    the `series_completed` frame names the streaming mode, and a hand-kept list
    of which venues are delayed would be wrong the day an entitlement changes.
    """

    candles: list[Candle]
    delay_seconds: int
    resolved: str | None


# ---------------------------------------------------------------- the page side

#: Installed once per page and reused. It speaks TradingView's own chart
#: protocol, which is why it is here rather than expressed as a sequence of
#: small evaluate() calls: every step is answered by an asynchronous frame on a
#: shared socket, so the collection has to live where the callbacks land.
#:
#: `request_more_data` IS THE WHOLE POINT. `create_series` alone returns what
#: the server considers one page - about 5,000 bars - and the difference
#: between this provider and the 500-bar MCP path is that this one keeps asking
#: until it has what the caller wanted or the history genuinely ends.
_INSTALL_JS = r"""
(function () {
  /* ALWAYS REDEFINED, never skipped when already present. An `if (window.__zlFetch)
     return` guard here is free to write and expensive to own: the page outlives
     every restart of this app, so a stale definition from an older build keeps
     answering, and it answers PLAUSIBLY - same bars, same speed, only a renamed
     field missing. That cost an afternoon once already: the delay field came
     back null for all 26 instruments, including the COMEX contracts whose own
     protocol frame plainly said `delayed_streaming_600`, and it read as "every
     feed is live" rather than as "you are running last week's function". */
  window.__zlFetch = function (sym, res, want, budgetMs) {
    return new Promise(function (resolve) {
      var api = window.TradingViewApi && window.TradingViewApi._chartApiInstance;
      if (!api) return resolve({ error: 'no chart api' });
      var S = 'cs_zl' + Math.random().toString(36).slice(2, 10);
      var acc = {}, mode = null, resolved = null, settled = false, rounds = 0, errs = [];
      function finish() {
        if (settled) return;
        settled = true;
        try { api.removeSeries(S, 'sds_1'); } catch (e) {}
        var out = Object.keys(acc).map(function (k) { return acc[k]; });
        out.sort(function (a, b) { return a[0] - b[0]; });
        resolve({ bars: out, mode: mode, symbol: resolved, rounds: rounds, errs: errs });
      }
      function one(m) {
        try {
          if (!m) return;
          var meth = m.method || m.m, p = m.params || m.p;
          if (meth === 'symbol_resolved' && p && p[1]) resolved = p[1].pro_name || p[1].name;
          if (meth === 'data_update' && p && p.plots) {
            p.plots.forEach(function (pt) { if (pt && pt.value) acc[pt.value[0]] = pt.value; });
          }
          if (meth === 'series_completed') {
            if (p && p[1]) mode = String(p[1]);
            var have = Object.keys(acc).length;
            /* Stop on rounds as well as on count: a symbol whose history ends
               before `want` would otherwise ask forever for bars that do not
               exist, and the server answers each time with the same page. */
            if (have >= want || rounds >= 15) return finish();
            var before = have;
            rounds++;
            try {
              api.requestMoreData(S, 'sds_1', Math.min(want - have + 10, 20000), rec);
            } catch (e) { errs.push('more: ' + e.message); return finish(); }
            /* A round that added nothing is the end of the history. */
            setTimeout(function () {
              if (!settled && Object.keys(acc).length === before) finish();
            }, 8000);
          }
          if (meth && /error/.test(meth)) errs.push(meth + ' ' + JSON.stringify(p).slice(0, 160));
        } catch (e) { errs.push('handler: ' + e.message); }
      }
      /* The socket hands a bare message object to some callbacks and an array
         to others. Reading one shape and assuming the other is what made the
         first working version of this return zero bars with no error at all. */
      var rec = function (m) { if (Array.isArray(m)) m.forEach(one); else one(m); };
      try {
        api.createSession(S, { onMessage: rec });
        api.chartCreateSession(S, {});
      } catch (e) { return resolve({ error: 'session: ' + e.message }); }
      setTimeout(function () {
        try {
          api.resolveSymbol(S, 'sds_sym_1',
            '={"symbol":' + JSON.stringify(sym) + ',"adjustment":"splits"}', rec);
        } catch (e) { errs.push('resolve: ' + e.message); }
      }, 500);
      setTimeout(function () {
        try {
          api.createSeries(S, 'sds_1', 's1', 'sds_sym_1', String(res),
            Math.min(want, 5000), null, rec);
        } catch (e) { errs.push('series: ' + e.message); }
      }, 2000);
      setTimeout(finish, budgetMs);
    });
  };
  return 'installed';
})()
"""


# ---------------------------------------------------------------- the CDP side


async def _page_ws() -> str:
    """The debugger socket of the TradingView page, or a refusal saying why.

    The target list is filtered on URL rather than taken first: an Electron app
    exposes several targets - service workers, devtools, background pages - and
    evaluating chart JS in one of those fails in a way that reads like a chart
    problem.
    """
    url = f"http://{CDP_HOST}:{CDP_PORT}/json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            targets = (await client.get(url)).json()
    except Exception as exc:  # noqa: BLE001 - every failure here means the same
        raise ProviderError(
            "TradingView Desktop is not reachable on "
            f"{CDP_HOST}:{CDP_PORT}. Start it, or launch it with "
            "--remote-debugging-port=9222."
        ) from exc

    for t in targets:
        if t.get("type") == "page" and "tradingview.com" in (t.get("url") or ""):
            ws = t.get("webSocketDebuggerUrl")
            if ws:
                return ws
    raise ProviderError(
        "TradingView Desktop is running but no chart page was found. "
        "Open a chart tab and try again."
    )


async def _evaluate(expression: str, timeout: float) -> Any:
    """Run one expression in the page and return its value.

    `awaitPromise` is what makes the fetch routine usable at all: the bars
    arrive over a websocket inside the page, so the only alternative is polling
    a global from out here, which turns one call into an unbounded number.
    """
    ws_url = await _page_ws()

    async def run() -> Any:
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
            await ws.send(
                json.dumps(
                    {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": expression,
                            "awaitPromise": True,
                            "returnByValue": True,
                        },
                    }
                )
            )
            while True:
                frame = json.loads(await ws.recv())
                if frame.get("id") != 1:
                    continue
                if "error" in frame:
                    raise ProviderError(f"TradingView refused: {frame['error']}")
                result = frame.get("result") or {}
                if "exceptionDetails" in result:
                    detail = result["exceptionDetails"]
                    raise ProviderError(f"TradingView page error: {detail.get('text')}")
                return (result.get("result") or {}).get("value")

    # WITHOUT THIS the socket waits forever. `awaitPromise` hands the deadline
    # to a page that may never settle it - a chart mid-reload answers nothing
    # and never errors - and an API worker blocked on that is indistinguishable
    # from a hung server.
    try:
        return await asyncio.wait_for(run(), timeout)
    except TimeoutError as exc:
        raise ProviderError(
            f"TradingView did not answer within {timeout:.0f}s"
        ) from exc


#: A tape the protocol called delayed without saying by how much. NOT zero,
#: which is the whole point: zero means live, and a mode this function cannot
#: parse is the one case where guessing live is the expensive direction to be
#: wrong in. Callers test `!= 0`, never `> 0`.
DELAY_UNKNOWN = -1


def _delay_seconds(mode: str | None) -> int:
    """Seconds of exchange delay named by a `series_completed` streaming mode.

    The protocol spells it `delayed_streaming_600`, so the number is read out
    of the string rather than looked up - a table of which venues are delayed
    would be wrong the day an entitlement changes. Anything that is not a
    delayed mode - `streaming`, and whatever else a venue sends - is live.
    """
    if not mode or "delayed" not in mode:
        return 0
    tail = mode.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else DELAY_UNKNOWN


# ---------------------------------------------------------------- the provider


class TradingViewProvider:
    """Bars from the desktop app's own authenticated data session."""

    name = "tradingview"

    def delay_of(self, symbol: str) -> int | None:
        """Exchange delay last seen for `symbol`, or None if never fetched.

        A METHOD, not only the module function below it. `exchange_delay` looks
        this up with `getattr` on the provider INSTANCE, so a module-level
        function alone answers None forever - which is indistinguishable from
        "this feed cannot say" and is how the delay silently failed to reach
        the chart the first time.
        """
        return delay_of(symbol)

    def available(self) -> bool:
        """Is the desktop app up with a chart page open?

        Synchronous by contract and called on a request path, so it is a
        connect-and-look rather than a full evaluate: the question is whether
        this provider can be tried, and a wrong "yes" costs one clear error
        while a wrong "no" hides the feed entirely.
        """
        try:
            targets = httpx.get(f"http://{CDP_HOST}:{CDP_PORT}/json", timeout=2.0)
            return any(
                t.get("type") == "page" and "tradingview.com" in (t.get("url") or "")
                for t in targets.json()
            )
        except Exception:  # noqa: BLE001
            return False

    async def feed(self, symbol: str, interval: str, bars: int) -> Feed:
        """`fetch` plus what the tape said about itself.

        Split out rather than folded in because the delay is the one fact about
        this provider a caller most needs and the `Provider` protocol has
        nowhere to put it.
        """
        resolution = _RESOLUTION.get(interval)
        if resolution is None:
            raise ProviderError(f"tradingview has no {interval} interval")
        if interval not in INTERVALS:
            raise ProviderError(f"unknown interval {interval!r}")

        # `vendor_symbol` lives in sources.py and importing it at module scope
        # would make these two files import each other.
        from .sources import vendor_symbol

        ticker = vendor_symbol(self.name, symbol)

        await _evaluate(_INSTALL_JS, timeout=10.0)
        payload = await _evaluate(
            "window.__zlFetch("
            f"{json.dumps(ticker)}, {json.dumps(resolution)}, "
            f"{int(bars)}, {_PAGE_BUDGET_MS})",
            timeout=FETCH_TIMEOUT,
        )

        if not isinstance(payload, dict) or payload.get("error"):
            reason = (payload or {}).get("error") if isinstance(payload, dict) else None
            raise ProviderError(f"tradingview returned nothing for {symbol}: {reason}")

        rows = payload.get("bars") or []
        if not rows:
            # The in-page errors are surfaced rather than summarised: "no bars"
            # and "this symbol does not exist on your plan" need different fixes.
            errs = "; ".join(payload.get("errs") or []) or "no bars returned"
            raise ProviderError(f"tradingview has no {interval} data for {ticker}: {errs}")

        candles = [
            Candle(
                time=int(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]) if len(r) > 5 and r[5] is not None else 0.0,
            )
            for r in rows
            if r and len(r) >= 5
        ]
        delay = _delay_seconds(payload.get("mode"))
        _SEEN_DELAY[symbol.upper()] = delay
        return Feed(
            candles=normalize(candles, bars),
            delay_seconds=delay,
            resolved=payload.get("symbol"),
        )

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        return (await self.feed(symbol, interval, bars)).candles


def _selftest() -> None:
    """The two pure decisions in this file, neither of which touches the network.

    `_delay_seconds` is checked against the exact strings the protocol sends
    because it parses rather than looks up, and a parser that silently answers
    zero would report a ten-minute-old tape as live - the one error this
    provider must not make quietly.
    """
    assert _delay_seconds("delayed_streaming_600") == 600
    assert _delay_seconds("delayed_streaming_900") == 900
    assert _delay_seconds("streaming") == 0
    assert _delay_seconds(None) == 0
    # A delayed mode this cannot parse must NOT read as live. Written as its own
    # case because the first version of this function returned 0 here and the
    # first version of this test asserted that it did.
    assert _delay_seconds("delayed_streaming_unknown") == DELAY_UNKNOWN
    assert _delay_seconds("delayed_streaming_unknown") != 0

    # Every interval the app speaks has a TradingView spelling, so a new one
    # cannot be added upstream and silently fall through to "no interval".
    assert set(_RESOLUTION) == set(INTERVALS), set(INTERVALS) ^ set(_RESOLUTION)

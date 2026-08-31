"""The MetaTrader 5 terminal already running on this machine, as a data source.

Measured against the Exness terminal here on 2026-08-19, a trial account on
Exness-MT5Trial7:

    99,999 fifteen-minute XAUUSD bars returned in 0.01 seconds

That is three orders of magnitude past what every HTTP provider in this package
can reach. Binance hard-caps a page at 1000 bars, Yahoo refuses any intraday
window older than its recency wall - 8 days at 1m, 60 at 15m - and both cost a
network round trip per call. The terminal reads its own local history file, so
depth and latency both stop being the thing that shapes a measurement.

Two properties nothing else here has:

  * THIS IS THE BROKER'S OWN TAPE. Every other source is a proxy for the venue
    the user would actually trade on - binance serves tokenized gold, yahoo
    serves COMEX futures. A zone drawn from these bars sits where it sits in the
    terminal, which is the only place it can be acted on.
  * A per-bar SPREAD, in the broker's real pricing. Dukascopy was the only other
    source that carried one, and it carried a different venue's.

The cost of both: this provider exists only where a terminal is installed and
logged in, which means Windows and means nothing in CI. It is imported
defensively for exactly that reason and reports itself unavailable rather than
breaking the registry.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..models import Candle
from .base import ProviderError, normalize
from .sources import vendor_symbol

try:  # pragma: no cover - absent on any non-Windows machine, including CI
    import MetaTrader5 as _mt5
except ImportError:
    _mt5 = None

# Typed `Any` deliberately. The package ships no usable stubs, so a checker
# reads every call on it as an error on the module AND as an error on the None
# branch - twenty diagnostics that say nothing about this code. `None` remains
# the real signal and is tested for at every entry point below.
mt5: Any = _mt5

# Canonical interval -> MT5 timeframe constant. All eight map exactly, which is
# not true of any other provider here: yahoo has no native 4h and binance has no
# 1w on some symbols. Built only when the package imported, because the
# constants live on the module.
_TIMEFRAMES: dict[str, int] = (
    {}
    if mt5 is None
    else {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "30m": mt5.TIMEFRAME_M30,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
        "1w": mt5.TIMEFRAME_W1,
    }
)

#: Measured, not guessed: 99,999 returns 99,999 bars and 100,000 returns none at
#: all with `(-2, 'Terminal: Invalid params')`. A caller asking for more gets
#: fewer bars, never an empty chart with a message about parameters.
_MAX_COUNT = 99_999


#: Jeda antar percobaan `mt5.initialize()`, dalam detik. Percobaan pertama
#: tanpa jeda, jadi anggarannya 3,85 detik untuk enam percobaan.
#:
#: KENAPA RETRY SAMA SEKALI. Terminal MT5 melayani satu klien Python pada satu
#: waktu. Dengan daemon auto-trade dan uvicorn 8100 sama sama hidup, proses
#: ketiga menerima `(-6, 'Terminal: Authorization failed')`. Diukur 30 Agustus
#: 2026, 30 panggilan `history.load` berturut turut: 0 sukses, 30 gagal.
#:
#: KENAPA JADWALNYA SEPERTI INI, dan bukan sleep tetap. Diukur pada hari yang
#: sama, 20 percobaan tiap jadwal, dengan daemon dan server berjalan:
#:
#:   enam kali 50 ms         12 sukses di attempt 1, 1 di attempt 8, 7 GAGAL
#:   0,1 0,25 0,5 1,0 2,0    18 sukses di attempt 1, 1 di attempt 4, 1 gagal
#:
#: Tabrakannya sementara, jadi yang menolong adalah menunggu lebih lama, bukan
#: mencoba lebih sering.
_RETRY_WAITS = (0.1, 0.25, 0.5, 1.0, 2.0)


def _retrying(probe) -> bool:
    """`probe()` sekali, lalu sekali per jeda, sampai True atau jadwal habis.

    SATU JADWAL UNTUK DUA PEMERIKSAAN, karena keduanya menunggu hal yang sama:
    terminal yang sedang sibuk atau sedang menyambung ulang. Dua salinan jadwal
    akan menua terpisah, dan yang tertinggal adalah yang tidak ada test-nya.
    """
    if probe():
        return True
    for wait in _RETRY_WAITS:
        time.sleep(wait)
        if probe():
            return True
    return False


def _initialize_with_retry() -> bool:
    """`mt5.initialize()` yang tidak menyerah pada tabrakan sesaat.

    Yang gagal TIDAK menelan `last_error()`: pemanggil yang mengangkat
    ProviderError membaca error terakhir, jadi pesannya tetap menyebut sebab
    yang sebenarnya.
    """
    return _retrying(mt5.initialize)


def _broker_link_up() -> bool:
    """Link ke broker hidup, ditunggu kalau ia sedang berkedip.

    KENAPA INI DITUNGGU DAN BUKAN LANGSUNG DITOLAK. Cabang ini benar: terminal
    bisa terbuka sementara link broker-nya putus, dan dalam keadaan itu ia
    menyajikan history basi tanpa satu error pun. Yang salah adalah menolak
    request pada kedipan pertama. Diukur 30 Agustus 2026, 40 sampel selama 10
    detik pada hari Minggu: `terminal_info().connected` False pada 17 sampel,
    yaitu 43 persen. Itu angka yang menjelaskan kenapa `pytest` gagal di test
    yang berpindah pindah dan `tools/validate_api` mati di baris yang berbeda
    tiap run.

    Link yang benar benar mati tetap diangkat, karena ia False sepanjang
    seluruh anggaran 3,85 detik.
    """
    def up() -> bool:
        info = mt5.terminal_info()
        return bool(info is not None and info.connected)

    return _retrying(up)


class MT5Provider:
    """Bars from the local terminal. No key, no network, no rate limit."""

    name = "mt5"

    #: No network and no metered quota, so callers may ask as often as they
    #: like. `get_forming` reads this to decide whether a once-a-second poll is
    #: something it can serve fresh or something it has to cache.
    local = True

    def __init__(self) -> None:
        # ponytail: ONE lock for the whole provider, not one per symbol. The
        # MetaTrader5 package is a single process-wide connection to one
        # terminal - there is nothing per-key to hold - and a fetch measured
        # 0.01s, so serialising every call costs nothing worth a second lock.
        self._lock = asyncio.Lock()
        self._lock_loop: asyncio.AbstractEventLoop | None = None
        self._connected = False

    def _loop_lock(self) -> asyncio.Lock:
        """Lock yang milik loop yang sedang berjalan.

        Lihat `app/providers/__init__.py` di sekitar `_locks_loop` untuk sebab
        dan angkanya. Provider ini dibangun sekali di level modul
        (`app/providers/__init__.py:29`), jadi lock-nya hidup lebih lama dari
        loop mana pun yang memakainya, dan `asyncio.run` kedua di process yang
        sama bertemu lock dari loop yang sudah mati.
        """
        loop = asyncio.get_running_loop()
        if loop is not self._lock_loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    def available(self) -> bool:
        """Static capability only: is the package importable at all.

        Whether the terminal is running and logged in is a live question, and
        `probe` below is what answers it. Reporting the two as one would list
        this provider as up on a machine where the terminal is closed, and the
        user would find out by picking it and getting a 502.
        """
        return mt5 is not None

    async def probe(self) -> bool:
        if mt5 is None:
            return False
        async with self._loop_lock():
            try:
                return await asyncio.to_thread(self._connect)
            except ProviderError:
                return False

    async def fetch(self, symbol: str, interval: str, bars: int) -> list[Candle]:
        if mt5 is None:
            raise ProviderError(
                "the MetaTrader5 package is not installed - it is Windows-only, "
                "and this provider needs a terminal on this machine"
            )
        timeframe = _TIMEFRAMES.get(interval)
        if timeframe is None:
            raise ProviderError(f"mt5 has no {interval} interval")

        vendor = vendor_symbol(self.name, symbol)
        async with self._loop_lock():
            # The MetaTrader5 API is blocking C, so it goes to a thread: a
            # terminal that is busy or reconnecting would otherwise stall the
            # whole event loop, and `/api/health` would stop answering with it.
            return await asyncio.to_thread(
                self._fetch, vendor, timeframe, min(bars, _MAX_COUNT)
            )

    async def account(self) -> dict[str, object]:
        """Balance, equity and leverage from the terminal that is logged in.

        WHY THIS EXISTS. Position sizing needs an account size, and Zonelab took
        it as a number typed into a box. A typed number is stale the moment a
        position opens, and `realised_risk_pct` then reports a percentage of an
        account that no longer exists - wrong in the one direction that matters,
        because equity falls in drawdown and a stale larger figure sizes UP
        exactly when it should size down.

        EQUITY, NOT BALANCE, is what a caller should size on, and both are
        returned so the difference is visible rather than assumed: they diverge
        by the floating result of whatever is already open. Reading them live
        means a lot suggestion can change between two page loads with no
        parameter touched, which is correct and must therefore be SAID by
        whatever displays it, not left to be discovered.

        NO LOGIN AND NO SERVER NAME. The account number identifies a real
        trading account and sizing does not need it, so it is not returned and
        cannot end up in a log, a snapshot or a screenshot. `currency` is here
        because a lot size means nothing without it.

        READ ONLY. Nothing in this provider places, modifies or closes an order,
        and nothing here should ever grow that ability - the whole engine draws
        and measures, and an execution path would be a different program with a
        different trust boundary.
        """
        if mt5 is None:
            raise ProviderError(
                "the MetaTrader5 package is not installed - it is Windows-only, "
                "and this provider needs a terminal on this machine"
            )
        async with self._loop_lock():
            return await asyncio.to_thread(self._account)

    # -- everything below runs in a worker thread ----------------------------

    def _account(self) -> dict[str, object]:
        self._connect()
        info = mt5.account_info()
        if info is None:
            # The terminal answers None when it is running but not logged in,
            # which is a real state and not an error worth a traceback: reported
            # in the vendor's own terms, like every other provider failure here.
            code, text = mt5.last_error()
            raise ProviderError(
                f"the terminal is attached but has no account: mt5 error {code}: {text}"
            )
        return {
            "currency": info.currency,
            "balance": float(info.balance),
            "equity": float(info.equity),
            "free_margin": float(info.margin_free),
            "leverage": int(info.leverage),
            "read_at": int(time.time()),
        }

    def _connect(self) -> bool:
        """Attach to the running terminal, or start one, and confirm it is live.

        `initialize()` is safe to call repeatedly, but it is not free, so the
        result is remembered. `connected` is checked separately every time
        because a terminal can stay open while its broker link drops, and in
        that state it serves stale history without a single error.
        """
        if not self._connected:
            if not _initialize_with_retry():
                raise ProviderError(
                    f"cannot reach a MetaTrader 5 terminal: {mt5.last_error()}. "
                    "Open the terminal and log in, then try again."
                )
            self._connected = True

        if not _broker_link_up():
            # Do not leave a half-dead handle behind: the next call should get a
            # fresh initialize rather than inherit this one.
            self._connected = False
            mt5.shutdown()
            raise ProviderError(
                "the MetaTrader 5 terminal is open but not connected to its "
                "broker, so its history is stale"
            )
        return True

    def _fetch(self, vendor: str, timeframe: int, count: int) -> list[Candle]:
        self._connect()

        # A symbol the user has never opened is not in Market Watch, and
        # `copy_rates_from_pos` on it returns nothing with a success code -
        # which reads downstream as "this instrument has no history".
        if not mt5.symbol_select(vendor, True):
            raise ProviderError(
                f"the terminal carries no symbol '{vendor}' "
                f"({mt5.last_error()}). Check the broker's naming."
            )

        rates = mt5.copy_rates_from_pos(vendor, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            raise ProviderError(
                f"mt5 returned no bars for {vendor}: {mt5.last_error()}"
            )

        info = mt5.symbol_info(vendor)
        point = float(info.point) if info and info.point else 0.0
        offset = self._server_offset(vendor)

        candles = [
            Candle(
                time=int(row["time"]) - offset,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                # `real_volume` is exchange volume and is 0 on every forex and
                # metal symbol, where the broker has no book to report. Tick
                # count is the only activity measure that exists there, and it
                # is what the terminal's own volume histogram draws.
                volume=float(row["real_volume"] or row["tick_volume"]),
                # MT5 reports ONE spread per bar in points, not a tick-weighted
                # mean across it - so this is the same quantity dukascopy
                # measures, arrived at differently, and the two are not
                # interchangeable to the digit. Zero means the broker recorded
                # none, which is "not measured" and must stay None: see the
                # field's own description in models/primitives.py.
                spread=float(row["spread"]) * point if row["spread"] and point else None,
            )
            for row in rates
        ]
        return normalize(candles, count)

    @staticmethod
    def _server_offset(vendor: str) -> int:
        """Seconds to subtract to turn broker wall time into real UTC.

        MT5 stamps every bar in the SERVER's timezone and hands it over as an
        epoch, so a GMT+3 broker's 13:45 bar arrives claiming to be 13:45 UTC.
        Uncorrected that shifts the entire chart three hours, and nothing
        downstream can notice: `clock.py` nails the quarter grid to New York
        wall time, `drop_forming` compares a bar's end against `time.time()`,
        and both would simply be wrong by a whole number of hours.

        Measured here on 2026-08-19: Exness-MT5Trial7 runs at UTC exactly, so
        this returns 0 and changes nothing today. It is here for the Real
        account, where GMT+2 and GMT+3 are the common settings.

        The bound is what makes this safe. The last tick is only a clock reading
        while the market is OPEN; once it closes the tick goes stale by hours or
        days and the difference stops being an offset. MT5 brokers run GMT+0 to
        GMT+3, so anything outside [-30 minutes, +3.5 hours] is staleness, not a
        timezone, and is refused rather than rounded into a wrong answer.
        """
        tick = mt5.symbol_info_tick(vendor)
        if tick is None or not tick.time:
            return 0
        difference = tick.time - int(time.time())
        return round(difference / 3600) * 3600 if -1800 <= difference <= 12600 else 0

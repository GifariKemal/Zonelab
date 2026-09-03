"""Wyckoff phase readings over a rolling trading range.

This is the DETERMINABLE subset of the Wyckoff schematic, stated in the spec at
`docs/superpowers/specs/2026-08-31-wyckoff-design.md`. The full schematic has
phases that need volume or discretion (Selling Climax, Secondary Test, Last
Point of Support); those are left out rather than guessed, because this project
refuses to invent a rule a source never published. What survives is what OHLC
can actually say:

  - a TRADING RANGE (TR): the high and low of the preceding window;
  - a SPRING: a sweep below the TR low that closes back inside it;
  - an UPTHRUST: a sweep above the TR high that closes back inside;
  - a SIGN OF STRENGTH (SOS): a close above the TR high;
  - a SIGN OF WEAKNESS (SOW): a close below the TR low.

All five are geometry on bars, classified no-lookahead from the bars that
precede the event.

SUDAH DIUKUR SEKARANG, DAN HASILNYA NULL. Baris ini dulu berbunyi "nothing here
has been measured against outcomes", dan itu berhenti benar pada 31 Agustus 2026
ketika `tools/wyckoff_outcomes.py` menjalankannya. Klaim yang diuji: apakah tiap
fase mendahului move arah yang ia NAMAI, di atas drift instrumennya sendiri.
Horizon 96 bar, kontrol `excess move = forward move - symbol drift`, sembilan
instrumen (XAUUSD, XAGUSD, XPTUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, US30, USOIL),
t kritis 2,498 sesudah koreksi.

  fase        n        t        excess ATR   walk-forward
  sos      19.667    -0,95      -0,134       13 dari 36 fold positif
  sow      15.420    -0,75      -0,104       16 dari 36
  spring   15.941    -0,27      -0,036       17 dari 36
  upthrust 18.299    +0,27      +0,037       20 dari 36

DAN ITU MENJAWAB PERTANYAAN "APAKAH KITA PUNYA BREAKOUT". Punya, di sini: `sos`
adalah range breakout naik yang dikonfirmasi close, `sow` yang turun, dan
`spring`/`upthrust` adalah false breakout di kedua sisi. Keempat kuadran itu
sudah digambar DAN sudah diukur. `sos` bukan cuma null, tandanya condong SALAH:
sebuah close di atas TR high mendahului move 0,134 ATR di BAWAH drift
instrumennya, dengan 13 dari 36 fold positif, yaitu di bawah kebetulan.

Dua pengukuran bertetangga juga null di n besar: H6 menguji BOS, CHoCH dan sweep
sebagai arah (n=9.210, t=2,27, magnitudo runtuh 13x antar paruh), dan kontrol H9
sendiri adalah break biasa tanpa sweep di depannya (delta +0,119, t=1,22,
n=5.128).

Jadi ini reading, bukan bias, dan itu bukan kehati-hatian melainkan hasil ukur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Candle

Kind = Literal["spring", "upthrust", "sos", "sow"]


@dataclass(frozen=True)
class WyckoffPhase:
    """One phase event against a rolling trading range."""

    kind: Kind
    at: int            # index of the event bar
    level: float       # the TR edge swept or broken
    tr_low: float
    tr_high: float
    tr_from: int       # first bar of the range window this was read against

    #: Bar pertama SESUDAH event yang memperdagangkan kembali `level`, atau
    #: None selama belum ada.
    #:
    #: DIHITUNG DI SINI, BUKAN DI FRONTEND, dan itu bukan preferensi arsitektur.
    #: Retest adalah pertanyaan tentang bar, dan frontend hanya punya harga plus
    #: koordinat; menghitungnya di sana akan menaruh analisis kedua di tempat
    #: yang tidak punya deretnya. Bentuknya menyalin `taken_at` di
    #: `liquidity.py`, yang sudah menyelesaikan pertanyaan yang sama.
    #:
    #: DAN IA DIGAMBAR TERPISAH DARI BREAK-NYA, dengan alasan terukur. Bulkowski
    #: mengukur 8.765 pattern breakout turun: pullback terjadi 58 persen dari
    #: waktu dan hasilnya 53 lawan 47, dan 97 persen tipe pattern dengan
    #: breakout naik perform LEBIH BAIK TANPA throwback. Konfirmasi independen:
    #: ORB pullback entry di MNQ stop-out 80,7 persen, n=83. Jadi menggambar
    #: retest sebagai BAGIAN dari breakout akan menyandikan asumsi yang datanya
    #: tolak; ia objek sendiri yang kebetulan sering hadir.
    retested_at: int | None

    @property
    def knowable_at(self) -> int:
        return self.at


def _range(candles: list[Candle], i: int, lookback: int) -> tuple[float, float]:
    """The trading range high/low of the `lookback` bars ending before bar `i`."""
    window = candles[i - lookback:i]
    return max(c.high for c in window), min(c.low for c in window)


def _retest(candles: list[Candle], level: float, after: int) -> int | None:
    """Bar pertama sesudah `after` yang memperdagangkan kembali `level`.

    Menyentuh, bukan menembus: sebuah retest adalah harga yang kembali KE level
    itu, dan syarat menembusnya akan membuang justru kasus yang paling sering
    dibicarakan, yaitu level yang ditahan lalu dilanjutkan.
    """
    for j in range(after + 1, len(candles)):
        if candles[j].low <= level <= candles[j].high:
            return j
    return None


def phases(candles: list[Candle], lookback: int = 20) -> list[WyckoffPhase]:
    """Spring, upthrust, sign-of-strength and sign-of-weakness events.

    For each bar after the warm-up, the trading range is the high/low of the
    `lookback` bars before it, and the current bar is read against that range.
    A sweep that rejects is a spring/upthrust; a close through the edge is a
    SOS/SOW. A bar can carry at most one phase: a rejected sweep is checked
    first, because a close back inside the range is not a break of it.
    """
    out: list[WyckoffPhase] = []
    for i in range(lookback, len(candles)):
        tr_high, tr_low = _range(candles, i, lookback)
        cur = candles[i]
        # Sweep + rejection: the bar's wick crosses the edge and the close is
        # back inside. This is the same operationalisation of "purge" as
        # `app/psp.py`: the bar must have arrived from the near side.
        if cur.open >= tr_low and cur.low < tr_low and cur.close > tr_low:
            out.append(WyckoffPhase("spring", i, tr_low, tr_low, tr_high,
                                       i - lookback,
                                       _retest(candles, tr_low, i)))
            continue
        if cur.open <= tr_high and cur.high > tr_high and cur.close < tr_high:
            out.append(WyckoffPhase("upthrust", i, tr_high, tr_low, tr_high,
                                       i - lookback,
                                       _retest(candles, tr_high, i)))
            continue
        # A clean break of the edge.
        if cur.close > tr_high:
            out.append(WyckoffPhase("sos", i, tr_high, tr_low, tr_high,
                                       i - lookback,
                                       _retest(candles, tr_high, i)))
        elif cur.close < tr_low:
            out.append(WyckoffPhase("sow", i, tr_low, tr_low, tr_high,
                                       i - lookback,
                                       _retest(candles, tr_low, i)))
    return out

"""Macro Volatility Regime - the VIX/ATR percentile filter.

The M4 Quarterly model fails in historically low volatility. When the
market is range-bound or quiet, the manipulation/distribution cycle
breaks down - there is no liquidity to sweep and no expansion to ride.

This module provides two regime filters:

1. ATR Percentile: if the current ATR is in the bottom 20th percentile
   of its own history, the market is in a low-volatility chop regime.
   The engine should reduce risk or halt trading.

2. The VIX proxy: if a volatility index is available, the engine can
   use it directly. Most MT5 terminals don't carry VIX, so the ATR
   percentile is the primary filter.

USAGE:
    from app.regime import regime, ATR_PERCENTILE_THRESHOLD
    r = regime(atr_array)
    if r == "chop":
        # reduce risk to 0.5x or halt
"""

from __future__ import annotations

import numpy as np

#: The ATR percentile below which the market is in "chop" regime.
#: Bottom 20% of historical ATR values. When the current ATR is below
#: this threshold, the market lacks the volatility to sustain the
#: manipulation/distribution cycle.
ATR_PERCENTILE_THRESHOLD = 20

#: The minimum number of ATR values needed for the percentile calculation.
MIN_ATR_HISTORY = 100


def regime(atr_values: np.ndarray) -> str:
    """The current volatility regime based on ATR percentile.

    Returns:
      'chop'   - current ATR is in the bottom 20th percentile.
                 Low volatility. Reduce risk or halt.
      'normal' - current ATR is in the middle 60%.
      'wild'   - current ATR is in the top 20th percentile.
                 High volatility. Normal execution, wider stops.
    """
    if len(atr_values) < MIN_ATR_HISTORY:
        return "normal"
    current = atr_values[-1]
    if current <= 0:
        return "normal"
    lo = float(np.percentile(atr_values, ATR_PERCENTILE_THRESHOLD))
    hi = float(np.percentile(atr_values, 100 - ATR_PERCENTILE_THRESHOLD))
    if current < lo:
        return "chop"
    if current > hi:
        return "wild"
    return "normal"


# `risk_multiplier(reg)` DIHAPUS 29 Agustus 2026, dan alasannya bukan sekadar
# "tidak dipakai".
#
# Ia mengembalikan 0,5 untuk regime "chop" dan 1,0 selain itu, dengan nol
# pemanggil di seluruh repo. Yang membuatnya layak dihapus dan bukan sekadar
# ditandai: ia API siap pakai yang mengundang seseorang mengalikan ukuran
# posisi dengan angka yang tidak punya satu pun pengukuran di belakangnya.
#
# Modul ini harness PENGUKUR, diimpor `tools/quant.py` dan
# `tools/walkforward.py`, dan `regime_at` di sini memang dipakai untuk MENGUKUR
# apakah regime memisahkan hasil. Sejauh ini tidak.
#
# Pengali risiko yang benar-benar sampai ke lot cuma satu di repo ini,
# `monday_mult` di `tools/execute.py`, dan kode itu menyatakan sendiri bahwa ia
# tidak punya pengukuran dan hanya boleh tinggal karena bergerak ke arah yang
# aman. Dua pengali di dua tempat, satu tanpa pemanggil, adalah bentuk
# duplikasi yang paling mudah tersambung tanpa sengaja.

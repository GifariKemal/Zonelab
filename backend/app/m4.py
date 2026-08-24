"""M4 Freedom Model — state machine for daily execution.

Four states, one trade per day. The engine moves through the states based on
New York wall-clock time and market conditions. Once a trade is placed, the
engine is disabled until the next session.

STATE 1 — Pre-09:00 NY: Lock the HTF narrative/bias.
  Bullish if price is BELOW the stacked True Opens (TDO/TWO/TMO).
  Bearish if price is ABOVE. This is the bias for the rest of the day.

STATE 2 — 09:00-10:30 NY: The "Q3-of-Q3" Killzone.
  REJECT ALL ENTRY SIGNALS before 09:30 NY. After 09:30, scan for
  the Judas Swing — the counter-move (sweep) before the true Q3 expansion.

STATE 3 — The Trigger: Scan for exactly ONE Sequential SMT across the
  Triad. Requires displacement (FVG inside the break leg), not drift.
  Once found, move to execution.

STATE 4 — Execution: Maximum ONE trade per day. Win or lose, disable
  the engine after the trade is complete.

This module is the state definitions and the time-based transitions. The
execution logic lives in `execute.py` and `autotrade.py`; this module only
decides WHICH state the engine is in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Literal

from .clock import NY


class M4State(Enum):
    """The four states of the M4 Freedom Model."""

    LOCKED = auto()       # Pre-09:00 — HTF narrative locked
    JUDAS = auto()        # 09:00-10:30 — scan for Judas Swing
    TRIGGER = auto()      # Scan for SSMT + tCISD
    EXECUTED = auto()     # Trade placed — engine disabled


@dataclass(frozen=True)
class M4Status:
    """The engine's current state, and the facts that produced it."""

    state: M4State
    ny_time: str
    ny_hour: int
    ny_minute: int
    bias: Literal["bullish", "bearish", "unknown"] = "unknown"
    bias_reason: str = ""


#: NY time the Judas window opens. Before this, NO entry signals are valid.
JUDAS_OPEN_HOUR = 9
JUDAS_OPEN_MINUTE = 30

#: NY time the Judas window closes. After this, the engine may scan for triggers.
JUDAS_CLOSE_HOUR = 10
JUDAS_CLOSE_MINUTE = 30

#: NY time the engine is disabled for the day. After this, no new trades.
SESSION_CLOSE_HOUR = 16
SESSION_CLOSE_MINUTE = 0


def current() -> M4Status:
    """The engine's current state, based on New York wall-clock time.

    Called once per cycle by the daemon. The state determines what the
    engine is allowed to do: before 09:30 it only reads bias, between
    09:30 and 10:30 it scans for the Judas Swing, after 10:30 it scans
    for the full trigger.
    """
    now = datetime.now(tz=NY)
    hour = now.hour
    minute = now.minute
    time_str = now.strftime("%H:%M")

    if now.weekday() >= 5:
        return M4Status(state=M4State.LOCKED, ny_time=time_str,
                        ny_hour=hour, ny_minute=minute,
                        bias="unknown", bias_reason="weekend")

    if hour < JUDAS_OPEN_HOUR or (hour == JUDAS_OPEN_HOUR and minute < JUDAS_OPEN_MINUTE):
        return M4Status(state=M4State.LOCKED, ny_time=time_str,
                        ny_hour=hour, ny_minute=minute,
                        bias="unknown",
                        bias_reason="pre-09:30 — bias locked from True Opens")

    if hour < JUDAS_CLOSE_HOUR or (hour == JUDAS_CLOSE_HOUR and minute < JUDAS_CLOSE_MINUTE):
        return M4Status(state=M4State.JUDAS, ny_time=time_str,
                        ny_hour=hour, ny_minute=minute,
                        bias="unknown",
                        bias_reason="09:30-10:30 — Judas window, reject entries before 09:30")

    if hour < SESSION_CLOSE_HOUR:
        return M4Status(state=M4State.TRIGGER, ny_time=time_str,
                        ny_hour=hour, ny_minute=minute,
                        bias="unknown",
                        bias_reason="post-10:30 — scan for SSMT + tCISD trigger")

    return M4Status(state=M4State.LOCKED, ny_time=time_str,
                    ny_hour=hour, ny_minute=minute,
                    bias="unknown", bias_reason="post-16:00 — session closed")


def bias_from_opens(price: float, true_opens: list[float]) -> tuple[Literal["bullish", "bearish", "unknown"], str]:
    """Determine HTF bias from stacked True Opens.

    Bullish: price is BELOW the stacked True Opens (TDO/TWO/TMO).
    Bearish: price is ABOVE the stacked True Opens.
    Unknown: no True Opens are available.

    This is the M4 STATE 1 bias lock. It is computed once per session
    and never recalculated.
    """
    if not true_opens:
        return "unknown", "no True Opens available"
    stacked = sorted(true_opens)
    below = sum(1 for o in stacked if price < o)
    above = sum(1 for o in stacked if price > o)
    if below > above:
        return "bullish", f"price below {below}/{len(stacked)} True Opens"
    if above > below:
        return "bearish", f"price above {above}/{len(stacked)} True Opens"
    return "unknown", f"price at equilibrium of {len(stacked)} True Opens"
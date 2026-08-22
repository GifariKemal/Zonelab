"""The auto-trade switch, and the heartbeat that stops it from lying.

THE SHAPE, AND WHY IT IS NOT A BUTTON THAT TRADES. `tools/execute.py` lives
outside `app/` on purpose: the web server cannot place an order, and that is a
property of the layout rather than of anyone's care. A UI button that placed
orders would hand that ability to every HTTP request that reaches the server.

So the button writes a FLAG and nothing else. A daemon the operator started -
`tools/autotrade.py` - reads the flag each cycle and does the trading. The server
still cannot send anything, and the worst a compromised or mistaken request can
do is arm a daemon that may not be running.

THE HEARTBEAT IS THE HALF THAT MATTERS. A switch that reads ON while nothing is
running is exactly the failure this project keeps a list of: an instrument
reporting green over a crashed process. So the daemon stamps `last_seen` every
cycle and the reader reports `daemon_alive` computed from it. Enabled and alive
are two different facts and are never collapsed into one.

NOT COMMITTED. The file names an account's trading state; `.gitignore` keeps it
out for the same reason it keeps out `.journal/`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

STATE = Path(__file__).resolve().parent.parent / ".autotrade.json"

#: How long a heartbeat stays credible. Three times the daemon's own 20-second
#: cycle, so one slow cycle - a provider timeout, a fetch behind a lock - does
#: not read as a dead daemon, and a real death is visible inside a minute.
STALE_AFTER = 60


def read() -> dict[str, Any]:
    """The switch, the heartbeat, and whether that heartbeat is still credible.

    A missing or unparseable file is OFF with no daemon. Never an exception and
    never a default of ON: the failure mode of this file has to be "not trading".
    """
    raw: dict[str, Any] = {}
    if STATE.exists():
        try:
            raw = json.loads(STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    seen = int(raw.get("last_seen") or 0)
    age = max(0, int(time.time()) - seen) if seen else None
    return {
        "enabled": bool(raw.get("enabled")),
        "updated_at": int(raw.get("updated_at") or 0),
        "note": str(raw.get("note") or ""),
        "symbol": raw.get("symbol"),
        "interval": raw.get("interval"),
        "risk_pct": raw.get("risk_pct"),
        "last_seen": seen or None,
        "heartbeat_age_seconds": age,
        "daemon_pid": raw.get("daemon_pid"),
        # ENABLED AND ALIVE ARE SEPARATE. The UI has to be able to say "armed but
        # nothing is running", which is the state a reader is most likely to be
        # wrong about.
        "daemon_alive": age is not None and age <= STALE_AFTER,
    }


def _write(**fields: Any) -> dict[str, Any]:
    """Merge `fields` into the file and return the full reading.

    Read-modify-write rather than replace: the switch is written by the API and
    the heartbeat by the daemon, and neither may erase the other's field.
    """
    current: dict[str, Any] = {}
    if STATE.exists():
        try:
            current = json.loads(STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            current = {}
    current.update(fields)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(current, indent=1, sort_keys=True), encoding="utf-8")
    return read()


def arm(enabled: bool, note: str = "") -> dict[str, Any]:
    """Flip the switch. This function places no order and never will."""
    return _write(enabled=bool(enabled), updated_at=int(time.time()), note=note[:200])


def beat(symbol: str, interval: str, risk_pct: float) -> dict[str, Any]:
    """The daemon saying it is alive, and what it is armed to trade.

    The parameters are written by the DAEMON rather than by the switch, so the UI
    reports what is actually being traded instead of what somebody typed into a
    form. A daemon started on 15m while the chart shows 1h is a real mistake and
    this is where it becomes visible.
    """
    return _write(last_seen=int(time.time()), daemon_pid=os.getpid(),
                  symbol=symbol, interval=interval, risk_pct=risk_pct)

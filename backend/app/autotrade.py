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
import subprocess
import sys
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


def _still_running(pid: int) -> bool:
    """Is `pid` a live PYTHON process on this machine right now?

    NOT `os.kill(pid, 0)`. On Windows CPython implements `os.kill` as
    `OpenProcess` followed by `TerminateProcess(handle, sig)` for every signal
    except CTRL_C_EVENT and CTRL_BREAK_EVENT, so the POSIX idiom for "does this
    process exist" KILLS the daemon it was asking about, with exit code 0 and no
    log line to say why. That is the same class of accident as the window-title
    kill in `docs/QA-PRODUKSI.md` section 16 that closed the desktop: a probe
    that acts instead of observing.

    THE IMAGE NAME IS CHECKED AS WELL AS THE NUMBER, because PID reuse is real.
    A crashed daemon leaves its number behind in the switch file and the OS
    hands that number to whatever starts next; if it lands on notepad.exe, a
    check on the number alone would refuse a legitimate fresh start forever.

    It is deliberately a WEAK identity - the API server is `python.exe` too -
    and the caller carries the strong half. `owner()` only asks this question
    about a heartbeat younger than STALE_AFTER, which bounds the reuse window to
    a minute. What survives both filters is a PID reused by ANOTHER python
    process inside sixty seconds of a daemon crash; that is what the operator
    override on the daemon exists for.

    Not being able to tell answers True. Refusing to start beside a daemon that
    may be alive costs one operator flag; starting beside one that is alive
    races two processes on the same idempotency check and the same order cap.
    """
    if sys.platform == "win32":
        try:
            found = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=15,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return True
        # An absent PID answers "INFO: No tasks are running which match..." on
        # stdout with exit code 0, so the return code says nothing and the text
        # is what has to be read.
        return "python" in found.lower()
    try:
        return "python" in Path(f"/proc/{int(pid)}/cmdline").read_bytes().decode(
            "utf-8", "replace").lower()
    except OSError:
        # No /proc, or no such process. Either way there is nothing here that can
        # be shown to be a live daemon, and this project only runs the daemon on
        # Windows: the terminal provider has no wheel anywhere else.
        return False


def owner() -> dict[str, Any] | None:
    """The OTHER daemon already holding this switch, or None when it is free.

    WHY THIS EXISTS. On 29 August 2026 two identical daemons were live at once,
    PIDs 12948 and 19912, both on `mt5:XAUUSD --risk-pct 0.03`. The switch file
    carries a single `daemon_pid` field so it named 19912 and nothing anywhere
    knew about 12948, while `tools/monitor.py` reported "daemon hidup" and read
    as healthy. Both were dry run, which is the only reason it cost nothing: two
    senders would race on the same journal idempotency check and the same
    `--max-orders` cap, and both would pass a check the other was about to
    invalidate.

    THREE FACTS, NOT ONE, and each one is a way to answer None:

      1. A field that names nobody, or names us, is not a conflict.
      2. A heartbeat older than STALE_AFTER is not a conflict. This is the half
         that keeps a crashed daemon from blocking its own replacement forever,
         and it is the same staleness rule the UI already reports with.
      3. A number whose process is gone, or is no longer python, is not a
         conflict. See `_still_running` for why the number alone is not enough.

    Read-only, like everything else in this module: it reports, it does not
    signal, terminate, or write.
    """
    state = read()
    pid = state.get("daemon_pid")
    # `.get` rather than `[...]`, because this dict is also produced by fakes in
    # tests and by older switch files written before the field existed.
    if not isinstance(pid, int) or isinstance(pid, bool) or pid == os.getpid():
        return None
    if not state.get("daemon_alive"):
        return None
    if not _still_running(pid):
        return None
    return {"pid": pid,
            "heartbeat_age_seconds": state.get("heartbeat_age_seconds"),
            "symbol": state.get("symbol"), "interval": state.get("interval")}

@echo off
REM ===========================================================================
REM  Zonelab: exit-only loop. Closes positions that crossed the 21:00 UTC
REM  rollover, and does NOTHING else.
REM
REM  Double-click this file. Close the window to stop it.
REM
REM  WHY IT EXISTS SEPARATELY FROM THE DAEMON. `tools/autotrade.py` calls
REM  `exits()` inside `if state["enabled"]:`, so the only way to get the exit
REM  rule from the daemon is to arm the switch, and arming the switch also runs
REM  the entry pass. A position that is already open needs managing whether or
REM  not you want new entries, so this runs the exit on its own.
REM
REM  WHAT IT CAN AND CANNOT DO. It calls `tools.flatten --send`, which closes
REM  only positions carrying a `placed` line in this repo's journal and refuses
REM  everything else. There is no code path in it that opens a position or
REM  places an order.
REM
REM  THE NUMBER BEHIND IT. `docs/ALUR-ORDER.md` section 7, mt5:XAUUSD 1h, 50,000
REM  bars, Exness costs, gated population: holding to the 80-bar horizon gives
REM  +0.198 R (t=5.10) and flat at the rollover gives +0.221 R (t=6.74), both
REM  8 of 8 folds. The whole difference is the Friday cohort, +0.128 held
REM  against +0.218 flat, and the cost driving it is the 4.545 bp per-night
REM  administration fee Exness charges on gold past 21:00 UTC.
REM
REM  MEASURED ON GOLD ONLY. BTCUSD is EXTRAPOLATION here: the study is XAUUSD,
REM  and a carry probe on this account measured BTC swap at 0.0000 after five
REM  rollovers, so the cost mechanism the study found does not apply to it.
REM  Stated rather than hidden.
REM ===========================================================================

setlocal
cd /d "%~dp0backend"
set PYTHONPATH=.

REM 300 seconds. NOT a measured number, and said so: nothing in this repo has
REM ever measured a scan cadence. It is short enough that a position is closed
REM within five minutes of the rollover it crossed, and long enough not to hold
REM the single MT5 client against the API server on 8100.
set INTERVAL=300

echo Zonelab exit-only loop. Rollover 21:00 UTC. Ctrl-C or close to stop.
echo.

:loop
echo [%DATE% %TIME%]
.venv\Scripts\python.exe -m tools.flatten --symbol mt5:XAUUSD,mt5:BTCUSD --send
if errorlevel 1 echo   GAGAL: flatten keluar dengan status bukan nol
echo.
timeout /t %INTERVAL% /nobreak >nul
goto loop

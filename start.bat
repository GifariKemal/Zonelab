@echo off
REM ===========================================================================
REM  Zonelab: start the API, the web app and the auto-trade daemon, then open
REM  the browser.
REM
REM  Double-click this file. Nothing to type, no PowerShell.
REM  Close everything again with stop.bat.
REM
REM  ONE WINDOW, BOTH SERVERS. An earlier version opened a console per server
REM  and it was worse to read, not better: two windows to find, two to arrange,
REM  and the moment a request touches both you are reading two logs side by side
REM  to follow one thing. `start /b` keeps a child attached to THIS console, so
REM  both logs land in one place in the order they happened.
REM
REM  This replaced start.ps1 rather than sitting beside it, on purpose. Two
REM  launchers would each carry the port numbers, the venv path and the kill
REM  logic, and they would drift - which is the one mistake this project keeps
REM  finding in its own code. One launcher, one place to change a port.
REM
REM  Why .bat and not .ps1, measured on this machine rather than assumed:
REM  `assoc .ps1` answers "File association not found for extension .ps1", so a
REM  .ps1 cannot be double-clicked into running at all, while `assoc .bat`
REM  answers `.bat=batfile`. PowerShell is the better LANGUAGE - structured port
REM  lookup, real error handling - but it is not a one-click launcher on Windows.
REM ===========================================================================
setlocal EnableDelayedExpansion
title Zonelab

REM Run from the folder this file lives in, whatever the caller's working
REM directory was. Double-clicking from Explorer starts here, but a shortcut or
REM a scheduled task does not.
cd /d "%~dp0"

set "API_PORT=8100"
set "WEB_PORT=3100"
set "PY=%CD%\backend\.venv\Scripts\python.exe"

REM  The auto-trade daemon's launch flags. THE SWITCH IN THE UI CANNOT SET
REM  THESE. Symbols, timeframes, risk and the required clauses are read once at
REM  start and never re-read, so changing any of them means editing this line
REM  and starting again. `.autotrade.json` carries a `risk_pct` field too, but
REM  the daemon WRITES that field rather than reading it - it is a report, not a
REM  setting, and editing it there changes nothing.
REM
REM  `--send` IS ARMED HERE ON PURPOSE, and arming is not trading. The daemon
REM  re-reads the switch every cycle and does nothing at all while it is off -
REM  it does not even open MT5. Arming it here is what makes the switch mean
REM  what it says: turn it on on the page and orders go out. Delete `--send`
REM  from this line to run the daemon in dry run, where it prints what it would
REM  have sent and sends nothing.
set "AT_FLAGS=--symbol mt5:XAUUSD,mt5:BTCUSD --interval 15m,30m --risk-pct 0.01 --max-total-risk-pct 0.04 --require bias_agrees --send"

REM Absolute path to curl rather than the bare name. `where curl` on this
REM machine finds Git's copy in mingw64 first, which is only on PATH inside a
REM Git shell - and this file is meant to be double-clicked from Explorer, where
REM it would not be. Windows has shipped its own curl in System32 since Windows
REM 10 1803, so naming it outright removes the question.
set "CURL=%SystemRoot%\System32\curl.exe"

echo.
echo  Zonelab
echo  =======
echo.

REM ---------------------------------------------------------------- first run
if not exist "%PY%" (
    echo  Creating the Python environment ^(first run only^)...
    python -m venv "%CD%\backend\.venv"
    if errorlevel 1 (
        echo.
        echo  Could not create the virtual environment. Is Python on PATH?
        echo  Check with:  python --version
        goto :fail
    )
    "%PY%" -m pip install --quiet --upgrade pip
    "%PY%" -m pip install --quiet -r "%CD%\backend\requirements.txt"
    if errorlevel 1 (
        echo  Installing the Python dependencies failed.
        goto :fail
    )
)

if not exist "%CD%\frontend\node_modules" (
    echo  Installing web dependencies ^(first run only^)...
    pushd "%CD%\frontend"
    call npm install
    if errorlevel 1 (
        popd
        echo  npm install failed. Is Node on PATH?  Check with:  node --version
        goto :fail
    )
    popd
)

REM ------------------------------------------- clear anything already running
REM
REM DELEGATED TO stop.bat, not reimplemented here. This used to be its own copy
REM of the port sweep, which reclaimed the two listening sockets and nothing
REM else - so it relied on the npm shim and the uvicorn launcher choosing to
REM exit once their sibling died. They do: measured over five consecutive starts
REM the process count held at exactly four with no drift. But that is an
REM observation about this machine today, not a guarantee, and a stale process is
REM the worst kind of leftover - it answers with the code it was started with, so
REM an edit to the source looks like it did nothing at all.
REM
REM stop.bat already sweeps all three ways: the window, both port owners, and the
REM server processes that hold no port. Calling it means there is ONE sweep to
REM get right, and start.bat can never fall behind it.
call "%CD%\stop.bat" /q

REM --------------------------------------------------------------- the API
echo  Starting the API on http://127.0.0.1:%API_PORT%
start /b "" /D "%CD%\backend" "%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %API_PORT%

REM The web app is useless without the API, so wait for it rather than opening a
REM browser onto an error banner.
REM
REM AND THE WAIT MUST NOT FALL THROUGH TO SUCCESS. An earlier launcher printed a
REM green "API ready" after twenty seconds of failed probes, which is the one
REM message that must never be a guess: everything after it reads it as
REM permission to carry on.
call :waitfor "http://127.0.0.1:%API_PORT%/api/health" 40 "API"
if not defined READY (
    echo.
    echo  The API did not answer on http://127.0.0.1:%API_PORT% within 20 seconds.
    echo  Its error is above, in this window.
    echo  The web app was NOT started and the browser was NOT opened.
    goto :fail
)
echo  API ready.

REM ------------------------------------------------------ the auto-trade daemon
REM
REM STARTED HERE, because for ten hours on 31 August 2026 it was started
REM nowhere. The machine rebooted at 23:47, this file brought the API and the
REM web app back at 05:24, and nothing brought the daemon back at all - so
REM /api/autotrade answered `enabled: true, daemon_alive: false` and the switch
REM sat green on the page over a process that did not exist. That is the same
REM defect as a gate reporting green over a crash, which is the one mistake this
REM project keeps finding in itself.
REM
REM AFTER THE API, not before it and not beside it. The check below asks the API
REM whether the daemon is heartbeating, so the API has to be answering first.
REM
REM ITS OWN LOG FILE, not this window. One cycle prints a line per candidate and
REM there were 21 of them every twenty seconds - in this window that buries the
REM API and the web app completely. APPENDED rather than truncated: what the
REM trader did yesterday is the first thing anyone asks about an order they did
REM not expect.
echo  Starting the auto-trade daemon ^(logging to backend\.autotrade.log^)
start "" /b /D "%CD%\backend" cmd /c ""%PY%" -m tools.autotrade %AT_FLAGS% >> "%CD%\backend\.autotrade.log" 2>&1"

REM AND WAITED FOR, for the same reason every other wait in this file exists.
REM The daemon has a start path that REFUSES: `autotrade.owner()` returns
REM non-empty while another daemon still holds the switch, and it exits without
REM one order ever going out. Under `start /b` that exit is invisible - the
REM window says "Starting the auto-trade daemon" and nothing afterwards
REM contradicts it. `daemon_alive` is computed from the heartbeat the loop
REM writes, so it can only be true once a cycle has actually run.
call :waitdaemon 30
if not defined READY (
    echo.
    echo  WARNING: the auto-trade daemon is NOT heartbeating after 15 seconds.
    echo  The API and the web app are fine. The switch on the page will show
    echo  whatever it was left at, and NOTHING WILL TRADE.
    echo  Its reason is at the end of backend\.autotrade.log.
    echo.
)

REM ------------------------------------------------------------- the web app
echo  Starting the web app on http://localhost:%WEB_PORT%
REM NO `-- --port` HERE, and the port is not passed twice. `package.json`'s dev
REM script is already `next dev -p 3100`, so adding it produced
REM `next dev -p 3100 --port 3100` in the log - two spellings of one value, which
REM is the exact pattern this project keeps having to unpick. package.json owns
REM the web port; `WEB_PORT` above is what this file PROBES and opens the browser
REM on, so if the two ever disagree the wait below fails and says so instead of
REM opening a browser onto nothing.
start /b "" /D "%CD%\frontend" cmd /c "npm run dev"

REM Waited for as well, for the same reason. Next compiles on first boot and is
REM not listening for a while, so a browser opened on a timer arrives at a
REM refused connection and the reader has to reload past it. 60 tries because a
REM cold Turbopack build is slower than the API's start by a wide margin.
call :waitfor "http://127.0.0.1:%WEB_PORT%/" 60 "web app"
if not defined READY (
    echo.
    echo  The web app did not answer on http://localhost:%WEB_PORT% within 30 seconds.
    echo  Its error is above, in this window. The API is still running.
    echo  Stop everything with stop.bat.
    goto :fail
)

start "" "http://localhost:%WEB_PORT%"

echo.
echo  ---------------------------------------------------------------
echo   Zonelab is on http://localhost:%WEB_PORT%
echo.
echo   Both servers log into THIS window, oldest first. Lines that
echo   start with INFO are the API; the rest are the web app.
echo.
echo   The auto-trade daemon logs to backend\.autotrade.log instead. It is
echo   armed but idle until the switch on the page is turned on.
echo.
echo   Leave this window open. Stop everything with stop.bat.
echo   A keypress in this window also ends it.
echo  ---------------------------------------------------------------
echo.

REM Hold the window open so the logs keep arriving somewhere a reader can see.
REM
REM `pause >nul` AND NOT A PING LOOP, and this is the fix for a real symptom the
REM user saw: "sometimes a cmd process suddenly appears then disappears". The
REM first version held the window with
REM
REM     :hold
REM     ping -n 3600 127.0.0.1 >nul
REM     goto :hold
REM
REM which spawns a real ping.exe every hour, for every instance of this file that
REM is still alive. Measured: twelve orphaned launchers from twelve test runs had
REM twelve ping.exe cycling between them, and that is exactly what a flicker looks
REM like. `pause` is an INTERNAL cmd command - it spawns nothing at all - so the
REM window now holds with zero processes and zero flicker.
REM
REM `>nul` hides the "Press any key" prompt, which would otherwise print in the
REM middle of the server logs. A keypress does end this batch, and that is stated
REM below rather than prevented: the servers are `start /b` children of this
REM console, so closing the window takes them with it, and stop.bat is the way to
REM stop them cleanly either way.
pause >nul
exit /b 0

REM ---------------------------------------------------------------- helpers
:waitdaemon
REM %1 = attempts at half a second each. Sets READY once the daemon heartbeats.
REM
REM ASKED THROUGH THE API rather than by counting processes, and those are not
REM the same question. A daemon that is running but wedged still has a process;
REM `daemon_alive` is false unless the loop wrote a heartbeat within
REM STALE_AFTER seconds, and that heartbeat is what the switch on the page
REM actually depends on.
REM
REM PARSED BY PYTHON, not by findstr. Matching the raw JSON would mean putting a
REM double quote inside a `findstr /c:` string, which batch does not escape, and
REM the venv interpreter is already sitting in %PY%.
set "READY="
for /l %%I in (1,1,%~1) do (
    if not defined READY (
        "%PY%" -c "import json,sys,urllib.request; sys.exit(0 if json.load(urllib.request.urlopen('http://127.0.0.1:%API_PORT%/api/autotrade',timeout=2))['daemon_alive'] else 1)" 2>nul && set "READY=1"
        if not defined READY ping -n 2 127.0.0.1 >nul
    )
)
goto :eof


:waitfor
REM %1 = url, %2 = attempts at half a second each, %3 = what it is.
set "READY="
for /l %%I in (1,1,%~2) do (
    if not defined READY (
        "%CURL%" -s -o nul --max-time 2 "%~1" && set "READY=1"
        if not defined READY (
            REM `ping` rather than `timeout`, which refuses to run when stdin is
            REM redirected - and that is exactly what happens when this file is
            REM launched by anything other than a console.
            ping -n 2 127.0.0.1 >nul
        )
    )
)
goto :eof


:fail
echo.
pause
exit /b 1

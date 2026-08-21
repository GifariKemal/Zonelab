@echo off
REM ===========================================================================
REM  Zonelab: stop everything.
REM
REM  Double-click this file. It is safe to run when nothing is up - it says so
REM  rather than pretending it did something.
REM
REM  THREE PASSES, AND ALL THREE ARE NEEDED.
REM
REM  1. The launcher window, by title.
REM  2. Whoever holds either port. `python -m uvicorn` runs as TWO processes and
REM     the CHILD owns the listening socket, so killing the launcher leaves the
REM     child serving - four uvicorn processes were once found alive across two
REM     runs that way, and a leftover is worse than an obvious failure because it
REM     answers with the code it was started with, so an edit to the source looks
REM     like it did nothing.
REM  3. The server processes that hold NO port at all. Measured while writing
REM     this: a live Zonelab was five processes, and only two of them owned a
REM     socket. The npm shim and the Turbopack worker own nothing and would have
REM     survived passes 1 and 2 completely.
REM ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "API_PORT=8100"
set "WEB_PORT=3100"
set "STOPPED=0"

REM `/q` is start.bat calling in, not a user double-clicking. It suppresses the
REM banner and the closing keypress; every line about what was actually stopped
REM still prints, because those belong in start.bat's log.
REM
REM CALLED RATHER THAN COPIED, and that is the point of the flag. start.bat used
REM to carry its own copy of the port sweep, which reclaimed the two listening
REM sockets and nothing else - so it relied on the npm shim and the uvicorn
REM launcher choosing to exit when their sibling died. Measured over five
REM consecutive starts they did, staying at exactly four processes with no drift,
REM but "they did on this machine today" is not the same as "they must". One
REM sweep, one implementation, called from both files.
set "QUIET="
if /i "%~1"=="/q" set "QUIET=1"

if not defined QUIET (
    echo.
    echo  Stopping Zonelab
    echo  ================
    echo.
)

call :bytitle "Zonelab"
call :freeport %API_PORT% "API"
call :freeport %WEB_PORT% "web app"
call :leftovers

if not defined QUIET (
    echo.
    if "%STOPPED%"=="0" (
        echo  Nothing was running.
    ) else (
        echo  Stopped.
    )
)

REM ------------------------------------------------------------ and verify it
REM Said after checking, not instead of checking.
REM
REM AND CHECKED AFTER A PAUSE, because the first version raced the operating
REM system. `taskkill /F` returns as soon as the kill is signalled, not once the
REM process is gone, and a uvicorn launcher whose child has just died exits a
REM moment later on its own. Verifying immediately reported "2 server processes
REM survived" on a run that had in fact cleaned up completely - a false alarm is
REM as bad as a false all-clear, because the reader learns to ignore the line.
REM SKIPPED IN /q MODE for the same self-reference reason `:launchers` is: the
REM count below includes start.bat launchers, and in /q mode the only one running
REM is start.bat itself. It reported "something Zonelab is STILL running" into
REM start.bat's own log on every single boot. start.bat does not need a verdict
REM from here anyway - it waits for both servers to answer HTTP, which is a
REM stronger check than counting processes.
if defined QUIET goto :done

REM RE-CHECKED, NOT WAITED ONCE. `taskkill /F` returns when the kill is
REM signalled, not when the process is gone, and a launcher whose children are
REM unwinding takes a moment. A single three-second pause was not enough: it
REM reported "2 server processes survived" on one clean run and "something is
REM STILL running" on another, both times on a machine that ended up completely
REM clear. A false alarm is as bad as a false all-clear, because the reader learns
REM to ignore the line - so this looks again instead of guessing longer.
set "LEFT="
set "SERVERS=0"
for /l %%T in (1,1,5) do (
    if not "%%T"=="1" ping -n 3 127.0.0.1 >nul
    set "LEFT="
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%API_PORT% " /c:":%WEB_PORT% " ^| findstr /i LISTENING') do set "LEFT=1"
    call :countservers
    if not defined LEFT if "!SERVERS!"=="0" goto :clean
)
if defined LEFT goto :dirty
if not "%SERVERS%"=="0" goto :dirty

:clean
if not defined QUIET echo  Ports %API_PORT% and %WEB_PORT% are free and no Zonelab server is running.
goto :done

:dirty
echo.
echo  WARNING: something Zonelab is STILL running.
if defined LEFT echo    a port is still held - see:  netstat -ano ^| findstr LISTENING
if not "%SERVERS%"=="0" echo    %SERVERS% server process^(es^) survived.
echo  Run this file again. If it persists, reboot or look with Task Manager.

:done
if defined QUIET exit /b 0
echo.
pause
exit /b 0

REM ---------------------------------------------------------------- helpers
:bytitle
REM %1 = the window title start.bat sets. The trailing wildcard matters: cmd.exe
REM appends the running command to the title it was given.
REM
REM ============================ READ THIS ONE ============================
REM THE IMAGENAME FILTER IS NOT OPTIONAL. It is here because the version without
REM it KILLED THE USER'S DESKTOP.
REM
REM A File Explorer window takes its title from the folder it is showing. Anyone
REM running this file is, by definition, standing in the Zonelab folder - so
REM there was an Explorer window titled exactly "Zonelab", `WINDOWTITLE eq
REM Zonelab*` matched it, and `taskkill /F` ended explorer.exe. The desktop, the
REM taskbar and every open folder went with it. Measured after the fact:
REM `Get-Process explorer` returned 0.
REM
REM A window title is a label anyone can wear. Never kill by one alone. Both
REM filters together can only ever match a console: `IMAGENAME eq cmd.exe` AND
REM the title this launcher set.
REM ======================================================================
REM
REM AND IT ASKS BEFORE ACTING, because the first version read `taskkill`'s exit
REM code as "did I kill something" - and MEASURED on this machine, `taskkill /FI`
REM with a filter matching nothing still exits 0. So it printed "Closed the
REM Zonelab window" with no servers running at all, and then "Stopped" instead of
REM "Nothing was running". A stop script that reports success without looking is
REM the same defect as a readiness probe that falls through to green.
REM
REM `tasklist` answers honestly: with no match it prints "INFO: No tasks are
REM running which match the specified criteria", which contains no `.exe`, so
REM `findstr` returns 1 and the block is skipped.
tasklist /FI "IMAGENAME eq cmd.exe" /FI "WINDOWTITLE eq %~1*" /NH 2>nul | findstr /i "\.exe" >nul
if errorlevel 1 goto :eof
taskkill /F /FI "IMAGENAME eq cmd.exe" /FI "WINDOWTITLE eq %~1*" >nul 2>&1
echo  Closed the %~1 console window.
set "STOPPED=1"
goto :eof

REM ---------------------------------------------------------------------------
REM WHY THERE IS NO COMMAND-LINE SWEEP FOR start.bat ITSELF.
REM
REM start.bat ends by holding its window open, so the `cmd.exe` running it lives
REM until something stops it - and for a while nothing did. Twelve test runs left
REM twelve launchers alive, each holding a ping.exe from the old hold loop, and
REM that is exactly what the user saw as a window flickering in and out.
REM
REM Two attempts at fixing it with wmic both failed, and both failures are the
REM same shape:
REM
REM   1. SELF-KILL. `call` does not spawn a process, so when start.bat calls
REM      `stop.bat /q` the sweep runs INSIDE the very cmd.exe whose command line
REM      contains `start.bat`. It killed start.bat during its own cleanup, before
REM      a single server started.
REM   2. SELF-MATCH. Gating it on /q fixed that and exposed the next one: the
REM      WRAPPER process running a test that called stop.bat also mentions
REM      start.bat in its command line, so a completely clean machine reported
REM      "Stopping a start.bat launcher" and then "something is STILL running".
REM      Fourth time in one session that a filter matched the thing doing the
REM      filtering.
REM
REM So the sweep is gone. `:bytitle` handles the real case precisely: a launcher
REM started by double-clicking sets `title Zonelab`, and `IMAGENAME eq cmd.exe`
REM plus that title can only match a console this project opened. What stays
REM uncovered is a start.bat launched by another SCRIPT, which sets no title -
REM a testing pattern, not a way anyone uses this.
REM
REM And the hold loop is a `pause` now, which spawns nothing, so an uncovered
REM orphan costs one idle cmd.exe rather than a ping every hour.
REM ---------------------------------------------------------------------------

:freeport
REM %1 = port, %2 = what it is, for the message.
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%~1 " ^| findstr /i LISTENING') do (
    echo  Stopping the process holding port %~1 ^(%~2^), pid %%P.
    set "STOPPED=1"
    REM A PID appears twice when it listens on IPv4 and IPv6, so the second
    REM taskkill fails harmlessly and its output is discarded.
    taskkill /F /PID %%P >nul 2>&1
)
goto :eof

:leftovers
REM The server processes that own no socket, so nothing above could find them.
REM
REM THE FILTER IS NARROW ON PURPOSE, and the wide version was dangerous. The
REM obvious rule - "any process whose command line mentions Zonelab" - matched
REM FOURTEEN processes on this machine when it was tested read-only, including
REM WindowsTerminal.exe, three bash.exe and WMIC.exe itself. Every one of those
REM mentions the path because it is running a command about it. A `wmic delete`
REM on that filter would have closed the terminal the user was standing in.
REM
REM So both rules require Zonelab in the command line AND pin the executable:
REM python running uvicorn, node running anything. Checked read-only before this
REM was wired up - it matched exactly the server processes and no shell, terminal
REM or wmic.
REM
REM THE ZONELAB CONDITION IS ON THE PYTHON RULE TOO, and it was missing at first.
REM `Name='python.exe' and CommandLine like '%%uvicorn%%'` on its own would end
REM ANY uvicorn on the machine - another project's API, someone else's dev server.
REM Nothing about this file entitles it to reach outside its own folder.
REM
REM WRITTEN OUT TWICE RATHER THAN PASSED TO A HELPER, and that is not laziness of
REM the wrong kind. The first version passed the WQL clause as a `call` argument,
REM and `%%` in a batch argument is expanded on the way in - so the query wmic
REM actually received had single `%` signs and matched nothing. It printed no
REM leftovers while the verification at the bottom, which had the same clause
REM INLINE, counted two. Two spellings of one query is the bug this file exists
REM to avoid; one spelling that works beats a helper that does not.
REM
REM The CSV columns are Node,Name,ProcessId - the machine name comes FIRST, which
REM is why the tokens start at 2. Reading tokens 1,2 printed the process name in
REM the pid column, which is how that was caught.
REM
REM THE HEADER ROW IS SKIPPED BY ITS NAME COLUMN, not by its pid column. Testing
REM `%%B` against "ProcessId" looked right and did not work: wmic's CSV ends every
REM line with CRLF, so `%%B` on the header is `ProcessId` plus a stray carriage
REM return and never equals the literal. It printed
REM `Stopping a leftover web process, Name pid=ProcessId.` on a real run. `%%A`
REM sits mid-line, so it carries no CR and compares cleanly.
for /f "skip=1 tokens=2,3 delims=," %%A in ('wmic process where "Name='python.exe' and CommandLine like '%%uvicorn%%' and CommandLine like '%%Zonelab%%'" get Name^,ProcessId /format:csv 2^>nul') do (
    if not "%%B"=="" if /i not "%%A"=="Name" (
        echo  Stopping a leftover API process, %%A pid=%%B.
        set "STOPPED=1"
        taskkill /F /PID %%B >nul 2>&1
    )
)
for /f "skip=1 tokens=2,3 delims=," %%A in ('wmic process where "Name='node.exe' and CommandLine like '%%Zonelab%%'" get Name^,ProcessId /format:csv 2^>nul') do (
    if not "%%B"=="" if /i not "%%A"=="Name" (
        echo  Stopping a leftover web process, %%A pid=%%B.
        set "STOPPED=1"
        taskkill /F /PID %%B >nul 2>&1
    )
)
goto :eof

:countservers
REM How many server processes are left, for the verification above.
set "SERVERS=0"
for /f "skip=1 tokens=2,3 delims=," %%A in ('wmic process where "CommandLine like '%%Zonelab%%' and ((Name='python.exe' and CommandLine like '%%uvicorn%%') or Name='node.exe')" get Name^,ProcessId /format:csv 2^>nul') do (
    if not "%%B"=="" if /i not "%%A"=="Name" set /a SERVERS+=1
)
goto :eof

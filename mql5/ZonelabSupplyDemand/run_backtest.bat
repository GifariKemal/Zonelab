@echo off
REM Jalankan Strategy Tester untuk ZonelabSD.
REM
REM PERINGATAN: terminal Exness yang sama dipakai daemon auto-trade LIVE.
REM Kalau saklar MENYALA, jangan jalankan ini - tester bersaing dengan terminal
REM dan bisa mengganggu order riil. Matikan daemon dulu (stop.bat), pastikan
REM .autotrade.json "enabled" false, baru jalankan.

setlocal
set TERMINAL=C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe
set CONFIG=%~dp0tester.ini

echo Menjalankan tester dengan config:
echo   %CONFIG%
echo.
echo Kalau daemon auto-trade masih hidup, hentikan dulu (Ctrl+C sekarang).
pause

"%TERMINAL%" /config:"%CONFIG%"

echo.
echo Selesai. Report tester ada di folder MQL5\Files atau lihat jendela terminal.
endlocal

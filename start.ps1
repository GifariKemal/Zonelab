# Starts the API and the web app together, then opens the browser.
#   pwsh -File start.ps1
# Stop both with Ctrl+C in this window.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$apiPort = 8100
$webPort = 3100

$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating the Python environment (first run only)..." -ForegroundColor Yellow
    python -m venv (Join-Path $root "backend\.venv")
    & $python -m pip install --quiet --upgrade pip
    & $python -m pip install --quiet -r (Join-Path $root "backend\requirements.txt")
}

if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "Installing web dependencies (first run only)..." -ForegroundColor Yellow
    Push-Location (Join-Path $root "frontend"); npm install; Pop-Location
}

$api = Start-Process -PassThru -NoNewWindow -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $apiPort `
    -WorkingDirectory (Join-Path $root "backend")

# The web app is useless without the API, so wait for it rather than opening a
# browser onto an error banner.
foreach ($i in 1..40) {
    try { Invoke-RestMethod "http://127.0.0.1:$apiPort/api/health" -TimeoutSec 2 | Out-Null; break }
    catch { Start-Sleep -Milliseconds 500 }
}
Write-Host "API ready on http://127.0.0.1:$apiPort" -ForegroundColor Green

$web = Start-Process -PassThru -NoNewWindow -FilePath "npm" `
    -ArgumentList "run", "dev", "--", "--port", $webPort `
    -WorkingDirectory (Join-Path $root "frontend")

Start-Sleep -Seconds 4
Start-Process "http://localhost:$webPort"
Write-Host "Zonelab is on http://localhost:$webPort. Ctrl+C to stop." -ForegroundColor Green

try { Wait-Process -Id $web.Id }
finally {
    foreach ($p in @($api, $web)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}

# ============================================================================
# ARGOS OSINT v4.0 — Docker tek-tıkla başlatıcı (Windows PowerShell)
# ----------------------------------------------------------------------------
# Kullanim:
#   .\scripts\docker_start.ps1
#
# Akis:
#   1) docker compose up --build -d
#   2) Start-Sleep 3
#   3) Invoke-RestMethod http://localhost:8000/__ping
# ============================================================================
$ErrorActionPreference = "Stop"

# Repo koku script konumunun bir ust dizini
Set-Location -Path (Join-Path $PSScriptRoot "..")

# ---- 1. .env kontrolu -----------------------------------------------------
if (-not (Test-Path ".env")) {
    Write-Host "[uyari] .env dosyasi bulunamadi - API anahtarlari olmadan calisacak." -ForegroundColor Yellow
    Write-Host "         Ornek: Copy-Item .env.example .env  ve duzenleyin."
}

# ---- 2. Build & up --------------------------------------------------------
Write-Host "[1/3] docker compose up --build -d" -ForegroundColor Cyan
docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "[hata] docker compose up basarisiz." -ForegroundColor Red
    exit $LASTEXITCODE
}

# ---- 3. Hazir olmasini bekle ----------------------------------------------
Write-Host "[2/3] healthcheck'i bekliyorum..." -ForegroundColor Cyan
Start-Sleep -Seconds 3

# ---- 4. /__ping ile dogrula -----------------------------------------------
Write-Host "[3/3] http://localhost:8000/__ping" -ForegroundColor Cyan
try {
    $ping = Invoke-RestMethod -Uri "http://localhost:8000/__ping" -TimeoutSec 5
    Write-Host ""
    Write-Host "[ok] ARGOS OSINT calisiyor." -ForegroundColor Green
    Write-Host ("     /__ping yaniti: {0}" -f ($ping | ConvertTo-Json -Compress))
    Write-Host "     UI:    http://localhost:8000/ui/dashboard.html"
    Write-Host "     Docs:  http://localhost:8000/docs"
    Write-Host "     Logs:  docker compose logs -f argos"
}
catch {
    Write-Host ""
    Write-Host "[hata] /__ping yanit vermedi: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "       Loglara bakin: docker compose logs argos"
    exit 1
}

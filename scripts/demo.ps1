#Requires -Version 5
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$base = "http://127.0.0.1:8000"

Write-Host "== health ==" -ForegroundColor Cyan
try {
  Invoke-RestMethod "$base/__ping" | ConvertTo-Json -Depth 5
} catch {
  Write-Host "ping failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n== scan demo ==" -ForegroundColor Cyan
try {
  $resp = Invoke-RestMethod "$base/scan/full?username=ahmedsn198&timeout=30"
  New-Item -ItemType Directory -Force -Path demo | Out-Null
  $resp | ConvertTo-Json -Depth 20 | Out-File -FilePath demo\scan_result.json -Encoding utf8
  Write-Host "Saved -> demo\scan_result.json" -ForegroundColor Green
} catch {
  Write-Host "scan failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n== playwright title smoke (inside container) ==" -ForegroundColor Cyan
docker exec footprint-backend-footprint-1 sh -lc "python - <<'PY'
import asyncio
from playwright.async_api import async_playwright
from app.utils import pw_safe

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://www.example.com', wait_until='networkidle')
        t = await pw_safe.page_title(page)
        print('title:', t or '<empty>')
        await browser.close()

asyncio.run(run())
PY"

Write-Host "`nDone." -ForegroundColor Green

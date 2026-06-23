#!/usr/bin/env bash
set -euo pipefail
base="http://127.0.0.1:8000"
mkdir -p demo
echo "== health =="
curl -s "$base/__ping" | python -m json.tool || true
echo
echo "== scan demo =="
curl -s "$base/scan/full?username=ahmedsn198&timeout=30" | python -m json.tool > demo/scan_result.json || true
echo "Saved -> demo/scan_result.json"
echo
echo "== playwright title smoke (inside container) =="
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
echo
echo "Done."

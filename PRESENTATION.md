# Footprint Backend — Quick Demo Guide

## What we’ll show (2 mins)
- Robust Playwright title reader: `app/utils/pw_safe.py` → `page_title(...)`  ← **[DEMO]**
- LinkedIn stabilizations: `app/services/linkedin_service.py` (uses `pw_safe.page_title` + `goto(..., wait_until=...)`)  ← **[DEMO]**
- Username parsing: `app/services/person_aggregator.py` → `_platform_from_url`  ← **[DEMO]**
- Health + Scan endpoints working.

## How to run (one command)
- PowerShell (Windows): `scripts\demo.ps1`
- Bash (Mac/Linux): `bash scripts/demo.sh`

Outputs land in `demo/`:
- `demo/scan_result.json` → full JSON (pretty)
- Terminal prints: health + page title smoke

## Fast navigation in Cursor
- `Ctrl/Cmd + P` → type `pw_safe.py`
- Search: `Ctrl/Cmd + Shift + F` → `[DEMO]`
- Symbols: `Ctrl/Cmd + Shift + O`

## Talk track (30s each)
1. `pw_safe.page_title`: retries, JS `document.title`, Playwright fallback, `og:title`, no exceptions → returns `""`.
2. `linkedin_service`: replaced fragile `page.title()` with `pw_safe.page_title(page)` and enforced `wait_until`.
3. `_platform_from_url`: maps hosts → platforms, trims/cleans handle, covers special paths (x/linkedin/facebook).

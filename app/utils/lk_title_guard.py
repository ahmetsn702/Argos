# LinkedIn-safe title readers (async/sync) — no Page.title() usage.
import re, asyncio, time

async def safe_title(page, tries: int = 5, wait_ms: int = 15000) -> str:
    for _ in range(tries):
        try:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=wait_ms)
            except Exception:
                pass
            try:
                await page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                pass
            await page.wait_for_timeout(200)
            t = await page.evaluate("document.title || ''")
            if t:
                return t
        except Exception:
            await asyncio.sleep(0.3)
            continue
    # og:title fallback
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=wait_ms)
        html = await page.content()
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"<]+)', html, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""

def safe_title_sync(page, tries: int = 5, wait_ms: int = 15000) -> str:
    for _ in range(tries):
        try:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=wait_ms)
            except Exception:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                pass
            page.wait_for_timeout(200)
            t = page.evaluate("document.title || ''")
            if t:
                return t
        except Exception:
            time.sleep(0.3)
            continue
    # og:title fallback
    try:
        page.wait_for_load_state("domcontentloaded", timeout=wait_ms)
        html = page.content()
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"<]+)', html, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""








from __future__ import annotations
import asyncio, re, time
# [DEMO] Robust Playwright title reader with retries + fallbacks
async def page_title(page, tries: int = 5, wait_ms: int = 15000):
    # Hata fırlatmadan, redirect dalgalarına dayanıklı başlık okuma
    for _ in range(tries):
        try:
            # Esnek yükleme bekleme
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=wait_ms)
            except Exception:
                pass
            try:
                await page.wait_for_load_state("networkidle", timeout=2000)
            except Exception:
                pass
            await page.wait_for_timeout(200)

            # 1) JS ile oku (en stabil yol)
            title = await page.evaluate("document.title || ''")
            if title:
                return title


        except Exception as e:
            # LinkedIn: "Execution context was destroyed" ⇢ kısa bekle ve yeniden dene
            if "Execution context was destroyed" in str(e):
                await asyncio.sleep(0.5)
                continue
            await asyncio.sleep(0.3)
            continue

    # 3) Son çare: og:title
    try:
        html = await page.content()
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"<]+)', html, re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""

def page_title_sync(page, tries: int = 5, wait_ms: int = 15000):
    # Redirect dalgalarında stabil başlık okuma (SYNC), hata fırlatma YOK.
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
            # 1) JS ile oku (çoğunlukla daha stabil)
            title = page.evaluate("document.title || ''")
            if title:
                return title
        except Exception as e:
            if "Execution context was destroyed" in str(e):
                time.sleep(0.5)
                continue
            time.sleep(0.3)
            continue
    # son çare: og:title
    try:
        page.wait_for_load_state("domcontentloaded", timeout=wait_ms)
        html = page.content()
        import re as _re
        m = _re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"<]+)', html, _re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""
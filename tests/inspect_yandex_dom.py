"""Yandex Images DOM inspector — headed Chromium, sayfayı açar ve buton selector'larını loglar."""
import asyncio
from playwright.async_api import async_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=400)
        ctx = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1366, "height": 850},
            locale="tr-TR",
        )
        page = await ctx.new_page()
        await page.goto("https://yandex.com/images/", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        # Tüm buton/input elementlerini logla
        print("\n=== BUTTONS ===")
        buttons = await page.evaluate("""() => {
            return [...document.querySelectorAll('button')].map(b => ({
                tag: 'button',
                id: b.id,
                className: b.className.slice(0,120),
                ariaLabel: b.getAttribute('aria-label'),
                title: b.title,
                text: b.innerText?.slice(0,60),
                dataElem: b.getAttribute('data-elem'),
                dataBem: b.getAttribute('data-bem')?.slice(0,120),
            }));
        }""")
        for b in buttons:
            print(b)

        print("\n=== FILE INPUTS ===")
        inputs = await page.evaluate("""() => {
            return [...document.querySelectorAll('input[type=file]')].map(i => ({
                id: i.id,
                className: i.className.slice(0,120),
                name: i.name,
                accept: i.accept,
                parentClass: i.parentElement?.className?.slice(0,120),
            }));
        }""")
        for i in inputs:
            print(i)

        print("\n=== CAMERA / CBIR ELEMENTS ===")
        cbir = await page.evaluate("""() => {
            const sel = '[class*="cbir"], [class*="camera"], [class*="visual"], [data-id*="cbir"], [aria-label*="image" i], [aria-label*="resim" i], [aria-label*="foto" i]';
            return [...document.querySelectorAll(sel)].slice(0,20).map(el => ({
                tag: el.tagName,
                id: el.id,
                className: el.className.slice(0,120),
                ariaLabel: el.getAttribute('aria-label'),
                dataBem: el.getAttribute('data-bem')?.slice(0,100),
            }));
        }""")
        for c in cbir:
            print(c)

        print("\n=== SVG / IMG ICONS near search ===")
        icons = await page.evaluate("""() => {
            return [...document.querySelectorAll('.search-form button, .search .button, [class*="Search"] button')].slice(0,10).map(el => ({
                tag: el.tagName,
                className: el.className.slice(0,120),
                ariaLabel: el.getAttribute('aria-label'),
                html: el.outerHTML.slice(0,200),
            }));
        }""")
        for ic in icons:
            print(ic)

        # Sayfanın tam URL'sini ve başlığını da logla
        print(f"\nURL: {page.url}")
        print(f"Title: {await page.title()}")

        await page.wait_for_timeout(5000)
        await browser.close()

asyncio.run(main())

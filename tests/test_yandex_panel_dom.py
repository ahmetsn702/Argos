"""Yandex upload panel — kamera tıkla, panel render'ını bekle, DOM'u logla."""
import asyncio, tempfile, os
from playwright.async_api import async_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TINY_JPEG = bytes([
    0xFF,0xD8,0xFF,0xE0,0x00,0x10,0x4A,0x46,0x49,0x46,0x00,0x01,0x01,0x00,0x00,0x01,
    0x00,0x01,0x00,0x00,0xFF,0xDB,0x00,0x43,0x00,0x08,0x06,0x06,0x07,0x06,0x05,0x08,
    0x07,0x07,0x07,0x09,0x09,0x08,0x0A,0x0C,0x14,0x0D,0x0C,0x0B,0x0B,0x0C,0x19,0x12,
    0x13,0x0F,0x14,0x1D,0x1A,0x1F,0x1E,0x1D,0x1A,0x1C,0x1C,0x20,0x24,0x2E,0x27,0x20,
    0x22,0x2C,0x23,0x1C,0x1C,0x28,0x37,0x29,0x2C,0x30,0x31,0x34,0x34,0x34,0x1F,0x27,
    0x39,0x3D,0x38,0x32,0x3C,0x2E,0x33,0x34,0x32,0xFF,0xC0,0x00,0x0B,0x08,0x00,0x01,
    0x00,0x01,0x01,0x01,0x11,0x00,0xFF,0xC4,0x00,0x1F,0x00,0x00,0x01,0x05,0x01,0x01,
    0x01,0x01,0x01,0x01,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x01,0x02,0x03,0x04,
    0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0xFF,0xC4,0x00,0xB5,0x10,0x00,0x02,0x01,0x03,
    0x03,0x02,0x04,0x03,0x05,0x05,0x04,0x04,0x00,0x00,0x01,0x7D,0x01,0x02,0x03,0x00,
    0x04,0x11,0x05,0x12,0x21,0x31,0x41,0x06,0x13,0x51,0x61,0x07,0x22,0x71,0x14,0x32,
    0x81,0x91,0xA1,0x08,0x23,0x42,0xB1,0xC1,0x15,0x52,0xD1,0xF0,0x24,0x33,0x62,0x72,
    0x82,0xFF,0xDA,0x00,0x08,0x01,0x01,0x00,0x00,0x3F,0x00,0xFB,0xD3,0xFF,0xD9
])

async def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(TINY_JPEG); tmp.flush(); tmp.close()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False, slow_mo=300)
            ctx = await browser.new_context(
                user_agent=UA, viewport={"width": 1366, "height": 850}, locale="tr-TR"
            )
            page = await ctx.new_page()
            await page.goto("https://yandex.com/images/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)

            # 1. Kamera butonunu tıkla
            cam = page.locator("button.HeaderDesktopActions-CbirButton")
            await cam.first.click()

            # 2. Panel içinde bir şeyler render oluncaya kadar bekle
            print("Panel render bekleniyor...")
            try:
                # "Dosyadan yükle" veya benzeri bir link/buton bekle
                await page.wait_for_selector(
                    ".cbir-uploader__panel a, .cbir-uploader__panel button, .cbir-uploader__panel label, [class*='CbirPanel'] input, [class*='CbirPanel'] button, [class*='CbirPanel'] label",
                    timeout=8000
                )
                print("Panel elementi bulundu!")
            except Exception as e:
                print(f"Selector timeout: {e}")

            # 3. Panel tam HTML'ini logla
            panel_html = await page.evaluate("""() => {
                const p = document.querySelector('.cbir-uploader__panel');
                return p ? p.innerHTML : 'NOT FOUND';
            }""")
            print(f"\ncbir-uploader__panel HTML (ilk 1500):\n{panel_html[:1500]}")

            # 4. CbirPanel altındaki tüm interaktif elementler
            cbir_panel = await page.evaluate("""() => {
                const root = document.querySelector('[id^="CbirPanel"]');
                if (!root) return 'CbirPanel root not found';
                return root.innerHTML.slice(0, 2000);
            }""")
            print(f"\nCbirPanel root HTML (ilk 2000):\n{cbir_panel[:2000]}")

            # 5. Tüm input[type=file] — panel açıldıktan sonra
            all_inputs = await page.evaluate("""() => {
                return [...document.querySelectorAll('input[type=file]')].map(i => ({
                    class: i.className, id: i.id,
                    display: getComputedStyle(i).display,
                    parentTag: i.parentElement?.tagName,
                    parentClass: i.parentElement?.className?.slice(0,100),
                    grandParentClass: i.parentElement?.parentElement?.className?.slice(0,100),
                }));
            }""")
            print(f"\nFile inputs (panel sonrası): {all_inputs}")

            # 6. Tüm butonlar (panel sonrası)
            btns = await page.evaluate("""() => {
                return [...document.querySelectorAll('button, label[for], a')].filter(el => {
                    const c = el.className || '';
                    return c.includes('cbir') || c.includes('Cbir') || c.includes('upload') || c.includes('file');
                }).map(el => ({
                    tag: el.tagName, class: el.className.slice(0,120),
                    text: el.innerText?.slice(0,60), forAttr: el.getAttribute('for'),
                    href: el.getAttribute('href'),
                }));
            }""")
            print(f"\ncbir/upload butonlar: {btns}")

            await page.wait_for_timeout(3000)
            await browser.close()
    finally:
        os.unlink(tmp.name)

asyncio.run(main())

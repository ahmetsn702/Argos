"""Yandex upload flow v3 — CbirPanel-FileControlsButton + file chooser."""
import asyncio, tempfile, os, struct, zlib
from playwright.async_api import async_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def make_png(w=50, h=50):
    """Minimal geçerli PNG üret."""
    def chunk(name, data):
        c = struct.pack('>I', len(data)) + name + data
        return c + struct.pack('>I', zlib.crc32(name + data) & 0xFFFFFFFF)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    raw = b''.join(b'\x00' + b'\xFF\x00\x00' * w for _ in range(h))
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend

async def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(make_png(50, 50)); tmp.flush(); tmp.close()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False, slow_mo=400)
            ctx = await browser.new_context(
                user_agent=UA, viewport={"width": 1366, "height": 850}, locale="tr-TR"
            )
            page = await ctx.new_page()
            page.on("framenavigated", lambda f: print(f"  → {f.url[:120]}") if f == page.main_frame else None)

            await page.goto("https://yandex.com/images/", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)

            # 1. Kamera butonuna tıkla → panel açılsın
            await page.locator("button.HeaderDesktopActions-CbirButton").first.click()
            print("Kamera tıklandı")

            # 2. "Dosya seç" butonunu bekle
            dosya_sec = page.locator("button.CbirPanel-FileControlsButton").first
            await dosya_sec.wait_for(state="visible", timeout=6000)
            print(f"'Dosya seç' butonu görünür: {await dosya_sec.inner_text()}")

            # 3. file chooser ile yükle
            async with page.expect_file_chooser(timeout=5000) as fc_info:
                await dosya_sec.click()
            chooser = await fc_info.value
            await chooser.set_files(tmp.name)
            print("Dosya seçildi, sonuç bekleniyor...")

            # 4. Tüm navigasyon URL'lerini izle, cbir_id içereni yakala
            result_url = None
            def on_nav(frame):
                nonlocal result_url
                u = frame.url
                if "cbir_id" in u or ("gorsel" in u and "rpt=imageview" in u):
                    result_url = u
                    print(f"  ★ CBIR URL yakalandı: {u[:200]}")
            page.on("framenavigated", on_nav)

            try:
                await page.wait_for_function(
                    "() => window.location.href.includes('cbir') || window.location.search.length > 80",
                    timeout=20000
                )
            except Exception:
                pass

            await page.wait_for_timeout(5000)

            if result_url:
                print(f"\n=== BAŞARILI UPLOAD URL ===\n{result_url}")
            else:
                print(f"Son URL: {page.url[:200]}")

            await page.wait_for_timeout(5000)
            await browser.close()
    finally:
        os.unlink(tmp.name)

asyncio.run(main())

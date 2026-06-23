# app/services/yandex_search.py
"""
Yandex Images ters görsel arama — Playwright wrapper.
"""
from __future__ import annotations
import asyncio
import tempfile
import time
import logging
from typing import Any, Dict, List

from app.services._yandex_parser import parse_yandex_html, is_captcha_page

logger = logging.getLogger("footprint.yandex")

try:
    from playwright.async_api import async_playwright
    from playwright.async_api import TimeoutError as PwTimeout
    _PW_AVAILABLE = True
except ImportError:
    _PW_AVAILABLE = False

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Gerçek DOM'dan doğrulanmış selector'lar (2026-05 yandex.com.tr)
_CAMERA_BTN   = "button.HeaderDesktopActions-CbirButton"   # kamera ikonu
_UPLOAD_BTN   = "button.CbirPanel-FileControlsButton"      # "Dosya seç" paneli
_RESULT_GLOB  = "**/gorsel/search?cbir_id**"               # yandex.com.tr sonuç URL


def _err(msg: str, took_ms: int) -> Dict[str, Any]:
    return {"engine": "yandex", "ok": False, "results": [], "error": msg, "took_ms": took_ms}


async def search_yandex(
    image_bytes: bytes,
    max_results: int = 10,
    timeout_ms: int = 30_000,
) -> Dict[str, Any]:
    """
    Yandex Images'a görsel yükle, sonuçları döndür.

    Dönüş şeması (diğer engine'lerle aynı):
    {"engine": "yandex", "ok": bool, "results": [...], "error": str|None, "took_ms": int}
    """
    t0 = time.time()

    if not _PW_AVAILABLE:
        return _err("playwright_unavailable", 0)

    browser = None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            ctx = await browser.new_context(
                user_agent=_UA,
                viewport={"width": 1366, "height": 850},
                locale="tr-TR",
            )
            page = await ctx.new_page()

            # 1. Ana sayfa
            try:
                await page.goto(
                    "https://yandex.com/images/",
                    wait_until="domcontentloaded",
                    timeout=15_000,
                )
            except PwTimeout:
                return _err("timeout_homepage", int((time.time() - t0) * 1000))

            if is_captcha_page(await page.content()):
                return _err("captcha_detected", int((time.time() - t0) * 1000))

            # 2a. Kamera ikonuna tıkla → upload paneli açılır
            try:
                cam = page.locator(_CAMERA_BTN)
                await cam.wait_for(state="visible", timeout=8_000)
                await cam.first.click()
            except Exception:
                return _err("camera_button_not_found", int((time.time() - t0) * 1000))

            # 2b. "Dosya seç" butonunu bekle → file chooser
            try:
                upload_btn = page.locator(_UPLOAD_BTN).first
                await upload_btn.wait_for(state="visible", timeout=8_000)
                async with page.expect_file_chooser(timeout=8_000) as fc_info:
                    await upload_btn.click()
                chooser = await fc_info.value
            except Exception as e:
                return _err(f"upload_button_not_found: {e}", int((time.time() - t0) * 1000))

            # 3. Görseli yükle
            await chooser.set_files(tmp_path)

            # 4. Sonuç URL'ye yönlenmeyi bekle (cbir_id içeren URL)
            try:
                await page.wait_for_url(_RESULT_GLOB, timeout=20_000)
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except PwTimeout:
                return _err("timeout_results", int((time.time() - t0) * 1000))

            if is_captcha_page(await page.content()):
                return _err("captcha_detected", int((time.time() - t0) * 1000))

            # 5. Parse
            html = await page.content()
            results = parse_yandex_html(html)

            await browser.close()
            browser = None

        took_ms = int((time.time() - t0) * 1000)
        filtered = [r for r in results if r["url"]][:max_results]
        return {
            "engine": "yandex",
            "ok": True,
            "results": filtered,
            "error": None,
            "took_ms": took_ms,
        }

    except Exception as exc:
        logger.warning(f"Yandex search hatasi: {type(exc).__name__}: {exc}")
        return _err(f"{type(exc).__name__}: {exc}", int((time.time() - t0) * 1000))
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if tmp_path:
            import os
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

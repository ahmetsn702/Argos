# tests/test_yandex_search.py
"""
Mock'lu birim testler: app/services/yandex_search.py
Playwright asla başlatılmaz.

Gerçek flow (yandex.com.tr'den doğrulandı):
  1. page.locator(CAMERA_BTN).wait_for() + .first.click()
  2. page.locator(UPLOAD_BTN).first.wait_for() + expect_file_chooser + click
  3. chooser = await fc_info.value  (coroutine)
  4. wait_for_url(cbir_id glob)
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))

SAMPLE_HTML = (FIXTURES / "yandex_sample_result.html").read_text(encoding="utf-8")
CAPTCHA_HTML = (FIXTURES / "yandex_captcha_page.html").read_text(encoding="utf-8")
FAKE_BYTES = b"fake_image_data"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─── Playwright mock fabrikası ────────────────────────────────────────────────

def _make_pw_mock(page_html: str):
    """
    Yeni 2-adım upload flow'unu mock'la:
    camera_btn.wait_for / first.click → upload_btn.first.wait_for / expect_file_chooser
    → await fc_info.value (coroutine property)
    """
    mock_chooser = AsyncMock()
    mock_chooser.set_files = AsyncMock()

    # expect_file_chooser context manager — fc_info.value coroutine döner
    class FakeFileChooserCM:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        @property
        def value(self):
            async def _get():
                return mock_chooser
            return _get()

    # locator: wait_for, first.click, first.wait_for hepsi async
    def _make_locator():
        loc = MagicMock()
        loc.wait_for = AsyncMock()
        first = MagicMock()
        first.click = AsyncMock()
        first.wait_for = AsyncMock()
        loc.first = first
        return loc

    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value=page_html)
    mock_page.locator = MagicMock(side_effect=lambda sel: _make_locator())
    mock_page.expect_file_chooser = MagicMock(return_value=FakeFileChooserCM())
    mock_page.wait_for_url = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_ctx)
    mock_browser.close = AsyncMock()
    mock_pw = MagicMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

    class FakePwCM:
        async def __aenter__(self): return mock_pw
        async def __aexit__(self, *a): return False

    return FakePwCM(), mock_page, mock_chooser


# ─── Testler ─────────────────────────────────────────────────────────────────

def test_playwright_unavailable_returns_error():
    if "app.services.yandex_search" in sys.modules:
        del sys.modules["app.services.yandex_search"]
    from app.services.yandex_search import search_yandex
    import app.services.yandex_search as ys_mod
    orig = ys_mod._PW_AVAILABLE
    ys_mod._PW_AVAILABLE = False
    try:
        result = run(search_yandex(FAKE_BYTES))
    finally:
        ys_mod._PW_AVAILABLE = orig
    assert result["ok"] is False
    assert result["error"] == "playwright_unavailable"
    print("  ✓ _PW_AVAILABLE=False → playwright_unavailable döner")


def test_successful_search_returns_results():
    mock_apm, _, mock_chooser = _make_pw_mock(SAMPLE_HTML)
    if "app.services.yandex_search" in sys.modules:
        del sys.modules["app.services.yandex_search"]
    from app.services.yandex_search import search_yandex
    with patch("app.services.yandex_search.async_playwright", return_value=mock_apm):
        result = run(search_yandex(FAKE_BYTES, max_results=20))
    assert result["ok"] is True, f"error={result.get('error')}"
    assert result["engine"] == "yandex"
    sites = [r for r in result["results"] if r["type"] == "yandex_site"]
    assert len(sites) == 3
    assert result["error"] is None
    mock_chooser.set_files.assert_awaited_once()
    print(f"  ✓ Başarılı arama: {len(result['results'])} sonuç, {len(sites)} site")


def test_captcha_page_returns_error():
    mock_apm, _, _ = _make_pw_mock(CAPTCHA_HTML)
    if "app.services.yandex_search" in sys.modules:
        del sys.modules["app.services.yandex_search"]
    from app.services.yandex_search import search_yandex
    with patch("app.services.yandex_search.async_playwright", return_value=mock_apm):
        result = run(search_yandex(FAKE_BYTES))
    assert result["ok"] is False
    assert result["error"] == "captcha_detected"
    print("  ✓ CAPTCHA → captcha_detected")


def test_max_results_respected():
    mock_apm, _, _ = _make_pw_mock(SAMPLE_HTML)
    if "app.services.yandex_search" in sys.modules:
        del sys.modules["app.services.yandex_search"]
    from app.services.yandex_search import search_yandex
    with patch("app.services.yandex_search.async_playwright", return_value=mock_apm):
        result = run(search_yandex(FAKE_BYTES, max_results=2))
    assert result["ok"] is True
    assert len(result["results"]) <= 2
    print(f"  ✓ max_results=2 → {len(result['results'])} sonuç")


def test_result_schema():
    mock_apm, _, _ = _make_pw_mock(SAMPLE_HTML)
    if "app.services.yandex_search" in sys.modules:
        del sys.modules["app.services.yandex_search"]
    from app.services.yandex_search import search_yandex
    with patch("app.services.yandex_search.async_playwright", return_value=mock_apm):
        result = run(search_yandex(FAKE_BYTES, max_results=20))
    for item in result["results"]:
        assert "url" in item and "type" in item and "title" in item
        assert item["url"].startswith("http")
    print(f"  ✓ {len(result['results'])} item doğru şemada")


if __name__ == "__main__":
    tests = [
        test_playwright_unavailable_returns_error,
        test_successful_search_returns_results,
        test_captcha_page_returns_error,
        test_max_results_respected,
        test_result_schema,
    ]
    failures = []
    print(f"\n{'='*55}\n Yandex Search — {len(tests)} test\n{'='*55}")
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            import traceback
            print(f"  ✗ {t.__name__}: {e}")
            traceback.print_exc()
            failures.append(t.__name__)
    print(f"\n{'='*55}")
    if failures:
        print(f" BAŞARISIZ: {failures}")
        sys.exit(1)
    print(" TÜM TESTLER GEÇTİ ✓")
    print("="*55)

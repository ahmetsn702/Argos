import pytest
import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.watchlist.archiver import WatchlistArchiver

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

class MockStorage:
    def __init__(self):
        self.saved_files = {}

    async def save(self, key: str, data: bytes) -> str:
        self.saved_files[key] = data
        return f"local://{key}"

    async def list(self, prefix: str = "") -> list:
        return [f"local://{k}" for k in self.saved_files.keys() if k.startswith(prefix)]

def test_archiver_init():
    storage = MockStorage()
    archiver = WatchlistArchiver(storage_adapter=storage)
    assert archiver.storage is storage

def test_archive_no_url():
    storage = MockStorage()
    archiver = WatchlistArchiver(storage_adapter=storage)
    
    with patch("playwright.async_api.async_playwright", side_effect=ImportError):
        uri = _run(archiver.archive(target_id=123, data={"value": "some_value"}))
        
    target_hash = hashlib.md5(b"123").hexdigest()
    assert uri.startswith(f"local://{target_hash}/")
    
    html_keys = [k for k in storage.saved_files.keys() if k.endswith("source.html")]
    assert len(html_keys) == 1
    assert target_hash in html_keys[0]
    
    html_content = storage.saved_files[html_keys[0]].decode("utf-8")
    assert "Archive of Target 123" in html_content
    assert "some_value" in html_content

def test_archive_url_prepends_http():
    storage = MockStorage()
    archiver = WatchlistArchiver(storage_adapter=storage)
    
    with patch("playwright.async_api.async_playwright", side_effect=ImportError):
        _run(archiver.archive(target_id=456, data={"url": "example.com"}))
        
    html_keys = [k for k in storage.saved_files.keys() if k.endswith("source.html")]
    html_content = storage.saved_files[html_keys[0]].decode("utf-8")
    assert "example.com" in html_content

def test_archive_playwright_exception():
    storage = MockStorage()
    archiver = WatchlistArchiver(storage_adapter=storage)
    
    with patch("playwright.async_api.async_playwright", side_effect=Exception("Playwright is broken")):
        uri = _run(archiver.archive(target_id=789, data={"url": "http://example.com"}))
        
    target_hash = hashlib.md5(b"789").hexdigest()
    html_keys = [k for k in storage.saved_files.keys() if k.endswith("source.html")]
    assert len(html_keys) == 1
    html_content = storage.saved_files[html_keys[0]].decode("utf-8")
    assert "Playwright capture failed: Playwright is broken" in html_content

def test_archive_locks():
    storage = MockStorage()
    archiver = WatchlistArchiver(storage_adapter=storage)
    
    WatchlistArchiver._locks.clear()
    
    with patch("playwright.async_api.async_playwright", side_effect=ImportError):
        _run(archiver.archive(target_id=1, data={}))
        
    assert 1 in WatchlistArchiver._locks
    assert isinstance(WatchlistArchiver._locks[1], asyncio.Lock)

def test_get_archive_empty():
    storage = MockStorage()
    archiver = WatchlistArchiver(storage_adapter=storage)
    res = _run(archiver.get_archive(target_id=999))
    assert res == []

def test_get_archive_sorting_and_grouping():
    storage = MockStorage()
    target_id = 55
    target_hash = hashlib.md5(str(target_id).encode("utf-8")).hexdigest()
    
    storage.saved_files[f"{target_hash}/2026-05-22T20-00-00/screenshot.png"] = b"scr1"
    storage.saved_files[f"{target_hash}/2026-05-22T20-00-00/source.html"] = b"html1"
    storage.saved_files[f"{target_hash}/2026-05-22T21-00-00/screenshot.png"] = b"scr2"
    storage.saved_files[f"{target_hash}/2026-05-22T21-00-00/source.html"] = b"html2"
    
    archiver = WatchlistArchiver(storage_adapter=storage)
    archives = _run(archiver.get_archive(target_id))
    
    assert len(archives) == 2
    assert archives[0]["timestamp"] == "2026-05-22T21:00:00"
    assert archives[0]["screenshot_uri"] == f"local://{target_hash}/2026-05-22T21-00-00/screenshot.png"
    assert archives[0]["html_uri"] == f"local://{target_hash}/2026-05-22T21-00-00/source.html"
    
    assert archives[1]["timestamp"] == "2026-05-22T20:00:00"
    assert archives[1]["screenshot_uri"] == f"local://{target_hash}/2026-05-22T20-00-00/screenshot.png"
    assert archives[1]["html_uri"] == f"local://{target_hash}/2026-05-22T20-00-00/source.html"

def test_get_archive_ignore_unrelated():
    storage = MockStorage()
    target_id = 77
    target_hash = hashlib.md5(str(target_id).encode("utf-8")).hexdigest()
    other_hash = hashlib.md5(b"88").hexdigest()
    
    storage.saved_files[f"{target_hash}/2026-05-22T20-00-00/screenshot.png"] = b"scr1"
    storage.saved_files[f"{other_hash}/2026-05-22T20-00-00/screenshot.png"] = b"scr_other"
    storage.saved_files[f"{target_hash}/invalid-structure.png"] = b"invalid"
    
    archiver = WatchlistArchiver(storage_adapter=storage)
    archives = _run(archiver.get_archive(target_id))
    
    assert len(archives) == 1
    assert archives[0]["screenshot_uri"] == f"local://{target_hash}/2026-05-22T20-00-00/screenshot.png"

def test_archive_success_playwright_mock():
    storage = MockStorage()
    archiver = WatchlistArchiver(storage_adapter=storage)
    
    mock_playwright = MagicMock()
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_page.goto = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"mocked_screenshot")
    mock_page.content = AsyncMock(return_value="<html>mocked_content</html>")
    
    class MockAsyncContextManager:
        async def __aenter__(self):
            return mock_playwright
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    with patch("playwright.async_api.async_playwright", return_value=MockAsyncContextManager()):
        uri = _run(archiver.archive(target_id=111, data={"url": "http://google.com"}))
        
    target_hash = hashlib.md5(b"111").hexdigest()
    assert uri.startswith(f"local://{target_hash}/")
    
    screenshot_keys = [k for k in storage.saved_files.keys() if k.endswith("screenshot.png")]
    html_keys = [k for k in storage.saved_files.keys() if k.endswith("source.html")]
    
    assert len(screenshot_keys) == 1
    assert len(html_keys) == 1
    assert storage.saved_files[screenshot_keys[0]] == b"mocked_screenshot"
    assert storage.saved_files[html_keys[0]] == b"<html>mocked_content</html>"

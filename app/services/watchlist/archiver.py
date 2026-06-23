import hashlib
import json
import asyncio
from datetime import datetime
from typing import Any, List, Optional
from app.services.storage.factory import get_storage_adapter
from app.repositories.watchlist_repo import WatchlistRepository

class WatchlistArchiver:
    _locks = {}

    def __init__(self, storage_adapter=None):
        self.storage = storage_adapter or get_storage_adapter()

    async def archive(self, target_id: Any, data: dict) -> str:
        # Avoid concurrent archive runs for the same target_id
        if target_id not in self._locks:
            self._locks[target_id] = asyncio.Lock()
        
        async with self._locks[target_id]:
            target_hash = hashlib.md5(str(target_id).encode("utf-8")).hexdigest()
            # ISO timestamp without colons for Windows compatibility
            timestamp = datetime.utcnow().isoformat()
            ts = timestamp.replace(":", "-")
            
            screenshot_key = f"{target_hash}/{ts}/screenshot.png"
            html_key = f"{target_hash}/{ts}/source.html"
            
            # Determine URL to navigate
            url = data.get("url")
            target_value = data.get("value") or data.get("target_value")
            
            if not url:
                try:
                    repo = WatchlistRepository()
                    target = await repo.get_target(target_id)
                    if target:
                        target_value = target.value
                        if target.type in ("domain", "url"):
                            url = target_value
                except Exception:
                    pass
            
            if url and not url.startswith(("http://", "https://")):
                url = f"http://{url}"
            
            screenshot_bytes = b""
            html_content = ""
            
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context()
                    page = await context.new_page()
                    
                    if url:
                        try:
                            await page.goto(url, timeout=30000)
                            screenshot_bytes = await page.screenshot(full_page=True)
                            html_content = await page.content()
                        except Exception as e:
                            # Fallback: screenshot fail -> HTML-only
                            html_content = f"<html><body><h1>Archive of Target {target_id}</h1><p>Failed to load {url}: {str(e)}</p><pre>{json.dumps(data, indent=2)}</pre></body></html>"
                            await page.set_content(html_content)
                            screenshot_bytes = await page.screenshot(full_page=True)
                    else:
                        html_content = f"<html><body><h1>Archive of Target {target_id}</h1><pre>{json.dumps(data, indent=2)}</pre></body></html>"
                        await page.set_content(html_content)
                        screenshot_bytes = await page.screenshot(full_page=True)
                        
                    await browser.close()
            except Exception as e:
                # Playwright failed to launch or is missing
                if not html_content:
                    html_content = f"<html><body><h1>Archive of Target {target_id}</h1><p>Playwright capture failed: {str(e)}</p><pre>{json.dumps(data, indent=2)}</pre></body></html>"
            
            # Save files
            if screenshot_bytes:
                await self.storage.save(screenshot_key, screenshot_bytes)
            await self.storage.save(html_key, html_content.encode("utf-8"))
            
            return f"local://{target_hash}/{ts}"

    async def get_archive(self, target_id: Any) -> List[dict]:
        target_hash = hashlib.md5(str(target_id).encode("utf-8")).hexdigest()
        uris = await self.storage.list(prefix=target_hash)
        
        archives = {}
        for uri in uris:
            clean_uri = uri
            if clean_uri.startswith("local://"):
                path_part = clean_uri[len("local://"):]
            else:
                path_part = clean_uri
                
            parts = path_part.split("/")
            if len(parts) >= 3:
                t_hash, ts, filename = parts[0], parts[1], parts[2]
                if t_hash == target_hash:
                    if ts not in archives:
                        if "T" in ts:
                            date_part, time_part = ts.split("T", 1)
                            timestamp_val = f"{date_part}T{time_part.replace('-', ':')}"
                        else:
                            timestamp_val = ts.replace("-", ":")
                        archives[ts] = {
                            "timestamp": timestamp_val,
                            "screenshot_uri": None,
                            "html_uri": None
                        }
                    if filename == "screenshot.png":
                        archives[ts]["screenshot_uri"] = uri
                    elif filename == "source.html":
                        archives[ts]["html_uri"] = uri
                        
        result = list(archives.values())
        result.sort(key=lambda x: x["timestamp"], reverse=True)
        return result

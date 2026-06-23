# Monkeypatch: page.title() çağrılarını güvenli hale getirir (async+sync).
# Not: İçeride asla self.title() çağırmayız; sadece evaluate/og:title kullanırız.
def apply():
    # ---- ASYNC ----
    try:
        from playwright.async_api import Page as APage
        async def _safe_title_async(self):
            import re, asyncio
            for _ in range(5):
                try:
                    try:
                        await self.wait_for_load_state("domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    try:
                        await self.wait_for_load_state("networkidle", timeout=2000)
                    except Exception:
                        pass
                    await self.wait_for_timeout(200)
                    t = await self.evaluate("document.title || ''")
                    if t:
                        return t
                except Exception:
                    await asyncio.sleep(0.3)
                    continue
            try:
                html = await self.content()
                m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"<]+)', html, re.I)
                if m:
                    return m.group(1)
            except Exception:
                pass
            return ""
        APage.title = _safe_title_async
    except Exception:
        pass

    # ---- SYNC ----
    try:
        from playwright.sync_api import Page as SPage
        def _safe_title_sync(self):
            import re, time
            for _ in range(5):
                try:
                    try:
                        self.wait_for_load_state("domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    try:
                        self.wait_for_load_state("networkidle", timeout=2000)
                    except Exception:
                        pass
                    self.wait_for_timeout(200)
                    t = self.evaluate("document.title || ''")
                    if t:
                        return t
                except Exception:
                    time.sleep(0.3)
                    continue
            try:
                html = self.content()
                m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"<]+)', html, re.I)
                if m:
                    return m.group(1)
            except Exception:
                pass
            return ""
        SPage.title = _safe_title_sync
    except Exception:
        pass

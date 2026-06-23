from fastapi import APIRouter
import sys, inspect

router = APIRouter()

@router.get("/__pw_status")
async def pw_status():
    out = {"sitecustomize_loaded": "sitecustomize" in sys.modules}
    try:
        import playwright.async_api as pa
        fn = pa.Page.title
        out["async_title_qualname"] = getattr(fn, "__qualname__", str(fn))
        out["async_title_module"]   = getattr(fn, "__module__", "")
    except Exception as e:
        out["async_title_error"] = repr(e)
    try:
        import playwright._impl._page as impl
        fn = impl.Page.title
        out["impl_title_qualname"] = getattr(fn, "__qualname__", str(fn))
        out["impl_title_module"]   = getattr(fn, "__module__", "")
    except Exception as e:
        out["impl_title_error"] = repr(e)
    return out

@router.get("/__pw_smoke")
async def pw_smoke():
    # run page.title() inside the *server process* to see if it still blows up
    from playwright.async_api import async_playwright
    out = {}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            page = await b.new_page()
            await page.goto("https://www.linkedin.com", wait_until="domcontentloaded")
            out["title"] = await page.title()  # should be patched and safe
            await b.close()
        out["ok"] = True
    except Exception as e:
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
    return out
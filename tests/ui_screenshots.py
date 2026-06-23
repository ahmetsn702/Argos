"""Quick visual check — one module at a time, take screenshots."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
MINI = ROOT / "ui" / "mini_panel.html"
SHOTS = ROOT / "tests" / "screenshots"
SHOTS.mkdir(exist_ok=True)

# Aynı mock payloadlarını import et
sys.path.insert(0, str(ROOT / "tests"))
from ui_smoke_test import MOCK


def install_fetch_mock(page):
    js = """
    (() => {
      const MOCK = __MOCK__;
      window.fetch = async (url) => {
        for (const [k,v] of Object.entries(MOCK)) {
          if (String(url).includes(k))
            return new Response(JSON.stringify(v), {status:200, headers:{'Content-Type':'application/json'}});
        }
        return new Response('{}', {status:404});
      };
    })();
    """.replace("__MOCK__", json.dumps(MOCK))
    page.evaluate(js)


def shot(page, name):
    p = SHOTS / f"{name}.png"
    page.screenshot(path=str(p), full_page=False)
    print(f"  → {p.name}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(MINI.as_uri())
        page.wait_for_load_state("networkidle")
        install_fetch_mock(page)

        scenarios = [
            ("mosint", "card-mosint", "#ms-btn", lambda: page.fill("#ms-email", "test@example.com")),
            ("phone", "card-phone", "#phone-btn", lambda: page.fill("#phone-num", "+905551234567")),
            ("darkweb", "card-darkweb", "#dw-btn", lambda: page.fill("#dw-q", "test@example.com")),
            ("domain", "card-domain", "#dm-btn", lambda: page.fill("#dm-target", "google.com")),
            ("face", "card-face", None, None),  # face requires file upload
            ("geo", "card-geo", None, None),  # geo also file
            ("compare", "card-compare", "#cmp-btn", lambda: page.fill("#cmp-user", "testuser")),
            ("huntx", "card-huntx", "#hunt-btn", lambda: page.fill("#hunt-name", "Test User")),
            ("bios", "card-bios", "#bios-btn", lambda: page.fill("#bios-user", "testuser")),
            ("temporal", "card-temporal", "#ti-btn", lambda: page.fill("#ti-seed", "email:test@x.com")),
            ("pivot", "card-pivot", "#pv-btn", lambda: (
                page.fill("#pv-fid", "email:x@x.com"),
                page.fill("#pv-seed", "x@x.com"),
            )),
        ]

        for name, target, btn, fill in scenarios:
            page.click(f'.sidebar button[data-target="{target}"]')
            page.wait_for_timeout(80)
            if btn and fill:
                fill()
                page.click(btn)
                page.wait_for_timeout(500)
            shot(page, name)

        # Open tech details for one module
        page.click('.sidebar button[data-target="card-darkweb"]')
        page.wait_for_timeout(80)
        page.click("#dw-tech > summary")
        page.wait_for_timeout(200)
        shot(page, "darkweb_tech_open")

        browser.close()
    print(f"\nGörüntüler: {SHOTS}")


if __name__ == "__main__":
    main()

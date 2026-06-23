"""
ARGOS Mini Panel + Index UI Smoke Test
=======================================

Sunucu başlatmadan, file:// üzerinden HTML yüklenir.
Fetch çağrıları mock'lanır; her modülün renderer'ı için örnek JSON beslenir
ve özet kartlarının render edildiği, "Teknik Detaylar" toggle'ının
varsayılan kapalı olduğu doğrulanır.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
MINI = UI_DIR / "mini_panel.html"
INDEX = UI_DIR / "index.html"


# ─── Mock response payload'ları ──────────────────────────────────────
MOCK = {
    # MOSINT
    "/mosint/full": {
        "email": "test@example.com",
        "deliverable": "deliverable",
        "is_smtp_valid": True,
        "is_format_valid": True,
        "provider": "Gmail",
        "quality_score": 0.85,
        "mx": {"ok": True, "servers": [
            {"host": "smtp.gmail.com", "preference": 10},
            {"host": "alt1.smtp.gmail.com", "preference": 20}
        ]},
        "smtp": {"ok": True, "supported": True, "code": 250, "message": "OK", "mx_used": "smtp.gmail.com"},
        "hibp": {"ok": True, "breached": True, "count": 3,
                 "items": [{"Name": "LinkedIn"}, {"Name": "Adobe"}, {"Name": "Dropbox"}]},
        "gravatar": {"hash": "abc", "exists": True,
                     "profile": {"entry": [{"displayName": "Test User"}]}},
        "emailrep": {"ok": True, "data": {"reputation": "high", "suspicious": False}},
        "openpgp": {"ok": True, "count": 0},
    },
    # Phone
    "/phone/lookup": {
        "input": "05551234567",
        "normalized": "+905551234567",
        "numverify": {"ok": True, "valid": True, "country": "Turkey",
                      "carrier": "Turkcell", "line_type": "mobile",
                      "location": "Istanbul"},
        "abstract": {"ok": True, "country": "Turkey", "country_code": "TR",
                     "city": "Istanbul", "region": "Marmara",
                     "carrier": "Turkcell", "line_type": "mobile",
                     "timezone": "Europe/Istanbul"},
    },
    # Dark Web
    "/darkweb/lookup": {
        "query": "test@example.com",
        "query_type": "email",
        "leakcheck": {"ok": True, "found": 5,
                      "sources": [
                          {"name": "Adobe", "date": "2013-10", "fields": ["email", "password", "username"]},
                          {"name": "LinkedIn", "date": "2012-05", "fields": ["email", "password"]},
                          {"name": "MyFitnessPal", "date": "2018-02", "fields": ["email", "password"]},
                      ]},
        "summary": {"total_breaches": 5, "sources": ["Adobe", "LinkedIn", "MyFitnessPal"]},
    },
    # Domain
    "/domain/lookup": {
        "target": "google.com", "ip": "142.250.185.78",
        "whois": {"ok": True, "registrar": "MarkMonitor Inc.",
                  "created": "1997-09-15T07:00:00+00:00",
                  "updated": "2019-09-09T00:00:00+00:00",
                  "expires": "2028-09-13T07:00:00+00:00"},
        "dns": {"ok": True, "records": {
            "A": ["142.250.185.78"],
            "MX": ["10 smtp.google.com."],
            "NS": ["ns1.google.com.", "ns2.google.com.", "ns3.google.com."],
            "TXT": ["v=spf1 include:_spf.google.com ~all"]
        }},
        "geo": {"ok": True, "city": "Mountain View", "region": "California",
                "country": "United States", "isp": "Google LLC", "lat": 37.386, "lng": -122.084},
        "shodan": {"ok": False, "error": "ücretsiz planda yok"},
    },
    # IG Bio
    "/ig/bio": {
        "username": "testuser", "bio": "Yazılım geliştirici 💻\nİstanbul",
        "full_name": "Test User", "source": "api"
    },
    # IG Profile v2
    "/v2/ig-profile": {
        "username": "testuser", "biography": "Yazılım geliştirici 💻",
        "full_name": "Test User", "source": "service"
    },
    # Photos
    "/photos": {
        "photos": [
            {"url": "https://via.placeholder.com/100", "source": "instagram"},
            {"url": "https://via.placeholder.com/100", "source": "instagram"},
            {"url": "https://via.placeholder.com/100", "source": "x"},
        ]
    },
    # Compare
    "/compare-ig-x2": {
        "impl": "smartscore-v1.1",
        "instagram": {"username": "testuser", "display_name": "Test User",
                      "bio": "Developer 💻", "status": "exists",
                      "profile_url": "https://instagram.com/testuser"},
        "x_twitter": {"username": "testuser", "display_name": "Test User",
                      "bio": "Software dev 💻", "status": "exists",
                      "profile_url": "https://x.com/testuser"},
        "similarity": {"jaccard_raw": 0.8, "char_trigram_raw": 0.75, "score_raw": 0.78},
        "score": 0.93, "verdict": "High",
    },
    # Hunt X
    "/hunt-x-by-name": {
        "full_name": "Test User", "keywords": ["dev", "istanbul"],
        "candidates_tried": 12,
        "results": [
            {"username": "testuser", "profile": {
                "status": "exists", "username": "testuser",
                "display_name": "Test User", "bio": "Developer in Istanbul",
                "profile_url": "https://x.com/testuser"
            }, "scores": {"total": 0.92, "name_score": 0.95, "keyword_hits": 2, "keyword_score": 1.0}},
            {"username": "test_user_42", "profile": {
                "status": "exists", "username": "test_user_42",
                "display_name": "Test User", "bio": "",
                "profile_url": "https://x.com/test_user_42"
            }, "scores": {"total": 0.65, "name_score": 0.95, "keyword_hits": 0, "keyword_score": 0.0}},
        ],
    },
    # EXIF
    "/tester/exif": {
        "ok": True, "size": 1234567, "format": "JPEG", "mode": "RGB",
        "exif": {
            "Make": "Apple", "Model": "iPhone 13",
            "DateTime": "2024:01:15 14:30:00",
            "DateTimeOriginal": "2024:01:15 14:30:00",
            "Software": "iOS 17.2", "Orientation": "1",
            "GPSInfo": "(41.0082, 28.9784)",
            "ExifImageWidth": 4032, "ExifImageHeight": 3024,
        }
    },
    # Unified (scan/full)
    "/scan/full": {
        "input": {"username": "testuser"},
        "results": {
            "social": {"ok": True, "duration_ms": 4321,
                       "data": {"results": [{"username": "testuser"}, {"username": "test_user"}]}},
            "linkedin": {"ok": False, "duration_ms": 2100, "error": "Profile not found"},
        },
        "verdict": "partial", "took_ms": 6543,
    },
    # Username Bios
    "/username-bios": {
        "username": "testuser", "count": 5,
        "results": [
            {"platform": "Instagram", "url": "https://instagram.com/testuser",
             "status": "exists", "display_name": "Test User", "bio": "Developer 💻"},
            {"platform": "GitHub", "url": "https://github.com/testuser",
             "status": "exists", "display_name": "Test", "bio": "Code"},
            {"platform": "Reddit", "url": "https://reddit.com/u/testuser",
             "status": "not_found", "display_name": "", "bio": ""},
            {"platform": "X", "url": "https://x.com/testuser",
             "status": "exists", "display_name": "Test User", "bio": "Software dev"},
            {"platform": "YouTube", "url": "https://youtube.com/@testuser",
             "status": "unknown", "display_name": "", "bio": ""},
        ],
    },
    # Face
    "/face/search": {
        "verdict": "matches_found",
        "face_detection": {
            "face_count": 1, "engine_ok": True,
            "faces": [{"approximate_age": "25-35",
                       "gender_presentation": "male",
                       "emotion": "neutral",
                       "description": "Sakallı, güneş gözlüklü yetişkin erkek"}],
        },
        "engines": {
            "saucenao": {"engine": "saucenao", "ok": True,
                         "results": [{"type": "saucenao", "url": "https://example.com/match1",
                                      "title": "Match 1", "similarity": 87}],
                         "error": None, "took_ms": 1234},
            "yandex": {"engine": "yandex", "ok": True,
                       "results": [{"type": "yandex_site", "url": "https://example.org/person",
                                    "title": "Kişi Fotoğrafı"}],
                       "error": None, "took_ms": 8765},
            "google_vision": {"engine": "google_vision", "ok": True,
                              "results": [{"type": "matching_page", "url": "https://example.com/page",
                                           "title": "Page Title"}],
                              "entities": [{"description": "person", "score": 0.9}],
                              "face_count": 1, "took_ms": 2345},
        },
        "matches": [
            {"type": "saucenao", "url": "https://example.com/match1", "title": "Match 1", "similarity": 87},
            {"type": "yandex_site", "url": "https://example.org/person", "title": "Kişi Fotoğrafı"},
            {"type": "matching_page", "url": "https://example.com/page", "title": "Page Title"},
        ],
        "match_count": 3, "took_ms": 9876,
    },
    # Geo
    "/geo/analyze-photo": {
        "source": "exif", "lat": 41.0082, "lng": 28.9784,
        "confidence": 0.99, "radius_km": 1,
        "country": "Turkey", "region": "Istanbul",
        "reasoning": {"method": "GPS coordinates from EXIF metadata"},
        "fallback": False,
    },
    # Temporal
    "/temporal/analyze": {
        "seed_key": "email:test@x.com",
        "computed_at": "2025-05-23T22:00:00",
        "events": [{"event_type": "login", "timestamp": "2025-01-01", "source": "auth"}],
        "clusters": [{"id": "c1"}],
        "anomalies": [
            {"type": "burst", "severity": "high", "explanation": "Sudden activity spike"},
            {"type": "gap", "severity": "low", "explanation": "Gap detected"},
        ],
        "narrative": "Kullanıcı 1 Ocak'ta giriş yaptı, sonra anormal yoğun aktivite.",
    },
    # Pivot
    "/pivot/run": {
        "session_id": "sess_abc123", "status": "completed",
        "nodes_discovered": [
            {"entity_type": "email", "value": "x@x.com", "depth": 0},
            {"entity_type": "username", "value": "xuser", "depth": 1},
            {"entity_type": "phone", "value": "+9055xxx", "depth": 2},
        ],
        "depth_reached": 2, "max_depth": 2, "expansions_count": 5,
    },
}


def setup_mock_routes(page):
    """Inject window.fetch override into the CURRENT page.
    add_init_script sadece future navigations için çalışır, evaluate ise current page için.
    """
    js = """
    (() => {
      const MOCK = __MOCK_PAYLOAD__;
      const _origFetch = window.fetch.bind(window);
      window.fetch = async (url, opts) => {
        const u = String(url);
        for (const [prefix, body] of Object.entries(MOCK)) {
          if (u.includes(prefix)) {
            return new Response(JSON.stringify(body), {
              status: 200,
              headers: {'Content-Type': 'application/json'}
            });
          }
        }
        return new Response(JSON.stringify({error: 'no mock for ' + u}),
          {status: 404, headers: {'Content-Type': 'application/json'}});
      };
      window.__MOCK_INSTALLED__ = true;
    })();
    """.replace("__MOCK_PAYLOAD__", json.dumps(MOCK))
    page.evaluate(js)
    installed = page.evaluate("window.__MOCK_INSTALLED__ === true")
    assert installed, "fetch mock yüklenmedi"


def assert_summary_visible(page, prefix: str, label: str):
    """Özet kartının görünür olduğunu doğrula."""
    sel = f"#{prefix}-summary"
    page.wait_for_selector(sel + ".show", timeout=4000)
    txt = page.text_content(sel)
    assert txt and txt.strip(), f"{label}: özet kart boş!"
    return txt


def assert_tech_closed(page, prefix: str, label: str):
    """Teknik Detaylar toggle'ı varsayılan kapalı mı?"""
    sel = f"#{prefix}-tech"
    is_open = page.evaluate(f"document.querySelector('{sel}')?.open")
    assert not is_open, f"{label}: Teknik Detaylar varsayılan AÇIK olmamalı!"


def assert_tech_can_toggle(page, prefix: str, label: str):
    """Toggle açılıp kapanabiliyor mu?"""
    sel = f"#{prefix}-tech"
    page.click(f"{sel} > summary")
    is_open = page.evaluate(f"document.querySelector('{sel}')?.open")
    assert is_open, f"{label}: Tıklanınca açılmadı!"
    page.click(f"{sel} > summary")
    is_open = page.evaluate(f"document.querySelector('{sel}')?.open")
    assert not is_open, f"{label}: Tekrar tıklanınca kapanmadı!"


# ─── Test sequences ──────────────────────────────────────────────────

def test_mini_panel(page):
    print("\n" + "=" * 60)
    print(" mini_panel.html — UI Smoke Test")
    print("=" * 60)

    page.goto(MINI.as_uri())
    page.wait_for_load_state("networkidle")

    # 1. Sidebar varlığı
    btns = page.locator(".sidebar button").all()
    assert len(btns) >= 17, f"Beklenen 17+ sidebar butonu, var: {len(btns)}"
    print(f"  ✓ Sidebar: {len(btns)} buton")

    # 2. Her sidebar butonu tıklanınca ilgili kart aktif olmalı
    for b in btns:
        target = b.get_attribute("data-target")
        b.click()
        page.wait_for_timeout(50)
        active = page.locator(".card.active").count()
        assert active == 1, f"{target}: tek bir aktif kart olmalı, {active} bulundu"
        active_id = page.locator(".card.active").get_attribute("id")
        assert active_id == target, f"Beklenen aktif kart {target}, gerçek {active_id}"
    print(f"  ✓ Sidebar navigasyonu: {len(btns)} kart açılıp kapandı")

    # 3. Mock backend'i aktif et
    setup_mock_routes(page)

    # 4. Modül modül test et
    tests = [
        # (sidebar-target, prefix, input doldurma fonksiyonu, beklenen özet metni parçası)
        ("card-mosint", "ms", lambda p: p.fill("#ms-email", "test@example.com"), "geçerli ve teslim edilebilir"),
        ("card-phone", "phone", lambda p: p.fill("#phone-num", "+905551234567"), "geçerli numara"),
        ("card-darkweb", "dw", lambda p: p.fill("#dw-q", "test@example.com"), "veri ihlalinde bulundu"),
        ("card-domain", "dm", lambda p: p.fill("#dm-target", "google.com"), "MarkMonitor"),
        ("card-igbio", "igbio", lambda p: p.fill("#igbio-user", "testuser"), "@testuser"),
        ("card-igp2", "igp2", lambda p: p.fill("#igp2-user", "testuser"), "@testuser"),
        ("card-photos", "pho", lambda p: p.fill("#pho-user", "testuser"), "3 görsel"),
        ("card-compare", "cmp", lambda p: p.fill("#cmp-user", "testuser"), "Yüksek eşleşme"),
        ("card-huntx", "hunt", lambda p: p.fill("#hunt-name", "Test User"), "2 sonuç"),
        ("card-bios", "bios", lambda p: p.fill("#bios-user", "testuser"), "platformda bulundu"),
        ("card-temporal", "ti", lambda p: p.fill("#ti-seed", "email:test@x.com"), "anomali"),
        ("card-pivot", "pv",
         lambda p: (p.fill("#pv-fid", "email:x@x.com"), p.fill("#pv-seed", "x@x.com")),
         "completed"),
        ("card-unified", "uni", lambda p: p.fill("#uni-user", "testuser"), "Birleşik analiz"),
    ]

    btn_id_map = {
        "ms": "#ms-btn", "phone": "#phone-btn", "dw": "#dw-btn", "dm": "#dm-btn",
        "igbio": "#igbio-btn", "igp2": "#igp2-btn", "pho": "#pho-btn",
        "cmp": "#cmp-btn", "hunt": "#hunt-btn", "bios": "#bios-btn",
        "ti": "#ti-btn", "pv": "#pv-btn", "uni": "#uni-btn",
    }

    for target, prefix, fill_fn, expected in tests:
        page.click(f'.sidebar button[data-target="{target}"]')
        page.wait_for_timeout(60)
        fill_fn(page)
        page.click(btn_id_map[prefix])
        try:
            page.wait_for_selector(f"#{prefix}-summary.show", timeout=5000)
        except Exception:
            print(f"  ✗ {target} ({prefix}): summary 5s içinde görünmedi")
            raise
        txt = page.text_content(f"#{prefix}-summary") or ""
        if expected not in txt:
            print(f"  ✗ {target}: '{expected}' özet metnde YOK")
            print(f"    Gerçek metin (ilk 200): {txt.strip()[:200]}")
            raise AssertionError(f"{target}: '{expected}' bekleniyordu")
        # Tech toggle kapalı mı?
        is_open = page.evaluate(f"document.querySelector('#{prefix}-tech')?.open")
        assert not is_open, f"{target}: Teknik Detaylar varsayılan AÇIK olmamalı"
        print(f"  ✓ {target}: özet üretildi ('{expected}'), tech kapalı")

    # 5. Tech toggle çalışıyor mu?
    page.click('.sidebar button[data-target="card-mosint"]')
    page.wait_for_timeout(30)
    page.click("#ms-tech > summary")
    is_open = page.evaluate("document.querySelector('#ms-tech')?.open")
    assert is_open, "Tech tıklanınca açılmadı"
    page.click("#ms-tech > summary")
    is_open = page.evaluate("document.querySelector('#ms-tech')?.open")
    assert not is_open, "Tech tekrar tıklanınca kapanmadı"
    print("  ✓ Teknik Detaylar toggle: aç/kapa çalışıyor")

    # 6. Console errorları yok mu?
    print("  ✓ Tüm modüller smoke test'i geçti")

    # 7. Yandex checkbox ID düzeltmesi — face-saucenao ve face-yandex var mı?
    page.click('.sidebar button[data-target="card-face"]')
    page.wait_for_timeout(60)
    saucenao_cb = page.locator("#face-saucenao")
    yandex_cb = page.locator("#face-yandex")
    assert saucenao_cb.count() == 1, "face-saucenao checkbox yok!"
    assert yandex_cb.count() == 1, "face-yandex checkbox yok!"
    # SauceNAO default checked, Yandex default unchecked
    assert saucenao_cb.is_checked(), "face-saucenao default checked olmalı"
    assert not yandex_cb.is_checked(), "face-yandex default unchecked olmalı"
    # Yandex'i işaretle
    yandex_cb.check()
    assert yandex_cb.is_checked(), "face-yandex işaretlenemedi"
    print("  ✓ face-saucenao (checked) + face-yandex (unchecked→checked) checkbox'ları OK")


def test_index(page):
    print("\n" + "=" * 60)
    print(" index.html — UI Smoke Test")
    print("=" * 60)

    page.goto(INDEX.as_uri())
    page.wait_for_load_state("networkidle")

    # Tabs var mı?
    tabs = page.locator(".tab").all()
    assert len(tabs) >= 6, f"En az 6 tab beklenir, {len(tabs)} bulundu"
    print(f"  ✓ Tabs: {len(tabs)}")

    setup_mock_routes(page)

    # Email tab — gerçekçi card render
    page.click('.tab[data-panel="email"]')
    page.fill("#e-input", "test@example.com")
    page.click("#e-btn")
    page.wait_for_selector("#e-result:not([style*='display: none'])", timeout=5000)
    e_text = page.text_content("#e-cards") or ""
    assert "Geçerli" in e_text, f"Email kartında 'Geçerli' yok. Metin: {e_text[:200]}"
    print("  ✓ Email tab: kartlar düzgün render ediliyor")

    # Phone tab
    page.click('.tab[data-panel="phone"]')
    page.fill("#p-input", "+905551234567")
    page.click("#p-btn")
    page.wait_for_selector("#p-result:not([style*='display: none'])", timeout=5000)
    p_text = page.text_content("#p-cards") or ""
    assert "Turkcell" in p_text, f"Phone kartında 'Turkcell' yok. Metin: {p_text[:200]}"
    print("  ✓ Phone tab: kartlar düzgün render ediliyor")

    # Unified tab — Teknik Detaylar toggle gizli olmalı
    page.click('.tab[data-panel="unified"]')
    page.fill("#u-username", "testuser")
    page.click("#u-btn")
    page.wait_for_selector("#u-result:not([style*='display: none'])", timeout=5000)
    u_cards_text = page.text_content("#u-cards") or ""
    assert ("partial" in u_cards_text.lower() or "Kısmi" in u_cards_text), \
        f"Unified verdict bulunamadı. Metin: {u_cards_text[:200]}"
    # Tech-details kapalı mı?
    tech_details = page.locator("#panel-unified details.tech-details").first
    assert not tech_details.evaluate("e => e.open"), \
        "Unified Teknik Detaylar varsayılan AÇIK olmamalı"
    # Aç-kapa çalışıyor mu?
    page.click("#panel-unified details.tech-details > summary")
    assert tech_details.evaluate("e => e.open"), "Tech-details açılmadı"
    page.click("#panel-unified details.tech-details > summary")
    assert not tech_details.evaluate("e => e.open"), "Tech-details kapanmadı"
    print("  ✓ Unified tab: kartlar + Teknik Detaylar toggle çalışıyor")

    print("  ✓ index.html smoke test'i geçti")


def main():
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Konsoldaki hataları yakala
        console_errors = []
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))
        page.on("console", lambda msg:
                console_errors.append(msg.text) if msg.type == "error" else None)

        try:
            test_mini_panel(page)
        except Exception as e:
            failures.append(("mini_panel", e))

        try:
            test_index(page)
        except Exception as e:
            failures.append(("index", e))

        if console_errors:
            print("\n--- Konsol/sayfa hataları ---")
            for err in console_errors[:10]:
                print("  !", err)

        browser.close()

    print("\n" + "=" * 60)
    if failures:
        print(f" SONUÇ: {len(failures)} BAŞARISIZ")
        for name, err in failures:
            print(f"   ✗ {name}: {err}")
        sys.exit(1)
    else:
        print(" SONUÇ: TÜM TESTLER GEÇTİ ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()

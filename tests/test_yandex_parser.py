# tests/test_yandex_parser.py
"""Birim testler: app/services/_yandex_parser.py"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))

from app.services._yandex_parser import parse_yandex_html, is_captcha_page


# ─── Fixtures ────────────────────────────────────────────────────────────────
SAMPLE_HTML = (FIXTURES / "yandex_sample_result.html").read_text(encoding="utf-8")
CAPTCHA_HTML = (FIXTURES / "yandex_captcha_page.html").read_text(encoding="utf-8")


# ─── Testler ─────────────────────────────────────────────────────────────────

def test_empty_html_returns_empty_list():
    assert parse_yandex_html("") == []
    assert parse_yandex_html("   ") == []

def test_none_like_input():
    assert parse_yandex_html("<html><body></body></html>") == []

def test_parse_site_count():
    results = parse_yandex_html(SAMPLE_HTML)
    sites = [r for r in results if r["type"] == "yandex_site"]
    assert len(sites) == 3, f"Beklenen 3 site, bulundu: {len(sites)}"

def test_parse_site_fields():
    results = parse_yandex_html(SAMPLE_HTML)
    sites = [r for r in results if r["type"] == "yandex_site"]
    first = sites[0]
    assert "url" in first and first["url"].startswith("https://"), f"url hatalı: {first}"
    assert "title" in first and len(first["title"]) > 0, f"title boş: {first}"
    assert first["url"] == "https://example.com/person-photo"
    assert "Örnek" in first["title"]

def test_parse_similar_images():
    results = parse_yandex_html(SAMPLE_HTML)
    similar = [r for r in results if r["type"] == "yandex_similar"]
    assert len(similar) == 2, f"Beklenen 2 benzer görsel, bulundu: {len(similar)}"
    assert similar[0]["url"] == "https://img.example.com/similar1.jpg"

def test_parse_tags():
    results = parse_yandex_html(SAMPLE_HTML)
    tags = [r for r in results if r["type"] == "yandex_tag"]
    assert len(tags) == 3
    tag_texts = [t["title"] for t in tags]
    assert "yüz tanıma" in tag_texts

def test_result_order_sites_first():
    """Site sonuçları benzer görsellerden önce gelir."""
    results = parse_yandex_html(SAMPLE_HTML)
    types = [r["type"] for r in results if r["type"] != "yandex_tag"]
    first_similar = next((i for i, t in enumerate(types) if t == "yandex_similar"), len(types))
    last_site = max((i for i, t in enumerate(types) if t == "yandex_site"), default=-1)
    assert last_site < first_similar, "Site sonuçları benzer görsellerden önce olmalı"

def test_is_captcha_page_true():
    assert is_captcha_page(CAPTCHA_HTML) is True

def test_is_captcha_page_false():
    assert is_captcha_page(SAMPLE_HTML) is False

def test_is_captcha_page_empty():
    assert is_captcha_page("") is False

def test_site_urls_are_valid_http():
    results = parse_yandex_html(SAMPLE_HTML)
    for r in results:
        if r["url"]:
            assert r["url"].startswith("http"), f"Geçersiz URL: {r['url']}"

def test_no_duplicate_urls():
    results = parse_yandex_html(SAMPLE_HTML)
    urls = [r["url"] for r in results if r["url"]]
    assert len(urls) == len(set(urls)), "Duplicate URL var"


# ─── Runner ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    tests = [
        test_empty_html_returns_empty_list,
        test_none_like_input,
        test_parse_site_count,
        test_parse_site_fields,
        test_parse_similar_images,
        test_parse_tags,
        test_result_order_sites_first,
        test_is_captcha_page_true,
        test_is_captcha_page_false,
        test_is_captcha_page_empty,
        test_site_urls_are_valid_http,
        test_no_duplicate_urls,
    ]
    failures = []
    print(f"\n{'='*55}\n Yandex Parser — {len(tests)} test\n{'='*55}")
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            failures.append(t.__name__)
    print(f"\n{'='*55}")
    if failures:
        print(f" BAŞARISIZ: {failures}")
        sys.exit(1)
    print(" TÜM TESTLER GEÇTİ ✓")
    print("="*55)

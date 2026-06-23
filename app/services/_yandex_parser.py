# app/services/_yandex_parser.py
"""
Yandex Images sonuç sayfası HTML parser — Playwright'tan bağımsız saf fonksiyonlar.
Test edilebilir; side-effect yok.
"""
from __future__ import annotations
import re
from typing import List, Dict

# CAPTCHA sayfası işaretleri
_CAPTCHA_PATTERNS = [
    "CheckboxCaptcha",
    "smartcaptcha",
    "captcha__image",
    "showcaptcha",
    "I am not a robot",
]

def is_captcha_page(html: str) -> bool:
    """HTML içeriği CAPTCHA içeriyor mu?"""
    for pat in _CAPTCHA_PATTERNS:
        if pat in html:
            return True
    return False


def _extract_sites(html: str) -> List[Dict]:
    """CbirSites bölümünden siteleri çıkar."""
    results = []

    # Örn: <a class="CbirSites-ItemTitle" href="https://..." ...>Başlık</a>
    links = re.findall(
        r'class="[^"]*CbirSites-ItemTitle[^"]*"[^>]+href="(https?://[^"]+)"[^>]*>([^<]{1,200})',
        html,
    )
    for url, title in links:
        results.append({
            "type": "yandex_site",
            "url": url.strip(),
            "title": title.strip(),
        })

    # Fallback: CbirSites-Item içindeki ilk <a href>
    if not results:
        blocks = re.findall(
            r'CbirSites-Item[^<]*(?:<[^>]+>)*.*?href="(https?://[^"]+)"[^>]*>([^<]{1,200})',
            html, re.DOTALL,
        )
        for url, title in blocks[:10]:
            results.append({
                "type": "yandex_site",
                "url": url.strip(),
                "title": title.strip(),
            })

    return results


def _extract_similar(html: str) -> List[Dict]:
    """CbirSimilar / Thumb bölümünden benzer görsel URL'lerini çıkar."""
    results = []

    # Thumbnail link'leri: Thumb blokları içindeki <a href="https://...">
    # Tipik pattern: class="Thumb-Image" href="https://..."
    links = re.findall(
        r'class="[^"]*Thumb[^"]*"[^>]+href="(https?://[^"]+)"',
        html,
    )
    seen: set = set()
    for url in links:
        url = url.strip()
        if url not in seen:
            seen.add(url)
            results.append({"type": "yandex_similar", "url": url, "title": ""})

    return results


def _extract_tags(html: str) -> List[str]:
    """CbirTags bölümünden tag text'lerini çıkar."""
    return re.findall(r'class="[^"]*CbirTags-Tag[^"]*"[^>]*>([^<]{1,80})<', html)


def parse_yandex_html(html: str) -> List[Dict]:
    """
    Yandex Images sonuç sayfası HTML'ini parse et.

    Döndürdüğü liste: site sonuçları önce, benzer görseller arkasından.
    Her item: {"type": str, "url": str, "title": str}
    """
    if not html or not html.strip():
        return []

    sites = _extract_sites(html)
    similar = _extract_similar(html)
    tags = _extract_tags(html)

    results = sites + similar
    # tag'leri meta olarak en sona ekle (URL yok ama UI'da ek bilgi sağlar)
    for tag in tags[:10]:
        results.append({"type": "yandex_tag", "url": "", "title": tag.strip()})

    return results

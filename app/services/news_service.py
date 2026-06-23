import asyncio
import httpx
import re
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup
from typing import List, Dict


def _parse_rss_date(val: str) -> str:
    """RSS pubDate'i ISO'ya çevir."""
    if not val:
        return None
    # Örnek: Mon, 24 May 2026 12:00:00 GMT
    try:
        dt = datetime.strptime(val.strip(), "%a, %d %b %Y %H:%M:%S %Z")
        return dt.isoformat()
    except ValueError:
        # Alternatif
        for fmt in ("%d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(val.strip(), fmt).isoformat()
            except ValueError:
                continue
    return val


async def _fetch_google_news(query: str, limit: int) -> List[Dict]:
    url = (
        f"https://news.google.com/rss/search"
        f"?q={quote(query)}"
        f"&hl=tr&gl=TR&ceid=TR:tr"
    )
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except Exception:
        return results

    soup = BeautifulSoup(resp.content, "xml")
    items = soup.find_all("item")[:limit]
    for item in items:
        title = item.find("title")
        link = item.find("link")
        pub_date = item.find("pubDate")
        source_tag = item.find("source")

        title_text = title.get_text(strip=True) if title else None
        url_text = link.get_text(strip=True) if link else None
        date_text = _parse_rss_date(pub_date.get_text(strip=True)) if pub_date else None
        source_text = source_tag.get_text(strip=True) if source_tag else "Google News"

        if title_text and url_text:
            results.append({
                "title": title_text,
                "url": url_text,
                "source": source_text,
                "date": date_text,
                "snippet": "",
            })
    return results


async def _fetch_milliyet(query: str, limit: int) -> List[Dict]:
    url = f"https://arama.milliyet.com.tr/aramaresult.aspx?q={quote(query)}"
    results = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception:
        return results

    soup = BeautifulSoup(resp.text, "html.parser")
    # Milliyet arama sonuçlarında yaygın kart yapısı
    cards = soup.select("div.catImg.list.items, div.search-result-item, article.card, div.news-item")
    if not cards:
        # fallback: herhangi bir başlık + link
        cards = soup.find_all("a", href=re.compile(r"/\d{4}/\d{2}/\d{2}/|detay\.aspx|haber"))

    seen = set()
    for card in cards[:limit * 2]:
        if card.name == "a":
            a = card
        else:
            a = card.find("a", href=True)
        if not a:
            continue
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://arama.milliyet.com.tr" + href
        if href in seen:
            continue
        seen.add(href)

        title_tag = a.get("title") or (a.find(string=True) if a.find(string=True) else None)
        title = (title_tag or "").strip()
        if not title:
            h_tag = card.find(["h2", "h3", "h4", "h5"])
            if h_tag:
                title = h_tag.get_text(strip=True)
        if not title:
            continue

        snippet_tag = card.find("p")
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        # Tarih bulmaya çalış
        date = None
        time_tag = card.find("time")
        if time_tag and time_tag.get("datetime"):
            date = time_tag.get("datetime")
        else:
            date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", card.get_text())
            if date_match:
                try:
                    date = datetime.strptime(date_match.group(1), "%d.%m.%Y").isoformat()
                except ValueError:
                    date = date_match.group(1)

        results.append({
            "title": title,
            "url": href,
            "source": "Milliyet",
            "date": date,
            "snippet": snippet,
        })
        if len(results) >= limit:
            break
    return results


async def _fetch_sozcu(query: str, limit: int) -> List[Dict]:
    url = f"https://www.sozcu.com.tr/arama/?s={quote(query)}"
    results = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception:
        return results

    soup = BeautifulSoup(resp.text, "html.parser")
    # Sözcü arama sonuçlarında muhtemelen .news-item, .search-item, article vb.
    cards = soup.select("div.search-item, article.news-item, div.news-box, div.content-list-item")
    if not cards:
        # fallback: herhangi bir link içeren başlık
        cards = soup.find_all("a", href=re.compile(r"\d{4}/\d{2}/\d{2}/|/yazarlar/|/yazarlar-"))

    seen = set()
    for card in cards[:limit * 2]:
        if card.name == "a":
            a = card
        else:
            a = card.find("a", href=True)
        if not a:
            continue
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.sozcu.com.tr" + href
        if href in seen:
            continue
        seen.add(href)

        title = (a.get_text(strip=True) or "").strip()
        if not title:
            title_tag = card.find(["h2", "h3", "h4", "h5", "span", "div"])
            if title_tag:
                title = title_tag.get_text(strip=True)
        if not title:
            continue

        snippet_tag = card.find("p")
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        # Tarih bulmaya çalış
        date = None
        time_tag = card.find("time")
        if time_tag and time_tag.get("datetime"):
            date = time_tag.get("datetime")
        else:
            date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", card.get_text())
            if date_match:
                try:
                    date = datetime.strptime(date_match.group(1), "%d.%m.%Y").isoformat()
                except ValueError:
                    date = date_match.group(1)

        results.append({
            "title": title,
            "url": href,
            "source": "Sözcü",
            "date": date,
            "snippet": snippet,
        })
        if len(results) >= limit:
            break
    return results


def _sort_by_date(results: List[Dict]) -> List[Dict]:
    def _key(item):
        d = item.get("date")
        if not d:
            return datetime.min.isoformat()
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00")).isoformat()
        except Exception:
            return datetime.min.isoformat()
    return sorted(results, key=_key, reverse=True)


async def search_tr_news(query: str, limit: int = 10) -> dict:
    if not query or not query.strip():
        return {"query": query or "", "total": 0, "results": []}

    google_task = _fetch_google_news(query, limit)
    milliyet_task = _fetch_milliyet(query, limit)
    sozcu_task = _fetch_sozcu(query, limit)

    google_res, milliyet_res, sozcu_res = await asyncio.gather(
        google_task, milliyet_task, sozcu_task, return_exceptions=True
    )

    all_results: List[Dict] = []
    for res in (google_res, milliyet_res, sozcu_res):
        if isinstance(res, Exception):
            continue
        if isinstance(res, list):
            all_results.extend(res)

    # Tekrar eden URL'leri kaldır (ilk gelen kalır)
    seen = set()
    unique_results = []
    for r in all_results:
        url = r.get("url", "")
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique_results.append(r)

    sorted_results = _sort_by_date(unique_results)[:limit]

    return {
        "query": query.strip(),
        "total": len(sorted_results),
        "results": sorted_results,
    }


# Alias for backwards compatibility
search_turkish_news = search_tr_news

"""MERSİS firma sorgulama servisi.

mersis.gtb.gov.tr → mersis.ticaret.gov.tr'ye redirect ediyor.
Site JavaScript (SPA) ile render ediliyor — statik HTTP scraping mümkün değil.
Servis şu an not döndürür; Playwright tabanlı scraping gelecekte eklenebilir.
"""
import httpx
from bs4 import BeautifulSoup

_BASE = "https://mersis.ticaret.gov.tr"
_TIMEOUT = 15.0
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# Bilinen API endpoint denemeleri
_API_CANDIDATES = [
    "/api/v1/mersis/companies",
    "/api/companies",
    "/rest/sirket/sorgula",
    "/api/sirket",
]


async def query_mersis(q: str, page_size: int = 10) -> dict:
    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        follow_redirects=True,
        verify=False,
        headers=_HEADERS,
    ) as client:
        # JSON API endpoint'lerini dene
        for path in _API_CANDIDATES:
            try:
                r = await client.get(
                    f"{_BASE}{path}",
                    params={"companyName": q, "unvan": q, "pageSize": page_size},
                )
                if r.status_code == 200 and "application/json" in r.headers.get("content-type", ""):
                    data = r.json()
                    items = data if isinstance(data, list) else (
                        data.get("content") or data.get("data") or data.get("items") or []
                    )
                    if items:
                        results = []
                        for item in items[:page_size]:
                            results.append({
                                "mersis_no":        item.get("mersisNo") or item.get("mersis_no"),
                                "company_name":     item.get("unvan") or item.get("companyName") or item.get("company_name"),
                                "tax_number":       item.get("vergiNo") or item.get("taxNumber") or item.get("tax_number"),
                                "status":           item.get("durum") or item.get("status"),
                                "address":          item.get("adres") or item.get("address"),
                                "registration_date":item.get("tescilTarihi") or item.get("registrationDate"),
                                "source": "mersis_api",
                            })
                        return {"query": q, "total": len(results), "results": results, "source": "mersis_api"}
            except Exception:
                continue

        # MERSİS SPA olduğu için statik scraping çalışmıyor
        return {
            "query": q,
            "total": 0,
            "results": [],
            "note": (
                "MERSİS (mersis.ticaret.gov.tr) JavaScript tabanlı bir SPA — "
                "statik HTTP sorgusu desteklenmiyor. "
                "Manuel arama için: https://mersis.ticaret.gov.tr"
            ),
            "source": "mersis",
        }

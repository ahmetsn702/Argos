import httpx
import asyncio
from app.core.config import settings

async def leakcheck_lookup(query: str, query_type: str = "auto", timeout: float = 10.0) -> dict:
    key = getattr(settings, "LEAKCHECK_KEY", None)
    if not key:
        return {"ok": False, "error": "LEAKCHECK_KEY eksik"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(
                "https://leakcheck.io/api/v2/query/" + query,
                headers={"X-API-Key": key},
                params={"type": query_type}
            )
            data = r.json()
            if not data.get("success"):
                return {"ok": False, "error": data.get("error", "Bilinmeyen hata")}
            sources = data.get("sources", [])
            return {
                "ok": True,
                "found": data.get("found", 0),
                "query": query,
                "sources": [
                    {
                        "name": s.get("name"),
                        "date": s.get("date"),
                        "entries": s.get("entries"),
                        "fields": s.get("fields", []),
                    }
                    for s in sources
                ],
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def _search_breachdirectory(query: str, timeout: float = 10.0) -> dict:
    key = getattr(settings, "RAPIDAPI_KEY", None)
    if not key:
        return {"ok": False, "error": "RAPIDAPI_KEY eksik"}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
            r = await cli.get(
                "https://breachdirectory.p.rapidapi.com/",
                headers={
                    "X-RapidAPI-Key": key,
                    "X-RapidAPI-Host": "breachdirectory.p.rapidapi.com",
                },
                params={"func": "auto", "term": query}
            )
            if r.status_code != 200:
                return {"ok": False, "error": f"HTTP Error {r.status_code}"}
            data = r.json()
            if not data.get("found", 0):
                return {"ok": True, "found": 0, "query": query, "sources": []}
            results = data.get("result", [])
            sources = []
            seen_sources = set()
            for res in results:
                raw_sources = res.get("sources", "")
                source_list = [s.strip() for s in raw_sources.split(",")] if isinstance(raw_sources, str) else raw_sources
                for s in source_list:
                    if s not in seen_sources:
                        seen_sources.add(s)
                        sources.append({
                            "name": s,
                            "date": None,
                            "entries": 1,
                            "fields": ["password", "sha1"] if res.get("password") or res.get("sha1") else [],
                        })
            if not sources and results:
                sources.append({
                    "name": "Bilinmeyen Kaynak",
                    "date": None,
                    "entries": len(results),
                    "fields": []
                })
            return {
                "ok": True,
                "found": len(results),
                "query": query,
                "sources": sources
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def darkweb_osint(query: str, query_type: str = "auto", timeout: float = 10.0) -> dict:
    leakcheck_task = leakcheck_lookup(query, query_type, timeout)
    breachdir_task = _search_breachdirectory(query, timeout)

    leakcheck, breachdirectory = await asyncio.gather(
        leakcheck_task,
        breachdir_task,
        return_exceptions=True
    )

    lc_res = leakcheck if not isinstance(leakcheck, Exception) else {"ok": False, "error": str(leakcheck)}
    bd_res = breachdirectory if not isinstance(breachdirectory, Exception) else {"ok": False, "error": str(breachdirectory)}

    total_breaches = 0
    sources = []

    if lc_res.get("ok"):
        total_breaches += lc_res.get("found", 0)
        sources.extend(s["name"] for s in lc_res.get("sources", []) if s.get("name"))
    
    if bd_res.get("ok"):
        total_breaches += bd_res.get("found", 0)
        sources.extend(s["name"] for s in bd_res.get("sources", []) if s.get("name"))

    return {
        "query": query,
        "query_type": query_type,
        "leakcheck": lc_res,
        "breachdirectory": bd_res,
        "summary": {
            "total_breaches": total_breaches,
            "sources": sorted(list(set(sources))),
        }
    }


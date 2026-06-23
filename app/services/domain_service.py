import httpx
import asyncio
import socket
from app.core.config import settings

from datetime import datetime, timezone


async def _nictr_lookup(domain: str, timeout: float = 10.0) -> dict:
    from app.services.nictr_service import query_nictr
    try:
        return await query_nictr(domain)
    except Exception as exc:
        return {"error": str(exc), "domain": domain, "source": "nic.tr"}

async def whois_lookup(domain: str, timeout: float = 10.0) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(f"https://api.whois.vu/?q={domain}")
            data = r.json()
            
            def _to_iso(val):
                if val is None:
                    return None
                try:
                    ts = float(val)
                    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                except (ValueError, TypeError):
                    return str(val)

            return {
                "ok": True,
                "registrar": data.get("registrar"),
                "created": _to_iso(data.get("created")),
                "updated": _to_iso(data.get("updated")),
                "expires": _to_iso(data.get("expires")),
                "statuses": data.get("statuses"),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def dns_lookup(domain: str, timeout: float = 10.0) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            results = {}
            for rtype in ["A", "MX", "TXT", "NS"]:
                r = await cli.get(
                    "https://dns.google/resolve",
                    params={"name": domain, "type": rtype}
                )
                data = r.json()
                results[rtype] = [a.get("data") for a in data.get("Answer", [])]
            return {"ok": True, "records": results}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def ip_geo_lookup(ip: str, timeout: float = 10.0) -> dict:
    key = getattr(settings, "ABSTRACT_IP_KEY", None) or ""
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            if key:
                r = await cli.get(
                    "https://ipgeolocation.abstractapi.com/v1/",
                    params={"api_key": key, "ip_address": ip}
                )
            else:
                r = await cli.get(f"http://ip-api.com/json/{ip}")
            data = r.json()
            if key:
                return {
                    "ok": True,
                    "ip": data.get("ip_address"),
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "country": data.get("country"),
                    "isp": data.get("connection", {}).get("isp_name"),
                    "lat": data.get("latitude"),
                    "lng": data.get("longitude"),
                    "vpn": data.get("security", {}).get("is_vpn"),
                    "tor": data.get("security", {}).get("is_tor"),
                    "threat": data.get("security", {}).get("is_threat"),
                }
            else:
                return {
                    "ok": True,
                    "ip": data.get("query"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "country": data.get("country"),
                    "isp": data.get("isp"),
                    "lat": data.get("lat"),
                    "lng": data.get("lon"),
                }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def _empty_result(error: str) -> dict:
    return {"ok": False, "error": error}

async def domain_osint(target: str, timeout: float = 10.0) -> dict:
    target = target.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
    try:
        ip = socket.gethostbyname(target)
    except Exception:
        ip = None

    whois, dns, geo, nictr = await asyncio.gather(
        whois_lookup(target, timeout),
        dns_lookup(target, timeout),
        ip_geo_lookup(ip, timeout) if ip else _empty_result("IP çözümlenemedi"),
        _nictr_lookup(target, timeout),
        return_exceptions=True
    )

    return {
        "target": target,
        "ip": ip,
        "whois": whois if not isinstance(whois, Exception) else {"ok": False, "error": str(whois)},
        "dns": dns if not isinstance(dns, Exception) else {"ok": False, "error": str(dns)},
        "geo": geo if not isinstance(geo, Exception) else {"ok": False, "error": str(geo)},
        "shodan": {"ok": False, "error": "Shodan ücretsiz planda desteklenmiyor"},
        "nictr": nictr if not isinstance(nictr, Exception) else {"error": str(nictr), "domain": target, "source": "nic.tr"},
    }

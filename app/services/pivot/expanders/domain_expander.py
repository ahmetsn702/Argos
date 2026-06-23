# app/services/pivot/expanders/domain_expander.py
"""Expanders for FindingType.DOMAIN."""

from typing import List

from app.models.confidence import ConfidenceFinding
from app.services.confidence.adapters import domain_to_findings
from app.services.pivot.stubs import dns_lookup, shodan_host_lookup


async def expand_via_whois(value: str) -> List[ConfidenceFinding]:
    """Domain → WHOIS lookup."""
    try:
        from app.services.domain_service import domain_osint
        result = await domain_osint(value, timeout=10.0)
        if not isinstance(result, dict):
            return []
        payload = {
            "domain": value,
            "registrant_email": result.get("registrant_email", ""),
            "registrant_name": result.get("registrant_name", ""),
            "registrar": result.get("registrar"),
            "created_date": result.get("created_date"),
            "ips": result.get("ips", []) or [],
        }
        return domain_to_findings(payload)
    except Exception:
        return []


async def expand_via_dns(value: str) -> List[ConfidenceFinding]:
    return await dns_lookup(value)


async def expand_via_shodan(value: str) -> List[ConfidenceFinding]:
    return await shodan_host_lookup(value)

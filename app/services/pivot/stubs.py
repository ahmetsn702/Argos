# app/services/pivot/stubs.py
"""Placeholder async stubs for OSINT modules not yet implemented.

All return an empty ConfidenceFinding list. These are referenced by the
strategy_map so the registry is complete; real implementations can be
swapped in later without touching the orchestrator.
"""

from typing import List

from app.models.confidence import ConfidenceFinding


async def carrier_lookup(value: str) -> List[ConfidenceFinding]:
    """Phone carrier lookup. TODO: integrate dedicated carrier API."""
    return []


async def reverse_phone_lookup(value: str) -> List[ConfidenceFinding]:
    """Reverse phone → name/social lookup. TODO."""
    return []


async def dns_lookup(value: str) -> List[ConfidenceFinding]:
    """Domain → DNS records (A, MX, NS, TXT). TODO."""
    return []


async def asn_lookup(value: str) -> List[ConfidenceFinding]:
    """IP → ASN/owner. TODO."""
    return []


async def ip_geo_lookup(value: str) -> List[ConfidenceFinding]:
    """IP → geo location. TODO."""
    return []


async def reverse_dns_lookup(value: str) -> List[ConfidenceFinding]:
    """IP → reverse DNS PTR. TODO."""
    return []


async def person_aggregator(value: str) -> List[ConfidenceFinding]:
    """Name → cross-source person aggregator. TODO."""
    return []


async def cse_search(value: str) -> List[ConfidenceFinding]:
    """Generic value → Google CSE search. TODO."""
    return []


async def shodan_host_lookup(value: str) -> List[ConfidenceFinding]:
    """Domain/IP → Shodan host info. TODO (key already in env)."""
    return []

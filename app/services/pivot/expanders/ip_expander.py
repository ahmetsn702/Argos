# app/services/pivot/expanders/ip_expander.py
"""Expanders for FindingType.IP. All currently stubs."""

from typing import List

from app.models.confidence import ConfidenceFinding
from app.services.pivot.stubs import asn_lookup, ip_geo_lookup, reverse_dns_lookup


async def expand_via_ip_geo(value: str) -> List[ConfidenceFinding]:
    return await ip_geo_lookup(value)


async def expand_via_reverse_dns(value: str) -> List[ConfidenceFinding]:
    return await reverse_dns_lookup(value)


async def expand_via_asn(value: str) -> List[ConfidenceFinding]:
    return await asn_lookup(value)

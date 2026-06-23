# app/services/pivot/expanders/phone_expander.py
"""Expanders for FindingType.PHONE."""

from typing import List

from app.models.confidence import ConfidenceFinding
from app.services.confidence.adapters import phone_to_findings
from app.services.pivot.stubs import carrier_lookup, reverse_phone_lookup


async def expand_via_phone_lookup(value: str) -> List[ConfidenceFinding]:
    """Phone → numverify-style validation."""
    try:
        from app.routers.phone import phone_lookup
        result = await phone_lookup(phone=value)
        if not isinstance(result, dict):
            return []
        payload = {
            "phone": value,
            "valid": bool(result.get("valid")),
            "country_code": result.get("country_code") or result.get("country"),
            "carrier": result.get("carrier"),
            "line_type": result.get("line_type"),
        }
        return phone_to_findings(payload)
    except Exception:
        return []


async def expand_via_carrier_lookup(value: str) -> List[ConfidenceFinding]:
    return await carrier_lookup(value)


async def expand_via_reverse_lookup(value: str) -> List[ConfidenceFinding]:
    return await reverse_phone_lookup(value)

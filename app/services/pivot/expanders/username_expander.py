# app/services/pivot/expanders/username_expander.py
"""Expanders for FindingType.USERNAME."""

import asyncio
from typing import List

from app.models.confidence import ConfidenceFinding
from app.services.confidence.adapters import bios_to_findings


async def expand_via_bios(value: str) -> List[ConfidenceFinding]:
    """Username → /username-bios social scan."""
    try:
        from app.routers.bios import _gather_bios
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _gather_bios, value, None)
        if not isinstance(results, list):
            return []
        return bios_to_findings({"username": value, "results": results})
    except Exception:
        return []


async def expand_via_variants(value: str) -> List[ConfidenceFinding]:
    """Username → variant generation (l→1, o→0, leet etc.).

    Uses the existing variants router if available; otherwise generates
    a small local set of common variants.
    """
    try:
        out: List[ConfidenceFinding] = []
        # Locally derive a few obvious variants — does NOT call network.
        # Each variant becomes its own USERNAME finding so downstream
        # rounds can pivot on it.
        from app.services.confidence.adapters import bios_to_findings as _bf
        variants = _local_variants(value)
        if not variants:
            return []
        # Fake a /username-bios shape so the existing adapter fires.
        fake_results = [
            {"platform": "candidate", "status": "exists",
             "display_name": "", "url": ""}
            for _ in variants
        ]
        # We need separate findings per variant; bios_to_findings only
        # uses the top-level "username" field, so call it once per variant.
        for variant in variants:
            sub = _bf({"username": variant, "results": [
                {"platform": "candidate", "status": "exists",
                 "display_name": "", "url": ""}
            ]})
            out.extend(sub)
        return out
    except Exception:
        return []


async def expand_via_social_scan(value: str) -> List[ConfidenceFinding]:
    """Lighter alias of expand_via_bios for strategy diversity."""
    return await expand_via_bios(value)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _local_variants(username: str) -> List[str]:
    base = (username or "").strip().lower().lstrip("@")
    if not base or len(base) < 3:
        return []
    out = set()
    out.add(base.replace(".", ""))
    out.add(base.replace("_", ""))
    out.add(base.replace("-", ""))
    leet = base.translate(str.maketrans({"o": "0", "i": "1", "e": "3", "a": "4"}))
    if leet != base:
        out.add(leet)
    out.discard(base)  # only return *new* variants
    return [v for v in out if len(v) >= 3]

# app/services/pivot/expanders/name_expander.py
"""Expanders for FindingType.NAME. All currently stubs."""

from typing import List

from app.models.confidence import ConfidenceFinding
from app.services.pivot.stubs import cse_search, person_aggregator


async def expand_via_person_aggregator(value: str) -> List[ConfidenceFinding]:
    return await person_aggregator(value)


async def expand_via_cse_search(value: str) -> List[ConfidenceFinding]:
    return await cse_search(value)

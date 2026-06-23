# app/services/pivot/expanders/face_expander.py
"""Expanders for image/face based pivots.

Real implementation requires bytes input and reverse-image search; the
strategy_map currently invokes only the stub form (string-arg signature)
to keep the registry uniform. A future revision will accept richer
inputs via a dedicated request shape.
"""

from typing import List

from app.models.confidence import ConfidenceFinding


async def expand_via_reverse_image(value: str) -> List[ConfidenceFinding]:
    """Placeholder: reverse-image-search needs bytes, not a string value.

    Returning [] keeps the pipeline consistent until a media-aware pivot
    request is introduced.
    """
    return []

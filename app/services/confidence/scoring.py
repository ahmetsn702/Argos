# app/services/confidence/scoring.py
"""Noisy-OR scoring with aging, cross-type bonus, and contradicts penalty."""

import math
import os
from datetime import datetime
from typing import List

from app.models.confidence import ConfidenceFinding
from app.services.confidence.weights import get_weight, load_weights


def _get_aging_rate() -> float:
    try:
        v = float(os.getenv("CONFIDENCE_AGING_RATE", "0.95"))
        return max(0.0, min(1.0, v))
    except Exception:
        return 0.95


def apply_aging(weight: float, observed_at: datetime,
                now: datetime, aging_rate: float) -> float:
    days_old = max(0, (now - observed_at).days)
    if aging_rate == 1.0 or days_old == 0:
        return weight
    return round(weight * (aging_rate ** days_old), 6)


def noisy_or(weights: List[float]) -> float:
    if not weights:
        return 0.0
    clamped = [max(0.0, min(1.0, w)) for w in weights]
    base = 1.0 - math.prod(1.0 - w for w in clamped)
    return round(base, 6)


def compute_score(finding: ConfidenceFinding,
                  now: datetime = None,
                  weights_dict: dict = None) -> float:
    if now is None:
        now = datetime.utcnow()
    if weights_dict is None:
        weights_dict = load_weights()

    aging_rate = _get_aging_rate()

    # Step 1: aged weights
    aged = [
        apply_aging(get_weight(obs.source_id, weights_dict),
                    obs.observed_at, now, aging_rate)
        for obs in finding.sources
    ]

    # Step 2: Noisy-OR base
    base = noisy_or(aged)

    # Step 3: cross-type bonus (max 0.10)
    unique_kinds = {obs.source_kind for obs in finding.sources}
    bonus = min(0.05 * (len(unique_kinds) - 1), 0.10)

    # Step 4: contradicts penalty (max 0.45)
    penalty = min(0.15 * len(finding.contradicted_by), 0.45)

    return round(max(0.0, min(1.0, base + bonus - penalty)), 4)

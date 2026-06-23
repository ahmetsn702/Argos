# app/services/confidence/weights.py
"""Source weight table with ENV override support."""

import os

DEFAULT_SOURCE_WEIGHTS = {
    "darkweb_hibp":      0.90,
    "phone_verified":    0.85,
    "domain_whois":      0.80,
    "social_verified":   0.70,
    "social_unverified": 0.50,
    "web_scraping":      0.40,
    "ai_gemini":         0.35,
}


def load_weights() -> dict:
    weights = dict(DEFAULT_SOURCE_WEIGHTS)
    raw = os.getenv("CONFIDENCE_WEIGHT_OVERRIDES", "")
    if not raw:
        return weights
    for part in raw.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        key = key.strip()
        try:
            f = float(val.strip())
            if 0.0 <= f <= 1.0:
                weights[key] = f
        except (ValueError, TypeError):
            pass
    return weights


def get_weight(source_id: str, weights: dict = None) -> float:
    if weights is None:
        weights = load_weights()
    return weights.get(source_id, 0.50)

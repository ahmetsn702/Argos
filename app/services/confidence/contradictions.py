# app/services/confidence/contradictions.py
"""Type-aware contradiction detection + manual flag aggregation."""

import math
from typing import Dict, List, Tuple

from app.models.confidence import ConfidenceFinding, FindingType


def _haversine_km(lat1: float, lng1: float,
                  lat2: float, lng2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _levenshtein_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    n, m = len(a), len(b)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return 1.0 - prev[m] / max(n, m)


def _parse_location(value: str) -> Tuple[float, float]:
    try:
        # "lat:38.6700,lng:39.2200"
        parts = value.split(",")
        lat = float(parts[0].split(":")[1])
        lng = float(parts[1].split(":")[1])
        return (lat, lng)
    except Exception:
        return None


def _parse_phone_country(value: str) -> str:
    # E.164: "+905551234567" → "90", "+15551234567" → "1"
    if not value.startswith("+"):
        return None
    digits = value[1:]
    # Try common 1-3 digit prefixes (1=US, 7=RU, 20-999=rest)
    # Heuristic: 1-digit (1,7), 2-digit (20-99), 3-digit (100-999)
    # We just extract the numeric prefix up to first recognisable boundary.
    # Simple approach: return first 1 or 2 digits as country discriminator.
    # For contradiction detection we only need to tell "same country or not".
    # Use ITU-T E.164 first digit groups:
    #   1 digit  : 1 (NANP), 7 (Russia/Kaz)
    #   2 digits : 20,27,30-39,40-49,51-59,60-69,81,82,84,86,90-99
    #   3 digits : everything else
    if digits[0] in ("1", "7"):
        return digits[0]
    if len(digits) >= 2 and digits[:2] in {
        "20", "27", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39",
        "40", "41", "42", "43", "44", "45", "46", "47", "48", "49",
        "51", "52", "53", "54", "55", "56", "57", "58", "59",
        "60", "61", "62", "63", "64", "65", "66",
        "81", "82", "84", "86",
        "90", "91", "92", "93", "94", "95", "96", "97", "98",
    }:
        return digits[:2]
    if len(digits) >= 3:
        return digits[:3]
    return digits[:2] if len(digits) >= 2 else digits[:1]


def _location_contradicts(
    findings: Dict[str, ConfidenceFinding]
) -> List[Tuple[str, str, str]]:
    locs = [(fid, _parse_location(f.value))
            for fid, f in findings.items()
            if f.type == FindingType.LOCATION]
    locs = [(fid, coords) for fid, coords in locs if coords is not None]
    result = []
    seen = set()
    for i in range(len(locs)):
        for j in range(i + 1, len(locs)):
            id1, (lat1, lng1) = locs[i]
            id2, (lat2, lng2) = locs[j]
            km = _haversine_km(lat1, lng1, lat2, lng2)
            if km > 500:
                pair = tuple(sorted([id1, id2]))
                if pair not in seen:
                    seen.add(pair)
                    result.append((pair[0], pair[1],
                                   f"locations {km:.0f}km apart"))
    return result


def _phone_country_contradicts(
    findings: Dict[str, ConfidenceFinding]
) -> List[Tuple[str, str, str]]:
    phones = [(fid, _parse_phone_country(f.value))
              for fid, f in findings.items()
              if f.type == FindingType.PHONE]
    phones = [(fid, cc) for fid, cc in phones if cc is not None]
    result = []
    seen = set()
    for i in range(len(phones)):
        for j in range(i + 1, len(phones)):
            id1, cc1 = phones[i]
            id2, cc2 = phones[j]
            if cc1 != cc2:
                pair = tuple(sorted([id1, id2]))
                if pair not in seen:
                    seen.add(pair)
                    result.append((pair[0], pair[1],
                                   f"different country codes: {cc1} vs {cc2}"))
    return result


def _name_contradicts(
    findings: Dict[str, ConfidenceFinding]
) -> List[Tuple[str, str, str]]:
    names = [(fid, f.value)
             for fid, f in findings.items()
             if f.type == FindingType.NAME]
    result = []
    seen = set()
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            id1, n1 = names[i]
            id2, n2 = names[j]
            sim = _levenshtein_similarity(n1, n2)
            if sim < 0.5:
                pair = tuple(sorted([id1, id2]))
                if pair not in seen:
                    seen.add(pair)
                    result.append((pair[0], pair[1],
                                   f"name similarity {sim:.2f} < 0.5"))
    return result


def _manual_flag_contradicts(
    findings: Dict[str, ConfidenceFinding]
) -> List[Tuple[str, str, str]]:
    result = []
    seen = set()
    for fid, f in findings.items():
        for obs in f.sources:
            for target_id in obs.contradicts:
                pair = tuple(sorted([fid, target_id]))
                if pair not in seen:
                    seen.add(pair)
                    result.append((pair[0], pair[1], "manual flag"))
    return result


def detect_contradictions(
    findings: Dict[str, ConfidenceFinding]
) -> List[Tuple[str, str, str]]:
    all_results = (
        _location_contradicts(findings)
        + _phone_country_contradicts(findings)
        + _name_contradicts(findings)
        + _manual_flag_contradicts(findings)
    )
    seen = set()
    deduped = []
    for id1, id2, reason in all_results:
        pair = tuple(sorted([id1, id2]))
        if pair not in seen:
            seen.add(pair)
            deduped.append((id1, id2, reason))
    return deduped

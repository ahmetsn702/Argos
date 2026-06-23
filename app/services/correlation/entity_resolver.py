# app/services/correlation/entity_resolver.py
# -*- coding: utf-8 -*-
"""Identity resolution: decide if two profiles belong to the same person.

Combines three weighted signals:
  - Bio similarity (uses app.utils.common.bio_similarity)
  - Display-name similarity (Turkish-character-aware token Jaccard)
  - Username morphology similarity (digit/separator-tolerant Levenshtein)

Optionally a face-match score may be supplied; weights redistribute when absent.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.utils.common import bio_similarity, verdict_from_score

from .models import IdentityMatch, ProfileInput

# --- Tunables ----------------------------------------------------------------
# Weights when face score is available; sum must equal 1.0.
_WEIGHTS_WITH_FACE = {"bio": 0.40, "name": 0.25, "username": 0.25, "face": 0.10}

# Weights when face is unavailable; the face share is redistributed.
_WEIGHTS_NO_FACE = {"bio": 0.45, "name": 0.275, "username": 0.275}

# Same-name detection threshold (used by verdict_from_score for tighter bands).
_SAME_NAME_THRESHOLD = 0.95

_TR_FOLD = str.maketrans("ıİşŞğĞçÇöÖüÜ", "iissggccoouu")


# --- Username similarity ------------------------------------------------------
def _levenshtein_ratio(a: str, b: str) -> float:
    """Simple Levenshtein similarity ratio in [0, 1]. No external dep."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    n, m = len(a), len(b)
    if n < m:
        a, b = b, a
        n, m = m, n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return 1.0 - (prev[m] / max(n, m))


def _username_similarity(a: str, b: str) -> float:
    """Username similarity tolerant to digit suffixes and separators.

    >>> _username_similarity("alice", "alice")     -> 1.0
    >>> _username_similarity("alice92", "alice")   -> 0.85 (digit suffix only)
    >>> _username_similarity("alice_smith", "alicesmith") -> 0.9 (separators)
    >>> otherwise: Levenshtein ratio.
    """
    a = (a or "").strip().lower().lstrip("@")
    b = (b or "").strip().lower().lstrip("@")
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    a_no_digits = re.sub(r"\d+$", "", a) or a
    b_no_digits = re.sub(r"\d+$", "", b) or b
    if a_no_digits and b_no_digits and a_no_digits == b_no_digits:
        return 0.85

    a_clean = re.sub(r"[_.\-]", "", a)
    b_clean = re.sub(r"[_.\-]", "", b)
    if a_clean == b_clean and a_clean:
        return 0.9

    return _levenshtein_ratio(a, b)


# --- Display-name similarity --------------------------------------------------
def _name_norm(s: str) -> str:
    """Lowercase + Turkish character folding + whitespace squash."""
    if not s:
        return ""
    s = s.strip().lower().translate(_TR_FOLD)
    return " ".join(s.split())


def _display_name_score(a: Optional[str], b: Optional[str]) -> float:
    """Token-level Jaccard with Turkish folding."""
    na, nb = _name_norm(a or ""), _name_norm(b or "")
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    set_a, set_b = set(na.split()), set(nb.split())
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


# --- Pairwise comparison ------------------------------------------------------
def compare_profiles(
    a: ProfileInput,
    b: ProfileInput,
    face_match_score: Optional[float] = None,
) -> IdentityMatch:
    """Compute combined identity confidence for one profile pair."""
    bio_sim = bio_similarity(a.bio or "", b.bio or "")
    bio_score = float(bio_sim.get("score", 0.0))
    name_score = _display_name_score(a.display_name, b.display_name)
    user_score = _username_similarity(a.username, b.username)

    signals: Dict[str, float] = {
        "bio_score": round(bio_score, 4),
        "name_score": round(name_score, 4),
        "username_score": round(user_score, 4),
    }

    if face_match_score is not None:
        signals["face_score"] = round(float(face_match_score), 4)
        w = _WEIGHTS_WITH_FACE
        confidence = (
            w["bio"] * bio_score
            + w["name"] * name_score
            + w["username"] * user_score
            + w["face"] * float(face_match_score)
        )
    else:
        w = _WEIGHTS_NO_FACE
        confidence = (
            w["bio"] * bio_score
            + w["name"] * name_score
            + w["username"] * user_score
        )

    confidence = round(min(1.0, max(0.0, confidence)), 4)
    same_name = name_score >= _SAME_NAME_THRESHOLD
    verdict = verdict_from_score(confidence, same_name)

    evidence: List[str] = []
    if bio_score >= 0.7:
        evidence.append(f"bio benzerliği yüksek ({bio_score:.2f})")
    elif bio_score >= 0.4:
        evidence.append(f"bio benzerliği orta ({bio_score:.2f})")
    if name_score >= _SAME_NAME_THRESHOLD:
        evidence.append("display name eşit")
    elif name_score >= 0.5:
        evidence.append(f"display name kısmen örtüşüyor ({name_score:.2f})")
    if user_score >= 0.85:
        evidence.append(f"username benzerliği yüksek ({user_score:.2f})")
    if face_match_score is not None and face_match_score >= 0.8:
        evidence.append(f"yüz eşleşmesi ({face_match_score:.2f})")

    a_id = f"profile:{a.platform}:{a.username}"
    b_id = f"profile:{b.platform}:{b.username}"

    return IdentityMatch(
        entity_a=a_id,
        entity_b=b_id,
        confidence=confidence,
        verdict=verdict,
        signals=signals,
        evidence=evidence,
    )


def resolve_identity(
    profiles: List[ProfileInput],
    face_scores: Optional[Dict[Tuple[int, int], float]] = None,
) -> List[IdentityMatch]:
    """Compute pairwise matches for N>=2 profiles. Returns N*(N-1)/2 matches.

    `face_scores` (optional) maps (i, j) index tuples to a face match score.
    """
    matches: List[IdentityMatch] = []
    n = len(profiles)
    for i in range(n):
        for j in range(i + 1, n):
            face = None
            if face_scores:
                face = face_scores.get((i, j))
            matches.append(compare_profiles(profiles[i], profiles[j], face))
    return matches


__all__ = [
    "compare_profiles",
    "resolve_identity",
]

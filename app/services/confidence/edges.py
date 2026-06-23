# app/services/confidence/edges.py
"""SAME_AS and CONTRADICTS edge builders."""

from typing import Dict, List

from app.models.confidence import ConfidenceEdge, ConfidenceFinding, EdgeType, FindingType
from app.services.confidence.contradictions import detect_contradictions

# Pairs of different types that imply SAME_AS when co-present
_SAME_AS_PAIRS = {
    frozenset({FindingType.EMAIL, FindingType.PHONE}),
    frozenset({FindingType.EMAIL, FindingType.USERNAME}),
    frozenset({FindingType.PHONE, FindingType.USERNAME}),
}


def _same_as_edges(findings: Dict[str, ConfidenceFinding]) -> List[ConfidenceEdge]:
    type_map: Dict[FindingType, List[str]] = {}
    for fid, f in findings.items():
        type_map.setdefault(f.type, []).append(fid)

    edges = []
    seen = set()
    types = list(type_map.keys())
    for i in range(len(types)):
        for j in range(i + 1, len(types)):
            pair = frozenset({types[i], types[j]})
            if pair not in _SAME_AS_PAIRS:
                continue
            for id1 in type_map[types[i]]:
                for id2 in type_map[types[j]]:
                    key = tuple(sorted([id1, id2]))
                    if key in seen:
                        continue
                    seen.add(key)
                    f1 = findings[id1]
                    f2 = findings[id2]
                    edges.append(ConfidenceEdge(
                        source_id=key[0],
                        target_id=key[1],
                        edge_type=EdgeType.SAME_AS,
                        weight=min(f1.confidence_score, f2.confidence_score),
                    ))
    return edges


def _contradicts_edges(findings: Dict[str, ConfidenceFinding]) -> List[ConfidenceEdge]:
    edges = []
    for id1, id2, reason in detect_contradictions(findings):
        pair = tuple(sorted([id1, id2]))
        edges.append(ConfidenceEdge(
            source_id=pair[0],
            target_id=pair[1],
            edge_type=EdgeType.CONTRADICTS,
            weight=1.0,
            metadata={"reason": reason},
        ))
    return edges


def build_edges(findings: Dict[str, ConfidenceFinding]) -> List[ConfidenceEdge]:
    edges = []
    edges.extend(_same_as_edges(findings))
    edges.extend(_contradicts_edges(findings))
    # Dedup by (source_id, target_id, edge_type)
    seen = set()
    result = []
    for e in edges:
        key = (e.source_id, e.target_id, e.edge_type)
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result

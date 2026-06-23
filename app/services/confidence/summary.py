# app/services/confidence/summary.py
"""ConfidenceGraph → LLM-ready summary dict."""

from typing import Any, Dict, List

from app.models.confidence import ConfidenceGraph


def confidence_summary(graph: ConfidenceGraph) -> Dict[str, Any]:
    findings = list(graph.findings.values())

    high, medium, low, contradicted, single_source = [], [], [], [], []

    for f in sorted(findings, key=lambda x: x.confidence_score, reverse=True):
        item = {
            "id": f.id,
            "type": f.type.value,
            "value": f.value,
            "score": round(f.confidence_score, 2),
            "sources": len(f.sources),
        }
        if f.confidence_score > 0.8:
            high.append(item)
        elif f.confidence_score >= 0.5:
            medium.append(item)
        else:
            low.append(item)

        if f.contradicted_by:
            contradicted.append({**item, "contradicted_by": f.contradicted_by})

        if len(f.sources) == 1:
            single_source.append(item)

    total = len(findings)
    avg = round(sum(f.confidence_score for f in findings) / total, 2) if total else 0.0

    return {
        "high_confidence": high,
        "medium_confidence": medium,
        "low_confidence": low,
        "contradicted": contradicted,
        "single_source": single_source,
        "stats": {
            "total_findings": total,
            "avg_score": avg,
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "contradicted_count": len(contradicted),
            "single_source_count": len(single_source),
            "edge_count": len(graph.edges),
        },
    }

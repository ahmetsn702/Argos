# app/services/correlation/geo_cluster.py
# -*- coding: utf-8 -*-
"""Geographic clustering: aggregate lat/lng points from OSINT sources and
produce density clusters via simple grid bucketing (no sklearn dependency).

Algorithm:
    Each point is bucketed into a fixed-size lat/lng grid cell. Cells with
    `>= MIN_CLUSTER_SIZE` points are reported as clusters with their centroid
    (mean lat, mean lng), member sources and labels. Default cell size is
    0.5° (~55km at the equator).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .models import GeoCluster, GeoPoint, GeoRequest

MIN_CLUSTER_SIZE = 2


# --- Helpers ------------------------------------------------------------------
def _coerce_float(v: Any) -> Optional[float]:
    """Accept int/float as-is, parse strings, reject the rest."""
    if isinstance(v, bool):  # bool is subclass of int — exclude
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


def _coords(d: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    """Pull (lat, lng) from a dict if both are numeric."""
    if not isinstance(d, dict):
        return None
    lat = _coerce_float(d.get("lat"))
    lng = _coerce_float(d.get("lng"))
    if lat is None or lng is None:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    return lat, lng


def _cell_key(lat: float, lng: float, cell: float) -> Tuple[int, int]:
    return (int(math.floor(lat / cell)), int(math.floor(lng / cell)))


# --- Point extraction ---------------------------------------------------------
def _extract_points(req: GeoRequest) -> List[GeoPoint]:
    """Pull GeoPoints from each supported source. Tolerant to missing fields."""
    points: List[GeoPoint] = []

    # 1. domain → /domain/lookup response → geo.lat/geo.lng
    if req.domain:
        geo = req.domain.get("geo") or {}
        coords = _coords(geo)
        if coords:
            label = ", ".join(filter(None, [geo.get("city"), geo.get("country")]))
            points.append(GeoPoint(
                lat=coords[0], lng=coords[1],
                source="ip_geo", confidence=0.6,
                label=label or "ip_geo",
            ))

    # 2. exif → /geo/analyze-photo response → lat/lng at top level
    if req.exif:
        coords = _coords(req.exif)
        if coords:
            conf = _coerce_float(req.exif.get("confidence")) or 0.95
            label = ", ".join(filter(None, [req.exif.get("region"), req.exif.get("country")]))
            points.append(GeoPoint(
                lat=coords[0], lng=coords[1],
                source="exif", confidence=conf,
                label=label or "exif",
            ))

    # 3. phone → caller-supplied phone.geo.lat/lng (numverify alone has no coords)
    if req.phone:
        geo = req.phone.get("geo") or {}
        coords = _coords(geo)
        if coords:
            location = ((req.phone.get("numverify") or {}).get("location")
                        or geo.get("label")
                        or "phone")
            points.append(GeoPoint(
                lat=coords[0], lng=coords[1],
                source="phone", confidence=0.4,
                label=str(location),
            ))

    # 4. extras
    if req.extra_points:
        for p in req.extra_points:
            coords = _coords(p) if isinstance(p, dict) else None
            if not coords:
                continue
            conf = _coerce_float(p.get("confidence"))
            points.append(GeoPoint(
                lat=coords[0], lng=coords[1],
                source=str(p.get("source") or "user"),
                confidence=conf if conf is not None else 1.0,
                label=str(p.get("label") or ""),
            ))

    return points


# --- Clustering ---------------------------------------------------------------
def _cluster_points(points: List[GeoPoint], cell: float) -> List[Dict[str, Any]]:
    """Grid bucket points; cells with >= MIN_CLUSTER_SIZE become clusters."""
    if not points:
        return []
    buckets: Dict[Tuple[int, int], List[int]] = {}
    for i, p in enumerate(points):
        buckets.setdefault(_cell_key(p.lat, p.lng, cell), []).append(i)

    clusters: List[Dict[str, Any]] = []
    for key, idxs in buckets.items():
        if len(idxs) < MIN_CLUSTER_SIZE:
            continue
        members = [points[i] for i in idxs]
        avg_lat = sum(m.lat for m in members) / len(members)
        avg_lng = sum(m.lng for m in members) / len(members)
        clusters.append({
            "centroid_lat": round(avg_lat, 6),
            "centroid_lng": round(avg_lng, 6),
            "count": len(members),
            "sources": sorted({m.source for m in members}),
            "labels": [m.label for m in members if m.label],
            "point_indices": idxs,
            "cell": list(key),
        })
    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters


def _primary_region(clusters: List[Dict[str, Any]], points: List[GeoPoint]) -> Optional[str]:
    """Top cluster's first non-empty label, or highest-confidence point's label."""
    for c in clusters:
        for label in c.get("labels") or []:
            if label:
                return label
    if points:
        for p in sorted(points, key=lambda x: -x.confidence):
            if p.label:
                return p.label
    return None


# --- Public API ---------------------------------------------------------------
def build_geo_cluster(req: GeoRequest) -> GeoCluster:
    """Aggregate lat/lng signals into a GeoCluster envelope."""
    points = _extract_points(req)
    clusters = _cluster_points(points, req.cell_size_deg)
    primary = _primary_region(clusters, points)
    return GeoCluster(points=points, centroids=clusters, primary_region=primary)


__all__ = ["build_geo_cluster"]

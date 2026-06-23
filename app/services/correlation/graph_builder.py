# app/services/correlation/graph_builder.py
# -*- coding: utf-8 -*-
"""Graph assembly: turn OSINT signals + correlation outputs into a node/edge
graph with degree centrality. Internal representation uses (source, target);
the router-level translator emits vis.js-compatible {from, to} keys.

Node groups (matches EntityType where applicable):
    person | email | phone | profile | breach | domain | ip | geo_cluster

Edge types:
    owns           — person → primary entity (email/phone/profile)
    breached_in    — email → breach
    registered     — email → domain (when email's domain matches the domain entity)
    resolves_to    — domain → ip
    same_as        — profile ↔ profile (from identity_matches verdict ∈
                     {likely_same, unclear})
    geo_proximity  — geo_cluster ↔ contributing entity
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import Graph, GraphEdge, GraphNode, GraphRequest


# --- ID helpers ---------------------------------------------------------------
def _safe(value: str) -> str:
    """Replace ID-breaking characters in a value segment."""
    return (value or "?").replace(":", "_").strip()


def _id(prefix: str, value: str) -> str:
    return f"{prefix}:{_safe(value)}"


# --- Build helpers ------------------------------------------------------------
class _GraphBuilder:
    """Mutable accumulator used while building a Graph."""

    def __init__(self) -> None:
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._edge_keys: set = set()  # dedupe (source,target,edge_type) triples

    def add_node(self, node_id: str, label: str, group: str, **metadata: Any) -> str:
        existing = self._nodes.get(node_id)
        if existing is None:
            self._nodes[node_id] = GraphNode(
                id=node_id, label=label, group=group,
                metadata={k: v for k, v in metadata.items() if v is not None},
            )
        else:
            for k, v in metadata.items():
                if v is not None:
                    existing.metadata[k] = v
        return node_id

    def add_edge(self, source: str, target: str, edge_type: str,
                 label: Optional[str] = None, **metadata: Any) -> None:
        if source == target:
            return
        key = (source, target, edge_type)
        rev_key = (target, source, edge_type)
        if key in self._edge_keys or rev_key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self._edges.append(GraphEdge(
            source=source, target=target,
            edge_type=edge_type, label=label or edge_type,
            metadata={k: v for k, v in metadata.items() if v is not None},
        ))

    def finalize(self) -> Graph:
        # Degree centrality (undirected)
        degree = {nid: 0 for nid in self._nodes}
        for e in self._edges:
            degree[e.source] = degree.get(e.source, 0) + 1
            degree[e.target] = degree.get(e.target, 0) + 1
        max_d = max(degree.values()) if degree else 0
        if max_d > 0:
            centrality = {nid: round(d / max_d, 4) for nid, d in degree.items()}
        else:
            centrality = {nid: 0.0 for nid in degree}

        return Graph(
            nodes=list(self._nodes.values()),
            edges=self._edges,
            metadata={
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
                "centrality": centrality,
                "node_types_present": sorted({n.group for n in self._nodes.values()}),
            },
        )


# --- Extractors ---------------------------------------------------------------
def _extract_email_id(b: _GraphBuilder, mosint: Optional[Dict[str, Any]]) -> Optional[str]:
    if not mosint:
        return None
    email = mosint.get("email")
    if not email:
        return None
    eid = _id("email", email)
    b.add_node(eid, email, "email", verdict=mosint.get("verdict"))
    return eid


def _extract_domain_id(
    b: _GraphBuilder,
    mosint: Optional[Dict[str, Any]],
    domain: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[str]]:
    """Return (domain_id, ip_id). Either may be None."""
    target = None
    ip = None
    if mosint:
        target = mosint.get("domain")
    if domain:
        target = domain.get("target") or target
        ip = domain.get("ip")
    if not target and not ip:
        return None, None
    domain_id = _id("domain", target) if target else None
    ip_id = _id("ip", ip) if ip else None
    if domain_id:
        b.add_node(domain_id, target, "domain")
    if ip_id:
        b.add_node(ip_id, ip, "ip")
    if domain_id and ip_id:
        b.add_edge(domain_id, ip_id, "resolves_to")
    return domain_id, ip_id


def _extract_breaches(
    b: _GraphBuilder,
    mosint: Optional[Dict[str, Any]],
    email_id: Optional[str],
) -> List[str]:
    if not mosint:
        return []
    hibp = (mosint.get("sources") or {}).get("hibp") or {}
    if not hibp.get("ok"):
        return []
    out: List[str] = []
    for entry in (hibp.get("data") or {}).get("breaches", []) or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("Name") or "?"
        bid = _id("breach", name)
        b.add_node(
            bid, name, "breach",
            date=entry.get("BreachDate"),
            data_classes=list(entry.get("DataClasses") or []),
        )
        if email_id:
            b.add_edge(email_id, bid, "breached_in")
        out.append(bid)
    return out


def _extract_profiles(
    b: _GraphBuilder,
    bios: Optional[Dict[str, Any]],
    person_id: Optional[str],
) -> List[str]:
    if not bios:
        return []
    username = bios.get("username")
    if not username:
        return []
    out: List[str] = []
    for r in (bios.get("results") or []):
        if not isinstance(r, dict) or r.get("status") != "exists":
            continue
        platform = (r.get("platform") or "").lower()
        if not platform:
            continue
        pid = f"profile:{_safe(platform)}:{_safe(username)}"
        b.add_node(
            pid, f"{platform}:{username}", "profile",
            display_name=r.get("display_name"),
            url=r.get("url"),
        )
        if person_id:
            b.add_edge(person_id, pid, "owns")
        out.append(pid)
    return out


def _extract_phone_id(
    b: _GraphBuilder,
    phone: Optional[Dict[str, Any]],
    person_id: Optional[str],
) -> Optional[str]:
    if not phone:
        return None
    nv = phone.get("numverify") or {}
    number = nv.get("number") or phone.get("number")
    if not number:
        return None
    pid = _id("phone", number)
    b.add_node(
        pid, number, "phone",
        country=nv.get("country"),
        carrier=nv.get("carrier"),
    )
    if person_id:
        b.add_edge(person_id, pid, "owns")
    return pid


def _link_email_to_domain(
    b: _GraphBuilder,
    email_id: Optional[str],
    domain_id: Optional[str],
) -> None:
    if not (email_id and domain_id):
        return
    addr = email_id.split(":", 1)[1] if ":" in email_id else ""
    target = domain_id.split(":", 1)[1] if ":" in domain_id else ""
    if "@" in addr and addr.split("@", 1)[1].lower() == target.lower():
        b.add_edge(email_id, domain_id, "registered")


def _add_identity_edges(
    b: _GraphBuilder,
    matches: Optional[List[Dict[str, Any]]],
) -> None:
    if not matches:
        return
    for m in matches:
        if not isinstance(m, dict):
            continue
        if m.get("verdict") not in ("likely_same", "unclear"):
            continue
        a, c = m.get("entity_a"), m.get("entity_b")
        if not a or not c:
            continue
        for ref in (a, c):
            if ref not in b._nodes:
                # synthesise a stub node from prefix
                if ":" in ref:
                    prefix, label = ref.split(":", 1)
                    b.add_node(ref, label, prefix)
                else:
                    b.add_node(ref, ref, "unknown")
        b.add_edge(
            a, c, "same_as",
            verdict=m.get("verdict"),
            confidence=m.get("confidence"),
        )


def _add_geo_edges(
    b: _GraphBuilder,
    geo_cluster: Optional[Dict[str, Any]],
    person_id: Optional[str],
    domain_id: Optional[str],
    phone_id: Optional[str],
) -> None:
    if not geo_cluster:
        return
    for i, c in enumerate(geo_cluster.get("centroids") or []):
        if not isinstance(c, dict):
            continue
        cluster_id = f"geo_cluster:{i}"
        b.add_node(
            cluster_id,
            f"cluster@({c.get('centroid_lat')},{c.get('centroid_lng')})",
            "geo_cluster",
            count=c.get("count"),
            centroid_lat=c.get("centroid_lat"),
            centroid_lng=c.get("centroid_lng"),
        )
        for src in (c.get("sources") or []):
            if src == "ip_geo" and domain_id:
                b.add_edge(cluster_id, domain_id, "geo_proximity")
            elif src == "exif" and person_id:
                b.add_edge(cluster_id, person_id, "geo_proximity")
            elif src == "phone" and phone_id:
                b.add_edge(cluster_id, phone_id, "geo_proximity")
            elif person_id:
                b.add_edge(cluster_id, person_id, "geo_proximity")


# --- Public API ---------------------------------------------------------------
def build_graph(req: GraphRequest) -> Graph:
    """Assemble a Graph from raw OSINT + correlation outputs."""
    b = _GraphBuilder()

    person_id = None
    if req.person:
        person_id = _id("person", req.person)
        b.add_node(person_id, req.person, "person")

    email_id = _extract_email_id(b, req.mosint)
    if email_id and person_id:
        b.add_edge(person_id, email_id, "owns")

    domain_id, _ip_id = _extract_domain_id(b, req.mosint, req.domain)
    _link_email_to_domain(b, email_id, domain_id)

    _extract_breaches(b, req.mosint, email_id)
    _extract_profiles(b, req.bios, person_id)

    phone_id = _extract_phone_id(b, req.phone, person_id)

    _add_identity_edges(b, req.identity_matches)
    _add_geo_edges(b, req.geo_cluster, person_id, domain_id, phone_id)

    return b.finalize()


# --- vis.js translation -------------------------------------------------------
def to_vis_shape(g: Graph) -> Dict[str, Any]:
    """Translate internal Graph to vis.js DataSet shape (`from`/`to` keys)."""
    return {
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "group": n.group,
                "metadata": n.metadata,
            }
            for n in g.nodes
        ],
        "edges": [
            {
                "from": e.source,
                "to": e.target,
                "label": e.label,
                "edge_type": e.edge_type,
                "metadata": e.metadata,
            }
            for e in g.edges
        ],
        "metadata": g.metadata,
    }


__all__ = ["build_graph", "to_vis_shape"]

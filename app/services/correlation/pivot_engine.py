# app/services/correlation/pivot_engine.py
# -*- coding: utf-8 -*-
"""Recursive OSINT pivot: expand a seed (email/username/phone) by chaining
through `/mosint/full` and `/username-bios`. Extracts new emails/phones/
profiles/breaches/domains and recurses up to `max_depth`.

Safety:
- BFS depth-limited (hard cap 3 via PivotRequest.Field constraint)
- Per-level entity cap (default 20)
- Wall-clock time budget (hard cap 180s via PivotRequest.Field constraint)
- Loop protection via canonical-id seen set
- Only expands entities reachable from the user-provided seed; no random
  scanning.

Test patch points (module-level so unittest.mock.patch finds them):
    _call_mosint(email)         → returns mosint_full payload dict
    _call_bios(username)        → returns list of bios result dicts
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.utils.common import EMAIL_PATTERN

from .models import (
    Entity,
    EntityType,
    Graph,
    GraphEdge,
    GraphNode,
    PivotRequest,
    PivotResult,
    PivotSeed,
)


# Phone numbers in free text: international or local-with-separator forms.
_PHONE_PATTERN = re.compile(r"\+?\d[\d\s\-]{7,}\d")
_USERNAME_LOCAL_PATTERN = re.compile(r"^[a-z0-9._-]+$")


# --- External call wrappers (patched by tests) --------------------------------
async def _call_mosint(email: str) -> Dict[str, Any]:
    """Thin wrapper around `app.routers.mosint_api.mosint_full`. Tests patch this."""
    from app.routers.mosint_api import mosint_full  # local import; rate-limit-free
    return await mosint_full(email=email, timeout=8.0)


async def _call_bios(username: str) -> List[Dict[str, Any]]:
    """Thin wrapper around `app.routers.bios._gather_bios`. Sync fn, off-loaded."""
    from app.routers.bios import _gather_bios
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _gather_bios, username, None)


# --- Extraction helpers -------------------------------------------------------
def _username_candidates_from_email(email: str) -> List[str]:
    """Derive plausible username variants from an email's local part."""
    local = email.split("@", 1)[0].lower() if "@" in email else email.lower()
    if not local or not _USERNAME_LOCAL_PATTERN.match(local):
        return []
    candidates = {local, local.replace(".", ""), local.replace("_", "").replace("-", "")}
    return [c for c in candidates if len(c) >= 3]


def _normalise_phone(s: str) -> str:
    return re.sub(r"[\s\-]", "", s)


def _extract_text_entities(text: str) -> Tuple[List[str], List[str]]:
    """Return (emails, phones) found in free text."""
    if not text:
        return [], []
    emails = [m.lower() for m in EMAIL_PATTERN.findall(text)]
    phones = [_normalise_phone(m) for m in _PHONE_PATTERN.findall(text)]
    return emails, phones


# --- Per-kind expanders -------------------------------------------------------
async def _expand_email(email: str) -> Dict[str, List[Any]]:
    """Call mosint, return a dict of newly-discoverable items."""
    out = {"emails": [], "usernames": [], "phones": [],
           "profiles": [], "breaches": [], "domains": []}
    try:
        result = await _call_mosint(email)
    except Exception:
        return out
    if not isinstance(result, dict):
        return out

    domain = result.get("domain")
    if domain:
        out["domains"].append(str(domain).lower())

    hibp = (result.get("sources") or {}).get("hibp") or {}
    if hibp.get("ok"):
        for b in (hibp.get("data") or {}).get("breaches", []) or []:
            if isinstance(b, dict) and b.get("Name"):
                out["breaches"].append(b["Name"])

    out["usernames"].extend(_username_candidates_from_email(email))
    return out


async def _expand_username(username: str) -> Dict[str, List[Any]]:
    """Call bios for one username; harvest new entities (profiles + bio text)."""
    out = {"emails": [], "usernames": [], "phones": [],
           "profiles": [], "breaches": [], "domains": []}
    try:
        results = await _call_bios(username)
    except Exception:
        return out
    if not isinstance(results, list):
        return out

    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("status") != "exists":
            continue
        platform = (r.get("platform") or "").lower()
        if platform:
            out["profiles"].append((platform, username))
        emails, phones = _extract_text_entities(r.get("bio") or "")
        out["emails"].extend(emails)
        out["phones"].extend(phones)
    return out


# --- Graph construction (minimal) ---------------------------------------------
def _build_pivot_graph(seed: PivotSeed, discovered: List[Entity]) -> Graph:
    """Anchor node + one edge per discovered entity; no inter-entity edges."""
    seed_label = seed.email or seed.username or seed.phone or "seed"
    seed_id = f"pivot:{seed_label}"

    nodes: List[GraphNode] = [GraphNode(id=seed_id, label=seed_label, group="person")]
    edges: List[GraphEdge] = []
    seen_ids = {seed_id}

    for ent in discovered:
        nid = ent.canonical_id()
        if nid in seen_ids:
            continue
        seen_ids.add(nid)
        nodes.append(GraphNode(
            id=nid,
            label=ent.value,
            group=ent.type.value,
            metadata=dict(ent.metadata),
        ))
        edges.append(GraphEdge(
            source=seed_id, target=nid,
            edge_type="discovered", label="discovered",
        ))

    return Graph(
        nodes=nodes,
        edges=edges,
        metadata={"node_count": len(nodes), "edge_count": len(edges)},
    )


# --- Public API ---------------------------------------------------------------
async def run_pivot(req: PivotRequest) -> PivotResult:
    """BFS expansion of OSINT entities from the seed, bounded by all limits.

    Depth semantics:
        depth 0 = seed entities
        depth 1 = entities discovered by expanding the seed
        depth N = entities reachable in N expansion rounds
        max_depth = max number of expansion rounds performed
    """
    started = time.monotonic()
    deadline = started + req.time_budget_seconds

    discovered: List[Entity] = []
    seen: Set[str] = set()
    truncated = False
    depth_reached = 0  # = number of expansion rounds successfully completed

    def _add_entity(ent: Entity) -> bool:
        cid = ent.canonical_id()
        if cid in seen:
            return False
        seen.add(cid)
        discovered.append(ent)
        return True

    def _mark_username(u: str) -> bool:
        key = f"_username:{u}"
        if key in seen:
            return False
        seen.add(key)
        return True

    # Seed (depth 0)
    expand_queue: List[Tuple[str, str]] = []
    if req.seed.email:
        e = req.seed.email.strip().lower()
        if e and _add_entity(Entity(type=EntityType.EMAIL, value=e)):
            expand_queue.append(("email", e))
    if req.seed.username:
        u = req.seed.username.strip().lstrip("@").lower()
        if u and _mark_username(u):
            expand_queue.append(("username", u))
    if req.seed.phone:
        p = _normalise_phone(req.seed.phone.strip())
        if p and _add_entity(Entity(type=EntityType.PHONE, value=p)):
            expand_queue.append(("phone", p))

    # Each iteration expands the current expand_queue and produces next_queue.
    # After `max_depth` iterations, anything still in next_queue is truncated.
    rounds_done = 0
    while expand_queue and rounds_done < req.max_depth:
        if time.monotonic() > deadline:
            truncated = True
            break

        next_queue: List[Tuple[str, str]] = []
        new_count = 0  # newly-added entities in this round
        cap_hit = False

        for kind, value in expand_queue:
            if cap_hit:
                break
            if time.monotonic() > deadline:
                truncated = True
                break

            if kind == "email":
                harvest = await _expand_email(value)
            elif kind == "username":
                harvest = await _expand_username(value)
            else:  # phone — no expansion in Phase 6
                continue

            # Flatten harvest into a single ordered list so the per-level cap
            # is enforced uniformly across entity kinds.
            flat: List[Tuple[str, Any]] = []
            flat.extend(("email", e) for e in harvest["emails"])
            flat.extend(("username", u) for u in harvest["usernames"])
            flat.extend(("phone", p) for p in harvest["phones"])
            flat.extend(("profile", pp) for pp in harvest["profiles"])
            flat.extend(("breach", b) for b in harvest["breaches"])
            flat.extend(("domain", d) for d in harvest["domains"])

            for ekind, eval_ in flat:
                if new_count >= req.max_entities_per_level:
                    truncated = True
                    cap_hit = True
                    break
                added = False
                if ekind == "email":
                    added = _add_entity(Entity(type=EntityType.EMAIL, value=eval_))
                    if added:
                        next_queue.append(("email", eval_))
                elif ekind == "username":
                    added = _mark_username(eval_)
                    if added:
                        next_queue.append(("username", eval_))
                elif ekind == "phone":
                    added = _add_entity(Entity(type=EntityType.PHONE, value=eval_))
                elif ekind == "profile":
                    plat, uname = eval_
                    added = _add_entity(Entity(
                        type=EntityType.PROFILE, value=uname,
                        metadata={"platform": plat},
                    ))
                elif ekind == "breach":
                    added = _add_entity(Entity(type=EntityType.BREACH, value=eval_))
                elif ekind == "domain":
                    added = _add_entity(Entity(type=EntityType.DOMAIN, value=eval_))
                if added:
                    new_count += 1

        rounds_done += 1
        depth_reached = rounds_done
        expand_queue = next_queue

    # If queue still has unexpanded items, max_depth was the bottleneck.
    if expand_queue and rounds_done >= req.max_depth:
        truncated = True

    graph = _build_pivot_graph(req.seed, discovered) if req.include_graph else None
    took_ms = int((time.monotonic() - started) * 1000)

    return PivotResult(
        seed=req.seed,
        discovered=discovered,
        graph=graph,
        truncated=truncated,
        depth_reached=depth_reached,
        took_ms=took_ms,
    )


__all__ = ["run_pivot", "_call_mosint", "_call_bios"]

# -*- coding: utf-8 -*-
from app.services.ig_photos import get_ig_photos
from app.services.x_photos import get_x_photos
from app.services.fb_photos import get_fb_photos

async def collect_photos(username: str, sources="ig,x,fb", limit: int = 12):
    if isinstance(sources, str):
        srcs = [s.strip().lower() for s in sources.split(",") if s.strip()]
    else:
        srcs = [str(s).lower() for s in sources]

    per_source = max(1, limit)
    meta = {}
    bag = []

    for s in srcs:
        if s == "ig":
            r = await get_ig_photos(username, per_source); meta["ig"] = r.get("meta", {})
            bag += [dict(p, network="ig") for p in r.get("photos", [])]
        elif s in ("x","twitter"):
            r = await get_x_photos(username, per_source); meta["x"] = r.get("meta", {})
            bag += [dict(p, network="x") for p in r.get("photos", [])]
        elif s == "fb":
            r = await get_fb_photos(username, per_source); meta["fb"] = r.get("meta", {})
            bag += [dict(p, network="fb") for p in r.get("photos", [])]

    seen, photos = set(), []
    for p in bag:
        u = p["url"]
        if u in seen: continue
        photos.append(p); seen.add(u)

    photos = photos[:limit]
    return {"username": username, "sources": srcs, "count": len(photos), "photos": photos, "meta": meta}

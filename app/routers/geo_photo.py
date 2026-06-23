"""Geo Photo OSINT router: extract location from photos via EXIF, shadow analysis, and AI vision."""

import base64
from datetime import datetime, timezone
from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, Form, Request, UploadFile

from app.core.limiter import limiter
from pydantic import BaseModel

from app.models.geo import GeoResult  # canonical location

from app.services.geo_service import analyze_visual_signals, fuse_signals, google_vision_detect
from app.services.geo_comparison import compare_with_candidates
from app.utils.solar_math import (
    CV2_AVAILABLE,
    PVLIB_AVAILABLE,
    extract_shadow_info,
    lat_candidates_from_sun,
    sun_position_from_shadow,
)

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

router = APIRouter(prefix="/geo", tags=["Geo"])


def _dms_to_decimal(dms, ref: str) -> float | None:
    """Convert EXIF GPS DMS tuple to decimal degrees."""
    try:
        d, m, s = [float(x) for x in dms]
        decimal = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def _extract_gps_from_exif(image_bytes: bytes) -> dict | None:
    """Extract GPS coordinates from EXIF data."""
    if not PILLOW_AVAILABLE:
        return None
    try:
        img = Image.open(BytesIO(image_bytes))
        exif = img._getexif()
        if not exif:
            return None

        gps_info = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value

        if "GPSLatitude" not in gps_info or "GPSLongitude" not in gps_info:
            return None

        lat = _dms_to_decimal(gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N"))
        lng = _dms_to_decimal(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))

        if lat is None or lng is None:
            return None
        return {"lat": lat, "lng": lng}
    except Exception:
        return None


@router.post("/analyze-photo", response_model=GeoResult)
@limiter.limit("10/minute")
async def analyze_photo(
    request: Request,
    image: UploadFile = File(...),
    timestamp: str | None = Form(None),
):
    """Analyze a photo to determine its geographic location."""
    image_bytes = await image.read()

    # 1. EXIF GPS check
    gps = _extract_gps_from_exif(image_bytes)
    if gps:
        return GeoResult(
            source="exif", lat=gps["lat"], lng=gps["lng"],
            confidence=0.99, radius_km=1,
            reasoning={"method": "GPS coordinates from EXIF metadata"},
        )

    # 2. Solar analysis
    solar_data = None
    if CV2_AVAILABLE:
        try:
            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img_cv = __import__("cv2").imdecode(arr, __import__("cv2").IMREAD_COLOR)
            shadow = extract_shadow_info(img_cv)
            if shadow:
                sun_pos = sun_position_from_shadow(shadow["angle_deg"], shadow["length_ratio"])
                if sun_pos:
                    dt = datetime.now(timezone.utc)
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        except ValueError:
                            pass
                    candidates = lat_candidates_from_sun(sun_pos["elevation"], sun_pos["azimuth"], dt)
                    if candidates:
                        solar_data = {"candidates": candidates, "sun": sun_pos, "shadow": shadow}
        except Exception:
            pass

    # 3. Visual analysis + Google Vision API (parallel-ready)
    image_b64 = base64.b64encode(image_bytes).decode()
    visual_data = await analyze_visual_signals(image_b64)

    # 3b. Google Vision API (landmark + web detection)
    web_hints = await google_vision_detect(image_b64)

    # 3c. Satellite comparison (if visual_data has Turkey region info)
    comparison_result = None
    if visual_data and visual_data.get("turkey_region"):
        try:
            comparison_result = await compare_with_candidates(image_b64, visual_data)
        except Exception:
            pass

    # 4. Fusion
    fused = await fuse_signals(solar_data, visual_data, web_hints=web_hints, comparison_result=comparison_result)

    if fused.get("error"):
        return GeoResult(source="ai_fusion", fallback=True, reasoning=fused)

    # Use source from fusion logic
    source = fused.pop("source", "visual_fusion")

    return GeoResult(
        source=source,
        lat=fused.get("lat"),
        lng=fused.get("lng"),
        confidence=fused.get("confidence", 0.0),
        radius_km=fused.get("radius_km", 2000),
        country=fused.get("country"),
        region=fused.get("region"),
        reasoning=fused.get("reasoning", {}),
        fallback=fused.get("fallback", False),
    )


@router.get("/health")
async def geo_health():
    """Check geo module health and available sub-modules."""
    return {
        "status": "ok",
        "modules": {
            "solar": CV2_AVAILABLE and PVLIB_AVAILABLE,
            "vision": bool(__import__("os").getenv("GOOGLE_API_KEY") or __import__("os").getenv("GOOGLE_CSE_API_KEY")),
            "exif": PILLOW_AVAILABLE,
        },
    }

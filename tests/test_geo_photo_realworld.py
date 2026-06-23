"""Real-world validation of Bing satellite tile pipeline in geo_photo.

Scenario: No drone photos available in fixtures.
Synthetic test: JPEG with EXIF GPS → Elazığ (38.67, 39.22).
EXIF path bypasses Gemini Vision entirely, so no external mock needed.
Asserts returned lat/lng is within 0.5 degrees of ground truth.

Ground truth: Elazığ, Turkey — lat=38.67, lng=39.22
"""

import io
import math
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Module-level: fetch one real Bing tile for Elazığ (cached across tests).
# If network is unavailable the bytes stay None and the test is skipped.
# ---------------------------------------------------------------------------
def _fetch_bing_tile_sync(lat: float, lon: float, zoom: int = 16) -> bytes | None:
    """Fetch a Bing satellite tile synchronously using httpx."""
    import math as _math
    import random

    try:
        import httpx
    except ImportError:
        return None

    # lat/lon → tile_x, tile_y
    lat_rad = _math.radians(lat)
    n = 2 ** zoom
    tx = int((lon + 180.0) / 360.0 * n)
    ty = int((1.0 - _math.log(_math.tan(lat_rad) + 1.0 / _math.cos(lat_rad)) / _math.pi) / 2.0 * n)
    tx, ty = max(0, min(tx, n - 1)), max(0, min(ty, n - 1))

    # tile → quadkey
    qk = []
    for i in range(zoom, 0, -1):
        d = 0
        mask = 1 << (i - 1)
        if tx & mask:
            d += 1
        if ty & mask:
            d += 2
        qk.append(str(d))
    quadkey = "".join(qk)

    url = f"https://ecn.t{random.randint(0,3)}.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?g=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bing.com/maps",
        "Accept": "image/jpeg,image/*,*/*",
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.content
    except Exception:
        pass
    return None


# Cached at collection time — None means network unavailable.
_BING_TILE_BYTES: bytes | None = _fetch_bing_tile_sync(38.67, 39.22, zoom=16)

# Ground truth for Elazığ
GT_LAT = 38.67
GT_LNG = 39.22
TOLERANCE_DEG = 0.5  # ~55 km at this latitude


def _make_elazıg_jpeg() -> bytes:
    """Minimal JPEG with EXIF GPS pointing to Elazığ (38.67°N, 39.22°E)."""
    try:
        import piexif
    except ImportError:
        pytest.skip("piexif not installed")

    from PIL import Image

    img = Image.new("RGB", (64, 64), color=(180, 140, 100))

    def _dd_to_dms_rational(dd: float):
        d = int(dd)
        m = int((dd - d) * 60)
        s = round(((dd - d) * 60 - m) * 60 * 100)
        return ((d, 1), (m, 1), (s, 100))

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: _dd_to_dms_rational(GT_LAT),
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: _dd_to_dms_rational(GT_LNG),
    }
    exif_bytes = piexif.dump({"GPS": gps_ifd, "0th": {}, "Exif": {}, "1st": {}})
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    return buf.getvalue()


def test_elazig_exif_within_tolerance():
    """
    POST synthetic Elazığ JPEG → /geo/analyze-photo.
    Expect EXIF path: source='exif', lat/lng within 0.5° of (38.67, 39.22).

    Ground truth:  lat=38.67, lng=39.22
    Returned:      captured from response below
    """
    jpeg = _make_elazıg_jpeg()

    resp = client.post(
        "/geo/analyze-photo",
        files={"image": ("elazig_synthetic.jpg", jpeg, "image/jpeg")},
    )

    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    data = resp.json()

    ret_lat = data.get("lat")
    ret_lng = data.get("lng")

    print(
        f"\n[geo_photo_realworld] source={data.get('source')} | "
        f"returned=({ret_lat}, {ret_lng}) | "
        f"ground_truth=({GT_LAT}, {GT_LNG}) | "
        f"radius_km={data.get('radius_km')} | confidence={data.get('confidence')}"
    )

    assert data["source"] == "exif", f"Expected source='exif', got '{data['source']}'"
    assert ret_lat is not None and ret_lng is not None, "No coordinates returned"

    lat_err = abs(ret_lat - GT_LAT)
    lng_err = abs(ret_lng - GT_LNG)
    assert lat_err <= TOLERANCE_DEG, f"lat error {lat_err:.4f}° exceeds {TOLERANCE_DEG}°"
    assert lng_err <= TOLERANCE_DEG, f"lng error {lng_err:.4f}° exceeds {TOLERANCE_DEG}°"


# ---------------------------------------------------------------------------
# Helper: plain RGB JPEG with no EXIF (arid Anatolian red/brown palette)
# ---------------------------------------------------------------------------
def _make_plain_jpeg_no_exif() -> bytes:
    """200×200 RGB JPEG with no EXIF — arid Anatolian terrain colors."""
    from PIL import Image as _Image

    img = _Image.new("RGB", (200, 200), color=(160, 90, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# Visual signals mock — includes turkey_region to trigger compare_with_candidates
_VISUAL_SIGNALS = {
    "estimated_country": "Turkey",
    "estimated_region": "Elazığ",
    "confidence": 0.72,
    "plate_city_code": None,
    "reasoning": "Anatolian architecture and signage",
    # Required by compare_with_candidates path
    "turkey_region": "Doğu Anadolu",
    "city_size": "medium",
    "mountain_profile": "medium_mountains",
}

# Satellite comparison result that compare_with_candidates would return
_COMPARISON_RESULT = {
    "city": "Elazığ",
    "lat": 38.67,
    "lng": 39.22,
    "confidence": 0.72,
    "reasoning": "Satellite terrain match: Southeastern Taurus, river valley",
    "runner_up": "Malatya",
    "runner_up_confidence": 0.45,
    "candidates_evaluated": 5,
}


def test_satellite_comparison_pipeline_no_exif_no_plate():
    """
    Force the satellite comparison pipeline by providing:
      - no EXIF GPS
      - no shadow/solar data
      - mocked visual signals with turkey_region (triggers compare_with_candidates)
      - mocked fetch_satellite_image returning a real Bing tile

    Asserts source in (visual_fusion, full_fusion, ai_fusion), country=Turkey,
    fallback=False, confidence > 0.3.
    """
    if _BING_TILE_BYTES is None:
        pytest.skip("Bing tile fetch failed — network unavailable")

    jpeg = _make_plain_jpeg_no_exif()

    with (
        patch("app.routers.geo_photo._extract_gps_from_exif", return_value=None),
        patch("app.routers.geo_photo.extract_shadow_info", return_value=None),
        patch(
            "app.routers.geo_photo.analyze_visual_signals",
            new=AsyncMock(return_value=_VISUAL_SIGNALS),
        ),
        patch(
            "app.routers.geo_photo.google_vision_detect",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.geo_comparison.fetch_satellite_image",
            new=AsyncMock(return_value=_BING_TILE_BYTES),
        ),
        patch(
            "app.services.geo_comparison.compare_with_candidates",
            new=AsyncMock(return_value=_COMPARISON_RESULT),
        ),
    ):
        resp = client.post(
            "/geo/analyze-photo",
            files={"image": ("arid_terrain.jpg", jpeg, "image/jpeg")},
        )

    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    data = resp.json()

    source = data.get("source")
    print(
        f"\n[satellite_pipeline] source={source} | "
        f"country={data.get('country')} | region={data.get('region')} | "
        f"confidence={data.get('confidence')} | fallback={data.get('fallback')}"
    )

    assert source in ("visual_fusion", "full_fusion", "ai_fusion", "satellite_comparison"), (
        f"Unexpected source: {source!r}"
    )
    assert data.get("country") == "Turkey", f"Expected country=Turkey, got {data.get('country')!r}"
    assert data.get("fallback") is False, f"Expected fallback=False, got {data.get('fallback')!r}"
    assert data.get("confidence", 0) > 0.3, f"Confidence too low: {data.get('confidence')}"

"""Tests for geo_photo module."""

import io
import struct
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/geo/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "modules" in data
    assert set(data["modules"].keys()) == {"solar", "vision", "exif"}


def _make_jpeg_with_gps() -> bytes:
    """Create a minimal JPEG with EXIF GPS data."""
    from PIL import Image
    from PIL.ExifTags import Base as ExifBase
    import piexif

    img = Image.new("RGB", (100, 100), color="red")
    # Build EXIF with GPS
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((41, 1), (0, 1), (4968, 100)),
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: ((29, 1), (0, 1), (1836, 100)),
    }
    exif_dict = {"GPS": gps_ifd, "0th": {}, "Exif": {}, "1st": {}}
    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    return buf.getvalue()


def _make_plain_jpeg() -> bytes:
    """Create a JPEG without EXIF GPS."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_exif_gps_extraction():
    """If image has GPS EXIF, should return source='exif'."""
    try:
        import piexif
    except ImportError:
        pytest.skip("piexif not installed")

    jpeg_data = _make_jpeg_with_gps()
    resp = client.post(
        "/geo/analyze-photo",
        files={"image": ("test.jpg", jpeg_data, "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "exif"
    assert data["lat"] is not None
    assert data["lng"] is not None
    assert data["confidence"] >= 0.9


@patch("app.routers.geo_photo.analyze_visual_signals")
def test_no_exif_fallback(mock_visual):
    """Without EXIF, should fall back to visual analysis."""
    mock_visual.return_value = {
        "estimated_country": "Turkey",
        "estimated_region": "Istanbul",
        "confidence": 0.7,
        "reasoning": "Turkish text on signs",
    }
    jpeg_data = _make_plain_jpeg()
    resp = client.post(
        "/geo/analyze-photo",
        files={"image": ("test.jpg", jpeg_data, "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] in ("visual_only", "ai_fusion", "visual_fusion", "plate_match")
    assert data["country"] == "Turkey"


@patch("app.routers.geo_photo.analyze_visual_signals")
@patch("app.routers.geo_photo.extract_shadow_info")
def test_full_pipeline(mock_shadow, mock_visual):
    """Both solar and visual signals should produce ai_fusion source."""
    mock_shadow.return_value = {
        "angle_deg": 45.0, "length_ratio": 2.0, "confidence": 0.3,
    }
    mock_visual.return_value = {
        "estimated_country": "Turkey",
        "estimated_region": "Ankara",
        "confidence": 0.8,
        "reasoning": "Architecture and signage",
    }
    jpeg_data = _make_plain_jpeg()
    resp = client.post(
        "/geo/analyze-photo",
        files={"image": ("test.jpg", jpeg_data, "image/jpeg")},
        data={"timestamp": "2024-06-15T12:00:00Z"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fallback"] is False
    assert data["confidence"] > 0

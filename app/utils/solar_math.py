"""Shadow analysis and solar position estimation using OpenCV + pvlib."""

import numpy as np
from datetime import datetime

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pvlib
    from pvlib import solarposition
    import pandas as pd
    PVLIB_AVAILABLE = True
except ImportError:
    PVLIB_AVAILABLE = False


def extract_shadow_info(image: np.ndarray) -> dict | None:
    """Detect shadow from image using HSV dark region analysis."""
    if not CV2_AVAILABLE or image is None:
        return None
    try:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # Shadow mask: low value, low saturation
        lower = np.array([0, 0, 0])
        upper = np.array([180, 255, 80])
        mask = cv2.inRange(hsv, lower, upper)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 500:
            return None

        rect = cv2.minAreaRect(largest)
        angle = rect[2]
        w, h = rect[1]
        length_ratio = max(w, h) / (min(w, h) + 1e-6)

        # Normalize angle to 0-180
        angle_deg = abs(angle) if angle < 0 else angle
        confidence = min(cv2.contourArea(largest) / (image.shape[0] * image.shape[1]), 1.0)

        return {
            "angle_deg": round(angle_deg, 2),
            "length_ratio": round(length_ratio, 2),
            "confidence": round(confidence, 4),
        }
    except Exception:
        return None


def sun_position_from_shadow(angle_deg: float, length_ratio: float) -> dict | None:
    """Estimate sun elevation and azimuth from shadow geometry."""
    try:
        import math
        # Shadow length ratio approximates tan(90 - elevation)
        elevation = math.degrees(math.atan(1.0 / length_ratio))
        # Shadow angle is opposite to sun azimuth
        azimuth = (angle_deg + 180) % 360
        return {
            "elevation": round(elevation, 2),
            "azimuth": round(azimuth, 2),
        }
    except Exception:
        return None


def lat_candidates_from_sun(elevation: float, azimuth: float, dt_utc: datetime) -> list[dict] | None:
    """Find latitude candidates matching observed sun position using pvlib."""
    if not PVLIB_AVAILABLE:
        return None
    try:
        candidates = []
        times = pd.DatetimeIndex([dt_utc], tz="UTC")

        for lat in range(-60, 70, 5):
            sp = solarposition.get_solarposition(times, lat, 0)
            calc_elev = sp["apparent_elevation"].iloc[0]
            calc_azi = sp["azimuth"].iloc[0]

            elev_diff = abs(calc_elev - elevation)
            azi_diff = min(abs(calc_azi - azimuth), 360 - abs(calc_azi - azimuth))

            if elev_diff < 15 and azi_diff < 30:
                conf = 1.0 - (elev_diff / 15 * 0.5 + azi_diff / 30 * 0.5)
                candidates.append({"lat": lat, "confidence": round(conf, 3)})

        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        return candidates if candidates else None
    except Exception:
        return None

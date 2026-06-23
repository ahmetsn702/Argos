"""Geo comparison service: candidate city filtering and satellite image comparison."""

import asyncio
import base64
import json
import logging

from app.core.config import settings
from app.utils.plate_lookup import TR_PLATE_TO_CITY

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

GOOGLE_API_KEY = settings.GOOGLE_API_KEY or settings.GOOGLE_CSE_API_KEY or ""

# Approximate populations for 81 Turkish provinces (2023 estimates)
CITY_POPULATIONS: dict[str, int] = {
    "Adana": 2270000, "Adıyaman": 635000, "Afyonkarahisar": 750000,
    "Ağrı": 510000, "Amasya": 340000, "Ankara": 5750000,
    "Antalya": 2690000, "Artvin": 170000, "Aydın": 1130000,
    "Balıkesir": 1240000, "Bilecik": 230000, "Bingöl": 282000,
    "Bitlis": 350000, "Bolu": 320000, "Burdur": 270000,
    "Bursa": 3195000, "Çanakkale": 560000, "Çankırı": 195000,
    "Çorum": 530000, "Denizli": 1050000, "Diyarbakır": 1810000,
    "Edirne": 415000, "Elazığ": 590000, "Erzincan": 235000,
    "Erzurum": 760000, "Eskişehir": 905000, "Gaziantep": 2130000,
    "Giresun": 450000, "Gümüşhane": 150000, "Hakkari": 280000,
    "Hatay": 1660000, "Isparta": 445000, "Mersin": 1890000,
    "İstanbul": 15910000, "İzmir": 4460000, "Kars": 285000,
    "Kastamonu": 380000, "Kayseri": 1430000, "Kırklareli": 365000,
    "Kırşehir": 240000, "Kocaeli": 2080000, "Konya": 2310000,
    "Kütahya": 580000, "Malatya": 810000, "Manisa": 1460000,
    "Kahramanmaraş": 1170000, "Mardin": 870000, "Muğla": 1020000,
    "Muş": 410000, "Nevşehir": 310000, "Niğde": 365000,
    "Ordu": 760000, "Rize": 350000, "Sakarya": 1070000,
    "Samsun": 1370000, "Siirt": 335000, "Sinop": 220000,
    "Sivas": 640000, "Tekirdağ": 1110000, "Tokat": 610000,
    "Trabzon": 810000, "Tunceli": 85000, "Şanlıurfa": 2140000,
    "Uşak": 375000, "Van": 1140000, "Yozgat": 420000,
    "Zonguldak": 590000, "Aksaray": 430000, "Bayburt": 85000,
    "Karaman": 255000, "Kırıkkale": 290000, "Batman": 630000,
    "Şırnak": 540000, "Bartın": 200000, "Ardahan": 95000,
    "Iğdır": 200000, "Yalova": 295000, "Karabük": 250000,
    "Kilis": 145000, "Osmaniye": 545000, "Düzce": 400000,
}

# Mountain profile tags for each province
# Maps province name -> mountain profile category
CITY_MOUNTAIN_PROFILES: dict[str, str] = {
    # Güneydoğu Toroslar (SE Taurus) - steep, close, rugged
    "Elazığ": "se_taurus", "Malatya": "se_taurus", "Tunceli": "se_taurus",
    "Bingöl": "se_taurus", "Muş": "se_taurus", "Adıyaman": "se_taurus",
    "Kahramanmaraş": "se_taurus",
    # Kuzey Anadolu Dağları (N Anatolian) - lower, distant, forested
    "Ankara": "n_anatolian", "Kastamonu": "n_anatolian", "Bolu": "n_anatolian",
    "Çankırı": "n_anatolian", "Amasya": "n_anatolian", "Çorum": "n_anatolian",
    "Sinop": "n_anatolian", "Tokat": "n_anatolian", "Samsun": "n_anatolian",
    # Doğu Anadolu Yüksek Dağları - very high, volcanic, snow-capped
    "Ağrı": "e_anatolian_high", "Kars": "e_anatolian_high", "Erzurum": "e_anatolian_high",
    "Van": "e_anatolian_high", "Ardahan": "e_anatolian_high", "Iğdır": "e_anatolian_high",
    "Hakkari": "e_anatolian_high", "Erzincan": "e_anatolian_high", "Bitlis": "e_anatolian_high",
    # Karadeniz Kıyı Dağları - steep, green, fog
    "Trabzon": "blacksea", "Rize": "blacksea", "Giresun": "blacksea",
    "Artvin": "blacksea", "Ordu": "blacksea", "Gümüşhane": "blacksea",
    "Bayburt": "blacksea",
    # İç Anadolu Platosu - flat steppe
    "Konya": "ic_anadolu_flat", "Aksaray": "ic_anadolu_flat", "Nevşehir": "ic_anadolu_flat",
    "Kırşehir": "ic_anadolu_flat", "Niğde": "ic_anadolu_flat", "Karaman": "ic_anadolu_flat",
    "Yozgat": "ic_anadolu_flat", "Kırıkkale": "ic_anadolu_flat", "Eskişehir": "ic_anadolu_flat",
    "Sivas": "ic_anadolu_flat", "Kayseri": "ic_anadolu_flat",
    # Marmara Bölgesi
    "İstanbul": "marmara", "Bursa": "marmara", "Kocaeli": "marmara",
    "Sakarya": "marmara", "Tekirdağ": "marmara", "Edirne": "marmara",
    "Kırklareli": "marmara", "Çanakkale": "marmara", "Balıkesir": "marmara",
    "Bilecik": "marmara", "Yalova": "marmara", "Düzce": "marmara",
    # Ege Bölgesi
    "İzmir": "aegean", "Aydın": "aegean", "Denizli": "aegean",
    "Manisa": "aegean", "Muğla": "aegean", "Uşak": "aegean",
    "Kütahya": "aegean", "Afyonkarahisar": "aegean",
    # Akdeniz Bölgesi
    "Antalya": "mediterranean", "Mersin": "mediterranean", "Adana": "mediterranean",
    "Hatay": "mediterranean", "Isparta": "mediterranean", "Burdur": "mediterranean",
    "Osmaniye": "mediterranean", "Kilis": "mediterranean", "Gaziantep": "mediterranean",
    # Güneydoğu Anadolu
    "Diyarbakır": "se_anatolian", "Şanlıurfa": "se_anatolian", "Mardin": "se_anatolian",
    "Siirt": "se_anatolian", "Batman": "se_anatolian", "Şırnak": "se_anatolian",
    # Kalanlar
    "Zonguldak": "n_anatolian", "Bartın": "n_anatolian", "Karabük": "n_anatolian",
}

# Region name -> mountain profile categories mapping
REGION_TO_PROFILES: dict[str, list[str]] = {
    "marmara": ["marmara"],
    "ege": ["aegean"],
    "akdeniz": ["mediterranean"],
    "ic_anadolu": ["ic_anadolu_flat"],
    "dogu_anadolu": ["se_taurus", "e_anatolian_high", "blacksea"],
    "guneydogu_anadolu": ["se_anatolian"],
    "karadeniz": ["blacksea"],
}

# Mountain profile visual label -> profile categories mapping
MOUNTAIN_PROFILE_TO_CATEGORIES: dict[str, list[str]] = {
    "none_flat": ["ic_anadolu_flat", "se_anatolian"],
    "low_hills": ["n_anatolian", "marmara", "aegean"],
    "medium_mountains": ["se_taurus", "blacksea", "mediterranean", "e_anatolian_high"],
    "high_mountains": ["e_anatolian_high"],
}

# City size -> population range
CITY_SIZE_RANGES: dict[str, tuple[int, int]] = {
    "metropolis": (5_000_000, 999_999_999),
    "large": (1_000_000, 5_000_000),
    "medium": (200_000, 1_000_000),
    "small": (50_000, 200_000),
}


def _normalize_region(region: str) -> str:
    """Normalize Turkish region name to internal key."""
    mapping = {
        "marmara": "marmara",
        "ege": "ege",
        "akdeniz": "akdeniz",
        "ic anadolu": "ic_anadolu", "iç anadolu": "ic_anadolu", "i̇ç anadolu": "ic_anadolu",
        "dogu anadolu": "dogu_anadolu", "doğu anadolu": "dogu_anadolu",
        "guneydogu anadolu": "guneydogu_anadolu", "güneydoğu anadolu": "guneydogu_anadolu",
        "karadeniz": "karadeniz",
    }
    key = region.strip().lower()
    return mapping.get(key, key)


async def get_candidate_cities(
    turkey_region: str,
    city_size: str,
    mountain_profile: str,
) -> list[dict]:
    """Filter candidate cities by region + city size + mountain profile.

    Returns up to 15 candidates sorted by match confidence, each containing:
    - city, plate_code, lat, lng, population, mountain_profile, confidence
    """
    region_key = _normalize_region(turkey_region)

    # Get valid mountain profiles for the primary region
    primary_profiles = REGION_TO_PROFILES.get(region_key, [])

    # Get valid mountain profiles for neighboring regions
    neighbor_regions = []
    if region_key == "ic_anadolu":
        neighbor_regions = ["dogu_anadolu", "guneydogu_anadolu"]
    elif region_key == "dogu_anadolu":
        neighbor_regions = ["ic_anadolu", "guneydogu_anadolu"]
    elif region_key == "guneydogu_anadolu":
        neighbor_regions = ["ic_anadolu", "dogu_anadolu"]

    neighbor_profiles = []
    for r in neighbor_regions:
        neighbor_profiles.extend(REGION_TO_PROFILES.get(r, []))

    # Get mountain categories matching the visual mountain profile
    mountain_categories = MOUNTAIN_PROFILE_TO_CATEGORIES.get(mountain_profile.lower(), [])

    # Get population range for city size
    pop_range = CITY_SIZE_RANGES.get(city_size.lower(), (0, 999_999_999))
    pop_min, pop_max = pop_range

    candidates = []
    for plate_code, (city_name, lat, lng) in TR_PLATE_TO_CITY.items():
        pop = CITY_POPULATIONS.get(city_name, 0)
        city_mtn = CITY_MOUNTAIN_PROFILES.get(city_name, "unknown")

        # Score calculation
        score = 0.0

        # Region match (0.4 weight)
        if city_mtn in primary_profiles:
            score += 0.4
        elif city_mtn in neighbor_profiles:
            score += 0.3

        # Mountain profile match (0.3 weight)
        if city_mtn in mountain_categories:
            score += 0.3

        # Population range match (0.3 weight)
        if pop_min <= pop <= pop_max:
            score += 0.3
        elif pop_min * 0.5 <= pop <= pop_max * 1.5:
            # Partial match for nearby population ranges
            score += 0.15

        # Skip cities with zero relevance
        if score < 0.3:
            continue

        candidates.append({
            "city": city_name,
            "plate_code": plate_code,
            "lat": lat,
            "lng": lng,
            "population": pop,
            "mountain_profile": city_mtn,
            "confidence": round(score, 2),
        })

    # Sort by confidence descending, then by population descending
    candidates.sort(key=lambda c: (-c["confidence"], -c["population"]))

    return candidates[:15]


import math

def _latlon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    tile_x = int((lon + 180.0) / 360.0 * n)
    tile_y = int(
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0 * n
    )
    tile_x = max(0, min(tile_x, n - 1))
    tile_y = max(0, min(tile_y, n - 1))
    return tile_x, tile_y


def _tile_to_quadkey(tile_x: int, tile_y: int, zoom: int) -> str:
    quadkey = []
    for i in range(zoom, 0, -1):
        digit = 0
        mask = 1 << (i - 1)
        if tile_x & mask:
            digit += 1
        if tile_y & mask:
            digit += 2
        quadkey.append(str(digit))
    return ''.join(quadkey)


async def fetch_satellite_image(lat: float, lon: float, zoom: int = 17) -> bytes | None:
    '''Fetch satellite JPEG tile from Bing Maps Virtual Earth CDN via quadkey.
    No API key needed for direct CDN access. Returns raw JPEG bytes or None.'''
    import httpx
    import random

    tile_x, tile_y = _latlon_to_tile(lat, lon, zoom)
    quadkey = _tile_to_quadkey(tile_x, tile_y, zoom)
    server = random.randint(0, 3)
    url = f'https://ecn.t{server}.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?g=1'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.bing.com/maps',
        'Accept': 'image/jpeg,image/*,*/*',
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200 and len(response.content) > 1000:
                return response.content
            if zoom == 17:
                return await fetch_satellite_image(lat, lon, zoom=16)
            return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'Bing tile fetch failed: {e}')
        return None


def _safe_b64_decode(data) -> bytes:
    '''Decode base64, or pass through if data is already raw JPEG/PNG bytes.
    Bing satellite tiles return raw bytes; Gemini Vision pipeline sends base64.
    This helper handles both without global monkeypatching.'''
    import base64
    if isinstance(data, bytes):
        if data.startswith(b'\xff\xd8') or data.startswith(b'\x89PNG'):
            return data
        try:
            return base64.b64decode(data)
        except Exception:
            return data
    if isinstance(data, str):
        return base64.b64decode(data)
    raise TypeError(f'Unsupported type for b64 decode: {type(data)}')


async def compare_with_candidates(original_b64: str, visual_data: dict) -> dict | None:
    """Compare original photo with satellite images of candidate cities using Gemini Vision.

    Steps:
    1. Get candidate cities based on visual_data's turkey_region, city_size, mountain_profile
    2. Fetch satellite images for each candidate (parallel, max 10)
    3. Send all images to Gemini for comparison
    4. Return best match with coordinates

    Returns dict with city, lat, lng, confidence, reasoning or None on error.
    """
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        return None

    turkey_region = visual_data.get("turkey_region")
    city_size = visual_data.get("city_size")
    mountain_profile = visual_data.get("mountain_profile")

    if not turkey_region or not city_size or turkey_region.lower() == "null":
        return None

    try:
        # 1. Get candidate cities
        candidates = await get_candidate_cities(
            turkey_region=turkey_region,
            city_size=city_size or "medium",
            mountain_profile=mountain_profile or "medium_mountains",
        )

        if not candidates:
            logger.info("No candidate cities found for comparison")
            return None

        logger.info(f"Satellite comparison: {len(candidates)} candidates - {[c['city'] for c in candidates]}")

        # 2. Fetch satellite images in parallel
        async def _fetch_one(cand: dict) -> tuple[dict, str | None]:
            img = await fetch_satellite_image(cand["lat"], cand["lng"])
            return cand, img

        results = await asyncio.gather(*[_fetch_one(c) for c in candidates])

        # Filter out failed fetches
        valid_pairs = [(cand, img) for cand, img in results if img is not None]

        if not valid_pairs:
            logger.warning("No satellite images could be fetched")
            return None

        logger.info(f"Fetched {len(valid_pairs)} satellite images successfully")

        # 3. Build Gemini prompt with all images
        city_list = "\n".join(
            f"  {i+1}. {cand['city']} (pop: {cand['population']:,}, "
            f"mountain: {cand['mountain_profile']}, lat: {cand['lat']}, lng: {cand['lng']})"
            for i, (cand, _) in enumerate(valid_pairs)
        )

        comparison_prompt = f"""You are comparing an original aerial/drone photograph with satellite images of {len(valid_pairs)} Turkish candidate cities.

The first image is the ORIGINAL photo to geolocate.
The following images (numbered 1 to {len(valid_pairs)}) are satellite views of these candidate cities:
{city_list}

Compare the original photo against each satellite image. Focus on:
1. CITY GRID PATTERN: Does the street layout match? Regular grid vs organic winding streets.
2. MOUNTAIN/TERRAIN PROFILE: Does the surrounding terrain match? Mountain distance, height, direction.
3. ROAD NETWORK: Highway patterns, river crossings, valley orientation.
4. URBAN DENSITY: Does the building density and spread match?
5. GEOGRAPHIC FEATURES: Rivers, lakes, terrain contours.

Return ONLY this JSON (no markdown, no extra text):
{{
  "best_match_index": 0,
  "city": "city name",
  "confidence": 0.0,
  "reasoning": "why this city matches best",
  "runner_up": "second best city name",
  "runner_up_confidence": 0.0
}}

The best_match_index is 1-based (1 to {len(valid_pairs)}).
confidence should be between 0.0 and 1.0 — only use >0.7 if the match is very clear."""

        # Build content parts: prompt + original image + satellite images
        content_parts = [comparison_prompt]

        # Original image
        original_data = _safe_b64_decode(original_b64)
        content_parts.append(types.Part.from_bytes(data=original_data, mime_type="image/jpeg"))

        # Satellite images
        for _, sat_b64 in valid_pairs:
            sat_data = _safe_b64_decode(sat_b64)
            content_parts.append(types.Part.from_bytes(data=sat_data, mime_type="image/png"))

        # 4. Call Gemini
        client = genai.Client(api_key=GOOGLE_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=content_parts,
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]

        result = json.loads(text)

        # Map back to candidate data
        match_idx = int(result.get("best_match_index", 1)) - 1
        if 0 <= match_idx < len(valid_pairs):
            matched_cand = valid_pairs[match_idx][0]
            return {
                "city": matched_cand["city"],
                "lat": matched_cand["lat"],
                "lng": matched_cand["lng"],
                "confidence": float(result.get("confidence", 0.0)),
                "reasoning": result.get("reasoning", "Satellite comparison match"),
                "runner_up": result.get("runner_up"),
                "runner_up_confidence": float(result.get("runner_up_confidence", 0.0)),
                "candidates_evaluated": len(valid_pairs),
            }

        return None

    except Exception as e:
        logger.warning(f"Satellite comparison failed: {type(e).__name__}: {e}")
        return None

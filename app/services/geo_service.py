"""Geo analysis service: Gemini Vision (ETHAN-style CoT) + signal fusion."""

import base64
import json
import logging
import re

from app.core.config import settings
from app.utils.plate_lookup import lookup_plate, TR_PLATE_TO_CITY

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

GOOGLE_API_KEY = settings.GOOGLE_API_KEY or settings.GOOGLE_CSE_API_KEY or ""

VISION_PROMPT = """You are an expert OSINT geolocation analyst. Analyze this image systematically using ALL steps below. Every step is MANDATORY.

STEP 1 - OBSERVE (list only what you actually see, no assumptions):
- Text/signage: exact text, alphabet/script type, language, city/district names (especially Turkish signs/tabela yazıları)
- Road infrastructure: lane markings color, road signs, guardrails, poles (especially electric pole types)
- Vehicles: types, license plate patterns (color, format, numbers if visible, vehicle density)
- Architecture: building style, materials, era (especially Turkish regional styles: e.g. Doğu Anadolu taş/Eastern Anatolian stone, Karadeniz ahşap/Black Sea wood, Ege beyaz badana/Aegean white-washed)
- Vegetation: specific plant types, density
- Sky/shadows: sun position estimate, shadow directions and lengths
- Terrain/Geography: mountain/sea/plains profile (dağ/deniz/ova profili)

STEP 2 - CITY SIZE ESTIMATION (MANDATORY):
WARNING: Drone/aerial photos create a zoom bias — cities appear larger from above than they actually are. A 300K-population city filmed by drone can look like a 1M+ metropolis. Do NOT rely on visual spread alone.
Use these STRUCTURAL indicators to resist drone bias:

a) BLOCK-LEVEL DENSITY: Count approximate buildings per visible city block.
   - Metropolis (5M+): 20+ buildings/block, many 10+ story towers, continuous dense fabric
   - Large (1-5M): 10-20 buildings/block, mostly 5-8 story mid-rises, organized grid
   - Medium (200K-1M): 5-12 buildings/block, mostly 3-5 story, gaps between buildings visible
   - Small (50K-200K): 2-6 buildings/block, mostly 1-3 story, yards/gardens between structures

b) URBAN GRID PATTERN: Distinguish planned vs organic growth.
   - Planned large city: Wide boulevards (4+ lanes), regular rectangular blocks, systematic grid, ring roads, grade-separated intersections
   - Organic medium city: Narrow streets (2 lanes dominant), irregular block shapes, winding roads adapted to terrain, few if any ring roads

c) INTERSECTION & SQUARE SCALE: Large cities have complex multi-lane intersections with traffic lights at every corner, roundabouts with 4+ exits, large public squares. Medium cities have simple T-junctions, small roundabouts, modest town squares.

d) INFRASTRUCTURE MARKERS:
   - Metropolis: Metro/tram lines, airport visible, stadium, multiple hospital campuses
   - Large: Organized public transit stops, university campuses, industrial zones at periphery
   - Medium: Bus stops only, single university if any, small organized industrial site (OSB)
   - Small: Minimal public transit, agricultural land immediately adjacent to town center

If the image is aerial/drone, ALWAYS cross-check visual spread against block density and grid pattern before deciding city_size.

STEP 3 - MOUNTAIN PROFILE (MANDATORY):
Analyze the background terrain/mountain profile visible in the image:
- "none_flat": Flat terrain, plains, or coastal area with no elevation visible
- "low_hills": Low rolling hills visible, elevation under ~500m
- "medium_mountains": Medium height mountains visible, 500-2000m range, green or brown slopes
- "high_mountains": High mountains visible, >2000m estimated, possibly snow-capped peaks, dramatic relief

TURKEY-SPECIFIC MOUNTAIN SIGNATURES (use these for region narrowing):
- Güneydoğu Toroslar (SE Taurus): Steep, rugged, high peaks CLOSE to city (within 5-10km). Bare rock, dramatic relief. Cities nestled in valleys. → Elazığ, Malatya, Tunceli, Kahramanmaraş, Adana (north side)
- Kuzey Anadolu Dağları (N Anatolian): Lower, rounded, DISTANT from city center (20-40km). Forested slopes. → Ankara (north), Çankırı, Kastamonu, Amasya
- Doğu Anadolu Yüksek Dağları: Very high (3000m+), often snow-capped even in spring. Volcanic cones. → Ağrı, Kars, Erzurum, Van
- Karadeniz Kıyı Dağları: Steep but green, forested, descending sharply to coast. Fog/cloud contact. → Trabzon, Rize, Artvin
- İç Anadolu Platosu: No significant mountains, flat steppe, occasional low hills. → Konya, Aksaray, Kırşehir
Evaluate mountain DISTANCE from city edge, STEEPNESS, VEGETATION on slopes, and SNOW presence.

STEP 4 - BUILDING ERA ANALYSIS (MANDATORY):
Determine the dominant construction period:
- "new": Post-2000 modern buildings dominant, glass facades, contemporary architecture, new residential towers
- "mixed": Mix of old and new construction, different era buildings side by side
- "old": Pre-2000 buildings dominant, historical structures, traditional construction materials

STEP 5 - TURKEY REGION ANALYSIS (if Turkey is suspected):
If the image appears to be from Turkey, identify the geographic region based on visual clues:
- "Marmara": Industrial zones, Bosphorus/Sea of Marmara, dense urbanization, ferry terminals
- "Ege": White-washed houses, olive groves, Aegean coast, tourism infrastructure
- "Akdeniz": Palm trees, Mediterranean coast, citrus groves, resort towns, greenhouse farming
- "İç Anadolu": Steppe landscape, flat plateau, continental climate vegetation, Cappadocia-like terrain
- "Doğu Anadolu": High mountains often snow-capped, stone architecture, harsh terrain, sparse vegetation, cold climate indicators
- "Güneydoğu Anadolu": Basalt stone buildings, arid terrain, Mesopotamian plains, flat with distant hills
- "Karadeniz": Lush green vegetation, wooden houses, steep terrain, tea/hazelnut plantations, fog/rain indicators
Use architecture style, vegetation, terrain, and climate indicators to determine the region.

STEP 6 - ANALYZE SIGNALS (high confidence first):
- License plates: format match to country/region database
- Language/script: narrow to country/region
- Road markings: yellow vs white centerlines (Americas=yellow, Europe=white)
- Left/right hand traffic
- Architecture style → region
- Vegetation → climate zone → latitude band

STEP 7 - HYPOTHESES (list top 3 candidate regions/cities with evidence for/against each)

STEP 8 - SYNTHESIZE
Based on ALL your analysis above, produce the final answer.
For city_candidates: provide exactly 3 Turkish city guesses (if Turkey is suspected) or 3 city guesses for the identified country. Each MUST include estimated population and geographic coordinates.

Return ONLY this JSON (no markdown, no extra text):
{
  "language": "detected language",
  "script": "alphabet type",
  "architecture": "style description",
  "vegetation": "plant/climate type",
  "plates": "plate pattern and country match if identified",
  "plate_city_code": "numeric code if Turkish plate detected (e.g. 23 for Elazig)",
  "signs": "road/shop sign content",
  "driving_side": "left or right",
  "road_markings": "yellow or white centerlines",
  "estimated_country": "most likely country",
  "estimated_region": "city/region if determinable",
  "city_size": "metropolis|large|medium|small",
  "mountain_profile": "none_flat|low_hills|medium_mountains|high_mountains",
  "building_era": "new|mixed|old",
  "turkey_region": "Marmara|Ege|Akdeniz|İç Anadolu|Doğu Anadolu|Güneydoğu Anadolu|Karadeniz or null if not Turkey",
  "top3_candidates": [
    {"location": "...", "confidence": 0.0, "evidence_for": "...", "evidence_against": "..."},
    {"location": "...", "confidence": 0.0, "evidence_for": "...", "evidence_against": "..."},
    {"location": "...", "confidence": 0.0, "evidence_for": "...", "evidence_against": "..."}
  ],
  "city_candidates": [
    {"city": "...", "population": "estimated population string", "lat": 0.0, "lng": 0.0, "confidence": 0.0, "evidence": "..."},
    {"city": "...", "population": "estimated population string", "lat": 0.0, "lng": 0.0, "confidence": 0.0, "evidence": "..."},
    {"city": "...", "population": "estimated population string", "lat": 0.0, "lng": 0.0, "confidence": 0.0, "evidence": "..."}
  ],
  "confidence": 0.0,
  "reasoning": "brief synthesis incorporating city_size, mountain_profile, building_era, and turkey_region analysis"
}"""

# Hardcoded country centroids for fallback geocoding
COUNTRY_COORDS = {
    "adana": (37.0, 35.32),
    "adiyaman": (37.76, 38.28),
    "adıyaman": (37.76, 38.28),
    "afyonkarahisar": (38.76, 30.54),
    "agri": (39.72, 43.05),
    "aksaray": (38.37, 34.04),
    "amasya": (40.65, 35.83),
    "ankara": (39.92, 32.85),
    "antalya": (36.9, 30.7),
    "ardahan": (41.11, 42.7),
    "artvin": (41.18, 41.82),
    "australia": (-25.0, 134.0),
    "aydin": (37.85, 27.85),
    "aydın": (37.85, 27.85),
    "ağrı": (39.72, 43.05),
    "balikesir": (39.65, 27.89),
    "balıkesir": (39.65, 27.89),
    "bartin": (41.64, 32.34),
    "bartın": (41.64, 32.34),
    "batman": (37.88, 41.13),
    "bayburt": (40.26, 40.23),
    "bilecik": (40.15, 29.98),
    "bingol": (38.88, 40.5),
    "bingöl": (38.88, 40.5),
    "bitlis": (38.4, 42.12),
    "bolu": (40.74, 31.61),
    "brazil": (-14.0, -51.0),
    "burdur": (37.72, 30.29),
    "bursa": (40.18, 29.06),
    "canada": (56.0, -106.0),
    "canakkale": (40.15, 26.41),
    "cankiri": (40.6, 33.62),
    "china": (35.0, 105.0),
    "corum": (40.55, 34.96),
    "denizli": (37.78, 29.09),
    "diyarbakir": (37.91, 40.23),
    "diyarbakır": (37.91, 40.23),
    "duzce": (40.84, 31.16),
    "düzce": (40.84, 31.16),
    "edirne": (41.68, 26.56),
    "egypt": (26.0, 30.0),
    "elazig": (38.67, 39.22),
    "elazığ": (38.67, 39.22),
    "erzincan": (39.75, 39.49),
    "erzurum": (39.9, 41.27),
    "eskisehir": (39.78, 30.52),
    "eskişehir": (39.78, 30.52),
    "france": (46.0, 2.0),
    "gaziantep": (37.07, 37.38),
    "germany": (51.0, 10.0),
    "giresun": (40.91, 38.39),
    "greece": (39.0, 22.0),
    "gumushane": (40.46, 39.48),
    "gümüşhane": (40.46, 39.48),
    "hakkari": (37.57, 43.74),
    "hatay": (36.4, 36.35),
    "igdir": (39.92, 44.04),
    "india": (20.0, 77.0),
    "iran": (32.0, 53.0),
    "iraq": (33.0, 44.0),
    "isparta": (37.76, 30.55),
    "istanbul": (41.01, 28.95),
    "italy": (42.0, 12.0),
    "izmir": (38.42, 27.14),
    "iğdır": (39.92, 44.04),
    "i̇stanbul": (41.01, 28.95),
    "i̇zmir": (38.42, 27.14),
    "japan": (36.0, 138.0),
    "kahramanmaras": (37.58, 36.94),
    "kahramanmaraş": (37.58, 36.94),
    "karabuk": (41.2, 32.62),
    "karabük": (41.2, 32.62),
    "karaman": (37.18, 33.22),
    "kars": (40.6, 43.1),
    "kastamonu": (41.38, 33.78),
    "kayseri": (38.73, 35.49),
    "kilis": (36.72, 37.12),
    "kirikkale": (39.85, 33.51),
    "kirklareli": (41.74, 27.22),
    "kirsehir": (39.15, 34.17),
    "kocaeli": (40.85, 29.88),
    "konya": (37.87, 32.49),
    "kutahya": (39.42, 29.98),
    "kütahya": (39.42, 29.98),
    "kırklareli": (41.74, 27.22),
    "kırıkkale": (39.85, 33.51),
    "kırşehir": (39.15, 34.17),
    "malatya": (38.35, 38.31),
    "manisa": (38.62, 27.43),
    "mardin": (37.32, 40.74),
    "mersin": (36.81, 34.64),
    "mexico": (23.0, -102.0),
    "mugla": (37.22, 28.37),
    "mus": (38.74, 41.5),
    "muğla": (37.22, 28.37),
    "muş": (38.74, 41.5),
    "netherlands": (52.0, 5.0),
    "nevsehir": (38.62, 34.72),
    "nevşehir": (38.62, 34.72),
    "nigde": (37.97, 34.68),
    "niğde": (37.97, 34.68),
    "ordu": (40.98, 37.88),
    "osmaniye": (37.07, 36.25),
    "poland": (52.0, 20.0),
    "rize": (41.02, 40.52),
    "russia": (61.0, 105.0),
    "sakarya": (40.77, 30.4),
    "samsun": (41.29, 36.33),
    "sanliurfa": (37.16, 38.8),
    "siirt": (37.93, 41.95),
    "sinop": (42.02, 35.15),
    "sirnak": (37.52, 42.46),
    "sivas": (39.75, 37.02),
    "south korea": (36.0, 128.0),
    "spain": (40.0, -4.0),
    "sweden": (62.0, 15.0),
    "tekirdag": (40.98, 27.51),
    "tekirdağ": (40.98, 27.51),
    "tokat": (40.31, 36.55),
    "trabzon": (41.0, 39.72),
    "tunceli": (39.11, 39.55),
    "turkey": (39.0, 35.0),
    "türkiye": (39.0, 35.0),
    "uk": (54.0, -2.0),
    "united kingdom": (54.0, -2.0),
    "united states": (39.0, -98.0),
    "usa": (39.0, -98.0),
    "usak": (38.68, 29.41),
    "uşak": (38.68, 29.41),
    "van": (38.49, 43.38),
    "yalova": (40.65, 29.27),
    "yozgat": (39.82, 34.81),
    "zonguldak": (41.45, 31.79),
    "çanakkale": (40.15, 26.41),
    "çankırı": (40.6, 33.62),
    "çorum": (40.55, 34.96),
    "şanlıurfa": (37.16, 38.8),
    "şırnak": (37.52, 42.46),
}


async def analyze_visual_signals(image_base64: str) -> dict | None:
    """Analyze image with Gemini Vision API using ETHAN-style CoT prompt."""
    import os
    logger.info(f"GOOGLE_API_KEY present: {bool(GOOGLE_API_KEY)}")
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        return None
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        image_data = base64.b64decode(image_base64)

        # Load country clues from JSON file
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            clues_path = os.path.join(current_dir, "..", "data", "country_clues.json")
            if os.path.exists(clues_path):
                with open(clues_path, "r", encoding="utf-8") as f:
                    clues_data = json.load(f)
                clues_str = json.dumps(clues_data, indent=2, ensure_ascii=False)
                prompt = (
                    f"{VISION_PROMPT}\n\n"
                    f"VISUAL CLUES REFERENCE DATABASE (use these verified facts for reasoning about driving side and road markings of these countries, do not assume or guess otherwise):\n"
                    f"{clues_str}"
                )
            else:
                prompt = VISION_PROMPT
        except Exception as ex:
            logger.warning(f"Failed to load country clues context: {ex}")
            prompt = VISION_PROMPT

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
            ],
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Gemini Vision failed: {type(e).__name__}: {e}")
        return None


async def google_vision_detect(image_base64: str) -> dict | None:
    """Send image to Google Cloud Vision API for landmark + web detection.
    Returns web_hints dict with landmarks and location hints from similar web images.
    Silently returns None on any error.
    """
    api_key = settings.GOOGLE_API_KEY
    if not api_key:
        return None
    try:
        import httpx
    except ImportError:
        logger.debug("httpx not available, skipping Google Vision API")
        return None

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    payload = {
        "requests": [{
            "image": {"content": image_base64},
            "features": [
                {"type": "LANDMARK_DETECTION", "maxResults": 5},
                {"type": "WEB_DETECTION", "maxResults": 10},
            ]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        response = data.get("responses", [{}])[0]
        result = {"landmarks": [], "web_entities": [], "web_locations": [], "similar_urls": []}

        # Landmark detection
        for lm in response.get("landmarkAnnotations", []):
            entry = {"name": lm.get("description", ""), "confidence": lm.get("score", 0.0)}
            locs = lm.get("locations", [])
            if locs:
                ll = locs[0].get("latLng", {})
                entry["lat"] = ll.get("latitude")
                entry["lng"] = ll.get("longitude")
            result["landmarks"].append(entry)

        # Web detection
        web = response.get("webDetection", {})
        for entity in web.get("webEntities", []):
            result["web_entities"].append({
                "description": entity.get("description", ""),
                "score": entity.get("score", 0.0),
            })

        # Pages with matching images - extract location hints from URLs
        for page in web.get("pagesWithMatchingImages", []):
            page_url = page.get("url", "")
            result["similar_urls"].append(page_url)
            # Try to parse city/location from URL path segments
            location_hints = _parse_location_from_url(page_url)
            if location_hints:
                result["web_locations"].extend(location_hints)

        # Visually similar images
        for img in web.get("visuallySimilarImages", []):
            img_url = img.get("url", "")
            location_hints = _parse_location_from_url(img_url)
            if location_hints:
                result["web_locations"].extend(location_hints)

        # Deduplicate web_locations
        seen = set()
        unique_locations = []
        for loc in result["web_locations"]:
            key = loc.lower()
            if key not in seen:
                seen.add(key)
                unique_locations.append(loc)
        result["web_locations"] = unique_locations

        logger.info(f"Google Vision API: {len(result['landmarks'])} landmarks, {len(result['web_locations'])} web locations")
        return result if (result["landmarks"] or result["web_locations"] or result["web_entities"]) else None

    except Exception as e:
        logger.warning(f"Google Vision API failed: {type(e).__name__}: {e}")
        return None


def _parse_location_from_url(url: str) -> list[str]:
    """Extract potential city/location names from URL path and query parameters."""
    locations = []
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        # Combine path and query for analysis
        text = unquote(parsed.path + "?" + parsed.query).lower()
        # Remove common non-location path segments
        noise = {"www", "http", "https", "com", "org", "net", "html", "php", "jpg",
                 "jpeg", "png", "gif", "images", "photos", "gallery", "uploads",
                 "media", "content", "wp", "static", "assets", "files", "page",
                 "index", "view", "detail", "article", "post", "blog"}

        # Check for Turkish city names in URL
        for city_key in COUNTRY_COORDS:
            # Only match Turkish cities (skip country names)
            if len(city_key) > 2 and city_key not in {
                "australia", "brazil", "canada", "china", "egypt", "france",
                "germany", "greece", "india", "iran", "iraq", "italy", "japan",
                "mexico", "netherlands", "poland", "russia", "south korea",
                "spain", "sweden", "turkey", "türkiye", "uk", "united kingdom",
                "united states", "usa"
            }:
                # Word boundary match in URL text
                pattern = r'[\-_/\?&=]' + re.escape(city_key) + r'[\-_/\?&=\.]'
                if re.search(pattern, "-" + text + "-"):
                    locations.append(city_key)
    except Exception:
        pass
    return locations


async def fuse_signals(solar_data: dict | None, visual_data: dict | None, web_hints: dict | None = None, comparison_result: dict | None = None) -> dict:
    """Fuse solar and visual signals into a location estimate."""
    if not solar_data and not visual_data:
        return {"error": "no signals", "fallback": True}

    result = {
        "lat": None, "lng": None, "confidence": 0.0,
        "radius_km": 2000, "country": None, "region": None,
        "top3_candidates": None,
        "reasoning": {"solar": None, "visual": None, "fusion": None},
        "source": "visual_fusion",
        "fallback": False,
    }

    solar_lat = None
    solar_conf = 0.0
    if solar_data and solar_data.get("candidates"):
        best = solar_data["candidates"][0]
        solar_lat = best["lat"]
        solar_conf = best.get("confidence", 0.0)
        result["lat"] = solar_lat
        result["radius_km"] = 800
        result["reasoning"]["solar"] = f"Sun position suggests lat ~{solar_lat}"
        result["source"] = "solar_fusion"

    # Plate lookup (highest priority for Turkish plates)
    plate_match = None
    if visual_data and visual_data.get("plate_city_code"):
        plate_match = lookup_plate(visual_data["plate_city_code"])

    if plate_match:
        city, plat, plng = plate_match
        result["lat"] = plat
        result["lng"] = plng
        result["radius_km"] = 15
        result["country"] = "Turkey"
        result["region"] = city
        result["source"] = "plate_match"
        result["reasoning"]["visual"] = f"Turkish plate code {visual_data['plate_city_code']} → {city}"

    # Signs OCR matching (Turkish city/district check)
    signs_match = None
    if visual_data and visual_data.get("signs"):
        signs_text = str(visual_data["signs"]).lower()
        
        def normalize_tr(s: str) -> str:
            mapping = {
                'ş': 's', 'ı': 'i', 'ğ': 'g', 'ç': 'c', 'ö': 'o', 'ü': 'u'
            }
            res = s.lower()
            for k, v in mapping.items():
                res = res.replace(k, v)
            import unicodedata
            return "".join(c for c in unicodedata.normalize('NFKD', res) if not unicodedata.combining(c))
        
        norm_signs = normalize_tr(signs_text)
        
        custom_districts = {
            "abdullah pasa": ("Elazığ", 38.67, 39.22),
            "abdullahpaşa": ("Elazığ", 38.67, 39.22),
        }
        
        for dist_name, coord in custom_districts.items():
            if dist_name in norm_signs:
                signs_match = coord
                break
                
        if not signs_match:
            for code, (city_name, lat, lng) in TR_PLATE_TO_CITY.items():
                norm_city = normalize_tr(city_name)
                if norm_city in norm_signs:
                    signs_match = (city_name, lat, lng)
                    break

    if signs_match and not plate_match:
        city_name, slat, slng = signs_match
        result["lat"] = slat
        result["lng"] = slng
        result["radius_km"] = 50
        result["country"] = "Turkey"
        result["region"] = city_name
        result["source"] = "signs_match"
        result["reasoning"]["visual"] = f"Turkish signs OCR match → {city_name}"

    # Doğu Anadolu region filter (city_size + mountain_profile based)
    region_filter_match = None
    if visual_data and not plate_match and not signs_match:
        city_size = str(visual_data.get("city_size", "")).lower()
        turkey_region = str(visual_data.get("turkey_region", "")).lower()
        # Normalize Turkish characters for comparison
        turkey_region_norm = turkey_region.replace("ğ", "g").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c")

        if city_size in ("small", "medium") and "dogu anadolu" in turkey_region_norm:
            east_anatolia_cities = [
                "elazig", "elazığ", "malatya", "tunceli", "bingol", "bingöl",
                "mus", "muş", "bitlis", "van", "hakkari", "agri", "ağrı",
                "kars", "ardahan", "igdir", "iğdır", "erzurum", "erzincan", "bayburt",
            ]
            # Filter COUNTRY_COORDS to only East Anatolia provinces
            east_coords = {k: v for k, v in COUNTRY_COORDS.items() if k in east_anatolia_cities}

            # Match city_candidates against East Anatolia provinces
            candidates = visual_data.get("city_candidates", [])
            best_match = None
            best_conf = -1.0
            for cand in candidates:
                cand_city = str(cand.get("city", "")).lower()
                # Normalize candidate city name
                cand_norm = cand_city.replace("ğ", "g").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c")
                for ec_key, ec_coords in east_coords.items():
                    ec_norm = ec_key.replace("ğ", "g").replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ç", "c")
                    if ec_norm in cand_norm or cand_norm in ec_norm:
                        cand_conf = float(cand.get("confidence", 0.0))
                        if cand_conf > best_conf:
                            best_conf = cand_conf
                            best_match = (ec_key.title(), ec_coords[0], ec_coords[1])
                            break

            if best_match:
                region_filter_match = best_match
                city_name_rf, rf_lat, rf_lng = region_filter_match
                result["lat"] = rf_lat
                result["lng"] = rf_lng
                result["radius_km"] = 100
                result["country"] = "Turkey"
                result["region"] = city_name_rf
                result["source"] = "region_filter_match"
                result["reasoning"]["visual"] = (
                    f"Doğu Anadolu bölge filtresi: city_size={city_size}, "
                    f"mountain_profile={visual_data.get('mountain_profile', 'N/A')} → {city_name_rf}"
                )
                logger.info(f"Region filter match: {city_name_rf} (Doğu Anadolu, {city_size})")

    # Web hints from Google Vision API (landmark + web detection)
    web_hint_match = None
    if web_hints and not plate_match and not signs_match and not region_filter_match:
        # Priority 1: Landmark detection with coordinates
        for lm in web_hints.get("landmarks", []):
            if lm.get("lat") is not None and lm.get("lng") is not None:
                web_hint_match = (lm["name"], lm["lat"], lm["lng"])
                result["lat"] = lm["lat"]
                result["lng"] = lm["lng"]
                result["radius_km"] = 50
                result["country"] = "Turkey"
                result["region"] = lm["name"]
                result["source"] = "web_landmark_match"
                result["reasoning"]["visual"] = f"Google Vision landmark: {lm['name']} (conf={lm.get('confidence', 0):.2f})"
                logger.info(f"Web landmark match: {lm['name']}")
                break

        # Priority 2: Location hints from similar web images
        if not web_hint_match and web_hints.get("web_locations"):
            for loc in web_hints["web_locations"]:
                loc_lower = loc.lower()
                coords = COUNTRY_COORDS.get(loc_lower)
                if coords:
                    web_hint_match = (loc.title(), coords[0], coords[1])
                    result["lat"] = coords[0]
                    result["lng"] = coords[1]
                    result["radius_km"] = 200
                    result["country"] = "Turkey"
                    result["region"] = loc.title()
                    result["source"] = "web_image_match"
                    result["reasoning"]["visual"] = f"Google Vision web detection: similar images reference {loc.title()}"
                    logger.info(f"Web image location match: {loc.title()}")
                    break

    # Satellite comparison result
    sat_comparison_match = None
    if comparison_result and not plate_match and not signs_match:
        comp_conf = float(comparison_result.get("confidence", 0.0))
        if comp_conf > 0.5:
            sat_comparison_match = (
                comparison_result["city"],
                comparison_result["lat"],
                comparison_result["lng"],
            )
            result["lat"] = comparison_result["lat"]
            result["lng"] = comparison_result["lng"]
            result["radius_km"] = 50
            result["country"] = "Turkey"
            result["region"] = comparison_result["city"]
            result["source"] = "satellite_comparison"
            result["reasoning"]["visual"] = (
                f"Satellite comparison: {comparison_result['city']} "
                f"(conf={comp_conf:.2f}, evaluated {comparison_result.get('candidates_evaluated', '?')} cities, "
                f"runner-up: {comparison_result.get('runner_up', 'N/A')})"
            )
            logger.info(
                f"Satellite comparison match: {comparison_result['city']} "
                f"(conf={comp_conf:.2f})"
            )

    # Visual signals (country resolution)
    visual_lat, visual_lng = None, None
    visual_conf = 0.0
    if visual_data and visual_data.get("estimated_country"):
        country = visual_data["estimated_country"].lower()
        coords = COUNTRY_COORDS.get(country)
        if coords:
            visual_lat, visual_lng = coords
        if not plate_match and not signs_match and not region_filter_match and not web_hint_match and not sat_comparison_match:
            result["country"] = visual_data.get("estimated_country")
            result["region"] = visual_data.get("estimated_region")
        visual_conf = visual_data.get("confidence", 0.5)
        if not plate_match and not signs_match and not region_filter_match and not web_hint_match and not sat_comparison_match:
            result["reasoning"]["visual"] = visual_data.get("reasoning", "Visual analysis")
        if visual_lat is not None and not plate_match and not signs_match and not region_filter_match and not web_hint_match and not sat_comparison_match:
            result["lat"] = visual_lat
            result["lng"] = visual_lng
            result["radius_km"] = 500

    # Calculate dynamic confidence
    if plate_match:
        # plate_match has 0.9+ base confidence
        result["confidence"] = 0.90 + (0.09 * solar_conf)
    elif signs_match:
        # signs_match has 0.7+ base confidence
        result["confidence"] = 0.70 + (0.15 * solar_conf)
    elif sat_comparison_match:
        # satellite comparison has 0.70+ base confidence
        result["confidence"] = 0.70 + (0.10 * solar_conf)
    elif region_filter_match:
        # region_filter_match has 0.65+ base confidence
        result["confidence"] = 0.65 + (0.15 * solar_conf)
    elif web_hint_match:
        # web_hint_match has 0.60+ base confidence
        lm_boost = 0.10 if web_hints and web_hints.get("landmarks") else 0.0
        result["confidence"] = 0.60 + lm_boost + (0.10 * solar_conf)
    else:
        # only standard visual/solar signals: max 0.60
        result["confidence"] = min(solar_conf * 0.4 + visual_conf * 0.6, 0.60)

    # top3 candidates passthrough
    if visual_data and visual_data.get("top3_candidates"):
        result["top3_candidates"] = visual_data["top3_candidates"]

    # Fusion logic
    if plate_match and solar_lat is not None:
        result["source"] = "full_fusion"
        result["radius_km"] = 25
        result["reasoning"]["fusion"] = f"Plate match ({plate_match[0]}) confirmed by solar lat ~{solar_lat}"
    elif signs_match and solar_lat is not None and not plate_match:
        result["source"] = "full_fusion"
        result["radius_km"] = 50
        result["reasoning"]["fusion"] = f"Signs match ({signs_match[0]}) confirmed by solar lat ~{solar_lat}"
    elif sat_comparison_match and solar_lat is not None:
        result["source"] = "full_fusion"
        result["radius_km"] = 40
        result["reasoning"]["fusion"] = f"Satellite comparison ({sat_comparison_match[0]}) confirmed by solar lat ~{solar_lat}"
    elif region_filter_match and solar_lat is not None:
        result["source"] = "full_fusion"
        result["radius_km"] = 80
        result["reasoning"]["fusion"] = f"Region filter ({region_filter_match[0]}) confirmed by solar lat ~{solar_lat}"
    elif web_hint_match and solar_lat is not None:
        result["source"] = "full_fusion"
        result["radius_km"] = 100
        result["reasoning"]["fusion"] = f"Web detection ({web_hint_match[0]}) confirmed by solar lat ~{solar_lat}"
    elif solar_lat is not None and visual_lat is not None and not plate_match and not signs_match and not region_filter_match and not web_hint_match and not sat_comparison_match:
        result["lat"] = round((solar_lat + visual_lat) / 2, 2)
        result["lng"] = visual_lng
        result["radius_km"] = 25
        result["source"] = "full_fusion"
        result["reasoning"]["fusion"] = "Solar + visual signals combined"
    elif solar_lat is not None and not plate_match and not signs_match and not region_filter_match and not web_hint_match and not sat_comparison_match:
        result["reasoning"]["fusion"] = "Solar only (visual unavailable)"
        result["source"] = "solar_fusion"
    elif plate_match:
        result["reasoning"]["fusion"] = f"Plate match: {plate_match[0]}"
    elif signs_match:
        result["reasoning"]["fusion"] = f"Signs match: {signs_match[0]}"
    elif sat_comparison_match:
        result["reasoning"]["fusion"] = f"Satellite comparison match: {sat_comparison_match[0]} (solar unavailable)"
    elif region_filter_match:
        result["reasoning"]["fusion"] = f"Region filter match: {region_filter_match[0]} (solar unavailable)"
    elif web_hint_match:
        result["reasoning"]["fusion"] = f"Web hint match: {web_hint_match[0]} (solar unavailable)"
    elif visual_lat is not None:
        result["reasoning"]["fusion"] = "Visual only (solar unavailable)"
        result["source"] = "visual_fusion"

    result["confidence"] = round(min(result["confidence"], 0.99), 3)
    return result

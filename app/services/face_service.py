import asyncio
import base64
import io
import logging
import os
import tempfile
import time
from typing import Any, Dict, List
from app.core.config import settings

logger = logging.getLogger("footprint.face")


# ─── KATMAN 1: Yerel yüz tespiti ───────────────────────────────────────────

def _detect_faces_local(image_bytes: bytes) -> Dict[str, Any]:
    """
    face_recognition ile yüz tespiti.
    Koordinatlar, landmark sayısı, kaç yüz var döner.
    dlib import hatası varsa Gemini Vision fallback.
    """
    # Yontem 1: face_recognition (dlib gerektirir)
    try:
        import face_recognition
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        locations = face_recognition.face_locations(img_array, model="hog")
        landmarks_list = face_recognition.face_landmarks(img_array, locations)

        faces = []
        for i, (loc, landmarks) in enumerate(zip(locations, landmarks_list)):
            top, right, bottom, left = loc
            faces.append({
                "index": i,
                "bbox": {"top": top, "right": right, "bottom": bottom, "left": left},
                "width_px": right - left,
                "height_px": bottom - top,
                "landmark_count": sum(len(v) for v in landmarks.values()),
            })

        cropped_b64 = None
        if locations:
            top, right, bottom, left = locations[0]
            pad = 30
            h, w = img_array.shape[:2]
            cropped = img.crop((max(0, left - pad), max(0, top - pad), min(w, right + pad), min(h, bottom + pad)))
            buf = io.BytesIO()
            cropped.save(buf, format="JPEG", quality=90)
            cropped_b64 = base64.b64encode(buf.getvalue()).decode()

        return {"ok": True, "face_count": len(faces), "faces": faces, "cropped_face_b64": cropped_b64, "engine": "face_recognition"}

    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"face_recognition hatasi: {e}")

    # Yontem 2: Gemini Vision (dlib olmadan)
    try:
        import json, re, os
        from google import genai
        from google.genai import types

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY", "")
        if not api_key:
            return {"ok": False, "face_count": 0, "faces": [], "cropped_face_b64": None, "error": "no_api_key"}

        client = genai.Client(api_key=api_key)

        prompt = """Bu görseli analiz et. SADECE geçerli JSON döndür, markdown veya açıklama YOK.

Şema:
{"face_count": <tam_sayı>, "faces": [{"approximate_age": "<yaş_aralığı>", "gender_presentation": "<male/female/unknown>", "emotion": "<neutral/happy/sad/angry/surprised>", "description": "<kısa Türkçe tasvir>"}], "has_face": <true/false>}

Kurallar:
- "approximate_age": Yaş aralığı sayısal olarak yaz (örn: "20-30", "40-50", "child", "elderly").
- "gender_presentation": SADECE şu değerlerden biri: "male", "female", "unknown".
- "emotion": SADECE şu değerlerden biri: "neutral", "happy", "sad", "angry", "surprised".
- "description": Yüzün belirgin özelliklerini TÜRKÇE olarak 1-2 cümlede özetle. Örnekler:
    "Sakallı, gözlüklü genç adam"
    "Kısa siyah saçlı, gülümseyen kadın"
    "Güneş gözlüklü, esmer yetişkin erkek"
    "Şapka takan, kameraya bakmayan kişi"
  Saç rengi/uzunluğu, gözlük, sakal/bıyık, şapka, başörtüsü, takı, makyaj, ifade gibi belirgin görsel özellikleri kullan.
  İngilizce kelime ya da çeviri kullanma; tamamen Türkçe yaz."""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")],
        )
        text = re.sub(r"```json|```", "", response.text.strip()).strip()
        data = json.loads(text)

        return {
            "ok": True,
            "face_count": data.get("face_count", 0),
            "faces": data.get("faces", []),
            "cropped_face_b64": None,
            "engine": "gemini_vision"
        }
    except Exception as e:
        logger.warning(f"Gemini vision hatasi: {e}")
        return {"ok": False, "face_count": 0, "faces": [], "cropped_face_b64": None, "error": str(e)}


# ─── KATMAN 2: Yandex Ters Görsel Arama ────────────────────────────────────

async def _search_yandex(image_bytes: bytes) -> Dict[str, Any]:
    """Yandex Images Playwright wrapper — face_service engine şemasına uydurur."""
    from app.services.yandex_search import search_yandex
    return await search_yandex(image_bytes, max_results=10)

async def _search_saucenao(image_bytes: bytes) -> Dict[str, Any]:
    """SauceNAO ters gorsel arama."""
    import httpx
    t0 = time.time()
    print("SauceNAO fonksiyonu cagrildi")
    api_key = settings.SAUCENAO_API_KEY
    if not api_key:
        print("SauceNAO: API key yok, atlaniyor")
        return {"engine": "saucenao", "ok": False, "results": [],
                "error": "no_api_key", "took_ms": 0}
    data = {"output_type": 2, "numres": 6}
    if api_key:
        data["api_key"] = api_key
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.post(
                "https://saucenao.com/search.php",
                data=data,
                files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            )
            print(f"SauceNAO status={r.status_code}")
            print(f"SauceNAO body={r.text[:500]}")

            if r.status_code != 200:
                err_msg = f"HTTP {r.status_code}: {r.text[:100]}"
                logger.error(f"SauceNAO HTTP hatasi: {err_msg}")
                return {
                    "engine": "saucenao",
                    "ok": False,
                    "results": [],
                    "error": err_msg,
                    "took_ms": int((time.time() - t0) * 1000),
                }

            data = r.json()
            header_top = data.get("header", {})
            api_status = header_top.get("status", 0)
            if api_status != 0:
                err_msg = header_top.get("message", "API returned error status")
                logger.error(f"SauceNAO API hatasi status={api_status} message={err_msg}")
                return {
                    "engine": "saucenao",
                    "ok": False,
                    "results": [],
                    "error": f"API Error {api_status}: {err_msg}",
                    "took_ms": int((time.time() - t0) * 1000),
                }

            results = []
            for result in data.get("results", []):
                header = result.get("header", {})
                data_inner = result.get("data", {})
                try:
                    similarity = float(header.get("similarity", 0))
                except (ValueError, TypeError):
                    similarity = 0.0
                if similarity < 60:
                    continue
                urls = data_inner.get("ext_urls", [])
                for url in urls:
                    results.append({
                        "type": "saucenao",
                        "url": url,
                        "title": data_inner.get("title", ""),
                        "similarity": similarity,
                        "source": header.get("index_name", ""),
                    })
            print(f"SauceNAO results sayisi: {len(results)}")
            return {
                "engine": "saucenao",
                "ok": True,
                "results": results,
                "error": None,
                "took_ms": int((time.time() - t0) * 1000),
            }
    except Exception as e:
        logger.exception("SauceNAO aramasi sirasinda bir exception olustu")
        return {"engine": "saucenao", "ok": False, "results": [],
                "error": f"{type(e).__name__}: {e}",
                "took_ms": int((time.time() - t0) * 1000)}


async def _search_google_lens(image_bytes: bytes) -> Dict[str, Any]:
    """Google Lens ters gorsel arama - API key gerektirmez."""
    import httpx, re, base64
    t0 = time.time()
    try:
        async with httpx.AsyncClient(
            timeout=20, follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        ) as client:
            r = await client.post(
                "https://lens.google.com/upload",
                files={"encoded_image": ("image.jpg", image_bytes, "image/jpeg")},
                data={"image_url": "", "sbisrc": "4"},
            )
            print(f"Google Lens status={r.status_code} url={str(r.url)[:150]}")
            print(f"Google Lens body={r.text[:300]}")

            html = r.text
            results = []
            urls = re.findall(r'"(https?://(?!(?:www\.google\.|gstatic\.|googleapis\.))[^"]{10,100})"', html)
            seen = set()
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    results.append({"type": "google_lens", "url": url, "title": ""})
                if len(results) >= 10:
                    break

            return {
                "engine": "google_lens",
                "ok": len(results) > 0,
                "results": results,
                "error": None,
                "took_ms": int((time.time() - t0) * 1000),
            }
    except Exception as e:
        print(f"Google Lens hatasi: {type(e).__name__}: {e}")
        return {"engine": "google_lens", "ok": False, "results": [],
                "error": str(e), "took_ms": int((time.time() - t0) * 1000)}


async def _search_tineye(image_bytes: bytes) -> Dict[str, Any]:
    """TinEye ters gorsel arama."""
    import httpx
    t0 = time.time()
    key = getattr(settings, "TINEYE_KEY", None)
    if not key:
        logger.info("TinEye: API key yok, aramaya devam edilmiyor (graceful skip)")
        return {
            "engine": "tineye",
            "ok": False,
            "results": [],
            "error": "no_api_key",
            "took_ms": 0,
        }
    try:
        headers = {"X-API-KEY": key}
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.post(
                "https://api.tineye.com/rest/search/",
                headers=headers,
                files={"image": ("image.jpg", image_bytes, "image/jpeg")},
            )
            logger.info(f"TinEye API status={r.status_code}")
            if r.status_code != 200:
                err_msg = f"HTTP {r.status_code}: {r.text[:100]}"
                logger.error(f"TinEye HTTP hatasi: {err_msg}")
                return {
                    "engine": "tineye",
                    "ok": False,
                    "results": [],
                    "error": err_msg,
                    "took_ms": int((time.time() - t0) * 1000),
                }
            data = r.json()
            results = []
            for match in data.get("results", [])[:6]:
                backlinks = match.get("backlinks", [])
                page_url = match.get("page_url", "")
                if not page_url and backlinks:
                    page_url = backlinks[0].get("url", "") if isinstance(backlinks[0], dict) else backlinks[0]
                image_url = match.get("image_url", "")
                results.append({
                    "type": "tineye",
                    "url": page_url or image_url,
                    "title": match.get("domain", "") or "TinEye Match",
                    "score": match.get("score", 0),
                })
            return {
                "engine": "tineye",
                "ok": len(results) > 0,
                "results": results,
                "error": None,
                "took_ms": int((time.time() - t0) * 1000),
            }
    except Exception as e:
        logger.exception("TinEye aramasi sirasinda bir exception olustu")
        return {"engine": "tineye", "ok": False, "results": [],
                "error": f"{type(e).__name__}: {e}",
                "took_ms": int((time.time() - t0) * 1000)}



# ─── KATMAN 3: Google Vision Web Detection ─────────────────────────────────

async def _search_google_vision(image_bytes: bytes) -> Dict[str, Any]:
    """
    Google Cloud Vision API webDetection ile benzer görselleri bulur.
    """
    t0 = time.time()
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY", "")
    if not api_key:
        return {
            "engine": "google_vision", "ok": False,
            "results": [], "error": "no_api_key", "took_ms": 0
        }

    try:
        import httpx

        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
        b64_image = base64.b64encode(image_bytes).decode()

        payload = {
            "requests": [{
                "image": {"content": b64_image},
                "features": [
                    {"type": "WEB_DETECTION", "maxResults": 10},
                    {"type": "FACE_DETECTION", "maxResults": 5},
                    {"type": "LABEL_DETECTION", "maxResults": 5},
                ]
            }]
        }

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload)
            data = r.json()

        resp = (data.get("responses") or [{}])[0]
        web = resp.get("webDetection", {})
        faces = resp.get("faceAnnotations", [])

        results = []
        for img in web.get("fullMatchingImages", [])[:5]:
            results.append({"type": "full_match", "url": img.get("url", ""), "score": img.get("score", 0)})
        for img in web.get("partialMatchingImages", [])[:5]:
            results.append({"type": "partial_match", "url": img.get("url", ""), "score": img.get("score", 0)})
        for page in web.get("pagesWithMatchingImages", [])[:5]:
            results.append({"type": "matching_page", "url": page.get("url", ""), "title": page.get("pageTitle", "")})

        entities = []
        for entity in web.get("webEntities", [])[:5]:
            desc = entity.get("description", "")
            score = entity.get("score", 0)
            if desc:
                entities.append({"description": desc, "score": score})

        face_emotions = []
        for f in faces:
            face_emotions.append({
                "joy": f.get("joyLikelihood"),
                "sorrow": f.get("sorrowLikelihood"),
                "anger": f.get("angerLikelihood"),
                "surprise": f.get("surpriseLikelihood"),
            })

        # faceAnnotations bossa, webEntities'den person/face say
        face_count = len(faces)
        if face_count == 0:
            person_entities = [e for e in web.get("webEntities", [])
                              if any(kw in (e.get("description", "") or "").lower()
                                     for kw in ("person", "face", "portrait", "selfie"))]
            if person_entities:
                face_count = len(person_entities)

        return {
            "engine": "google_vision",
            "ok": True,
            "results": results,
            "entities": entities,
            "face_count": face_count,
            "face_emotions": face_emotions,
            "best_guess": web.get("bestGuessLabels", []),
            "error": None,
            "took_ms": int((time.time() - t0) * 1000),
        }

    except Exception as e:
        logger.warning(f"Google Vision hatasi: {e}")
        return {
            "engine": "google_vision", "ok": False, "results": [],
            "error": str(e), "took_ms": int((time.time() - t0) * 1000)
        }


# ─── ANA ORKESTRATİF ────────────────────────────────────────────────────────

async def run_face_search(image_bytes: bytes, engines: List[str], max_results: int) -> Dict[str, Any]:
    t0 = time.time()

    # Katman 1: Yerel tespit (sync, executor'da çalıştır)
    local_result = await asyncio.get_event_loop().run_in_executor(
        None, _detect_faces_local, image_bytes
    )

    if local_result["face_count"] == 0 and local_result["ok"]:
        logger.info("Gorselde yuz tespit edilemedi")

    # Kırpılmış yüz varsa onu kullan, yoksa orijinali
    search_image = image_bytes
    if local_result.get("cropped_face_b64"):
        search_image = base64.b64decode(local_result["cropped_face_b64"])

    # Katman 2 & 3: Paralel
    tasks = []
    logger.info(f"run_face_search engines listesi: {engines}")
    # "yandex" artık gerçek Yandex Playwright arama; "saucenao" SauceNAO API
    if "yandex" in engines:
        tasks.append(("yandex", _search_yandex(search_image)))
    if "saucenao" in engines:
        if settings.SAUCENAO_API_KEY:
            logger.info("SauceNAO task ekleniyor")
            tasks.append(("saucenao", _search_saucenao(search_image)))
        else:
            logger.info("SAUCENAO_API_KEY yok, Google Lens kullaniliyor")
            tasks.append(("google_lens", _search_google_lens(search_image)))
    if "tineye" in engines:
        tasks.append(("tineye", _search_tineye(search_image)))
    if "google_vision" in engines:
        tasks.append(("google_vision", _search_google_vision(search_image)))

    engine_results = {}
    if tasks:
        gathered = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        for (name, _), result in zip(tasks, gathered):
            if isinstance(result, Exception):
                engine_results[name] = {"engine": name, "ok": False, "error": str(result), "results": []}
            else:
                engine_results[name] = result

    # Tüm URL'leri birleştir ve dedup
    all_urls = []
    seen = set()
    for eng_result in engine_results.values():
        for item in eng_result.get("results", []):
            url = item.get("url", "")
            if url and url not in seen:
                seen.add(url)
                all_urls.append(item)

    # Verdict
    total_matches = len(all_urls)
    if total_matches > 0:
        verdict = "matches_found"
    elif local_result.get("face_count", 0) == 0:
        verdict = "no_face_detected"
    else:
        verdict = "no_match"

    return {
        "verdict": verdict,
        "face_detection": {
            "face_count": local_result.get("face_count", 0),
            "faces": local_result.get("faces", []),
            "engine_ok": local_result.get("ok", False),
        },
        "engines": engine_results,
        "matches": all_urls[:max_results],
        "match_count": total_matches,
        "took_ms": int((time.time() - t0) * 1000),
    }

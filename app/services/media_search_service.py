import base64, httpx, piexif
from typing import List, Dict
from app.core.config import (REQUEST_TIMEOUT, SAFE, LOCALE, API_KEY, CX)
def calculate_risk_score(search_results: List[Dict] = None, exif_data: Dict = None) -> Dict:
    score = 0; reasons = []; sm = ["facebook.com","linkedin.com","instagram.com","twitter.com","x.com"]
    if search_results:
        score += len(search_results) * 5
        if len(search_results) > 0: reasons.append(f"{len(search_results)} adet arama sonucu bulundu (+{len(search_results)*5} Puan)")
        for r in search_results:
            if any(s in r.get("platform","") for s in sm): score += 15; reasons.append(f"Sosyal medya profili bulundu ({r.get('platform')}) (+15 Puan)"); break
    if exif_data:
        if "GPS" in exif_data and exif_data.get("GPS"): score += 50; reasons.append("Fotoğrafta GPS verisi bulundu (+50 Puan)")
        if "Exif" in exif_data and exif_data.get("Exif",{}).get("DateTimeOriginal"): score += 10; reasons.append("Fotoğrafta çekim tarihi bilgisi bulundu (+10 Puan)")
    level = "Düşük"; 
    if score > 70: level="Yüksek"
    elif score > 30: level="Orta"
    return {"score": score, "level": level, "reasons": reasons}
async def text_search_google(name: str, site: str=None, page: int=1, num: int=10) -> List[Dict]:
    if not API_KEY or not CX: return []
    query = f'"{name}"'; start = (page-1)*num+1
    params = {"key":API_KEY,"cx":CX,"q":query,"num":num,"start":start,"hl":LOCALE,"safe":SAFE}
    if site: params["siteSearch"]=site; params["siteSearchFilter"]="i"
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
        if r.status_code != 200: return []
        items = r.json().get("items",[]) or []; results=[]
        from urllib.parse import urlparse
        for it in items:
            link = it.get("link","")
            results.append({"title": it.get("title"), "link": link, "snippet": it.get("snippet"), "platform": urlparse(link).netloc if link else ""})
        return results
    except httpx.HTTPError: return []
async def reverse_image_search_google(image_bytes: bytes) -> List[Dict]:
    if not API_KEY: return []
    vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    body = {"requests":[{"image":{"content":encoded},"features":[{"type":"WEB_DETECTION","maxResults":20}]}]}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT+10) as client:
            r = await client.post(vision_url, json=body)
        if r.status_code != 200: return []
        web = r.json().get("responses",[{}])[0].get("webDetection",{})
        return [{"title": e.get("pageTitle","Başlık Yok"), "link": e.get("url")} for e in web.get("pagesWithMatchingImages",[])]
    except httpx.HTTPError: return []
def extract_exif_readable(image_bytes: bytes):
    exif_dict = piexif.load(image_bytes); readable={}
    for ifd, tags in exif_dict.items():
        if ifd=="thumbnail": continue
        readable[ifd]={}
        for tag, value in tags.items():
            tag_name = piexif.TAGS[ifd].get(tag,{}).get("name", f"UnknownTag_{tag}")
            try: readable[ifd][tag_name] = value.decode("utf-8", errors="ignore")
            except Exception: readable[ifd][tag_name] = value
    return readable

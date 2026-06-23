from typing import Optional
from fastapi import APIRouter, Query, File, UploadFile
from app.services.media_search_service import extract_exif_readable, calculate_risk_score, text_search_google, reverse_image_search_google
router = APIRouter(tags=["media"])
@router.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    try:
        exif = extract_exif_readable(image_bytes)
        risk = calculate_risk_score(exif_data=exif)
        if not any(exif.values()): return {"filename": file.filename, "message":"EXIF verisi yok.", "risk_info": risk}
        return {"filename": file.filename, "exif_data": exif, "risk_info": risk}
    except Exception:
        return {"filename": file.filename, "message":"EXIF okunamadı veya dosya fotoğraf değil.", "risk_info": calculate_risk_score()}
@router.post("/combined-search")
async def combined_search(name: str = Query(...), site: Optional[str]=Query(None), file: Optional[UploadFile]=File(None)):
    text_results = await text_search_google(name=name, site=site)
    if file:
        image_bytes = await file.read(); image_results = await reverse_image_search_google(image_bytes=image_bytes)
        def norm(u:str): 
            if not u: return ""
            return u.lower().replace("https://","").replace("http://","").replace("www.","").rstrip("/")
        links_norm = {norm(r.get("link")) for r in image_results}
        intersection = [t for t in text_results if norm(t.get("link")) in links_norm]
        return {"search_name":name,"site_filter":site,"image_filename":file.filename,"intersection_results":intersection,"text_search_count":len(text_results),"image_search_count":len(image_results),"text_search_results":text_results,"image_search_results":image_results}
    else:
        risk = calculate_risk_score(search_results=text_results)
        return {"search_name":name,"site_filter":site,"image_filename":None,"intersection_results":[],"text_search_count":len(text_results),"image_search_count":0,"text_search_results":text_results,"image_search_results":[],"risk_info":risk}

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(tags=["ai"])

@router.post("/ai-bio-analysis")
def ai_bio_analysis(payload: dict = Body(...)):
    username = (payload or {}).get("username","").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username gerekli.")
    # placeholder (lokal AI entegrasyonunu sonra takarız)
    prompt = f"Analyze bios for user: {username}. Return JSON with fields match_confidence_score and analysis_summary_tr."
    return JSONResponse({"username": username, "ai": {"note": "placeholder", "prompt_preview": prompt}})

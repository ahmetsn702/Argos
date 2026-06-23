from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
import hashlib, random

router = APIRouter()

# -------- Models --------
class CaptionIn(BaseModel):
    image_url: HttpUrl
    tone: Optional[str] = None
    num: int = 3  # 2-3 öneri için 3 ideal

class CaptionItem(BaseModel):
    text: str
    style: str
    score: float

class CaptionOut(BaseModel):
    captions: List[CaptionItem]
    flags: List[str] = []

class HashtagIn(BaseModel):
    text: str
    topic: Optional[str] = None
    num: int = 8   # 5-8 öneri için 8 ideal

class HashtagOut(BaseModel):
    hashtags: List[str]

class Slot(BaseModel):
    dow: int
    hour: int
    score: float

class BestTimeOut(BaseModel):
    top3: List[Slot]
    heatmap: List[List[float]]  # 7x24

# -------- Helpers --------
def _seed(s: str) -> random.Random:
    h = int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16) % (2**32)
    return random.Random(h)

def _gen_captions(url: str, tone: Optional[str], num: int):
    base = ["Kısa", "Bilgilendirici", "Etkileşim", "Minimal", "Soru"]
    tone = (tone or "").strip().lower()
    r = _seed(url + (tone or ""))
    k = max(1, min(num, 5))
    picks = r.sample(base, k=k)
    caps = []
    for i, st in enumerate(picks):
        tag = f"{st}" if not tone else f"{st} · {tone.capitalize()}"
        core = [
            "Gökyüzünün ötesine bak!",
            "Bugünün anı: {h}",
            "Detaylar açıklamada.",
            "Bir görsel, bin kelime.",
            "Takipte kal 👀",
        ]
        text = core[i % len(core)].replace("{h}", hashlib.md5(url.encode()).hexdigest()[:6])
        score = min(round(0.68 + i*0.07 + r.random()*0.18, 3), 0.99)
        caps.append({"text": text, "style": tag, "score": score})
    return caps

def _kw(text: str):
    w = [x.strip("#,.!?;:()[]{}\"'").lower() for x in text.split()]
    w = [x for x in w if x and x.isalnum() and len(x) > 2]
    return list(dict.fromkeys(w))[:10]

def _hash_tags(text: str, topic: Optional[str], num: int):
    base = ["#photo", "#daily", "#discover", "#explore", "#original", "#content"]
    kws = _kw(text)
    if topic:
        base.extend([f"#{topic.lower()}", f"#{topic.lower()}daily"])
    base.extend([f"#{k}" for k in kws[:6]])
    out = list(dict.fromkeys(base))
    return out[:max(1, min(num, 20))]

def _best_time(account: Optional[str]) -> Dict[str, Any]:
    # Basit sezgisel: İstanbul alışkanlığına göre akşam zirvesi
    rng = _seed(account or "global")
    heat = [[0.0 for _ in range(24)] for _ in range(7)]
    for d in range(7):
        for h in range(24):
            base = 0.2
            if 18 <= h <= 22: base += 0.5  # akşam
            if 12 <= h <= 14: base += 0.2  # öğle
            base += rng.random()*0.15
            heat[d][h] = round(min(base, 1.0), 3)
    flat = [ (heat[d][h], d, h) for d in range(7) for h in range(24) ]
    flat.sort(reverse=True)
    top3 = [{"dow": d, "hour": h, "score": round(s,3)} for s,d,h in flat[:3]]
    return {"top3": top3, "heatmap": heat}

# -------- Routes --------
@router.post("/captions", response_model=CaptionOut, tags=["compose"])
def captions(body: CaptionIn):
    try:
        items = _gen_captions(str(body.image_url), body.tone, body.num)
        flags = []
        if "nude" in str(body.image_url).lower():
            flags.append("sensitive:review")
        return {"captions": items, "flags": flags}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/schedule/best-time", response_model=BestTimeOut, tags=["compose"])
def best_time(account: Optional[str] = Query(None)):
    return BestTimeOut(**_best_time(account))

@router.post("/hashtags", response_model=HashtagOut, tags=["compose"])
def hashtags(body: HashtagIn):
    return {"hashtags": _hash_tags(body.text, body.topic, body.num)}
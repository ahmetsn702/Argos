import json, httpx
from typing import List, Dict
from collections import Counter
from app.core.config import (OLLAMA_API_URL, OLLAMA_MODEL)
from app.utils.common import normalize_bio_text, tokens, jaccard, char_ngrams, cosine_sim
def bio_similarity(b1: str, b2: str) -> Dict[str, float]:
    nb1 = normalize_bio_text(b1); nb2 = normalize_bio_text(b2)
    if nb1 and nb1 == nb2:
        return {"jaccard":1.0,"char_trigram":1.0,"score":1.0,"jaccard_intersection":len(set(tokens(b1))),"jaccard_a_tokens":len(set(tokens(b1))),"jaccard_b_tokens":len(set(tokens(b2)))}
    subset_boost = 0.0
    if nb1 and nb2:
        shorter = nb1 if len(nb1) <= len(nb2) else nb2
        longer  = nb2 if shorter is nb1 else nb1
        if len(shorter) >= 3 and shorter in longer: subset_boost = 0.88
    t1, t2 = tokens(b1), tokens(b2)
    j, inter, a_count, b_count = jaccard(t1, t2)
    c = cosine_sim(char_ngrams(b1,3), char_ngrams(b2,3))
    combined = 0.6*j + 0.4*c; score = max(combined, subset_boost)
    return {"jaccard": j, "char_trigram": c, "score": score, "jaccard_intersection": inter, "jaccard_a_tokens": a_count, "jaccard_b_tokens": b_count}
def verdict_from_score(score: float, same_display_name: bool) -> str:
    hi = 0.75 if not same_display_name else 0.68; mid = 0.55 if not same_display_name else 0.50
    if score >= hi: return "likely_same"
    if score >= mid: return "unclear"
    return "unlikely"
def build_ai_prompt(profiles: List[Dict]) -> str:
    lines=[]
    for p in profiles:
        lines.append(f"- Platform: {p.get('platform','')}")
        lines.append(f"  - Görünen İsim: {p.get('display_name','')}")
        lines.append(f"  - Biyografi: {p.get('bio','')}")
        lines.append("")
    schema = r'''{
  "match_confidence_score": <0..100 tam sayı>,
  "analysis_summary_tr": "<Türkçe 1-2 cümle özet>",
  "common_entities": {
    "locations": ["<yalnızca metinde geçen şehir/ülke vb.>"],
    "organizations": ["<yalnızca metinde geçen kurum/şirket/okul>"],
    "titles": ["<yalnızca metinde geçen unvan/rol>"]
  },
  "conclusion": "<'Yüksek Olasılıkla Aynı Kişi' | 'Orta Olasılıkla Aynı Kişi' | 'Düşük Olasılık'>",
  "evidence": [{"platform":"<Platform>","field":"<display_name | bio>","span":"<birebir alıntı>"}]
}'''
    return f"Aşağıdaki profilleri analiz et ve şemaya %100 uyan TEK bir JSON üret.\n\nSADECE ŞEMA:\n{schema}\n\nVERİ:\n" + "\n".join(lines)
def _string_in_profiles(s: str, profiles: List[Dict]) -> bool:
    if not s: return False
    s_norm = s.strip().lower()
    for p in profiles:
        for key in ("display_name","bio"):
            txt = (p.get(key) or "").lower()
            if s_norm and s_norm in txt: return True
    return False
def validate_and_ground_ai(ai: Dict, profiles: List[Dict]) -> Dict:
    out = {"match_confidence_score":0,"analysis_summary_tr":"","common_entities":{"locations":[],"organizations":[],"titles":[]},"conclusion":"Düşük Olasılık","evidence":[],"validation_warnings":[]}
    if not isinstance(ai, dict): return {**out, "validation_warnings":["AI yanıtı JSON değil."], "raw": ai}
    try: score = int(ai.get("match_confidence_score",0))
    except Exception: score = 0; out["validation_warnings"].append("Skor tamsayı değil; 0'a çekildi.")
    score = max(0, min(100, score)); out["match_confidence_score"]=score
    summary = ai.get("analysis_summary_tr") or ai.get("analysis_summary") or ""
    out["analysis_summary_tr"] = summary.strip()[:600] if isinstance(summary,str) else ""
    ents = ai.get("common_entities") or {}
    for k in ("locations","organizations","titles"):
        arr = ents.get(k, []); cleaned=[]
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, str) and _string_in_profiles(item, profiles): cleaned.append(item.strip())
                elif isinstance(item, str): out["validation_warnings"].append(f"Metinde geçmeyen {k[:-1]}: '{item}' — kaldırıldı.")
        else: out["validation_warnings"].append(f"{k} listesi değil; boş sayıldı.")
        out["common_entities"][k]=cleaned[:10]
    ev = ai.get("evidence") or []; valid_ev=[]
    if isinstance(ev, list):
        for e in ev:
            if not isinstance(e, dict): continue
            plat = (e.get("platform") or "").strip(); field = (e.get("field") or "").strip(); span = (e.get("span") or "").strip()
            if field not in ("display_name","bio"): continue
            if span and _string_in_profiles(span, profiles): valid_ev.append({"platform":plat,"field":field,"span":span})
            else: out["validation_warnings"].append(f"Kanıt metinde yok: '{span}' — atlandı.")
    else: out["validation_warnings"].append("evidence listesi değil.")
    out["evidence"]=valid_ev[:12]
    total_bio_len = sum(len((p.get("bio") or "").strip()) for p in profiles)
    if total_bio_len < 20: score = min(score,30); out["validation_warnings"].append("Biyografiler çok kısa/boş; skor 30 ile sınırlandı.")
    if len(valid_ev)==0: score=min(score,40); out["validation_warnings"].append("Kanıt yok; skor 40 ile sınırlandı.")
    out["match_confidence_score"]=score
    if score>=75: concl="Yüksek Olasılıkla Aynı Kişi"
    elif score>=55: concl="Orta Olasılıkla Aynı Kişi"
    else: concl="Düşük Olasılık"
    if total_bio_len<20 or len(valid_ev)==0: concl="Düşük Olasılık"
    out["conclusion"]=concl; return out
async def analyze_bios_with_local_ai(profiles: List[Dict]) -> Dict:
    prompt = build_ai_prompt(profiles)
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "format":"json", "stream": False, "options":{"num_gpu":0,"temperature":0,"top_p":0.1,"num_ctx":1024,"seed":42}}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(OLLAMA_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json(); raw = data.get("response") or "{}"
        try: ai_obj = json.loads(raw)
        except Exception: return {"error":"AI JSON parse edilemedi.","raw":raw}
        grounded = validate_and_ground_ai(ai_obj, profiles); grounded["model"]=OLLAMA_MODEL; return grounded
    except httpx.ConnectError:
        return {"error":"Ollama'ya bağlanılamadı. 11434 açık mı?"}
    except Exception as e:
        return {"error": f"Lokal AI analizi başarısız: {str(e)}"}

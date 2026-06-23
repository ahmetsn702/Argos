import re
from typing import Dict, List, Tuple
from collections import Counter
from bs4 import BeautifulSoup
from app.core.config import IG_USER_AGENT
def ua() -> Dict[str, str]:
    return {
        "User-Agent": IG_USER_AGENT,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.7,tr-TR,tr;q=0.6",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
def clean_text(txt: str) -> str:
    if not txt: return ""
    return re.sub(r"\s+", " ", txt).strip()
def soup(html: str):
    try:
        return BeautifulSoup(html, "html.parser")
    except Exception:
        return None
BOILERPLATE_X = [
    "don’t miss what’s happening","don't miss what's happening","people on x are the first to know",
    "log in","sign up","join twitter today","join x today","you need to enable javascript",
    "create an account","see more tweets","account doesn’t exist","account doesn't exist",
]
JINA_GARBAGE_HINTS = ["title:", "url source:", "markdown content:"]
def is_valid_bio(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 3: return False
    tl = t.lower()
    if any(b in tl for b in BOILERPLATE_X): return False
    if any(h in tl for h in JINA_GARBAGE_HINTS): return False
    return True
URL_PATTERN = re.compile(r"https?://\S+")
EMAIL_PATTERN = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")
HANDLE_PATTERN = re.compile(r"[@#]\w+")
EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF]", flags=re.UNICODE)
def normalize_bio_text(s: str) -> str:
    if not s: return ""
    s = URL_PATTERN.sub(" ", s)
    s = EMAIL_PATTERN.sub(" ", s)
    s = HANDLE_PATTERN.sub(" ", s)
    s = EMOJI_PATTERN.sub(" ", s)
    s = s.lower()
    s = re.sub(r"[^0-9a-zçğıöşü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
def tokens(s: str) -> List[str]:
    return [t for t in normalize_bio_text(s).split() if len(t) >= 2]
def jaccard(a: List[str], b: List[str]) -> Tuple[float, int, int, int]:
    sa, sb = set(a), set(b)
    inter = len(sa & sb); union = len(sa | sb)
    if union == 0: return 0.0, inter, len(sa), len(sb)
    return inter/union, inter, len(sa), len(sb)
def char_ngrams(s: str, n: int = 3) -> Counter:
    s = normalize_bio_text(s).replace(" ", "")
    return Counter([s[i:i+n] for i in range(max(0, len(s)-n+1))])
def cosine_sim(c1: Counter, c2: Counter) -> float:
    if not c1 or not c2: return 0.0
    inter = set(c1) & set(c2)
    dot = sum(c1[k]*c2[k] for k in inter)
    mag1 = sum(v*v for v in c1.values()) ** 0.5
    mag2 = sum(v*v for v in c2.values()) ** 0.5
    if mag1 == 0 or mag2 == 0: return 0.0
    return dot / (mag1 * mag2)
def _as_pct(x: float) -> float:
    try: return round(float(x)*100.0, 2)
    except Exception: return 0.0

def bio_similarity(b1: str, b2: str) -> dict:
    nb1 = normalize_bio_text(b1); nb2 = normalize_bio_text(b2)
    if nb1 and nb1 == nb2:
        from .common import tokens
        return {"jaccard":1.0,"char_trigram":1.0,"score":1.0,
                "jaccard_intersection": len(set(tokens(b1))),
                "jaccard_a_tokens": len(set(tokens(b1))),
                "jaccard_b_tokens": len(set(tokens(b2)))}
    from .common import tokens, char_ngrams, cosine_sim, jaccard
    t1, t2 = tokens(b1), tokens(b2)
    j, inter, a_count, b_count = jaccard(t1, t2)
    c = cosine_sim(char_ngrams(b1,3), char_ngrams(b2,3))
    combined = 0.6*j + 0.4*c
    return {"jaccard":j, "char_trigram":c, "score":combined,
            "jaccard_intersection": inter, "jaccard_a_tokens": a_count, "jaccard_b_tokens": b_count}

def verdict_from_score(score: float, same_display_name: bool) -> str:
    hi = 0.75 if not same_display_name else 0.68
    mid = 0.55 if not same_display_name else 0.50
    if score >= hi: return "likely_same"
    if score >= mid: return "unclear"
    return "unlikely"

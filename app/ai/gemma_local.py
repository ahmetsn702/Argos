import typing
import os, re
from typing import Dict, Any, List, Tuple
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL_DIR = os.getenv("GEMMA_MODEL_DIR", os.path.join(os.getcwd(), "app", "models", "gemma3_270m_it"))

_tok = None
_model = None

# TR/Latin + temel noktalama dışını sil (emoji/diğer alfabeleri ayıklar)
_ALLOWED = re.compile(r"[^A-Za-zÇĞİÖŞÜçğıöşü0-9@#&%+/\-.,:;!?()'\" \n]")

def _sanitize_tr_text(text: str) -> str:
    return _ALLOWED.sub("", text or "").strip()

def _load():
    global _tok, _model
    if _model is not None:
        return

    compute_dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
    )

    _tok = AutoTokenizer.from_pretrained(MODEL_DIR, use_fast=True, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR,
        device_map="auto",
        quantization_config=quant,
        dtype=compute_dtype,      # 'torch_dtype' uyarısını kaldırır
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )
    if _tok.pad_token is None:
        _tok.pad_token = _tok.eos_token

def _apply_chat(system_msg: str, user_msg: str):
    msgs = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg},
    ]
    prompt = _tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = _tok(prompt, return_tensors="pt")
    return inputs

def _decode_new_only(gen_ids, inputs):
    # Sadece üretilen kısmı çöz (prompt’u çıkar)
    gen_ids = gen_ids[0][inputs["input_ids"].shape[-1]:]
    return _tok.decode(gen_ids, skip_special_tokens=True).strip()

def _trim_to_words(s: str, max_words: int = 20) -> str:
    words = s.strip().split()
    if len(words) <= max_words:
        return s.strip()
    return " ".join(words[:max_words]).rstrip(" ,;:") + "."

# ------------------------- GENERATE --------------------------------------------

def generate(prompt: typing.Optional[str] = None, max_new_tokens: int = 64, temperature: float = 0.0, top_p: float = 0.9) -> str:
    """
    Kısa, tek cümlelik Türkçe yanıt üretir. Varsayılan deterministik (temp=0.0).
    Çıkış TR karakter filtresinden geçer ve max ~20 kelimeye kırpılır.
    """
    _load()

    system = "Yalnızca düzgün Türkçe yaz. Kısa, net, tekrar etme, tek cümle. Yalnızca cevap, başka açıklama yok."
    # LLM'i tek cümlelik net forma zorlayalım:
    user   = f"Aşağıdaki talimatı tek bir Türkçe cümleyle yerine getir. En fazla 20 kelime. Nokta ile bitir.\nTalimat: {prompt}\nCÜMLE:"

    inputs = _apply_chat(system, user).to(_model.device)
    do_sample = bool(temperature and float(temperature) > 0.0)

    gen_kwargs = dict(
        max_new_tokens=int(max_new_tokens),
        repetition_penalty=1.12,
        no_repeat_ngram_size=3,
        pad_token_id=_tok.eos_token_id,
        eos_token_id=_tok.eos_token_id,
    )
    if do_sample:
        gen_kwargs.update(dict(do_sample=True, temperature=float(temperature), top_p=float(top_p)))
    else:
        gen_kwargs.update(dict(do_sample=False))

    with torch.no_grad():
        out = _model.generate(**inputs, **gen_kwargs)

    txt = _decode_new_only(out, inputs)
    # "CÜMLE:" sonrası ilk satırı çek
    c = txt.splitlines()[0] if txt else ""
    c = _sanitize_tr_text(c)
    c = _trim_to_words(c, 20)
    # Tek cümle garantisi: fazla satırları at
    if "." in c:
        c = c.split(".")[0].strip() + "."
    return c

# ------------------------- ANALYZE_BIO -----------------------------------------

_KEYWORDS_ROLE  = re.compile(r"\b(founder|co[- ]?founder|kurucu|ceo|cto|cpo|lead|manager|müdür|danışman|advisor|mentor|researcher|öğrenci|student|developer|engineer)\b", re.I)
_KEYWORDS_TECH  = re.compile(r"\b(ai|ml|python|pytorch|data|veri|nlp|cv|cloud|aws|gcp|azure|kubernetes|sql)\b", re.I)
_KEYWORDS_BRAND = re.compile(r"\b(google|meta|microsoft|apple|amazon|openai|deepmind|acme|@)\b", re.I)

def _heuristic_bio(bio: str) -> Tuple[List[str], int]:
    """
    Hiç madde/SCORE çıkmazsa, input'tan 3-5 madde türet ve basit bir skor hesapla.
    """
    raw = bio
    # Parçala
    parts = re.split(r"[•·\u2022|,/;–—|\n]+", raw)
    parts = [p.strip(" -•\t\r ") for p in parts if p and len(p.strip()) > 0]

    # Kısa maddeler üret
    bullets: List[str] = []
    for p in parts:
        p1 = _sanitize_tr_text(p)
        if 2 <= len(p1.split()) <= 8:  # çok uzun/çok kısa olmasın
            bullets.append(p1)
        if len(bullets) >= 5:
            break

    if not bullets:
        # son çare: boş kalmasın
        bullets = [w for w in [
            "Kısa ve net profil",
            "Rol ve uzmanlık vurgusu",
            "İletişime açık"
        ] if w]

    # Skor: basit pozitif/negatif
    score = 60
    txt_l = raw.lower()
    if _KEYWORDS_ROLE.search(txt_l):  score += 10
    if _KEYWORDS_BRAND.search(txt_l): score += 10
    if _KEYWORDS_TECH.search(txt_l):  score += 10
    # çok emoji/çok kalabalık ise biraz kırp
    many_emoji = len(re.findall(r"[^\w\s,.;:@#&%+/\-'\"]", raw)) > 5
    if many_emoji: score -= 10
    score = max(0, min(100, score))

    return bullets[:5], score

def analyze_bio(bio: str) -> Dict[str, Any]:
    """
    3–5 madde + en sonda 'SCORE=<int>'.
    Model başarısız olursa heuristic fallback çalışır.
    """
    _load()

    bio = _sanitize_tr_text((bio or "").strip())

    system = (
        "Biyografi analiz asistanısın. ÇIKTI FORMATINI KESİNLİKLE TAKİP ET:\n"
        "- <madde 1>\n- <madde 2>\n- <madde 3>\n[opsiyonel 1-2 madde daha]\n"
        "Sonda tek satır: SCORE=<0-100>\n"
        "Başka hiçbir satır/emoji/başlık yok. Kısa, net, Türkçe veya kısa İngilizce olabilir."
    )

    fewshot = (
        "ÖRNEK GİRİŞ:\n"
        "BIO:\n"
        "Founder @Acme • ex-Google • Python & data • coffee addict ☕️\n\n"
        "ÖRNEK ÇIKIŞ:\n"
        "- Ürün ve ekip kuruculuğu tecrübesi\n"
        "- Büyük teknoloji geçmişi (ex-Google)\n"
        "- Python ve veri odaklı çalışma\n"
        "- Dinamik ve enerjik iletişim\n"
        "SCORE=82\n\n"
    )

    user = f"{fewshot}BIO:\n{bio}\n\nSADECE belirtilen formatı üret."

    inputs = _apply_chat(system, user).to(_model.device)
    with torch.no_grad():
        out = _model.generate(
            **inputs,
            max_new_tokens=180,
            do_sample=False,
            repetition_penalty=1.12,
            no_repeat_ngram_size=3,
            pad_token_id=_tok.eos_token_id,
            eos_token_id=_tok.eos_token_id,
        )

    txt = _decode_new_only(out, inputs)
    txt = _sanitize_tr_text(txt)

    bullets: List[str] = []
    for ln in txt.splitlines():
        s = ln.strip()
        if s.startswith("- "):
            item = s[2:].strip()
            if item:
                bullets.append(item)

    m = re.search(r"SCORE\s*=\s*(\d{1,3})", txt)
    score = None
    if m:
        try:
            score = max(0, min(100, int(m.group(1))))
        except Exception:
            score = None

    # Fallback – model formatı bozarsa yine dolu döneriz
    if not bullets or score is None:
        bullets2, score2 = _heuristic_bio(bio)
        if not bullets:
            bullets = bullets2
        if score is None:
            score = score2

    return {"ok": True, "bullets": bullets[:5], "score": score, "raw": txt}
# ==== FOOTPRINT PATCH @ 2025-10-19 18:57:59 ====
# === [PATCH BEGIN :: helpers for chat & bio] =================================
import re
from typing import List, Dict, Any

DEFAULT_SYSTEM_TR = "Kısa, net, Türkçe yanıt ver. Tekrar etme."

def _collapse_dupes(s: str) -> str:
    s = re.sub(r"\b(\w+)(\s+\1){1,}\b", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"([.!?])\1{1,}", r"\1", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def _clean_short_reply(txt: str, max_sentences: int = 2) -> str:
    if not txt:
        return txt
    txt = txt.strip()
    txt = re.split(r"\[ASİSTAN\]|\[ASISTAN\]|\n(?:Assistant|ASİSTAN)\s*:", txt, 1)[-1].strip()
    if "```" in txt:
        return _collapse_dupes(txt)
    parts = re.split(r"(?<=[.!?])\s+", txt)
    txt = " ".join(parts[:max_sentences]).strip()
    return _collapse_dupes(txt)

def _build_chat_prompt(messages: List[Dict[str, str]] = None,
                       system: str = None,
                       prompt: typing.Optional[str] = None = None) -> str:
    sys_msg = (system or DEFAULT_SYSTEM_TR).strip()
    if messages and isinstance(messages, list):
        blocks = [f"[SİSTEM]\n{sys_msg}"]
        for m in messages:
            role = (m.get("role","user") or "user").lower()
            content = (m.get("content") or "").strip()
            tag = "KULLANICI" if role == "user" else ("ASİSTAN" if role == "assistant" else role.upper())
            blocks.append(f"[{tag}]\n{content}")
        blocks.append("[ASİSTAN]\n")
        return "\n\n".join(blocks)
    p = (prompt or "").strip()
    return f"[SİSTEM]\n{sys_msg}\n\n[KULLANICI]\n{p}\n\n[ASİSTAN]\n"
# === [PATCH helpers END] =====================================================# === [PATCH A :: generate() kısa sohbet + sampling + tekrar kilidi] ==========
def generate(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Girdi:
      - prompt: typing.Optional[str] = None  (opsiyonel; messages yoksa)
      - messages: [{role, content}] (opsiyonel)
      - system: str  (opsiyonel)
      - max_new_tokens: int (default 80, [16..128])
      - temperature: float  (default 0.6, [0.1..1.2])
      - top_p: float         (default 0.92, [0.5..0.99])
      - repetition_penalty: float (default 1.12, [1.0..1.3])
      - no_repeat_ngram_size: int (default 4, [3..6])
      - max_sentences: int   (default 2)
    Çıktı: { "text": "...", "meta": {...} }
    """
    def _clamp(v, a, b): return max(a, min(b, v))
    max_new = _clamp(int(body.get("max_new_tokens", 80)), 16, 128)
    temperature = float(body.get("temperature", 0.6))
    top_p = float(body.get("top_p", 0.92))
    rep_pen = float(body.get("repetition_penalty", 1.12))
    ngram = int(body.get("no_repeat_ngram_size", 4))
    max_sent = int(body.get("max_sentences", 2))
    system = body.get("system")
    messages = body.get("messages")
    prompt = body.get("prompt")

    full_prompt = _build_chat_prompt(messages=messages, system=system, prompt=prompt)

    inputs = tokenizer(full_prompt, return_tensors="pt").to(model.device)
    eos_id = tokenizer.eos_token_id or tokenizer.convert_tokens_to_ids("</s>")
    pad_id = eos_id

    gen_ids = model.generate(
        **inputs,
        do_sample=True,
        temperature=_clamp(temperature, 0.1, 1.2),
        top_p=_clamp(top_p, 0.5, 0.99),
        max_new_tokens=max_new,
        repetition_penalty=_clamp(rep_pen, 1.0, 1.3),
        no_repeat_ngram_size=max(3, min(6, ngram)),
        renormalize_logits=True,
        eos_token_id=eos_id,
        pad_token_id=pad_id,
    )

    out_full = tokenizer.decode(gen_ids[0], skip_special_tokens=True)
    reply = out_full
    if "[ASİSTAN]" in out_full:
        reply = out_full.split("[ASİSTAN]", 1)[-1]
    elif prompt and prompt in out_full:
        reply = out_full.split(prompt, 1)[-1]

    reply = _clean_short_reply(reply, max_sentences=max_sent)
    return {
        "text": reply.strip(),
        "meta": {
            "max_new_tokens": max_new,
            "temperature": temperature,
            "top_p": top_p,
            "no_repeat_ngram_size": ngram,
            "repetition_penalty": rep_pen
        }
    }
# === [PATCH A END] ===========================================================# === [PATCH B :: analyze_bio() stabil 3–5 madde + SCORE] =====================
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
def _norm_tr(s: str) -> str:
    s = (s or "").replace("\u200b", "").strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s
def _ascii_lo(s: str) -> str:
    return _norm_tr(s).translate(_TR).lower()
def _score_bio(bio: str) -> Dict[str, Any]:
    t = _ascii_lo(bio)
    kws_pos = ["osint","yazilim","developer","engineer","security","ai","ml","python","fastapi","react","hatay","firat","universite","ögrenci","ogrenci","cv","github"]
    kws_risk = ["casino","bet","bahis","loan","kredi","18+","xxx","sex","porn","hacktool","crack","drug","mdma","btc-doubling"]
    has_link = bool(re.search(r"(https?://|@|#)", bio))
    pos = sum(1 for k in kws_pos if re.search(rf"\b{re.escape(k)}\b", t))
    risk = sum(1 for k in kws_risk if re.search(rf"\b{re.escape(k)}\b", t))
    length_bonus = min(len(bio)//40, 10)
    base = 50 + pos*6 - risk*10 + length_bonus
    if has_link: base += 4
    base = max(0, min(100, base))
    return {"score": int(base), "pos": pos, "risk": risk, "has_link": has_link}
def analyze_bio(body: Dict[str, Any]) -> Dict[str, Any]:
    bio = body.get("bio") or body.get("text") or ""
    bio = _norm_tr(bio)
    met = _score_bio(bio)
    bullets = []
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", bio)
    uniq = []
    for w in words:
        lw = w.lower()
        if len(lw) >= 3 and lw not in uniq:
            uniq.append(lw)
    top = ", ".join(uniq[:6]) if uniq else "—"
    bullets.append(f"- Anahtar kelimeler: {top}")
    tone = "teknik/öğrenci" if met["pos"] >= 2 else ("genel" if len(bio) >= 20 else "belirsiz")
    bullets.append(f"- Ton/Alan: {tone}")
    strong = []
    if met["pos"] >= 3: strong.append("teknik ilgi yüksek")
    if met["has_link"]: strong.append("harici bağlantı mevcut")
    bullets.append(f"- Güçlü sinyaller: {', '.join(strong) if strong else '—'}")
    warn = []
    if met["risk"] >= 1: warn.append("riskli kelimeler")
    if len(bio) < 10: warn.append("çok kısa bio")
    bullets.append(f"- Uyarılar: {', '.join(warn) if warn else '—'}")
    if len(bullets) < 5:
        bullets.append("- Öneri: bio’yu somut ilgi alanları ve 1 bağlantı ile zenginleştir")
    out = "\n".join(bullets[:5]) + f"\nSCORE={met['score']}"
    out = _collapse_dupes(out)
    return {"text": out}
# === [PATCH B END] ===========================================================
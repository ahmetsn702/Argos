import os, re, warnings
from typing import Any, Dict, List

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# -------- Model Load (offline) ----------
MODEL_DIR = os.environ.get("GEMMA_MODEL_DIR") or os.environ.get("LLAMA_MODEL_DIR")
tokenizer = None
model = None

def _init():
    global tokenizer, model
    if tokenizer is not None and model is not None:
        return
    if not MODEL_DIR or not os.path.isdir(MODEL_DIR):
        warnings.warn(f"MODEL_DIR yok veya geçersiz: {MODEL_DIR}")
        return
    try:
        # 4-bit (bitsandbytes) ile yükle (tamamen lokal)
        try:
            from transformers import BitsAndBytesConfig
            bnb_conf = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                          bnb_4bit_compute_dtype=torch.bfloat16)
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_DIR,
                device_map="auto",
                quantization_config=bnb_conf,
                trust_remote_code=True,
                local_files_only=True,
            )
        except Exception:
            # transformers sürüm farkı için fallback
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_DIR,
                device_map="auto",
                load_in_4bit=True,
                trust_remote_code=True,
                local_files_only=True,
            )

        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_DIR,
            use_fast=True,
            local_files_only=True,
            trust_remote_code=True,
        )
        if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
            tokenizer.pad_token = tokenizer.eos_token
        model.eval()
        print("gemma_local_fixed: model/tokenizer yüklendi:", MODEL_DIR)
    except Exception as e:
        tokenizer = None
        model = None
        warnings.warn(f"Model yüklenemedi: {e}")

_init()

# -------- Helpers ----------
# === Chat template aware prompt builder (LLaMA/HF) ===
def _build_chat_prompt_v2(messages: List[Dict[str, str]] = None,
                          system: str = None,
                          prompt: str = None) -> str:
    sys_msg = (system or DEFAULT_SYSTEM_TR).strip()
    try:
        # HF LLaMA tokenizer'larında chat template varsa onu kullan
        if messages and hasattr(tokenizer, "apply_chat_template"):
            msgs = []
            if sys_msg:
                msgs.append({"role": "system", "content": sys_msg})
            for m in messages:
                msgs.append({"role": (m.get("role","user") or "user"),
                             "content": (m.get("content") or "")})
            return tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True
            )
    except Exception:
        pass
    # Fallback: eski blok-tag şablonu (uyumluluk için)
    if messages and isinstance(messages, list):
        blocks = [f"[SİSTEM]\n{sys_msg}"] if sys_msg else []
        for m in messages:
            role = (m.get("role","user") or "user").lower()
            content = (m.get("content") or "").strip()
            tag = "KULLANICI" if role == "user" else ("ASİSTAN" if role == "assistant" else role.upper())
            blocks.append(f"[{tag}]\n{content}")
        blocks.append("[ASİSTAN]\n")
        return "\n\n".join(blocks)
    p = (prompt or "").strip()
    return f"[SİSTEM]\n{sys_msg}\n\n[KULLANICI]\n{p}\n\n[ASİSTAN]\n"
def _resolve_hf_dir(d: str) -> str | None:
    import os
    if not d or not os.path.isdir(d):
        return None
    def ok(p: str) -> bool:
        files = set(os.listdir(p))
        has_tok = ("tokenizer.json" in files) or ("tokenizer.model" in files)
        has_cfg = ("config.json" in files)
        has_wts = any(f.endswith(".safetensors") or f == "pytorch_model.bin" for f in files)
        has_gguf = any(f.endswith(".gguf") for f in files)
        return has_tok and has_cfg and has_wts and (not has_gguf)
    if ok(d):
        return d
    # bir seviye aşağı bak
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p) and ok(p):
            return p
    # iki seviye aşağı bak (gerekirse)
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            for name2 in os.listdir(p):
                p2 = os.path.join(p, name2)
                if os.path.isdir(p2) and ok(p2):
                    return p2
    return None
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
                       prompt: str = None) -> str:
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

# -------- A) Kısa sohbet üretimi ----------
def generate(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Girdi:
      - prompt | messages | system
      - max_new_tokens(16..128) default=80
      - temperature=0.6, top_p=0.92, repetition_penalty=1.12, no_repeat_ngram_size=4, max_sentences=2
    """
    if model is None or tokenizer is None:
        raise RuntimeError("Model yüklü değil. GEMMA_MODEL_DIR kontrol edin.")

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

    full_prompt = _build_chat_prompt_v2(messages=messages, system=system, prompt=prompt)
    inputs = tokenizer(full_prompt, return_tensors="pt").to(model.device)
    eos_id = tokenizer.eos_token_id or tokenizer.convert_tokens_to_ids("</s>")
    pad_id = tokenizer.pad_token_id or eos_id

    with torch.inference_mode():
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

    return {"text": (out if "out" in locals() else ""),
        "meta": {
            "max_new_tokens": max_new,
            "temperature": temperature,
            "top_p": top_p,
            "no_repeat_ngram_size": ngram,
            "repetition_penalty": rep_pen
        }
    }

# -------- B) Stabil bio analizi ----------
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

# == FOOTPRINT_DYNAMIC_RELOAD_SAFE ==
try:
    reload_model  # zaten varsa tekrar tanımlama
except NameError:
    _LAST_MODEL_DIR = None

    def _hf_dir_ok(d: str) -> bool:
        import os
        if not d or not os.path.isdir(d):
            return False
        files = set(os.listdir(d))
        has_tok = ("tokenizer.json" in files) or ("tokenizer.model" in files)
        has_cfg = ("config.json" in files)
        has_wts = any(f.endswith(".safetensors") or f == "pytorch_model.bin" for f in files)
        has_gguf = any(f.endswith(".gguf") for f in files)
        return has_tok and has_cfg and has_wts and (not has_gguf)

    def _maybe_reinit(force_dir: str | None = None):
        import os, warnings, torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        global MODEL_DIR, _LAST_MODEL_DIR, tokenizer, model
        env_dir = force_dir or os.environ.get("GEMMA_MODEL_DIR") or os.environ.get("LLAMA_MODEL_DIR")
        if env_dir and env_dir != MODEL_DIR:
            MODEL_DIR = env_dir
        need = (tokenizer is None or model is None or MODEL_DIR != _LAST_MODEL_DIR)
        if not need:
            return
        if not _hf_dir_ok(MODEL_DIR):
            _LAST_ERROR = f"HF model dizini değil veya eksik: {MODEL_DIR}"; warnings.warn(f"HF model dizini değil veya eksik: {MODEL_DIR}")
            tokenizer = None; model = None; _LAST_MODEL_DIR = MODEL_DIR
            return
        tokenizer = None; model = None
        try:
            try:
                from transformers import BitsAndBytesConfig
                bnb_conf = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                              bnb_4bit_compute_dtype=torch.bfloat16)
                _m = AutoModelForCausalLM.from_pretrained(
                    MODEL_DIR, device_map="auto", quantization_config=bnb_conf,
                    trust_remote_code=True, local_files_only=True,
                )
            except Exception:
                _m = AutoModelForCausalLM.from_pretrained(
                    MODEL_DIR, device_map="auto", load_in_4bit=True,
                    trust_remote_code=True, local_files_only=True,
                )
            _t = AutoTokenizer.from_pretrained(
                MODEL_DIR, use_fast=True, local_files_only=True, trust_remote_code=True,
            )
            if _t.pad_token_id is None and _t.eos_token_id is not None:
                _t.pad_token = _t.eos_token
            _m.eval()
            model = _m; tokenizer = _t; _LAST_MODEL_DIR = MODEL_DIR
            print("dynamic reload OK:", MODEL_DIR)
        except Exception as e:
            tokenizer = None; model = None; _LAST_MODEL_DIR = MODEL_DIR
            warnings.warn(f"Reload başarısız: {e}")

    def reload_model(dir: str | None = None) -> dict:
        import os
        if dir:
            os.environ["GEMMA_MODEL_DIR"] = dir
        _maybe_reinit(dir)
        ok = bool(model and tokenizer)
        return {"ok": ok, "model_dir": MODEL_DIR, "loaded": ok}

# Eski generate/analyze_bio üstüne güvenli sarmalayıcılar
try:
    _orig_generate
except NameError:
    _orig_generate = generate
    def generate(body: Dict[str, Any]) -> Dict[str, Any]:
        _maybe_reinit()
        if model is None or tokenizer is None:
            raise RuntimeError(f"Model yüklü değil veya HF format değil. MODEL_DIR={MODEL_DIR}")
        return _orig_generate(body)

try:
    _orig_analyze_bio
except NameError:
    _orig_analyze_bio = analyze_bio
    def analyze_bio(body: Dict[str, Any]) -> Dict[str, Any]:
        _maybe_reinit()
        return _orig_analyze_bio(body)
# == FOOTPRINT_DYNAMIC_RELOAD_SAFE_END ==

# == FOOTPRINT_OVERRIDE_INIT ==
_OvDefaults = {"device": None, "quant4bit": True, "attn": "eager"}
_OVERRIDES = globals().get("_OVERRIDES", dict(_OvDefaults))

def _maybe_reinit_v2(force_dir: str | None = None):
    import os, warnings, torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    global MODEL_DIR, tokenizer, model, _OVERRIDES
    # overrides
    ov = globals().get("_OVERRIDES", dict(_OvDefaults))
    device   = ov.get("device")
    use_4bit = bool(ov.get("quant4bit", True))
    attn     = ov.get("attn", "eager")

    # attention kernel seçimi
    try:
        if attn == "eager":
            try:
                torch.backends.cuda.enable_flash_sdp(False)
                torch.backends.cuda.enable_mem_efficient_sdp(False)
                torch.backends.cuda.enable_math_sdp(True)
            except Exception:
                pass
        else:
            try:
                torch.backends.cuda.enable_flash_sdp(True)
                torch.backends.cuda.enable_mem_efficient_sdp(True)
            except Exception:
                pass
    except Exception:
        pass

    # env ve yol
    env_dir = force_dir or os.environ.get("GEMMA_MODEL_DIR") or os.environ.get("LLAMA_MODEL_DIR")
    if env_dir:
        globals()["MODEL_DIR"] = env_dir

    # device seçimi
    if device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        devmap = "cpu"
    elif device == "cuda":
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        devmap = "auto"
    else:
        devmap = "auto"

    # HF dizini kontrolü (öncesinde dizini çözümle)

    try:

        _rd = _resolve_hf_dir(MODEL_DIR)

        if _rd:

            globals()["MODEL_DIR"] = _rd

    except Exception:

        pass

    # HF dizini kontrolü
    try:
        _ok = _hf_dir_ok(MODEL_DIR)  # type: ignore
    except Exception:
        _ok = bool(MODEL_DIR and os.path.isdir(MODEL_DIR))
    if not _ok:
        _LAST_ERROR = f"HF model dizini değil veya eksik: {MODEL_DIR}"; warnings.warn(f"HF model dizini değil veya eksik: {MODEL_DIR}")
        globals()["tokenizer"] = None; globals()["model"] = None
        return

    # temiz yükle
    globals()["tokenizer"] = None; globals()["model"] = None
    try:
        if use_4bit and device != "cpu":
            try:
                from transformers import BitsAndBytesConfig
                bnb_conf = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                              bnb_4bit_compute_dtype=torch.float16)
                _m = AutoModelForCausalLM.from_pretrained(
                    MODEL_DIR, device_map=devmap, quantization_config=bnb_conf,
                    trust_remote_code=True, local_files_only=True,
                )
            except Exception:
                _m = AutoModelForCausalLM.from_pretrained(
                    MODEL_DIR, device_map=devmap, load_in_4bit=True,
                    trust_remote_code=True, local_files_only=True,
                )
        else:
            # 4-bit KAPALI (CPU veya istek üzerine)
            _m = AutoModelForCausalLM.from_pretrained(
                MODEL_DIR, device_map=devmap, torch_dtype=torch.float16 if device=="cuda" else None,
                trust_remote_code=True, local_files_only=True,
            )

        _t = AutoTokenizer.from_pretrained(
            MODEL_DIR, use_fast=True, local_files_only=True, trust_remote_code=True,
        )
        if _t.pad_token_id is None and _t.eos_token_id is not None:
            _t.pad_token = _t.eos_token

        _m.eval()
        globals()["model"] = _m
        globals()["tokenizer"] = _t
        print("reload v2 OK:", MODEL_DIR, "device=", device, "4bit=", use_4bit, "attn=", attn)
    except Exception as e:
        globals()["tokenizer"] = None; globals()["model"] = None
        _LAST_ERROR = str(e); warnings.warn(f"Reload v2 başarısız: {e}")

# Eski fonksiyon adını yeni sürüme yönlendir
globals()["_maybe_reinit"] = _maybe_reinit_v2

# reload_model v2: HTTP'den override al ve yeniden yükle
def reload_model(dir: str | None = None, device: str | None = None,
                 quant4bit: bool | None = None, attn: str | None = None) -> dict:
    import os, warnings
    global _OVERRIDES
    try:
        if "_OVERRIDES" not in globals() or not isinstance(_OVERRIDES, dict):
            _OVERRIDES = dict(_OvDefaults)
        if device is not None:
            _OVERRIDES["device"] = device
            if device == "cpu":
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
                devmap = "cpu"
            elif device == "cuda":
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
        if quant4bit is not None:
            _OVERRIDES["quant4bit"] = bool(quant4bit)
        if attn is not None:
            _OVERRIDES["attn"] = attn
        if dir:
            os.environ["GEMMA_MODEL_DIR"] = dir
        _maybe_reinit_v2(dir)
        ok = bool(globals().get("model") and globals().get("tokenizer"))
        return {"ok": ok, "model_dir": os.environ.get("GEMMA_MODEL_DIR") or globals().get("MODEL_DIR"),
                "loaded": ok, "overrides": _OVERRIDES}
    except Exception as e:
        warnings.warn(f"reload v2 error: {e}")
        return {"ok": False, "error": str(e)}
# == FOOTPRINT_OVERRIDE_INIT_END ==# == FOOTPRINT_LAST_ERROR ==
try:
    _LAST_ERROR
except NameError:
    _LAST_ERROR = None

# == FOOTPRINT_DUMP_STATE ==
def dump_state() -> dict:
    try:
        md = globals().get("MODEL_DIR")
        m  = globals().get("model")
        t  = globals().get("tokenizer")
        ov = globals().get("_OVERRIDES")
        le = globals().get("_LAST_ERROR")
        dev = None
        dt  = None
        nop = None
        if m is not None:
            try:
                d = getattr(getattr(m, "device", None), "type", None) or getattr(m, "device", None)
                dev = str(d) if d is not None else None
            except Exception:
                dev = None
            try:
                _dt = getattr(getattr(m, "dtype", None), "name", None) or getattr(m, "dtype", None)
                dt = str(_dt) if _dt is not None else None
            except Exception:
                dt = None
        if t is not None:
            try:
                nop = str(getattr(t, "name_or_path", None))
            except Exception:
                nop = None
        return {
            "MODEL_DIR": md,
            "has_model": bool(m),
            "has_tokenizer": bool(t),
            "device": dev,
            "dtype": dt,
            "name_or_path": nop,
            "overrides": ov,
            "last_error": le,
        }
    except Exception as e:
        return {"error": str(e)}
# == FOOTPRINT_DUMP_STATE_END ==
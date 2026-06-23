# app/tools/fb_dump.py (v3.8 - session+headers, referer download, script JSON/escaped URL sweep, stronger login detect)
import os, re, sys, json, time, hashlib
from urllib.parse import urlparse, parse_qs, urljoin, unquote
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

CANDIDATES = [
    os.path.join(BASE_DIR, "secrets", "fb.cookie"),
    os.path.join(os.path.dirname(BASE_DIR), "secrets", "fb.cookie"),
]
COOKIE_FILE = next((p for p in CANDIDATES if os.path.exists(p)), CANDIDATES[0])

MIN_BYTES = int(os.getenv("FB_MIN_BYTES", "8192"))  # 8KB default
DEBUG = os.getenv("FB_DEBUG")

# single session for all requests (cookies, connection reuse, headers)
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Referer": "https://www.facebook.com/",
})

def read_cookie():
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        t = f.read().strip()
    t = re.sub(r"^\s*cookie:\s*", "", t, flags=re.I)
    # push raw cookie string to session
    SESSION.headers["Cookie"] = t
    return t

def host_ok(u: str) -> bool:
    h = (urlparse(u).hostname or "").lower()
    return ("scontent" in h) or ("fbcdn.net" in h) or ("lookaside.fbsbx.com" in h) or ("lookaside.facebook.com" in h)

def safe_unwrap(u: str) -> str:
    if "safe_image.php" in u:
        q = parse_qs(urlparse(u).query)
        if "url" in q and q["url"]:
            return unquote(q["url"][0])
    return u

def looks_like_login(html: str, final_url: str, soup: BeautifulSoup | None = None) -> bool:
    if "/login/" in final_url or "login.php" in final_url:
        return True
    L = (html or "").lower()
    flags = ('id="login_form"', 'name="login"', "oturum aç", "giriş yap",
             "log in to facebook", "you must log in", 'og:site_name" content="facebook')
    if any(tok in L for tok in flags):
        return True
    if soup:
        if soup.find("input", {"type": "password", "name": "pass"}):
            return True
        if soup.find("form", {"id": "login_form"}):
            return True
    return False

def seeds(username: str):
    u = username.strip().lstrip("@")
    mb = f"https://mbasic.facebook.com/{u}"
    m  = f"https://m.facebook.com/{u}"
    www= f"https://www.facebook.com/{u}"
    return [
        # www
        f"{www}/photos", f"{www}?sk=photos",
        f"{www}/photos_by", f"{www}?sk=photos_by",
        f"{www}/media", f"{www}/timeline/photos/",
        f"https://www.facebook.com/pg/{u}/photos",
        f"https://www.facebook.com/pg/{u}/photos/?ref=page_internal&type=3",
        # m / mbasic
        f"{m}/photos", f"{m}?sk=photos", f"{m}/photos_by", f"{m}?sk=photos_by", f"{m}/media",
        f"https://m.facebook.com/pg/{u}/photos",
        f"https://m.facebook.com/pg/{u}/photos/?ref=page_internal&type=3",
        f"{mb}/photos", f"{mb}?v=photos", f"{mb}/photos_by", f"{mb}?v=photos_by", f"{mb}/media",
        mb, m, www,
    ]

def fetch(url: str, cookie: str, timeout=20):
    r = SESSION.get(url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    if DEBUG:
        try:
            os.makedirs("/tmp/fb_debug", exist_ok=True)
        except Exception:
            pass
    return r.text, r.url

def _pick_from_srcset(val: str):
    try:
        items = []
        for part in val.split(","):
            p = part.strip()
            if not p: continue
            segs = p.split()
            url = segs[0]
            w = 0
            if len(segs) > 1 and segs[1].endswith("w"):
                try: w = int(segs[1][:-1])
                except: w = 0
            items.append((w, url))
        items.sort(reverse=True)
        return items[0][1] if items else None
    except:
        return None

def _normalize_possible_url(u: str) -> str:
    try:
        u = u.replace("\\/", "/")
        u = u.replace("&amp;", "&")
        u = unquote(u)
    except Exception:
        pass
    return u

_SCRIPT_SWEEPS = (
    r"https://[A-Za-z0-9_.-]*(?:scontent|fbcdn)[^\"'\\s>]+",
    r"https:\\/\\/[A-Za-z0-9_.-]*(?:scontent|fbcdn)[^\"'\\s>]+",
    r"https:%2F%2F[A-Za-z0-9_.-]*(?:scontent|fbcdn)[^\"'\\s>]+",
    r'{"__typename":"Image","uri":"(https?://[^"]+)"',
    r'"src":"(https?://[A-Za-z0-9_.-]*(?:scontent|fbcdn)[^"]+)"',
)

def extract_img_urls(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    details = []

    # 1) <img> + srcset
    for im in soup.find_all("img"):
        src = im.get("src") or im.get("data-src") or im.get("data-original")
        srcset = im.get("srcset")
        cand = None
        if srcset: cand = _pick_from_srcset(srcset)
        if not cand and src: cand = src
        if not cand: continue
        full = safe_unwrap(urljoin(base_url, cand))
        if any(tok in full for tok in ("s206x206","p206x206","s320x320")): continue
        if host_ok(full): urls.add(full)

    # 2) CSS background-image
    for tag in soup.find_all(True):
        st = tag.get("style") or ""
        for u in re.findall(r"url\(([^)]+)\)", st):
            u = _normalize_possible_url(u.strip("\"' "))
            full = safe_unwrap(urljoin(base_url, u))
            if any(tok in full for tok in ("s206x206","p206x206","s320x320")): continue
            if host_ok(full): urls.add(full)

    # 3) SCRIPT/JSON sweep (hydration verisi)
    for sc in soup.find_all("script"):
        body = sc.string or sc.text or ""
        if not body:
            continue
        for pat in _SCRIPT_SWEEPS:
            for u in re.findall(pat, body):
                u = _normalize_possible_url(u if isinstance(u, str) else u[0] if isinstance(u, tuple) else u)
                full = safe_unwrap(urljoin(base_url, u))
                if any(tok in full for tok in ("s206x206","p206x206","s320x320")): continue
                if host_ok(full): urls.add(full)

    # 4) GLOBAL sweep (HTML tamamında—script/JSON dahil)
    for pat in _SCRIPT_SWEEPS[:3]:
        for u in re.findall(pat, html):
            u = _normalize_possible_url(u)
            full = safe_unwrap(urljoin(base_url, u))
            if any(tok in full for tok in ("s206x206","p206x206","s320x320")): continue
            if host_ok(full): urls.add(full)

    # 5) Detay linkleri
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if any(k in h for k in ("photo.php", "/photo", "/photos/", "story.php", "story_fbid",
                                "/permalink/", "?fbid=", "/posts/", "/reel/", "set=a.")):
            details.append(urljoin(base_url, h))

    # 6) data-ft içi photo_id/story_fbid → detail
    for tag in soup.find_all(attrs={"data-ft": True}):
        dft = tag.get("data-ft") or ""
        try:
            dft = dft.replace("&quot;", "\"")
            m = re.search(r'"photo_id"\s*:\s*"(\d+)"', dft) or re.search(r'"story_fbid"\s*:\s*"(\d+)"', dft)
            if m:
                details.append(f"https://m.facebook.com/photo.php?fbid={m.group(1)}")
        except Exception:
            pass

    details = list(dict.fromkeys(details))
    return list(urls), details, soup

def extract_og_image(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    for m in soup.find_all("meta"):
        prop = (m.get("property") or "").lower()
        if prop in ("og:image","og:image:url","og:image:secure_url"):
            cont = m.get("content")
            if cont:
                u = safe_unwrap(urljoin(base_url, cont))
                if host_ok(u): return u
    for l in soup.find_all("link", rel=True, href=True):
        if "image_src" in (",".join(l.get("rel"))).lower():
            u = safe_unwrap(urljoin(base_url, l["href"]))
            if host_ok(u): return u
    m = re.search(r"https://[A-Za-z0-9_.-]*scontent[^\"'\\s>]+", html)
    if m:
        u = safe_unwrap(urljoin(base_url, _normalize_possible_url(m.group(0))))
        if host_ok(u): return u
    return None

def extract_fbids(html: str):
    fbids = set()
    pats = (
        r"fbid=(\d+)",
        r"photo_fbid=(\d+)",
        r"story_fbid=(\d+)",
        r'"fbid"\s*:\s*"(\d+)"',
        r'"photo_id"\s*:\s*"(\d+)"',
    )
    for pat in pats:
        for m in re.finditer(pat, html):
            fbids.add(m.group(1))
    return list(fbids)

def download(url: str, outdir: str, cookie: str, referer: str | None = None):
    headers = {}
    if referer:
        headers["Referer"] = referer
    r = SESSION.get(url, headers=headers, timeout=25, stream=True, allow_redirects=True)
    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    looks_image = ctype.startswith("image/") or url.lower().split("?")[0].endswith((".jpg",".jpeg",".png",".webp",".gif",".bmp"))
    if not looks_image: return None
    b = r.content
    if len(b) < MIN_BYTES: return None
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    ext = (ctype.split("/", 1)[1] if ("/" in ctype and ctype.startswith("image/")) else
           (os.path.splitext(url.split("?")[0])[1].lstrip(".") or "jpg"))
    fpath = os.path.join(outdir, f"{h}.{ext}")
    with open(fpath, "wb") as f: f.write(b)
    return os.path.basename(fpath)

def resolve_page_id(username: str, cookie: str):
    tries = [
        f"https://www.facebook.com/{username}",
        f"https://m.facebook.com/{username}",
        f"https://mbasic.facebook.com/{username}",
    ]
    pats = [r'"page_id"\s*:\s*"(\d+)"', r'"entity_id"\s*:\s*"(\d+)"', r'fb://page/(\d+)', r'page_id=(\d+)']
    for url in tries:
        try:
            html, final_url = fetch(url, cookie, timeout=20)
            s = BeautifulSoup(html, "html.parser")
            if looks_like_login(html, final_url, s): continue
            for pat in pats:
                m = re.search(pat, html)
                if m: return m.group(1)
        except Exception:
            continue
    return None

def collect(username: str, outdir: str, limit: int = 120):
    os.makedirs(outdir, exist_ok=True)
    cookie = read_cookie()
    seen, saved = set(), []
    snap = {"username": username, "ts": int(time.time()), "seeds": [], "images": []}

    pid = resolve_page_id(username, cookie)
    dyn = []
    if pid:
        dyn = [
            f"https://www.facebook.com/profile.php?id={pid}&sk=photos",
            f"https://www.facebook.com/profile.php?id={pid}&sk=photos_by",
            f"https://m.facebook.com/profile.php?id={pid}&sk=photos",
            f"https://mbasic.facebook.com/profile.php?id={pid}&v=photos",
        ]

    for s in (seeds(username) + dyn):
        try:
            html, final_url = fetch(s, cookie)
            imgs, details, soup = extract_img_urls(html, final_url)
            if looks_like_login(html, final_url, soup):
                snap["seeds"].append({"seed": s, "final": final_url, "login": True})
                continue

            snap["seeds"].append({"seed": s, "final": final_url, "len": len(html), "n_imgs": len(imgs), "n_details": len(details)})

            # FBID -> detail
            for fbid in extract_fbids(html):
                details.append(f"https://m.facebook.com/photo.php?fbid={fbid}")

            # direct imgs
            for u in imgs:
                if u in seen: continue
                seen.add(u)
                fn = download(u, outdir, cookie, referer=final_url)
                if fn:
                    saved.append(fn)
                    snap["images"].append({"url": u, "file": fn, "from": "direct"})
                    if len(saved) >= limit: raise StopIteration

            # detail -> og:image
            for dl in list(dict.fromkeys(details)):
                if len(saved) >= limit: break
                try:
                    h2, u2 = fetch(dl, cookie, timeout=20)
                    s2 = BeautifulSoup(h2, "html.parser")
                    if looks_like_login(h2, u2, s2): continue
                    og = extract_og_image(h2, u2)
                    if og and og not in seen:
                        seen.add(og)
                        fn = download(og, outdir, cookie, referer=u2)
                        if fn:
                            saved.append(fn)
                            snap["images"].append({"url": og, "file": fn, "from": "og"})
                except Exception:
                    continue

            if len(saved) >= limit:
                break
        except StopIteration:
            break
        except Exception:
            continue

    with open(os.path.join(outdir, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    return saved

def main():
    if len(sys.argv) < 3:
        print("Usage: python -m app.tools.fb_dump <username> <outdir> [limit]", file=sys.stderr)
        sys.exit(2)
    username = sys.argv[1]
    outdir = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) >= 4 else 120
    files = collect(username, outdir, limit)
    print(json.dumps({"saved": len(files)}, ensure_ascii=False))

if __name__ == "__main__":
    main()# --- strict host filter for image downloads (avoid favicons) ---
try:
    import os
    from urllib.parse import urlparse
    _orig_download = download
    def download(url, outdir, cookie, referer=None):
        # FB_STRICT_HOSTS=1 ise sadece fbcdn/scontent hostlarından indir
        if os.getenv("FB_STRICT_HOSTS","1") == "1":
            try:
                hn = (urlparse(url).hostname or "").lower()
            except Exception:
                hn = ""
            if ("fbcdn" not in hn) and ("scontent" not in hn):
                return None
        return _orig_download(url, outdir, cookie, referer=referer)
except Exception as _e:
    pass
# --- end strict host patch ---
# --- cookie hard loader (auto) ---
try:
    import os, re
    from urllib.parse import unquote

    def _fb_apply_cookie_file(_path):
        try:
            if not os.path.exists(_path):
                return
            _txt = open(_path, "r", encoding="utf-8", errors="ignore").read().strip()
            jar = {}
            if _txt.startswith("# Netscape") or "\t" in _txt:
                # Netscape TSV
                for ln in _txt.splitlines():
                    ln = ln.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    parts = ln.split("\t")
                    if len(parts) >= 7:
                        name = parts[-2].strip()
                        val  = parts[-1].strip()
                        jar[name] = val
            else:
                # Tek satır: k=v;k=v;...
                for tok in _txt.split(";"):
                    tok = tok.strip()
                    if not tok or "=" not in tok:
                        continue
                    k, v = tok.split("=", 1)
                    jar[k.strip()] = v.strip()
            # Önemli olanları set et
            for k in ("c_user", "xs", "datr", "sb", "locale"):
                if k in jar:
                    SESSION.cookies.set(k, unquote(jar[k]), domain=".facebook.com")
        except Exception as _e:
            print("[cookie-hard-loader:parse]", _e)

    # Yalnızca yoksa yükle
    if not SESSION.cookies.get("c_user"):
        _fb_apply_cookie_file(COOKIE_FILE)
except Exception as _e:
    print("[cookie-hard-loader]", _e)
# --- end cookie hard loader ---
# --- strict fbcdn host gate (auto) ---
try:
    from urllib.parse import urlparse
    _orig_download = download
    def download(url, outdir, cookie, referer=None):
        hn = (urlparse(url).hostname or "").lower()
        if ("fbcdn" not in hn) and ("scontent" not in hn):
            return None
        return _orig_download(url, outdir, cookie, referer=referer)
except Exception as _e:
    print("[strict-host]", _e)
# --- end ---
# --- strict fbcdn host gate (auto) ---
try:
    from urllib.parse import urlparse
    _orig_download = download
    def download(url, outdir, cookie, referer=None):
        hn = (urlparse(url).hostname or "").lower()
        if ("fbcdn" not in hn) and ("scontent" not in hn):
            return None
        return _orig_download(url, outdir, cookie, referer=referer)
except Exception as _e:
    print("[strict-host]", _e)
# --- end ---

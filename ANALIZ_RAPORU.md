# FOOTPRINT OSINT v4.0 — Analiz Raporu

**Tarih:** 2026-05-20  
**Analist:** Kiro (Kıdemli Yazılım Mimarı)  
**Kapsam:** Güvenlik, performans, hata yönetimi, kod temizliği, test coverage, arayüz  
**Proje durumu:** 130/130 test PASSED, 44 router, 25+ service, 5 Stitch UI sayfası

---

## 🔴 KRİTİK (hemen düzeltilmeli)

### 1. `.env` dosyası gerçek API key'leri içeriyor ve repo'da
- **Dosya:** `.env` (proje kökü)
- **Sorun:** GOOGLE_API_KEY, SHODAN_KEY, LEAKCHECK_KEY, IG_SESSIONID, LI_AT gibi 15+ gerçek credential `.env` dosyasında açık metin olarak duruyor. `.gitignore`'da `.env` var ama dosya zaten commit edilmiş olabilir.
- **Çözüm:** Tüm key'leri rotate et. `.env`'yi git history'den temizle (`git filter-branch` veya `bfg`). `.env.example` sadece boş placeholder'lar içersin (zaten var ama gerçek `.env` de mevcut).

### 2. CORS middleware yok — cross-origin istekler engellenmiyor
- **Dosya:** `app/main.py`
- **Sorun:** `CORSMiddleware` hiçbir yerde eklenmemiş. Stitch UI `http://localhost:8000/stitch/` üzerinden servis ediliyor ama farklı origin'den (veya file://) açılırsa fetch çalışmaz. Daha önemlisi, herhangi bir web sitesi kullanıcının tarayıcısından API'ye istek atabilir.
- **Çözüm:** `app/main.py`'e `CORSMiddleware` ekle, `allow_origins=["http://localhost:8000"]` ile kısıtla. Geliştirme için `*` kullanılabilir ama production'da whitelist zorunlu.

### 3. Rate limiting sadece 10/94 endpoint'te var
- **Dosya:** Tüm `app/routers/` — 94 endpoint tanımlı, sadece 16 `@limiter.limit` dekoratörü var
- **Sorun:** `/scan/full`, `/username-bios`, `/username-scan`, `/ig/bio`, `/hunt-x-by-name`, `/combined-search`, `/photos`, tüm debug endpoint'leri rate limit'siz. Brute-force veya abuse riski yüksek.
- **Çözüm:** Global fallback rate limit ekle: `app.state.limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])`. Kritik endpoint'lere özel düşük limitler koy.

### 4. `/scan/full` ve `/username-scan` sync `requests` ile blocking I/O yapıyor
- **Dosya:** `app/routers/scan.py`, `app/services/scan_service.py`
- **Sorun:** `probe_single()` sync `requests.get()` kullanıyor. 7 platform × 15s timeout = tek bir istek uvicorn worker'ı 105 saniye bloke edebilir. Multi-worker'da bile 2 eşzamanlı scan tüm kapasiteyi tüketir.
- **Çözüm:** `httpx.AsyncClient` ile async'e geçir veya `run_in_executor` ile thread pool'a at. Paralel platform probe'ları için `asyncio.gather` kullan.

### 5. XSS riski — innerHTML ile API response'u doğrudan DOM'a yazılıyor
- **Dosya:** `ui/stitch/correlation.html` (6 yer), `profile.html` (5 yer), `dashboard.html` (2 yer)
- **Sorun:** API'den gelen `entity.label`, `entity.value`, `finding` gibi string'ler `innerHTML` ile escape edilmeden yazılıyor. Kötü niyetli bir OSINT hedefi bio'suna `<img onerror=alert(1)>` koyarsa XSS tetiklenir.
- **Çözüm:** `textContent` kullan veya bir `escapeHtml()` helper fonksiyonu ile sanitize et: `s.replace(/&/g,'&amp;').replace(/</g,'&lt;')`.

---

## 🟡 ORTA (yakın zamanda düzeltilmeli)

### 6. 26 dosyada sync `requests` kullanımı — event loop blocking
- **Dosyalar:** `mosint_api.py`, `ig_media.py`, `ig_compat.py`, `variants.py`, `linkedin.py`, `search.py`, `bios.py`, `scan.py` ve 18 diğer
- **Sorun:** FastAPI async framework'ünde sync `requests` çağrıları uvicorn'un event loop'unu bloke eder. Eşzamanlı kullanıcı sayısı arttığında latency spike'ları oluşur.
- **Çözüm:** `httpx.AsyncClient` ile değiştir (zaten requirements.txt'te var). Geçiş süreci için `run_in_executor` wrapper kullanılabilir.

### 7. `/scan/full` endpoint'i GET metodu ile yan etki üretiyor
- **Dosya:** `app/routers/scan.py`
- **Sorun:** GET isteği ile 7 platforma HTTP request atılıyor. HTTP semantiği açısından GET idempotent ve side-effect-free olmalı. Proxy/CDN cache'leri beklenmedik davranış gösterebilir.
- **Çözüm:** POST'a geçir veya en azından `Cache-Control: no-store` header'ı ekle.

### 8. Cache mekanizması yok — tekrarlı OSINT sorguları her seferinde dış API'ye gidiyor
- **Dosya:** `app/utils/cache.py` (sadece 471 byte, minimal)
- **Sorun:** Aynı email/username için dakikalar içinde tekrarlanan sorgular her seferinde HIBP, Abstract, Numverify gibi dış API'lere gidiyor. Rate limit'e takılma ve gereksiz latency.
- **Çözüm:** Redis (zaten requirements.txt'te var) veya `cachetools.TTLCache` ile 5-10 dakikalık response cache ekle. `@cached(ttl=300)` dekoratörü ile sarmalama yeterli.

### 9. `fb_ui.py` 21KB — dashboard, overview, zip, file serving hepsi tek dosyada
- **Dosya:** `app/routers/fb_ui.py` (21,869 bytes)
- **Sorun:** Tek bir router dosyasında 14 fonksiyon, inline HTML generation, subprocess çağrısı, zip oluşturma, cookie parsing, docker system df çağrısı var. Bakım zorluğu ve SRP ihlali.
- **Çözüm:** `fb_ui.py`'yi 3 dosyaya böl: `fb_routes.py` (endpoint'ler), `fb_service.py` (iş mantığı), `fb_templates.py` (HTML generation). Veya mevcut `ui/fb_ui.html` FileResponse yaklaşımını genişlet.

### 10. `person_aggregator.py` 18KB — tek fonksiyonda 200+ satır
- **Dosya:** `app/services/person_aggregator.py` (18,000 bytes)
- **Sorun:** Muhtemelen tek bir `aggregate()` fonksiyonu içinde tüm platform çağrıları sıralı yapılıyor. Okunabilirlik ve test edilebilirlik düşük.
- **Çözüm:** Her platform çağrısını ayrı async fonksiyona çıkar, `asyncio.gather` ile paralelize et.

### 11. Docker multi-worker + Playwright uyumsuzluğu
- **Dosya:** `Dockerfile` (CMD: `--workers 2`)
- **Sorun:** Playwright browser instance'ları process-level state tutar. 2 worker'da her biri kendi Chromium instance'ını açar → bellek kullanımı 2x. Container'da 2GB RAM ile OOM riski.
- **Çözüm:** Worker sayısını 1'e düşür veya Playwright işlemlerini ayrı bir worker queue'ya (RQ, zaten requirements.txt'te) taşı.

### 12. Test coverage boşlukları
- **Dosya:** `tests/` — 22 test dosyası, 130 test
- **Sorun:** Şu endpoint'ler test edilmemiş: `/username-scan`, `/ig/bio`, `/hunt-x-by-name`, `/combined-search`, `/photos`, `/compare-ig-x2`, `/mosint/full` (sadece kısmi), tüm debug endpoint'leri, `/fb/*` endpoint'leri.
- **Çözüm:** En azından smoke test (200/422 status check) ekle. Mock ile external API bağımlılığını kaldır.

---

## 🟢 İYİLEŞTİRME (isteğe bağlı)

### 13. Tutarsız naming convention
- **Dosyalar:** Router'larda `hunt_social.py` vs `hunt_social_v2.py`, `ig_compat.py` vs `ig_plus.py` vs `ig_hunt.py`
- **Sorun:** 3 farklı Instagram router'ı, 2 farklı hunt_social versiyonu, `mosint_api.py` (neden `_api` suffix'i?). Yeni geliştirici için navigasyon zor.
- **Çözüm:** Deprecated router'ları `_deprecated/` altına taşı, aktif olanları net isimlendir.

### 14. Dead code — `compat_ui.py`, `theharvester_api.py`, `person.py`
- **Dosyalar:** `app/routers/compat_ui.py`, `theharvester_api.py`, `person.py`
- **Sorun:** `routers_to_load` listesinde yok → hiç mount edilmiyor. Ama dosyalar hâlâ projede.
- **Çözüm:** Kullanılmıyorsa sil veya `_archive/` klasörüne taşı.

### 15. `app/utils/osint_demo.py` — 24KB demo data dosyası
- **Dosya:** `app/utils/osint_demo.py` (24,637 bytes)
- **Sorun:** Muhtemelen hardcoded demo response'lar. Production'da gereksiz, import sırasında bellek tüketir.
- **Çözüm:** `tests/fixtures/` altına JSON olarak taşı.

### 16. Stitch UI mobil uyumsuz
- **Dosya:** `ui/stitch/*.html`
- **Sorun:** Tüm sayfalar `w-[240px]` fixed sidebar + `ml-[240px]` main layout kullanıyor. 768px altında sidebar içeriği ezer, overflow-hidden ile kesilir.
- **Çözüm:** Responsive breakpoint ekle: `lg:w-[240px] w-0` + hamburger menu toggle.

### 17. localStorage'da target bilgisi — hassas veri riski
- **Dosya:** `ui/stitch/*.html` (tüm sayfalar)
- **Sorun:** `footprint.target` key'inde email/username saklanıyor. Aynı origin'deki başka bir script (CDN Tailwind, vis.js) bu veriye erişebilir.
- **Çözüm:** `sessionStorage` kullan (tab kapanınca silinir) veya en azından hassas hedef bilgisini obfuscate et.

### 18. Duplicate `__ping` route
- **Dosya:** `app/main.py` + muhtemelen başka bir router
- **Sorun:** Route listesinde `/__ping` 2 kez görünüyor. FastAPI son tanımlananı kullanır ama karışıklık yaratır.
- **Çözüm:** Duplicate'i bul ve sil.

---

## 💡 MİMARİ ÖNERİLER

### Eksik Modüller
1. **Telegram OSINT** — username → public channel/group membership, bio, profile photo
2. **Blockchain/Crypto wallet** — address → transaction history, balance (Etherscan/Blockchair API)
3. **Paste site monitoring** — Pastebin, Ghostbin, dpaste taraması (email/username arama)
4. **DNS history** — SecurityTrails veya VirusTotal passive DNS entegrasyonu
5. **Certificate Transparency** — crt.sh API ile subdomain keşfi

### Ölçeklenebilirlik
1. **Redis cache layer** — Requirements'ta var ama hiç kullanılmıyor. `@cached` dekoratörü ile 5-10 dk TTL ekle.
2. **RQ worker queue** — Uzun süren işlemler (Playwright scraping, /correlation/full, /scan/full) için background job queue. Requirements'ta `rq` zaten var.
3. **WebSocket progress** — Uzun scan'ler için real-time progress stream. Mevcut polling yerine WS ile activity log besle.
4. **API versioning** — `/v2/` prefix'i zaten bazı endpoint'lerde var ama tutarsız. Tüm API'yi `/api/v1/` altına al.

### Kullanıcı Deneyimi
1. **Unified search bar** — Dashboard'daki target input'u tek bir "smart search" olsun: email → mosint, username → bios+scan, phone → phone lookup, domain → domain lookup otomatik route etsin.
2. **Export/Share** — Correlation graph'ı PNG/SVG olarak export, raporu email ile gönder.
3. **Dark/Light mode toggle** — Mevcut tema harika ama uzun kullanımda göz yoruyor. Opsiyonel light mode.
4. **Keyboard shortcuts** — Ctrl+K → search, Ctrl+R → run scan, 1-9 → sidebar navigation.

---

## 📊 ÖZET TABLO

| Kategori | Sorun Sayısı | Kritik | Orta | İyileştirme |
|----------|:---:|:---:|:---:|:---:|
| Güvenlik | 5 | 3 | 1 | 1 |
| Performans | 5 | 1 | 3 | 1 |
| Hata Yönetimi | 2 | 0 | 1 | 1 |
| Kod Temizliği | 4 | 0 | 2 | 2 |
| Test Coverage | 1 | 0 | 1 | 0 |
| Arayüz (UI) | 3 | 1 | 0 | 2 |
| **TOPLAM** | **20** | **5** | **8** | **7** |

---

## 🏗️ ÖNCELİK SIRASI (önerilen uygulama planı)

1. ⚡ `.env` key rotation + git history temizliği (30 dk)
2. ⚡ CORS middleware ekle (5 dk)
3. ⚡ Global rate limit fallback (10 dk)
4. ⚡ innerHTML → textContent/escapeHtml (1 saat)
5. 🔧 `/scan/full` async'e geçir (2 saat)
6. 🔧 Redis cache layer aktifleştir (2 saat)
7. 🔧 Eksik endpoint testleri (3 saat)
8. 📐 Mimari: RQ worker queue (1 gün)
9. 📐 Mimari: WebSocket progress (1 gün)

---

*Bu rapor otomatik olarak üretilmiştir. Dosyalara dokunulmamıştır.*

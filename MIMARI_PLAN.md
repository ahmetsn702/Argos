# FOOTPRINT OSINT v4.0 — Mimari Refactor Planı

**Hedef Mimari:** Layered Architecture + Repository Pattern  
**Mevcut durum:** 130/130 test PASSED · 44 router · 25 service · 26 dosyada sync `requests`  
**Hedef:** Aynı endpoint`ler, aynı testler, daha temiz katmanlama

---

## Genel Stratejik İlkeler

1. **Strangler Fig pattern** — Eski kodu silmeden yenisini yan yana inşa et, son adımda eski`yi kaldır.
2. **Her PR`da test sayısı azalmamalı** — Refactor`dan önce mevcut davranış için karakteristik testi yaz, sonra değiştir.
3. **Geriye dönük uyumluluk** — Endpoint URL`leri, query param`ları, response şemaları aynı kalmalı.
4. **Faz bağımsızlığı** — Her faz kendi başına merge edilebilir, geri alınabilir olmalı.
5. **Ölçülebilir başarı** — Her faz "X test, Y endpoint, Z ms latency" gibi somut kriterlerle bitmeli.

---

## FAZ 1 — Temel Altyapı (Models + Repository Base)

**Tahmini süre:** 6-8 saat  
**Risk seviyesi:** Düşük (yeni dosya ekleme, mevcut kodu değiştirmiyor)  
**Bağımlılık:** Yok

### Hedef
`app/models/` ve `app/repositories/` klasörlerini oluştur. Base class`ları yaz. Mevcut Pydantic modelleri merkezi konuma taşı.

### Adımlar (sıralı)

**1.1. Yeni klasör yapısı oluştur**
- `app/models/__init__.py` — yeni
- `app/repositories/__init__.py` — yeni
- `app/repositories/base.py` — yeni

**1.2. `app/repositories/base.py` — async HTTP base class**
- `BaseRepository` sınıfı: `httpx.AsyncClient` instance, retry decorator (tenacity opsiyonel), timeout, default headers, error handling.
- Metodlar: `_get(url, **kwargs)`, `_post(url, **kwargs)`, `_handle_response(resp)` (status code → exception eşlemesi).
- `RepositoryError`, `RepositoryTimeout`, `RepositoryRateLimited` özel exception`ları.
- Test: `tests/test_base_repository.py` — mock `httpx` ile happy path + 5xx + timeout + rate limit senaryoları.

**1.3. `app/services/base.py` — base service**
- `BaseService` opsiyonel ABC. Cache helper`ı (TTL, get/set), logging context, repository injection pattern.
- Test gereksiz (sadece interface).

**1.4. Pydantic modelleri merkezi konuma taşı**
- `app/models/identity.py` ← `correlation/models.py`'deki 23 model (yeni klasör değil, mevcut yapı zaten iyi — sadece import path`leri normalleştir).
- `app/models/composer.py` ← `routers/composer.py`'den 7 BaseModel
- `app/models/person.py` ← `services/person_aggregator.py`'den 5 BaseModel
- `app/models/geo.py` ← `routers/geo_photo.py`'den `GeoResult`
- `app/models/llm.py` ← `routers/llm_analysis.py`'den `OsintAnalysisRequest`
- Backward-compat: eski lokasyondan re-export kalsın.
- Test: tüm mevcut testler import path`lerini korumalı.

**1.5. `app/core/cache.py` — Redis-backed TTL cache**
- `app/utils/cache.py` (471 byte minimal) yerine production-ready cache.
- `cachetools.TTLCache` fallback + Redis (varsa).
- Dekoratör: `@cached(ttl=300, key_func=...)`.
- Test: `tests/test_cache.py` — TTL expiry, hit/miss, fallback davranışı.

### Riskler
- Pydantic model import yolları değişirse 30+ test kırılabilir. **Çözüm:** Eski dosyalarda re-export bırak.
- `tenacity` yeni dependency. **Çözüm:** Stdlib ile manuel retry yaz.

### Başarı kriteri
- `pytest --tb=short -q` → **130 passed** (değişmedi)
- `app/models/` ve `app/repositories/` klasörleri mevcut
- `BaseRepository` ve `BaseService` test edilmiş (5+ yeni test → 135 toplam)

---

## FAZ 2 — Async Geçiş (Sync requests → httpx.AsyncClient)

**Tahmini süre:** 16-20 saat (en uzun faz)  
**Risk seviyesi:** Yüksek (event loop + retry semantiği, Playwright çakışması)  
**Bağımlılık:** Faz 1 (BaseRepository hazır olmalı)

### Hedef
26 dosyada sync `requests` kullanımını async `httpx.AsyncClient`'e çevir. `/scan/full` ve benzeri sync endpoint`leri async`e taşı, paralel platform probe`ları için `asyncio.gather` kullan.

### Bağımlılık Haritası

**Düşük bağımlılık (önce):**
- `utils/ig_utils.py`, `services/youtube_service.py`, `services/reddit_service.py`,
  `services/github_service.py`, `services/x_photos.py`, `services/ig_photos.py`

**Orta bağımlılık:**
- `services/scan_service.py`, `services/x_fetch.py`, `services/instagram_service.py`,
  `services/fb_service.py`, `services/fb_photos.py`, `services/media_search_service.py`,
  `services/ig_profile.py`, `services/ai_service.py`

**Yüksek bağımlılık (sonra):**
- `services/ig_media.py` (6 yer), `services/person_aggregator.py`
- `routers/scan.py`, `routers/bios.py`, `routers/linkedin.py`, `routers/search.py`
- `routers/mosint_api.py` (8 yer), `routers/ig_compat.py` (3), `routers/variants.py` (3)

### Adımlar (sıralı)

**2.1. Karakteristik test yazısı**
- Her async`e geçirilecek service için "şu input verilince şu output döner" şeklinde mock-based test.
- Davranışı dondur. Refactor sırasında testler aynı şekilde geçmeli.
- ~15 yeni test → toplam ~145.

**2.2. Düşük bağımlılık servisleri (paralel uygulanabilir)**
- 6 dosyada minimal değişiklik: `requests` → `httpx`. Her birinde 1 çağrı.

**2.3. `services/scan_service.py` — paralelize et**
- Mevcut: 7 platform sıralı sync `probe_single` çağrısı, ~7×timeout = 105s worst case.
- Hedef: `async def probe_single` + `asyncio.gather` ile 7 platform paralel = ~timeout (15s) worst case.
- Router `routers/scan.py` async`e geçirilmeli.

**2.4. `services/instagram_service.py`, `ig_profile.py`, `ig_media.py`**
- 3 dosyada toplam 10+ sync requests.
- Repository pattern ile `app/repositories/instagram_repo.py` taşı.
- `IG_SESSIONID` cookie management async client`a taşı.

**2.5. `routers/mosint_api.py` — async**
- 8 sync requests çağrısı (Hunter, EmailRep, HIBP, Abstract).
- Her dış API için kısa metodlar.
- `asyncio.gather(return_exceptions=True)` ile fault-tolerant paralel çağrı.

**2.6. `routers/scan.py`, `routers/bios.py`, `routers/linkedin.py`, `routers/search.py`**
- Sync def → async def.
- `requests.Session()` → `httpx.AsyncClient()` context manager.

**2.7. `services/person_aggregator.py` — async + paralel**
- 18KB monolit, sıralı çağrılar.
- Her platform çağrısını ayrı async metoda çıkar, `gather` ile paralelle.

### Riskler
- **Playwright + httpx çakışması:** Async context`te yanlış kullanım deadlock yaratabilir. **Çözüm:** Playwright çağrılarını `run_in_executor` ile sync olarak çağır.
- **`requests.Session()` cookie state:** Async geçişte cookie`ler kaybolabilir. **Çözüm:** `httpx.AsyncClient(cookies=...)` ile context-bound session.
- **Rate limit timing:** Paralel çağrılar dış API rate limit`ini hızlı tüketir. **Çözüm:** Service-level semaphore (`asyncio.Semaphore(3)`).
- **Test instability:** Async test`ler `pytest-asyncio` gerektirir.

### Başarı kriteri
- 26 dosyada `import requests` → `import httpx`
- `pytest -q` → **145+ passed**
- `/scan/full` latency %50+ azalmalı (paralel platform probe`ları)
- Locust/k6 ile basit yük testi: 10 eşzamanlı `/scan/full` → tüm istekler timeout`a takılmadan tamamlanmalı

---

## FAZ 3 — Instagram Konsolidasyonu

**Tahmini süre:** 8-10 saat  
**Risk seviyesi:** Orta (5 router birleştiriliyor, endpoint çakışmaları var)  
**Bağımlılık:** Faz 2

### Hedef
5 farklı Instagram router`ını tek `app/routers/instagram.py` dosyasında birleştir.

### Mevcut Durum Analizi

| Endpoint | Router | Durum |
|----------|--------|-------|
| `GET /ig/bio` | `ig_compat.py` | Stitch UI kullanıyor |
| `GET /ig-profile` | `hunt_social.py` + `hunt_social_v2.py` | ÇAKIŞMA — son yüklenen kazanıyor |
| `GET /ig-profile-v1` | `ig_hunt.py` | Legacy |
| `GET /v2/ig-profile` | `hunt_social_v2.py` | Aktif |
| `GET /hunt-ig-by-name` | `hunt_social.py` | Aktif |
| `GET /v2/hunt-ig-by-name` | `hunt_social.py` | Aktif |
| `GET /_old/hunt-ig-by-name` | `hunt_social_v2.py` + `ig_hunt.py` | ÇAKIŞMA |
| `POST /ig-media`, `/ig-media-lite`, `/ig-media-zip5` | `ig_plus.py` | Aktif |
| `POST /compare-ig-x-plus` | `ig_plus.py` | Aktif |
| `GET /ig-bio-ui` | `ig_plus.py` | UI route, taşınmalı |

**Tespit edilen ÇAKIŞMALAR:** `/ig-profile` ve `/_old/hunt-ig-by-name` 2 farklı router`da tanımlı. FastAPI son include edilen route`u kullanır → davranış routers_to_load sırasına bağlı, bug riski.

### Adımlar (sıralı)

**3.1. Endpoint envanteri ve davranış dondurma**
- Her IG endpoint için "şu input → şu shape response" testi yaz (mock`la).
- Çakışan endpoint`lerin hangi davranışı koruduğunu netleştir.
- ~10 yeni karakteristik test → toplam ~155.

**3.2. `app/repositories/instagram_repo.py` — yeni**
- Tüm IG dış API çağrıları (web scraping, GraphQL, mobile API, Playwright).
- Metodlar: `fetch_profile_html(username)`, `fetch_via_graphql(username)`, `fetch_via_playwright(username)`, `fetch_media(username, limit)`, `search_by_name(name)`.

**3.3. `app/services/instagram_service.py` — genişlet**
- Mevcut dosya 5KB, çok dar.
- Service metodları: `get_bio(username)`, `get_profile(username)`, `get_media(username, limit)`, `search(query)`.
- Her metod repository`i çağırır, fallback chain`i (web → graphql → playwright) burada kararlaştırılır.
- Cache layer: `@cached(ttl=300, key=username)`.

**3.4. `app/routers/instagram.py` — yeni, birleştirilmiş router**
- Tüm IG endpoint`leri tek dosyada.
- Sadece HTTP katmanı: input parse, service çağrısı, response.
- Rate limit dekoratörleri.
- ~10 endpoint, ~150 satır hedef (mevcut 5 dosya toplam ~30KB).

**3.5. Eski router`ları kaldır**
- `routers_to_load` listesinden çıkar: `ig_compat`, `ig_plus`, `ig_hunt`, `hunt_social`, `hunt_social_v2`.
- Listeye ekle: `instagram`.
- Dosyaları sil veya `app/routers/_archive/` altına taşı.

**3.6. UI/template ayrılması**
- `ig_plus.py`'deki `/ig-bio-ui` HTML üretimi → `ui/` veya `app/templates/`.

### Riskler
- **Çakışan endpoint davranış kaybı:** Faz 3.1`de davranışı testle dondur.
- **Cookie/auth state:** 5 router farklı şekilde IG_SESSIONID kullanıyor olabilir. Repository`de tek noktadan yönet.
- **Playwright tek instance:** Race condition riski. `app/utils/pw_safe.py`'i tek browser pool ile genişlet.

### Başarı kriteri
- `pytest -q` → **155+ passed**
- `/__routes` çıktısında IG endpoint sayısı aynı (10 endpoint)
- Stitch UI`da `/profile.html` IG bilgisi getirebiliyor
- Eski 5 router dosyası silinmiş
- Toplam IG kodu ≤ 12KB (mevcut ~30KB`tan %60 azalma)

---

## FAZ 4 — fb_ui.py Refactor

**Tahmini süre:** 4-6 saat  
**Risk seviyesi:** Düşük  
**Bağımlılık:** Faz 1

### Hedef
21KB monoliti 4 dosyaya böl: router (HTTP), service (subprocess + zip), template (HTML), repository (cookie parsing).

### Mevcut Durum Analizi
`fb_ui.py` içinde:
- 3 farklı runtime constants block (FB_ROOT, FB_CWD, FB_PY) — duplicate
- 14 endpoint
- Inline HTML generation (`_html_page()` 250+ satır)
- Subprocess çağrıları (`app.tools.fb_dump`)
- Zip oluşturma (`zipfile.ZipFile`)
- Cookie parsing (`_cookie_summary()`)
- Docker `system df` çağrısı

### Adımlar (sıralı)

**4.1. Karakteristik test**
- `tests/test_fb_ui.py` yeni — `/fb`, `/fb/overview`, `/dashboard` endpoint`leri için smoke test.

**4.2. `app/repositories/fb_repo.py` — yeni**
- Cookie parsing (Netscape/JSON formatları), masking.
- File system erişimi (`_outdir`, `_safe_dir`, `_images_under`).

**4.3. `app/services/fb_dump_service.py` — yeni**
- Subprocess wrapper: `run_dump(username, limit, min_bytes, debug)`.
- Zip oluşturma: `build_zip(outdir) → bytes`.
- Snapshot okuma/doğrulama.

**4.4. `app/templates/fb_templates.py` — yeni**
- `_html_page()` ve `/fb/overview`, `/dashboard` HTML üretimi buraya.
- Veya daha iyisi: HTML`leri `ui/fb/*.html` statik dosyalarına taşı.

**4.5. `app/routers/fb_ui.py` — incelt**
- Sadece HTTP routing kalsın (~150 satır, mevcut 21KB → 4-5KB).

**4.6. Duplicate kodu temizle**
- 3 yerde tanımlı `FB_ROOT`/`FB_CWD`/`FB_PY` constants → tek yerden import.
- 2 yerde tanımlı `fb_zip` endpoint duplicate → tek tanım.

### Riskler
- **Subprocess timeout:** 5 dakikalık timeout`la çalışıyor, async router`da blocking. **Çözüm:** `asyncio.create_subprocess_exec` veya RQ background job.
- **Local-only `/dashboard` kontrolü:** IP whitelist mantığı router`da kalmalı.

### Başarı kriteri
- `pytest -q` → **160+ passed**
- `routers/fb_ui.py` ≤ 6KB (mevcut 21KB)
- `/fb/*` endpoint`lerin tümü çalışıyor
- Inline HTML kalmadı

---

## FAZ 5 — Dead Code Temizliği

**Tahmini süre:** 2-3 saat  
**Risk seviyesi:** Düşük  
**Bağımlılık:** Faz 3 ve Faz 4

### Hedef
Mount edilmeyen router`ları, kullanılmayan service`leri, ölü importları kaldır.

### Adımlar (sıralı)

**5.1. Router temizliği**
- `routers_to_load` listesinde olmayanları sil:
  - `app/routers/compat_ui.py`
  - `app/routers/theharvester_api.py`
  - `app/routers/person.py`
  - `app/routers/hibp.py` — kullanılıyor mu kontrol et

**5.2. Service temizliği**
- Hangi service hangi router tarafından import ediliyor? grep ile tara.

**5.3. `app/utils/osint_demo.py` (24KB) — taşı veya sil**
- Hardcoded demo response varsa `tests/fixtures/osint_samples.json` olarak ayır.

**5.4. UI dead files**
- `ui/dashboard.html`, `ui/correlation.html`, `ui/graph.html` — eski Stitch çıktıları, `ui/stitch/` yerine geçti.
- `stitch_*.html` proje kökünde 4 adet, ~80KB.

**5.5. Duplicate Pydantic re-export`larını kaldır**
- Faz 1`de bırakılan backward-compat import`ları kaldır.

**5.6. Unused imports**
- `ruff check --select=F401` ile tara.

### Riskler
- **Gizli dependency:** Test veya deployment script`i silinen dosyaya import yapıyor olabilir. **Çözüm:** Silmeden önce `grep -r` ile referans kontrolü.

### Başarı kriteri
- `pytest -q` → **160+ passed**
- Proje boyutu %15-20 azalmış
- `ruff check` → 0 unused import warning

---

## FAZ 6 — Test Coverage Genişletme

**Tahmini süre:** 12-16 saat  
**Risk seviyesi:** Düşük  
**Bağımlılık:** Faz 5

### Hedef
Repository unit test`leri, service integration test`leri, eksik endpoint smoke test`leri.

### Adımlar (sıralı)

**6.1. Repository unit testleri**
- Her `app/repositories/*.py` için: `tests/repositories/test_<name>_repo.py`.
- Mock `httpx` (`respx` kütüphanesi) ile.
- Senaryolar: 200 success, 4xx client error, 5xx server error, timeout, retry.
- ~25 yeni test (5 repo × 5 senaryo).

**6.2. Service integration testleri**
- Her service için repository mock`lanmış test.
- Cache hit/miss, fallback chain, error propagation.
- ~20 yeni test.

**6.3. Eksik endpoint smoke testleri**
- `/username-scan`, `/ig/bio`, `/ig-profile`, `/ig-media`, `/hunt-x-by-name`, `/combined-search`, `/photos`, `/compare-ig-x2`, `/fb/*`, `/debug/*`.
- Her endpoint için minimal: 200/422 status, response key kontrolü.
- ~30 yeni test.

**6.4. End-to-end testler**
- `/scan/full` → tüm modüllerin döndüğü senaryo.
- `/correlation/full` → tüm fan-out senaryosu.
- LLM analyst → mock`lı.
- ~10 yeni test.

**6.5. Performance testler (opsiyonel)**
- `pytest-benchmark` ile kritik endpoint`lerde latency baseline.
- `/scan/full` < 5s, `/correlation/full` < 8s, `/analysis/osint` < 6s.

### Riskler
- **Test bağımlılığı:** External API mock`suz test eklenirse CI`da kırılır. **Çözüm:** `respx` veya `pytest-httpx` ile tüm dış istekleri mock`la.

### Başarı kriteri
- `pytest -q` → **220+ passed**
- Coverage report (pytest-cov) → %75+ statement coverage
- Tüm yeni testler `< 30s` toplam sürede tamamlanmalı

---

## Faz Özeti Tablosu

| Faz | Süre | Risk | Test Δ | Endpoint Δ | Code Δ | Bağımlılık |
|-----|:---:|:---:|:---:|:---:|:---:|:---:|
| 1. Altyapı | 6-8h | Düşük | +5 | 0 | +files | Yok |
| 2. Async geçiş | 16-20h | Yüksek | +15 | 0 | ~26 file | F1 |
| 3. IG konsolidasyonu | 8-10h | Orta | +10 | 0 | -25KB | F2 |
| 4. fb_ui refactor | 4-6h | Düşük | +5 | 0 | -16KB | F1 |
| 5. Dead code | 2-3h | Düşük | 0 | 0 | -50KB | F3, F4 |
| 6. Test coverage | 12-16h | Düşük | +90 | 0 | +tests | F5 |
| **TOPLAM** | **48-63h** | — | **+125** | **0** | **-90KB net** | — |

---

## Yol Haritası (kalendar bazlı)

**Hafta 1 (15-20h):** Faz 1 + Faz 2 (düşük bağımlılık servisleri)  
**Hafta 2 (15-20h):** Faz 2 devam → 145 test PASSED  
**Hafta 3 (10-14h):** Faz 3 (IG) + Faz 4 (fb_ui)  
**Hafta 4 (8-12h):** Faz 5 + Faz 6 başlangıç  
**Hafta 5 (10-15h):** Faz 6 final + benchmark

---

## Genel Riskler ve Mitigasyon

| Risk | Olasılık | Etki | Mitigasyon |
|------|:---:|:---:|---|
| Stitch UI`nın bozulması | Orta | Yüksek | Her faz sonu manuel UI testi (5 sayfa açılış + 1 işlem) |
| Test sayısının azalması | Düşük | Yüksek | `pytest --co` ile test sayımı doğrulanır, azalma → CI red |
| Endpoint URL değişikliği | Düşük | Çok Yüksek | `/__routes` snapshot karşılaştırması |
| Docker deployment kırılması | Düşük | Yüksek | `docker-compose up` smoke test, `/__ping` 200 |
| Async migration regresyon | Yüksek | Orta | Karakteristik testler, async wrapper deneme zincirleri |
| External API rate limit`e takılma | Orta | Düşük | `respx` mock zorunlu |

---

## Tüm Refactor`ın Final Başarı Kriterleri

- `pytest --tb=short -q` → **220+ passed, 0 failed, 0 skipped**
- `/__routes` çıktısındaki endpoint sayısı **mevcut + 0** (azalmamalı, artmamalı)
- Stitch UI`daki 5 sayfa hatasız çalışıyor
- `docker-compose up` → container 30 saniye içinde sağlıklı (`/__ping` 200)
- Toplam Python kod boyutu **%20 azalmış** (~90KB net düşüş)
- Tüm sync `requests` çağrıları async olmuş
- `app/repositories/` ve `app/models/` klasörleri kullanımda
- Coverage rapor → **%75+ statement coverage**
- En az **1 production-grade README/CONTRIBUTING.md** mimari dokümantasyonu

---

## Plana Dahil Olmayan Şeyler (Sonraki Sprint`ler)

- **CORS middleware ekleme** (Analiz Raporu kritik #2 — bu plan başlamadan önce hızlıca yapılmalı)
- **`.env` key rotation** (Analiz Raporu kritik #1 — derhal, refactor`la ilgisiz)
- **Yeni OSINT modülleri** (Telegram, blockchain, paste sites)
- **WebSocket progress** (yeni feature, refactor`dan sonra)
- **API versioning (`/api/v1/`)** (breaking change, ayrı planlanmalı)
- **Light/dark mode toggle** (UI feature)

---

*Bu plan dosyalara dokunmadan üretilmiştir. Uygulanmadan önce maintainer review`ı önerilir.*

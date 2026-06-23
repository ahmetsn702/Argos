# ARGOS — Proje Analizi

_Tarih: 24 Mayıs 2026_

---

## 1. Genel Bakış

**ARGOS**, FastAPI tabanlı bir OSINT (Açık Kaynak İstihbarat) platformudur. Versiyon 4.0 olarak etiketlenmiş olmakla birlikte, kod tabanında v5 katmanları da (Agent, Watchlist, Graph DB, Temporal, Confidence) aktif olarak mevcuttur. Yerel çalışmak üzere tasarlanmış; Docker opsiyonel, ana akış `venv_fresh` + `uvicorn` üzerinden.

**Giriş noktası:** `app/main.py` → `http://localhost:8000`

---

## 2. Mimari

```
HTTP İsteği
    ↓
FastAPI (main.py)
    ↓
CORSMiddleware + APIVersionMiddleware + RateLimiter (slowapi)
    ↓
Router (app/routers/*.py)          ← ~45 adet router
    ↓
Service (app/services/*.py)        ← iş mantığı
    ↓
Repository (app/repositories/*.py) ← SQLite / Neo4j / Memory
    ↓
Veri Kaynakları (dış API, Playwright scraping, yerel model)
```

### Katmanlar

| Katman | Konum | Açıklama |
|--------|-------|----------|
| Core | `app/core/` | config (pydantic-settings), cache, rate-limiter, feature flags |
| Routers | `app/routers/` | HTTP endpoint tanımları, ~45 dosya |
| Services | `app/services/` | İş mantığı; düz servisler + 7 alt modül |
| Models | `app/models/` | Pydantic veri modelleri |
| Repositories | `app/repositories/` | Veri erişim katmanı (SQLite watchlist, Neo4j graf) |
| Utils | `app/utils/` | Yardımcı fonksiyonlar (Playwright patch, IG helpers, solar math) |
| AI | `app/ai/` | Yerel Gemma 3 270M modeli (opsiyonel) |
| UI | `ui/` | Statik HTML/JS dosyaları |

---

## 3. Modüller ve İşlevleri

### 3.1 Temel OSINT Servisleri

| Servis | Dosya | Ne Yapar |
|--------|-------|----------|
| Email OSINT | `routers/mosint_api.py` + `hibp_service.py` | HIBP breach sorgusu, e-posta doğrulama |
| Username Search | `routers/bios.py` + `routers/hunt_social_v2.py` | Sosyal medya kullanıcı adı taraması |
| Instagram | `services/instagram_service.py` + `ig_media.py` + `ig_profile.py` | Profil scraping, medya, Playwright |
| Facebook | `services/fb_service.py` + `fb_photos.py` + `fb_dump_service.py` | FB profil/fotoğraf dump |
| LinkedIn | `services/linkedin_service.py` | Profil çekme (cookie tabanlı) |
| Phone | `services/phone_service.py` | Numverify/Veriphone API |
| Domain | `services/domain_service.py` | WHOIS, DNS, Shodan |
| Dark Web | `services/darkweb_service.py` | Leak check API |
| Geo/Foto | `services/geo_service.py` + `geo_comparison.py` | EXIF analizi, Google/Yandex coğrafi arama |
| Yüz Tanıma | `services/face_service.py` | face_recognition (dlib) → Yandex fallback → Gemini Vision |
| Yandex Search | `services/yandex_search.py` + `_yandex_parser.py` | Playwright ile Yandex görsel arama |

### 3.2 Analitik Katmanlar (v5)

| Modül | Konum | İşlev |
|-------|-------|-------|
| Correlation Engine | `services/correlation/` | Çapraz kaynak korelasyonu; coğrafi cluster, temporal, risk skoru, entity resolver, graf builder |
| Confidence System | `services/confidence/` | Güven skoru grafiği; ağırlıklar, normalizasyon, çelişki tespiti, cache |
| Temporal Analysis | `services/temporal/` | Zaman serisi çıkarımı, anomali tespiti, kümeleme, narratör |
| Pivot Engine | `services/pivot/` | OSINT pivotlama; strategy map, executor, session store |
| Graph DB | `services/graph_db/` | Neo4j entegrasyonu; ETL, Cypher guard, shadow reader (dual-write) |

### 3.3 Otomasyon Katmanları (v5)

| Modül | Konum | İşlev |
|-------|-------|-------|
| Agent Loop | `services/agent/loop.py` | Özerk soruşturma döngüsü; tool registry, budget enforcer, audit log |
| Playbook | `services/agent/playbook/` | Önceden tanımlı OSINT iş akışları |
| RAG | `services/agent/rag/` | ChromaDB tabanlı retrieval-augmented generation |
| Watchlist | `services/watchlist/` | Hedef izleme; diff engine, archiver, scheduler, notifiers |
| Storage | `services/storage/` | Pluggable storage; local FS veya S3 |
| Maltego | `services/maltego/` | Maltego transform desteği; .mtgx export |

### 3.4 AI / LLM

| Bileşen | Detay |
|---------|-------|
| Yerel Gemma 3 270M | `app/models/gemma3_270m_it/` (~500MB safetensors), `app/ai/gemma_local.py` |
| Ollama Bridge | `app/core/config.py` → `OLLAMA_API_URL`, `OLLAMA_MODEL=phi3:mini` |
| OpenCode Bridge | `services/opencode_bridge.py` → localhost:4096 HTTP API |
| LLM Analyst | `services/llm_analyst.py` → `routers/llm_analysis.py` |

---

## 4. UI Katmanı

| Dosya | Açıklama |
|-------|----------|
| `ui/index.html` | Ana OSINT arayüzü (~24KB) |
| `ui/mini_panel.html` | Kompakt uzman paneli (~76KB, en aktif) |
| `ui/stitch/` | Stitch tarafından üretilmiş component'ler (dashboard, watchlist, correlation, profile, report, llm_analysis, ask_argos) |
| `ui/geo_photo.html` | Fotoğraf coğrafi analiz UI |
| `ui/fb_dashboard.html` / `fb_overview.html` | Facebook özel UI |
| `app/static/tester/ui.html` | API tester UI |

Mount noktaları: `/ui`, `/stitch`, `/static` (NoCacheStaticFiles ile cache kapalı).

---

## 5. Konfigürasyon

Tüm ayarlar `.env` dosyasından `pydantic-settings` ile okunur. Kritik değişkenler:

```
HIBP_KEY, GOOGLE_API_KEY, GOOGLE_CSE_API_KEY/CX
NUMVERIFY_KEY, NUMLOOKUP_KEY, SHODAN_KEY
SAUCENAO_API_KEY, TINEYE_KEY, LEAKCHECK_KEY
IG_SESSIONID, LI_AT
NEO4J_URI/USER/PASSWORD, GRAPH_DB_ENABLED=False (kapalı)
REDIS_URL (yoksa in-memory cache)
OLLAMA_API_URL, OLLAMA_MODEL
```

---

## 6. Test Altyapısı

- **~80+ test dosyası** `tests/` altında
- pytest 9.0.3, pytest.ini ile konfigüre
- Playwright tabanlı UI testleri (`ui_smoke_test.py`, `test_smart_bar_ui.py`)
- Yandex scraping test seti (5 dosya)
- Screenshot kanıtları `tests/screenshots/` altında (12 panel görüntüsü)
- Feature flag testi: `test_feature_flags.py`

---

## 7. Bağımlılıklar (requirements.txt özeti)

| Paket | Versiyon | Kullanım |
|-------|----------|----------|
| fastapi | 0.120.0 | Web framework |
| uvicorn | 0.38.0 | ASGI server |
| pydantic / pydantic-settings | 2.x | Config + validation |
| playwright | 1.55.0 | Browser automation |
| httpx | 0.28.1 | Async HTTP client |
| beautifulsoup4 | 4.14.2 | HTML parsing |
| sqlalchemy | 2.0.44 | ORM (watchlist SQLite) |
| redis | 7.0.0 | Cache backend |
| rq | 2.6.0 | Task queue |
| croniter | 6.0.0 | Watchlist zamanlayıcı |
| piexif | 1.1.3 | EXIF verisi |

---

## 8. Veri Akışı — Örnek: Yüz Arama

```
POST /face/search (multipart: image)
    ↓ face_search router
    ↓ face_service.py
    ├─ Katman 1: face_recognition (dlib) — yüz tespit + crop
    ├─ Katman 2: Yandex görsel arama (Playwright)
    │       └─ yandex_search.py → _yandex_parser.py
    └─ Katman 3: Gemini Vision API fallback
    ↓ Sonuç JSON
```

---

## 9. Veri Akışı — Örnek: Agent Soruşturması

```
POST /agent/run {seed, goal}
    ↓ agent router
    ↓ InvestigationLoop.run()
    ├─ ToolRegistry.list_available()
    ├─ BudgetEnforcer.check_and_consume()  ← günlük kota
    ├─ tool.execute({seed, goal})
    ├─ AuditLogger.log_tool_call()
    └─ confidence güncelleme (0→1 arası)
    ↓ InvestigationReport (JSON)
```

---

## 10. Tespit Edilen Önemli Noktalar

### Güçlü Yanlar
- Katmanlı mimari (router → service → repository) temiz
- Her servis kendi async metodunu sağlıyor
- Confidence + Correlation sistemi ciddi bir analitik katman
- Playwright + API fallback zinciri yüz aramada sağlam
- Watchlist scheduler lifespan event'e bağlı (temiz startup/shutdown)
- Feature flags ile özellik açma/kapama var

### Dikkat Gerektiren Noktalar
- `GRAPH_DB_ENABLED=False` → Neo4j devre dışı; graph endpoint'leri stub döndürür
- Gemma 3 yerel modeli opsiyonel ama 500MB binary repo içinde
- OpenCode Bridge `localhost:4096` bağımlılığı — OpenCode çalışmıyorsa servis düşmez ama LLM yanıtı olmaz
- `app/services/test_koordinasyon.py` yanlış konumda (services/ altında test dosyası)
- Agent tool'ları stub seviyesinde; gerçek tool implementasyonları eksik olabilir
- `SELF_BASE_URL` README'de var ama config.py'de yok

### Servis Durumu (Çalışma zamanı bağımlılıkları)
| Servis | Gereksinim | Varsayılan |
|--------|-----------|-----------|
| HIBP | API key | Opsiyonel |
| Instagram | Playwright + IG_SESSIONID | Opsiyonel |
| Yandex face | Playwright | Çalışıyor |
| Neo4j | Harici servis | Kapalı |
| Redis | Harici servis | In-memory fallback |
| Ollama | Yerel model | Opsiyonel |
| OpenCode | localhost:4096 | Opsiyonel |

---

## 11. Başlatma

```powershell
# venv_fresh ile
.\venv_fresh\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# veya START.ps1 varsa
.\START.ps1
```

Ana arayüz: http://localhost:8000/mini?mode=expert (mini_panel.html)  
API docs: http://localhost:8000/docs  
Route listesi: http://localhost:8000/__routes

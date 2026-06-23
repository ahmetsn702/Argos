# ARGOS OSINT — Proje Dokümantasyonu

## İçindekiler
1. [Proje Hakkında](#proje-hakkında)
2. [Mimari](#mimari)
3. [Kurulum](#kurulum)
4. [Ortam Değişkenleri](#ortam-değişkenleri)
5. [Sunucu Başlatma](#sunucu-başlatma)
6. [Endpoint Referansı](#endpoint-referansı)
7. [Geo Photo Modülü](#geo-photo-modülü)
8. [Servisler](#servisler)
9. [Teknik Borç & Bilinen Sorunlar](#teknik-borç--bilinen-sorunlar)
10. [Komut Referansı](#komut-referansı)

---

## Proje Hakkında

ARGOS, hedef profilleme ve istihbarat toplama süreçlerini otomatikleştiren tam yığın bir OSINT aracıdır.

**Stack:**
- Backend: Python 3.12 + FastAPI + Uvicorn
- Frontend: Vanilla HTML/CSS/JS (terminal/hacker estetiği)
- AI: Gemini 2.0 Flash Vision (Google Generative AI)
- Harita: Leaflet.js + OpenStreetMap
- Scraping: Playwright (headless Chromium)
- Solar: pvlib + ephem
- Computer Vision: OpenCV

**Versiyon:** v4.0  
**Entry point:** `app/main.py`

---

## Mimari

```
argos/
├── app/
│   ├── main.py                  # FastAPI app, router yükleme (dinamik safe_include)
│   ├── boot_env.py              # .env yükleme, başlangıç
│   ├── core/
│   │   └── config.py            # Pydantic Settings, tüm API key'ler buradan
│   ├── routers/                 # ~30 endpoint modülü
│   │   ├── geo_photo.py         # ★ Yeni: Fotoğraf → Konum analizi
│   │   ├── ig_plus.py           # Instagram gelişmiş (65KB, refactor gerekli)
│   │   ├── unified.py           # Birleşik profil arama
│   │   ├── mini_panel.py        # Expert mode UI paneli
│   │   └── ...
│   ├── services/                # İş mantığı katmanı
│   │   ├── geo_service.py       # ★ Yeni: Gemini Vision + Bayesian fusion
│   │   ├── instagram_service.py # Aktif Instagram servisi (bunu kullan)
│   │   ├── x_fetch.py           # Twitter/X veri çekme
│   │   ├── linkedin_service.py  # LinkedIn (Playwright)
│   │   └── ...
│   ├── utils/
│   │   ├── solar_math.py        # ★ Yeni: pvlib gölge → güneş açısı
│   │   ├── plate_lookup.py      # ★ Yeni: TR plaka kodu → şehir koordinatı
│   │   ├── pw_safe.py           # Playwright güvenli wrapper
│   │   └── ...
│   ├── tools/
│   │   ├── ig_native.py         # Instagram native araçlar
│   │   └── fb_dump.py           # Facebook dump
│   └── ai/
│       └── gemma_local_fixed.py # Yerel Gemma AI (opsiyonel)
├── ui/
│   ├── index.html               # Ana UI (terminal temalı)
│   ├── osint.html               # OSINT arayüzü
│   └── geo_photo.html           # ★ Yeni: Fotoğraf geolokasyon UI
├── tests/
│   ├── test_ping.py
│   ├── test_scan_full.py
│   └── test_geo_photo.py        # ★ Yeni: 4 test
├── scripts/
│   ├── demo.ps1
│   └── demo.sh
├── .env                         # API key'ler (git'e girmesin)
├── .env.example                 # Şablon
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## Kurulum

### 1. Python Ortamı

```bash
# Virtual environment oluştur
python -m venv venv

# Aktive et (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Aktive et (bash/zsh)
source venv/bin/activate
```

### 2. Bağımlılıkları Kur

```bash
pip install -r requirements.txt
```

**Kritik paketler:**
```bash
pip install fastapi uvicorn[standard] httpx python-multipart python-dotenv
pip install pillow opencv-python pvlib google-generativeai geopy numpy
pip install playwright beautifulsoup4 requests
pip install pytest pytest-asyncio httpx
```

### 3. Playwright Browser Kur

```bash
playwright install chromium
playwright install-deps  # Linux'ta gerekli
```

### 4. .env Dosyasını Hazırla

```bash
cp .env.example .env
# .env dosyasını düzenle
```

---

## Ortam Değişkenleri

```env
# === API Anahtarları ===
EMAILREP_KEY=          # Kullanılmıyor (dead config)
HIBP_KEY=              # Have I Been Pwned — boşsa HIBP devre dışı
HUNTER_KEY=            # Kullanılmıyor (dead config)
GOOGLE_CSE_API_KEY=    # Google Custom Search — medya/kişi arama
GOOGLE_CSE_CX=         # Google CSE ID
GOOGLE_API_KEY=        # Gemini Vision API — geo_photo modülü için şart

# === Oturum Çerezleri ===
IG_SESSIONID=          # Instagram session cookie (instagram_service.py kullanır)
LI_AT=                 # LinkedIn li_at cookie (linkedin_service.py kullanır)

# === Uygulama Ayarları ===
PYTHONUTF8=1
SELF_BASE=http://localhost:8000
PROXY_TIMEOUT=30
IG_PW_TIMEOUT_MS=15000
REQUEST_TIMEOUT=15
HEADLESS_MODE=1        # 1=headless, 0=görünür tarayıcı
DEMO_MODE=1            # 1=demo verileri kullan
ALLOW_REMOTE_DASHBOARD=0
LOCALE=tr
SAFE_SEARCH=off
```

### GOOGLE_API_KEY Nasıl Alınır

1. https://aistudio.google.com/apikey adresine git
2. "Create API Key" → proje seç
3. Anahtarı kopyala → `.env`'e yapıştır
4. Sunucuyu yeniden başlat

### IG_SESSIONID Nasıl Alınır

1. Instagram.com'a giriş yap
2. F12 → Application → Cookies → instagram.com
3. `sessionid` değerini kopyala → `.env`'e yapıştır

### LI_AT Nasıl Alınır

1. LinkedIn.com'a giriş yap
2. F12 → Application → Cookies → linkedin.com
3. `li_at` değerini kopyala → `.env`'e yapıştır

---

## Sunucu Başlatma

```powershell
# Proje klasörüne git
cd C:\Footprint\argos

# Sunucuyu başlat (--reload geliştirme için)
python -m uvicorn app.main:app --reload --port 8000

# Prodüksiyon (reload olmadan)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

**Erişim:**
- Ana UI: http://localhost:8000/mini
- Geo Photo: http://localhost:8000/ui/geo_photo.html
- Swagger: http://localhost:8000/docs
- Tüm route'lar: http://localhost:8000/__routes
- Health: http://localhost:8000/__ping

---

## Endpoint Referansı

### ✅ Çalışan Endpoint'ler

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/` | GET | Ana sayfaya redirect |
| `/__ping` | GET | Health check → `{"status": "ok"}` |
| `/__routes` | GET | Tüm yüklü route listesi |
| `/mini` | GET | Expert panel UI |
| `/username-bios` | GET | Çoklu platform bio arama |
| `/ig/bio` | GET | Instagram bio çekme |
| `/compare-ig-x2` | GET | IG-X profil karşılaştırma |
| `/hunt-x-by-name` | GET | İsimle X/Twitter arama |
| `/linkedin-bio` | GET | LinkedIn bio |
| `/combined-search` | POST | Google CSE birleşik arama |
| `/username-scan` | GET | Kullanıcı adı tarama |
| `/mosint/full` | GET | Email OSINT |
| `/geo/analyze-photo` | POST | ★ Fotoğraf → konum analizi |
| `/geo/health` | GET | Geo modül sağlık kontrolü |

### ❌ Broken Endpoint'ler

| Endpoint | Sorun |
|----------|-------|
| `/analyze-email` | db/models modülü eksik |
| `/scan/full` | Cross-router import sorunu |

---

## Geo Photo Modülü

### Nasıl Çalışır

```
Fotoğraf yükle
    ↓
1. EXIF GPS kontrolü (Pillow)
    ↓ GPS varsa → direkt koordinat (source: "exif")
    ↓ GPS yoksa ↓
2. OpenCV shadow analizi (solar_math.py)
    ↓ Gölge bulunduysa → güneş açısı → enlem tahmini
3. Gemini Vision analizi (geo_service.py)
    ↓ ETHAN-style CoT prompt
    ↓ Sinyal katmanları:
       - Tabela/yazı dili ve alfabesi
       - Araç plakaları (TR → plate_lookup.py)
       - Yol çizgisi rengi (sarı=Amerika, beyaz=Avrupa)
       - Sürüş yönü (sol/sağ)
       - Mimari stil
       - Bitki örtüsü
4. Fusion (geo_service.py)
    ↓ plate_match: plaka kodu → şehir koordinatı ±15km
    ↓ full_fusion: solar + visual ±25km
    ↓ visual_fusion: sadece görsel ±500km
5. Leaflet haritada göster
```

### Source Badge Anlamları

| Badge | Renk | Anlam | Radius |
|-------|------|-------|--------|
| `exif` | Beyaz | GPS metadatası bulundu | ~0 km |
| `plate_match` | Mor | Türk plakası tespit edildi | ±15 km |
| `full_fusion` | Neon yeşil | Solar + visual birleşti | ±25 km |
| `visual_fusion` | Turuncu | Sadece görsel analiz | ±500 km |
| `solar_fusion` | Mavi | Sadece gölge analizi | ±200 km |

### API Kullanımı

```bash
# Fotoğraf analizi
curl -X POST http://localhost:8000/geo/analyze-photo \
  -F "image=@foto.jpg" \
  -F "timestamp=2024-08-15T14:30:00Z"

# Health check
curl http://localhost:8000/geo/health
```

### Örnek Response

```json
{
  "source": "plate_match",
  "lat": 38.67,
  "lng": 39.22,
  "confidence": 0.77,
  "radius_km": 15,
  "country": "Turkey",
  "region": "Elazığ",
  "reasoning": {
    "solar": "Shadow analysis inconclusive",
    "visual": "License plate '23' detected → Elazığ",
    "fusion": "plate_match: TR plate code 23 → Elazığ coordinates"
  },
  "fallback": false
}
```

### Türk Plaka Tablosu

`app/utils/plate_lookup.py` — 81 il, 01-81 arası plaka kodu → şehir + koordinat.

```python
from app.utils.plate_lookup import lookup_plate

result = lookup_plate("23")
# → ("Elazığ", 38.67, 39.22)
```

---

## Servisler

### Instagram

**Aktif servis:** `app/services/instagram_service.py`  
Session-based, retry mekanizmalı, IG_SESSIONID kullanır.

```python
from app.services.instagram_service import fetch_instagram_profile
profile = await fetch_instagram_profile("kullanici_adi")
```

> ⚠️ `ig_service.py` duplicate — kullanma, kaldırılacak.

### Twitter/X

**Aktif servis:** `app/services/x_fetch.py`

```python
from app.services.x_fetch import fetch_x_profile_simple
profile = await fetch_x_profile_simple("kullanici_adi")
```

> ⚠️ `x_service.py` sadece wrapper — kullanma, kaldırılacak.

### LinkedIn

**Aktif servis:** `app/services/linkedin_service.py`  
Playwright + LI_AT cookie gerektirir.

### Gemini Vision

**Servis:** `app/services/geo_service.py`  
Model: `gemini-2.0-flash`  
GOOGLE_API_KEY gerektirir.

---

## Teknik Borç & Bilinen Sorunlar

### Duplicate Servisler (Kaldırılacak)

| Kaldırılacak | Yerine Kullan |
|--------------|---------------|
| `ig_service.py` | `instagram_service.py` |
| `ig_fetch.py` | `instagram_service.py` direkt import |
| `x_service.py` | `x_fetch.py` direkt import |
| `gemma_local.py` | `gemma_local_fixed.py` |

### Broken Router'lar

| Dosya | Sorun |
|-------|-------|
| `tools.py` | `db` ve `models` modülleri eksik |
| `osint_demo.py` | `SimpleNamespace` import eksik |
| `compare.py` | Devre dışı bırakıldı |
| `compat_ui.py` | Hiç eklenmemiş |

### Endpoint Çakışmaları

- `hunt_social.py` ve `ig_hunt.py` → ikisi de `/ig-profile` tanımlıyor
- `media.py` ve `search.py` → ikisi de `/combined-search` tanımlıyor

### Refactor Listesi

- [ ] `ig_plus.py` (65KB) → parçala: API / UI / proxy ayrı dosyalara
- [ ] Inline HTML'leri `ui/` altına taşı (mini_panel.py, fb_ui.py)
- [ ] Tutarsız error handling → standart `{"error": "...", "fallback": true}` pattern
- [ ] Dead config temizle: EMAILREP_KEY, HUNTER_KEY .env'den çıkar

---

## Komut Referansı

### Geliştirme

```powershell
# Sunucu başlat
cd C:\Footprint\argos
python -m uvicorn app.main:app --reload --port 8000

# Testleri çalıştır
python -m pytest tests/ -v

# Sadece geo testleri
python -m pytest tests/test_geo_photo.py -v

# Belirli test
python -m pytest tests/test_geo_photo.py::test_health_endpoint -v

# Bağımlılıkları güncelle
pip freeze > requirements.txt
```

### Hata Ayıklama

```powershell
# Route listesini gör
curl http://localhost:8000/__routes

# Geo modül sağlık kontrolü
curl http://localhost:8000/geo/health

# Swagger UI
start http://localhost:8000/docs

# Sunucu loglarını izle
python -m uvicorn app.main:app --reload --port 8000 --log-level debug
```

### Temizlik

```powershell
# pycache temizle
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force

# .bak dosyalarını bul
Get-ChildItem -Recurse -Filter "*.bak*" | Select-Object FullName

# Log dosyalarını temizle
Remove-Item logs\*.log, logs\*.pid, logs\*.txt -ErrorAction SilentlyContinue
```

### Playwright

```powershell
# Chromium kur
playwright install chromium

# Bağımlılıkları kur (Linux)
playwright install-deps

# Playwright versiyonunu kontrol et
python -c "import playwright; print(playwright.__version__)"
```

### Paket Yönetimi

```powershell
# Tüm paketleri kur
pip install -r requirements.txt

# Tek paket kur
pip install google-generativeai

# Kurulu paketleri listele
pip list

# Güncel olmayan paketleri gör
pip list --outdated
```

---

## Notlar

- `venv_fresh/` klasörü git'e girmemeli, `.gitignore`'a ekli olmalı
- `.env` dosyası asla git'e girmesin, sadece `.env.example` gönder
- `app/models/` altına büyük AI model dosyaları koyma, `.gitignore`'a ekle
- Sunucu her zaman proje kökünden başlatılmalı (`cd proje_klasörü` sonra `uvicorn`)
- GOOGLE_API_KEY olmadan geo_photo modülü fallback döner, hata vermez

---

*Son güncelleme: Mayıs 2026*

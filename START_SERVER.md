# 🚀 Footprint Backend - Başlatma Rehberi

## 📋 Proje Yapısı

Bu projede **2 ayrı FastAPI uygulaması** var:

### 1. `app/main.py` - Basit Dosya Yönetim API
- **Port**: 8000
- **Özellikler**: 
  - Dosya okuma/yazma
  - Followers listesi yönetimi
  - Temel veri işleme
- **Kullanım**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### 2. `main.py` (Root) - Tam OSINT Backend
- **Port**: 8000 (varsayılan)
- **Özellikler**:
  - Instagram, X (Twitter), Facebook, LinkedIn entegrasyonu
  - OSINT arama ve analiz
  - AI destekli analiz (Gemma)
  - Playwright browser automation
  - Çoklu router desteği
- **Kullanım**: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`

## ⚙️ Kurulum Adımları

### 1. Virtual Environment Oluştur
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Bağımlılıkları Yükle
```powershell
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
playwright install chromium
```

### 3. Konfigürasyon (Opsiyonel)
Cookie dosyalarını ayarla (varsa):
- `app/secrets/ig.cookie` - Instagram
- `app/secrets/fb.cookie` - Facebook
- `app/secrets/x.cookie` - X (Twitter)
- `app/secrets/linkedin.cookie` - LinkedIn

## 🎯 Sunucuyu Başlatma

### Yöntem 1: Root Main.py (Tam Özellikler - **ÖNERİLEN**)
```powershell
.\venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Yöntem 2: App Main.py (Sadece Dosya Yönetimi)
```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Yöntem 3: Start Script (Auto)
```powershell
.\start.ps1
```
**Not**: Bu script `app.main:app`'i başlatır.

## 🧪 Test Endpoint'leri

### Root Main.py Endpoint'leri:
```powershell
# Ping - Servis durumu
curl http://localhost:8000/__ping

# Routes listesi
curl http://localhost:8000/__routes

# OSINT UI
curl http://localhost:8000/osint/ui

# Instagram Bio
curl "http://localhost:8000/ig/bio?username=instagram"

# Hunt Social
curl "http://localhost:8000/hunt-ig-by-name?full_name=John Doe"

# LinkedIn Debug
curl http://localhost:8000/debug/linkedin-ping
```

### App Main.py Endpoint'leri:
```powershell
# Health Check
curl http://localhost:8000/health

# Config
curl http://localhost:8000/config

# Files List
curl http://localhost:8000/files
```

## 📊 Mevcut Durum

**Şu Anda Çalışan**: Root `main.py` (Port 8000)

**Aktif Endpoint'ler**:
- `/` - Ana sayfa (UI redirect)
- `/__ping` - Servis durumu
- `/__routes` - Tüm route'lar
- `/__pw_status` - Playwright durumu
- `/__pw_smoke` - Playwright test
- `/osint/ui` - OSINT arama arayüzü
- `/osint/search` - OSINT arama API
- `/ig/bio` - Instagram profil
- `/ig-followers` - Instagram takipçiler
- `/hunt-ig-by-name` - Instagram kullanıcı arama
- `/compare-ig-x2` - IG/X karşılaştırma
- `/debug/linkedin-ping` - LinkedIn debug
- `/docs` - Swagger API dokümantasyonu
- `/redoc` - ReDoc API dokümantasyonu

## 🔍 Sorun Giderme

### Port zaten kullanımda
```powershell
# Tüm python/uvicorn process'lerini durdur
Get-Process | Where-Object {$_.ProcessName -match "python|uvicorn"} | Stop-Process -Force

# Portu kontrol et
netstat -ano | findstr :8000
```

### Playwright hatası
```powershell
playwright install chromium
playwright install-deps
```

### Import hatası
```powershell
# sitecustomize.py'nin root'ta olduğundan emin ol
# PYTHONPATH ayarla (gerekirse)
$env:PYTHONPATH = "C:\Users\ahmed\Desktop\footprint-backend"
```

## 📦 Docker ile Çalıştırma

```powershell
# Build ve Başlat
docker compose up --build -d

# Logları izle
docker compose logs -f

# Durdur
docker compose down
```

## 🎨 UI Arayüzleri

1. **Ana UI**: http://localhost:8000/ (→ /ui/ redirect)
2. **OSINT Mini**: http://localhost:8000/osint/ui
3. **API Docs**: http://localhost:8000/docs
4. **ReDoc**: http://localhost:8000/redoc

## 🔧 Geliştirme Modu

```powershell
# Reload ile çalıştır (kod değişikliklerinde otomatik yenilenir)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Debug modu
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# Farklı port
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## ✅ Başarılı Başlatma Kontrolü

Sunucu başarıyla çalışıyorsa şu çıktıları görmelisiniz:

```
INFO:     Will watch for changes in these directories: ['C:\\Users\\ahmed\\Desktop\\footprint-backend']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [XXXX] using WatchFiles
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
[ok] mounted: ig_fetcher.router
[ok] mounted: hunt_social.router
[ok] mounted: similarity.router
[ok] mounted: linkedin_debug.router
[v343] routes sample: ['/', '/__osint_probe', '/__ping', ...]
INFO:     Application startup complete.
```

## 🎯 Sonraki Adımlar

1. ✅ Virtual environment hazır
2. ✅ Bağımlılıklar yüklü
3. ✅ Playwright kurulu
4. ✅ Sunucu çalışıyor
5. 🎉 Tarayıcıda test et: http://localhost:8000/

---

**Son Güncelleme**: 2025-10-26  
**Versiyon**: 3.4.3+  
**Python**: 3.11.9  
**FastAPI**: 0.120.0


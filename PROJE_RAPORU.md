# 📊 Footprint Backend - Detaylı Proje Raporu ve Başlatma Rehberi

**Tarih**: 26 Ekim 2025  
**Python Versiyon**: 3.11.9  
**FastAPI Versiyon**: 0.120.0  
**Durum**: ✅ ÇALIŞIR DURUMDA

---

## 🏗️ Proje Mimarisi

Bu projede **2 AYRI** FastAPI uygulaması bulunmaktadır:

### 1️⃣ `app/main.py` - Dosya Yönetim Servisi
```
📁 Lokasyon: app/main.py
🎯 Amaç: Basit dosya okuma/yazma ve veri yönetimi
📡 Port: 8000
```

**Özellikler**:
- ✅ `/health` - Sistem sağlık kontrolü
- ✅ `/config` - Konfigürasyon bilgileri
- ✅ `/files` - Dosya listesi
- ✅ `/file/{name}` - Dosya okuma
- ✅ `/file/{name}/head` - Dosya başı
- ✅ `/file/{name}/tail` - Dosya sonu
- ✅ `/followers` - Takipçi verileri
- ✅ `/stats` - İstatistikler

**Başlatma Komutu**:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 2️⃣ `main.py` (Root) - Tam OSINT Backend Servisi
```
📁 Lokasyon: main.py (root dizin)
🎯 Amaç: Kapsamlı OSINT analiz ve sosyal medya tarama
📡 Port: 8000
```

**Özellikler**:
- 🎯 **OSINT Arama**: Kişi/profil araştırma ve analiz
- 📸 **Instagram**: Bio çekme, follower analizi
- 🐦 **X (Twitter)**: Profil tarama
- 👔 **LinkedIn**: Public profil çekme
- 📘 **Facebook**: Veri toplama
- 🤖 **AI Analiz**: Gemma model ile akıllı analiz
- 🌐 **Playwright**: Tarayıcı otomasyonu
- 🔍 **Meta Arama**: DDG, Bing, Yandex entegrasyonu

**Router'lar**:
1. `ig_fetcher` - Instagram bio endpoint'i (`/ig/bio`)
2. `hunt_social` - Instagram kullanıcı arama (`/hunt-ig-by-name`)
3. `similarity` - Profil karşılaştırma (`/compare-ig-x2`)
4. `linkedin_debug` - LinkedIn debug (`/debug/linkedin-ping`)
5. `osint_demo` - OSINT arama UI/API (`/osint/ui`, `/osint/search`)

**Endpoint'ler**:
- ✅ `/` - Ana sayfa (UI'ye yönlendirir)
- ✅ `/__ping` - Servis durumu
- ✅ `/__routes` - Tüm route'ların listesi
- ✅ `/__pw_status` - Playwright durumu
- ✅ `/__pw_smoke` - Playwright smoke test
- ✅ `/osint/ui` - OSINT arama arayüzü (Web UI)
- ✅ `/osint/search` - OSINT arama API
- ✅ `/ig/bio?username=X` - Instagram profil bilgisi
- ✅ `/ig-followers?account=X` - Instagram takipçi listesi
- ✅ `/hunt-ig-by-name?full_name=X` - İsimden IG kullanıcısı bul
- ✅ `/compare-ig-x2` - Instagram & X karşılaştırma
- ✅ `/debug/linkedin-ping` - LinkedIn servis kontrolü
- ✅ `/docs` - Swagger API dokümantasyonu
- ✅ `/redoc` - ReDoc API dokümantasyonu

**Başlatma Komutu**:
```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🚀 KURULUM VE BAŞLATMA - ADIM ADIM

### Adım 1: Virtual Environment Oluşturma
```powershell
cd C:\Users\ahmed\Desktop\footprint-backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Adım 2: Bağımlılıkları Yükleme
```powershell
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
playwright install chromium
```

### Adım 3: Sunucuyu Başlatma

#### 🎯 **YÖNTEM 1: OTOMATIK (ÖNERİLEN)**
```powershell
.\BASLA.ps1
```
Bu script:
- ✅ Eski process'leri temizler
- ✅ Virtual environment kontrol eder
- ✅ Bağımlılıkları kontrol eder  
- ✅ Port 8000'i temizler
- ✅ Root main.py'yi başlatır

#### 🎯 **YÖNTEM 2: MANUEL**
```powershell
# Virtual environment'ı aktifleştir
.\venv\Scripts\Activate.ps1

# Root main.py'yi başlat (Tam OSINT özellikleri)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# VEYA app/main.py'yi başlat (Sadece dosya yönetimi)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 🎯 **YÖNTEM 3: start.ps1 Script'i**
```powershell
.\start.ps1
```
**Not**: Bu script `app.main:app`'i başlatır (dosya yönetimi servisi).

---

## 🧪 TEST VE DOĞRULAMA

### Tarayıcıda Test:
1. **Ana Sayfa**: http://localhost:8000/
2. **OSINT UI**: http://localhost:8000/osint/ui
3. **API Docs**: http://localhost:8000/docs
4. **ReDoc**: http://localhost:8000/redoc

### PowerShell'de Test:
```powershell
# Servis durumu
Invoke-WebRequest -Uri "http://localhost:8000/__ping" | Select-Object -ExpandProperty Content

# Tüm route'lar
$routes = (Invoke-WebRequest -Uri "http://localhost:8000/__routes").Content | ConvertFrom-Json
$routes | ForEach-Object { Write-Host $_ }

# Instagram profil test
Invoke-WebRequest -Uri "http://localhost:8000/ig/bio?username=instagram"
```

### Curl ile Test:
```bash
curl http://localhost:8000/__ping
curl http://localhost:8000/__routes
curl "http://localhost:8000/ig/bio?username=instagram"
curl "http://localhost:8000/hunt-ig-by-name?full_name=John Doe"
```

---

## 📁 DOSYA YAPISI

```
footprint-backend/
├── main.py                 # 🎯 Ana OSINT backend (Root)
├── app/
│   ├── main.py            # Dosya yönetim servisi
│   ├── routers/           # API endpoint'leri
│   │   ├── osint_demo.py  # OSINT arama
│   │   ├── hunt_social.py # IG kullanıcı arama
│   │   ├── similarity.py  # Karşılaştırma
│   │   ├── linkedin_debug.py
│   │   └── ...
│   ├── services/          # İş mantığı
│   ├── utils/             # Yardımcı fonksiyonlar
│   ├── tools/             # IG/FB araçları
│   └── secrets/           # Cookie dosyaları
├── ui/                    # Frontend dosyaları
├── venv/                  # Virtual environment
├── ig_fetcher.py          # IG fetch modülü (root'ta)
├── hunt_social.py         # Hunt modülü (root'ta)
├── similarity.py          # Similarity modülü (root'ta)
├── sitecustomize.py       # Playwright patch
├── requirements.txt       # Python bağımlılıkları
├── docker-compose.yml     # Docker konfigürasyonu
├── Dockerfile             # Docker image
├── start.ps1              # Başlatma script'i (app.main)
├── BASLA.ps1              # Yeni otomatik başlatma (main)
├── START_SERVER.md        # Bu rehber
└── PROJE_RAPORU.md        # Detaylı rapor

```

---

## 🔧 ÖNEMLİ NOTLAR

### 1. İki Farklı Uygulama
- **`main.py`** (root): Tam OSINT özellikleri, tüm router'lar
- **`app/main.py`**: Sadece dosya yönetimi

### 2. Port Yönetimi
- Her iki uygulama da varsayılan olarak **port 8000** kullanır
- Aynı anda sadece biri çalışabilir
- Farklı portlar için: `--port 8001`

### 3. Cookie Dosyaları
Instagram, Facebook, LinkedIn entegrasyonları için cookie'ler gereklidir:
- `app/secrets/ig.cookie`
- `app/secrets/fb.cookie`  
- `app/secrets/x.cookie`
- `app/secrets/linkedin.cookie`

### 4. Playwright
- Tarayıcı otomasyonu için **Chromium** yüklü olmalı
- Kurulum: `playwright install chromium`
- `sitecustomize.py` dosyası Playwright'i yamalar

### 5. Module Import Yapısı
Root'taki modüller (`ig_fetcher.py`, `hunt_social.py`, etc.) main.py tarafından dinamik olarak yüklenir.

---

## 🐛 SORUN GİDERME

### Problem 1: Port Zaten Kullanımda
```powershell
# Tüm Python process'lerini durdur
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Port 8000'i kullanan process'leri bul ve durdur
$pids = (netstat -ano | Select-String ":8000.*LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique)
$pids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
```

### Problem 2: "404 Not Found" Hatası
- **Sebep**: Yanlış uygulama çalışıyor olabilir
- **Çözüm**:
  - `app.main` çalışıyorsa: `/health` endpoint'i çalışır, `/__ping` çalışmaz
  - Root `main` çalışıyorsa: `/__ping` çalışır, `/health` çalışmaz
  - Doğru uygulamayı başlattığınızdan emin olun

### Problem 3: Import Hatası
```powershell
# sitecustomize.py'nin root'ta olduğundan emin olun
Test-Path .\sitecustomize.py

# PYTHONPATH'i ayarlayın
$env:PYTHONPATH = "C:\Users\ahmed\Desktop\footprint-backend"
```

### Problem 4: Playwright Hatası
```powershell
playwright install chromium
playwright install-deps  # Linux/macOS için
```

---

## 📊 MEVCUT DURUM (26.10.2025 16:37)

### ✅ Tamamlanan İşlemler:
1. ✅ Virtual environment oluşturuldu ve aktif
2. ✅ Tüm bağımlılıklar yüklendi (FastAPI, Playwright, vb.)
3. ✅ Playwright Chromium kuruldu
4. ✅ Sunucu başlatıldı ve çalışıyor
5. ✅ Endpoint'ler test edildi
6. ✅ Başlatma script'leri oluşturuldu

### 🎯 Hangi Uygulama Çalışıyor?
**Şu anda**: `app.main:app` (Dosya Yönetim Servisi)
- Port: 8000
- Test: `http://localhost:8000/health` ✅ Çalışıyor
- Test: `http://localhost:8000/__ping` ❌ 404 (Bu endpoint root main'de var)

### 🔄 Root main.py'ye Geçiş İçin:
```powershell
# Mevcut servisi durdur
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Root main'i başlat
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# VEYA otomatik script'i kullan
.\BASLA.ps1
```

---

## 🎓 KULLANIM SENARYOLARI

### Senaryo 1: OSINT Araştırma
1. http://localhost:8000/osint/ui adresine git
2. Kişi adı, şehir, username gir
3. Platform seç (IG, X, FB)
4. "Ara" butonuna tıkla
5. Sonuçları incele

### Senaryo 2: Instagram Profil Çekme
```powershell
curl "http://localhost:8000/ig/bio?username=instagram"
```

### Senaryo 3: İsimden Instagram Kullanıcısı Bulma
```powershell
curl "http://localhost:8000/hunt-ig-by-name?full_name=John Doe&kw=developer,tech"
```

### Senaryo 4: API Dokümantasyonu
1. http://localhost:8000/docs adresine git
2. İnteraktif API testi yap
3. Try it out → Execute

---

## 📚 EK KAYNAKLAR

- **README.md**: Genel proje bilgisi
- **START_SERVER.md**: Başlatma rehberi
- **docker-compose.yml**: Docker konfigürasyonu
- **requirements.txt**: Python bağımlılıkları

---

## 🎉 SONUÇ

Proje **başarıyla** kuruldu ve çalışır durumda! İki ayrı FastAPI uygulaması mevcut:

1. **`app.main`**: Basit dosya yönetimi servisi
2. **`main` (root)**: Tam özellikli OSINT backend

İhtiyacınıza göre uygun uygulamayı başlatabilirsiniz. OSINT özellikleri için **root main.py** önerilir.

---

**Hazırlayan**: Cursor AI Assistant  
**Tarih**: 26 Ekim 2025  
**Versiyon**: 1.0


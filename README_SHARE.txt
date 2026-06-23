Footprint Backend - Hızlı Başlangıç
1) Docker Desktop kurulu olsun ve açık olsun.
2) Klasörü çıkarın, .env.share dosyasını gerekirse .env olarak yeniden adlandırın ve kendi anahtarlarınızı doldurun.
3) PowerShell:  docker compose up -d --build footprint
4) Arayüz:      http://127.0.0.1:8000/mini?mode=expert
Swagger:        http://127.0.0.1:8000/docs
Not: "data/", "secrets/" ve yerel venv klasörleri pakete dahil değildir.

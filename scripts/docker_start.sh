#!/usr/bin/env bash
# ============================================================================
# ARGOS OSINT v4.0 — Docker tek-tıkla başlatıcı (Linux / macOS)
# ----------------------------------------------------------------------------
# Build + detached up + 3 sn bekleme + healthcheck (/__ping)
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

# ---- 1. .env varlığı kontrolü ---------------------------------------------
if [[ ! -f .env ]]; then
  echo "[uyari] .env dosyasi bulunamadi — API anahtarlari olmadan calisacak."
  echo "         Ornek: cp .env.example .env && nano .env"
fi

# ---- 2. Build & up --------------------------------------------------------
echo "[1/3] docker compose up --build -d"
docker compose up --build -d

# ---- 3. Konteynerin hazir olmasini bekle ----------------------------------
echo "[2/3] healthcheck'i bekliyorum..."
sleep 3

# ---- 4. /__ping ile dogrula -----------------------------------------------
echo "[3/3] http://localhost:8000/__ping"
if curl -fsS --max-time 5 http://localhost:8000/__ping; then
  echo
  echo
  echo "[ok] ARGOS OSINT calisiyor."
  echo "     UI:    http://localhost:8000/ui/dashboard.html"
  echo "     Docs:  http://localhost:8000/docs"
  echo "     Logs:  docker compose logs -f argos"
else
  echo
  echo "[hata] /__ping yanit vermedi. Loglara bakin: docker compose logs argos"
  exit 1
fi

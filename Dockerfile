# syntax=docker/dockerfile:1.6
# ============================================================================
# ARGOS OSINT v4.0 — Container image
# ----------------------------------------------------------------------------
# Base:    python:3.12-slim
# Ports:   8000 (uvicorn)
# Browser: Playwright Chromium (installed with --with-deps)
# Native:  dlib (face_recognition) + opencv-python require build-essential,
#          cmake, libboost-python-dev, libgl1, libglib2.0-0
# ============================================================================
FROM python:3.12-slim AS runtime

# ---- 1. OS-level build & runtime dependencies ------------------------------
# build-essential + cmake + libboost-python-dev → dlib / face_recognition
# libgl1 + libglib2.0-0                          → opencv-python at runtime
# curl                                           → healthcheck inside container
# fonts-liberation, libnss3, libxss1, …          → playwright chromium runtime
#                                                  (most of these are pulled in
#                                                  by `playwright install chromium --with-deps`,
#                                                  but we pre-install the small set
#                                                  that survives image trimming.)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        libboost-python-dev \
        libgl1 \
        libglib2.0-0 \
        curl \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ---- 2. Python environment hygiene -----------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# ---- 3. Python dependencies (cached layer) ---------------------------------
# Copy requirements.txt first so dependency layer is cached when only app code
# changes.
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# ---- 4. Playwright browser + its remaining OS deps -------------------------
# `--with-deps` triggers apt-get install for the Chromium runtime libs that
# Playwright itself knows it needs. Safe & idempotent.
RUN python -m playwright install --with-deps chromium

# ---- 5. Application code ---------------------------------------------------
# .dockerignore strips: .git, .env, venv/, __pycache__, *.pyc, logs/, …
COPY . .

# ---- 6. Runtime configuration ----------------------------------------------
EXPOSE 8000

# Optional self-test inside container; docker-compose.yml has a richer one.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=20s \
  CMD curl -fsS http://localhost:8000/__ping || exit 1

# Playwright browser instance'ları process-level state tutar. Multi-worker
# OOM riskini önlemek için tek worker kullanılıyor.
# Ölçeklendirme için RQ worker queue kullan.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--timeout-keep-alive", "5"]

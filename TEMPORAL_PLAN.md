# ARGOS Temporal Intelligence v1.0 — Implementation Plan

## Toplam Test Hedefi
404 (mevcut) + ~36-38 yeni = ~440-442 passed

## FAZ PLANI

| FAZ | Kapsam | Test | Kümülatif |
|-----|--------|------|-----------|
| 1 | Models + Constants + Parsing | ~7 | 411 |
| 2 | Extractors + Clusters | ~7 | 418 |
| 3 | Anomaly Detectors | ~7 | 425 |
| 4 | Narrator + Cache + Service | ~9-10 | 434-435 |
| 5 | Router + Endpoints + Verification | ~6-7 | 440-442 |

## DOSYA YAPISI

app/
  models/temporal.py
  services/temporal/
    __init__.py
    constants.py
    parsing.py
    extractors.py
    clusters.py
    anomalies.py
    narrator.py
    cache.py
    service.py
  routers/temporal.py
  main.py (PATCH: "temporal" ekle)

tests/
  test_temporal_models.py
  test_temporal_parsing.py
  test_temporal_extractors.py
  test_temporal_clusters.py
  test_temporal_anomalies.py
  test_temporal_narrator.py
  test_temporal_cache.py
  test_temporal_service.py
  test_temporal_endpoints.py

## KARARLAR

- Timestamp: Çoklu event per finding (breach ayrı + first_observed)
- Anomali eşikleri: ENV override edilebilir sabitler
- LLM narrative: anomalies!=[] VE narrative=true ise tetiklenir
- Cache: TemporalAnalysisCache TTL=6h (ENV: TEMPORAL_TTL_HOURS)
- correlation/temporal.py: dokunulmaz, tamamen ayrı
- event_type: Sabit Enum (TimelineEventType)
- Timezone: ENV offset, default +3 (TR)
- Severity: Yoğunluk skalası + ENV override

## ENDPOINT'LER

POST /temporal/analyze     (rate: 5/dk)
GET  /temporal/timeline/{seed_key}
GET  /temporal/anomalies/{seed_key}

## MEVCUT SİSTEM ENTEGRASYONU

- app/services/confidence/cache.py → default_cache (girdi)
- app/services/confidence/graph.py → ConfidenceGraph (model)
- app/services/llm_analyst.py → OsintAnalyst (narrator pattern)
- app/routers/confidence.py → rate limit pattern
- app/main.py → _safe_include ile "temporal" ekle

## ENV DEĞİŞKENLERİ (tümü opsiyonel, defaultlu)

TEMPORAL_TTL_HOURS=6
TEMPORAL_NIGHT_TZ_OFFSET=3
TEMPORAL_NIGHT_START_HOUR=0
TEMPORAL_NIGHT_END_HOUR=6
TEMPORAL_CLUSTER_WINDOW_MIN=60
TEMPORAL_BURST_MIN_PLATFORMS=3
TEMPORAL_BURST_MED_PLATFORMS=5
TEMPORAL_BURST_HIGH_PLATFORMS=8
TEMPORAL_SILENCE_DAYS=180
TEMPORAL_BREACH_OVERLAP_DAYS=30

## DURUM

| FAZ | Durum |
|-----|-------|
| 1 | ✅ Tamamlandı |
| 2 | ✅ Tamamlandı |
| 3 | ✅ Tamamlandı |
| 4 | ✅ Tamamlandı |
| 5 | ✅ Tamamlandı |

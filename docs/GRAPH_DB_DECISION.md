# Graph DB Decision — ARGOS v5

> **Karar:** Confidence Graph kalıcı katmanı için **Neo4j Community 5.x**, Strangler Fig stratejisiyle, feature flag (`GRAPH_DB_ENABLED`) arkasında.
> **Durum:** Faz 3.1 tamamlandı (driver soyutlama + ABC). Faz 3.2 → 3.6 sırayla yürüyecek.

---

## 1. Neden Strangler Fig?

ARGOS v4'te tüm confidence graph state'i `default_cache: dict` üzerinde tutuluyor. Tek seferde Neo4j'ye geçmek üç riski birden tetikler:

1. **478 testin tamamı in-memory davranışa bağımlı** — bir gecede hepsini Neo4j gerektirir hale getirmek hem CI'yı hem geliştirme döngüsünü kırar.
2. **Endpoint sözleşmesi (`ConfidenceGraph` Pydantic şeması) sabit kalmalı** — UI, raporlar, Stitch grafiği, Maltego export bu şemaya bağlı. Geçiş süresince üst arayüzler şemanın yokluğunu fark etmemeli.
3. **Operasyonel rollback hızı sıfır olmalı** — Neo4j down olduğunda servis 503'e gitmek yerine eski yola düşmeli. Bu yalnızca her iki yolun aynı anda yaşadığı bir geçiş döneminde mümkündür.

**Strangler Fig** bu üç kısıtı tek desende çözüyor:

```
[ Caller ]               [ Caller ]                 [ Caller ]
     |                        |                          |
     v                        v                          v
[ in-memory ]   →  [ in-memory + Neo4j ]      →    [ Neo4j only ]
                       (dual-write)
                  flag=false reads in-memory
                  flag=true reads Neo4j
```

- Faz 3.3 dual-write açar; flag default `false` — okuma in-memory.
- Faz 3.4 flag `true` ile okuma Neo4j'ye geçer; in-memory hâlâ yazılır (veri sigortası).
- Sonraki minor sürümde dual-write kapatılır, in-memory kaldırılır.

Test etkisi: yeni testler `@pytest.mark.graph_db` ile etiketlenir; default CI bunları çalıştırmaz, mevcut 478 (+ Faz 0 ile 5) test bozulmadan kalır.

---

## 2. Neden Neo4j Community?

| Kriter | Neo4j Community 5.x | Memgraph 2.x | ARGOS için anlamı |
|---|---|---|---|
| Lisans | GPLv3 (community) | BSL → Apache 2.0 | İkisi de yeterli (kapalı kaynak değil). |
| Cypher uyumu | Referans implementasyonu | OpenCypher %95+ | Aynı sorgu kodu çalışır. |
| Bellek modeli | Disk-first, page cache | Tamamen in-memory + WAL | ARGOS Python tarafı zaten RAM yiyor → DB'yi diske bırakmak toplam bütçeyi koruyor. |
| Docker imajı | ~600 MB | ~250 MB | Neo4j daha büyük; tek seferlik pull. |
| Tipik RAM (10K node) | ~512 MB | ~300 MB | ARGOS ölçeğinde fark önemsiz. |
| Browser/UI | Built-in Neo4j Browser | Memgraph Lab (ayrı container) | Geliştirici verimliliği önemli. |
| Python driver | `neo4j` resmi, çok olgun | `neo4j` driver bolt uyumlu | Aynı driver çalışıyor. |
| Bolt protokolü | Var | Var | **Soyutlama sayesinde ileride Memgraph'a geçiş 1 satır config.** |

**Operasyonel gerekçe:** Bolt protokolü her ikisinde de standart. Bizim driver'ımız `settings.NEO4J_URI` üzerinden konuşuyor; backend değiştirmek yalnızca URI'yi değiştirmek demek. O yüzden **bugün Neo4j seçmek ileride Memgraph'a geçişi engellemiyor**. Memgraph'ın in-memory hızı ARGOS ölçeğinde gerekli olmadığı için Neo4j'nin doküman bolluğu ve Browser UI avantajını alıyoruz.

---

## 3. Feature Flag Stratejisi

- **`GRAPH_DB_ENABLED`** (`app/core/config.py` Settings, `app/core/feature_flags.py`)
  - Default: `false`
  - Kapalıyken `get_driver()` → `None` (exception YOK)
  - Açık ama Neo4j ulaşılamaz: connect denenip raise; çağıran try/except ile in-memory'ye düşer
  - `neo4j` paketi import edilemiyorsa: `None` (graceful degrade)

- **Driver erişimi tek noktadan:** `app.services.graph_db.driver.get_driver()`. Hiçbir router/servis doğrudan `neo4j` import etmez. Bu sayede:
  - Mock'lamak tek seam'den kolay (testler `monkeypatch` ile)
  - Memgraph/başka backend geçişi tek dosyada
  - Driver lifecycle (close on shutdown) tek yerden

- **Repository soyutlama:** `GraphRepository` ABC (`app/services/graph_db/repository_base.py`). Concrete implementasyonlar (gelecekte `Neo4jGraphRepository`, `InMemoryGraphRepository`) bu kontrata bağlı. Üst katmanlar (router, service) yalnızca abstract tipi görür; somut sınıf factory tarafından flag'e göre seçilir.

---

## 4. Geçiş Takvimi

| Faz | İçerik | Test etkisi | Flag durumu | Tamamlanma |
|---|---|---|---|---|
| **3.1** | Driver soyutlama + GraphRepository ABC + bu doküman | +5 (hiçbiri Neo4j gerekmez) | n/a | ✅ Şimdi |
| 3.2 | Neo4j schema constraint/index + ETL adapter + Neo4jGraphRepository concrete | +14 (`@pytest.mark.graph_db`, CI default skip) | flag false; manuel test | — |
| 3.3 | `ConfidenceCache.merge_and_save` içine opsiyonel dual-write (try/except) + `/graph/_shadow_compare/{seed_key}` | +10 (`@pytest.mark.graph_db`) | flag false; dev'de true ile shadow karşılaştır | — |
| 3.4 | `/confidence/graph` flag-aware okuma | +8 | flag true → okuma Neo4j; in-memory yazılmaya devam | — |
| 3.5 | Yeni endpoint'ler: `/graph/neighbors`, `/graph/paths`, `/graph/intersect`, `/graph/cypher` (readonly) | +18 | flag true zorunlu | — |
| 3.6 | Stitch UI panel + Cypher cookbook | +4 (`@pytest.mark.e2e`) | flag true | — |
| **v5.1** (sonra) | Dual-write kapat, in-memory katmanı sil | n/a | flag artık koşul değil | — |

**Toplam etki:** Paket 3 sonu 543 test (478 v4 + 5 Faz 0 + 60 Paket 3); CI default 488'i çalıştırır (graph_db marker'lı 55 test devre dışı).

---

## 5. Rollback

| Senaryo | Aksiyon |
|---|---|
| Neo4j down | `GRAPH_DB_ENABLED=false` → restart → in-memory yola döner. Veri kaybı yok (Faz 3.3'ten itibaren her şey in-memory'ye de yazılıyor). |
| Performans regresyonu | Aynı: flag false. Detaylı analiz için `/graph/_shadow_compare` ile fark raporu. |
| Cypher injection şüphesi | `/graph/cypher` rate limit + readonly Neo4j user (Faz 3.5'te kurulacak); en kötüsü endpoint'i `app/main.py` `routers_to_load`'tan çıkar. |
| ETL bug — Neo4j veri bozuk | `MATCH (n) DETACH DELETE n` + dual-write yeniden çalıştığında sıfırdan dolar (kaynak in-memory). |

---

## 6. Mevcut Faz 3.1 Çıktıları

- `app/services/graph_db/__init__.py` — paket marker
- `app/services/graph_db/driver.py` — `get_driver()` singleton + `close_driver()` graceful shutdown
- `app/services/graph_db/repository_base.py` — `GraphRepository` ABC, 6 async abstract metot
- `tests/test_graph_db_driver.py` — 5 birim test (Neo4j gerçek bağlantısı YOK; mock'lu)
- `docs/GRAPH_DB_DECISION.md` — bu doküman

**Önemli:** Faz 3.1 hiçbir mevcut dosyaya dokunmaz. `GRAPH_DB_ENABLED=false` (default) sürdükçe ARGOS v4 davranışı bit bazında aynıdır.

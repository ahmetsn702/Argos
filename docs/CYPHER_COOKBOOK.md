# ARGOS Cypher Cookbook

> ARGOS v5 Graph DB endpoint'leri için hazır sorgu örnekleri.
> Tüm sorgular `POST /graph/cypher` endpoint'i üzerinden çalıştırılır.

---

## Genel Kurallar

- Tüm sorgular **readonly** — write operasyonları (CREATE, MERGE, DELETE, SET, REMOVE, DROP, LOAD CSV, FOREACH) HTTP 400 döner.
- `POST /graph/cypher` body: `{"query": "MATCH ..."}`
- Neighbors endpoint max hop: **4**
- Paths endpoint max hop: **6**
- `GRAPH_DB_ENABLED=false` iken tüm endpoint'ler `{"enabled": false}` döner.

---

## Hazır Sorgular

### 1. Tüm finding'leri listele

```cypher
MATCH (f:Finding)
RETURN f.id, f.type, f.confidence
ORDER BY f.confidence DESC
LIMIT 20
```

### 2. Belirli tipte finding'ler

```cypher
MATCH (f:Finding {type: "email"})
RETURN f.id, f.value, f.confidence
```

### 3. Yüksek confidence finding'ler

```cypher
MATCH (f:Finding)
WHERE f.confidence > 0.7
RETURN f
ORDER BY f.confidence DESC
```

### 4. İki finding arası bağlantı

```cypher
MATCH (a:Finding {id: "finding_id_1"}),
      (b:Finding {id: "finding_id_2"})
MATCH p = shortestPath((a)-[*..6]-(b))
RETURN p
```

### 5. En bağlantılı node'lar (degree centrality)

```cypher
MATCH (f:Finding)-[r]-()
RETURN f.id, f.type, count(r) AS degree
ORDER BY degree DESC
LIMIT 10
```

### 6. Zaman bazlı analiz (son 7 gün)

```cypher
MATCH (f:Finding)
WHERE f.created_at > datetime() - duration('P7D')
RETURN f.id, f.type, f.created_at
ORDER BY f.created_at DESC
```

### 7. Belirli seed'e ait tüm finding'ler

```cypher
MATCH (f:Finding {seed_key: "email:user@example.com"})
RETURN f.id, f.type, f.value, f.confidence
ORDER BY f.confidence DESC
```

### 8. İki seed'in ortak komşuları

```cypher
MATCH (a:Finding {seed_key: "seed_a"})-[]-(common)
MATCH (b:Finding {seed_key: "seed_b"})-[]-(common)
RETURN DISTINCT common
ORDER BY common.confidence DESC
LIMIT 50
```

### 9. Belirli ilişki tipindeki bağlantılar

```cypher
MATCH (a:Finding)-[r:SUPPORTS]->(b:Finding)
RETURN a.id, b.id, r.weight
ORDER BY r.weight DESC
LIMIT 20
```

### 10. Çelişen finding'ler

```cypher
MATCH (a:Finding)-[r:CONTRADICTS]-(b:Finding)
RETURN a.id, a.value, b.id, b.value, r.weight
```

---

## Yasak Sorgular (HTTP 400 döner)

Aşağıdaki keyword'ler tespit edildiğinde sorgu reddedilir:

```
CREATE, MERGE, DELETE, DETACH, SET, REMOVE,
DROP, CALL APOC.SCHEMA, CALL DB.INDEX, LOAD CSV, FOREACH
```

---

## Endpoint Referansı

| Metot | Endpoint | Açıklama |
|---|---|---|
| GET | `/graph/neighbors/{finding_id}?hops=2` | N-hop komşular (max 4) |
| GET | `/graph/paths?from_id=X&to_id=Y&max_hops=4` | En kısa yol (max 6) |
| GET | `/graph/intersect?seed_a=X&seed_b=Y` | İki seed'in ortak finding'leri |
| POST | `/graph/cypher` | Serbest readonly Cypher sorgusu |
| GET | `/graph/_shadow_compare/{seed_key}` | Memory↔Neo4j tutarlılık kontrolü |

---

## Stitch UI Kullanımı

`correlation.html` sayfasında sağ alt köşedeki **⬡ GRAPH DB** paneli:

- **2-Hop** butonu: Girilen `finding_id` için 2-hop komşuları getirir.
- **Kesişim** butonu: İki `seed_key` arasındaki ortak finding'leri bulur.
- Sonuçlar panel içindeki `<pre>` alanında JSON olarak gösterilir.
- `GRAPH_DB_ENABLED=false` iken "Graph DB devre dışı" mesajı görünür.

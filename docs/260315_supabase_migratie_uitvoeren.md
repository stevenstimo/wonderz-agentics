# 260315 — Supabase migratie: uit te voeren vanaf host met Supabase-toegang

De exe.dev server kan Supabase (poort 5432) niet bereiken (network unreachable). Fase 2 en Fase 3 moeten daarom vanaf een machine met netwerktoegang tot Supabase worden uitgevoerd (of via Supabase Dashboard waar mogelijk).

## Wat er al klaarstaat op de server

- **Stap 0:** SUPABASE_DB_URL staat in `.env`.
- **Pre-flight:** Alle 7 checks geslaagd (72 tabellen, pgvector lokaal, migraties, Vercel-config).
- **Fase 1:** Schema- en data-export op de server:
  - `~/wonderz_schema_export.sql` (schema-only, ~4238 regels, artefact-regel verwijderd)
  - `~/wonderz_data_export.sql` (data-only, 3289 regels)

## Fase 2 — Uitvoeren vanaf machine met Supabase-toegang

1. **Bestanden van server halen** (lokaal of CI):
   ```bash
   scp exe.dev:~/wonderz_schema_export.sql ./
   scp exe.dev:~/wonderz_data_export.sql ./
   ```

2. **Supabase: pgvector**
   - In Supabase Dashboard → SQL Editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

3. **Schema importeren**
   - Stel de Supabase direct connection string in (poort 5432, uit Dashboard → Project Settings → Database → URI).
   ```bash
   export SUPABASE_DB_URL="postgresql://postgres:[PASSWORD]@db.cqasccazioqjodctawzx.supabase.co:5432/postgres"
   psql "$SUPABASE_DB_URL" -f wonderz_schema_export.sql 2>&1
   ```
   - Eventuele errors over bestaande objecten (bij herhaalde run) zijn vaak acceptabel; controleer daarna met `\dt` of alle tabellen bestaan.

4. **Verifiëren**
   ```bash
   psql "$SUPABASE_DB_URL" -c "\dt"
   psql "$SUPABASE_DB_URL" -c "SELECT '[1,2,3]'::vector(3) <=> '[1,2,4]'::vector(3);"
   ```

## Fase 3 — Data migreren (na Fase 2)

**Op de server:** backend eerst stoppen, dan verse data-dump maken:

```bash
sudo systemctl stop wonderz-backend
pg_dump "postgresql://wonderz:wonderz123@localhost:5432/wonderz" \
  --data-only --no-owner --no-acl --disable-triggers \
  -f ~/wonderz_data_final.sql
```

**Import in Supabase** (vanaf machine met toegang): moet in **één** psql-sessie zodat triggers uit blijven tijdens de import.

Maak een wrapperbestand (bijv. `import_data.sql`):

```sql
SET session_replication_role = replica;
\i wonderz_data_final.sql
SET session_replication_role = DEFAULT;
```

Run dan (pad naar `wonderz_data_final.sql` moet kloppen voor `\i`):

```bash
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f import_data.sql
```

Of in één keer zonder apart bestand (vanaf de map waar `wonderz_data_final.sql` staat):

```bash
printf 'SET session_replication_role = replica;\n\\i wonderz_data_final.sql\nSET session_replication_role = DEFAULT;\n' | psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1
```

**Record counts vergelijken:** lokaal vs. Supabase `pg_stat_user_tables` (kolom `relname`, niet `tablename`).

Daarna op de server: **Fase 4** (DATABASE_URL wijzigen, backend herstarten) — zie hoofdplan; dat zijn de twee harde stop-momenten.

---

## Fase 5 — BGE-M3 embeddings verifiëren

De backend gebruikt overal dezelfde pool (`get_db()` → `TrainingWorkflow(pool)`). Na de DATABASE_URL-switch schrijven nieuwe trainingen dus naar Supabase.

**Optioneel: training triggeren**
```bash
curl -X POST https://wonderz-agentic.exe.xyz/api/agents/agent:copywriter/train \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"url": "https://example.com"}' -s
```

**In Supabase SQL Editor: controleer of nieuwe chunks met embedding bestaan**
```sql
SELECT agent_id, source_url, chunk_index, created_at, length(chunk_text) AS chunk_chars, (embedding IS NOT NULL) AS has_embedding
FROM agent_knowledge
ORDER BY created_at DESC
LIMIT 10;
```

---

## Fase 6 — Vercel + CORS (uitgevoerd in repo)

- **CORS:** `app/main.py` leest nu `CORS_ORIGINS` uit de omgeving (comma-separated). Default: localhost + wonderz-agentic.exe.xyz.
- **Op de server:** Voeg het Vercel-domein toe en herstart:
  ```bash
  # In .env toevoegen of aanpassen, bijv.:
  CORS_ORIGINS=http://localhost:3000,http://localhost:3001,https://wonderz-agentic.exe.xyz,https://crew-intelligent.vercel.app
  sudo systemctl restart wonderz-backend
  ```
- **Vercel:** In Project Settings → Environment Variables instellen: `VITE_API_URL=https://wonderz-agentic.exe.xyz`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. Root Directory: `web_ui/frontend`.
- **Deploy:** `git push origin main` (als Vercel aan de repo gekoppeld is), of handmatig deployen vanuit `web_ui/frontend`.

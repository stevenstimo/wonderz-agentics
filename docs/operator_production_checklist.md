# Operator Checklist — Crew Intelligent Productie

**Datum:** zie Git | **Uitvoerder:** operator | **Geschatte tijd:** 15 minuten

Stop bij elke fout. Documenteer het resultaat van elke verificatiestap.

---

## Stap 1 — Migratie 063: users + inbound_emails

```bash
# Check of tabel al bestaat (skip als output een rij toont)
psql "$DATABASE_URL" -c "\dt" | grep "inbound_emails"

# Uitvoeren (alleen als bovenstaande leeg was)
psql "$DATABASE_URL" -f app/migrations/063_inbound_emails_and_users.sql
```

**Verificatie:**
```sql
SELECT COUNT(*) AS users        FROM users;
SELECT COUNT(*) AS inbound      FROM inbound_emails;
SELECT indexname FROM pg_indexes WHERE tablename = 'inbound_emails';
```

Verwacht: beide queries geven een getal (0 of meer), minimaal 2 indices op `inbound_emails`.

---

## Stap 2 — Migratie 064: jobs.intake_source

```bash
# Check of kolom al bestaat (skip als output een rij toont)
psql "$DATABASE_URL" -c "SELECT intake_source FROM jobs LIMIT 1;" 2>/dev/null

# Uitvoeren (alleen als bovenstaande faalde)
psql "$DATABASE_URL" -f app/migrations/064_jobs_intake_source.sql
```

**Verificatie:**
```sql
SELECT id, intake_source FROM jobs LIMIT 3;
-- Verwacht: intake_source kolom aanwezig, waarde 'browser' voor bestaande jobs
```

---

## Stap 3 — Supabase auth trigger

Ga naar **Supabase Dashboard → SQL Editor** en voer de inhoud van `docs/supabase_trigger.sql` uit.

Dat bestand bevat:
1. `CREATE OR REPLACE FUNCTION sync_user_to_app()` — sync nieuwe auth-users naar `public.users`
2. `CREATE TRIGGER on_auth_user_created` — vuurt bij INSERT en DELETE op `auth.users`
3. Backfill: `INSERT INTO public.users SELECT id, email FROM auth.users ON CONFLICT DO NOTHING`

**Verificatie (uitvoeren in dezelfde SQL Editor):**
```sql
SELECT
    (SELECT COUNT(*) FROM auth.users)   AS auth_count,
    (SELECT COUNT(*) FROM public.users) AS app_count;
-- Beide getallen moeten gelijk zijn
```

---

## Stap 4 — Eindverificatie

```sql
-- Tabellen aanwezig
SELECT tablename FROM pg_tables
WHERE tablename IN ('users','inbound_emails','hired_agents','jobs','job_steps')
ORDER BY tablename;
-- Verwacht: 5 rijen

-- Kolommen jobs correct
SELECT column_name FROM information_schema.columns
WHERE table_name = 'jobs'
AND column_name IN ('id','status','intake_source','inbound_email_id')
ORDER BY column_name;
-- Verwacht: 4 rijen

-- Trigger actief
SELECT trigger_name FROM information_schema.triggers
WHERE trigger_name = 'on_auth_user_created';
-- Verwacht: 1 rij

-- Users gesynchroniseerd
SELECT
    (SELECT COUNT(*) FROM auth.users)   AS auth_count,
    (SELECT COUNT(*) FROM public.users) AS app_count;
-- Verwacht: gelijke aantallen
```

**Backend herstart na migraties:**
```bash
git pull && sudo systemctl restart wonderz-backend
```

Alle vier stappen succesvol? Email intake is live. Nieuwe signups worden automatisch gesynchroniseerd naar `public.users` en inkomende emails worden gekoppeld aan hun account.

---

## Resultaat laatste run (via psql op productie-DB)

| Stap | Actie | Resultaat |
|------|--------|-----------|
| **1** | Tabellen bestonden al; migratie 063 overgeslagen. | ✅ users: 3, inbound_emails: 11. Indices op `inbound_emails`: 5 (o.a. pkey, message_id_key, status, from, received). |
| **2** | Kolom bestond al; migratie 064 overgeslagen. | ✅ `intake_source` aanwezig; waarden o.a. `email`, `browser`. |
| **3** | Handmatig in Supabase Dashboard. | ⏳ Trigger en auth/users-verificatie moeten in **Supabase Dashboard → SQL Editor** worden uitgevoerd (`auth.users` is niet bereikbaar via gewone `psql "$DATABASE_URL"`). |
| **4** | Eindverificatie (tabellen + kolommen). | ✅ 5 tabellen aanwezig. ✅ 4 kolommen op `jobs`. Trigger: 0 rijen via deze verbinding (trigger leeft in Supabase; na Stap 3 in Dashboard controleren). |

**Opmerking:** De checks `auth.users` en `on_auth_user_created` moeten in het **Supabase Dashboard → SQL Editor** gedaan worden; via een directe Postgres-URL is het `auth`-schema vaak niet zichtbaar.

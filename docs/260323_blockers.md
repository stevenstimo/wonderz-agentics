# 260323 — Blockers / notities

## Supabase: `information_schema.columns` voor `lessons`

**Blocker:** Live SQL in de Supabase SQL editor is in deze omgeving niet uitgevoerd.

**Actie voor operator:** Controleer of `lessons` deze kolommen heeft en of `source_job_id` bestaat:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'lessons'
ORDER BY ordinal_position;
```

**Code-aanpassing:** `app/services/lesson_from_completed_job.py` gebruikt nu:

- Als `source_job_id` bestaat: `SELECT`/`INSERT` met `source_job_id` en vergelijking `source_job_id::text = $1`.
- Anders: `task_id` voor duplicate-check en `INSERT` (zelfde titel/teksten), conform oudere schema’s zonder `source_job_id`.

Als jullie schema afwijkt, pas de INSERT-kolomlijst aan op basis van de query hierboven.

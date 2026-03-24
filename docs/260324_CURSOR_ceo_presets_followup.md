# 260324_CURSOR_ceo_presets_followup

Vervolg op CEO preset gate (`ceo_intent.py`, NEXUS `_ceo_preset_gate`).

## Verplichte git-regels

- Nooit `git restore`, `git checkout --force`, `git reset` of `git clean` uitvoeren
- Bij elke git-operatie eerst `git status` rapporteren en wachten op bevestiging
- Alleen specifieke bestanden stagen, nooit `git add -A`

## Pre-flight

```bash
ls app/orchestration/ceo_intent.py
psql postgresql://wonderz:wonderz123@localhost:5432/wonderz \
  -c "SELECT preset_id FROM job_type_presets ORDER BY preset_id;"
psql postgresql://wonderz:wonderz123@localhost:5432/wonderz \
  -c "\d jobs" | grep -E "payload|notes"
```

Verwacht: `ceo_intent.py` aanwezig, 8 presets, kolom `payload`, geen `notes`.

## Fasen (implementatie in repo)

1. **`_block_job`**: `block_reason`, `ceo_preset_blocked`, `missing_roles` in `jobs.payload` JSONB.
2. **Frontend BLOCKED**: `JobSplitView.jsx`, `JobLifecycleView.jsx`, `JobDetail.jsx` (badge + whitelist).
3. **`usage_count`**: alleen bij eerste overgang naar `JOB_READY`, met `preset_usage_counted` in payload.
4. **`preset_bookings`**: migratie `048_preset_bookings_unique.sql` — `UNIQUE (job_id, preset_id, slot_role)`; `register_preset_bookings` met `ON CONFLICT DO NOTHING`; `compute_deviation_slots` voor CEO/COO vs Donna/Mr. Klein.

## Commits (na bevestiging)

Zie oorspronkelijke prompt voor voorgestelde commit messages en file lists.

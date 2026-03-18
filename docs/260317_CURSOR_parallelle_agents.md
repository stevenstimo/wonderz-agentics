# 260317 — Parallelle agent-uitvoering NEXUS (Cursor run)

**Doel:** Voer fasen 2, 3 en 4 uit conform het plan in dit document en het plan in `.cursor/plans/nexus_parallelle_agent-uitvoering_7672c6e5.plan.md`.

---

## Kritieke punten voor Fase 2

### Merge depends_on in phase_2_planning
Na het laden van `job_steps` uit de DB moet het **plan uit de job context** worden geladen en moet **depends_on per step_index** worden gemerged in `ctx.execution_plan`. Zonder deze merge heeft phase_3 geen `depends_on` om op te beslissen, ook al staat het correct in het plan in de context.

- Haal job-row op (payload en/of context).
- Lees `plan = context.get("plan")` of uit payload.
- Als `plan` en `plan.get("steps")` bestaan: voor elke stap in `ctx.execution_plan` de `depends_on` uit de plan-step met dezelfde `step_index` overnemen en in de stap-dict zetten.

### _load_steps: merge bij elke aanroep
De while-loop in `_run_pipeline` herlaadt stappen via `_load_steps` bij elke iteratie. **Zorg dat _load_steps ook de depends_on-merge uitvoert**, niet alleen de job_steps-rijen ophaalt. Anders verlies je depends_on na de eerste wave.

- `_load_steps(job_id)` moet: (1) SELECT job_steps voor job_id ORDER BY step_index; (2) job payload/context laden; (3) plan.steps uitlezen en per step_index depends_on in de stap-dict mergen; (4) lijst van stap-dicts (met step_id, status, depends_on, …) retourneren.

### _mark_step_failed
Gebruik **step_id, niet step_index**: `UPDATE job_steps SET status='failed', error_log=$1, completed_at=now() WHERE id = $2`. Consistent met `_execute_step` (WHERE id).

---

## Run-instructie (onbeheerd)

1. Voer **fase 2, 3 en 4** uit conform het plan.
2. **Bij een blocker:** documenteer in `docs/260317_parallelle_agents_blockers.md` en ga door naar de volgende fase als die niet afhankelijk is van de blocker.
3. **Geen bevestiging tussen fasen** — voer alle fasen uit.
4. **Rapporteer alles in één overzicht** aan het einde.

### Wat je niet doet
- Geen wijzigingen buiten `nexus_pipeline.py`, `strategy_room.py`, `models/unified.py` — **uitzondering:** Fase 3 vereist één regel in `app/services/job_pipeline.py` (_insert_plan_steps: agent_id vullen).
- Geen nieuwe migraties.
- Geen aanraking van de data_query pipeline.
- `_execute_step` intern niet aanpassen, behalve agent_id en started_at (fase 3) indien nodig.

### Verificatie (later)
- Timestamp-overlap in job_steps controleren voor een job met twee onafhankelijke stappen.
- Sequentiële fallback testen op een plan zonder depends_on.

---

## Uitgevoerd overzicht (na run)

**Fase 2**
- `phase_2_planning`: na laden job_steps wordt job (payload/context) geladen en `_merge_depends_on_into_steps(ctx.execution_plan, job_context)` aangeroepen zodat elke stap `depends_on` heeft.
- `_load_steps(job_id)`: haalt job_steps op, laadt job context, voert dezelfde depends_on-merge uit en retourneert stap-dicts met step_id, status, depends_on, error_log.
- `_mark_step_failed(job_id, step_id, error)`: UPDATE job_steps SET status='failed', error_log=$, completed_at=now() WHERE id = $2 (step_id).
- `_get_next_wave(steps)`: pending-stappen waarvan deps completed zijn en agent_role niet al running.
- `_run_pipeline(ctx)`: while-loop met _load_steps per iteratie; wave bepalen; één stap of asyncio.gather; bij exception _mark_step_failed + _handle_pipeline_failure.
- `_handle_pipeline_failure(job_id, ctx, error_info)`: job op FAILED zetten.
- `_run_pipeline_sequential(ctx)`: bestaande for-loop.
- `phase_3_execution`: als `_is_parallel_ready(ctx.execution_plan)` dan `_run_pipeline(ctx)` anders `_run_pipeline_sequential(ctx)`.

**Fase 3**
- `_insert_plan_steps` (job_pipeline.py): kolom agent_id toegevoegd aan INSERT met waarde `agent:{step.agent_role}`.

**Fase 4**
- `_is_parallel_ready(steps)`: False als niet alle stappen `depends_on` hebben of circulaire dep (dep >= step_index).
- phase_3 roept parallel of sequential aan op basis van _is_parallel_ready.

**Blockers:** Geen (zie docs/260317_parallelle_agents_blockers.md).

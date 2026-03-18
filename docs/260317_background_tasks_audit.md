# BackgroundTasks audit — 260317

Alle `add_task`-aanroepen in de FastAPI-app. Aanbeveling: lichte taken (logging, korte DB-writes) mogen BackgroundTasks blijven; zware of externe-API-taken migreren naar een worker queue (Celery/ARQ).

## Vindplaatsen

| Bestand | Regel | Task / functie | Sync/async | Geschatte duur | Aanbeveling |
|---------|-------|----------------|------------|----------------|-------------|
| app/routes/jobs.py | 247 | run_intake_inline | async | 5–30 s | Naar queue — Anthropic |
| app/routes/jobs.py | 519 | run_intake_answers_inline | async | 5–30 s | Naar queue — Anthropic |
| app/routes/jobs.py | 621 | run_intake_answers_inline | async | 5–30 s | Naar queue — Anthropic |
| app/routes/jobs.py | 719 | run_data_pipeline | async | 10 s–min | Naar queue — data/API |
| app/routes/jobs.py | 759 | run_job_inline | async | 1–10 min | Naar queue — full pipeline/Anthropic |
| app/routes/jobs.py | 864 | run_intake_answers_inline | async | 5–30 s | Naar queue — Anthropic |
| app/routes/clients.py | 1251 | _process_datasource_background | async | 5–60 s | Naar queue — file/API |
| app/routes/clients.py | 1275 | _process_datasource_background | async | 5–60 s | Naar queue — file/API |
| app/routes/clients.py | 1344 | _run_file | async | 5–60 s | Naar queue — file processing |
| app/routes/hr.py | 635 | _run_start_training_safe | async | 1–10 min | Naar queue — training/API |
| app/routes/hr.py | 1113 | run_intake_inline | async | 5–30 s | Naar queue — Anthropic |
| app/routes/seo_upload.py | 254 | _process_seo_job | async | 10–120 s | Naar queue — SEO/API |
| app/routes/knowledge.py | 159 | run_embedding_task | async | 5–60 s | Naar queue — embedding API |
| app/routes/knowledge.py | 223 | run_embedding_task | async | 5–60 s | Naar queue — embedding API |
| app/routes/knowledge.py | 424 | reindex_document | async | 10–120 s | Naar queue — reindex |
| app/routes/knowledge.py | 657 | run_embedding_task | async | 5–60 s | Naar queue — embedding API |

## Queue-kandidaten (aanbevolen migratie)

- **Anthropic / pipeline:** run_intake_inline, run_intake_answers_inline, run_data_pipeline, run_job_inline
- **Embedding / reindex:** run_embedding_task, reindex_document
- **File / datasource:** _process_datasource_background, _run_file
- **Training:** _run_start_training_safe
- **SEO:** _process_seo_job

Alle bovenstaande kunnen > 1 s duren en/of externe API’s aanroepen. BackgroundTasks deelt dezelfde process/threadpool; bij veel gelijktijdige taken risico op uitputting of vertraging.

## Opmerking

- `app/services/job_pipeline.py` en `app/services/artifact_tracker.py` bevatten geen FastAPI `background_tasks.add_task`; de genoemde `add_task_cited_edges` is een methode op de tracker, geen BackgroundTask.

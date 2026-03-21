# 260321 — blockers (overnight resterende blokken)

## Blok F — console.log / console.warn (approve / handleApprove)

- `grep -rn "console\." web_ui/frontend/src/ --include="*.jsx" | grep -i "approve\|handleApprove"` → **geen treffers** (niets op één regel; geen `console.log`/`console.warn` in approve-paden in JSX).
- Extra check: alleen `console.log` in `Newbies.jsx` (niet approve-gerelateerd). **Geen verwijderingen nodig** voor deze scope.

## Blok H — Donna training (curl naar productie)

- Endpoint `POST /api/agents/{agent_id}/train` vereist **`require_super_admin`** (Bearer JWT).
- Curl **zonder** token zou **401** moeten geven; vanuit deze omgeving gaf `curl` **HTTP 000** (geen response — netwerk/proxy/sandbox), dus requests niet verifieerbaar hier.
- **Handmatig:** met super-admin token:
  `curl -X POST "https://wonderz-agentic.exe.xyz/api/agents/agent:c-suite:donna/train" -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"url":"..."}'`

---

## Blok 1 — `job_number` migratie (260321)

### Stap 1 — Supabase SQL (niet via Cursor)

- **Verificatie-query output:** niet uitgevoerd in deze omgeving — voer in Supabase SQL editor uit en noteer `COUNT(*)` / `COUNT(job_number)` zelf.
- **Naamgeving:** deze repo heeft al migratie `app/migrations/030_job_number_column.sql` met kolom **`job_number_int`** + sequence `jobs_job_number_seq`.  
  Als je in Supabase een **tweede** kolom `job_number` toevoegt (zoals in de prompt), kan dat **dubbel** zijn met `job_number_int` — controleer schema vóór je `ALTER TABLE ... job_number` draait.
- **Backend:** `_job_for_response` in `app/routes/jobs.py` leest nu **`job_number` voorkeur, anders `job_number_int`**; INSERT’s laten het nummer aan de DB-default over.

### Stap 3 — `journalctl` / restart

- `sudo systemctl restart wonderz-backend` kan hier wel; `journalctl` output hangt af van de VM.

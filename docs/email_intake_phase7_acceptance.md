# Email Intake Phase 7 — Acceptatiequeries

Na een geslaagde test-run (één email verwerkt tot job + stappen) kun je de volgende drie queries handmatig draaien. Hieronder de **verwachte output** op basis van die run.

---

## Query 1: Laatste 3 inbound_emails

```sql
SELECT email_id, status, job_id, completeness_score
FROM inbound_emails
ORDER BY created_at DESC
LIMIT 3;
```

**Verwachte output (voorbeeld na 1 geaccepteerde email):**

| email_id      | status    | job_id                               | completeness_score |
|---------------|-----------|--------------------------------------|--------------------|
| email:\<hash> | accepted  | \<uuid van de nieuwe job\>           | 0.82               |
| ...           | ...       | ...                                  | ...                |

- `email_id`: formaat `email:<message_id_hash>` (32 hex).
- `status`: `accepted` | `rejected_sender` | `pending` | `error`.
- `job_id`: UUID van de aangemaakte job, of NULL bij rejected/error.
- `completeness_score`: 0.0–1.0 bij accepted, anders NULL.

---

## Query 2: Laatste 3 jobs

```sql
SELECT id, status, intake_source, inbound_email_id
FROM jobs
ORDER BY created_at DESC
LIMIT 3;
```

**Verwachte output (voorbeeld):**

| id   | status        | intake_source | inbound_email_id |
|------|---------------|---------------|------------------|
| \<uuid\> | PLAN_PROPOSED | email         | email:\<hash\>   |
| ...  | ...           | browser       | NULL             |

- `id`: UUID van de job.
- `status`: `PLAN_PROPOSED` voor net aangemaakte email-jobs.
- `intake_source`: `email` voor deze flow, `browser` voor bestaande.
- `inbound_email_id`: `email:<hash>` van de gekoppelde inbound_emails rij, of NULL voor browser-jobs.

---

## Query 3: job_steps voor de job uit query 2

Vervang `<id uit query 2>` door de UUID van de email-job (eerste rij uit query 2).

```sql
SELECT job_id, step_index, agent_role, description
FROM job_steps
WHERE job_id = '<id uit query 2>'
ORDER BY step_index;
```

**Verwachte output (voorbeeld voor 1 CEO-step):**

| job_id  | step_index | agent_role | description        |
|---------|------------|------------|--------------------|
| \<uuid\> | 1          | copywriter | Blog 600 woorden   |

- Meerdere rijen als de CEO meerdere stappen heeft voorgesteld.
- `step_index`: 1, 2, 3, …
- `agent_role` / `description`: uit het CEO-plan (bijv. copywriter, reviewer).

---

## Controle

- Query 1: bij een geaccepteerde email hoort één rij met `status = accepted`, een niet-NULL `job_id` en een `completeness_score` tussen 0 en 1.
- Query 2: de bijbehorende job heeft `intake_source = 'email'` en `inbound_email_id` gelijk aan de `email_id` uit query 1.
- Query 3: voor die job bestaan één of meer `job_steps` met dezelfde `job_id`, oplopende `step_index` en ingevulde `agent_role` en `description`.

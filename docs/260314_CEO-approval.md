# 260314 — CEO Approval Gate voor Training
**Doel:** Implementeer de volledige CEO approval flow voor trainingsverzoeken, conform product spec v1.1 sectie 5.3 en 6.4.

---

## Context

Training van een agent kan nu direct gestart worden zonder toestemming. De spec vereist dat:
1. Een agent (of HR Manager) een trainingsverzoek indient via `POST /api/hr/training-request`.
2. De CEO dit verzoek ziet in een overzicht en goedkeurt of afwijst.
3. Alleen bij goedkeuring start de `TrainingWorkflow` automatisch.

De `training_requests` tabel en `POST /api/hr/approve-training` endpoint bestaan al. Het goedkeuringsscherm in de frontend ontbreekt nog.

---

## Pre-flight checks

Voer deze controles uit vóór je begint. Stop bij elke fout en meld wat er mis is.

```sql
-- (SQL) Supabase SQL editor
-- 1. Bestaat de training_requests tabel?
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'training_requests'
ORDER BY ordinal_position;

-- 2. Zijn er al verzoeken?
SELECT * FROM training_requests ORDER BY created_at DESC LIMIT 5;

-- 3. Bestaat de development_points tabel met status-kolom?
SELECT status, COUNT(*) FROM development_points GROUP BY status;
```

```bash
# (terminal) op de server
# 4. Bestaan de benodigde backend endpoints al?
grep -rn "training-request\|approve-training" app/routes/ --include="*.py"

# 5. Bestaat de TrainingWorkflow?
ls app/orchestrator/training_workflow.py 2>/dev/null || echo "ONTBREEKT"

# 6. Welke HR-routes zijn geregistreerd in main.py?
grep -n "hr" app/main.py
```

Rapporteer de output van alle zes checks vóór je verder gaat.

---

## Fase 1 — Backend: training-request endpoint verifiëren en uitbreiden

**Controleer** of `POST /api/hr/training-request` al correct werkt:

```python
# Verwacht gedrag:
# - Slaat verzoek op in training_requests met status 'PENDING'
# - Velden: request_id, agent_id, reason, confidence_score, suggested_url, status, created_at
# - Geeft { request_id, status: 'PENDING' } terug
```

Als het endpoint ontbreekt of incomplete is, maak/herstel het dan:

```python
# app/routes/hr.py — toevoegen aan bestaande router

@router.post("/training-request")
async def submit_training_request(body: dict, pool=Depends(get_pool)):
    async with pool.acquire() as conn:
        request_id = f"TR-{datetime.now().strftime('%Y-%m-%d')}-{str(uuid.uuid4())[:8].upper()}"
        await conn.execute("""
            INSERT INTO training_requests
                (request_id, agent_id, reason, confidence_score, suggested_url, status, created_at)
            VALUES ($1, $2, $3, $4, $5, 'PENDING', now())
            ON CONFLICT (request_id) DO NOTHING
        """,
            request_id,
            body.get("agent_id"),
            body.get("reason"),
            body.get("confidence_score"),
            body.get("suggested_url"),
        )
        return {"request_id": request_id, "status": "PENDING"}
```

**Controleer** of `POST /api/hr/approve-training` al correct werkt:

```python
# Verwacht gedrag bij approved=true:
# - Status training_request -> 'APPROVED'
# - approved_by + approved_at gevuld
# - TrainingWorkflow.start_training() aanroepen in background
# - development_point status -> 'IN_TRAINING' als er een gekoppeld point_id is

# Verwacht gedrag bij approved=false:
# - Status training_request -> 'REJECTED'
# - Optionele rejection_reason opslaan
```

Als het endpoint ontbreekt of incomplete is, herstel het conform bovenstaand gedrag.

**Acceptatiecriterium fase 1:**
```bash
# (terminal)
curl -X POST https://wonderz-agentic.exe.xyz/api/hr/training-request \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"agent_id": "agent:copywriter", "reason": "Test verzoek", "confidence_score": 0.4, "suggested_url": "https://example.com"}'
# Verwacht: { "request_id": "TR-...", "status": "PENDING" }

curl https://wonderz-agentic.exe.xyz/api/hr/training-requests \
  -H "Authorization: Bearer <token>"
# Verwacht: lijst met het zojuist aangemaakte verzoek
```

Stop hier. Rapporteer de curl-output vóór je naar fase 2 gaat.

---

## Fase 2 — Backend: GET /api/hr/training-requests endpoint

Voeg een lijst-endpoint toe als dat nog niet bestaat:

```python
@router.get("/training-requests")
async def get_training_requests(
    status: str = None,
    pool=Depends(get_pool)
):
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch("""
                SELECT tr.*, ha.agent_name, ha.role
                FROM training_requests tr
                JOIN hired_agents ha ON tr.agent_id = ha.agent_id
                WHERE tr.status = $1
                ORDER BY tr.created_at DESC
            """, status)
        else:
            rows = await conn.fetch("""
                SELECT tr.*, ha.agent_name, ha.role
                FROM training_requests tr
                JOIN hired_agents ha ON tr.agent_id = ha.agent_id
                ORDER BY tr.created_at DESC
            """)
        return {"training_requests": [dict(r) for r in rows], "count": len(rows)}
```

**Acceptatiecriterium fase 2:**
```bash
curl "https://wonderz-agentic.exe.xyz/api/hr/training-requests?status=PENDING" \
  -H "Authorization: Bearer <token>"
# Verwacht: { training_requests: [...], count: N }
```

Stop hier. Rapporteer de curl-output vóór je naar fase 3 gaat.

---

## Fase 3 — Frontend: Training Requests tab in HR Dashboard

Voeg een nieuwe tab "Trainingsverzoeken" toe aan `HRDashboard.jsx` (of een aparte pagina als de tab-structuur dat beter ondersteunt).

**Wat de tab toont:**

Een tabel met alle PENDING trainingsverzoeken:

| Agent | Rol | Reden | Confidence | Voorgestelde URL | Datum | Actie |
|---|---|---|---|---|---|---|
| Zoe | Support | Onvoldoende kennis Shopify 3.0 | 42% | shopify.dev/... | 14 mrt | Goedkeuren / Afwijzen |

**Gedrag Goedkeuren-knop:**
1. Toont een modal met:
   - Samenvatting van het verzoek (agent, reden, confidence score).
   - Invoerveld voor `source_url` (pre-filled met `suggested_url`, aanpasbaar).
   - Knoppen: "Goedkeuren" en "Annuleren".
2. Bij bevestigen: `POST /api/hr/approve-training` met `{ request_id, approved: true, source_url }`.
3. Na succes: rij verdwijnt uit de PENDING lijst (status is nu APPROVED).
4. Toon een inline succes-melding: "Training gestart voor [agent_name]".

**Gedrag Afwijzen-knop:**
1. Toont een simpele bevestigingsdialog: "Verzoek afwijzen? Dit kan niet ongedaan worden gemaakt."
2. Bij bevestigen: `POST /api/hr/approve-training` met `{ request_id, approved: false }`.
3. Na succes: rij verdwijnt uit de PENDING lijst.

**Lege state:**
Als er geen PENDING verzoeken zijn: "Geen openstaande trainingsverzoeken."

**Laadstate:**
Toon een spinner tijdens het ophalen en tijdens het verwerken van een actie. Geen dubbele klikken mogelijk terwijl een actie loopt.

**Regels:**
- Gebruik `useAuthReady` voor de initiële data fetch.
- Gebruik bestaande stijlen en componenten uit het HR Dashboard.
- Geen nieuwe dependencies installeren.
- Geen wijzigingen aan andere tabbladen of pagina's.

**Acceptatiecriterium fase 3:**
- Tab "Trainingsverzoeken" zichtbaar in HR Dashboard.
- Goedkeuren-modal opent met pre-filled URL.
- Na goedkeuren verdwijnt het verzoek uit de lijst.
- Na afwijzen verdwijnt het verzoek uit de lijst.
- Lege state toont correcte melding.

Stop hier. Rapporteer wat je hebt gebouwd vóór je naar fase 4 gaat.

---

## Fase 4 — Bouwen en deployen

```bash
# (terminal) op de server
cd ~/wonderz-agentics
git add -A && git commit -m "feat: CEO approval gate voor trainingsverzoeken"
git push origin main
cd web_ui/frontend && npm run build
sudo systemctl restart wonderz-backend
```

Test daarna handmatig:
1. Navigeer naar `/hr` → tab "Trainingsverzoeken".
2. Dien handmatig een test-verzoek in via curl (zie fase 1 acceptatiecriterium).
3. Ververs de pagina — verzoek zichtbaar?
4. Klik Goedkeuren — modal opent met URL-veld?
5. Bevestig — verzoek verdwijnt, succes-melding verschijnt?

Rapporteer de testresultaten.

---

## Wat je NIET doet

- Geen wijzigingen aan de bestaande `TrainingWorkflow` logica.
- Geen wijzigingen aan agent-training endpoints (`POST /api/agents/{id}/train`).
- Geen nieuwe tabellen aanmaken — `training_requests` bestaat al.
- Geen sidebar-aanpassingen — de HR-link staat al op `/hr`.
- Geen stijlwijzigingen buiten het nieuwe tabblad.

# HR Manager — Training Resource Discovery
**Datum:** 19 maart 2026
**Feature:** `hr_resource_discovery`
**Scope:** Backend + Frontend
**Prioriteit:** Medium

> Dit document is de authoritative bron voor deze Cursor-sessie. Bij twijfel: dit document prevaleert boven aannames.

---

## Context

De HR Manager detecteert al automatisch development points op basis van retry-patronen in `job_steps`. De nieuwe uitbreiding: de HR Manager zoekt zelf online naar trainingsmaterialen die aansluiten op een open development point, en zet die klaar ter goedkeuring. Na approve gaat de URL automatisch naar de training workflow.

**Bestaande flow (ongewijzigd):**
```
Development point open
    → CEO approval gate
    → Training workflow (scrape → chunk → embed → store)
```

**Nieuwe laag die we toevoegen:**
```
Development point open (impact = critical of high)
    → HR Manager: automatisch resource discovery starten
    → training_suggestions aanmaken (status: pending)
    → Gebruiker ziet suggesties in HR Dashboard
    → Approve / Reject
    → Bij approve: URL doorsturen naar bestaande training workflow
```

**Trigger-logica:**
- `critical` of `high` impact: discovery start automatisch na aanmaken development point
- `low` of `medium` impact: discovery start alleen via handmatige knop in UI

---

## Pre-flight checks (terminal + SQL)

Voer deze checks uit VOORDAT je ook maar één regel code schrijft. Stop bij elke fout en meld het.

```sql
-- (SQL) 1. Controleer hired_agents tabel
SELECT COUNT(*) FROM hired_agents LIMIT 1;

-- (SQL) 2. Controleer development_points tabel (of agent_improvements — zie noot)
SELECT column_name FROM information_schema.columns
WHERE table_name IN ('development_points', 'agent_improvements')
ORDER BY table_name, ordinal_position;

-- (SQL) 3. Controleer of training_suggestions al bestaat
SELECT to_regclass('public.training_suggestions');

-- (SQL) 4. Controleer bestaande HR endpoints in de codebase
```

```bash
# (terminal) Controleer bestaande HR routes
grep -r "hr" app/routers/ --include="*.py" -l
grep -r "training" app/routers/ --include="*.py" -l

# (terminal) Controleer of ANTHROPIC_API_KEY beschikbaar is in systemd override
sudo cat /etc/systemd/system/wonderz-backend.service.d/override.conf | grep ANTHROPIC
```

**Noot tabel-naamgeving:** De spec gebruikt `development_points`, de huidige implementatie gebruikt mogelijk `agent_improvements`. Gebruik de naam die al in productie staat. Pas de queries in dit document aan op de werkelijke naam. Doe dit NIET zelf — meld de naam eerst.

---

## Fase 1 — Database migratie

Bestandsnaam: `app/migrations/XXX_training_suggestions.sql`
Gebruik het volgende migratienummer als opvolger van de hoogste bestaande migratie.

```sql
CREATE TABLE IF NOT EXISTS training_suggestions (
  id              BIGSERIAL PRIMARY KEY,
  development_point_id BIGINT REFERENCES development_points(id) ON DELETE CASCADE,
  agent_id        TEXT REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
  url             TEXT NOT NULL,
  title           TEXT,
  rationale       TEXT,                          -- Waarom relevant voor dit development point
  discovered_by   TEXT DEFAULT 'hr-manager',
  status          TEXT DEFAULT 'pending'
                  CHECK (status IN ('pending', 'approved', 'rejected')),
  approved_by     TEXT,
  approval_notes  TEXT,
  discovered_at   TIMESTAMPTZ DEFAULT now(),
  reviewed_at     TIMESTAMPTZ
);

CREATE INDEX idx_training_suggestions_agent ON training_suggestions(agent_id);
CREATE INDEX idx_training_suggestions_status ON training_suggestions(status);
CREATE INDEX idx_training_suggestions_dp ON training_suggestions(development_point_id);
```

**Acceptatiecriteria fase 1:**
- [ ] Migratie draait zonder fouten in Supabase SQL editor
- [ ] `SELECT * FROM training_suggestions LIMIT 0;` werkt
- [ ] Foreign keys correct aangemaakt

Rapporteer na fase 1 en wacht op bevestiging.

---

## Fase 2 — Backend: discovery service

### 2.1 Nieuwe module: `app/services/hr_resource_discovery.py`

```python
"""
HR Manager — Training Resource Discovery
Zoekt online naar relevante trainingsmaterialen voor een development point.
Gebruikt Anthropic API met web_search tool.
"""

import json
import httpx
import asyncpg
from typing import Optional
from app.config import settings  # gebruik bestaand config pattern


class HRResourceDiscovery:

    async def discover_for_development_point(
        self,
        conn: asyncpg.Connection,
        development_point_id: int,
        agent_id: str,
        agent_role: str,
        pattern_description: str,
        impact: str,
    ) -> list[dict]:
        """
        Zoekt maximaal 3 relevante URLs voor een development point.
        Slaat resultaten op als training_suggestions (status: pending).
        Retourneert de aangemaakte suggestions.
        """
        # Bouw search query op basis van rol + patroon
        search_prompt = self._build_search_prompt(agent_role, pattern_description)

        # Claude API call met web_search tool
        results = await self._search_with_claude(search_prompt)

        if not results:
            return []

        # Sla op in training_suggestions
        suggestions = []
        for result in results[:3]:  # max 3 per discovery run
            row = await conn.fetchrow(
                """
                INSERT INTO training_suggestions
                  (development_point_id, agent_id, url, title, rationale, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                ON CONFLICT DO NOTHING
                RETURNING *
                """,
                development_point_id,
                agent_id,
                result["url"],
                result.get("title", ""),
                result.get("rationale", ""),
            )
            if row:
                suggestions.append(dict(row))

        return suggestions

    def _build_search_prompt(self, agent_role: str, pattern_description: str) -> str:
        return f"""
Je bent een HR Manager voor een AI-agent team. Je zoekt online naar de beste
trainingsmaterialen voor een agent met rol '{agent_role}' die last heeft van
het volgende patroon: "{pattern_description}".

Zoek naar maximaal 3 relevante, gezaghebbende online bronnen (documentatie,
tutorials, handleidingen) die een agent kunnen helpen dit patroon te verbeteren.

Geef je antwoord ALLEEN als JSON, zonder preamble of markdown backticks:
[
  {{
    "url": "https://...",
    "title": "Paginatitel",
    "rationale": "Waarom relevant voor dit development point (max 100 woorden)"
  }}
]

Kies alleen bronnen die:
- Publiek toegankelijk zijn
- Specifiek ingaan op de gedetecteerde gap
- Van een betrouwbare bron zijn (officiële docs, bekende platforms)
"""

    async def _search_with_claude(self, prompt: str) -> list[dict]:
        """
        Roept Anthropic API aan met web_search tool.
        Retourneert geparseerde lijst van {url, title, rationale}.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "web-search-2025-03-05",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-5-20250929",
                        "max_tokens": 1024,
                        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = response.json()

            # Extraheer text content uit response
            text_blocks = [
                block["text"]
                for block in data.get("content", [])
                if block.get("type") == "text"
            ]
            raw_text = "\n".join(text_blocks).strip()

            # Strip eventuele markdown backticks
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            return json.loads(raw_text)

        except Exception as e:
            # Discovery-fouten zijn non-critical: log en ga door
            print(f"[HRResourceDiscovery] discovery fout: {e}")
            return []
```

### 2.2 Trigger in bestaande HR manager

Zoek in de codebase waar development points worden aangemaakt (waarschijnlijk `app/agents/hr_manager.py` of `app/routers/hr.py`). Voeg na de INSERT van een development point het volgende toe:

```python
# Auto-trigger discovery voor critical en high impact
if impact in ("critical", "high"):
    from app.services.hr_resource_discovery import HRResourceDiscovery
    discovery = HRResourceDiscovery()
    await discovery.discover_for_development_point(
        conn=conn,
        development_point_id=new_point_id,
        agent_id=agent_id,
        agent_role=agent_role,
        pattern_description=pattern_description,
        impact=impact,
    )
```

**Belangrijk:** dit is een fire-and-forget achtergrondactie. Als de discovery faalt, mag het development point zelf NIET falen. Wrap in `try/except` als dat nog niet is gedaan.

**Acceptatiecriteria fase 2:**
- [ ] `HRResourceDiscovery` klasse bestaat en importeert zonder fouten
- [ ] Auto-trigger aanwezig bij critical/high development point aanmaak
- [ ] Fouten in discovery laten het aanmaken van het development point ongemoeid

Rapporteer na fase 2 en wacht op bevestiging.

---

## Fase 3 — Backend: API endpoints

Voeg toe aan het bestaande HR router bestand (gebruik het bestaande patroon voor auth/db).

```python
# GET /api/hr/training-suggestions
# Geeft alle pending suggestions terug, optioneel gefilterd op agent_id of status
@router.get("/training-suggestions")
async def get_training_suggestions(
    agent_id: Optional[str] = None,
    status: str = "pending",
    db=Depends(get_db),
    user=Depends(require_auth),
):
    query = """
        SELECT ts.*, ha.name as agent_name, ha.role as agent_role
        FROM training_suggestions ts
        JOIN hired_agents ha ON ts.agent_id = ha.agent_id
        WHERE ts.status = $1
    """
    params = [status]
    if agent_id:
        query += " AND ts.agent_id = $2"
        params.append(agent_id)
    query += " ORDER BY ts.discovered_at DESC"
    rows = await db.fetch(query, *params)
    return [dict(r) for r in rows]


# POST /api/hr/training-suggestions/{suggestion_id}/approve
@router.post("/training-suggestions/{suggestion_id}/approve")
async def approve_suggestion(
    suggestion_id: int,
    body: dict,  # {"approval_notes": "..."}
    db=Depends(get_db),
    user=Depends(require_auth),
):
    row = await db.fetchrow(
        """
        UPDATE training_suggestions
        SET status = 'approved',
            approved_by = $1,
            approval_notes = $2,
            reviewed_at = now()
        WHERE id = $3
        RETURNING *
        """,
        user["sub"],
        body.get("approval_notes", ""),
        suggestion_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Suggestion niet gevonden")

    # Stuur goedgekeurde URL door naar training workflow
    # Gebruik het bestaande CEO approval / training workflow patroon
    # Verwacht: training_workflow.start_training(agent_id, url, approved_by)
    suggestion = dict(row)
    try:
        from app.orchestration.training_workflow import TrainingWorkflow
        workflow = TrainingWorkflow()
        await workflow.start_training(
            agent_id=suggestion["agent_id"],
            url=suggestion["url"],
            approved_by=suggestion["approved_by"],
        )
    except Exception as e:
        print(f"[approve_suggestion] training start fout: {e}")
        # Approve staat al, training kan handmatig herstart worden

    return suggestion


# POST /api/hr/training-suggestions/{suggestion_id}/reject
@router.post("/training-suggestions/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: int,
    body: dict,  # {"approval_notes": "..."}
    db=Depends(get_db),
    user=Depends(require_auth),
):
    row = await db.fetchrow(
        """
        UPDATE training_suggestions
        SET status = 'rejected',
            approval_notes = $1,
            reviewed_at = now()
        WHERE id = $2
        RETURNING *
        """,
        body.get("approval_notes", ""),
        suggestion_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Suggestion niet gevonden")
    return dict(row)


# POST /api/hr/training-suggestions/discover
# Handmatige trigger voor low/medium development points
@router.post("/training-suggestions/discover")
async def manual_discover(
    body: dict,  # {"development_point_id": int, "agent_id": str, "agent_role": str, "pattern_description": str}
    db=Depends(get_db),
    user=Depends(require_auth),
):
    from app.services.hr_resource_discovery import HRResourceDiscovery
    discovery = HRResourceDiscovery()
    suggestions = await discovery.discover_for_development_point(
        conn=db,
        development_point_id=body["development_point_id"],
        agent_id=body["agent_id"],
        agent_role=body["agent_role"],
        pattern_description=body["pattern_description"],
        impact="manual",
    )
    return {"discovered": len(suggestions), "suggestions": suggestions}
```

**Acceptatiecriteria fase 3:**
- [ ] `GET /api/hr/training-suggestions` retourneert correct JSON
- [ ] `POST /api/hr/training-suggestions/{id}/approve` update status naar `approved`
- [ ] `POST /api/hr/training-suggestions/{id}/reject` update status naar `rejected`
- [ ] `POST /api/hr/training-suggestions/discover` triggert discovery en retourneert resultaten
- [ ] Approve roept bestaande training workflow aan

Rapporteer na fase 3 en wacht op bevestiging.

---

## Fase 4 — Frontend: Training Suggestions paneel in HR Dashboard

Voeg een nieuw tabblad of sectie toe aan het bestaande `HRDashboard.jsx` component.

### 4.1 Vereisten

- Toon lijst van `pending` training suggestions
- Per suggestion: agent naam + rol, URL (klikbaar), titel, rationale, development point referentie
- Twee knoppen per rij: **Approve** en **Reject**
- Na approve of reject: rij verdwijnt uit de pending lijst
- Handmatige trigger-knop per development point (zichtbaar bij low/medium impact punten): "Zoek bronnen"
- `useAuthReady` guard is verplicht (zie platform-standaard)
- Geen polling nodig: simpele fetch bij mount + na elke approve/reject

### 4.2 Componentstructuur

```
HRDashboard.jsx
  └── TrainingSuggestions.jsx  (nieuw subcomponent)
        ├── SuggestionRow.jsx  (optioneel, of inline)
        └── useTrainingSuggestions.js  (hook voor fetch + actions)
```

### 4.3 API calls

```javascript
// Fetch pending suggestions
GET /api/hr/training-suggestions?status=pending

// Approve
POST /api/hr/training-suggestions/{id}/approve
Body: { "approval_notes": "" }

// Reject
POST /api/hr/training-suggestions/{id}/reject
Body: { "approval_notes": "" }

// Handmatige discovery
POST /api/hr/training-suggestions/discover
Body: {
  "development_point_id": 123,
  "agent_id": "agent:copywriter:forrest-001",
  "agent_role": "copywriter",
  "pattern_description": "Tekst te formeel bij B2C doelgroep"
}
```

### 4.4 UI staat

| State | Weergave |
|-------|----------|
| Loading | Spinner of skeleton |
| Geen pending suggestions | "Geen openstaande suggesties." |
| Suggestions aanwezig | Tabel met rijen |
| Discovery bezig | Knop disabled + "Zoeken..." label |
| Approve/reject bezig | Knoppen disabled tijdens request |

**Acceptatiecriteria fase 4:**
- [ ] Pending suggestions zijn zichtbaar in HR Dashboard
- [ ] Approve knop update status en verwijdert rij
- [ ] Reject knop update status en verwijdert rij
- [ ] "Zoek bronnen" knop triggert handmatige discovery voor low/medium punten
- [ ] `useAuthReady` guard aanwezig in useEffect
- [ ] Geen `console.log` statements in eindcode

Rapporteer na fase 4 en wacht op bevestiging.

---

## Wat je NIET doet

- Geen wijzigingen aan de bestaande training workflow logica
- Geen wijzigingen aan het CEO approval gate systeem
- Niet de `development_points` / `agent_improvements` tabel aanpassen
- Geen nieuwe routes aanmaken buiten het bestaande HR router bestand
- Geen `git add -A` — stage altijd specifieke bestanden
- Geen meerdere fases tegelijk uitvoeren — wacht op bevestiging per fase
- Niet `is_active` of `is_suspended` aanraken
- Geen Vercel deploy suggeren — frontend bouwt server-side via `npm run build`

---

## Deployment na afronding

```bash
# (terminal) Vanuit ~/wonderz-agentics:
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```

---

## Acceptatiecriteria totaal

- [ ] `training_suggestions` tabel aangemaakt en bereikbaar
- [ ] Auto-discovery triggert bij critical/high development point
- [ ] Handmatige discovery werkt via UI-knop
- [ ] Suggesties zichtbaar in HR Dashboard
- [ ] Approve stuurt URL door naar training workflow
- [ ] Reject markeert als afgewezen zonder verdere actie
- [ ] Fouten in discovery breken geen bestaande functionaliteit
- [ ] Alle vier API endpoints werken correct

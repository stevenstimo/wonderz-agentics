# 260320 — Skill Factory: /knowledge/skills pagina + nieuwe skill form

**Datum:** 20 maart 2026
**Feature:** `skill_factory`
**Scope:** Backend (skills API) + Frontend (/knowledge/skills overzicht + /knowledge/skills/new formulier) + routing bugfix

> Dit document is de authoritative bron voor deze Cursor-sessie. Bij twijfel: dit document prevaleert boven aannames.

---

## Context

Er is een routing-bug: de knop "Nieuwe Skill Spec" stuurt de gebruiker naar `/knowledge/upload`, waardoor een upload in de `agent_knowledge` vectorstore terechtkomt. Dat is de Knowledge-laag, niet de Skills-laag.

Skills zijn geen uploads en geen vectorstore-chunks. Een skill is een geregistreerd object met naam, trigger-conditie en dependencies, opgeslagen in een aparte `skills` tabel. De `hired_agents.skills[]` array verwijst naar die records.

**Gewenste eindstaat:**
```
Knop "Nieuwe Skill Spec"
    → navigeert naar /knowledge/skills/new (formulier)
    → NIET naar /knowledge/upload

/knowledge/skills
    → overzichtslijst van alle geregistreerde skills
    → per skill: naam, trigger_condition, dependencies, gekoppelde agents, status
    → knop "+ Nieuwe skill" → /knowledge/skills/new

/knowledge/skills/new
    → formulier: naam, trigger-conditie, dependencies (tools + skills), agent koppelen
    → POST /api/skills → skill opgeslagen in skills tabel
    → na opslaan: terug naar /knowledge/skills
```

---

## Pre-flight checks — verplicht vóór elke code

Voer deze checks uit en rapporteer de uitkomst per stap. Stop bij een onverwacht resultaat.

```bash
# (terminal) 1. Bestaat er al een skills tabel of skills-route?
grep -r "skills" app/routes/ --include="*.py" -l
grep -r "/api/skills\|/skills" app/routes/ --include="*.py" -n | head -20
```

```sql
-- (SQL) 2. Bestaat de skills tabel al?
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'skills';

-- (SQL) 3. Als de tabel bestaat: toon kolommen
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'skills'
ORDER BY ordinal_position;

-- (SQL) 4. Hoe zien de huidige hired_agents.skills eruit?
SELECT agent_id, skills FROM hired_agents
WHERE skills != '[]'::jsonb
LIMIT 5;
```

```bash
# (terminal) 5. Zoek de knop "Nieuwe Skill Spec" in de frontend
grep -r "Nieuwe Skill\|skill.*upload\|knowledge/upload" web_ui/frontend/src/ --include="*.jsx" --include="*.tsx" -n

# (terminal) 6. Wat zijn de bestaande routes in de frontend router?
grep -r "knowledge" web_ui/frontend/src/ --include="*.jsx" --include="*.tsx" -n | grep -i "route\|path\|navigate" | head -20

# (terminal) 7. Welk component rendert /knowledge/skills (als het al bestaat)?
grep -r "knowledge/skills\|SkillFactory\|Skills" web_ui/frontend/src/ --include="*.jsx" --include="*.tsx" -n | head -20
```

**Rapporteer:**
- Of de `skills` tabel al bestaat en zo ja: alle kolommen
- Hoe `hired_agents.skills` er nu uitziet (JSONB strings of objecten)
- Exact bestand + regelnummer van de "Nieuwe Skill Spec" knop
- Of `/knowledge/skills` al een route heeft

Stop hier en wacht op bevestiging vóór fase 1.

---

## Fase 1 — Backend: skills tabel + API endpoints

### 1.1 Database migratie

**Alleen uitvoeren als de skills tabel nog niet bestaat (check pre-flight stap 2).**

Maak het migratiebestand aan:

**Bestand:** `app/migrations/XXX_skills.sql` (gebruik het eerstvolgende migratienummer)

```sql
CREATE TABLE IF NOT EXISTS skills (
  skill_id        TEXT PRIMARY KEY,           -- skill:write_landing_page
  name            TEXT NOT NULL UNIQUE,       -- 'write_landing_page'
  display_name    TEXT NOT NULL,              -- 'Write Landing Page'
  description     TEXT,
  trigger_condition TEXT,                     -- wanneer activeert CEO deze skill?
  requires_tools  TEXT[] DEFAULT '{}',        -- ['web_search', 'read_url']
  requires_skills TEXT[] DEFAULT '{}',        -- ['icp-definition']
  status          TEXT DEFAULT 'active'
                  CHECK (status IN ('active', 'inactive', 'draft')),
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
```

Draai de migratie via Shelley (psql op de server). Geen Supabase SQL editor.

### 1.2 Backend routes

**Bestand:** `app/routes/skills.py` (nieuw bestand)

```python
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_pool
import re

router = APIRouter(prefix="/api/skills", tags=["skills"])

def _slugify(name: str) -> str:
    """Genereert skill_id uit naam: 'Write Landing Page' → 'skill:write_landing_page'"""
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    return f"skill:{slug}"

@router.get("")
async def list_skills(pool=Depends(get_pool)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.*,
                   COALESCE(
                       (SELECT array_agg(ha.agent_id)
                        FROM hired_agents ha
                        WHERE ha.skills @> to_jsonb(ARRAY[s.name])),
                       '{}'
                   ) as linked_agents
            FROM skills s
            ORDER BY s.created_at DESC
        """)
        return [dict(r) for r in rows]

@router.post("")
async def create_skill(body: dict, pool=Depends(get_pool)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is verplicht")

    skill_id = _slugify(name)

    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT skill_id FROM skills WHERE name = $1", name
        )
        if existing:
            raise HTTPException(409, f"Skill '{name}' bestaat al")

        await conn.execute("""
            INSERT INTO skills
              (skill_id, name, display_name, description,
               trigger_condition, requires_tools, requires_skills, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
            skill_id,
            name,
            body.get("display_name") or name,
            body.get("description") or "",
            body.get("trigger_condition") or "",
            body.get("requires_tools") or [],
            body.get("requires_skills") or [],
            body.get("status") or "active",
        )

        # Optioneel: koppel direct aan agent(en) als agent_ids meegegeven
        agent_ids = body.get("agent_ids") or []
        for agent_id in agent_ids:
            await conn.execute("""
                UPDATE hired_agents
                SET skills = skills || to_jsonb($1::text),
                    updated_at = now()
                WHERE agent_id = $2
                  AND NOT (skills @> to_jsonb(ARRAY[$1]))
            """, name, agent_id)

        return {"skill_id": skill_id, "name": name, "status": "created"}

@router.get("/{skill_id}")
async def get_skill(skill_id: str, pool=Depends(get_pool)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM skills WHERE skill_id = $1", skill_id
        )
        if not row:
            raise HTTPException(404, "Skill niet gevonden")
        return dict(row)

@router.patch("/{skill_id}")
async def update_skill(skill_id: str, body: dict, pool=Depends(get_pool)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM skills WHERE skill_id = $1", skill_id
        )
        if not row:
            raise HTTPException(404, "Skill niet gevonden")

        await conn.execute("""
            UPDATE skills SET
              display_name      = COALESCE($2, display_name),
              description       = COALESCE($3, description),
              trigger_condition = COALESCE($4, trigger_condition),
              requires_tools    = COALESCE($5, requires_tools),
              requires_skills   = COALESCE($6, requires_skills),
              status            = COALESCE($7, status),
              updated_at        = now()
            WHERE skill_id = $1
        """,
            skill_id,
            body.get("display_name"),
            body.get("description"),
            body.get("trigger_condition"),
            body.get("requires_tools"),
            body.get("requires_skills"),
            body.get("status"),
        )
        return {"skill_id": skill_id, "status": "updated"}
```

### 1.3 Registreer router in main.py

```python
# app/main.py — voeg toe bij de andere router imports
from app.routes.skills import router as skills_router
app.include_router(skills_router)
```

**Acceptatiecriteria fase 1:**
- [ ] `GET /api/skills` geeft lege lijst terug (geen 500)
- [ ] `POST /api/skills` met `{ "name": "test_skill_001" }` geeft `{ skill_id, name, status: "created" }` terug
- [ ] `GET /api/skills` geeft het zojuist aangemaakte record terug
- [ ] `POST /api/skills` met dezelfde naam geeft 409 terug
- [ ] Record staat in de `skills` tabel via SQL check

```bash
# (terminal) verificatie
curl https://wonderz-agentic.exe.xyz/api/skills \
  -H "Authorization: Bearer <token>"
```

Stop na fase 1 en rapporteer.

---

## Fase 2 — Frontend: SkillFactory overzichtspagina

**Bestand:** `web_ui/frontend/src/pages/SkillFactory.jsx` (nieuw)

### 2.1 Wat de pagina doet

- Haalt alle skills op via `GET /api/skills`
- Toont een lijst/tabel van geregistreerde skills
- Per skill: display_name, skill_id (als badge), status, aantal gekoppelde agents, trigger_condition (ingekort)
- Lege state: "Nog geen skills geregistreerd. Maak je eerste skill aan."
- Knop "+ Nieuwe skill" rechtsboven → navigeert naar `/knowledge/skills/new`
- Klik op een skill → uitklapbaar detail (of modal) met alle velden inclusief requires_tools en requires_skills

### 2.2 Component structuur

```jsx
// web_ui/frontend/src/pages/SkillFactory.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthReady } from '../hooks/useAuthReady'; // bestaande hook

export default function SkillFactory() {
  const [skills, setSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const navigate = useNavigate();
  const { authReady, session } = useAuthReady();

  useEffect(() => {
    if (!authReady) return;
    fetchSkills();
  }, [authReady]);

  const fetchSkills = async () => {
    // GET /api/skills met Authorization header
    // Sla op in setSkills
    // setLoading(false) in finally
  };

  // Render: header met titel + "+ Nieuwe skill" knop
  // Lege state als skills.length === 0
  // Tabel/lijst als er skills zijn
  // Expandable detail per rij
}
```

### 2.3 Stijl

Gebruik de bestaande design-conventies van het platform:
- Dezelfde achtergrondkleur, padding, header-stijl als andere Knowledge-pagina's (`/knowledge`, `/knowledge/upload`)
- Tabel met lichte striping (elke andere rij licht grijs)
- Status badge: `active` = groen pill, `inactive` = grijs pill, `draft` = geel pill
- `skill_id` als klein monospace label naast de naam
- "+ Nieuwe skill" knop: primaire stijl (paars/indigo, zelfde als andere primaire knoppen in het platform)
- Geen nieuwe CSS-classes aanmaken als bestaande herbruikbaar zijn

### 2.4 Routing

Voeg de route toe in het bestaande router-bestand (check waar `/knowledge` en `/knowledge/upload` geregistreerd zijn):

```jsx
// Bestaand patroon — voeg toe:
<Route path="/knowledge/skills" element={<SkillFactory />} />
<Route path="/knowledge/skills/new" element={<NewSkillForm />} />
```

**Acceptatiecriteria fase 2:**
- [ ] `/knowledge/skills` laadt zonder errors
- [ ] Lege state zichtbaar bij geen skills
- [ ] Na fase 1 test-skill is zichtbaar in de lijst
- [ ] "+ Nieuwe skill" knop navigeert naar `/knowledge/skills/new` (pagina hoeft nog niet te bestaan)
- [ ] `useAuthReady` guard aanwezig
- [ ] Geen console errors

Stop na fase 2 en rapporteer.

---

## Fase 3 — Frontend: Nieuwe skill formulier

**Bestand:** `web_ui/frontend/src/pages/NewSkillForm.jsx` (nieuw)

### 3.1 Formuliervelden

| Veld | Type | Verplicht | Toelichting |
|------|------|-----------|-------------|
| Naam | Text input | Ja | snake_case identifier, bijv. `write_landing_page`. Automatisch lowercase + underscores bij typen. |
| Weergavenaam | Text input | Nee | Mensleesbare naam, bijv. "Write Landing Page". Auto-filled vanuit naam als leeg. |
| Beschrijving | Textarea | Nee | Wat doet deze skill? |
| Trigger-conditie | Textarea | Nee | Wanneer activeert de CEO deze skill? |
| Vereiste tools | Multi-select of tag-input | Nee | Kies uit bekende tools (zie lijst hieronder) of typ vrij. |
| Vereiste skills | Tag-input | Nee | Typ een skill-naam. Autocomplete op bestaande skills. |
| Koppel aan agent | Multi-select | Nee | Dropdown van actieve agents via `GET /api/agents`. |
| Status | Dropdown | Ja | `active` (default), `draft`, `inactive`. |

**Bekende tools voor multi-select (hardcoded lijst):**
```
knowledge_retrieval, search_internal_docs, read_lessons,
write_copy, write_report, write_feedback,
read_brief, read_product, read_analytics, read_artifact,
validate_output, check_evidence, score_confidence, approve_artifact,
web_search, search_web, read_url,
submit_artifact, flag_escalation, create_development_point,
read_logs, read_metrics, execute_query
```

### 3.2 Submit gedrag

```javascript
// POST /api/skills
{
  name: "write_landing_page",
  display_name: "Write Landing Page",
  description: "...",
  trigger_condition: "...",
  requires_tools: ["web_search"],
  requires_skills: ["icp-definition"],
  agent_ids: ["agent:copywriter:forrest-gump-001"],
  status: "active"
}
```

Na succesvolle POST: `navigate('/knowledge/skills')` met een succes-toast/melding.
Bij 409 (naam bestaat al): inline foutmelding onder het naam-veld.
Bij andere fout: algemene foutmelding bovenaan het formulier.

### 3.3 Validatie (client-side)

- Naam is verplicht
- Naam mag alleen lowercase letters, cijfers en underscores bevatten: `/^[a-z0-9_]+$/`
- Naam mag niet beginnen of eindigen met underscore
- Foutmelding direct zichtbaar onder het veld (niet alleen bij submit)

### 3.4 UX details

- Formulier heeft een "Annuleren" knop naast "Opslaan" — annuleren navigeert terug naar `/knowledge/skills`
- Tijdens submit: knop disabled + spinner
- Naam-veld: bij blur auto-format naar lowercase + spaties vervangen door underscores
- `useAuthReady` guard verplicht

**Acceptatiecriteria fase 3:**
- [ ] Formulier laadt op `/knowledge/skills/new`
- [ ] Naam-validatie werkt client-side
- [ ] Submit POST naar `/api/skills`
- [ ] Na succes: redirect naar `/knowledge/skills`, nieuwe skill zichtbaar in lijst
- [ ] 409 toont inline fout op naam-veld
- [ ] Annuleren werkt
- [ ] `useAuthReady` guard aanwezig
- [ ] Geen console errors

Stop na fase 3 en rapporteer.

---

## Fase 4 — Routing bugfix: "Nieuwe Skill Spec" knop

**Doel:** De bestaande knop "Nieuwe Skill Spec" die nu naar `/knowledge/upload` wijst, corrigeren naar `/knowledge/skills/new`.

Zoek het bestand en de exacte regel via de pre-flight check (stap 5). Vervang alleen de route/navigate-waarde. Raak de rest van het component niet aan.

```jsx
// VOOR (fout):
navigate('/knowledge/upload')
// of: href="/knowledge/upload"
// of: to="/knowledge/upload"

// NA (correct):
navigate('/knowledge/skills/new')
// of: href="/knowledge/skills/new"
// of: to="/knowledge/skills/new"
```

**Acceptatiecriteria fase 4:**
- [ ] Knop "Nieuwe Skill Spec" navigeert naar `/knowledge/skills/new`
- [ ] `/knowledge/upload` werkt nog steeds correct voor knowledge-uploads
- [ ] Geen andere wijzigingen in het betreffende component

Stop na fase 4 en rapporteer.

---

## Wat je NIET doet

- Geen `git add -A` — stage altijd specifieke bestanden
- Geen Vercel deploy-suggesties
- Geen WebSocket implementeren
- Geen wijzigingen aan `agent_knowledge` tabel of vectorstore-logica
- Geen wijzigingen aan `/knowledge/upload` flow
- Geen nieuwe npm packages installeren zonder expliciete goedkeuring
- Niet meerdere fases tegelijk uitvoeren
- Geen flat routing — gebruik het bestaande nested routing patroon (Layout + Outlet)
- Niet de `hired_agents.skills[]` array loskoppelen van de nieuwe `skills` tabel — bij skill aanmaken via het formulier worden beide bijgewerkt

---

## Deployment na afronding alle fases

```bash
# (terminal) vanuit ~/wonderz-agentics
git add app/routes/skills.py app/main.py app/migrations/XXX_skills.sql
git add web_ui/frontend/src/pages/SkillFactory.jsx
git add web_ui/frontend/src/pages/NewSkillForm.jsx
git add <bestand met routing bugfix>
git commit -m "feat: Skill Factory pages + skills API + routing bugfix"
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```

---

## Acceptatiecriteria totaal

- [ ] `GET /api/skills` werkt
- [ ] `POST /api/skills` maakt skill aan in `skills` tabel
- [ ] `/knowledge/skills` toont overzicht van alle skills
- [ ] `/knowledge/skills/new` toont formulier
- [ ] Nieuwe skill aanmaken via formulier werkt end-to-end
- [ ] Knop "Nieuwe Skill Spec" stuurt naar `/knowledge/skills/new` (niet naar `/knowledge/upload`)
- [ ] `/knowledge/upload` werkt nog steeds voor knowledge-uploads
- [ ] Geen regressions op bestaande pagina's

# CURSOR — CEO Dashboard + Newbies Lifecycle + Navigatie
**Datum:** 18 maart 2026
**Refs:** docs/framework/260317_crew_intelligent_agent_framework.md

---

## Context

Lees eerst:
- `docs/framework/260317_crew_intelligent_agent_framework.md` (architectuur, C-suite structuur)
- `docs/cursor/00_master_index.md` (fasering en status)

Dit zijn drie samenhangende wijzigingen die in één Cursor sessie 
worden uitgevoerd. Werk fase voor fase. Stop na elke fase en 
rapporteer voordat je doorgaat.

---

## Wat je NIET doet

- Geen migrations op `hired_agents` of `agent_knowledge`
- Geen wijzigingen aan de job flow of NEXUS pipeline
- Geen wijzigingen aan bestaande agent endpoints behalve wat hieronder staat
- Geen nieuwe dependencies installeren zonder te melden
- Nooit meerdere fasen tegelijk uitvoeren

---

## Fase A — Newbies lifecycle (backend)

### A.1 Wat het probleem is

De `newbies` tabel bestaat en is leeg. De 49 personas zitten in 
`hired_agents` met `is_active = false`. Dit is architectureel incorrect.

Een NewBie is een kandidaat in opleiding — nog niet operationeel.
Een Agent is operationeel en staat in `hired_agents`.

De juiste lifecycle is:

Persona → NewBie (newbies tabel) → training → readiness ≥ 70 
→ promoveren → hired_agents (is_active = true)

### A.2 Tabelstructuur controleren

Voer uit in Supabase SQL editor:

SELECT column_name FROM information_schema.columns
WHERE table_name = 'newbies' ORDER BY ordinal_position;

Voeg toe als kolommen ontbreken:

ALTER TABLE newbies
  ADD COLUMN IF NOT EXISTS type TEXT 
    CHECK (type IN ('worker','talent','orchestrator')),
  ADD COLUMN IF NOT EXISTS role TEXT,
  ADD COLUMN IF NOT EXISTS persona_source TEXT,
  ADD COLUMN IF NOT EXISTS readiness_score INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'in_training'
    CHECK (status IN ('in_training','ready','promoted')),
  ADD COLUMN IF NOT EXISTS development_priority TEXT,
  ADD COLUMN IF NOT EXISTS badge TEXT;

### A.3 Migratie hired_agents naar newbies

INSERT INTO newbies (
  newbie_id, newbie_name, type, role, persona_source,
  readiness_score, status, created_at, updated_at
)
SELECT agent_id, name, type, role, persona_source,
  readiness_score, 'in_training', created_at, updated_at
FROM hired_agents
WHERE is_active = false
ON CONFLICT (newbie_id) DO NOTHING;

DELETE FROM hired_agents WHERE is_active = false;

Stop hier. Rapporteer hoeveel rijen gemigreerd en verwijderd.
Wacht op bevestiging.

### A.4 Endpoints controleren en aanvullen

Controleer:
- GET /api/newbies — alle newbies gesorteerd op updated_at
- GET /api/newbies/ready — readiness ≥ 70 en status = 'ready'
- GET /api/newbies/{newbie_id} — één newbie

Voeg toe als het ontbreekt:
POST /api/newbies/{newbie_id}/promote
- Zet status = 'promoted' in newbies
- Maakt nieuw hired_agents record aan met is_active = true
- Kopieert alle relevante velden
- Geeft nieuw agent record terug

Acceptatiecriteria Fase A:
- newbies tabel heeft 49 rijen
- hired_agents heeft alleen is_active = true records
- GET /api/newbies geeft 49 newbies terug
- GET /api/newbies/ready werkt correct
- POST /api/newbies/{id}/promote werkt correct

**Stop hier. Rapporteer. Wacht op bevestiging.**

---

## Fase B — CEO Dashboard

### B.1 Huidige situatie

Dashboard toont "Start New Project" formulier.
Verplaats dit naar Developer Bot pagina. Niet verwijderen.

### B.2 Vier blokken

Blok 1 — Crew Status:
- Actieve agents (hired_agents is_active = true)
- NewBies in training (newbies status = 'in_training')
- NewBies klaar (newbies status = 'ready')
- Gesuspendeerd (hired_agents is_suspended = true)

Blok 2 — Operationeel vandaag:
- Jobs lopend (status = 'RUNNING')
- Jobs voltooid vandaag (status = 'COMPLETED', today)
- Wachten op goedkeuring (status = 'JOB_READY')
- Fouten (status = 'FAILED' of 'BUDGET_EXCEEDED')

Blok 3 — Agent Health:
- Open development points (status = 'open')
- Training verzoeken open (status = 'training_requested')
- Agents met meer dan 3 open development points

Blok 4 — Recente activiteit:
- Laatste 5 voltooide jobs
- Laatste 3 development points aangemaakt

### B.3 Backend endpoint

Nieuw bestand: app/routes/dashboard.py
Endpoint: GET /api/dashboard/ceo
Registreer in app/main.py

Response schema:
{
  "crew_status": { "active_agents": 0, "newbies_in_training": 0,
    "newbies_ready": 0, "suspended_agents": 0 },
  "operational": { "jobs_running": 0, "jobs_completed_today": 0,
    "jobs_awaiting_approval": 0, "jobs_failed": 0 },
  "agent_health": { "open_development_points": 0,
    "training_requests_open": 0, "high_retry_agents": [] },
  "recent_activity": { "recent_jobs": [], "recent_development_points": [] }
}

### B.4 Frontend

- Vervang Dashboard inhoud door CEO Dashboard component
- Data van GET /api/dashboard/ceo
- Vier metric card blokken
- Auto-refresh elke 60 seconden
- Loading state en foutmelding
- Groen = goed, amber = aandacht, rood = actie vereist

Acceptatiecriteria Fase B:
- Vier blokken met live data
- Getallen kloppen met DB
- Auto-refresh werkt
- Start New Project verplaatst naar Developer Bot
- Mobiel responsive

Stop hier. Rapporteer. Wacht op bevestiging.

---

## Fase C — Navigatie

### C.1 Nieuwe structuur

WORKSPACE: Dashboard, Inbox, Job Center, Mission Control
OPERATIONS: Crew, Newbies, Hiring Hall
DEVELOPMENT: Training Hub, HR (Improvements als tab erin)
GOVERNANCE: COO Approval (hernoemd), Agents

### C.2 Wijzigingen

1. CEO Approval → COO Approval in sidebar
2. Improvements als tab in HR, redirect /improvements → /hr
3. MANAGEMENT → OPERATIONS, nieuwe secties DEVELOPMENT en GOVERNANCE
4. Agents van MANAGEMENT naar GOVERNANCE

### C.3 Niet wijzigen

- Geen pagina-inhoud
- Geen routes verwijderen, alleen redirects
- Geen nieuwe pagina's

Acceptatiecriteria Fase C:
- Sidebar toont OPERATIONS, DEVELOPMENT, GOVERNANCE
- COO Approval correct hernoemd
- Improvements in HR samengevoegd
- Alle pagina's bereikbaar
- Geen broken links

Stop hier. Rapporteer. Wacht op bevestiging.

---

## Deploy na alle fasen

```bash
cd ~/wonderz-agentics
git add -A
git commit -m "feat: CEO dashboard, newbies lifecycle, navigation restructure"
git push
sudo systemctl restart wonderz-backend
cd web_ui/frontend && npm run build
```

---

*Spec: docs/framework/260317_crew_intelligent_agent_framework.md*
*Master index: docs/cursor/00_master_index.md*

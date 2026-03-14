# CURSOR PROMPTS: Openstaande fases
**Datum:** 260314  
**Project:** Crew Intelligent / Wonderz-Agentics  
**Uitvoervolgorde:** Fase A eerst, daarna B, C, D.  
**Voer per fase apart uit. Vraag na elke fase bevestiging voor je doorgaat.**

---

# FASE A: CEO Approval Gate Training

## Context
De HR Manager detecteert verbeterpunten via `scan_job_steps` en maakt `development_points` aan. Als een development point training vereist, moet de CEO dit goedkeuren voordat training start. Dit is de governance-laag tussen HR analyse en het starten van `TrainingWorkflow`.

Flow:
```
HR Manager maakt development_point aan (status: OPEN)
  → HR Manager zet status op AWAITING_APPROVAL
  → CEO ziet open verzoeken in UI
  → CEO keurt goed (optioneel: source_url meegeven) of wijst af
  → Bij goedkeuring: status IN_TRAINING, TrainingWorkflow start
  → Bij afwijzing: status DISMISSED
```

## Pre-flight
```sql
-- Verifieer development_points tabel
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'development_points' ORDER BY ordinal_position;

-- Verifieer dat TrainingWorkflow beschikbaar is
-- Zoek in codebase naar: TrainingWorkflow, start_training, agent_knowledge
```

## Backend

### app/routes/hr.py — voeg toe aan bestaand HR router bestand

```python
from pydantic import BaseModel
from typing import Optional

class ApproveTrainingRequest(BaseModel):
    approved: bool
    source_url: Optional[str] = None
    rejection_reason: Optional[str] = None


# POST /api/hr/development-points/{point_id}/submit-for-approval
# HR Manager zet een OPEN point op AWAITING_APPROVAL
@router.post("/development-points/{point_id}/submit-for-approval")
async def submit_for_approval(point_id: str, request: Request, user=Depends(get_current_user)):
    async with request.app.state.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE development_points
            SET status = 'AWAITING_APPROVAL'
            WHERE point_id = $1 AND status = 'OPEN'
            """,
            point_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Point niet gevonden of niet in status OPEN")
    return {"submitted": True, "point_id": point_id}


# GET /api/hr/development-points/awaiting-approval
# CEO haalt lijst op van open verzoeken
@router.get("/development-points/awaiting-approval")
async def get_awaiting_approval(request: Request, user=Depends(get_current_user)):
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT dp.*, ha.agent_name, ha.role
            FROM development_points dp
            JOIN hired_agents ha ON dp.agent_id = ha.agent_id
            WHERE dp.status = 'AWAITING_APPROVAL'
            ORDER BY 
                CASE dp.impact WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                dp.created_at ASC
            """
        )
    return {"items": [dict(r) for r in rows], "count": len(rows)}


# POST /api/hr/development-points/{point_id}/approve
# CEO keurt goed of wijst af
@router.post("/development-points/{point_id}/approve")
async def approve_development_point(
    point_id: str,
    body: ApproveTrainingRequest,
    request: Request,
    user=Depends(get_current_user),
):
    async with request.app.state.pool.acquire() as conn:
        # Haal het point op
        point = await conn.fetchrow(
            "SELECT * FROM development_points WHERE point_id = $1 AND status = 'AWAITING_APPROVAL'",
            point_id,
        )
        if not point:
            raise HTTPException(status_code=404, detail="Point niet gevonden of niet in AWAITING_APPROVAL")

        if body.approved:
            # Zet op IN_TRAINING, sla source_url op
            await conn.execute(
                """
                UPDATE development_points
                SET status = 'IN_TRAINING',
                    source_url = COALESCE($2, source_url),
                    approved_by = $3
                WHERE point_id = $1
                """,
                point_id,
                body.source_url,
                user.get("sub", "operator"),
            )

            # Start TrainingWorkflow als source_url beschikbaar is
            final_url = body.source_url or point["source_url"]
            if final_url:
                try:
                    from app.services.training_workflow import TrainingWorkflow
                    workflow = TrainingWorkflow(request.app.state.pool)
                    # Start asynchroon zodat de API direct teruggeeft
                    import asyncio
                    asyncio.create_task(
                        workflow.start_training(
                            agent_id=point["agent_id"],
                            url=final_url,
                            approved_by=user.get("sub", "operator"),
                        )
                    )
                except Exception as e:
                    # Log maar gooi niet: goedkeuring is geslaagd, training start apart
                    import logging
                    logging.getLogger(__name__).error(f"TrainingWorkflow start mislukt: {e}")

            return {"approved": True, "point_id": point_id, "training_started": bool(final_url)}

        else:
            # Afwijzen
            await conn.execute(
                """
                UPDATE development_points
                SET status = 'DISMISSED',
                    approved_by = $2,
                    root_cause = COALESCE(root_cause || ' | Afgewezen: ' || $3, root_cause)
                WHERE point_id = $1
                """,
                point_id,
                user.get("sub", "operator"),
                body.rejection_reason or "Geen reden opgegeven",
            )
            return {"approved": False, "point_id": point_id}
```

## Frontend

### web_ui/frontend/src/pages/HRApprovalPage.jsx — nieuwe pagina

```jsx
import { useEffect, useState } from "react";
import { buildAuthHeaders } from "../utils/authz";

const IMPACT_COLORS = { high: "#DC2626", medium: "#D97706", low: "#6B7280" };

export default function HRApprovalPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState(null);

  const fetchItems = async () => {
    try {
      const res = await fetch("/api/hr/development-points/awaiting-approval", {
        headers: buildAuthHeaders(),
      });
      const data = await res.json();
      setItems(data.items || []);
    } catch (err) {
      console.error("[HRApprovalPage]", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchItems(); }, []);

  const handleDecision = async (pointId, approved, sourceUrl = null, rejectionReason = null) => {
    setProcessingId(pointId);
    try {
      await fetch(`/api/hr/development-points/${pointId}/approve`, {
        method: "POST",
        headers: { ...buildAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ approved, source_url: sourceUrl, rejection_reason: rejectionReason }),
      });
      await fetchItems();
    } catch (err) {
      console.error("[HRApprovalPage] handleDecision", err);
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="hr-approval-page">
      <div className="page-header">
        <h1>CEO Training Approval</h1>
        <p className="page-subtitle">
          Trainingsverzoeken van de HR Manager wachten op jouw goedkeuring.
        </p>
      </div>

      {loading && <p>Laden...</p>}
      {!loading && items.length === 0 && (
        <p className="empty-state">Geen openstaande verzoeken.</p>
      )}

      {items.map((item) => (
        <ApprovalCard
          key={item.point_id}
          item={item}
          isProcessing={processingId === item.point_id}
          onDecision={handleDecision}
        />
      ))}
    </div>
  );
}

function ApprovalCard({ item, isProcessing, onDecision }) {
  const [sourceUrl, setSourceUrl] = useState(item.source_url || "");
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  return (
    <div className={`approval-card impact-${item.impact}`}>
      <div className="card-header">
        <span className="agent-name">{item.agent_name}</span>
        <span className="agent-role">{item.role}</span>
        <span className="impact-badge" style={{ color: IMPACT_COLORS[item.impact] }}>
          {item.impact?.toUpperCase()}
        </span>
        <span className="frequency">x{item.frequency} keer gezien</span>
      </div>

      <p className="issue-description">{item.issue_description}</p>

      {item.root_cause && (
        <p className="root-cause"><strong>Oorzaak:</strong> {item.root_cause}</p>
      )}
      {item.evidence_example && (
        <p className="evidence"><strong>Bewijs:</strong> {item.evidence_example}</p>
      )}

      <div className="source-url-input">
        <label>Training URL (optioneel, overschrijft voorstel)</label>
        <input
          type="url"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          placeholder="https://..."
          disabled={isProcessing}
        />
      </div>

      <div className="card-actions">
        {isProcessing ? (
          <span className="spinner">Verwerken...</span>
        ) : (
          <>
            <button
              className="btn-approve"
              onClick={() => onDecision(item.point_id, true, sourceUrl || null)}
            >
              Goedkeuren
            </button>

            {!showRejectInput ? (
              <button
                className="btn-reject-open"
                onClick={() => setShowRejectInput(true)}
              >
                Afwijzen
              </button>
            ) : (
              <div className="reject-inline">
                <input
                  type="text"
                  placeholder="Reden (optioneel)"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <button
                  className="btn-reject-confirm"
                  onClick={() => onDecision(item.point_id, false, null, rejectReason)}
                >
                  Bevestig afwijzing
                </button>
                <button className="btn-cancel" onClick={() => setShowRejectInput(false)}>
                  Annuleer
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

### Sidebar.jsx — voeg "CEO Approval" toe onder HR

```jsx
// Voeg toe bij de HR sectie in de sidebar
// Gebruik Shield of CheckCircle icoon (lucide-react)
// Badge: aantal items in AWAITING_APPROVAL

// Polling voor de badge (elke 60s — minder urgent dan system events):
const [approvalCount, setApprovalCount] = useState(0);
useEffect(() => {
  const fetch = () =>
    fetchWithAuth("/api/hr/development-points/awaiting-approval")
      .then((d) => setApprovalCount(d.count || 0))
      .catch(() => {});
  fetch();
  const i = setInterval(fetch, 60000);
  return () => clearInterval(i);
}, []);
```

### main.jsx — route toevoegen

```jsx
import HRApprovalPage from "./pages/HRApprovalPage";
<Route path="/hr/approval" element={<HRApprovalPage />} />
```

## Acceptatiecriteria
- [ ] `GET /api/hr/development-points/awaiting-approval` geeft items gesorteerd op impact
- [ ] `POST /api/hr/development-points/{id}/approve` met `approved: true` zet status op IN_TRAINING
- [ ] `POST /api/hr/development-points/{id}/approve` met `approved: false` zet status op DISMISSED
- [ ] Als `source_url` beschikbaar: TrainingWorkflow start asynchroon
- [ ] HRApprovalPage toont alle AWAITING_APPROVAL items met impact-kleur
- [ ] Approve/reject werkt vanuit de UI
- [ ] Sidebar badge toont het aantal openstaande verzoeken

---

# FASE B: Kennis Detail View

## Context
Elke agent heeft een `agent_knowledge` tabel met gechunkte embeddings van getrainde URL's. De operator moet kunnen zien: welke URL's zijn getraind, wanneer, hoeveel chunks, en of de bron nog actief is. Dit is de kennisbibliotheek per agent.

## Backend — voeg toe aan agents router

```python
# GET /api/agents/{agent_id}/knowledge
# Overzicht van alle kennisbronnen van een agent (gegroepeerd per URL)
@router.get("/{agent_id}/knowledge")
async def get_agent_knowledge(agent_id: str, request: Request, user=Depends(get_current_user)):
    async with request.app.state.pool.acquire() as conn:
        # Controleer of agent bestaat
        agent = await conn.fetchrow(
            "SELECT agent_id, agent_name FROM hired_agents WHERE agent_id = $1", agent_id
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent niet gevonden")

        # Groepeer chunks per source_url
        sources = await conn.fetch(
            """
            SELECT 
                source_url,
                COUNT(*) AS chunk_count,
                MAX(added_at) AS last_added,
                bool_and(is_active) AS all_active
            FROM agent_knowledge
            WHERE agent_id = $1
            GROUP BY source_url
            ORDER BY MAX(added_at) DESC
            """,
            agent_id,
        )
    return {
        "agent_id": agent_id,
        "agent_name": agent["agent_name"],
        "sources": [dict(s) for s in sources],
        "total_chunks": sum(s["chunk_count"] for s in sources),
    }


# DELETE /api/agents/{agent_id}/knowledge
# Deactiveer alle chunks van een specifieke source_url
@router.delete("/{agent_id}/knowledge")
async def deactivate_knowledge_source(
    agent_id: str, source_url: str, request: Request, user=Depends(get_current_user)
):
    async with request.app.state.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE agent_knowledge
            SET is_active = false
            WHERE agent_id = $1 AND source_url = $2 AND is_active = true
            """,
            agent_id,
            source_url,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Bron niet gevonden of al inactief")
    return {"deactivated": True, "source_url": source_url}
```

## Frontend

### web_ui/frontend/src/components/AgentKnowledgeTab.jsx — nieuwe tab in AgentDetail

```jsx
import { useEffect, useState } from "react";
import { buildAuthHeaders } from "../utils/authz";

export default function AgentKnowledgeTab({ agentId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [removingUrl, setRemovingUrl] = useState(null);

  const fetchKnowledge = async () => {
    try {
      const res = await fetch(`/api/agents/${agentId}/knowledge`, {
        headers: buildAuthHeaders(),
      });
      setData(await res.json());
    } catch (err) {
      console.error("[AgentKnowledgeTab]", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchKnowledge(); }, [agentId]);

  const handleDeactivate = async (sourceUrl) => {
    if (!confirm(`Bron verwijderen uit kennisbank?\n${sourceUrl}`)) return;
    setRemovingUrl(sourceUrl);
    try {
      await fetch(
        `/api/agents/${agentId}/knowledge?source_url=${encodeURIComponent(sourceUrl)}`,
        { method: "DELETE", headers: buildAuthHeaders() }
      );
      await fetchKnowledge();
    } catch (err) {
      console.error("[AgentKnowledgeTab] deactivate", err);
    } finally {
      setRemovingUrl(null);
    }
  };

  if (loading) return <p>Laden...</p>;
  if (!data) return <p>Kon kennisbank niet laden.</p>;

  return (
    <div className="agent-knowledge-tab">
      <div className="knowledge-header">
        <h3>Kennisbank</h3>
        <span className="chunk-count">{data.total_chunks} chunks totaal</span>
      </div>

      {data.sources.length === 0 && (
        <p className="empty-state">
          Deze agent heeft nog geen getrainde kennisbronnen.
        </p>
      )}

      <div className="knowledge-sources">
        {data.sources.map((source) => (
          <div
            key={source.source_url}
            className={`knowledge-source ${!source.all_active ? "inactive" : ""}`}
          >
            <div className="source-info">
              <a
                href={source.source_url}
                target="_blank"
                rel="noreferrer"
                className="source-url"
              >
                {source.source_url}
              </a>
              <span className="source-meta">
                {source.chunk_count} chunks •{" "}
                {new Date(source.last_added).toLocaleDateString("nl-NL")}
                {!source.all_active && (
                  <span className="inactive-label"> • Inactief</span>
                )}
              </span>
            </div>
            {source.all_active && (
              <button
                className="btn-deactivate"
                onClick={() => handleDeactivate(source.source_url)}
                disabled={removingUrl === source.source_url}
              >
                {removingUrl === source.source_url ? "Verwijderen..." : "Verwijder"}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### AgentDetail.jsx — voeg Knowledge tab toe

Zoek de bestaande tab-structuur in `AgentDetail.jsx` (er zijn al tabs voor Profile, Direct Chat, etc.). Voeg toe:

```jsx
import AgentKnowledgeTab from "../components/AgentKnowledgeTab";

// In de tabs array/definitie:
{ id: "knowledge", label: "Kennisbank" }

// In de tab-content render:
{activeTab === "knowledge" && <AgentKnowledgeTab agentId={agent.agent_id} />}
```

## Acceptatiecriteria
- [ ] `GET /api/agents/{id}/knowledge` geeft bronnen gegroepeerd per URL terug
- [ ] `DELETE /api/agents/{id}/knowledge?source_url=...` zet chunks op `is_active = false`
- [ ] AgentDetail heeft een "Kennisbank" tab
- [ ] Tab toont alle getrainde URL's met chunk-count en datum
- [ ] Verwijder-knop werkt en refresht de lijst

---

# FASE C: Spinner Goedkeuren Modal HR

## Context
De HR Manager heeft een "Goedkeuren" modal (voor development points of training approvals). Op dit moment is er geen visuele feedback terwijl de POST wordt verstuurd. De gebruiker klikt en er gebeurt ogenschijnlijk niets. Dit is een UX-fix.

## Wat aanpassen

Zoek in de codebase naar de bestaande HR approve modal/functie. Zoekwoorden:
```
handleApprove, goedkeuren, AWAITING_APPROVAL, approve, development_points modal
```

Waarschijnlijk in: `HRDashboard.jsx`, `HRManagerPage.jsx`, of een modal component.

## Patroon om toe te passen

Pas dit patroon toe op de bestaande approve-handler. Vervang de huidige implementatie:

```jsx
// VOOR (zonder feedback):
const handleApprove = async (pointId) => {
  await fetch(`/api/hr/development-points/${pointId}/approve`, { ... });
  fetchData();
};

// NA (met spinner en disabled state):
const [approvingId, setApprovingId] = useState(null);

const handleApprove = async (pointId) => {
  setApprovingId(pointId);
  try {
    const res = await fetch(`/api/hr/development-points/${pointId}/approve`, {
      method: "POST",
      headers: { ...buildAuthHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ approved: true }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await fetchData(); // Refresh lijst
  } catch (err) {
    console.error("[HR] handleApprove mislukt:", err);
    // Toon foutmelding aan gebruiker (geen alert(), gebruik een inline error state)
  } finally {
    setApprovingId(null);
  }
};
```

### Knop in de modal:

```jsx
<button
  className="btn-approve"
  onClick={() => handleApprove(point.point_id)}
  disabled={approvingId === point.point_id}
>
  {approvingId === point.point_id ? (
    <span className="spinner-inline">
      <span className="spinner-dot" />
      Verwerken...
    </span>
  ) : (
    "Goedkeuren"
  )}
</button>
```

### CSS voor de spinner (voeg toe aan de bestaande stylesheet):

```css
.spinner-inline {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner-dot {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

## Acceptatiecriteria
- [ ] Knop toont "Verwerken..." + spinner tijdens de API call
- [ ] Knop is `disabled` terwijl de call loopt (voorkomt dubbele submit)
- [ ] Na succes: modal sluit of lijst refresht
- [ ] Bij fout: knop gaat terug naar normale staat, fout zichtbaar in UI (geen `alert()`)

---

# FASE D: Console Logs handleApprove opruimen

## Context
De `handleApprove` functie (en mogelijk andere handlers in de HR/jobs flow) heeft overbodige `console.log` statements die in productie aanwezig zijn. Dit is rommelig en kan gevoelige data lekken naar de browser console.

## Aanpak

Zoek in de codebase naar alle `console.log` in de volgende bestanden:
```
HRDashboard.jsx, HRManagerPage.jsx, JobDetail.jsx, JobSplitView.jsx,
AgentDetail.jsx, AgentDirectChat.jsx
```

Zoekcommando voor Cursor:
```
console.log
```

### Regels:

| Type log | Actie |
|----------|-------|
| `console.log("data:", data)` — debug logs | Verwijder |
| `console.log("handleApprove called")` — trace logs | Verwijder |
| `console.error("...", err)` — echte fouten | Behoud, maar controleer dat ze geen gevoelige data loggen |
| `console.warn(...)` | Behoud alleen als functioneel relevant |

### Richtlijn na opruimen:

Elke `catch` blok mag precies één `console.error` houden met een beschrijvende prefix:

```jsx
// Goed:
catch (err) {
  console.error("[HRDashboard] handleApprove mislukt:", err.message);
}

// Fout (te veel detail naar console):
catch (err) {
  console.log("error", err);
  console.log("response", response);
  console.log("full error:", JSON.stringify(err));
}
```

## Acceptatiecriteria
- [ ] Geen `console.log` debug/trace statements in de geraakte bestanden
- [ ] `console.error` bewaard alleen voor echte foutpaden
- [ ] Geen gevoelige data (tokens, user data, API responses) in console output
- [ ] Functionaliteit ongewijzigd na opruimen

---

## ALGEMENE REGELS VOOR ALLE FASES

- Raak `development_points` tabel structuur niet aan (alleen status-updates via queries)
- Gebruik altijd `buildAuthHeaders()` voor API calls
- Alle nieuwe routes achter `get_current_user` dependency
- Geen `console.log` toevoegen in nieuwe code
- Deploy na alle 4 fases samen: `git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build && cd ../..`
- Migraties zijn niet nodig voor deze fases (geen nieuwe tabellen)

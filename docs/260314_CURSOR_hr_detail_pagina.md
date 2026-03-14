# CURSOR PROMPT: HR Development Point Detail Pagina
**Datum:** 260314  
**Project:** Crew Intelligent / Wonderz-Agentics  
**Scope:** UX verbetering HR Dashboard — detail pagina met kennisbron toevoegen + approve/reject

---

## Context

In het HR Dashboard staat per development point een rij met "Detail → Goedkeuren Afwijzen".  
De "Goedkeuren" knop opent nu een overlay met alleen een URL-veld. Dit is te beperkt en de status wordt niet correct bijgewerkt.

**Gewenste situatie:**
- Lijstweergave: alleen `Detail →` link, Goedkeuren en Afwijzen verdwijnen uit de lijst
- Detail pagina: volledige workflow met kennisbron toevoegen (URL / tekst / bestand) + Goedkeuren / Afwijzen

---

## Pre-flight

Zoek in de codebase naar:
```
HRDashboard.jsx          — huidige lijst + overlay
HRIssueDetail.jsx        — bestaande detail pagina (als die bestaat)
app/routes/hr.py         — submit-for-approval, approve endpoints
```

Controleer of `/hr/issue/:pointId` of `/hr/development-points/:pointId` al als route bestaat.

---

## Fase 1: Lijstweergave opschonen (HRDashboard.jsx)

Verwijder uit de tabelrij:
- De "Goedkeuren" knop en bijbehorende overlay/modal
- De "Afwijzen" knop en bijbehorende handler

Behoud alleen:
```jsx
<a href={`/hr/issues/${point.point_id}`} className="detail-link">
  Detail →
</a>
```

Verwijder ook de bijbehorende state die alleen voor die overlay/modal werd gebruikt (bijv. `approveModal`, `approveUrl`, `setApproveModal`). Laat overige state (filters, scan, weekly report) onaangetast.

---

## Fase 2: Backend — kennisbron opslaan voor een development point

Voeg toe aan `app/routes/hr.py`:

```python
from pydantic import BaseModel
from typing import Optional

class AddKnowledgeSourceRequest(BaseModel):
    source_type: str          # 'url' | 'text' | 'file'
    source_url: Optional[str] = None
    source_text: Optional[str] = None
    # Bestandsupload via apart multipart endpoint (zie Fase 2b)


# POST /api/hr/development-points/{point_id}/knowledge-source
# Sla een kennisbron op bij een development point (voor gebruik bij goedkeuring)
@router.post("/development-points/{point_id}/knowledge-source")
async def add_knowledge_source(
    point_id: str,
    body: AddKnowledgeSourceRequest,
    current_user=Depends(get_current_user),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        point = await conn.fetchrow(
            "SELECT * FROM development_points WHERE point_id = $1",
            point_id,
        )
        if not point:
            raise HTTPException(status_code=404, detail="Development point niet gevonden")

        # Bepaal de op te slaan URL/tekst
        if body.source_type == "url" and body.source_url:
            update_value = body.source_url
        elif body.source_type == "text" and body.source_text:
            # Sla tekst op als data-URI zodat TrainingWorkflow het kan verwerken
            import base64
            encoded = base64.b64encode(body.source_text.encode()).decode()
            update_value = f"data:text/plain;base64,{encoded}"
        else:
            raise HTTPException(status_code=400, detail="source_url of source_text vereist")

        await conn.execute(
            "UPDATE development_points SET source_url = $1 WHERE point_id = $2",
            update_value,
            point_id,
        )
    return {"saved": True, "point_id": point_id, "source_type": body.source_type}


# POST /api/hr/development-points/{point_id}/knowledge-source/file
# Bestandsupload als kennisbron
@router.post("/development-points/{point_id}/knowledge-source/file")
async def add_knowledge_source_file(
    point_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        point = await conn.fetchrow(
            "SELECT point_id FROM development_points WHERE point_id = $1", point_id
        )
        if not point:
            raise HTTPException(status_code=404, detail="Development point niet gevonden")

        content = await file.read()
        import base64
        encoded = base64.b64encode(content).decode()
        media_type = file.content_type or "application/octet-stream"
        data_uri = f"data:{media_type};base64,{encoded}"

        await conn.execute(
            "UPDATE development_points SET source_url = $1 WHERE point_id = $2",
            data_uri,
            point_id,
        )
    return {"saved": True, "point_id": point_id, "filename": file.filename}
```

Voeg bovenaan het bestand toe als nog niet aanwezig:
```python
from fastapi import UploadFile, File
```

---

## Fase 3: Detail pagina (HRIssueDetail.jsx uitbreiden of aanmaken)

Als `HRIssueDetail.jsx` al bestaat: breid uit met de kennisbron-sectie en approve/reject knoppen.  
Als die niet bestaat: maak `web_ui/frontend/src/pages/HRIssueDetail.jsx` aan.

```jsx
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch } from "../utils/apiFetch"; // of het bestaande import-pad

const IMPACT_COLORS = { high: "#DC2626", medium: "#D97706", low: "#6B7280" };
const STATUS_LABELS = {
  OPEN: "Open",
  AWAITING_APPROVAL: "Wacht op goedkeuring",
  IN_TRAINING: "In training",
  RESOLVED: "Opgelost",
  DISMISSED: "Afgewezen",
};

export default function HRIssueDetail() {
  const { pointId } = useParams();
  const navigate = useNavigate();

  const [point, setPoint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Kennisbron state
  const [sourceType, setSourceType] = useState("url"); // 'url' | 'text' | 'file'
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [sourceFile, setSourceFile] = useState(null);
  const [savingSource, setSavingSource] = useState(false);
  const [sourceError, setSourceError] = useState(null);

  // Approve/reject state
  const [processing, setProcessing] = useState(false);
  const [rejectMode, setRejectMode] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [actionError, setActionError] = useState(null);

  const fetchPoint = async () => {
    try {
      const data = await apiFetch(`/api/hr/development-points/${pointId}`);
      setPoint(data);
      if (data.source_url && !data.source_url.startsWith("data:")) {
        setSourceUrl(data.source_url);
      }
    } catch (err) {
      setError("Kon development point niet laden.");
      console.error("[HRIssueDetail] fetchPoint:", err?.message ?? err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPoint(); }, [pointId]);

  const handleSaveSource = async () => {
    setSavingSource(true);
    setSourceError(null);
    try {
      if (sourceType === "file" && sourceFile) {
        const formData = new FormData();
        formData.append("file", sourceFile);
        await apiFetch(
          `/api/hr/development-points/${pointId}/knowledge-source/file`,
          { method: "POST", body: formData }
        );
      } else {
        await apiFetch(
          `/api/hr/development-points/${pointId}/knowledge-source`,
          {
            method: "POST",
            body: JSON.stringify({
              source_type: sourceType,
              source_url: sourceType === "url" ? sourceUrl : undefined,
              source_text: sourceType === "text" ? sourceText : undefined,
            }),
          }
        );
      }
      await fetchPoint();
    } catch (err) {
      setSourceError("Opslaan mislukt. Probeer opnieuw.");
      console.error("[HRIssueDetail] handleSaveSource:", err?.message ?? err);
    } finally {
      setSavingSource(false);
    }
  };

  const handleApprove = async () => {
    setProcessing(true);
    setActionError(null);
    try {
      // Stap 1: submit for approval als nog OPEN
      if (point.status === "OPEN") {
        await apiFetch(
          `/api/hr/development-points/${pointId}/submit-for-approval`,
          { method: "POST" }
        );
      }
      // Stap 2: approve
      await apiFetch(
        `/api/hr/development-points/${pointId}/approve`,
        {
          method: "POST",
          body: JSON.stringify({
            approved: true,
            source_url: sourceUrl || null,
          }),
        }
      );
      navigate("/hr");
    } catch (err) {
      setActionError("Goedkeuren mislukt. Probeer opnieuw.");
      console.error("[HRIssueDetail] handleApprove:", err?.message ?? err);
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    setProcessing(true);
    setActionError(null);
    try {
      if (point.status === "OPEN") {
        await apiFetch(
          `/api/hr/development-points/${pointId}/submit-for-approval`,
          { method: "POST" }
        );
      }
      await apiFetch(
        `/api/hr/development-points/${pointId}/approve`,
        {
          method: "POST",
          body: JSON.stringify({
            approved: false,
            rejection_reason: rejectReason || null,
          }),
        }
      );
      navigate("/hr");
    } catch (err) {
      setActionError("Afwijzen mislukt. Probeer opnieuw.");
      console.error("[HRIssueDetail] handleReject:", err?.message ?? err);
    } finally {
      setProcessing(false);
    }
  };

  if (loading) return <div className="hr-issue-detail loading">Laden...</div>;
  if (error) return <div className="hr-issue-detail error">{error}</div>;
  if (!point) return null;

  const canAct = ["OPEN", "AWAITING_APPROVAL"].includes(point.status);

  return (
    <div className="hr-issue-detail">
      {/* Terug */}
      <button className="back-btn" onClick={() => navigate("/hr")}>
        ← Terug naar HR Dashboard
      </button>

      {/* Issue info */}
      <div className="issue-header">
        <div className="issue-meta">
          <span className="agent-name">{point.agent_name || point.agent_id}</span>
          <span className="issue-status">{STATUS_LABELS[point.status] || point.status}</span>
          <span
            className="impact-badge"
            style={{ color: IMPACT_COLORS[point.impact] }}
          >
            {point.impact?.toUpperCase()}
          </span>
          <span className="frequency">x{point.frequency} keer gezien</span>
        </div>
        <h1 className="issue-description">{point.issue_description}</h1>
        {point.root_cause && (
          <p className="root-cause"><strong>Oorzaak:</strong> {point.root_cause}</p>
        )}
        {point.evidence_example && (
          <p className="evidence"><strong>Bewijs:</strong> {point.evidence_example}</p>
        )}
      </div>

      {/* Kennisbron sectie — alleen tonen als actie mogelijk is */}
      {canAct && (
        <div className="knowledge-source-section">
          <h2>Kennisbron toevoegen</h2>
          <p className="section-subtitle">
            Optioneel: voeg een bron toe die als trainingsmateriaal wordt gebruikt.
          </p>

          {/* Type selector */}
          <div className="source-type-tabs">
            {["url", "text", "file"].map((type) => (
              <button
                key={type}
                className={`source-type-tab ${sourceType === type ? "active" : ""}`}
                onClick={() => setSourceType(type)}
              >
                {type === "url" ? "URL" : type === "text" ? "Tekst plakken" : "Bestand"}
              </button>
            ))}
          </div>

          {sourceType === "url" && (
            <input
              type="url"
              className="source-input"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://..."
            />
          )}

          {sourceType === "text" && (
            <textarea
              className="source-textarea"
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Plak hier de trainingstekst..."
              rows={8}
            />
          )}

          {sourceType === "file" && (
            <input
              type="file"
              className="source-file"
              accept=".txt,.pdf,.md,.docx"
              onChange={(e) => setSourceFile(e.target.files?.[0] || null)}
            />
          )}

          {sourceError && <p className="source-error">{sourceError}</p>}

          <button
            className="btn-save-source"
            onClick={handleSaveSource}
            disabled={savingSource}
          >
            {savingSource ? "Opslaan..." : "Bron opslaan"}
          </button>

          {point.source_url && !point.source_url.startsWith("data:") && (
            <p className="saved-source">
              Huidige bron: <a href={point.source_url} target="_blank" rel="noreferrer">{point.source_url}</a>
            </p>
          )}
          {point.source_url && point.source_url.startsWith("data:") && (
            <p className="saved-source">Huidige bron: bestand of tekst opgeslagen ✓</p>
          )}
        </div>
      )}

      {/* Acties */}
      {canAct && (
        <div className="issue-actions">
          {actionError && <p className="action-error">{actionError}</p>}

          {!rejectMode ? (
            <>
              <button
                className="btn-approve"
                onClick={handleApprove}
                disabled={processing}
              >
                {processing ? (
                  <span className="spinner-inline">
                    <span className="spinner-dot" /> Verwerken...
                  </span>
                ) : (
                  "Goedkeuren"
                )}
              </button>
              <button
                className="btn-reject-open"
                onClick={() => setRejectMode(true)}
                disabled={processing}
              >
                Afwijzen
              </button>
            </>
          ) : (
            <div className="reject-form">
              <input
                type="text"
                placeholder="Reden voor afwijzing (optioneel)"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
              />
              <button
                className="btn-reject-confirm"
                onClick={handleReject}
                disabled={processing}
              >
                {processing ? "Verwerken..." : "Bevestig afwijzing"}
              </button>
              <button
                className="btn-cancel"
                onClick={() => setRejectMode(false)}
                disabled={processing}
              >
                Annuleer
              </button>
            </div>
          )}
        </div>
      )}

      {/* Afgerond / dismissed */}
      {!canAct && (
        <div className="issue-closed">
          <p>
            Dit punt heeft status <strong>{STATUS_LABELS[point.status]}</strong> en kan niet meer worden bewerkt.
          </p>
        </div>
      )}
    </div>
  );
}
```

---

## Fase 4: Backend — GET /api/hr/development-points/{point_id}

Als dit endpoint nog niet bestaat, voeg toe aan `app/routes/hr.py`:

```python
# GET /development-points/{point_id}
# Haalt één development point op inclusief agent_name
@router.get("/development-points/{point_id}")
async def get_development_point(
    point_id: str,
    current_user=Depends(get_current_user),
):
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT dp.*, ha.name AS agent_name, ha.role
            FROM development_points dp
            LEFT JOIN hired_agents ha ON dp.agent_id = ha.agent_id
            WHERE dp.point_id = $1
            """,
            point_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Development point niet gevonden")
    return dict(row)
```

**Let op routevolgorde:** Plaats deze route BOVEN `/{point_id}/submit-for-approval` en `/{point_id}/approve` om conflicten te voorkomen. Controleer de volgorde in het bestand.

---

## Fase 5: Route toevoegen (main.jsx)

```jsx
import HRIssueDetail from "./pages/HRIssueDetail";

// In de routes, binnen de bestaande layout:
<Route path="/hr/issues/:pointId" element={<HRIssueDetail />} />
```

---

## Wat je NIET doet

- Geen wijziging aan de `development_points` tabelstructuur
- Geen nieuwe migraties
- `source_url` kolom bestaat al, die wordt hergebruikt voor URL, tekst (base64) en bestand (base64)
- De bestaande HR scan, weekly report en filter functionaliteit blijft onaangetast
- Geen `console.log` in nieuwe code

---

## Acceptatiecriteria

- [ ] HR Dashboard lijst heeft alleen nog `Detail →`, geen Goedkeuren/Afwijzen knoppen
- [ ] `/hr/issues/:pointId` laadt de detail pagina met issue info
- [ ] Kennisbron sectie heeft drie tabs: URL / Tekst plakken / Bestand
- [ ] "Bron opslaan" slaat de bron op in `development_points.source_url`
- [ ] "Goedkeuren" roept submit-for-approval + approve aan en navigeert terug naar `/hr`
- [ ] "Afwijzen" toont een reden-input, bevestigt en navigeert terug
- [ ] Spinner zichtbaar tijdens verwerken, knop disabled
- [ ] Bij niet-acteerbare status (IN_TRAINING, RESOLVED, DISMISSED): acties verborgen

---

## Deploy na implementatie

```bash
git pull && sudo systemctl restart wonderz-backend && cd web_ui/frontend && npm run build
```
(Vanuit `~/wonderz-agentics/web_ui/frontend`)

"""HR Manager API endpoints."""

import logging
import json
import re
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Set, Any, Annotated
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from arq import ArqRedis

from app.middleware.auth import require_admin_or_super_admin, require_super_admin, get_current_user, TokenPayload
from pydantic import BaseModel, model_validator, Field, root_validator

from app.database import get_db
from app.dependencies import get_arq_pool
from app.services.hr_manager import HRManager
from app.services.job_pipeline import run_intake_inline
from app.agents.hr_manager import HRManager as SpecHRManager, _serialize as _serialize_spec
from app.orchestration.manager import OperationsManager
from models.unified import JobStatus, StrategicBrief
from app.services.training_workflow import TrainingWorkflow
from app.services.hr_resource_discovery import HRResourceDiscovery

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr", tags=["hr"])

TRAINING_SUGGESTIONS_UNAVAILABLE = {
    "error": "training_suggestions niet beschikbaar",
    "detail": "Tabel bestaat nog niet",
}


async def _run_start_training_safe(workflow: TrainingWorkflow, agent_id: str, url: str, approved_by: str) -> None:
    """Run TrainingWorkflow.start_training in background; log and swallow errors so the HTTP response is not affected."""
    try:
        await workflow.start_training(agent_id, url, approved_by=approved_by)
    except Exception as e:
        logger.exception("TrainingWorkflow.start_training failed (background): %s", e)

async def _run_insert_suggestion_into_knowledge_library_safe(
    pool: Any,
    suggestion: dict[str, Any],
    approved_by: str,
) -> None:
    """Background ingest: HR training suggestion -> Knowledge Library entry.

    Swallow errors so approve endpoint never becomes blocking.
    """
    try:
        await _insert_suggestion_into_knowledge_library(pool=pool, suggestion=suggestion, approved_by=approved_by)
    except Exception as e:
        logger.exception("[HR approve->knowledge] library ingest failed (background): %s", e)


async def _insert_suggestion_into_knowledge_library(
    pool: Any,
    suggestion: dict[str, Any],
    approved_by: str,
) -> None:
    """Insert/approve a knowledge_documents entry for an approved HR suggestion.

    Idempotency: best-effort dedupe on knowledge_documents.source_url.
    """
    from datetime import timezone

    from app.services.knowledge_upload_service import create_document_with_chunks, run_embedding_task
    from app.services.training import extract_text, scrape_url

    source_url = str(suggestion.get("url") or "").strip()
    if not source_url:
        return

    title = str(suggestion.get("title") or source_url).strip() or source_url
    summary = str(suggestion.get("rationale") or suggestion.get("approval_notes") or "").strip() or None

    now = datetime.now(timezone.utc)

    def _json_serial_default(o: Any) -> Any:
        if hasattr(o, "isoformat"):
            return o.isoformat()
        if hasattr(o, "hex"):
            return str(o)
        if isinstance(o, (dict, list, str, int, float, bool)) or o is None:
            return o
        return str(o)

    document_id_to_embed: Optional[str] = None

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT document_id, status, embedding_status, version
            FROM knowledge_documents
            WHERE source_url = $1
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            source_url,
        )

        if existing:
            document_id = existing["document_id"]
            status = existing.get("status")
            embedding_status = existing.get("embedding_status")

            if status != "approved":
                await conn.execute(
                    """
                    UPDATE knowledge_documents
                    SET status = 'approved',
                        approved_by = $1,
                        approved_at = $2,
                        last_reviewed = $2,
                        updated_at = NOW()
                    WHERE document_id = $3
                    """,
                    approved_by or "hr-manager",
                    now,
                    document_id,
                )

                doc_after = await conn.fetchrow(
                    "SELECT * FROM knowledge_documents WHERE document_id = $1",
                    document_id,
                )
                if doc_after:
                    snapshot = dict(doc_after)
                    snapshot_json = json.dumps(snapshot, default=_json_serial_default)
                    await conn.execute(
                        """
                        INSERT INTO knowledge_versions
                            (document_id, version, change_note, created_by, approved_by, snapshot)
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                        """,
                        document_id,
                        int(doc_after.get("version") or 1),
                        "approved",
                        approved_by or "hr-manager",
                        approved_by or "hr-manager",
                        snapshot_json,
                    )

            if embedding_status in ("pending", "failed"):
                if embedding_status == "failed":
                    await conn.execute(
                        "UPDATE knowledge_documents SET embedding_status = 'pending' WHERE document_id = $1",
                        document_id,
                    )
                document_id_to_embed = str(document_id)
            elif embedding_status is None:
                document_id_to_embed = str(document_id)
        else:
            html = await scrape_url(source_url)
            text = extract_text(html)
            if not text or len(text) < 50:
                return

            created = await create_document_with_chunks(
                pool,
                text,
                source_url=source_url,
                source_type="url",
                title=title,
                doc_type="sop",
                domain="general",
                function_tag="general",
                client_slug=None,
                approved_by=approved_by or "hr-manager",
                access_level="approved",
                summary=summary,
                keywords=None,
            )
            document_id = created["document_id"]

            await conn.execute(
                """
                UPDATE knowledge_documents
                SET status = 'approved',
                    approved_by = $1,
                    approved_at = $2,
                    last_reviewed = $2,
                    updated_at = NOW()
                WHERE document_id = $3::uuid
                """,
                approved_by or "hr-manager",
                now,
                document_id,
            )

            doc_after = await conn.fetchrow(
                "SELECT * FROM knowledge_documents WHERE document_id = $1::uuid",
                document_id,
            )
            if doc_after:
                snapshot = dict(doc_after)
                snapshot_json = json.dumps(snapshot, default=_json_serial_default)
                await conn.execute(
                    """
                    INSERT INTO knowledge_versions
                        (document_id, version, change_note, created_by, approved_by, snapshot)
                    VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb)
                    """,
                    document_id,
                    int(doc_after.get("version") or 1),
                    "approved",
                    approved_by or "hr-manager",
                    approved_by or "hr-manager",
                    snapshot_json,
                )

            document_id_to_embed = str(document_id)

    if document_id_to_embed:
        await run_embedding_task(pool, document_id_to_embed)

TRAINING_REQUESTS_UNAVAILABLE = {
    "error": "training_requests niet beschikbaar",
    "detail": "Tabel bestaat nog niet",
}


def _is_training_requests_unavailable(exc: Exception) -> bool:
    try:
        import asyncpg
        if type(exc).__name__ == "UndefinedTableError" or (
            hasattr(asyncpg, "UndefinedTableError") and isinstance(exc, asyncpg.UndefinedTableError)
        ):
            return "training_requests" in str(exc).lower()
    except Exception:
        pass
    msg = str(exc).lower()
    return "training_requests" in msg and ("does not exist" in msg or "undefined_table" in msg or "relation" in msg)
_columns_cache: Dict[str, Set[str]] = {}


async def _get_table_columns(conn, table_name: str) -> Set[str]:
    if table_name in _columns_cache:
        return _columns_cache[table_name]
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table_name,
    )
    cols = {r["column_name"] for r in rows}
    _columns_cache[table_name] = cols
    return cols


def _decision_timestamp_column(columns: Set[str], approved: bool) -> Optional[str]:
    if approved and "approved_at" in columns:
        return "approved_at"
    if not approved and "rejected_at" in columns:
        return "rejected_at"
    if "resolved_at" in columns:
        return "resolved_at"
    if "updated_at" in columns:
        return "updated_at"
    return None


def _decision_actor_column(columns: Set[str], approved: bool) -> Optional[str]:
    if approved and "approved_by" in columns:
        return "approved_by"
    if not approved and "rejected_by" in columns:
        return "rejected_by"
    if "resolved_by" in columns:
        return "resolved_by"
    if "approved_by" in columns:
        return "approved_by"
    return None


def _decision_notes_column(columns: Set[str]) -> Optional[str]:
    if "approval_notes" in columns:
        return "approval_notes"
    if "notes" in columns:
        return "notes"
    return None


async def _training_suggestions_table_exists(conn: Any) -> bool:
    val = await conn.fetchval(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'training_suggestions'
        """
    )
    return bool(val)


def _training_suggestion_to_json(row: Any) -> dict[str, Any]:
    d = dict(row)
    for key in ("discovered_at", "reviewed_at"):
        v = d.get(key)
        if v is not None and hasattr(v, "isoformat"):
            d[key] = v.isoformat()
    return d


class DevelopmentPoint(BaseModel):
    point_id: Any
    agent_id: Optional[Any] = None
    agent_role: Optional[str] = None
    issue_description: str
    frequency: int
    impact: str
    status: str
    source_url: Optional[str] = None
    evidence_example: Optional[str] = None
    proposed_by: Optional[str] = None
    resolution: Optional[str] = None
    approval_notes: Optional[str] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None


class ApproveTrainingRequest(BaseModel):
    # Development point approval (legacy path)
    point_id: Optional[Any] = Field(default=None, description="Development point to approve")
    # Training request approval (new path)
    request_id: Optional[Any] = Field(default=None, description="Training request to approve")
    approved: Optional[bool] = Field(default=None, description="Approve or reject training request")
    source_url: Optional[str] = Field(default=None, description="Training URL")
    notes: Optional[str] = Field(default=None, description="Approval notes")
    approved_by: str = Field(default="ceo", description="Approver")
    rejection_reason: Optional[str] = Field(default=None, description="Reason when rejecting")

    @model_validator(mode='after')
    def validate_payload(self):
        if self.request_id or self.approved is not None:
            if self.approved is None:
                raise ValueError("approved is required when approving training requests")
        elif not self.point_id:
            raise ValueError("point_id or request_id is required")
        return self


class TrainingSuggestionNotesBody(BaseModel):
    """Optional notes when approving or rejecting a training suggestion."""

    approval_notes: Optional[str] = Field(default=None, max_length=4000)


class ManualTrainingDiscoverBody(BaseModel):
    """Trigger HR resource discovery for a development point (manual)."""

    development_point_id: Optional[str] = Field(
        default=None,
        description="Optional development point id; persisted as training_suggestions.development_point_ref (TEXT) in production",
    )
    agent_id: str = Field(default="")
    agent_role: str = ""
    pattern_description: str = Field(..., min_length=1)
    impact: str = Field(default="medium", description="Impact level (e.g. high, critical)")


class ResolveRequest(BaseModel):
    resolution: str


class AddKnowledgeSourceRequest(BaseModel):
    source_type: str  # 'url' | 'text' | 'file'
    source_url: Optional[str] = None
    source_text: Optional[str] = None


class ResolveHiringRequest(BaseModel):
    agent_id: Any
    notes: Optional[str] = None


class HiringDecisionRequest(BaseModel):
    decided_by: str = Field(default="ceo", description="Approver/rejector")
    notes: Optional[str] = None


async def _get_hr_manager() -> HRManager:
    pool = await get_db()
    return HRManager(pool)


async def _get_spec_hr() -> SpecHRManager:
    pool = await get_db()
    return SpecHRManager(pool)


class UpdatePointBody(BaseModel):
    status: Optional[str] = None
    approved_by: Optional[str] = None
    source_url: Optional[str] = None
    action: Optional[str] = None
    reason: Optional[str] = None


@router.get("/improvements")
async def list_improvements():
    """List improvement suggestions (alias for development-points)."""
    hr = await _get_hr_manager()
    points = await hr.get_development_points(status="OPEN")
    return [{"id": p.get("point_id") or p.get("id"), "agent_id": p.get("agent_id"),
             "agent_role": p.get("agent_role"), "category": p.get("category"),
             "description": p.get("description"), "impact": p.get("impact"),
             "status": p.get("status"), "source_url": p.get("source_url"),
             "created_at": str(p.get("created_at", ""))} for p in points]


@router.get("/development-points")
async def list_development_points(
    agent_id: Optional[str] = Query(None),
    agent_role: Optional[str] = Query(None),
    impact: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    format: Optional[str] = Query(None, description="'spec' for {development_points, count}"),
):
    """Lists development points with optional filters. Default: spec format for HRDashboard."""
    if format == "legacy":
        # Legacy format: use services HRManager
        hr = await _get_hr_manager()
        status_filter = None
        if status:
            status_lower = (status or "").lower()
            if status_lower not in {"all", "any", "*"}:
                status_filter = status
        points = await hr.get_development_points(
            agent_id=agent_id,
            agent_role=agent_role,
            impact=impact,
            status=status_filter,
        )
        return [
            DevelopmentPoint(
                point_id=p.get("point_id") or p.get("id"),
                agent_id=p.get("agent_id"),
                agent_role=p.get("agent_role"),
                issue_description=p.get("issue_description") or p.get("description") or "",
                frequency=p.get("frequency") or 0,
                impact=p.get("impact") or "low",
                status=p.get("status") or "OPEN",
                source_url=p.get("source_url"),
                evidence_example=p.get("evidence_example"),
                proposed_by=p.get("proposed_by"),
                resolution=p.get("resolution"),
                approval_notes=p.get("approval_notes") or p.get("notes"),
                approved_by=p.get("approved_by"),
                rejected_by=p.get("rejected_by"),
                created_at=p.get("created_at"),
                updated_at=p.get("updated_at"),
                resolved_at=p.get("resolved_at"),
            )
            for p in points
        ]
    # Spec format: { development_points, count }
    hr = await _get_spec_hr()
    pool = await get_db()
    async with pool.acquire() as conn:
        conditions = ["1=1"]
        params: list = []
        idx = 1
        if agent_id:
            conditions.append(f"ai.agent_id = ${idx}")
            params.append(agent_id)
            idx += 1
        if impact:
            conditions.append(f"ai.impact = ${idx}")
            params.append(impact)
            idx += 1
        if status:
            conditions.append(f"ai.status = ${idx}")
            params.append(status)
            idx += 1
        rows = await conn.fetch(
            f"""
            SELECT ai.*, ha.name as ha_agent_name FROM development_points ai
            LEFT JOIN hired_agents ha ON ai.agent_id = ha.agent_id
            WHERE {' AND '.join(conditions)}
            ORDER BY CASE ai.impact WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                     ai.created_at DESC
            """,
            *params,
        )
    # Map to legacy shape for _serialize_spec / API
    mapped = []
    for r in rows:
        d = dict(r)
        d["point_id"] = str(d.get("id", ""))
        d["issue_description"] = d.get("issue_description") or d.get("title") or ""
        d["root_cause"] = d.get("summary")
        d["impact"] = (d.get("impact") or "low").lower()
        d["evidence_example"] = d.get("details")
        d["frequency"] = 1
        mapped.append(d)
    serialized = _serialize_spec(mapped)
    return {"development_points": serialized, "count": len(serialized)}


def _extract_job_id_from_evidence(details_or_evidence: Optional[str]) -> Optional[str]:
    """Extract job UUID from details/evidence text, e.g. 'Job cdff169b-b49b-4ec4-..., 255x gezien'."""
    if not details_or_evidence:
        return None
    match = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        details_or_evidence,
        re.I,
    )
    return match.group(0) if match else None


@router.get("/development-points/awaiting-approval", dependencies=[Depends(get_current_user)])
async def get_awaiting_approval():
    """CEO: list development points waiting for approval, sorted by impact and created_at."""
    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ai.*, ha.name AS agent_name, ha.role
            FROM development_points ai
            JOIN hired_agents ha ON ai.agent_id = ha.agent_id
            WHERE ai.status = 'AWAITING_APPROVAL'
            ORDER BY
                CASE ai.impact WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                ai.created_at ASC
            """
        )
    items = []
    for r in rows:
        d = dict(r)
        for k in ("created_at", "updated_at"):
            if d.get(k) and hasattr(d[k], "isoformat"):
                d[k] = d[k].isoformat()
        d["point_id"] = str(d.get("id", ""))
        items.append(d)
    return {"items": items, "count": len(items)}


@router.get("/development-points/{point_id}")
async def get_development_point_detail(point_id: str):
    """
    Get one development point with agent info, timeline, pattern, impact_stats, etc.
    Spec: GET /api/hr/development-points/:pointId for Issue Detail page.
    """
    pool = await get_db()
    async with pool.acquire() as conn:
        dp_row = await conn.fetchrow(
            """
            SELECT ai.*, ha.name AS agent_name, ha.role AS agent_role, ha.agent_id AS ha_agent_id
            FROM development_points ai
            LEFT JOIN hired_agents ha ON ai.agent_id = ha.agent_id
            WHERE ai.id::text = $1
            """,
            point_id,
        )
        if not dp_row:
            raise HTTPException(status_code=404, detail=f"Development point {point_id} niet gevonden")
        point_id = str(dp_row["id"])

        ha_cols = await _get_table_columns(conn, "hired_agents")
        agent_row = await conn.fetchrow(
            "SELECT * FROM hired_agents WHERE agent_id = $1",
            dp_row["agent_id"],
        ) if dp_row.get("agent_id") else None

        run_id = _extract_job_id_from_evidence(dp_row.get("details"))
        if not run_id and dp_row.get("agent_id"):
            first_job = await conn.fetchval(
                """
                SELECT job_id FROM job_steps
                WHERE agent_id = $1 AND retry_reason IS NOT NULL AND trim(retry_reason) != ''
                ORDER BY started_at DESC NULLS LAST
                LIMIT 1
                """,
                dp_row["agent_id"],
            )
            if first_job:
                run_id = str(first_job)

        timeline: List[Dict[str, Any]] = []
        if run_id:
            step_cols = await _get_table_columns(conn, "job_steps")
            steps = await conn.fetch(
                """
                SELECT step_index, step_name, status, retry_count, retry_reason, started_at, completed_at
                FROM job_steps WHERE job_id = $1 ORDER BY step_index
                """,
                run_id,
            )
            for s in steps:
                started = s.get("started_at")
                completed = s.get("completed_at")
                time_str = (started or completed or "").strftime("%H:%M:%S") if hasattr(started or completed, "strftime") else ""
                duration_s = None
                if started and completed and hasattr(started, "timestamp") and hasattr(completed, "timestamp"):
                    duration_s = round(completed.timestamp() - started.timestamp(), 1)
                timeline.append({
                    "time": time_str,
                    "step": (s.get("step_name") or "").strip() or "Step",
                    "status": "ok" if (s.get("status") or "").lower() == "completed" else "fail",
                    "duration_s": duration_s,
                    "notes": (s.get("retry_reason") or "").strip() or None,
                })

        confidence = dp_row.get("confidence_score")
        if confidence is not None:
            confidence = float(confidence)
        point = {
            "point_id": point_id,
            "issue_description": dp_row.get("title") or "",
            "root_cause": dp_row.get("summary"),
            "evidence_example": dp_row.get("details"),
            "frequency": 1,
            "impact": (dp_row.get("impact") or "low").lower(),
            "status": (dp_row.get("status") or "OPEN").upper(),
            "proposed_by": dp_row.get("proposed_by"),
            "source_url": dp_row.get("source_url"),
            "confidence_score": confidence,
            "created_at": dp_row["created_at"].isoformat() if dp_row.get("created_at") and hasattr(dp_row["created_at"], "isoformat") else None,
            "resolved_at": dp_row["resolved_at"].isoformat() if dp_row.get("resolved_at") and hasattr(dp_row["resolved_at"], "isoformat") else None,
        }

        agent: Dict[str, Any] = {}
        if agent_row:
            agent = {
                "agent_id": agent_row.get("agent_id"),
                "agent_name": agent_row.get("name") or agent_row.get("agent_name") or str(agent_row.get("agent_id", "")),
                "agent_version": getattr(agent_row.get("agent_version"), "isoformat", None) or agent_row.get("agent_version") or "—",
                "role": agent_row.get("role"),
                "model": agent_row.get("model"),
                "temperature": float(agent_row["temperature"]) if agent_row.get("temperature") is not None else None,
                "top_p": float(agent_row["top_p"]) if agent_row.get("top_p") is not None else None,
                "max_tokens": agent_row.get("max_tokens"),
                "workflow": agent_row.get("workflow") or agent_row.get("role") or "—",
                "success_rate": float(agent_row["success_rate"]) if agent_row.get("success_rate") is not None else None,
            }
            for k in list(agent):
                if agent[k] is None and k not in ("agent_id", "agent_name", "workflow"):
                    agent[k] = None

        freq = 1
        pattern = {
            "workflow": agent.get("workflow") or "—",
            "trigger_condition": None,
            "affected_version": agent.get("agent_version"),
            "workflow_success_rate": agent.get("success_rate"),
            "failure_rate_condition": (1 - (agent.get("success_rate") or 0)) if agent.get("success_rate") is not None else None,
        }
        impact_stats = {
            "affected_jobs": None,
            "total_retries": freq,
            "extra_cost_per_100": None,
            "user_facing": False,
        }
        performance = {
            "success_rate": agent.get("success_rate"),
            "retry_rate": None,
            "validation_failure_rate": None,
            "avg_cost_per_run": None,
        }
        evidence = [run_id] if run_id else []
        feedback: Optional[Dict[str, Any]] = None

        # Cross-agent correlations for CrossAgentCard (same pattern: e.g. same issue or other open points)
        cross_agent: List[Dict[str, Any]] = []
        agent_id_val = dp_row.get("agent_id")
        if agent_id_val:
            # Current agent as first row (is_current=True); then others with same issue pattern
            open_same = await conn.fetch(
                """
                SELECT ai.id, ai.agent_id, ai.impact, ha.name AS agent_name
                FROM development_points ai
                LEFT JOIN hired_agents ha ON ai.agent_id = ha.agent_id
                WHERE ai.status = 'OPEN' AND ai.agent_id != $1
                  AND lower(trim(ai.title)) = lower(trim($2))
                ORDER BY ai.created_at DESC
                LIMIT 5
                """,
                agent_id_val,
                (dp_row.get("title") or "")[:200],
            )
            cross_agent.append({
                "agent_id": agent_id_val,
                "agent_name": agent_row.get("name") or agent_row.get("agent_name") if agent_row else str(agent_id_val),
                "version": agent.get("agent_version") if agent else "—",
                "failures_30d": freq,
                "impact": (dp_row.get("impact") or "low").lower(),
                "is_current": True,
            })
            for r in open_same:
                cross_agent.append({
                    "agent_id": r["agent_id"],
                    "agent_name": r["agent_name"] or r["agent_id"],
                    "version": "—",
                    "failures_30d": 1,
                    "impact": (r["impact"] or "low").lower(),
                    "is_current": False,
                })

        # Optional: derive diagnosis signals for UI (DiagnosisSignalsCard)
        signals: List[Dict[str, Any]] = []
        if point.get("root_cause"):
            conf = point.get("confidence_score")
            signals.append({
                "icon": "🔁",
                "name": "Consistent retry pattern",
                "description": (point.get("issue_description") or "")[:120] or "Retries detected",
                "weight": float(conf) if conf is not None else 0.85,
            })

        # Trend for FrequencyTrendCard (daily filled by future aggregation; here minimal for tiles)
        total_f = int(point.get("frequency") or 0)
        trend = {
            "daily": [],
            "total_failures": total_f,
            "peak_day": None,
            "daily_avg": round(total_f / 30.0, 1) if total_f else 0,
            "vs_prev_period_pct": None,
        }

        input_data: Optional[Dict[str, Any]] = None
        output_data: Optional[Dict[str, Any]] = None
        if run_id:
            job_row = await conn.fetchrow(
                "SELECT job_post, context FROM jobs WHERE id = $1",
                run_id,
            )
            if job_row:
                ctx = job_row.get("context")
                if isinstance(ctx, str):
                    try:
                        ctx = json.loads(ctx) if ctx else {}
                    except (TypeError, ValueError):
                        ctx = {}
                if not isinstance(ctx, dict):
                    ctx = {}
                task_prompt = job_row.get("job_post") or ctx.get("job_post") or ""
                briefing = ctx.get("briefing") or ctx.get("brief") or {}
                extra_params = ctx.get("extra_params") or ctx.get("extra_params") or {}
                input_data = {
                    "task_prompt": task_prompt,
                    "briefing": briefing if isinstance(briefing, dict) else {},
                    "extra_params": extra_params if isinstance(extra_params, dict) else {},
                }
            step_row = await conn.fetchrow(
                "SELECT output FROM job_steps WHERE job_id = $1 ORDER BY step_index DESC LIMIT 1",
                run_id,
            )
            if step_row and step_row.get("output"):
                out = step_row["output"]
                if isinstance(out, dict):
                    output_data = {
                        "summary": out.get("summary") or out.get("content") or "",
                        "validation_rules": out.get("validation_rules") or [],
                        "problem_description": out.get("problem_description") or out.get("error") or "",
                    }
                elif isinstance(out, str):
                    output_data = {"summary": out[:500], "validation_rules": [], "problem_description": ""}

    return {
        "point": point,
        "agent": agent,
        "timeline": timeline,
        "run_id": run_id,
        "pattern": pattern,
        "impact_stats": impact_stats,
        "performance": performance,
        "evidence": evidence,
        "feedback": feedback,
        "signals": signals,
        "trend": trend,
        "input": input_data,
        "output": output_data,
        "cross_agent": cross_agent,
    }


@router.get("/report")
async def get_weekly_report(_: None = Depends(require_admin_or_super_admin)):
    """Weekly HR performance report per agent. Super admin only. Uses spec agent (agent_name from name)."""
    hr = await _get_spec_hr()
    report = await hr.generate_weekly_report()
    return report


@router.post("/scan-patterns")
async def scan_patterns():
    """Manually trigger retry pattern scan."""
    hr = await _get_hr_manager()
    try:
        result = await hr.process_retry_patterns()
        return result
    except Exception as e:
        logger.error("Pattern scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve-training")
async def approve_training(req: ApproveTrainingRequest, arq_pool: ArqRedis = Depends(get_arq_pool)):
    """Approve a development point and start training."""
    logger.info("[approve-training] request_id=%s point_id=%s approved=%s source_url=%s", req.request_id, req.point_id, req.approved, req.source_url)
    # Training request approval path (only when request_id is explicitly provided)
    if req.request_id:
        try:
            pool = await get_db()

            async with pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'training_requests'"
                )
                if not exists:
                    return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)

                request = await conn.fetchrow(
                    "SELECT * FROM training_requests WHERE request_id = $1",
                    req.request_id,
                )
                if not request:
                    raise HTTPException(status_code=404, detail="Request not found")

                new_status = "APPROVED" if req.approved else "REJECTED"
                notes_value = req.notes if req.approved else (req.rejection_reason or req.notes)
                await conn.execute(
                    """
                    UPDATE training_requests
                    SET status = $1,
                        approved_at = NOW(),
                        approved_by = $2,
                        approval_notes = $3
                    WHERE request_id = $4
                    """,
                    new_status,
                    req.approved_by,
                    notes_value,
                    req.request_id,
                )

                if req.approved and req.point_id:
                    await conn.execute(
                        """
                        UPDATE development_points
                        SET status = 'IN_TRAINING', updated_at = NOW()
                        WHERE id = $1 OR id::text = $1
                        """,
                        req.point_id,
                    )

            if req.approved:
                url = req.source_url or request.get("suggested_url")
                if not url:
                    raise HTTPException(status_code=400, detail="No training URL provided")
                await arq_pool.enqueue_job(
                    "start_agent_training",
                    request["agent_id"],
                    url,
                    req.approved_by or "ceo",
                )

            return {
                "request_id": req.request_id,
                "status": new_status,
                "training_started": bool(req.approved),
            }
        except HTTPException:
            raise
        except Exception as e:
            if _is_training_requests_unavailable(e):
                return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)
            raise

    # Development point approval path (legacy)
    hr = await _get_hr_manager()
    try:
        result = await hr.approve_training(
            point_id=req.point_id,
            source_url=req.source_url,
            approved_by=req.approved_by,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Training approval failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_development_point_key_for_discovery(raw: Optional[str]) -> Optional[str]:
    """Normalize dev-point key for training_suggestions.development_point_ref (TEXT).

    Production expects NULL when no development point is selected.
    """
    if raw is None:
        return None
    normalized = str(raw).strip()
    return normalized if normalized else None


@router.get("/training-suggestions", dependencies=[Depends(get_current_user)])
async def list_training_suggestions(
    agent_id: Optional[str] = Query(None),
    status: str = Query("pending", description="pending | approved | rejected"),
):
    """List training suggestions (resource discovery) with optional filters."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if not await _training_suggestions_table_exists(conn):
            return JSONResponse(status_code=503, content=TRAINING_SUGGESTIONS_UNAVAILABLE)
        st = (status or "pending").strip().lower()
        if st not in ("pending", "approved", "rejected"):
            raise HTTPException(status_code=400, detail="status must be pending, approved, or rejected")
        if agent_id:
            rows = await conn.fetch(
                """
                SELECT ts.*, ha.name AS agent_name, ha.role AS agent_role
                FROM training_suggestions ts
                LEFT JOIN hired_agents ha ON ts.agent_id = ha.agent_id
                WHERE ts.status = $1 AND ts.agent_id = $2
                ORDER BY ts.discovered_at DESC NULLS LAST, ts.id DESC
                """,
                st,
                agent_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT ts.*, ha.name AS agent_name, ha.role AS agent_role
                FROM training_suggestions ts
                LEFT JOIN hired_agents ha ON ts.agent_id = ha.agent_id
                WHERE ts.status = $1
                ORDER BY ts.discovered_at DESC NULLS LAST, ts.id DESC
                """,
                st,
            )
    return {"suggestions": [_training_suggestion_to_json(r) for r in rows], "count": len(rows)}


@router.post("/training-suggestions/{suggestion_id}/approve")
async def approve_training_suggestion(
    suggestion_id: int,
    body: TrainingSuggestionNotesBody,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    current_user: TokenPayload = Depends(get_current_user),
):
    """Approve a pending suggestion and start training via TrainingWorkflow (background)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if not await _training_suggestions_table_exists(conn):
            return JSONResponse(status_code=503, content=TRAINING_SUGGESTIONS_UNAVAILABLE)
        row = await conn.fetchrow(
            """
            UPDATE training_suggestions
            SET status = 'approved',
                approved_by = $1,
                approval_notes = COALESCE($2, ''),
                reviewed_at = NOW()
            WHERE id = $3 AND status = 'pending'
            RETURNING *
            """,
            current_user.user_id,
            body.approval_notes or "",
            suggestion_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Suggestion not found or not pending")
        suggestion = dict(row)

    url = suggestion.get("url")
    agent_id_s = suggestion.get("agent_id")
    approver = current_user.user_id or "hr-dashboard"
    if url and agent_id_s:
        await arq_pool.enqueue_job(
            "start_agent_training",
            str(agent_id_s),
            str(url),
            approver,
        )

    # Additionally: make the approved resource visible in Knowledge Library (/knowledge).
    # Enqueued to ARQ so the approve endpoint remains non-blocking.
    if url:
        await arq_pool.enqueue_job(
            "insert_hr_suggestion_into_knowledge_library",
            str(url),
            str(suggestion.get("title") or ""),
            str(suggestion.get("rationale") or ""),
            approver,
        )

    return {
        "suggestion": _training_suggestion_to_json(suggestion),
        "training_started": bool(url and agent_id_s),
    }


@router.post("/training-suggestions/{suggestion_id}/reject")
async def reject_training_suggestion(
    suggestion_id: int,
    body: TrainingSuggestionNotesBody,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    """Reject a pending training suggestion."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if not await _training_suggestions_table_exists(conn):
            return JSONResponse(status_code=503, content=TRAINING_SUGGESTIONS_UNAVAILABLE)
        row = await conn.fetchrow(
            """
            UPDATE training_suggestions
            SET status = 'rejected',
                approved_by = $1,
                approval_notes = COALESCE($2, ''),
                reviewed_at = NOW()
            WHERE id = $3 AND status = 'pending'
            RETURNING *
            """,
            current_user.user_id,
            body.approval_notes or "",
            suggestion_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Suggestion not found or not pending")
    return {"suggestion": _training_suggestion_to_json(row)}


@router.post("/training-suggestions/discover", dependencies=[Depends(get_current_user)])
async def manual_discover_training_suggestions(body: ManualTrainingDiscoverBody):
    """Run HR resource discovery for a development point; inserts up to 3 pending suggestions."""
    pool = await get_db()
    discovery = HRResourceDiscovery()
    dp_key = _normalize_development_point_key_for_discovery(body.development_point_id)
    async with pool.acquire() as conn:
        if not await _training_suggestions_table_exists(conn):
            return JSONResponse(status_code=503, content=TRAINING_SUGGESTIONS_UNAVAILABLE)
        created = await discovery.discover_for_development_point(
            conn=conn,
            development_point_id=dp_key,
            agent_id=body.agent_id.strip(),
            agent_role=(body.agent_role or "").strip(),
            pattern_description=body.pattern_description.strip(),
            impact=(body.impact or "medium").strip(),
        )
    return {
        "discovered": len(created),
        "suggestions": [_training_suggestion_to_json(r) for r in created],
    }


@router.get("/hiring-requests")
async def get_hiring_requests(status: Optional[str] = None):
    """Get pending hiring requests."""
    pool = await get_db()

    query = "SELECT * FROM hiring_requests"
    params = []
    if status:
        query += " WHERE status = $1"
        params.append(status)
    else:
        query += " WHERE status = 'pending'"

    query += " ORDER BY created_at DESC"

    async with pool.acquire() as conn:
        requests = await conn.fetch(query, *params)

    return {
        "hiring_requests": [dict(r) for r in requests],
        "count": len(requests),
    }


@router.get("/hiring-requests/{request_id}/progress")
async def get_hiring_progress(request_id: str):
    from datetime import datetime
    pool = await get_db()
    async with pool.acquire() as conn:
        req = await conn.fetchrow("SELECT * FROM hiring_requests WHERE request_id = $1", request_id)
        if not req:
            raise HTTPException(404)
        elapsed = (datetime.utcnow() - req["created_at"]).total_seconds() / 60
        return {
            "status": req["status"],
            "progress_percentage": min(100, int(elapsed)),
            "status_message": "Agent ready!" if req["status"] == "hired" else "Waiting",
        }


@router.post("/hiring-requests/{request_id}/approve")
async def approve_hiring_request(request_id: str, payload: HiringDecisionRequest):
    """Approve a hiring request and mark the job as awaiting hire."""
    pool = await get_db()

    async with pool.acquire() as conn:
        request = await conn.fetchrow(
            "SELECT * FROM hiring_requests WHERE request_id = $1",
            request_id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        if request.get("status") not in (None, "pending", "awaiting_approval"):
            raise HTTPException(status_code=400, detail=f"Request already {request.get('status')}")

        columns = await _get_table_columns(conn, "hiring_requests")
        updates = {"status": "approved"}

        actor_col = _decision_actor_column(columns, approved=True)
        if actor_col:
            updates[actor_col] = payload.decided_by

        notes_col = _decision_notes_column(columns)
        if notes_col and payload.notes is not None:
            updates[notes_col] = payload.notes

        timestamp_col = _decision_timestamp_column(columns, approved=True)
        set_clauses = []
        values = []
        for col, val in updates.items():
            set_clauses.append(f"{col} = ${len(values) + 1}")
            values.append(val)
        if timestamp_col:
            set_clauses.append(f"{timestamp_col} = NOW()")

        values.append(request_id)
        await conn.execute(
            f"UPDATE hiring_requests SET {', '.join(set_clauses)} WHERE request_id = ${len(values)}",
            *values,
        )

        job_id = request.get("job_id")
        if job_id:
            await conn.execute(
                "UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                JobStatus.AWAITING_HIRE.value,
                job_id,
            )

    return {"request_id": request_id, "status": "approved", "job_id": request.get("job_id")}


@router.post("/hiring-requests/{request_id}/reject")
async def reject_hiring_request(request_id: str, payload: HiringDecisionRequest):
    """Reject a hiring request and cancel the related job."""
    pool = await get_db()

    async with pool.acquire() as conn:
        request = await conn.fetchrow(
            "SELECT * FROM hiring_requests WHERE request_id = $1",
            request_id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        if request.get("status") not in (None, "pending", "awaiting_approval"):
            raise HTTPException(status_code=400, detail=f"Request already {request.get('status')}")

        columns = await _get_table_columns(conn, "hiring_requests")
        updates = {"status": "rejected"}

        actor_col = _decision_actor_column(columns, approved=False)
        if actor_col:
            updates[actor_col] = payload.decided_by

        notes_col = _decision_notes_column(columns)
        if notes_col and payload.notes is not None:
            updates[notes_col] = payload.notes

        timestamp_col = _decision_timestamp_column(columns, approved=False)
        set_clauses = []
        values = []
        for col, val in updates.items():
            set_clauses.append(f"{col} = ${len(values) + 1}")
            values.append(val)
        if timestamp_col:
            set_clauses.append(f"{timestamp_col} = NOW()")

        values.append(request_id)
        await conn.execute(
            f"UPDATE hiring_requests SET {', '.join(set_clauses)} WHERE request_id = ${len(values)}",
            *values,
        )

        job_id = request.get("job_id")
        if job_id:
            await conn.execute(
                "UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                JobStatus.CANCELLED.value,
                job_id,
            )

    return {"request_id": request_id, "status": "rejected", "job_id": request.get("job_id")}


@router.post("/hiring-requests/{request_id}/resolve")
async def resolve_hiring_request(request_id: str, payload: ResolveHiringRequest):
    """Resolve a hiring request and resume job planning if possible."""
    pool = await get_db()

    async with pool.acquire() as conn:
        agent = await conn.fetchrow(
            "SELECT agent_id FROM hired_agents WHERE agent_id = $1",
            payload.agent_id,
        )
        if not agent:
            raise HTTPException(status_code=400, detail="Agent not found in hired_agents")

        request = await conn.fetchrow(
            "SELECT * FROM hiring_requests WHERE request_id = $1",
            request_id,
        )
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        await conn.execute(
            """
            UPDATE hiring_requests
            SET status = 'hired',
                hired_agent_id = $1,
                resolved_at = NOW(),
                notes = $2
            WHERE request_id = $3
            """,
            payload.agent_id,
            payload.notes,
            request_id,
        )

        job_id = request.get("job_id")
        if job_id:
            job = await conn.fetchrow("SELECT context FROM jobs WHERE id = $1", job_id)
            ctx = job.get("context") if job else None
            if isinstance(ctx, str):
                try:
                    ctx = json.loads(ctx)
                except Exception:
                    ctx = {}
            ctx = ctx or {}

            brief_data = ctx.get("brief")
            if brief_data:
                try:
                    brief = StrategicBrief.model_validate(brief_data)
                    def _dummy_runner(agent_name: str, input_data: dict) -> dict:
                        return {"status": "success", "summary": f"Ran {agent_name}"}
                    mgr = OperationsManager(agent_runner=_dummy_runner)
                    await mgr.generate_and_propose_plan(str(job_id), brief)
                    await conn.execute(
                        "UPDATE jobs SET status = $1, updated_at = NOW() WHERE id = $2",
                        JobStatus.PLAN_PROPOSED.value,
                        job_id,
                    )
                except Exception as e:
                    logger.error("Failed to resume planning for job %s: %s", job_id, e)

    return {"status": "resolved", "request_id": request_id}


class TrainingRequestIn(BaseModel):
    agent_id: Any
    reason: str
    confidence_score: Optional[float] = None
    suggested_url: Optional[str] = None


class TrainingRequestOut(BaseModel):
    request_id: Any
    agent_id: Any
    reason: str
    confidence_score: Optional[float] = None
    suggested_url: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    agent_name: Optional[str] = None
    role: Optional[str] = None


@router.post("/training-request")
async def submit_training_request(req: TrainingRequestIn):
    try:
        pool = await get_db()

        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'training_requests'"
            )
            if not exists:
                return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)

            request_id = f"TR-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

            await conn.execute(
                """
                INSERT INTO training_requests (
                    request_id, agent_id, reason,
                    confidence_score, suggested_url,
                    status, created_at
                ) VALUES ($1, $2, $3, $4, $5, 'PENDING', NOW())
                """,
                request_id,
                req.agent_id,
                req.reason,
                req.confidence_score,
                req.suggested_url,
            )

        return {
            "request_id": request_id,
            "status": "PENDING",
            "agent_id": req.agent_id,
        }
    except Exception as e:
        if _is_training_requests_unavailable(e):
            return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)
        raise


@router.get("/training-requests", response_model=List[TrainingRequestOut])
async def list_training_requests(status: Optional[str] = None):
    try:
        pool = await get_db()

        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'training_requests'"
            )
            if not exists:
                return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)

            if status:
                rows = await conn.fetch(
                    """
                    SELECT tr.*, ha.name AS agent_name, ha.role
                    FROM training_requests tr
                    LEFT JOIN hired_agents ha ON tr.agent_id = ha.agent_id
                    WHERE tr.status = $1
                    ORDER BY tr.created_at DESC
                    """,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT tr.*, ha.name AS agent_name, ha.role
                    FROM training_requests tr
                    LEFT JOIN hired_agents ha ON tr.agent_id = ha.agent_id
                    ORDER BY tr.created_at DESC
                    """
                )

        results = []
        for r in rows:
            data = dict(r)
            for key in ("created_at", "approved_at"):
                if data.get(key):
                    data[key] = data[key].isoformat()
            results.append(TrainingRequestOut(**data))
        return results
    except Exception as e:
        if _is_training_requests_unavailable(e):
            return JSONResponse(status_code=503, content=TRAINING_REQUESTS_UNAVAILABLE)
        raise


@router.patch("/development-points/{point_id}")
async def update_development_point(point_id: str, body: UpdatePointBody):
    """
    Spec endpoint: update development point status.
    Supports action-based body: approve, request_approval, dismiss; or direct status.
    Response: { success: true, point_id, new_status }.
    """
    valid_statuses = {"OPEN", "AWAITING_APPROVAL", "IN_TRAINING", "RESOLVED", "DISMISSED"}
    pool = await get_db()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM development_points WHERE id = $1 OR id::text = $1", point_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Point {point_id} niet gevonden")
    point_id = str(existing["id"])

    hr_spec = await _get_spec_hr()
    hr_service = await _get_hr_manager()
    new_status: Optional[str] = None

    if body.action:
        action = (body.action or "").strip().lower()
        if action == "approve":
            new_status = "IN_TRAINING"
            await hr_spec.update_point_status(point_id, new_status, body.approved_by or "ceo", body.source_url)
        elif action == "request_approval":
            new_status = "AWAITING_APPROVAL"
            await hr_spec.update_point_status(point_id, new_status, body.approved_by, body.source_url)
        elif action == "dismiss":
            success = await hr_service.dismiss_point(point_id)
            if not success:
                raise HTTPException(status_code=500, detail="Dismiss failed")
            new_status = "DISMISSED"
        else:
            raise HTTPException(status_code=400, detail=f"Ongeldige action. Gebruik: approve, request_approval, dismiss.")
    elif body.status:
        if body.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Ongeldige status. Kies uit: {valid_statuses}")
        new_status = body.status
        await hr_spec.update_point_status(point_id, new_status, body.approved_by, body.source_url)
    else:
        raise HTTPException(status_code=400, detail="Geef action of status op.")

    return {"success": True, "point_id": point_id, "new_status": new_status or body.status}


@router.post("/development-points/{point_id}/reproduce")
async def reproduce_development_point(point_id: str, arq_pool: ArqRedis = Depends(get_arq_pool)):
    """
    Start a new job based on the same run_id as this development point.
    Spec: POST /api/hr/development-points/:pointId/reproduce.
    Returns { job_id, status: "RUNNING" }.
    """
    pool = await get_db()
    async with pool.acquire() as conn:
        dp = await conn.fetchrow(
            "SELECT id, agent_id, details FROM development_points WHERE id = $1 OR id::text = $1",
            point_id,
        )
        if not dp:
            raise HTTPException(status_code=404, detail=f"Development point {point_id} niet gevonden")

        run_id = _extract_job_id_from_evidence(dp.get("details"))
        if not run_id:
            first_job = await conn.fetchval(
                """
                SELECT job_id FROM job_steps
                WHERE agent_id = $1 AND retry_reason IS NOT NULL AND trim(retry_reason) != ''
                ORDER BY started_at DESC NULLS LAST
                LIMIT 1
                """,
                dp["agent_id"],
            )
            run_id = str(first_job) if first_job else None
        if not run_id:
            raise HTTPException(
                status_code=400,
                detail="Geen run_id of evidence beschikbaar om te reproduceren.",
            )

        source = await conn.fetchrow(
            "SELECT id, user_id, job_post, context, source_platform FROM jobs WHERE id = $1",
            run_id,
        )
        if not source:
            raise HTTPException(status_code=404, detail=f"Bronjob {run_id} niet gevonden")

        user_id = str(source["user_id"])
        job_post = source.get("job_post") or ""
        if not job_post:
            ctx = source.get("context")
            if isinstance(ctx, dict) and ctx.get("job_post"):
                job_post = ctx["job_post"] or ""
            elif isinstance(ctx, str):
                try:
                    parsed = json.loads(ctx)
                    if isinstance(parsed, dict) and parsed.get("job_post"):
                        job_post = parsed["job_post"] or ""
                except (json.JSONDecodeError, ValueError):
                    pass
        if not job_post or len(job_post) < 10:
            raise HTTPException(status_code=400, detail="Bronjob heeft geen bruikbare job_post om te reproduceren.")

        source_platform = source.get("source_platform") or "custom"
        token_budget = 50_000
        new_job_id = str(uuid.uuid4())
        context = {"job_post": job_post, "source_platform": source_platform, "reproduced_from": run_id}

        await conn.execute(
            """
            INSERT INTO jobs (id, user_id, job_post, status, source_platform, context, token_budget, job_type, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now(), now())
            """,
            new_job_id,
            user_id,
            job_post,
            JobStatus.INTAKE_CLARIFICATION.value,
            source_platform,
            json.dumps(context),
            token_budget,
            "standard",
        )

    try:
        await arq_pool.enqueue_job("run_intake_inline", new_job_id, job_post)
    except Exception as e:
        logger.warning("Reproduce: intake enqueue failed for %s: %s", new_job_id, e)

    return {"job_id": new_job_id, "status": "RUNNING"}


@router.post("/development-points/{point_id}/resolve")
async def resolve_point(point_id: str, req: ResolveRequest):
    """Mark a development point as resolved."""
    hr = await _get_hr_manager()
    success = await hr.resolve_point(point_id, req.resolution)
    if not success:
        raise HTTPException(status_code=404, detail="Development point not found")
    return {"point_id": point_id, "status": "RESOLVED"}


@router.post("/development-points/{point_id}/dismiss")
async def dismiss_point(point_id: str):
    """Dismiss a development point."""
    hr = await _get_hr_manager()
    success = await hr.dismiss_point(point_id)
    if not success:
        raise HTTPException(status_code=404, detail="Development point not found")
    return {"point_id": point_id, "status": "DISMISSED"}


@router.post("/development-points/{point_id}/submit-for-approval", dependencies=[Depends(get_current_user)])
async def submit_for_approval(point_id: str):
    """HR Manager: set OPEN development point to AWAITING_APPROVAL."""
    pool = await get_db()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE development_points
            SET status = 'AWAITING_APPROVAL', updated_at = now()
            WHERE (id = $1 OR id::text = $1) AND status = 'OPEN'
            """,
            point_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Point niet gevonden of niet in status OPEN")
    return {"submitted": True, "point_id": point_id}


@router.post("/development-points/{point_id}/knowledge-source", dependencies=[Depends(get_current_user)])
async def add_knowledge_source(
    point_id: str,
    body: AddKnowledgeSourceRequest,
):
    """Sla een kennisbron op bij een development point (URL of tekst als data-URI in source_url)."""
    import base64
    pool = await get_db()
    async with pool.acquire() as conn:
        point = await conn.fetchrow(
            "SELECT id FROM development_points WHERE id = $1 OR id::text = $1",
            point_id,
        )
        if not point:
            raise HTTPException(status_code=404, detail="Development point niet gevonden")
        point_id = str(point["id"])

        if body.source_type == "url" and body.source_url:
            update_value = body.source_url
        elif body.source_type == "text" and body.source_text:
            encoded = base64.b64encode(body.source_text.encode("utf-8")).decode("ascii")
            update_value = f"data:text/plain;base64,{encoded}"
        else:
            raise HTTPException(status_code=400, detail="source_url of source_text vereist")

        await conn.execute(
            "UPDATE development_points SET source_url = $1, updated_at = now() WHERE id = $2",
            update_value,
            point_id,
        )
    return {"saved": True, "point_id": point_id, "source_type": body.source_type}


@router.post("/development-points/{point_id}/knowledge-source/file", dependencies=[Depends(get_current_user)])
async def add_knowledge_source_file(
    point_id: str,
    file: UploadFile = File(...),
):
    """Bestandsupload als kennisbron (opgeslagen als data-URI in source_url)."""
    import base64
    pool = await get_db()
    async with pool.acquire() as conn:
        point = await conn.fetchrow(
            "SELECT id FROM development_points WHERE id = $1 OR id::text = $1",
            point_id,
        )
        if not point:
            raise HTTPException(status_code=404, detail="Development point niet gevonden")
        point_id = str(point["id"])

        content = await file.read()
        encoded = base64.b64encode(content).decode("ascii")
        media_type = file.content_type or "application/octet-stream"
        data_uri = f"data:{media_type};base64,{encoded}"

        await conn.execute(
            "UPDATE development_points SET source_url = $1, updated_at = now() WHERE id = $2",
            data_uri,
            point_id,
        )
    return {"saved": True, "point_id": point_id, "filename": file.filename}


@router.post("/development-points/{point_id}/approve", dependencies=[Depends(get_current_user)])
async def approve_development_point(
    point_id: str,
    body: ApproveTrainingRequest,
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """CEO: approve (set IN_TRAINING, start TrainingWorkflow) or reject (set DISMISSED) a development point."""
    pool = await get_db()
    async with pool.acquire() as conn:
        point = await conn.fetchrow(
            """
            SELECT * FROM development_points
            WHERE (id = $1 OR id::text = $1) AND status = 'AWAITING_APPROVAL'
            """,
            point_id,
        )
        if not point:
            raise HTTPException(status_code=404, detail="Point niet gevonden of niet in AWAITING_APPROVAL")
        point_id = str(point["id"])
        agent_id = point.get("agent_id")
        approved_by = body.approved_by or "operator"

    if body.approved:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE development_points
                SET status = 'IN_TRAINING',
                    source_url = COALESCE($2, source_url),
                    updated_at = now()
                WHERE id = $1
                """,
                point_id,
                body.source_url or point.get("source_url"),
            )
        final_url = body.source_url or point.get("source_url")
        if final_url:
            try:
                await arq_pool.enqueue_job("start_agent_training", agent_id, final_url, approved_by)
            except Exception as e:
                logger.warning("TrainingWorkflow start mislukt voor point %s: %s", point_id, e)
        return {"approved": True, "point_id": point_id, "training_started": bool(final_url)}
    else:
        async with pool.acquire() as conn:
            cols = await _get_table_columns(conn, "development_points")
            set_clauses = ["status = 'DISMISSED'", "updated_at = now()"]
            params = [point_id]
            if "summary" in cols:
                set_clauses.append("summary = COALESCE(summary || ' | Afgewezen: ' || $2, 'Afgewezen: ' || $2)")
                params.append(body.rejection_reason or "Geen reden opgegeven")
            await conn.execute(
                f"""
                UPDATE development_points
                SET {', '.join(set_clauses)}
                WHERE id = $1
                """,
                *params,
            )
        return {"approved": False, "point_id": point_id}


@router.post("/scan")
async def trigger_scan(since_days: int = Query(default=7)):
    """Manually trigger an HR scan. Uses spec agent (retry_count, agent_id from job_steps) + direct_chat scan."""
    hr = await _get_spec_hr()
    try:
        job_results = await hr.scan_job_steps(since_days=since_days)
        chat_results = await hr.scan_direct_chats(since_days=since_days)
        results = job_results + chat_results
    except Exception as e:
        logger.error("HR scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    created = sum(1 for r in results if r.get("action") == "created")
    incremented = sum(1 for r in results if r.get("action") == "incremented")
    return {"scanned_days": since_days, "results": results, "created": created, "incremented": incremented}


@router.post("/run-ab-validation")
async def run_ab_validation():
    """P8: Run A/B validation for IN_TRAINING development points."""
    import time
    pool = await get_db()
    hr = await _get_spec_hr()
    start = time.perf_counter()
    try:
        result = await hr.run_ab_validation(pool)
    except Exception as e:
        logger.error("A/B validation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    duration_ms = int((time.perf_counter() - start) * 1000)
    return {**result, "duration_ms": duration_ms}


@router.post("/detect-cross-training")
async def detect_cross_training():
    """P8: Detect cross-training opportunities from lessons."""
    pool = await get_db()
    hr = await _get_spec_hr()
    try:
        created = await hr.detect_cross_training_opportunities(pool)
    except Exception as e:
        logger.error("Detect cross-training failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    return {"proposals_created": created}


@router.get("/cross-training-proposals")
async def list_cross_training_proposals(status: str = Query("pending")):
    """P8: List cross-training proposals (default: pending)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'cross_training_proposals'"
        )
        if not exists:
            return []
        rows = await conn.fetch(
            """
            SELECT proposal_id, lesson_id, source_agent_id, target_agent_ids, reason, status, created_at
            FROM cross_training_proposals
            WHERE status = $1
            ORDER BY created_at DESC
            """,
            status,
        )
    return [
        {
            "proposal_id": str(r["proposal_id"]),
            "lesson_id": r["lesson_id"],
            "source_agent_id": r["source_agent_id"],
            "target_agent_ids": r["target_agent_ids"] or [],
            "reason": r["reason"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]


class CrossTrainRequest(BaseModel):
    proposal_id: str
    approved: bool
    source_url: Optional[str] = None


@router.post("/cross-train")
async def cross_train(req: CrossTrainRequest):
    """P8: Approve or reject a cross-training proposal."""
    pool = await get_db()
    async with pool.acquire() as conn:
        prop = await conn.fetchrow(
            "SELECT * FROM cross_training_proposals WHERE proposal_id = $1",
            req.proposal_id,
        )
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if prop["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Proposal status is {prop['status']}")

    if not req.approved:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE cross_training_proposals SET status = 'rejected' WHERE proposal_id = $1",
                req.proposal_id,
            )
        return {"proposal_id": req.proposal_id, "status": "rejected"}

    # Approved: run training for each target agent
    from app.services.training_workflow import TrainingWorkflow
    import json

    lesson_id = prop["lesson_id"]
    source_url = req.source_url
    target_ids = prop["target_agent_ids"]
    if isinstance(target_ids, str):
        target_ids = json.loads(target_ids) if target_ids else []
    if not isinstance(target_ids, list):
        target_ids = []

    if source_url:
        workflow = TrainingWorkflow(pool)
        for agent_id in target_ids:
            try:
                await workflow.start_training(agent_id, source_url, approved_by="ceo")
            except Exception as e:
                logger.warning("Cross-train start_training failed for %s: %s", agent_id, e)
    else:
        # Store lesson text as chunk in agent_knowledge per target
        async with pool.acquire() as conn:
            lesson_row = await conn.fetchrow(
                "SELECT fix, title, gevonden, oorzaak FROM lessons WHERE lesson_id = $1",
                lesson_id,
            )
        text = ""
        if lesson_row:
            text = "\n\n".join(
                filter(None, [lesson_row.get("title"), lesson_row.get("gevonden"), lesson_row.get("oorzaak"), lesson_row.get("fix")])
            )
        if not text:
            text = f"Lesson {lesson_id}"
        source_ref = f"lesson:{lesson_id}"
        from app.services.training import generate_embedding
        for agent_id in target_ids:
            try:
                embedding = await generate_embedding(text[:8000])
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO agent_knowledge (agent_id, source_url, chunk_text, embedding, chunk_index, is_active)
                        VALUES ($1, $2, $3, $4::vector, 0, true)
                        """,
                        agent_id,
                        source_ref,
                        text[:12000],
                        json.dumps(embedding),
                    )
            except Exception as e:
                logger.warning("Cross-train chunk insert failed for %s: %s", agent_id, e)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE cross_training_proposals SET status = 'completed', completed_at = now() WHERE proposal_id = $1",
            req.proposal_id,
        )
    return {"proposal_id": req.proposal_id, "status": "completed", "targets": target_ids}


@router.get("/notifications")
async def list_ceo_notifications():
    """P8: List unread CEO notifications."""
    pool = await get_db()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ceo_notifications'"
        )
        if not exists:
            return []
        rows = await conn.fetch(
            """
            SELECT notification_id, type, message, related_id, is_read, created_at
            FROM ceo_notifications
            WHERE is_read = false
            ORDER BY created_at DESC
            """
        )
    return [
        {
            "notification_id": str(r["notification_id"]),
            "type": r["type"],
            "message": r["message"],
            "related_id": r["related_id"],
            "is_read": r["is_read"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        }
        for r in rows
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """P8: Mark a CEO notification as read."""
    pool = await get_db()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ceo_notifications'"
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Table not found")
        await conn.execute(
            "UPDATE ceo_notifications SET is_read = true WHERE notification_id = $1",
            notification_id,
        )
    return {"notification_id": notification_id, "is_read": True}


@router.post("/check-effectiveness/{point_id}")
async def check_training_effectiveness(point_id: str):
    """
    Vergelijkt retry frequentie voor en na training voor een development point.
    """
    pool = await get_db()

    try:
        async with pool.acquire() as conn:
            point = await conn.fetchrow(
                "SELECT * FROM development_points WHERE id = $1",
                point_id,
            )
            if not point:
                raise HTTPException(
                    status_code=404,
                    detail=f"Development point {point_id} not found",
                )

            agent_id = point["agent_id"]
            issue = point.get("title") or point.get("details") or ""
            baseline_at = point["created_at"]

            before_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM job_steps
                WHERE agent_id = $1
                AND (output_data::text ILIKE $2 OR input_data::text ILIKE $2)
                AND started_at < $3
                """,
                agent_id,
                f"%{issue}%",
                baseline_at,
            ) or 0

            after_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM job_steps
                WHERE agent_id = $1
                AND (output_data::text ILIKE $2 OR input_data::text ILIKE $2)
                AND started_at >= $3
                """,
                agent_id,
                f"%{issue}%",
                baseline_at,
            ) or 0

            resolved = after_count < before_count

            if resolved:
                await conn.execute(
                    """
                    UPDATE development_points
                    SET status = 'RESOLVED'
                    WHERE id = $1
                    """,
                    point_id,
                )
                new_status = "RESOLVED"
            else:
                new_status = point["status"]

        return {
            "point_id": point_id,
            "agent_id": agent_id,
            "before_count": before_count,
            "after_count": after_count,
            "resolved": resolved,
            "status": new_status,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

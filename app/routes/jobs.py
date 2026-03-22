"""
Job flow API routes for the intake, planning, and execution workflow.

Endpoints:
- POST /api/jobs - Create a new job (start intake)
- PATCH /api/jobs/{job_id}/answer - Submit intake answers
- POST /api/jobs/{job_id}/approve-plan - Approve execution plan
- POST /api/jobs/{job_id}/request-changes - Request plan changes
- POST /api/jobs/{job_id}/feedback - Submit feedback on completed work
- POST /api/jobs/{job_id}/approve - Final approval and deploy
- GET /api/jobs/{job_id} - Get job details
- PATCH /api/jobs/{job_id}/publish - Sla gepubliceerde URL op (COMPLETED jobs)
"""

import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, Form, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from arq import ArqRedis

from app.utils.document_parser import extract_text_from_file, ALLOWED_EXTENSIONS

from app.database import get_db
from app.middleware.auth import get_current_user, TokenPayload
from app.orchestration.manager import OperationsManager
from app.services.deployment import DeploymentService
from app.dependencies import get_arq_pool
from models.unified import JobStatus
from tools.unified_bridge import UnifiedToolBridge
from app.services.job_pipeline import (
    run_intake_inline,
    run_intake_answers_inline,
    run_job_inline,
    run_data_pipeline,
    _update_job_context,
)
from app.services.client_mention import resolve_first_mention
from app.services.client_context import extract_client_context
from app.models.requests import (
    CreateJobRequest,
    SubmitAnswersRequest,
    ChatMessageRequest,
    FeedbackRequest,
    ApprovePlanRequest,
    ApproveJobRequest,
    CreateJobResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])

GTM_JOB_KEYWORDS = ["gtm", "campagne", "campaign", "launch", "go-to-market", "lancering", "marktintroductie", "marketing strategie"]


class PublishJobBody(BaseModel):
    published_url: str = Field(..., min_length=10)
    published_at: Optional[datetime] = None


def _normalize_published_url(u: str) -> str:
    return (u or "").strip().rstrip("/").lower()


def get_token_budget(job_post: str) -> int:
    """GTM jobs get higher token budget (150k vs 50k default)."""
    if not job_post or not isinstance(job_post, str):
        return 50_000
    job_lower = job_post.lower()
    if any(kw in job_lower for kw in GTM_JOB_KEYWORDS):
        return 150_000
    return 50_000


def _json_default(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _to_jsonable(obj):
    """Recursively convert to JSON-serializable types (UUID/datetime from asyncpg)."""
    if obj is None:
        return None
    if hasattr(obj, "hex"):  # UUID
        return str(obj)
    if hasattr(obj, "isoformat"):  # datetime/date
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if hasattr(obj, "__float__") and not isinstance(obj, bool):  # Decimal, etc.
        return float(obj)
    return str(obj)  # fallback for any other type (e.g. Enum)


# ============ Dependency: Get OperationsManager ============

def get_operations_manager():
    """Return configured OperationsManager instance."""
    # The agent_runner callback would be configured here
    # For now, a simple placeholder
    def dummy_runner(agent_name: str, input_data: dict) -> dict:
        return {"status": "success", "summary": f"Ran {agent_name}"}
    
    return OperationsManager(agent_runner=dummy_runner)


def get_deployment_service() -> DeploymentService:
    """Return configured DeploymentService instance."""
    mode = os.getenv("DEPLOYMENT_MODE", "dry_run").lower()
    dry_run = mode != "live"
    tool_bridge = UnifiedToolBridge()
    return DeploymentService(tool_bridge=tool_bridge, dry_run=dry_run)


def _validate_job_id(job_id: str) -> str:
    """Validate job_id is a valid UUID."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job_id format (must be UUID)"
        )
    return job_id


async def _next_step_index(conn, job_id: str) -> int:
    row = await conn.fetchrow(
        "SELECT COALESCE(MAX(step_index), 0) AS max_index FROM job_steps WHERE job_id=$1",
        job_id
    )
    return (row.get("max_index") or 0) + 1


MAX_JOB_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ============ Routes ============

@router.post("/upload")
async def upload_job_file(file: UploadFile = File(...)):
    """
    Extract text from uploaded file (PDF, CSV, .md, .docx, .xlsx, .txt).
    Returns extracted_text for use in job_post when creating a job.
    """
    raw = await file.read()
    if len(raw) > MAX_JOB_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_JOB_FILE_SIZE // 1024 // 1024} MB)")
    filename = file.filename or "document"
    try:
        text = extract_text_from_file(filename, raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"extracted_text": text, "filename": filename}


@router.post("", response_model=CreateJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    req: CreateJobRequest,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    current_user: Annotated[TokenPayload, Depends(get_current_user)] = None,
):
    """
    Create a new job and start the intake flow.
    
    The CEO Agent will analyze the job post and either:
    - Ask clarifying questions (status: INTAKE_CLARIFICATION)
    - Propose a plan (status: PLAN_PROPOSED)
    
    Validation:
    - user_id must be a valid UUID
    - job_post must be at least 10 characters
    - source_platform is optional (defaults to 'custom' if omitted)
    """
    pool = await get_db()
    # #region agent log
    try:
        from app.debug_log import log_anthropic_key
        log_anthropic_key("jobs.py:create_job", "request handler env key", "H1", "run1")
    except Exception:
        pass
    # #endregion

    job_id = str(uuid.uuid4())
    source_platform = req.source_platform or "custom"
    # Prefer authenticated user_id from JWT; fall back to request body
    auth_user_id = current_user.user_id if current_user else None
    effective_user_id = auth_user_id or str(req.user_id)
    try:
        uuid.UUID(effective_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format (must be UUID)"
        )
    try:
        logger.info("Creating job %s for user %s (auth=%s, body=%s)", job_id, effective_user_id, auth_user_id, req.user_id)

        # Parse @client mention so pipeline and agents get client context
        client_slug = await resolve_first_mention(pool, effective_user_id, req.job_post)
        context = {
            "job_post": req.job_post,
            "source_platform": source_platform,
        }
        if client_slug:
            context["client_slug"] = client_slug
            context["injected_context"] = await extract_client_context(req.job_post, effective_user_id)
            logger.info("Job %s: client_slug=%s from @mention", job_id, client_slug)

        async with pool.acquire() as conn:
            if client_slug:
                row = await conn.fetchrow(
                    "SELECT client_name FROM clients WHERE user_id = $1 AND slug = $2",
                    effective_user_id,
                    client_slug,
                )
                if row:
                    context["client_name"] = row["client_name"]
            token_budget = get_token_budget(req.job_post)
            job_type = (req.job_type or "standard").strip() or "standard"
            await conn.execute(
                """
                INSERT INTO jobs (id, user_id, job_post, status, source_platform, context, token_budget, job_type, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now(), now())
                """,
                job_id,
                effective_user_id,
                req.job_post,
                JobStatus.INTAKE_CLARIFICATION.value,
                source_platform,
                json.dumps(context, default=_json_default),
                token_budget,
                job_type,
            )
        
        logger.info(f"Job {job_id} created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )
    
    # Queue intake flow (don't wait for result)
    try:
        await arq_pool.enqueue_job("run_intake_inline", job_id, req.job_post)
        logger.info(f"Intake task queued for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to queue intake task for job {job_id}: {e}", exc_info=True)
        # Don't fail the request if task queueing fails initially
    
    return CreateJobResponse(
        job_id=job_id,
        status=JobStatus.INTAKE_CLARIFICATION.value,
        message="Job created. Intake analysis queued."
    )


@router.post("/{job_id}/run-intake")
async def trigger_run_intake(job_id: str):
    """
    Run intake synchronously in this request.
    Use when background tasks are not run (e.g. serverless or separate workers).
    Only allowed when job status is INTAKE_CLARIFICATION.
    """
    job_id = _validate_job_id(job_id)
    logger.info("run-intake endpoint called for job %s", job_id)
    pool = await get_db()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if job["status"] != JobStatus.INTAKE_CLARIFICATION.value:
            # Intake already completed or not applicable; return 200 so UI doesn't show an error.
            return {
                "job_id": job_id,
                "status": job["status"],
                "message": "Intake already completed",
            }
        job_post = job.get("job_post") or ""
        ctx = job.get("payload") or job.get("context")
        if ctx and isinstance(ctx, dict) and ctx.get("job_post"):
            job_post = ctx["job_post"] or job_post
        elif ctx and isinstance(ctx, str):
            try:
                parsed = json.loads(ctx)
                if isinstance(parsed, dict) and parsed.get("job_post"):
                    job_post = parsed["job_post"] or job_post
            except json.JSONDecodeError:
                pass
    await run_intake_inline(job_id, job_post)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM jobs WHERE id=$1", job_id)
    return {"job_id": job_id, "status": row["status"], "message": "Intake completed."}


def _coerce_context(raw) -> dict:
    """Coerce context from DB to a plain dict. Handles None, dict, str,
    and double/triple-encoded JSON strings (JSONB string wrapping JSON)."""
    val = raw
    # Unwrap up to 3 layers of JSON-encoded strings
    for _ in range(3):
        if val is None:
            return {}
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, ValueError):
                return {}
        else:
            return {}
    # If after 3 rounds we still don't have a dict, give up
    return val if isinstance(val, dict) else {}


def _job_for_response(job_row) -> dict:
    """Prepare job dict for API response: inject job_number from dedicated column(s) into context.
    Prefer ``job_number`` (eigen kolom) then legacy ``job_number_int``.
    Uses payload or context (production may have payload only) so UI gets a single context object.
    """
    d = dict(job_row)
    d.pop("file_artifact_path", None)  # Don't expose server path to frontend
    jni = d.get("job_number")
    if jni is None:
        jni = d.get("job_number_int")
    raw_ctx = d.get("payload") or d.get("context")
    ctx = _coerce_context(raw_ctx)
    if jni is not None:
        ctx["job_number"] = f"{jni:04d}"
    elif "job_number" not in ctx:
        ctx["job_number"] = "?"
    d["context"] = ctx
    return d


def build_document_preview(job: dict) -> dict:
    """Build document_preview for the live document viewer. Uses context.final_content and
    payload.proposed_data as content sources (no separate artifact column on jobs).
    """
    status = job.get("status")
    context = job.get("context") or {}
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except Exception:
            context = {}
    if not isinstance(context, dict):
        context = {}

    payload = job.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

    # Content sources: context.final_content (job_pipeline), payload.proposed_data (nexus, may be string)
    def _final_content() -> str:
        c = context.get("final_content")
        if isinstance(c, str):
            return c
        pd = payload.get("proposed_data")
        if isinstance(pd, str):
            return pd
        if isinstance(pd, dict):
            return pd.get("content") or pd.get("text") or ""
        ctx_pd = context.get("proposed_data")
        if isinstance(ctx_pd, str):
            return ctx_pd
        if isinstance(ctx_pd, dict):
            return ctx_pd.get("content") or ctx_pd.get("text") or ""
        return ""

    def _steps_list():
        steps = (payload.get("plan") or {}).get("steps") if isinstance(payload.get("plan"), dict) else None
        if isinstance(steps, list):
            return steps
        steps = (context.get("plan") or {}).get("steps") if isinstance(context.get("plan"), dict) else None
        if isinstance(steps, list):
            return steps
        steps = payload.get("steps")
        return steps if isinstance(steps, list) else []

    title_fallback = job.get("job_post") or job.get("description") or "Document"
    if isinstance(title_fallback, str) and len(title_fallback) > 60:
        title_fallback = title_fallback[:57] + "..."

    if status == "INTAKE_CLARIFICATION":
        client_name = context.get("client_name", "") or ""
        subtitle = "Wordt aangevuld tijdens intake"
        if client_name:
            subtitle = f"{subtitle} — {client_name}"
        return {
            "type": "brief",
            "title": "Client Brief",
            "content": context.get("job_post") or job.get("description") or "",
            "subtitle": subtitle,
        }
    elif status == "PLAN_PROPOSED":
        steps = _steps_list()
        return {
            "type": "plan",
            "title": "Voorgesteld Plan",
            "steps": steps,
            "subtitle": f"{len(steps)} stappen",
        }
    elif status == "RUNNING":
        partial = context.get("final_content") or context.get("partial_content") or context.get("draft") or ""
        if not partial and isinstance(payload.get("proposed_data"), str):
            partial = payload["proposed_data"]
        return {
            "type": "draft",
            "title": "Bezig met genereren...",
            "content": partial,
            "subtitle": "Live preview",
        }
    elif status in ("JOB_READY", "COMPLETED"):
        content = _final_content()
        return {
            "type": "final",
            "title": title_fallback,
            "content": content,
            "subtitle": "Klaar voor review" if status == "JOB_READY" else "Goedgekeurd",
        }
    else:
        return {
            "type": "empty",
            "title": "Document",
            "content": "",
            "subtitle": "",
        }


@router.post("/{job_id}/chat")
async def send_chat_message(
    job_id: str,
    request: Request,
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Send a chat message for this job. Accepts:
    - multipart/form-data: message (required), file (optional)
    - application/json: { "message": "..." }
    - INTAKE_CLARIFICATION: appends message, re-runs intake (CEO may reply).
    - RUNNING: appends message to chat_history only (no re-run); user can still type and messages are stored.
    - Other statuses: 400.
    """
    job_id = _validate_job_id(job_id)
    content_type = (request.headers.get("content-type") or "").lower()
    msg = ""
    file = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        msg = (form.get("message") or "").strip()
        file = form.get("file")  # UploadFile or None
    else:
        try:
            body = await request.json()
            msg = (body.get("message") or "").strip()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    # Process optional file attachment
    attachment_info = None
    if file and file.filename:
        try:
            raw = await file.read()
            ext = (file.filename or "").lower().split(".")[-1] if "." in (file.filename or "") else ""
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type .{ext} not allowed. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                )
            summary = ""
            if ext in ("pdf", "xlsx", "xls", "csv", "docx", "txt", "md", "skill"):
                summary = extract_text_from_file(file.filename, raw)
            else:
                summary = f"[Image: {file.filename}]"
            attachment_info = {
                "filename": file.filename,
                "content_type": file.content_type or "application/octet-stream",
                "stored_at": datetime.utcnow().isoformat() + "Z",
                "summary": summary[:50000] if summary else "",  # cap for DB
            }
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    pool = await get_db()
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        status_val = job["status"]
        # #region agent log
        try:
            from app.debug_log import log_anthropic_key
            log_anthropic_key("jobs.py:send_chat_message", "before intake/ceo task dispatch", "H1", "run1")
        except Exception:
            pass
        # #endregion
        job_ctx = job.get("payload") or job.get("context")
        if status_val == JobStatus.INTAKE_CLARIFICATION.value:
            ctx = _coerce_context(job_ctx)
            chat_history = list(ctx.get("chat_history") or [])
            user_entry = {"role": "user", "content": msg}
            if attachment_info:
                user_entry["attachment"] = attachment_info
                attachments = list(ctx.get("attachments") or [])
                attachments.append(attachment_info)
                chat_history.append(user_entry)
                await _update_job_context(conn, job_id, {"chat_history": chat_history, "attachments": attachments})
            else:
                chat_history.append(user_entry)
                await _update_job_context(conn, job_id, {"chat_history": chat_history})
            await arq_pool.enqueue_job("run_intake_answers_inline", job_id, None)
            row = await conn.fetchrow("SELECT status FROM jobs WHERE id=$1", job_id)
            return {
                "job_id": job_id,
                "status": row["status"] if row else JobStatus.INTAKE_CLARIFICATION.value,
                "message": "Message sent. Re-analyzing...",
            }
        if status_val == JobStatus.RUNNING.value:
            from app.services.job_pipeline import ceo_reply_during_run
            ctx = _coerce_context(job_ctx)
            chat_history = list(ctx.get("chat_history") or [])
            user_entry = {"role": "user", "content": msg}
            if attachment_info:
                user_entry["attachment"] = attachment_info
                attachments = list(ctx.get("attachments") or [])
                attachments.append(attachment_info)
            chat_history.append(user_entry)
            user_msg_for_ceo = msg
            if attachment_info and attachment_info.get("summary"):
                user_msg_for_ceo = msg + "\n\n[Attachment: " + attachment_info.get("filename", "file") + "]\n" + attachment_info["summary"]
            try:
                ceo_reply, instruction = await ceo_reply_during_run(conn, job_id, ctx, user_msg_for_ceo)
            except Exception as e:
                logger.warning("ceo_reply_during_run failed for job %s: %s", job_id, e)
                ceo_reply = "Ik heb je bericht ontvangen en geef het door aan het team."
                instruction = msg[:200]
            chat_history.append({"role": "ceo", "content": ceo_reply})
            feedback_list = list(ctx.get("feedback_during_run") or [])
            feedback_list.append({"user": msg, "ceo_instruction": instruction or msg[:200]})
            updates = {
                "chat_history": chat_history,
                "feedback_during_run": feedback_list,
                "ceo_instruction_for_run": instruction or (feedback_list[-1]["ceo_instruction"] if feedback_list else ""),
            }
            if attachment_info:
                updates["attachments"] = attachments
            await _update_job_context(conn, job_id, updates)
            return {
                "job_id": job_id,
                "status": status_val,
                "message": "Message sent. CEO replied.",
            }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chat only available during intake or execution (current: {status_val})",
        )


@router.patch("/{job_id}/answer")
async def submit_intake_answer(
    job_id: str,
    req: SubmitAnswersRequest,
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    User submits answers to clarification questions.
    
    The CEO will re-analyze and either:
    - Ask more questions
    - Propose a plan
    
    Validation:
    - job_id must be a valid UUID
    - answers dict must not be empty
    - answers values must be non-empty strings
    """
    job_id = _validate_job_id(job_id)
    pool = await get_db()
    
    # Verify job exists
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
        if not job:
            logger.warning(f"Job not found: {job_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        if job['status'] not in [JobStatus.INTAKE_CLARIFICATION.value]:
            logger.warning(f"Invalid status for answers on job {job_id}: {job['status']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is not in INTAKE_CLARIFICATION status"
            )
    
    try:
        logger.info(f"Processing intake answers for job {job_id}")
        
        # Store clarification answers
        async with pool.acquire() as conn:
            for q_id, answer in req.answers.items():
                await conn.execute(
                    """
                    UPDATE clarifications
                    SET user_answer = $1, answered_at = now()
                    WHERE question_id = $2 AND job_id = $3
                    """,
                    answer, q_id, job_id
                )
        
        # Queue intake answers processing
        await arq_pool.enqueue_job("run_intake_answers_inline", job_id, req.answers)
        logger.info(f"Intake answers task queued for job {job_id}")
        
        # Fetch updated job status
        async with pool.acquire() as conn:
            updated_job = await conn.fetchrow("SELECT status FROM jobs WHERE id=$1", job_id)
        
        return {
            "job_id": job_id,
            "status": updated_job['status'],
            "message": "Answers submitted. Re-analyzing..."
        }
    
    except ValidationError as e:
        logger.warning(f"Validation error for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to process answers for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process answers: {str(e)}"
        )


@router.post("/{job_id}/approve-plan")
async def approve_plan(
    job_id: str,
    arq_pool: ArqRedis = Depends(get_arq_pool),
    manager: OperationsManager = Depends(get_operations_manager)
):
    """
    User approves the proposed execution plan.
    
    Sets status to RUNNING and kicks off the workflow.
    """
    job_id = _validate_job_id(job_id)
    pool = await get_db()
    
    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        current_status = job["status"]

        # Already finished: idempotent success
        if current_status in (JobStatus.JOB_READY.value, JobStatus.COMPLETED.value):
            return {
                "job_id": job_id,
                "status": current_status,
                "message": "Job already in final state."
            }

        # Already RUNNING: recover if all steps completed (e.g. client timed out on first approve)
        if current_status == JobStatus.RUNNING.value:
            steps = await conn.fetch(
                "SELECT id, status, output FROM job_steps WHERE job_id=$1 ORDER BY step_index",
                job_id,
            )
            all_done = len(steps) > 0 and all(s.get("status") in ("completed", "success") for s in steps)
            if all_done:
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.JOB_READY.value,
                    job_id,
                )
                logger.info(f"approve-plan: recovered job {job_id} to JOB_READY (all steps done)")
                return {
                    "job_id": job_id,
                    "status": JobStatus.JOB_READY.value,
                    "message": "Recovered: all steps were done, job set to JOB_READY."
                }
            return {
                "job_id": job_id,
                "status": JobStatus.RUNNING.value,
                "message": "Job is already running. Status updates every 5 seconds."
            }

        if current_status != JobStatus.PLAN_PROPOSED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is not in PLAN_PROPOSED state (current: {current_status})"
            )

        # data_query: run data pipeline only; do not start content pipeline or NEXUS
        context = _coerce_context(job.get("payload") or job.get("context"))
        if context.get("detected_task_type") == "data_query":
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                    JobStatus.RUNNING.value,
                    job_id,
                )
            await arq_pool.enqueue_job("run_data_pipeline", job_id)
            logger.info("approve_plan: data_query job %s, run_data_pipeline queued", job_id)
            return {
                "job_id": job_id,
                "status": JobStatus.RUNNING.value,
                "message": "Plan approved. Data pipeline started."
            }

    try:
        logger.info(f"Approving plan for job {job_id}")
        # Set RUNNING and start pipeline first so execution always starts even if manager fails
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.RUNNING.value,
                job_id,
            )
        context = _coerce_context(job.get("payload") or job.get("context"))
        use_nexus = os.getenv("USE_NEXUS_PIPELINE", "false").lower() == "true"
        if use_nexus:
            import asyncio
            from app.orchestration.nexus_pipeline import NEXUSPipeline
            row = await pool.fetchrow(
                "SELECT * FROM jobs WHERE id=$1",
                job_id,
            )
            user_id = str(row["user_id"]) if row and row.get("user_id") else ""
            job_post = (row["job_post"] or "") if row else ""
            platform = (row["source_platform"] or "browser") if row else "browser"
            token_budget = int(row.get("token_budget") or 50000) if row else 50000
            await arq_pool.enqueue_job("run_job_pipeline", job_id)
            logger.info("NEXUS pipeline enqueued for job %s", job_id)
            return {
                "job_id": job_id,
                "status": JobStatus.RUNNING.value,
                "message": "Plan approved. Workflow started."
            }
        await arq_pool.enqueue_job("run_job_inline", job_id, context)
        logger.info("Pipeline queued in background for job %s", job_id)
        return {
            "job_id": job_id,
            "status": JobStatus.RUNNING.value,
            "message": "Plan approved. Workflow started."
        }
    
    except Exception as e:
        logger.error(f"Failed to approve plan for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve plan: {str(e)}"
        )


@router.post("/{job_id}/request-changes")
async def request_plan_changes(
    job_id: str,
    req: FeedbackRequest
):
    """
    User requests changes to the proposed plan.
    
    Returns job to INTAKE_CLARIFICATION for revision.
    """
    job_id = _validate_job_id(job_id)
    pool = await get_db()
    
    try:
        async with pool.acquire() as conn:
            job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            # Update job status and store feedback
            await _update_job_context(conn, job_id, {"feedback": req.feedback})
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.INTAKE_CLARIFICATION.value,
                job_id,
            )
        
        logger.info(f"Plan changes requested for job {job_id}")
        
        return {
            "job_id": job_id,
            "status": JobStatus.INTAKE_CLARIFICATION.value,
            "message": "Feedback recorded. Returning to intake phase."
        }
    
    except Exception as e:
        logger.error(f"Failed to request plan changes for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process request: {str(e)}"
        )


@router.post("/{job_id}/feedback")
async def submit_feedback(
    job_id: str,
    req: FeedbackRequest,
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    """
    User submits feedback on completed workflow results.
    Sets status to INTAKE_CLARIFICATION, adds feedback as user message in chat_history,
    and triggers run_intake_answers_inline so the CEO responds and can trigger revision.
    """
    job_id = _validate_job_id(job_id)
    pool = await get_db()
    
    try:
        async with pool.acquire() as conn:
            job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            if job['status'] not in [JobStatus.JOB_READY.value, JobStatus.AWAITING_APPROVAL.value, JobStatus.COMPLETED.value]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job is not ready for feedback (status: {job['status']})"
                )
            
            ctx = _coerce_context(job.get("payload") or job.get("context"))
            chat_history = list(ctx.get("chat_history") or [])
            chat_history.append({"role": "user", "content": req.feedback})
            await _update_job_context(
                conn,
                job_id,
                {"chat_history": chat_history, "user_feedback": req.feedback},
            )
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.INTAKE_CLARIFICATION.value,
                job_id,
            )
        
        await arq_pool.enqueue_job("run_intake_answers_inline", job_id, None)
        logger.info(f"Feedback submitted for job {job_id}, intake re-running")
        
        return {
            "job_id": job_id,
            "status": JobStatus.INTAKE_CLARIFICATION.value,
            "message": "Feedback recorded. CEO will respond in the chat."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit feedback for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


@router.post("/{job_id}/approve")
async def approve_and_deploy(
    job_id: str,
    deployment_service: DeploymentService = Depends(get_deployment_service)
):
    """
    Final approval: User approves results. For content jobs: deploy artifacts then COMPLETED.
    For data_query (pipeline_type=direct_response): status update to COMPLETED only, no deploy.
    Job must be in JOB_READY state.
    """
    job_id = _validate_job_id(job_id)
    pool = await get_db()

    try:
        async with pool.acquire() as conn:
            job = await conn.fetchrow(
                "SELECT id, status, context, payload FROM jobs WHERE id=$1",
                job_id,
            )
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )

            if job["status"] != JobStatus.JOB_READY.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job is not ready for approval (status: {job['status']})"
                )

            ctx = _coerce_context(job.get("payload") or job.get("context"))
            is_data_job = ctx.get("pipeline_type") == "direct_response"

            if is_data_job:
                # Data jobs: no deploy, only set COMPLETED
                await conn.execute(
                    "UPDATE jobs SET status=$1, updated_at=now(), finished_at=now() WHERE id=$2",
                    JobStatus.COMPLETED.value,
                    job_id,
                )
                await _update_job_context(conn, job_id, {"deployment": {"skipped": True, "reason": "data_job"}})
                logger.info("Job %s approved (data job, no deploy)", job_id)
                return {
                    "job_id": job_id,
                    "status": JobStatus.COMPLETED.value,
                    "deployment": None,
                    "message": "Job afgesloten."
                }

            # Content jobs: deploy then COMPLETED
            logger.info("Deploying artifacts for job %s", job_id)
            deploy_result = await deployment_service.deploy_job(conn, job_id)
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now(), finished_at=now() WHERE id=$2",
                JobStatus.COMPLETED.value,
                job_id,
            )
            await _update_job_context(conn, job_id, {"deployment": deploy_result})
        logger.info("Job %s approved and deployed successfully", job_id)
        return {
            "job_id": job_id,
            "status": JobStatus.COMPLETED.value,
            "deployment": deploy_result,
            "message": "Job approved and deployed."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to approve and deploy job %s: %s", job_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy: {str(e)}"
        )


@router.patch("/{job_id}/publish")
async def publish_job(
    job_id: str,
    body: PublishJobBody,
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    Koppel de live URL aan een afgeronde job (GSC feedback loop).
    Alleen COMPLETED; URL moet http(s) zijn en uniek over alle jobs.
    """
    job_id = _validate_job_id(job_id)
    raw_url = (body.published_url or "").strip()
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="published_url moet met http:// of https:// beginnen",
        )

    pool = await get_db()
    when = body.published_at
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when is None:
        when = datetime.now(timezone.utc)

    norm = _normalize_published_url(raw_url)

    async with pool.acquire() as conn:
        has_col = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'jobs' AND column_name = 'published_url'
            """
        )
        if not has_col:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="published_url kolom ontbreekt — migratie 088_gsc_feedback_loop.sql uitvoeren",
            )

        job = await conn.fetchrow(
            "SELECT id, user_id, status, published_url FROM jobs WHERE id = $1",
            job_id,
        )
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if str(job["user_id"]) != str(current_user.user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Geen toegang tot deze job")
        if job["status"] != JobStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Alleen COMPLETED jobs kunnen een published_url krijgen (nu: {job['status']})",
            )

        others = await conn.fetch(
            "SELECT id, published_url FROM jobs WHERE published_url IS NOT NULL AND id <> $1",
            uuid.UUID(job_id),
        )
        for row in others:
            if row.get("published_url") and _normalize_published_url(row["published_url"]) == norm:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Deze URL is al gekoppeld aan een andere job",
                )

        await conn.execute(
            """
            UPDATE jobs
            SET published_url = $1, published_at = $2, updated_at = now()
            WHERE id = $3
            """,
            raw_url,
            when,
            uuid.UUID(job_id),
        )
        updated = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)

    return _to_jsonable(_job_for_response(updated))


@router.get("")
async def list_jobs(status: Optional[str] = None, source: Optional[str] = None, limit: int = 50):
    """List all jobs, optionally filtered by status and/or intake source (browser, email)."""
    pool = await get_db()
    async with pool.acquire() as conn:
        use_source = source in ("browser", "email")
        # SELECT * so both schema variants work (context and/or payload; production may have payload only)
        if status and use_source:
            rows = await conn.fetch(
                "SELECT * FROM jobs WHERE status=$1 AND intake_source=$2 ORDER BY created_at DESC LIMIT $3",
                status, source, limit
            )
        elif status:
            rows = await conn.fetch(
                "SELECT * FROM jobs WHERE status=$1 ORDER BY created_at DESC LIMIT $2",
                status, limit
            )
        elif use_source:
            rows = await conn.fetch(
                "SELECT * FROM jobs WHERE intake_source=$1 ORDER BY created_at DESC LIMIT $2",
                source, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT $1",
                limit
            )
    return [_job_for_response(r) for r in rows]


@router.get("/{job_id}/download")
async def download_job_artifact(job_id: str):
    """Download Word/Excel artifact for a completed job."""
    job_id = _validate_job_id(job_id)
    pool = await get_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT file_artifact_path, file_artifact_name, file_artifact_type FROM jobs WHERE id=$1",
            job_id,
        )
    if not row or not row.get("file_artifact_path"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Geen bestand beschikbaar voor deze job")
    path = row["file_artifact_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bestand niet gevonden op server")
    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    return FileResponse(
        path=path,
        filename=row.get("file_artifact_name", "artifact"),
        media_type=media_types.get(row.get("file_artifact_type", ""), "application/octet-stream"),
    )


@router.get("/{job_id}/system-events")
async def get_job_system_events(job_id: str, request: Request):
    """Events voor een specifieke job. Gebruikt door de job-detail view."""
    job_id = _validate_job_id(job_id)
    svc = getattr(request.app.state, "system_events", None)
    if not svc:
        return {"events": [], "count": 0}
    events = await svc.get_events(job_id=job_id)
    return {"events": events, "count": len(events)}


@router.get("/{job_id}")
async def get_job(job_id: str):
    """
    Retrieve complete job details including status, steps, clarifications, and artifacts.
    """
    job_id = _validate_job_id(job_id)
    pool = await get_db()
    
    try:
        async with pool.acquire() as conn:
            # Fetch job
            job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            # Fetch clarifications
            clarifications = await conn.fetch(
                "SELECT * FROM clarifications WHERE job_id=$1 ORDER BY asked_at DESC",
                job_id
            )
            
            # Fetch steps
            steps = await conn.fetch(
                "SELECT * FROM job_steps WHERE job_id=$1 ORDER BY step_index",
                job_id
            )
            steps_list = list(steps)
            # Auto-recover: if status is RUNNING but all steps are completed, set to JOB_READY
            if job["status"] == "RUNNING" and len(steps_list) > 0:
                all_done = all(s.get("status") in ("completed", "success") for s in steps_list)
                if all_done:
                    # Scan steps for image_url and store in context before status update
                    for s in steps_list:
                        out = s.get("output")
                        if isinstance(out, str):
                            try:
                                out = json.loads(out)
                            except json.JSONDecodeError:
                                continue
                        if isinstance(out, dict) and out.get("image_url"):
                            await _update_job_context(conn, job_id, {"image_url": out["image_url"]})
                            break
                    await conn.execute(
                        "UPDATE jobs SET status='JOB_READY', updated_at=now() WHERE id=$1",
                        job_id,
                    )
                    job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
            
            # Fetch artifacts
            artifacts = await conn.fetch(
                "SELECT * FROM artifacts WHERE job_id=$1 AND artifact_type != 'context' ORDER BY created_at DESC",
                job_id
            )
        
        job_dict = _job_for_response(job)
        payload = {
            "job": job_dict,
            "document_preview": build_document_preview(job_dict),
            "clarifications": [dict(c) for c in clarifications],
            "steps": [dict(s) for s in steps],
            "artifacts": [dict(a) for a in artifacts]
        }
        return _to_jsonable(payload)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}"
        )

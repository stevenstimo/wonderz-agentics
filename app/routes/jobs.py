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
"""

import os
import uuid
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel, ValidationError

import app.db as _db
from app.orchestration.manager import OperationsManager
from app.services.deployment import DeploymentService
from models.unified import JobStatus
from tools.unified_bridge import UnifiedToolBridge
try:
    from workers.tasks import run_intake, run_intake_answers, run_job
except Exception as _task_import_error:
    _task_logger = logging.getLogger(__name__)

    class _NoopTask:
        def __init__(self, name: str):
            self._name = name

        def delay(self, *args, **kwargs):
            _task_logger.warning(
                "Task '%s' not scheduled because worker dependencies are unavailable: %s",
                self._name,
                _task_import_error,
            )

    run_intake = _NoopTask("run_intake")
    run_intake_answers = _NoopTask("run_intake_answers")
    run_job = _NoopTask("run_job")
from app.models.requests import (
    CreateJobRequest,
    SubmitAnswersRequest,
    FeedbackRequest,
    ApprovePlanRequest,
    ApproveJobRequest,
    CreateJobResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


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


# ============ Routes ============

@router.get("")
async def list_jobs(status_filter: str = None, limit: int = 50, offset: int = 0):
    """List all jobs, optionally filtered by status."""
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")
    async with pool.acquire() as conn:
        if status_filter:
            rows = await conn.fetch(
                "SELECT id, user_id, job_post, status, source_platform, context, created_at, updated_at "
                "FROM jobs WHERE status=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                status_filter, limit, offset
            )
        else:
            rows = await conn.fetch(
                "SELECT id, user_id, job_post, status, source_platform, context, created_at, updated_at "
                "FROM jobs ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
        jobs = []
        for r in rows:
            ctx = r["context"]
            if isinstance(ctx, str):
                import json as _json
                ctx = _json.loads(ctx)
            jobs.append({
                "job_id": str(r["id"]),
                "user_id": str(r["user_id"]),
                "job_post": r["job_post"][:200] if r["job_post"] else None,
                "status": r["status"],
                "source_platform": r["source_platform"],
                "context": ctx,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            })
        return {"jobs": jobs, "total": len(jobs)}


@router.post("", response_model=CreateJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(req: CreateJobRequest, background_tasks: BackgroundTasks = None):
    """
    Create a new job and start the intake flow.
    
    The CEO Agent will analyze the job post and either:
    - Ask clarifying questions (status: INTAKE_CLARIFICATION)
    - Propose a plan (status: PLAN_PROPOSED)
    
    Validation:
    - user_id must be a valid UUID
    - job_post must be at least 10 characters
    - source_platform defaults to 'shopify'
    """
    if not _db._pool:
        logger.error("DB pool not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database unavailable"
        )
    
    job_id = str(uuid.uuid4())
    
    try:
        logger.info(f"Creating job {job_id} for user {req.user_id}")
        
        async with _db._pool.acquire() as conn:
            # Create job record
            await conn.execute(
                """
                INSERT INTO jobs (id, user_id, job_post, status, source_platform, context, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, now(), now())
                """,
                job_id,
                req.user_id,
                req.job_post,
                JobStatus.INTAKE_CLARIFICATION.value,
                req.source_platform,
                json.dumps({"job_post": req.job_post})
            )
        
        logger.info(f"Job {job_id} created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create job: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )
    
    # Run intake flow
    async def _run_intake_inline(jid, jp):
        try:
            mgr = get_operations_manager()
            await mgr.start_intake_flow(jid, jp)
            logger.info(f"Intake completed for job {jid}")
        except Exception as exc:
            logger.error(f"Inline intake failed for job {jid}: {exc}", exc_info=True)

    try:
        run_intake.delay(job_id, req.job_post)
        logger.info(f"Intake task queued for job {job_id}")
    except Exception as e:
        logger.warning(f"Celery unavailable, running intake inline for job {job_id}: {e}")
        import asyncio
        asyncio.ensure_future(_run_intake_inline(job_id, req.job_post))
    
    return CreateJobResponse(
        job_id=job_id,
        status=JobStatus.INTAKE_CLARIFICATION.value,
        message="Job created. Intake analysis queued."
    )


@router.patch("/{job_id}/answer")
async def submit_intake_answer(
    job_id: str,
    req: SubmitAnswersRequest
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
    
    if not _db._pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database unavailable"
        )
    
    # Verify job exists
    async with _db._pool.acquire() as conn:
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
        async with _db._pool.acquire() as conn:
            for q_id, answer in req.answers.items():
                await conn.execute(
                    """
                    UPDATE clarifications
                    SET user_answer = $1, answered_at = now()
                    WHERE question_id = $2 AND job_id = $3
                    """,
                    answer, q_id, job_id
                )
        
        # Run intake answers processing
        async def _run_answers_inline(jid, answers):
            try:
                mgr_ans = get_operations_manager()
                await mgr_ans.handle_user_answer(jid, answers)
                logger.info(f"Intake answers processed for job {jid}")
            except Exception as exc:
                logger.error(f"Inline intake answers failed for job {jid}: {exc}", exc_info=True)

        try:
            run_intake_answers.delay(job_id, req.answers)
            logger.info(f"Intake answers task queued for job {job_id}")
        except Exception:
            logger.warning(f"Celery unavailable, running answers inline for job {job_id}")
            import asyncio
            asyncio.ensure_future(_run_answers_inline(job_id, req.answers))
        
        # Fetch updated job status
        async with _db._pool.acquire() as conn:
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
    manager: OperationsManager = Depends(get_operations_manager)
):
    """
    User approves the proposed execution plan.
    
    Sets status to RUNNING and kicks off the workflow.
    """
    job_id = _validate_job_id(job_id)
    
    if not _db._pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database unavailable"
        )
    
    async with _db._pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, status, context FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        if job['status'] != JobStatus.PLAN_PROPOSED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job is not in PLAN_PROPOSED state"
            )
    
    try:
        logger.info(f"Approving plan for job {job_id}")
        
        # Approve the plan (transitions to RUNNING)
        await manager.approve_plan(job_id)
        
        # Run job execution
        context = json.loads(job['context']) if isinstance(job['context'], str) else job['context']

        async def _run_job_inline(jid, ctx):
            try:
                from workers.tasks import _build_agent_runner
                runner = _build_agent_runner(jid)
                mgr_run = OperationsManager(agent_runner=runner)
                await mgr_run.run_workflow(jid, None, ctx)
                logger.info(f"Workflow completed for job {jid}")
            except Exception as exc:
                logger.error(f"Inline workflow failed for job {jid}: {exc}", exc_info=True)

        try:
            run_job.delay(job_id, None, context)
            logger.info(f"Job execution task queued for job {job_id}")
        except Exception:
            logger.warning(f"Celery unavailable, running workflow inline for job {job_id}")
            import asyncio
            asyncio.ensure_future(_run_job_inline(job_id, context))

        return {
            "job_id": job_id,
            "status": JobStatus.RUNNING.value,
            "message": "Plan approved. Workflow execution started."
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
    
    if not _db._pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database unavailable"
        )
    
    try:
        async with _db._pool.acquire() as conn:
            job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            # Update job status and store feedback
            await conn.execute(
                """
                UPDATE jobs SET status=$1, context=jsonb_set(context, '{feedback}', to_jsonb($2::text)), updated_at=now()
                WHERE id=$3
                """,
                JobStatus.INTAKE_CLARIFICATION.value,
                req.feedback,
                job_id
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
    req: FeedbackRequest
):
    """
    User submits feedback on completed workflow results.
    
    Job must be in JOB_READY or AWAITING_APPROVAL state.
    """
    job_id = _validate_job_id(job_id)
    
    if not _db._pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database unavailable"
        )
    
    try:
        async with _db._pool.acquire() as conn:
            job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            if job['status'] not in [JobStatus.JOB_READY.value, JobStatus.AWAITING_APPROVAL.value]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job is not ready for feedback (status: {job['status']})"
                )
            
            # Store feedback and transition back to RUNNING for revision
            await conn.execute(
                """
                UPDATE jobs SET status=$1, context=jsonb_set(context, '{user_feedback}', to_jsonb($2::text)), updated_at=now()
                WHERE id=$3
                """,
                JobStatus.RUNNING.value,
                req.feedback,
                job_id
            )
        
        # Queue job retry with feedback
        run_job.delay(job_id, None, {"feedback": req.feedback})
        logger.info(f"Feedback submitted for job {job_id}, retrying execution")
        
        return {
            "job_id": job_id,
            "status": JobStatus.RUNNING.value,
            "message": "Feedback recorded. Retrying with revisions."
        }
    
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
    Final approval: User approves results and triggers deployment.
    
    Job must be in JOB_READY state.
    Deployment happens in configured mode (dry_run by default).
    """
    job_id = _validate_job_id(job_id)
    
    if not _db._pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database unavailable"
        )
    
    try:
        async with _db._pool.acquire() as conn:
            job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found"
                )
            
            if job['status'] != JobStatus.JOB_READY.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job is not ready for approval (status: {job['status']})"
                )
            
            # Deploy the artifacts
            logger.info(f"Deploying artifacts for job {job_id}")
            deploy_result = await deployment_service.deploy_job(conn, job_id)
            
            # Update job status to COMPLETED
            await conn.execute(
                """
                UPDATE jobs SET status=$1, context=jsonb_set(context, '{deployment}', to_jsonb($2::jsonb)), updated_at=now()
                WHERE id=$3
                """,
                JobStatus.COMPLETED.value,
                json.dumps(deploy_result),
                job_id
            )
        
        logger.info(f"Job {job_id} approved and deployed successfully")
        
        return {
            "job_id": job_id,
            "status": JobStatus.COMPLETED.value,
            "deployment": deploy_result,
            "message": "Job approved and deployed."
        }
    
    except Exception as e:
        logger.error(f"Failed to approve and deploy job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy: {str(e)}"
        )


@router.post("/{job_id}/restart")
async def restart_job(job_id: str):
    """
    Restart a stuck job: reset to PLAN_PROPOSED and re-run the workflow.
    Works for AWAITING_APPROVAL, INTAKE_CLARIFICATION, PLAN_PROPOSED, FAILED.
    """
    job_id = _validate_job_id(job_id)
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        current = job['status']
        restartable = ['AWAITING_APPROVAL', 'INTAKE_CLARIFICATION', 'PLAN_PROPOSED', 'FAILED', 'JOB_READY', 'COMPLETED']
        if current not in restartable:
            raise HTTPException(
                status_code=400,
                detail=f"Job status '{current}' cannot be restarted. Only: {', '.join(restartable)}"
            )

        # Parse context
        ctx = job['context']
        if isinstance(ctx, str):
            ctx = json.loads(ctx)
        ctx = ctx or {}

        # If no plan exists yet, generate a default one
        if 'plan' not in ctx:
            ctx['brief'] = ctx.get('brief', {})
            ctx['brief']['is_complete'] = True
            ctx['plan'] = {
                'brief': ctx['brief'],
                'steps': [
                    {'agent_role': 'copywriter', 'step_index': 1, 'description': 'Write text', 'requires_approval': False},
                    {'agent_role': 'reviewer', 'step_index': 2, 'description': 'Review text', 'requires_approval': False},
                ],
                'hired_agents': ['copywriter', 'reviewer'],
                'estimated_duration_seconds': 120,
            }

        # Reset retry counter
        if 'metadata' in ctx:
            ctx['metadata']['retries'] = 0
            ctx['metadata'].pop('awaiting_manual_approval', None)

        # Clear previous agent output so copy_agent writes fresh
        ctx.pop('copy_agent', None)
        ctx.pop('reviewer_agent', None)

        # Update job to RUNNING and start workflow
        await conn.execute(
            "UPDATE jobs SET status='RUNNING', context=$1, updated_at=NOW() WHERE id=$2",
            json.dumps(ctx, default=str), job_id
        )

    # Run workflow in background
    try:
        from workers.tasks import run_job
        run_job.delay(str(job_id))
    except Exception:
        import asyncio
        from app.orchestration.manager import WorkflowManager
        wm = WorkflowManager()
        asyncio.create_task(
            wm.run_workflow(str(job_id), None, {'context': ctx})
        )

    return {
        'job_id': str(job_id),
        'status': 'RUNNING',
        'message': f'Job restarted from {current}. Workflow running.'
    }


@router.get("/{job_id}")
async def get_job(job_id: str):
    """
    Retrieve complete job details including status, steps, clarifications, and artifacts.
    """
    job_id = _validate_job_id(job_id)
    
    if not _db._pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database unavailable"
        )
    
    try:
        async with _db._pool.acquire() as conn:
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
            
            # Fetch artifacts
            artifacts = await conn.fetch(
                "SELECT * FROM artifacts WHERE job_id=$1 AND artifact_type != 'context' ORDER BY created_at DESC",
                job_id
            )
        
        def _parse_artifact(a):
            """Ensure proposed_data and original_data are dicts, not JSON strings."""
            d = dict(a)
            for field in ('proposed_data', 'original_data'):
                val = d.get(field)
                if isinstance(val, str):
                    try:
                        d[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            return d

        return {
            "job": dict(job),
            "clarifications": [dict(c) for c in clarifications],
            "steps": [dict(s) for s in steps],
            "artifacts": [_parse_artifact(a) for a in artifacts]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}"
        )


# ============ Token Budget Endpoints ============

class UpdateTokenBudgetRequest(BaseModel):
    new_budget: int


@router.get("/{job_id}/token-usage")
async def get_token_usage(job_id: str):
    """Get token usage details for a job."""
    job_id = _validate_job_id(job_id)
    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT token_budget, tokens_used, token_limit_exceeded_at FROM jobs WHERE id = $1",
            job_id,
        )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        steps = await conn.fetch(
            "SELECT step_name, tokens_used, token_limit_per_step FROM job_steps WHERE job_id = $1 ORDER BY created_at",
            job_id,
        )

    budget = job["token_budget"] or 50000
    used = job["tokens_used"] or 0
    return {
        "job_id": job_id,
        "budget": budget,
        "used": used,
        "percentage": (used / budget * 100) if budget > 0 else 0,
        "exceeded": job["token_limit_exceeded_at"] is not None,
        "steps": [dict(s) for s in steps],
    }


@router.patch("/{job_id}/token-budget")
async def update_token_budget(job_id: str, req: UpdateTokenBudgetRequest):
    """Update token budget for a job (admin)."""
    job_id = _validate_job_id(job_id)
    if req.new_budget < 10000 or req.new_budget > 200000:
        raise HTTPException(status_code=400, detail="Budget must be between 10k and 200k tokens")

    pool = _db._pool
    if not pool:
        raise HTTPException(status_code=503, detail="DB pool not initialised")

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET token_budget = $1 WHERE id = $2",
            req.new_budget, job_id,
        )

    return {"job_id": job_id, "new_budget": req.new_budget}

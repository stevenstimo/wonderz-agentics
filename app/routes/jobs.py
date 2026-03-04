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
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import ValidationError

from app.database import get_db
from app.orchestration.manager import OperationsManager
from app.services.deployment import DeploymentService
from models.unified import JobStatus
from tools.unified_bridge import UnifiedToolBridge
from app.services.job_pipeline import (
    run_intake_inline,
    run_intake_answers_inline,
    run_job_inline,
)
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

@router.post("", response_model=CreateJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(req: CreateJobRequest, background_tasks: BackgroundTasks):
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
    
    job_id = str(uuid.uuid4())
    source_platform = req.source_platform or "custom"
    try:
        uuid.UUID(str(req.user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format (must be UUID)"
        )
    context = {
        "job_post": req.job_post,
        "source_platform": source_platform,
    }
    
    try:
        logger.info(f"Creating job {job_id} for user {req.user_id}")
        
        async with pool.acquire() as conn:
            # Create job record
            await conn.execute(
                """
                INSERT INTO jobs (id, user_id, job_post, status, source_platform, context, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, now(), now())
                """,
                job_id,
                str(req.user_id),
                req.job_post,
                JobStatus.INTAKE_CLARIFICATION.value,
                source_platform,
                json.dumps(context),
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
        background_tasks.add_task(run_intake_inline, job_id, req.job_post)
        logger.info(f"Intake task queued for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to queue intake task for job {job_id}: {e}", exc_info=True)
        # Don't fail the request if task queueing fails initially
    
    return CreateJobResponse(
        job_id=job_id,
        status=JobStatus.INTAKE_CLARIFICATION.value,
        message="Job created. Intake analysis queued."
    )


@router.patch("/{job_id}/answer")
async def submit_intake_answer(
    job_id: str,
    req: SubmitAnswersRequest,
    background_tasks: BackgroundTasks
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
        background_tasks.add_task(run_intake_answers_inline, job_id, req.answers)
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
    background_tasks: BackgroundTasks,
    manager: OperationsManager = Depends(get_operations_manager)
):
    """
    User approves the proposed execution plan.
    
    Sets status to RUNNING and kicks off the workflow.
    """
    job_id = _validate_job_id(job_id)
    pool = await get_db()
    
    async with pool.acquire() as conn:
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
        
        # Queue job execution
        context = json.loads(job['context']) if isinstance(job['context'], str) else job['context']
        background_tasks.add_task(run_job_inline, job_id, context)
        logger.info(f"Job execution task queued for job {job_id}")

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
    req: FeedbackRequest,
    background_tasks: BackgroundTasks
):
    """
    User submits feedback on completed workflow results.
    
    Job must be in JOB_READY or AWAITING_APPROVAL state.
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
        background_tasks.add_task(run_job_inline, job_id, {"feedback": req.feedback})
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
    pool = await get_db()
    
    try:
        async with pool.acquire() as conn:
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


@router.get("")
async def list_jobs(status: Optional[str] = None, limit: int = 50):
    """List all jobs, optionally filtered by status."""
    pool = await get_db()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT id, user_id, job_post, status, source_platform, created_at, updated_at, tokens_used, token_budget FROM jobs WHERE status=$1 ORDER BY created_at DESC LIMIT $2",
                status, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT id, user_id, job_post, status, source_platform, created_at, updated_at, tokens_used, token_budget FROM jobs ORDER BY created_at DESC LIMIT $1",
                limit
            )
    return [dict(r) for r in rows]


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
            
            # Fetch artifacts
            artifacts = await conn.fetch(
                "SELECT * FROM artifacts WHERE job_id=$1 AND artifact_type != 'context' ORDER BY created_at DESC",
                job_id
            )
        
        return {
            "job": dict(job),
            "clarifications": [dict(c) for c in clarifications],
            "steps": [dict(s) for s in steps],
            "artifacts": [dict(a) for a in artifacts]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}"
        )

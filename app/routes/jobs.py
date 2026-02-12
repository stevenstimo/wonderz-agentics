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

import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.db import _pool
from app.orchestration.manager import OperationsManager
from models.unified import JobStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ============ Request/Response Models ============

class CreateJobRequest(BaseModel):
    user_id: str
    job_post: str
    source_platform: Optional[str] = None


class AnswerIntakeRequest(BaseModel):
    answers: Dict[str, str]


class FeedbackRequest(BaseModel):
    feedback: str


class RequestChangesRequest(BaseModel):
    feedback: str


# ============ Dependency: Get OperationsManager ============

def get_operations_manager():
    """Return configured OperationsManager instance."""
    # The agent_runner callback would be configured here
    # For now, a simple placeholder
    def dummy_runner(agent_name: str, input_data: dict) -> dict:
        return {"status": "success", "summary": f"Ran {agent_name}"}
    
    return OperationsManager(agent_runner=dummy_runner)


async def _next_step_index(conn, job_id: str) -> int:
    row = await conn.fetchrow(
        "SELECT COALESCE(MAX(step_index), 0) AS max_index FROM job_steps WHERE job_id=$1",
        job_id
    )
    return (row.get("max_index") or 0) + 1


# ============ Routes ============

@router.post("")
async def create_job(req: CreateJobRequest, manager: OperationsManager = Depends(get_operations_manager)):
    """
    Create a new job and start the intake flow.
    
    The CEO Agent will analyze the job post and either:
    - Ask clarifying questions (status: INTAKE_CLARIFICATION)
    - Propose a plan (status: PLAN_PROPOSED)
    """
    if not _pool:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    
    job_id = str(uuid.uuid4())
    
    try:
        async with _pool.acquire() as conn:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")
    
    # Start intake flow (this is intentionally async and non-blocking for now)
    # In production, you'd queue this to a background task
    try:
        await manager.start_intake_flow(job_id, req.job_post)
    except Exception as e:
        # Log error but don't fail the request
        print(f"Intake flow error for {job_id}: {e}")
    
    return {
        "job_id": job_id,
        "status": JobStatus.INTAKE_CLARIFICATION.value
    }


@router.patch("/{job_id}/answer")
async def submit_intake_answer(
    job_id: str,
    req: AnswerIntakeRequest,
    manager: OperationsManager = Depends(get_operations_manager)
):
    """
    User submits answers to clarification questions.
    
    The CEO will re-analyze and either:
    - Ask more questions
    - Propose a plan
    """
    if not _pool:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    
    # Verify job exists
    async with _pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Store clarification answers
        async with _pool.acquire() as conn:
            for q_id, answer in req.answers.items():
                await conn.execute(
                    """
                    UPDATE clarifications
                    SET user_answer = $1, answered_at = now()
                    WHERE question_id = $2 AND job_id = $3
                    """,
                    answer, q_id, job_id
                )
        
        # Handle the answers and potentially move to next stage
        await manager.handle_user_answer(job_id, req.answers)
        
        # Fetch updated job status
        async with _pool.acquire() as conn:
            updated_job = await conn.fetchrow("SELECT status FROM jobs WHERE id=$1", job_id)
        
        return {
            "job_id": job_id,
            "status": updated_job['status']
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process answers: {e}")


@router.post("/{job_id}/approve-plan")
async def approve_plan(
    job_id: str,
    manager: OperationsManager = Depends(get_operations_manager)
):
    """
    User approves the proposed execution plan.
    
    Sets status to RUNNING and kicks off the workflow.
    """
    if not _pool:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    
    async with _pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, status, context FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job['status'] != JobStatus.PLAN_PROPOSED.value:
            raise HTTPException(status_code=400, detail="Job is not in PLAN_PROPOSED state")
    
    try:
        # Approve the plan (transitions to RUNNING)
        await manager.approve_plan(job_id)
        
        # Queue the actual job execution to Celery (placeholder)
        # In production: celery_task.delay(job_id, job.context)
        
        return {
            "job_id": job_id,
            "status": JobStatus.RUNNING.value,
            "message": "Plan approved. Workflow execution started."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve plan: {e}")


@router.post("/{job_id}/request-changes")
async def request_plan_changes(
    job_id: str,
    req: RequestChangesRequest
):
    """
    User requests changes to the proposed plan.
    
    Feedback is stored and the job goes back to INTAKE_CLARIFICATION.
    """
    if not _pool:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    
    async with _pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Store feedback
        step_index = await _next_step_index(conn, job_id)
        await conn.execute(
            """
            INSERT INTO job_steps (
                job_id,
                step_index,
                step_name,
                agent_role,
                status,
                output,
                created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, now())
            """,
            job_id,
            step_index,
            "plan_feedback",
            "user",
            "recorded",
            json.dumps({"feedback": req.feedback})
        )
        
        # Transition back to INTAKE_CLARIFICATION for refinement
        await conn.execute(
            "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
            JobStatus.INTAKE_CLARIFICATION.value,
            job_id
        )
    
    return {
        "job_id": job_id,
        "status": JobStatus.INTAKE_CLARIFICATION.value,
        "message": "Feedback recorded. Plan will be refined."
    }


@router.post("/{job_id}/feedback")
async def submit_job_feedback(
    job_id: str,
    req: FeedbackRequest,
    manager: OperationsManager = Depends(get_operations_manager)
):
    """
    User submits feedback on the completed job (JOB_READY state).
    
    The CEO determines which agents need to retry based on the feedback.
    """
    if not _pool:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    
    async with _pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, status FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job['status'] != JobStatus.JOB_READY.value:
            raise HTTPException(status_code=400, detail="Job is not ready for feedback")
    
    try:
        # Handle feedback (determines retry logic)
        await manager.handle_job_feedback(job_id, req.feedback)
        
        # Transition back to RUNNING for retry
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.RUNNING.value,
                job_id
            )
        
        return {
            "job_id": job_id,
            "status": JobStatus.RUNNING.value,
            "message": "Feedback received. Retrying affected agents."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to handle feedback: {e}")


@router.post("/{job_id}/approve")
async def approve_and_deploy(job_id: str):
    """
    User gives final approval on the review.
    
    Triggers deployment and marks job as COMPLETED.
    """
    if not _pool:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    
    async with _pool.acquire() as conn:
        job = await conn.fetchrow("SELECT id, status, context FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job['status'] != JobStatus.JOB_READY.value:
            raise HTTPException(status_code=400, detail="Job is not ready for approval")
        
        try:
            # Update status to COMPLETED
            await conn.execute(
                "UPDATE jobs SET status=$1, updated_at=now() WHERE id=$2",
                JobStatus.COMPLETED.value,
                job_id
            )
            
            # In production: queue deployment task to Celery
            # deployment_task.delay(job_id, job.context['artifacts'])
            
            return {
                "job_id": job_id,
                "status": JobStatus.COMPLETED.value,
                "message": "Job approved and deployed successfully!"
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to approve and deploy: {e}")


@router.get("/{job_id}")
async def get_job(job_id: str):
    """
    Get complete job details including current status, context, and history.
    """
    if not _pool:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    
    async with _pool.acquire() as conn:
        # Get job
        job = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get job steps
        steps = await conn.fetch("SELECT * FROM job_steps WHERE job_id=$1 ORDER BY step_index", job_id)
        
        # Get clarifications
        clarifications = await conn.fetch("SELECT * FROM clarifications WHERE job_id=$1", job_id)
        
        # Get artifacts
        artifacts = await conn.fetch("SELECT * FROM artifacts WHERE job_id=$1", job_id)
    
    return {
        "job": dict(job),
        "steps": [dict(s) for s in steps],
        "clarifications": [dict(c) for c in clarifications],
        "artifacts": [dict(a) for a in artifacts]
    }

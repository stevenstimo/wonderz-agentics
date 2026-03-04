import os
import sys
import asyncio
import json
import logging
from datetime import datetime

# Ensure repo root on path so we can import app package
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from workers.celery_app import celery
from app.orchestration.manager import OperationsManager
from app.db import init_db_pool

logger = logging.getLogger(__name__)

async def _log_failed_step(
    job_id: str,
    step_name: str,
    agent_role: str,
    input_payload: dict,
    error: Exception,
    retries: int,
):
    pool = await init_db_pool()
    if not pool:
        logger.warning("DB pool not initialised - skipping failure log for job %s", job_id)
        return

    async with pool.acquire() as conn:
        max_index = await conn.fetchval(
            "SELECT COALESCE(MAX(step_index), 0) FROM job_steps WHERE job_id = $1",
            job_id,
        )
        step_index = (max_index or 0) + 1
        await conn.execute(
            """
            INSERT INTO job_steps (
                job_id,
                step_index,
                agent_role,
                step_name,
                status,
                input_payload,
                output,
                token_limit_per_step,
                tokens_used,
                created_at,
                started_at,
                completed_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now(),now(),now())
            """,
            job_id,
            step_index,
            agent_role,
            step_name,
            "failed",
            input_payload or {},
            {
                "error": str(error),
                "exception_type": type(error).__name__,
                "retries": retries,
            },
            0,
            0,
        )


def _log_failed_step_sync(
    job_id: str,
    step_name: str,
    agent_role: str,
    input_payload: dict,
    error: Exception,
    retries: int,
):
    try:
        asyncio.run(
            _log_failed_step(
                job_id=job_id,
                step_name=step_name,
                agent_role=agent_role,
                input_payload=input_payload,
                error=error,
                retries=retries,
            )
        )
    except RuntimeError as exc:
        logger.warning("Failed to log job step for %s: %s", job_id, exc)

def _build_agent_runner(job_id: str, store_id: str = None):
    async def real_agent_runner(agent_name: str, input_payload: dict):
        try:
            mod = __import__(f"agents.{agent_name}", fromlist=["run"])  # e.g. agents.copy_agent
            run_fn = getattr(mod, "run")

            # Build ToolsProxy according to permissions
            try:
                from agents.agent_permissions import AGENT_ALLOWED_TOOLS
                allowed = AGENT_ALLOWED_TOOLS.get(agent_name, [])
            except Exception:
                allowed = []

            from agents.tools_proxy import ToolsProxy
            tools = ToolsProxy(allowed)

            payload_with_tools = {
                "job_id": job_id,
                "store_id": store_id,
                "context": input_payload.get("context", {}),
                "tools": tools,
                **(input_payload or {})
            }

            if asyncio.iscoroutinefunction(run_fn):
                return await run_fn(payload_with_tools)
            else:
                return run_fn(payload_with_tools)
        except ModuleNotFoundError:
            logger.error(f"Agent module not found: {agent_name}")
            return {"summary": f"agent module not found: {agent_name}"}

    return real_agent_runner


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=540,  # 9 minutes
    time_limit=600,  # 10 minutes hard timeout
)
def run_intake(self, job_id: str, job_post: str):
    """
    Celery task to run the intake analysis.
    
    Retries:
    - Attempt 1 immediate
    - Attempt 2 after 60 seconds
    - Attempt 3 after 120 seconds (2 ^ 1 * 60)
    - Attempt 4 after 240 seconds (2 ^ 2 * 60)
    Then dead-letter queue
    """
    manager = OperationsManager(agent_runner=_build_agent_runner(job_id))
    try:
        logger.info(f"Starting intake analysis for job {job_id}")
        asyncio.run(manager.start_intake_flow(job_id, job_post))
        logger.info(f"Completed intake analysis for job {job_id}")
        
    except asyncio.TimeoutError as e:
        logger.warning(f"Timeout during intake for job {job_id} (attempt {self.request.retries + 1}): {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
    except Exception as e:
        logger.error(f"Error running intake for job {job_id} (attempt {self.request.retries + 1}): {e}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            # Exponential backoff: 60s, 120s, 240s
            retry_countdown = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying intake for job {job_id} in {retry_countdown}s")
            raise self.retry(exc=e, countdown=retry_countdown)
        else:
            logger.critical(f"Max retries exceeded for intake job {job_id}. Moving to dead-letter.")
            _log_failed_step_sync(
                job_id=job_id,
                step_name="intake",
                agent_role="orchestrator",
                input_payload={"job_post": job_post},
                error=e,
                retries=self.request.retries + 1,
            )
            raise


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=540,
    time_limit=600,
)
def run_intake_answers(self, job_id: str, answers: dict):
    """
    Celery task to process intake answers and re-analyze.
    
    Retries with exponential backoff on failure.
    """
    manager = OperationsManager(agent_runner=_build_agent_runner(job_id))
    try:
        logger.info(f"Processing intake answers for job {job_id}")
        asyncio.run(manager.handle_user_answer(job_id, answers))
        logger.info(f"Completed intake answers for job {job_id}")
        
    except asyncio.TimeoutError as e:
        logger.warning(f"Timeout during intake answers for job {job_id} (attempt {self.request.retries + 1}): {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
    except Exception as e:
        logger.error(f"Error processing intake answers for job {job_id} (attempt {self.request.retries + 1}): {e}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            retry_countdown = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying intake answers for job {job_id} in {retry_countdown}s")
            raise self.retry(exc=e, countdown=retry_countdown)
        else:
            logger.critical(f"Max retries exceeded for intake answers job {job_id}")
            raise


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,  # Longer default for job execution
    soft_time_limit=540,
    time_limit=600,
)
def run_job(self, job_id: str, store_id: str = None, payload: dict = None):
    """
    Celery task entrypoint to run a workflow for a job id.
    
    Longer retry delays for job execution (120s, 240s, 480s)
    Includes timeout handling and comprehensive logging.
    """
    payload = payload or {}
    manager = OperationsManager(agent_runner=_build_agent_runner(job_id, store_id))

    try:
        logger.info(f"Starting job execution for job {job_id} (attempt {self.request.retries + 1})")
        asyncio.run(manager.run_workflow(job_id, store_id, payload))
        logger.info(f"Completed job execution for job {job_id}")
        
    except asyncio.TimeoutError as e:
        logger.warning(f"Timeout during job execution for {job_id} (attempt {self.request.retries + 1}): {e}")
        # Longer retry delay for job execution
        raise self.retry(exc=e, countdown=120 * (2 ** self.request.retries))
        
    except Exception as e:
        logger.error(f"Error running job {job_id} (attempt {self.request.retries + 1}): {e}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            retry_countdown = 120 * (2 ** self.request.retries)
            logger.info(f"Retrying job {job_id} in {retry_countdown}s")
            raise self.retry(exc=e, countdown=retry_countdown)
        else:
            logger.critical(f"Max retries exceeded for job {job_id}")
            _log_failed_step_sync(
                job_id=job_id,
                step_name="job",
                agent_role="orchestrator",
                input_payload={"store_id": store_id, "payload": payload},
                error=e,
                retries=self.request.retries + 1,
            )
            raise

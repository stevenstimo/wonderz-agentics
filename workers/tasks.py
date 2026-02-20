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
from app.services.hr_manager import HRManager

logger = logging.getLogger(__name__)

# --- Circuit Breaker ---
try:
    import redis as _redis_lib
    from app.services.circuit_breaker import CircuitBreaker
    _redis_client = _redis_lib.Redis(host='localhost', port=6379, db=0, socket_timeout=2)
    circuit_breaker = CircuitBreaker(_redis_client, failure_threshold=5, ttl_seconds=600)
except Exception as _cb_err:
    logger.warning("Circuit breaker not available: %s", _cb_err)
    circuit_breaker = None

# Map agent_role -> Python module name
ROLE_TO_MODULE = {
    "copywriter": "copy_agent",
    "reviewer": "reviewer_agent",
    "seo": "seo_agent",
    "developer": "developer_agent",
    "paid_ads_manager": "ads_agent",
    "data_analyst": "data_agent",
}
MODULE_TO_ROLE = {module: role for role, module in ROLE_TO_MODULE.items()}


def _build_agent_runner(job_id: str, store_id: str = None):
    async def real_agent_runner(agent_name: str, input_payload: dict):
        """Run an agent by name.

        Supports two naming conventions:
        - Legacy: 'copy_agent', 'reviewer_agent' (direct module names)
        - Dynamic: role-based names via the determine_next_step graph

        When the plan includes an agent_id (from hired_agents), we look up the
        agent config from the DB and inject it into the payload.
        """
        try:
            # Determine module name: try direct import first, then role mapping
            module_name = agent_name  # e.g. "copy_agent"
            try:
                mod = __import__(f"agents.{module_name}", fromlist=["run"])
            except ModuleNotFoundError:
                # Try role-based mapping
                mapped = ROLE_TO_MODULE.get(agent_name)
                if mapped:
                    mod = __import__(f"agents.{mapped}", fromlist=["run"])
                    module_name = mapped
                else:
                    raise

            run_fn = getattr(mod, "run")

            # Build ToolsProxy according to permissions
            try:
                from agents.agent_permissions import AGENT_ALLOWED_TOOLS
                allowed = AGENT_ALLOWED_TOOLS.get(module_name, [])
            except Exception:
                allowed = []

            from agents.tools_proxy import ToolsProxy
            tools = ToolsProxy(allowed)

            # Try to load agent config from hired_agents table
            agent_config = None
            try:
                import app.db as _db
                pool = _db._pool
                if pool:
                    async with pool.acquire() as conn:
                        # Try exact agent_id match first
                        agent_config = await conn.fetchrow(
                            "SELECT * FROM hired_agents WHERE agent_id = $1 AND status = 'active'",
                            f"agent:{agent_name}"
                        )
                        if not agent_config:
                            # Try by role (module mapping preferred for copy_agent -> copywriter)
                            role = MODULE_TO_ROLE.get(module_name) or MODULE_TO_ROLE.get(agent_name) or agent_name.replace("_agent", "")
                            agent_config = await conn.fetchrow(
                                "SELECT * FROM hired_agents WHERE role = $1 AND status = 'active' ORDER BY performance_score DESC LIMIT 1",
                                role
                            )
                    if agent_config:
                        agent_config = dict(agent_config)
            except Exception as e:
                logger.debug(f"Could not load agent config for {agent_name}: {e}")

            payload_with_tools = {
                "job_id": job_id,
                "store_id": store_id,
                "context": input_payload.get("context", {}),
                "tools": tools,
                "agent_config": agent_config,
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
    Circuit breaker + exponential backoff retries.
    """
    # Circuit breaker check
    if circuit_breaker and circuit_breaker.is_open():
        logger.error("Circuit breaker OPEN — rejecting intake for job %s", job_id)
        raise self.retry(exc=RuntimeError("Circuit breaker open"), countdown=120)

    manager = OperationsManager(agent_runner=_build_agent_runner(job_id))
    try:
        logger.info("Starting intake analysis for job %s", job_id)
        asyncio.run(manager.start_intake_flow(job_id, job_post))
        logger.info("Completed intake analysis for job %s", job_id)
        if circuit_breaker:
            circuit_breaker.record_success()

    except asyncio.TimeoutError as e:
        if circuit_breaker:
            circuit_breaker.record_failure()
        logger.warning("Timeout during intake for job %s (attempt %d): %s", job_id, self.request.retries + 1, e)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except Exception as e:
        if circuit_breaker:
            circuit_breaker.record_failure()
        logger.error("Error running intake for job %s (attempt %d): %s", job_id, self.request.retries + 1, e, exc_info=True)

        if self.request.retries < self.max_retries:
            retry_countdown = 60 * (2 ** self.request.retries)
            logger.info("Retrying intake for job %s in %ds", job_id, retry_countdown)
            raise self.retry(exc=e, countdown=retry_countdown)
        else:
            logger.critical("Max retries exceeded for intake job %s", job_id)
            raise


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=540,
    time_limit=600,
)
def run_intake_answers(self, job_id: str, answers: dict):
    """Celery task to process intake answers. Circuit breaker + retries."""
    if circuit_breaker and circuit_breaker.is_open():
        logger.error("Circuit breaker OPEN — rejecting intake answers for job %s", job_id)
        raise self.retry(exc=RuntimeError("Circuit breaker open"), countdown=120)

    manager = OperationsManager(agent_runner=_build_agent_runner(job_id))
    try:
        logger.info("Processing intake answers for job %s", job_id)
        asyncio.run(manager.handle_user_answer(job_id, answers))
        logger.info("Completed intake answers for job %s", job_id)
        if circuit_breaker:
            circuit_breaker.record_success()

    except asyncio.TimeoutError as e:
        if circuit_breaker:
            circuit_breaker.record_failure()
        logger.warning("Timeout during intake answers for job %s: %s", job_id, e)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except Exception as e:
        if circuit_breaker:
            circuit_breaker.record_failure()
        logger.error("Error processing intake answers for job %s: %s", job_id, e, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        else:
            logger.critical("Max retries exceeded for intake answers job %s", job_id)
            raise


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=540,
    time_limit=600,
)
def run_scheduled_jobs(self):
    """
    Background task: Execute due scheduled jobs.

    Runs every minute.
    """
    if circuit_breaker and circuit_breaker.is_open():
        logger.error("Circuit breaker OPEN — rejecting scheduled jobs run")
        raise self.retry(exc=RuntimeError("Circuit breaker open"), countdown=120)

    async def run():
        from app.db import init_db_pool
        from app.services.scheduler import JobScheduler

        pool = await init_db_pool()
        if not pool:
            logger.error("Scheduler failed: no database pool")
            return

        async def _enqueue_intake(job_id: str, job_post: str) -> None:
            try:
                run_intake.delay(job_id, job_post)
            except Exception as exc:
                logger.warning("Celery unavailable for intake of %s: %s", job_id, exc)
                mgr = OperationsManager(agent_runner=_build_agent_runner(job_id))
                await mgr.start_intake_flow(job_id, job_post)

        scheduler = JobScheduler(pool, enqueue_intake=_enqueue_intake)
        await scheduler.check_and_run_due_jobs()

    try:
        asyncio.run(run())
        if circuit_breaker:
            circuit_breaker.record_success()
    except Exception as exc:
        if circuit_breaker:
            circuit_breaker.record_failure()
        logger.error("Error running scheduled jobs: %s", exc, exc_info=True)
        raise


@celery.task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,  # Longer default for job execution
    soft_time_limit=540,
    time_limit=600,
)
def run_job(self, job_id: str, store_id: str = None, payload: dict = None):
    """Celery task to run full workflow. Circuit breaker + retries."""
    if circuit_breaker and circuit_breaker.is_open():
        logger.error("Circuit breaker OPEN — rejecting job %s", job_id)
        raise self.retry(exc=RuntimeError("Circuit breaker open"), countdown=120)

    payload = payload or {}
    manager = OperationsManager(agent_runner=_build_agent_runner(job_id, store_id))

    try:
        logger.info("Starting job execution for job %s (attempt %d)", job_id, self.request.retries + 1)
        asyncio.run(manager.run_workflow(job_id, store_id, payload))
        logger.info("Completed job execution for job %s", job_id)
        if circuit_breaker:
            circuit_breaker.record_success()

    except asyncio.TimeoutError as e:
        if circuit_breaker:
            circuit_breaker.record_failure()
        logger.warning("Timeout during job execution for %s: %s", job_id, e)
        raise self.retry(exc=e, countdown=120 * (2 ** self.request.retries))

    except Exception as e:
        if circuit_breaker:
            circuit_breaker.record_failure()
        logger.error("Error running job %s (attempt %d): %s", job_id, self.request.retries + 1, e, exc_info=True)

        if self.request.retries < self.max_retries:
            retry_countdown = 120 * (2 ** self.request.retries)
            logger.info("Retrying job %s in %ds", job_id, retry_countdown)
            raise self.retry(exc=e, countdown=retry_countdown)
        else:
            logger.critical("Max retries exceeded for job %s", job_id)
            raise


@celery.task
def run_hr_scan():
    """Background task: scan for retry patterns and create development points."""
    import asyncio
    from app.db import init_db_pool

    async def scan():
        pool = await init_db_pool()
        if not pool:
            logger.error("HR scan failed: no database pool")
            return
        hr = HRManager(pool)
        result = await hr.process_retry_patterns()
        logger.info("HR scan complete: %s", result)

    asyncio.run(scan())


@celery.task
def check_system_alerts():
    """
    Background task: Check alert conditions.

    Runs every 5 minutes.
    """
    import asyncio
    from app.db import init_db_pool
    from app.services.alerting import AlertManager

    async def check():
        pool = await init_db_pool()
        if not pool:
            logger.error("Alert check failed: no database pool")
            return

        alert_mgr = AlertManager(pool)
        alerts = await alert_mgr.check_and_alert()

        if alerts:
            logger.info("Sent %s alerts", len(alerts))

    asyncio.run(check())

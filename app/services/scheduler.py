"""Job scheduling system."""
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime
import json
import logging
from croniter import croniter

from models.unified import JobStatus
from app.services.template_manager import TemplateManager

logger = logging.getLogger(__name__)


class JobScheduler:
    """Manages scheduled/recurring jobs."""

    def __init__(self, pool, enqueue_intake: Optional[Callable[[str, str], None]] = None):
        self.pool = pool
        self.enqueue_intake = enqueue_intake

    async def create_schedule(
        self,
        user_id: str,
        template_id: str,
        job_config: Dict[str, Any],
        cron_expression: str,
        timezone: str = "UTC",
    ) -> str:
        """Create new job schedule."""
        try:
            cron = croniter(cron_expression, datetime.utcnow())
            next_run = cron.get_next(datetime)
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {e}")

        schedule_id = f"schedule:{user_id}:{int(datetime.utcnow().timestamp())}"

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO job_schedules (
                    schedule_id, user_id, template_id, job_config,
                    cron_expression, timezone, next_run_at
                ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                """,
                schedule_id,
                user_id,
                template_id,
                json.dumps(job_config),
                cron_expression,
                timezone,
                next_run,
            )

        logger.info("Created schedule %s, next run: %s", schedule_id, next_run)
        return schedule_id

    async def check_and_run_due_jobs(self) -> List[str]:
        """
        Check for jobs that need to run and execute them.

        Called by background task every minute.
        """
        async with self.pool.acquire() as conn:
            due_schedules = await conn.fetch(
                """
                SELECT * FROM job_schedules
                WHERE is_active = true
                  AND next_run_at <= NOW()
                ORDER BY next_run_at
                """
            )

        created_jobs: List[str] = []
        for schedule in due_schedules:
            try:
                job_id, job_post = await self._execute_scheduled_job(schedule)
                if job_id:
                    created_jobs.append(job_id)
                    if self.enqueue_intake:
                        await _maybe_await(self.enqueue_intake(job_id, job_post))
            except Exception as e:
                logger.error("Failed to execute schedule %s: %s", schedule["schedule_id"], e)

        return created_jobs

    async def _execute_scheduled_job(self, schedule: Dict[str, Any]) -> Tuple[str, str]:
        """Execute single scheduled job."""
        manager = TemplateManager(self.pool)
        variables = {
            key: str(value)
            for key, value in (schedule.get("job_config") or {}).items()
        }
        job_data = await manager.instantiate_template(
            schedule["template_id"],
            variables,
        )

        job_post = job_data["job_post"]
        job_id = f"scheduled-{schedule['schedule_id']}-{int(datetime.utcnow().timestamp())}"

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (
                    id, user_id, job_post, status,
                    source_platform, context, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6::jsonb, NOW(), NOW()
                )
                """,
                job_id,
                schedule["user_id"],
                job_post,
                JobStatus.INTAKE_CLARIFICATION.value,
                schedule.get("platform") or "custom",
                json.dumps({
                    "scheduled": True,
                    "schedule_id": schedule["schedule_id"],
                    "template_id": schedule["template_id"],
                }),
            )

        cron = croniter(schedule["cron_expression"], datetime.utcnow())
        next_run = cron.get_next(datetime)

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE job_schedules
                SET last_run_at = NOW(),
                    next_run_at = $1,
                    run_count = run_count + 1
                WHERE schedule_id = $2
                """,
                next_run,
                schedule["schedule_id"],
            )

        logger.info("Executed schedule %s, created job %s", schedule["schedule_id"], job_id)
        return job_id, job_post


async def _maybe_await(value):
    if value is None:
        return None
    if hasattr(value, "__await__"):
        return await value
    return value

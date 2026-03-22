"""Record a lesson from a completed job for the eval pipeline."""

import logging
import uuid

logger = logging.getLogger(__name__)


async def record_lesson_from_completed_job(pool, job_id: str) -> None:
    """Create a lesson entry linked to a completed job via source_job_id."""
    jid = uuid.UUID(job_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, job_type, job_post, status FROM jobs WHERE id = $1", jid
        )
        if not row or row["status"] not in ("COMPLETED", "JOB_READY"):
            logger.debug(f"lesson_from_completed_job: skip job {job_id} (status={row and row['status']})")
            return

        # Check if lesson already exists for this job
        existing = await conn.fetchval(
            "SELECT 1 FROM lessons WHERE source_job_id = $1", jid
        )
        if existing:
            return

        lesson_id = str(uuid.uuid4())
        job_type = row["job_type"] or "unknown"
        description = (row["job_post"] or "")[:200]

        await conn.execute(
            """
            INSERT INTO lessons (lesson_id, title, gevonden, oorzaak, fix, impact, source_job_id, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'active')
            """,
            lesson_id,
            f"Job {job_type} voltooid",
            f"Job {job_id} ({job_type}) is succesvol afgerond: {description}",
            "Pipeline executie succesvol",
            "Geen fix nodig — documentatie van succesvolle uitvoering",
            "low",
            jid,
        )
        logger.info(f"Lesson {lesson_id} created for completed job {job_id}")

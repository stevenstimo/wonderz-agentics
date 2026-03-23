"""Record a lesson from a completed job for the eval pipeline."""

import logging
import uuid

logger = logging.getLogger(__name__)


async def record_lesson_from_completed_job(pool, job_id: str) -> None:
    """Create a lesson entry linked to a completed job via source_job_id or task_id."""
    jid_str = str(job_id).strip()
    try:
        jid_uuid = uuid.UUID(jid_str)
    except ValueError:
        logger.debug("lesson_from_completed_job: invalid job_id %s", job_id)
        return

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, job_type, job_post, status FROM jobs WHERE id = $1",
            jid_uuid,
        )
        if not row or row["status"] not in ("COMPLETED", "JOB_READY"):
            logger.debug(
                "lesson_from_completed_job: skip job %s (status=%s)",
                job_id,
                row and row["status"],
            )
            return

        has_source_job_id = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'lessons'
              AND column_name = 'source_job_id'
            """
        )
        has_task_id = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'lessons'
              AND column_name = 'task_id'
            """
        )

        if has_source_job_id:
            existing = await conn.fetchval(
                "SELECT 1 FROM lessons WHERE source_job_id::text = $1",
                jid_str,
            )
        elif has_task_id:
            existing = await conn.fetchval(
                "SELECT 1 FROM lessons WHERE task_id = $1",
                jid_str,
            )
        else:
            logger.warning(
                "lesson_from_completed_job: lessons has neither source_job_id nor task_id; skip job %s",
                job_id,
            )
            return

        if existing:
            return

        lesson_id = str(uuid.uuid4())
        job_type = row["job_type"] or "unknown"
        description = (row["job_post"] or "")[:200]

        if has_source_job_id:
            await conn.execute(
                """
                INSERT INTO lessons (
                    lesson_id, title, gevonden, oorzaak, fix, impact, source_job_id, status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'active')
                """,
                lesson_id,
                f"Job {job_type} voltooid",
                f"Job {job_id} ({job_type}) is succesvol afgerond: {description}",
                "Pipeline executie succesvol",
                "Geen fix nodig — documentatie van succesvolle uitvoering",
                "low",
                jid_str,
            )
        else:
            await conn.execute(
                """
                INSERT INTO lessons (
                    lesson_id, title, gevonden, oorzaak, fix, impact, task_id, status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'active')
                """,
                lesson_id,
                f"Job {job_type} voltooid",
                f"Job {job_id} ({job_type}) is succesvol afgerond: {description}",
                "Pipeline executie succesvol",
                "Geen fix nodig — documentatie van succesvolle uitvoering",
                "low",
                jid_str,
            )
        logger.info("Lesson %s created for completed job %s", lesson_id, job_id)

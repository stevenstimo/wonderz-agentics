"""
ARQ worker for Crew Intelligent.

This worker runs job execution outside the FastAPI web process, so backend
restarts (or closed browser sessions) do not stop in-flight work.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from arq.connections import RedisSettings
from arq.cron import cron

from app.db import close_db_pool, init_db_pool

logger = logging.getLogger(__name__)


async def _set_stuck_running_jobs_failed(ctx: dict[str, Any]) -> None:
    """
    Recovery: mark jobs stuck in RUNNING for too long as FAILED.

    Important: uses the *actual* jobs schema in this repo:
    - primary key column is `id` (not `job_id`)
    - we persist error details in `jobs.payload.error_reason`
    """

    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] No db_pool in ctx; skipping stuck job recovery.")
        return

    error_detail = "Stuck RUNNING job detected at worker startup; marking as FAILED."

    async with pool.acquire() as conn:
        stuck_jobs = await conn.fetch(
            """
            SELECT id, updated_at
            FROM jobs
            WHERE status = 'RUNNING'
              AND updated_at < now() - interval '60 minutes'
            """
        )

        if not stuck_jobs:
            logger.info("[ARQ] Startup recovery: geen stuck jobs gevonden.")
            return

        logger.warning("[ARQ] Recovery: %d stuck RUNNING job(s) gevonden", len(stuck_jobs))

        payload_update = {"error_reason": error_detail}
        payload_json = json.dumps(payload_update)

        for row in stuck_jobs:
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'FAILED',
                    updated_at = now(),
                    payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb
                WHERE id = $2
                """,
                payload_json,
                row["id"],
            )
            logger.warning(
                "[ARQ] Job %s gezet op FAILED (was stuck sinds %s)",
                row["id"],
                row["updated_at"],
            )


async def startup(ctx: dict[str, Any]) -> None:
    # Initialise the global asyncpg pool (app.db.init_db_pool caches it in module state).
    ctx["db_pool"] = await init_db_pool()
    await _set_stuck_running_jobs_failed(ctx)


async def shutdown(ctx: dict[str, Any]) -> None:
    await close_db_pool()


# -----------------------
# Job-flow tasks (jobs)
# -----------------------

async def run_intake_inline(ctx: dict[str, Any], job_id: str, job_post: str) -> None:
    from app.services.job_pipeline import run_intake_inline

    await run_intake_inline(job_id, job_post)


async def run_intake_answers_inline(
    ctx: dict[str, Any], job_id: str, answers: Optional[dict[str, str]] = None
) -> None:
    from app.services.job_pipeline import run_intake_answers_inline

    await run_intake_answers_inline(job_id, answers or {})


async def run_data_pipeline(ctx: dict[str, Any], job_id: str) -> None:
    from app.services.job_pipeline import run_data_pipeline

    await run_data_pipeline(job_id)


async def run_job_inline(
    ctx: dict[str, Any], job_id: str, context_extra: Optional[dict[str, Any]] = None
) -> None:
    from app.services.job_pipeline import run_job_inline

    await run_job_inline(job_id, context_extra)


async def run_job_pipeline(ctx: dict[str, Any], job_id: str) -> None:
    """
    Execute the NEXUSPipeline for a given job id.

    This is used to replace the `USE_NEXUS_PIPELINE` web-process path.
    """

    from app.orchestration.nexus_pipeline import NEXUSPipeline

    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] db_pool missing; NEXUS pipeline task skipping for job %s", job_id)
        return

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, job_post, source_platform, token_budget FROM jobs WHERE id=$1",
            job_id,
        )

    if not row:
        logger.warning("[ARQ] Job not found for NEXUS pipeline: %s", job_id)
        return

    user_id = str(row.get("user_id") or "")
    job_post = str(row.get("job_post") or "")
    platform = str(row.get("source_platform") or "browser")
    token_budget = int(row.get("token_budget") or 50000)

    pipeline = NEXUSPipeline()
    await pipeline.run(
        job_id=job_id,
        user_id=user_id,
        platform=platform,
        job_post=job_post,
        token_budget=token_budget,
        pool=pool,
    )


# -----------------------
# HR / training tasks
# -----------------------

async def start_agent_training(ctx: dict[str, Any], agent_id: str, url: str, approved_by: str) -> None:
    from app.services.training_workflow import TrainingWorkflow

    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] db_pool missing; training skip for agent %s", agent_id)
        return

    workflow = TrainingWorkflow(pool)
    await workflow.start_training(agent_id=agent_id, url=url, approved_by=approved_by)


async def insert_hr_suggestion_into_knowledge_library(
    ctx: dict[str, Any],
    source_url: str,
    title: str,
    rationale: str,
    approved_by: str,
) -> None:
    """ARQ job: training_suggestion -> knowledge_documents (approved) non-blocking ingest."""
    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] db_pool missing; knowledge ingest skip for %s", source_url)
        return

    # Reuse the route helper to keep SQL logic in one place.
    from app.routes.hr import _insert_suggestion_into_knowledge_library

    suggestion = {
        "url": source_url,
        "title": title,
        "rationale": rationale,
    }
    await _insert_suggestion_into_knowledge_library(pool=pool, suggestion=suggestion, approved_by=approved_by)


async def _run_training_background(ctx: dict[str, Any], agent_id: str, url: str, approved_by: str) -> None:
    # Uses the existing embedding training implementation from the agents routes module.
    from app.routes.agents import _run_training_background

    await _run_training_background(agent_id, url, approved_by)


# -----------------------
# Clients datasource tasks
# -----------------------

async def _process_datasource_background(
    ctx: dict[str, Any],
    client_id: str,
    datasource_id: int,
    source_type: str,
    domain: Optional[str],
    sitemap_url: Optional[str],
    raw_text: Optional[str],
    feed_url: Optional[str],
    feed_splitting_tag: Optional[str],
    feed_identifier_tag: Optional[str],
) -> None:
    from app.routes.clients import _process_datasource_background

    await _process_datasource_background(
        client_id=client_id,
        datasource_id=datasource_id,
        source_type=source_type,
        domain=domain,
        sitemap_url=sitemap_url,
        raw_text=raw_text,
        feed_url=feed_url,
        feed_splitting_tag=feed_splitting_tag,
        feed_identifier_tag=feed_identifier_tag,
    )


async def _run_file(
    ctx: dict[str, Any],
    client_id: str,
    datasource_id: int,
    tmp_path: str,
    ext: str,
    name: str,
) -> None:
    """
    Worker-side file ingestion for /clients/{slug}/datasources/{id}/upload.

    The web endpoint writes a temporary file path and enqueues this task.
    """

    import os

    from app.database import get_db
    from app.services.client_file_processor import ClientFileProcessor

    pool = await get_db()
    try:
        with open(tmp_path, "rb") as f:
            data = f.read()

        proc = ClientFileProcessor(client_id, datasource_id, pool)
        if ext.lower() == "pdf":
            await proc.process_pdf(data, name)
        else:
            await proc.process_csv(data, name)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# -----------------------
# Knowledge (embeddings)
# -----------------------

async def process_knowledge_ingest(
    ctx: dict[str, Any],
    document_id: str,
    tmp_path: str = "",
    original_filename: str = "",
) -> None:
    """
    Fire-and-forget: URL scrape + chunk + embed, or file extract + chunk + embed.
    tmp_path empty → URL ingest for document_id; else temp file (deleted here).
    """
    import os

    from app.services.knowledge_upload_service import (
        ingest_file_from_temp_then_embed,
        ingest_url_document_then_embed,
    )

    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] db_pool missing; knowledge_ingest skip for %s", document_id)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return

    logger.info("[ARQ] knowledge_ingest gestart: %s", document_id)
    try:
        if tmp_path:
            await ingest_file_from_temp_then_embed(
                pool, document_id, tmp_path, original_filename or "upload"
            )
        else:
            await ingest_url_document_then_embed(pool, document_id)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def process_knowledge_replace_content(
    ctx: dict[str, Any],
    document_id: str,
    tmp_path: str,
    original_filename: str,
) -> None:
    """Replace document body from uploaded file: extract, chunk, embed on worker."""
    import os

    from app.services.knowledge_upload_service import replace_document_content_from_text, run_embedding_task
    from app.services.training import TrainingError
    from app.utils.document_parser import extract_text_from_file

    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] db_pool missing; knowledge_replace skip for %s", document_id)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return

    logger.info("[ARQ] knowledge_replace gestart: %s", document_id)
    try:
        try:
            with open(tmp_path, "rb") as f:
                raw = f.read()
            text = extract_text_from_file(original_filename or "upload", raw)
        except ValueError as e:
            logger.warning("knowledge_replace extract failed %s: %s", document_id, e)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE knowledge_documents
                    SET embedding_status = 'failed', updated_at = now()
                    WHERE document_id = $1::uuid
                    """,
                    document_id,
                )
            return

        if not text or len(text.strip()) < 50:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE knowledge_documents
                    SET embedding_status = 'failed', updated_at = now()
                    WHERE document_id = $1::uuid
                    """,
                    document_id,
                )
            return

        try:
            await replace_document_content_from_text(pool, document_id, text)
        except TrainingError as e:
            logger.warning("knowledge_replace chunk failed %s: %s", document_id, e)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE knowledge_documents
                    SET embedding_status = 'failed', updated_at = now()
                    WHERE document_id = $1::uuid
                    """,
                    document_id,
                )
            return

        await run_embedding_task(pool, document_id)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def run_embedding_task(ctx: dict[str, Any], document_id: str) -> None:
    from app.services.knowledge_upload_service import run_embedding_task

    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] db_pool missing; embedding skip for document %s", document_id)
        return

    await run_embedding_task(pool, document_id)


async def reindex_document(ctx: dict[str, Any], document_id: str) -> None:
    from app.services.knowledge_upload_service import reindex_document

    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] db_pool missing; reindex skip for document %s", document_id)
        return

    await reindex_document(pool, document_id)


# -----------------------
# SEO (seo_upload)
# -----------------------

async def _process_seo_job(
    ctx: dict[str, Any],
    job_id: str,
    input_path: str,
    brand_name: str,
    domain: str,
    audience: str,
    language: str,
    user_id: Optional[str],
    client_slug: Optional[str],
) -> None:
    from app.routes.seo_upload import _process_seo_job

    await _process_seo_job(
        job_id=job_id,
        input_path=input_path,
        brand_name=brand_name,
        domain=domain,
        audience=audience,
        language=language,
        user_id=user_id,
        client_slug=client_slug,
    )


async def run_gsc_performance_check(ctx: dict[str, Any]) -> None:
    """
    Wekelijks: GSC ophalen voor jobs met published_url (≥7 dagen live, geen recente meting),
    daarna HR-scan voor lage performers.
    """
    pool = ctx.get("db_pool")
    if not pool:
        logger.warning("[ARQ] GSC performance check: geen db_pool")
        return

    async with pool.acquire() as conn:
        has_jobs = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'jobs' AND column_name = 'published_url'
            """
        )
        has_jp = await conn.fetchval(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'job_performance'
            """
        )
        if not has_jobs or not has_jp:
            logger.info("[ARQ] GSC performance check overgeslagen (migratie / tabellen ontbreken)")
            return

        jobs_to_check = await conn.fetch(
            """
            SELECT j.id FROM jobs j
            WHERE j.published_url IS NOT NULL
              AND trim(j.published_url) <> ''
              AND j.published_at IS NOT NULL
              AND j.published_at < now() - INTERVAL '7 days'
              AND (
                  NOT EXISTS (
                      SELECT 1 FROM job_performance jp
                      WHERE jp.job_id = j.id
                        AND jp.measured_at > now() - INTERVAL '7 days'
                  )
              )
            """
        )

    from app.services.gsc_performance import fetch_url_performance, scan_job_performance

    for row in jobs_to_check:
        jid = str(row["id"])
        try:
            result = await fetch_url_performance(pool, jid)
            if result.get("error"):
                logger.warning("[ARQ] GSC fetch job %s: %s", jid, result["error"])
        except Exception:
            logger.exception("[ARQ] GSC fetch job %s gefaald", jid)

    try:
        created = await scan_job_performance(pool)
        if created:
            logger.info("[ARQ] GSC HR-scan: punten voor jobs %s", created)
    except Exception:
        logger.exception("[ARQ] GSC HR-scan gefaald")


class WorkerSettings:
    """
    ARQ worker settings consumed by `python -m arq app.worker.WorkerSettings`.
    """

    functions = [
        run_intake_inline,
        run_intake_answers_inline,
        run_data_pipeline,
        run_job_inline,
        run_job_pipeline,
        start_agent_training,
        insert_hr_suggestion_into_knowledge_library,
        _run_training_background,
        _process_datasource_background,
        _run_file,
        process_knowledge_ingest,
        process_knowledge_replace_content,
        run_embedding_task,
        reindex_document,
        _process_seo_job,
    ]

    cron_jobs = [
        cron(
            run_gsc_performance_check,
            weekday={0},
            hour=6,
            minute=0,
            run_at_startup=False,
        ),
    ]

    on_startup = startup
    on_shutdown = shutdown

    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))
    max_jobs = 10
    job_timeout = 3600  # 60 minutes in seconds? (3600s = 60 minutes)
    keep_result = 86400
    retry_jobs = False
    health_check_interval = 60


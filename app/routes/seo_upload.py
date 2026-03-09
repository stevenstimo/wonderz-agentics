"""
SEO Keyword Plan — file upload, processing, status polling, download.
POST /api/seo/upload, GET /api/seo/status/{job_id}, GET /api/seo/download/{job_id}
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.db import init_db_pool
from app.utils.seo_excel_generator import generate_seo_excel
from app.utils.seo_parser import parse_keywords_file
from app.agents.seo_agent import run_seo_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["seo"])
MAX_KEYWORDS = 2000
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _next_job_id() -> str:
    """Generate SEO-YYYY-NNN style job IDs."""
    year = datetime.now().strftime("%Y")
    # ASSUMPTION: simple sequential for v1; use DB sequence in production
    return f"SEO-{year}-{uuid.uuid4().hex[:8].upper()}"


async def _process_seo_job(
    job_id: str,
    input_path: str,
    brand_name: str,
    domain: str,
    audience: str,
    language: str,
):
    """Background task: parse, run agent, generate Excel, update DB."""
    pool = await init_db_pool()
    if not pool:
        await _mark_failed(job_id, "Database unavailable")
        return

    try:
        with open(input_path, "rb") as f:
            content = f.read()
        keywords = parse_keywords_file(content, input_path)


        async def _progress(processed: int, total: int, current_silo: str):
            pct = int(100 * processed / total) if total else 0
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE seo_jobs SET progress= $1, status='processing' WHERE job_id=$2",
                    pct,
                    job_id,
                )

        enriched = await run_seo_agent(
            job_id=job_id,
            keywords=keywords,
            brand_name=brand_name,
            domain=domain,
            audience=audience,
            language=language,
            progress_callback=_progress,
        )

        # Persist keywords to DB
        async with pool.acquire() as conn:
            for k in enriched:
                await conn.execute(
                    """
                    INSERT INTO seo_keywords (job_id, keyword, volume, kd, cpc, position, current_url,
                        intent, silo, content_type, title_suggestion, primary_source, audience_match, priority)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    """,
                    job_id,
                    k.get("keyword"),
                    k.get("volume"),
                    k.get("kd"),
                    k.get("cpc"),
                    k.get("position"),
                    k.get("current_url"),
                    k.get("intent"),
                    k.get("silo"),
                    k.get("content_type"),
                    k.get("title_suggestion"),
                    k.get("primary_source"),
                    k.get("audience_match"),
                    k.get("priority"),
                )

        output_path = generate_seo_excel(enriched, brand_name)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE seo_jobs SET status='ready', progress=100, output_file_path=$1, completed_at=now()
                WHERE job_id=$2
                """,
                output_path,
                job_id,
            )
        logger.info("SEO job %s completed: %s", job_id, output_path)

    except Exception as e:
        logger.exception("SEO job %s failed: %s", job_id, e)
        await _mark_failed(job_id, str(e))


async def _mark_failed(job_id: str, error: str):
    pool = await init_db_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE seo_jobs SET status='failed', error_log=$1, completed_at=now() WHERE job_id=$2",
                error[:5000],
                job_id,
            )


@router.post("/upload")
async def upload_seo_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    brand_name: str = Form(""),
    domain: str = Form(""),
    audience: str = Form(""),
    language: str = Form("nl"),
):
    """
    Upload CSV or XLSX keyword file. Returns job_id for status polling and download.
    """
    if not brand_name.strip():
        raise HTTPException(status_code=400, detail="brand_name is required")
    if not domain.strip():
        raise HTTPException(status_code=400, detail="domain is required")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    try:
        keywords = parse_keywords_file(raw, file.filename or "upload.csv")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(keywords) > MAX_KEYWORDS:
        raise HTTPException(status_code=400, detail=f"Max {MAX_KEYWORDS} keywords per upload")

    job_id = _next_job_id()
    out_dir = "/tmp/seo_plans"
    os.makedirs(out_dir, exist_ok=True)
    input_path = os.path.join(out_dir, f"{job_id}_input.csv")
    with open(input_path, "wb") as f:
        f.write(raw)

    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO seo_jobs (job_id, brand_name, domain, audience, language, keyword_count, status, input_file_path)
            VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
            """,
            job_id,
            brand_name.strip(),
            domain.strip(),
            audience.strip(),
            language.strip() or "nl",
            len(keywords),
            input_path,
        )

    background_tasks.add_task(
        _process_seo_job,
        job_id,
        input_path,
        brand_name.strip(),
        domain.strip(),
        audience.strip(),
        language.strip() or "nl",
    )

    return {
        "job_id": job_id,
        "keyword_count": len(keywords),
        "status": "processing",
    }


@router.get("/status/{job_id}")
async def get_seo_status(job_id: str):
    """Poll job status. Returns progress and download_url when ready."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT job_id, status, progress, keyword_count, output_file_path FROM seo_jobs WHERE job_id=$1",
            job_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    status = row["status"]
    progress = row["progress"] or 0
    keyword_count = row["keyword_count"] or 0

    # Estimate processed count during processing (agent inserts at end; use progress for estimate)
    keywords_processed = keyword_count if status == "ready" else int(progress / 100 * keyword_count)

    result = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "keywords_processed": keywords_processed,
        "keywords_total": keyword_count,
    }
    if status == "ready" and row.get("output_file_path"):
        result["download_url"] = f"/api/seo/download/{job_id}"
    return result


@router.get("/download/{job_id}")
async def download_seo_plan(job_id: str):
    """Stream Excel file. Content-Disposition: attachment."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT output_file_path, brand_name, status FROM seo_jobs WHERE job_id=$1",
            job_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["status"] != "ready":
        raise HTTPException(status_code=400, detail="Job not ready for download")
    path = row["output_file_path"]
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")

    brand = (row.get("brand_name") or "SEO_Plan").replace(" ", "_")[:30]
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"SEO_Plan_{brand}_{date_str}.xlsx"

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )

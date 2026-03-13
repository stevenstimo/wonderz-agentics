"""
SEO Keyword Plan — file upload, processing, status polling, download.
POST /api/seo/upload, GET /api/seo/status/{job_id}, GET /api/seo/download/{job_id}
"""
import logging
import os
import uuid
from urllib.parse import urlparse
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.db import init_db_pool
from app.middleware.auth import TokenPayload, get_current_user
from app.utils.seo_excel_generator import generate_seo_excel
from app.utils.seo_parser import parse_keywords_file
from app.agents.seo_agent import run_seo_agent
from app.services.seo_gsc_fetcher import fetch_gsc_for_keywords, get_gsc_site_url_for_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["seo"])
MAX_KEYWORDS = 2000
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _domain_from_site_url(site_url: str | None) -> str:
    """Extract hostname from GSC site_url (e.g. https://www.example.com/ -> www.example.com)."""
    if not site_url or not site_url.strip():
        return ""
    try:
        parsed = urlparse(site_url.strip())
        return parsed.netloc or parsed.path.split("/")[0] or ""
    except Exception:
        return ""


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
    user_id: Optional[str] = None,
    client_slug: Optional[str] = None,
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

        gsc_data: dict = {}
        gsc_site_url: Optional[str] = None
        if user_id and client_slug:
            keyword_texts = [k.get("keyword", "") for k in keywords if k.get("keyword")]
            if keyword_texts:
                gsc_data, gsc_site_url = await fetch_gsc_for_keywords(
                    user_id, client_slug, keyword_texts, days=90
                )

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
            gsc_data=gsc_data,
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

        output_path = generate_seo_excel(enriched, brand_name, gsc_site_url=gsc_site_url)

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
        import traceback
        error_detail = traceback.format_exc()
        print(f"[SEO ERROR] job {job_id}: {error_detail}")
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE seo_jobs SET status='failed', error_log=$1, completed_at=now() WHERE job_id=$2",
                error_detail[:2000],
                job_id,
            )


async def _mark_failed(job_id: str, error: str):
    pool = await init_db_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE seo_jobs SET status='failed', error_log=$1, completed_at=now() WHERE job_id=$2",
                error[:5000],
                job_id,
            )


@router.get("/jobs")
async def list_seo_jobs():
    """Return last 20 SEO jobs for history and download links."""
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT job_id, brand_name, keyword_count, status, created_at, client_slug "
            "FROM seo_jobs ORDER BY created_at DESC LIMIT 20"
        )
    return {"jobs": [dict(r) for r in rows]}


@router.post("/upload")
async def upload_seo_file(
    background_tasks: BackgroundTasks,
    current_user: TokenPayload = Depends(get_current_user),
    file: UploadFile = File(...),
    brand_name: str = Form(""),
    domain: str = Form(""),
    audience: str = Form(""),
    language: str = Form("nl"),
    client_slug: Optional[str] = Form(None),
):
    """
    Upload CSV or XLSX keyword file. Returns job_id for status polling and download.
    When client_slug is set, brand_name and domain are resolved from DB/GSC if empty.
    """
    user_id = current_user.user_id
    resolved_brand = brand_name.strip()
    resolved_domain = domain.strip()

    if client_slug and client_slug.strip():
        pool = await init_db_pool()
        if pool:
            async with pool.acquire() as conn:
                if not resolved_brand:
                    row = await conn.fetchrow(
                        "SELECT client_name FROM clients WHERE user_id = $1 AND slug = $2",
                        user_id,
                        client_slug.strip(),
                    )
                    if row and row.get("client_name"):
                        resolved_brand = (row["client_name"] or "").strip()
                if not resolved_domain:
                    site_url = await get_gsc_site_url_for_client(user_id, client_slug.strip())
                    resolved_domain = _domain_from_site_url(site_url)

    if not resolved_brand:
        raise HTTPException(status_code=400, detail="brand_name is required")
    if not resolved_domain:
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
    ext = (file.filename or "").lower().split(".")[-1] if "." in (file.filename or "") else "csv"
    if ext not in ("csv", "xlsx", "xls", "numbers"):
        ext = "csv"
    input_path = os.path.join(out_dir, f"{job_id}_input.{ext}")
    with open(input_path, "wb") as f:
        f.write(raw)

    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO seo_jobs (job_id, brand_name, domain, audience, language, keyword_count, status, input_file_path, client_slug)
            VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, $8)
            """,
            job_id,
            resolved_brand,
            resolved_domain,
            audience.strip(),
            language.strip() or "nl",
            len(keywords),
            input_path,
            client_slug.strip() if client_slug else None,
        )

    background_tasks.add_task(
        _process_seo_job,
        job_id,
        input_path,
        resolved_brand,
        resolved_domain,
        audience.strip(),
        language.strip() or "nl",
        user_id,
        client_slug.strip() if client_slug else None,
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

"""
SEO Keyword Plan — file upload, processing, status polling, download.
POST /api/seo/upload, GET /api/seo/status/{job_id}, GET /api/seo/download/{job_id}

SEO-routes: optionele ``initiated_by`` (``ceo``, ``coo``, ``direct``). Ontbreekt of leeg → ``direct`` (open tool); alleen expliciete ongeldige waarde → 403.
"""
import json
import logging
import os
import uuid
from urllib.parse import urlparse
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from arq import ArqRedis

from app.db import init_db_pool
from app.middleware.auth import TokenPayload, get_current_user
from app.dependencies import get_arq_pool
from app.agents.seo_talent_agent import run_seo_talent_review
from app.utils.seo_excel_generator import generate_seo_excel
from app.utils.seo_parser import load_keywords_job_file, parse_keywords_file
from app.utils.seo_validator_runner import validate_seo_excel_output
from app.agents.seo_agent import run_seo_agent
from app.services.seo_sheets_exporter import export_seo_to_sheets
from app.services.seo_gsc_fetcher import (
    fetch_gsc_for_keywords,
    fetch_gsc_performance_summary,
    get_gsc_site_url_for_client,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["seo"])


def _require_seo_initiator(initiated_by: str | None) -> str:
    """CEO/COO-flow of directe tool-toegang; alleen onbekende expliciete waarde → 403."""
    if initiated_by is None or (isinstance(initiated_by, str) and not initiated_by.strip()):
        return "direct"  # ontbreekt of alleen whitespace
    normalized = initiated_by.strip().lower()
    if normalized not in ("ceo", "coo", "direct"):
        raise HTTPException(
            status_code=403,
            detail="SEO tool kan alleen worden aangesproken via de CEO/COO flow of direct.",
        )
    return normalized


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


def _build_silo_summary(keywords: List[dict]) -> List[dict]:
    silos: dict[str, dict] = {}
    for k in keywords:
        silo = str(k.get("silo") or "").strip()
        if not silo:
            continue
        if silo not in silos:
            silos[silo] = {"silo": silo, "count": 0, "volume": 0, "kd_sum": 0.0}
        silos[silo]["count"] += 1
        silos[silo]["volume"] += int(k.get("volume") or 0)
        silos[silo]["kd_sum"] += float(k.get("kd") or 0.0)

    rows: List[dict] = []
    for v in silos.values():
        c = v["count"] or 1
        rows.append(
            {
                "silo": v["silo"],
                "count": v["count"],
                "volume": v["volume"],
                "avg_kd": round(v["kd_sum"] / c, 1),
            }
        )
    return sorted(rows, key=lambda x: x["volume"], reverse=True)


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
        keywords = load_keywords_job_file(input_path)

        gsc_data: dict = {}
        gsc_site_url: Optional[str] = None
        gsc_performance: dict = {}
        if user_id and client_slug:
            keyword_texts = [k.get("keyword", "") for k in keywords if k.get("keyword")]
            if keyword_texts:
                gsc_data, gsc_site_url = await fetch_gsc_for_keywords(
                    user_id, client_slug, keyword_texts, days=90
                )
            gsc_performance, _ = await fetch_gsc_performance_summary(user_id, client_slug, days=90)

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

        output_path = generate_seo_excel(
            enriched,
            brand_name,
            gsc_site_url=gsc_site_url,
            gsc_performance=gsc_performance if gsc_performance else None,
        )

        validation = await validate_seo_excel_output(output_path, job_id)

        # Talent review — niet blocker
        try:
            await run_seo_talent_review(
                keyword_data=enriched,
                silo_data=_build_silo_summary(enriched),
                brand_name=brand_name,
                job_id=job_id,
            )
        except Exception as e:
            logger.warning("[SEO Talent] niet-kritieke fout job %s: %s", job_id, e)

        # Sheets export — optioneel, niet blocker
        try:
            await export_seo_to_sheets(
                excel_path=output_path,
                brand_name=brand_name,
                job_id=job_id,
                user_id=user_id,
                client_slug=client_slug,
                db_pool=pool,
            )
        except Exception as e:
            logger.warning("[Sheets Export] niet-kritieke fout job %s: %s", job_id, e)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE seo_jobs SET status='ready', progress=100, output_file_path=$1,
                    validation_score=$2, completed_at=now()
                WHERE job_id=$3
                """,
                output_path,
                validation["score"],
                job_id,
            )
        logger.info("SEO job %s completed: %s", job_id, output_path)

    except ValueError as e:
        err_msg = str(e)[:2000]
        logger.warning("SEO job %s validation failed: %s", job_id, err_msg)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE seo_jobs SET status='failed', error_log=$1, completed_at=now() WHERE job_id=$2",
                err_msg,
                job_id,
            )

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
async def list_seo_jobs(
    initiated_by: str | None = Query(None, description="ceo of coo"),
):
    """Return last 20 SEO jobs for history and download links."""
    _require_seo_initiator(initiated_by)
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
    arq_pool: ArqRedis = Depends(get_arq_pool),
    current_user: TokenPayload = Depends(get_current_user),
    file: UploadFile = File(...),
    file_uk: Optional[UploadFile] = File(None),
    file_de: Optional[UploadFile] = File(None),
    brand_name: str = Form(""),
    domain: str = Form(""),
    audience: str = Form(""),
    language: str = Form("nl"),
    client_slug: Optional[str] = Form(None),
    initiated_by: Optional[str] = Form(None, description="ceo of coo"),
):
    """
    Upload CSV or XLSX keyword file. Returns job_id for status polling and download.
    When client_slug is set, brand_name and domain are resolved from DB/GSC if empty.
    """
    _require_seo_initiator(initiated_by)
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
        keywords: List[dict] = parse_keywords_file(raw, file.filename or "upload.csv", market="NL")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def _read_optional_market(f: Optional[UploadFile], market: str) -> None:
        nonlocal keywords
        if not f or not f.filename:
            return
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"Bestand {market} te groot (max 5MB)")
        try:
            extra = parse_keywords_file(data, f.filename, market=market)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"{market} export: {e}") from e
        keywords.extend(extra)

    await _read_optional_market(file_uk, "UK")
    await _read_optional_market(file_de, "DE")

    if len(keywords) > MAX_KEYWORDS:
        raise HTTPException(status_code=400, detail=f"Max {MAX_KEYWORDS} keywords per upload")

    job_id = _next_job_id()
    out_dir = "/tmp/seo_plans"
    os.makedirs(out_dir, exist_ok=True)
    ext = (file.filename or "").lower().split(".")[-1] if "." in (file.filename or "") else "csv"
    if ext not in ("csv", "xlsx", "xls", "numbers"):
        ext = "csv"
    merged_json = os.path.join(out_dir, f"{job_id}_merged.json")
    with open(merged_json, "w", encoding="utf-8") as jf:
        json.dump(keywords, jf, ensure_ascii=False)
    input_path = merged_json

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

    await arq_pool.enqueue_job(
        "_process_seo_job",
        job_id,
        input_path,
        resolved_brand,
        resolved_domain,
        audience.strip(),
        language.strip() or "nl",
        user_id,
        client_slug.strip() if client_slug else None,
    )

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "keyword_count": len(keywords),
            "status": "pending",
        },
    )


@router.get("/status/{job_id}")
async def get_seo_status(
    job_id: str,
    initiated_by: str | None = Query(None, description="ceo of coo"),
):
    """Poll job status. Returns progress and download_url when ready."""
    who = _require_seo_initiator(initiated_by)
    pool = await init_db_pool()
    if not pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT job_id, status, progress, keyword_count, output_file_path, validation_score "
            "FROM seo_jobs WHERE job_id=$1",
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
        result["download_url"] = f"/api/seo/download/{job_id}?initiated_by={who}"
    vs = row.get("validation_score")
    if vs is not None:
        result["validation_score"] = vs
    result["talent_score"] = None
    result["talent_status"] = None
    result["talent_comments"] = None
    result["sheets_url"] = None
    return result


@router.get("/download/{job_id}")
async def download_seo_plan(
    job_id: str,
    initiated_by: str | None = Query(None, description="ceo of coo"),
):
    """Stream Excel file. Content-Disposition: attachment."""
    _require_seo_initiator(initiated_by)
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
    date_str = datetime.now().strftime("%y%m%d")
    filename = f"{date_str}_{brand}_SEO_Plan.xlsx"

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )

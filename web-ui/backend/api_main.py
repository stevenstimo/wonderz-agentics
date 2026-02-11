
# --- Imports ---
import os
import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uuid
from typing import List, Optional
from models.ui import CrewMember, Task, TaskCrewShare, ImprovementItem
from models.unified import UnifiedProduct
from tools.adapters import ShopifyAdapter, WordPressAdapter
from app.db import init_db_pool, close_db_pool

# --- FastAPI app instance ---
app = FastAPI(title="Multi-Agentic Crew - Orchestrator API")

# --- Demo data for UI endpoints ---
demo_crew = [
    CrewMember(id='pm', name='Product Manager', role='Product Owner', status='active', current_task='Catalog design', progress=80),
    CrewMember(id='dev', name='Shopify Developer', role='Developer', status='busy', current_task='Implement Liquid templates', progress=60),
    CrewMember(id='review', name='Reviewer', role='Reviewer', status='idle', current_task='Waiting for review', progress=0),
    CrewMember(id='devops', name='DevOps', role='DevOps', status='active', current_task='CI/CD setup', progress=40),
    CrewMember(id='ai', name='AI Agent', role='AI', status='active', current_task='Generating code', progress=90),
]

demo_tasks = [
    Task(
        id='t1',
        title='Catalogus Structuur Ontwerpen',
        status='in_progress',
        crew=[TaskCrewShare(crew_id='pm', share=60), TaskCrewShare(crew_id='dev', share=40)],
    ),
    Task(
        id='t2',
        title='Liquid Templates Bouwen',
        status='completed',
        crew=[TaskCrewShare(crew_id='dev', share=80), TaskCrewShare(crew_id='ai', share=20)],
    ),
    Task(
        id='t3',
        title='SEO Optimalisatie',
        status='pending',
        crew=[TaskCrewShare(crew_id='review', share=50), TaskCrewShare(crew_id='ai', share=50)],
    ),
]

demo_improvements = [
    ImprovementItem(
        id="imp-1",
        agent_id="dev",
        agent_name="Shopify Developer",
        title="Tighten error handling in checkout flow",
        summary="Missing guardrails for null pricing data in edge cases.",
        details="Several checkout paths do not validate pricing payloads before render. Add defensive checks and a fallback path for missing totals.",
        severity="high",
        status="open",
        source="hr_manager",
    ),
    ImprovementItem(
        id="imp-2",
        agent_id="review",
        agent_name="Reviewer",
        title="More actionable review notes",
        summary="Feedback lacks clear next steps in 2 of the last 5 reviews.",
        details="Include concrete fix steps and references to specific files/lines. This improves turnaround speed and prevents ambiguity.",
        severity="medium",
        status="open",
        source="hr_manager",
    ),
]

# --- UI API endpoints ---
@app.get("/api/crew", response_model=List[CrewMember])
async def get_crew():
    return demo_crew

@app.get("/api/tasks", response_model=List[Task])
async def get_tasks():
    return demo_tasks


@app.get("/api/improvements", response_model=List[ImprovementItem])
async def get_improvements(agent_id: Optional[str] = None):
    from app.db import _pool
    if _pool is None:
        return demo_improvements
    query = (
        "SELECT id, agent_id, agent_name, title, summary, details, severity, "
        "status, source, created_at, updated_at "
        "FROM agent_improvements"
    )
    params = []
    if agent_id:
        query += " WHERE agent_id=$1"
        params.append(agent_id)
    query += " ORDER BY created_at DESC"
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]
    except Exception:
        return demo_improvements

# Dummy clients for demonstration (replace with real API clients)
class DummyShopifyClient:
    async def get_product(self, product_id):
        return {
            'id': product_id,
            'title': f'Shopify Product {product_id}',
            'body_html': '<p>Example description</p>',
            'variants': [{'price': '19.99', 'currency': 'EUR', 'inventory_quantity': 10}],
            'seo': {'title': 'SEO Title', 'description': 'SEO Desc'},
            'tags': 'tag1,tag2',
        }

class DummyWordPressClient:
    async def get_product(self, product_id):
        return {
            'id': product_id,
            'name': f'WP Product {product_id}',
            'description': '<p>WP description</p>',
            'price': '29.99',
            'currency': 'EUR',
            'stock_quantity': 5,
            'seo_title': 'WP SEO Title',
            'seo_description': 'WP SEO Desc',
            'tags': ['wp', 'product'],
            'attributes': {'color': 'red'},
        }

@app.get("/api/products/unified", response_model=List[UnifiedProduct])
async def get_unified_products():
    """Return a demo list of unified products from multiple platforms via adapters."""
    shopify_adapter = ShopifyAdapter(DummyShopifyClient())
    wp_adapter = WordPressAdapter(DummyWordPressClient())
    # Demo: fetch 1 product from each adapter
    shopify_product = await shopify_adapter.get_product("shopify-1")
    wp_product = await wp_adapter.get_product("wp-1")
    return [shopify_product, wp_product]

@app.on_event("startup")
async def on_startup():
    await init_db_pool()

@app.on_event("shutdown")
async def on_shutdown():
    await close_db_pool()

@app.post("/api/jobs")
async def create_job(req: CreateJobRequest):
    from app.db import _pool
    if _pool is None:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    job_id = str(uuid.uuid4())
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO jobs(id, store_id, job_type, status, payload, created_at) VALUES($1,$2,$3,$4,$5,now())",
            job_id,
            req.store_id,
            req.job_type,
            "queued",
            json.dumps(req.payload or {}),
        )
    try:
        from workers.tasks import run_job
        run_job.delay(job_id, req.store_id, req.payload or {})
    except Exception as e:
        async with _pool.acquire() as conn:
            await conn.execute("UPDATE jobs SET status=$1 WHERE id=$2", "failed", job_id)
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {e}")
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    from app.db import _pool
    if _pool is None:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, status, payload, result_summary, created_at, started_at, finished_at FROM jobs WHERE id=$1", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        return dict(row)

def _check_basic_auth_header(auth_header: str) -> None:
    if not auth_header:
        raise HTTPException(status_code=401, detail="Unauthorized")
    import base64, os
    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "basic":
            raise HTTPException(status_code=401, detail="Unauthorized")
        decoded = base64.b64decode(token).decode()
        user, pwd = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ok_user = os.getenv("APPROVAL_USER")
    ok_pass = os.getenv("APPROVAL_PASS")
    if not ok_user or not ok_pass or user != ok_user or pwd != ok_pass:
        raise HTTPException(status_code=403, detail="Forbidden")

@app.post("/api/jobs/{job_id}/approve")
async def approve_job(job_id: str, request: Request):
    """Approve a job that is in AWAITING_APPROVAL; transitions it back to 'queued' and re-enqueues the worker."""
    from app.db import _pool
    if _pool is None:
        raise HTTPException(status_code=500, detail="DB pool not initialized")
    # Check basic auth header
    _check_basic_auth_header(request.headers.get("Authorization"))
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, store_id, payload FROM jobs WHERE id=$1", job_id)
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        if row["status"] != "AWAITING_APPROVAL":
            raise HTTPException(status_code=409, detail="job is not awaiting approval")
        await conn.execute("UPDATE jobs SET status=$1, started_at=now() WHERE id=$2", "running", job_id)
        store_id = row["store_id"]
        payload = row["payload"]
    try:
        from workers.tasks import run_job
        run_job.delay(job_id, store_id, payload or {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to re-enqueue job: {e}")
    return {"job_id": job_id, "status": "running"}
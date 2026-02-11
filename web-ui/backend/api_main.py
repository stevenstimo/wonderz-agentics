
# --- Imports ---
import os
import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uuid
from typing import List, Optional
from models.ui import CrewMember, Task, TaskCrewShare, ImprovementItem, HiredAgent, ApprovalRequest, TrainingSession
from models.unified import UnifiedProduct
from tools.adapters import ShopifyAdapter, WordPressAdapter
from app.db import init_db_pool, close_db_pool
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from web_ui.backend.agents.ceo_manager import CEOManagerAgent
from web_ui.backend.agents.hr_agent import HRAgent
from config import ANTHROPIC_API_KEY

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
class CreateCrewMemberRequest(BaseModel):
    name: str
    role: str
    specialization: Optional[str] = None
    permissions: Optional[List[str]] = None


class UpdateCrewMemberRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[str] = None
    current_task: Optional[str] = None
    progress: Optional[int] = None


@app.get("/api/crew", response_model=List[CrewMember])
async def get_crew():
    from app.db import _pool
    if _pool is None:
        return demo_crew
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT crew_id as id, name, role, status, current_task, progress FROM crew_members WHERE status != 'deactivated' ORDER BY created_at DESC"
            )
        crew_list = []
        for row in rows:
            crew_list.append(CrewMember(
                id=row['id'],
                name=row['name'],
                role=row['role'],
                status=row['status'],
                current_task=row['current_task'],
                progress=row['progress'] or 0
            ))
        return crew_list
    except Exception:
        return demo_crew


@app.post("/api/crew")
async def create_crew_member(req: CreateCrewMemberRequest):
    """Create a new crew member"""
    from app.db import _pool
    if _pool is None:
        return {"error": "Database not initialized"}, 500
    
    crew_id = f"{req.role.lower()}_{uuid.uuid4().hex[:8]}"
    
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO crew_members (crew_id, name, role, specialization, permissions) VALUES ($1, $2, $3, $4, $5)",
                crew_id, req.name, req.role, req.specialization, json.dumps(req.permissions or [])
            )
        return {
            "status": "success",
            "crew_id": crew_id,
            "message": f"Crew member {req.name} created successfully"
        }
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/api/crew/{crew_id}")
async def get_crew_member(crew_id: str):
    """Get a specific crew member"""
    from app.db import _pool
    if _pool is None:
        return {"error": "Database not initialized"}, 500
    
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT crew_id, name, role, specialization, status, performance_score, completed_tasks, current_task, progress FROM crew_members WHERE crew_id = $1",
                crew_id
            )
        if row:
            return dict(row)
        return {"error": "Crew member not found"}, 404
    except Exception as e:
        return {"error": str(e)}, 500


@app.put("/api/crew/{crew_id}")
async def update_crew_member(crew_id: str, req: UpdateCrewMemberRequest):
    """Update a crew member"""
    from app.db import _pool
    if _pool is None:
        return {"error": "Database not initialized"}, 500
    
    updates = []
    params = []
    param_count = 1
    
    for field in ["name", "role", "specialization", "status", "current_task", "progress"]:
        value = getattr(req, field, None)
        if value is not None:
            updates.append(f"{field} = ${param_count}")
            params.append(value)
            param_count += 1
    
    if not updates:
        return {"error": "No fields to update"}, 400
    
    updates.append(f"updated_at = now()")
    params.append(crew_id)
    
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                f"UPDATE crew_members SET {', '.join(updates)} WHERE crew_id = ${param_count}",
                *params
            )
        return {"status": "success", "message": f"Crew member {crew_id} updated"}
    except Exception as e:
        return {"error": str(e)}, 500


@app.delete("/api/crew/{crew_id}")
async def delete_crew_member(crew_id: str):
    """Deactivate a crew member (soft delete)"""
    from app.db import _pool
    if _pool is None:
        return {"error": "Database not initialized"}, 500
    
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE crew_members SET status = 'deactivated', updated_at = now() WHERE crew_id = $1",
                crew_id
            )
        return {"status": "success", "message": f"Crew member {crew_id} deactivated"}
    except Exception as e:
        return {"error": str(e)}, 500


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


# ========================================
# CEO/Manager Agent Endpoints
# ========================================

# In-memory CEO agent instance
_ceo_agent = None


def get_ceo_agent():
    global _ceo_agent
    if _ceo_agent is None:
        _ceo_agent = CEOManagerAgent(ANTHROPIC_API_KEY)
    return _ceo_agent


class MakePlanRequest(BaseModel):
    project_idea: str
    context: Optional[dict] = None


class HireAgentRequest(BaseModel):
    name: str
    role: str
    specialization: Optional[str] = None
    permissions: Optional[List[str]] = None


class RequestApprovalInput(BaseModel):
    request_type: str
    details: dict


@app.post("/api/ceo/plan")
async def ceo_make_plan(req: MakePlanRequest):
    """CEO makes a plan for a project"""
    ceo = get_ceo_agent()
    result = ceo.make_plan(req.project_idea, context=req.context)
    return result


@app.post("/api/ceo/hire")
async def ceo_hire_agent(req: HireAgentRequest):
    """CEO hires a new agent"""
    ceo = get_ceo_agent()
    spec = {
        "name": req.name,
        "role": req.role,
        "specialization": req.specialization,
        "permissions": req.permissions or [],
    }
    result = ceo.hire_agent(spec)
    return result


@app.post("/api/ceo/approval/request")
async def ceo_request_approval(req: RequestApprovalInput):
    """Request CEO approval for a critical action"""
    ceo = get_ceo_agent()
    result = ceo.request_approval(req.request_type, req.details)
    return result


@app.post("/api/ceo/approval/{approval_id}/decide")
async def ceo_approve_or_reject(approval_id: str, approved: bool = True):
    """CEO approves or rejects a pending request"""
    ceo = get_ceo_agent()
    result = ceo.approve_request(approval_id, approved=approved)
    return result


@app.get("/api/ceo/telemetry")
async def ceo_get_telemetry():
    """Get CEO telemetry and system status"""
    ceo = get_ceo_agent()
    return ceo.get_telemetry()


@app.get("/api/ceo/agents", response_model=List[HiredAgent])
async def ceo_list_agents():
    """List all hired agents"""
    ceo = get_ceo_agent()
    return [HiredAgent(**agent) for agent in ceo.hired_agents.values()]


@app.get("/api/ceo/approvals", response_model=List[ApprovalRequest])
async def ceo_list_approvals():
    """List all approval requests"""
    ceo = get_ceo_agent()
    return [ApprovalRequest(**approval) for approval in ceo.approvals_pending]


# ========================================
# Training Module Endpoints
# ========================================

class RequestTrainingInput(BaseModel):
    crew_id: str
    agent_name: str
    training_url: str
    training_title: Optional[str] = None
    training_summary: Optional[str] = None


class CompleteTrainingInput(BaseModel):
    session_id: str
    knowledge_base: str
    summary: Optional[str] = None


@app.post("/api/training/request")
async def request_training(req: RequestTrainingInput):
    """Request training for an agent"""
    from app.db import _pool
    if _pool is None:
        return {"error": "Database not initialized"}, 500
    
    session_id = f"train_{uuid.uuid4().hex[:12]}"
    
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO training_sessions (session_id, crew_id, agent_name, training_url, training_title, training_summary) VALUES ($1, $2, $3, $4, $5, $6)",
                session_id, req.crew_id, req.agent_name, req.training_url, req.training_title, req.training_summary
            )
        
        ceo = get_ceo_agent()
        approval_result = ceo.request_approval("training", {
            "session_id": session_id,
            "agent": req.agent_name,
            "url": req.training_url,
        })
        
        return {
            "status": "success",
            "session_id": session_id,
            "approval_id": approval_result.get("approval_id"),
            "message": f"Training requested for {req.agent_name}. Awaiting CEO approval."
        }
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/api/training/sessions", response_model=List[TrainingSession])
async def list_training_sessions(crew_id: Optional[str] = None, status: Optional[str] = None):
    """List training sessions, optionally filtered by crew_id or status"""
    from app.db import _pool
    if _pool is None:
        return []
    
    query = "SELECT session_id, crew_id, agent_name, training_url, training_title, training_summary, knowledge_base, status, approval_status, requested_at, approved_at, completed_at, metadata FROM training_sessions WHERE 1=1"
    params = []
    param_count = 1
    
    if crew_id:
        query += f" AND crew_id = ${param_count}"
        params.append(crew_id)
        param_count += 1
    
    if status:
        query += f" AND status = ${param_count}"
        params.append(status)
        param_count += 1
    
    query += " ORDER BY requested_at DESC"
    
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return [TrainingSession(**dict(row)) for row in rows]
    except Exception:
        return []


@app.post("/api/training/{session_id}/complete")
async def complete_training(session_id: str, req: CompleteTrainingInput):
    """Mark a training session as complete with knowledge base content"""
    from app.db import _pool
    if _pool is None:
        return {"error": "Database not initialized"}, 500
    
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE training_sessions SET status = 'completed', knowledge_base = $1, completed_at = now(), updated_at = now() WHERE session_id = $2",
                req.knowledge_base, session_id
            )
        return {"status": "success", "message": f"Training {session_id} marked as completed"}
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/api/training/{crew_id}/knowledge-base")
async def get_agent_knowledge_base(crew_id: str):
    """Get the knowledge base for an agent"""
    from app.db import _pool
    if _pool is None:
        return {"knowledge_base": "", "sessions": []}
    
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT knowledge_base, training_url, training_title FROM training_sessions WHERE crew_id = $1 AND status = 'completed' ORDER BY completed_at DESC",
                crew_id
            )
        
        knowledge_base = ""
        sessions = []
        for row in rows:
            if row['knowledge_base']:
                knowledge_base += f"\n{row['knowledge_base']}"
            sessions.append({
                "title": row['training_title'],
                "url": row['training_url']
            })
        
        return {
            "crew_id": crew_id,
            "knowledge_base": knowledge_base.strip(),
            "training_sessions": sessions
        }
    except Exception as e:
        return {"error": str(e)}, 500


# ========================================
# HR Agent Endpoints
# ========================================

_hr_agent = None


def get_hr_agent():
    global _hr_agent
    if _hr_agent is None:
        _hr_agent = HRAgent(ANTHROPIC_API_KEY)
    return _hr_agent


class AnalyzePerformanceInput(BaseModel):
    agent_id: str
    agent_name: str
    performance_data: dict


class RegisterImprovementInput(BaseModel):
    agent_id: str
    agent_name: str
    title: str
    summary: Optional[str] = None
    details: Optional[str] = None
    severity: Optional[str] = "medium"
    source: Optional[str] = "hr_manager"


@app.post("/api/hr/analyze-performance")
async def hr_analyze_performance(req: AnalyzePerformanceInput):
    """HR Agent analyzes agent performance"""
    hr = get_hr_agent()
    result = hr.analyze_agent_performance(req.agent_id, req.agent_name, req.performance_data)
    return result


@app.post("/api/hr/register-improvement")
async def hr_register_improvement(req: RegisterImprovementInput):
    """Register an improvement point for an agent"""
    hr = get_hr_agent()
    improvement = {
        "title": req.title,
        "summary": req.summary,
        "details": req.details,
        "severity": req.severity,
        "source": req.source,
    }
    result = hr.register_improvement(req.agent_id, req.agent_name, improvement)
    return result


@app.get("/api/hr/improvements")
async def hr_get_improvements(agent_id: Optional[str] = None):
    """Get improvement points"""
    hr = get_hr_agent()
    return hr.get_agent_improvements(agent_id)


@app.get("/api/hr/development-plan/{agent_id}")
async def hr_get_development_plan(agent_id: str, agent_name: str = ""):
    """Generate a development plan for an agent"""
    if not agent_name:
        agent_name = f"Agent {agent_id}"
    
    hr = get_hr_agent()
    result = hr.get_development_plan(agent_id, agent_name)
    return result
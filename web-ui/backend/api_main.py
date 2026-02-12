from uuid import uuid4
# CrewMember toevoegen endpoint
@app.post("/api/crew", response_model=CrewMember)
def add_crew_member(crew: CrewMember, db: Session = Depends(get_db)):
    db_crew = CrewMemberSQL(
        id=crew.id or str(uuid4()),
        name=crew.name,
        role=crew.role,
        specialization=crew.specialization,
        status=crew.status,
        current_task=crew.current_task,
        progress=crew.progress,
        avatar_url=crew.avatar_url,
        system_instructions=crew.system_instructions,
        knowledge_base_sources=None,  # Optioneel: serialiseren indien gewenst
        tool_access_whitelist=None,   # Optioneel: serialiseren indien gewenst
        hiring_logic=crew.hiring_logic,
        persona=crew.persona,
        quality_notes=crew.quality_notes,
        development_notes=crew.development_notes
    )
    db.add(db_crew)
    db.commit()
    db.refresh(db_crew)
    return crew

# --- Imports ---
import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
import uuid
from typing import List, Optional
from models.ui import CrewMember, Task, TaskCrewShare, ImprovementItem, HiredAgent, ApprovalRequest, TrainingSession
from models.sql_models import CrewMemberSQL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
from models.unified import UnifiedProduct
from tools.adapters import ShopifyAdapter, WordPressAdapter
from app.db import init_db_pool, close_db_pool
import sys
backend_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(os.path.dirname(backend_dir))
sys.path.insert(0, repo_root)
sys.path.insert(0, backend_dir)
from agents.ceo_manager import CEOManagerAgent
from agents.hr_agent import HRAgent
from config import ANTHROPIC_API_KEY

# --- FastAPI app instance ---
app = FastAPI(title="Multi-Agentic Crew - Orchestrator API")

# --- CORS ---
cors_origins_env = os.getenv("CORS_ORIGINS")
cors_origins = (
    [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    if cors_origins_env
    else [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "https://wonderz-agentics.vercel.app",
        "https://frontend-rho-one-99.vercel.app",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Error Response Models ---
class ErrorResponse(BaseModel):
    """Standard error response format"""
    error: str
    code: str
    details: Optional[dict] = None
    timestamp: Optional[str] = None


class ExplainerSection(BaseModel):
    slug: str
    title: str
    body_markdown: str
    source: Optional[str] = None
    updated_at: Optional[str] = None


# --- Middleware for Global Error Handling ---
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Global error handling middleware"""
    try:
        response = await call_next(request)
        return response
    except ValueError as e:
        return {
            "error": str(e),
            "code": "VALIDATION_ERROR",
            "timestamp": str(datetime.now())
        }, 400
    except Exception as e:
        return {
            "error": "Internal server error",
            "code": "INTERNAL_ERROR",
            "details": {"message": str(e)},
            "timestamp": str(datetime.now())
        }, 500


# --- Crew API endpoints (database-backed) ---
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/crew", response_model=List[CrewMember])
def get_crew(db: Session = Depends(get_db)):
    crew = db.query(CrewMemberSQL).all()
    # Convert SQLAlchemy models to Pydantic models
    return [CrewMember(
        id=c.id,
        name=c.name,
        role=c.role,
        specialization=c.specialization,
        status=c.status,
        current_task=c.current_task,
        progress=c.progress,
        avatar_url=c.avatar_url,
        system_instructions=c.system_instructions,
        knowledge_base_sources=None,  # Optional: parse from string if needed
        tool_access_whitelist=None,   # Optional: parse from string if needed
        hiring_logic=c.hiring_logic,
        persona=c.persona,
        quality_notes=c.quality_notes,
        development_notes=c.development_notes
    ) for c in crew]

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

demo_explainer_sections = [
    {
        "slug": "how-it-works",
        "title": "How this tool works",
        "body_markdown": (
            "This workspace runs a multi-agent workflow that moves through intake, development, review, and delivery.\n\n"
            "Key things to know:\n"
            "- The backend orchestrates agents and stores results in the database.\n"
            "- The frontend shows progress and approvals in real time.\n"
            "- Crew members are configurable and their roles drive output quality.\n\n"
            "Update this section whenever workflows, stages, or integrations change."
        ),
        "source": "demo",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "slug": "persona",
        "title": "Persona and behavior",
        "body_markdown": (
            "Personas define how each crew member behaves: tone, priorities, and decision rules.\n\n"
            "Keep personas consistent with system instructions and training inputs. Update when you change prompt logic "
            "or agent responsibilities."
        ),
        "source": "demo",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "slug": "crew",
        "title": "Crew capabilities",
        "body_markdown": (
            "Each crew member is described by Persona, Quality, and Development.\n"
            "- Persona: how the agent thinks and communicates.\n"
            "- Quality: what the agent does well today.\n"
            "- Development: where the agent should improve next.\n\n"
            "This content is sourced from the crew database so it stays aligned with live agent configs."
        ),
        "source": "demo",
        "updated_at": datetime.utcnow().isoformat(),
    },
]


def _build_explainer_meta():
    return {
        "deploy_env": os.getenv("DEPLOY_ENV", "local"),
        "build_sha": os.getenv("DEPLOY_SHA", os.getenv("GIT_SHA", "unknown")),
        "build_time": os.getenv("BUILD_TIME"),
        "data_refreshed_at": datetime.utcnow().isoformat(),
    }

# --- UI API endpoints ---
class CreateCrewMemberRequest(BaseModel):
    name: str
    role: str
    specialization: Optional[str] = None
    permissions: Optional[List[str]] = None
    system_instructions: str
    knowledge_base_sources: Optional[List[str]] = None
    tool_access_whitelist: Optional[List[str]] = None
    hiring_logic: str
    persona: Optional[str] = None
    quality_notes: Optional[str] = None
    development_notes: Optional[str] = None
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name must be 100 characters or less")
        return v.strip()
    
    @validator('role')
    def validate_role(cls, v):
        valid_roles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training']
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v
    
    @validator('specialization')
    def validate_specialization(cls, v):
        if v is not None and len(v) > 250:
            raise ValueError("Specialization must be 250 characters or less")
        return v

    @validator('system_instructions')
    def validate_system_instructions(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("System instructions cannot be empty")
        if len(v) > 4000:
            raise ValueError("System instructions must be 4000 characters or less")
        return v

    @validator('hiring_logic')
    def validate_hiring_logic(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Hiring logic cannot be empty")
        if len(v) > 2000:
            raise ValueError("Hiring logic must be 2000 characters or less")
        return v

    @validator('knowledge_base_sources')
    def validate_knowledge_base_sources(cls, v):
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Knowledge base sources must be 50 items or less")
        for item in v:
            if not item or len(item.strip()) == 0:
                raise ValueError("Knowledge base sources cannot be empty")
            if len(item) > 2048:
                raise ValueError("Knowledge base source is too long (max 2048 characters)")
        return v

    @validator('tool_access_whitelist')
    def validate_tool_access_whitelist(cls, v):
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Tool access whitelist must be 50 items or less")
        for item in v:
            if not item or len(item.strip()) == 0:
                raise ValueError("Tool access whitelist entries cannot be empty")
            if len(item) > 200:
                raise ValueError("Tool access whitelist entry is too long (max 200 characters)")
        return v

    @validator('persona', 'quality_notes', 'development_notes')
    def validate_explainer_text(cls, v):
        if v is None:
            return v
        if len(v) > 2000:
            raise ValueError("Explainer fields must be 2000 characters or less")
        return v


class UpdateCrewMemberRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    specialization: Optional[str] = None
    status: Optional[str] = None
    current_task: Optional[str] = None
    progress: Optional[int] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[List[str]] = None
    tool_access_whitelist: Optional[List[str]] = None
    hiring_logic: Optional[str] = None
    persona: Optional[str] = None
    quality_notes: Optional[str] = None
    development_notes: Optional[str] = None
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError("Name cannot be empty")
            if len(v) > 100:
                raise ValueError("Name must be 100 characters or less")
        return v
    
    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            valid_roles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training']
            if v not in valid_roles:
                raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ['active', 'busy', 'idle', 'deactivated']
            if v not in valid_statuses:
                raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v
    
    @validator('progress')
    def validate_progress(cls, v):
        if v is not None:
            if not (0 <= v <= 100):
                raise ValueError("Progress must be between 0 and 100")
        return v

    @validator('system_instructions')
    def validate_system_instructions(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError("System instructions cannot be empty")
            if len(v) > 4000:
                raise ValueError("System instructions must be 4000 characters or less")
        return v

    @validator('hiring_logic')
    def validate_hiring_logic(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                raise ValueError("Hiring logic cannot be empty")
            if len(v) > 2000:
                raise ValueError("Hiring logic must be 2000 characters or less")
        return v

    @validator('persona', 'quality_notes', 'development_notes')
    def validate_update_explainer_text(cls, v):
        if v is None:
            return v
        if len(v) > 2000:
            raise ValueError("Explainer fields must be 2000 characters or less")
        return v

    @validator('knowledge_base_sources')
    def validate_knowledge_base_sources(cls, v):
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Knowledge base sources must be 50 items or less")
        for item in v:
            if not item or len(item.strip()) == 0:
                raise ValueError("Knowledge base sources cannot be empty")
            if len(item) > 2048:
                raise ValueError("Knowledge base source is too long (max 2048 characters)")
        return v

    @validator('tool_access_whitelist')
    def validate_tool_access_whitelist(cls, v):
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Tool access whitelist must be 50 items or less")
        for item in v:
            if not item or len(item.strip()) == 0:
                raise ValueError("Tool access whitelist entries cannot be empty")
            if len(item) > 200:
                raise ValueError("Tool access whitelist entry is too long (max 200 characters)")
        return v


class CreateJobRequest(BaseModel):
    store_id: Optional[str] = None
    job_type: str = "pdp_optimization"
    payload: Optional[dict] = None


@app.get("/api/crew", response_model=List[CrewMember])
async def get_crew():
    from app.db import _pool
    if _pool is None:
        return demo_crew
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT crew_id as id, name, role, specialization, status, current_task, progress, system_instructions, knowledge_base_sources, tool_access_whitelist, hiring_logic, persona, quality_notes, development_notes FROM crew_members WHERE status != 'deactivated' ORDER BY created_at DESC"
            )
        crew_list = []
        for row in rows:
            crew_list.append(CrewMember(
                id=row['id'],
                name=row['name'],
                role=row['role'],
                specialization=row['specialization'],
                status=row['status'],
                current_task=row['current_task'],
                progress=row['progress'] or 0,
                system_instructions=row['system_instructions'],
                knowledge_base_sources=row['knowledge_base_sources'],
                tool_access_whitelist=row['tool_access_whitelist'],
                hiring_logic=row['hiring_logic'],
                persona=row['persona'],
                quality_notes=row['quality_notes'],
                development_notes=row['development_notes']
            ))
        return crew_list
    except Exception:
        return demo_crew


@app.post("/api/crew")
async def create_crew_member(req: CreateCrewMemberRequest):
    """Create a new crew member"""
    from app.db import _pool
    
    if _pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please try again later."
        )
    
    crew_id = f"{req.role.lower()}_{uuid.uuid4().hex[:8]}"
    
    knowledge_base_sources = req.knowledge_base_sources or []
    tool_access_whitelist = req.tool_access_whitelist or []
    try:
        async with _pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO crew_members (crew_id, name, role, specialization, permissions, system_instructions, knowledge_base_sources, tool_access_whitelist, hiring_logic, persona, quality_notes, development_notes) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
                    crew_id,
                    req.name,
                    req.role,
                    req.specialization,
                    json.dumps(req.permissions or []),
                    req.system_instructions,
                    json.dumps(knowledge_base_sources),
                    json.dumps(tool_access_whitelist),
                    req.hiring_logic,
                    req.persona,
                    req.quality_notes,
                    req.development_notes
                )
                await conn.execute(
                    "INSERT INTO ceo_hired_agents (agent_id, name, role, specialization, status, permissions, system_instructions, knowledge_base_sources, tool_access_whitelist, hiring_logic, persona, quality_notes, development_notes) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) ON CONFLICT (agent_id) DO UPDATE SET name = EXCLUDED.name, role = EXCLUDED.role, specialization = EXCLUDED.specialization, status = EXCLUDED.status, permissions = EXCLUDED.permissions, system_instructions = EXCLUDED.system_instructions, knowledge_base_sources = EXCLUDED.knowledge_base_sources, tool_access_whitelist = EXCLUDED.tool_access_whitelist, hiring_logic = EXCLUDED.hiring_logic, persona = EXCLUDED.persona, quality_notes = EXCLUDED.quality_notes, development_notes = EXCLUDED.development_notes, updated_at = now()",
                    crew_id,
                    req.name,
                    req.role,
                    req.specialization,
                    "active",
                    json.dumps(req.permissions or []),
                    req.system_instructions,
                    json.dumps(knowledge_base_sources),
                    json.dumps(tool_access_whitelist),
                    req.hiring_logic,
                    req.persona,
                    req.quality_notes,
                    req.development_notes
                )
                await conn.execute(
                    "INSERT INTO hired_agents (agent_id, name, role, specialization, status, permissions, system_instructions, knowledge_base_sources, tool_access_whitelist, hiring_logic, persona, quality_notes, development_notes) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13) ON CONFLICT (agent_id) DO UPDATE SET name = EXCLUDED.name, role = EXCLUDED.role, specialization = EXCLUDED.specialization, status = EXCLUDED.status, permissions = EXCLUDED.permissions, system_instructions = EXCLUDED.system_instructions, knowledge_base_sources = EXCLUDED.knowledge_base_sources, tool_access_whitelist = EXCLUDED.tool_access_whitelist, hiring_logic = EXCLUDED.hiring_logic, persona = EXCLUDED.persona, quality_notes = EXCLUDED.quality_notes, development_notes = EXCLUDED.development_notes, updated_at = now()",
                    crew_id,
                    req.name,
                    req.role,
                    req.specialization,
                    "active",
                    json.dumps(req.permissions or []),
                    req.system_instructions,
                    json.dumps(knowledge_base_sources),
                    json.dumps(tool_access_whitelist),
                    req.hiring_logic,
                    req.persona,
                    req.quality_notes,
                    req.development_notes
                )
        return {
            "status": "success",
            "crew_id": crew_id,
            "message": f"Crew member {req.name} created successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create crew member: {str(e)}"
        )


@app.get("/api/crew/{crew_id}")
async def get_crew_member(crew_id: str):
    """Get a specific crew member"""
    from app.db import _pool
    
    if not crew_id or len(crew_id.strip()) == 0:
        raise HTTPException(status_code=400, detail="crew_id cannot be empty")
    
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT crew_id, name, role, specialization, status, performance_score, completed_tasks, current_task, progress, system_instructions, knowledge_base_sources, tool_access_whitelist, hiring_logic, persona, quality_notes, development_notes FROM crew_members WHERE crew_id = $1",
                crew_id
            )
        if row:
            return dict(row)
        raise HTTPException(status_code=404, detail=f"Crew member {crew_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.put("/api/crew/{crew_id}")
async def update_crew_member(crew_id: str, req: UpdateCrewMemberRequest):
    """Update a crew member"""
    from app.db import _pool
    
    if not crew_id or len(crew_id.strip()) == 0:
        raise HTTPException(status_code=400, detail="crew_id cannot be empty")
    
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    def build_updates(field_map, json_fields=None):
        updates = []
        params = []
        json_fields = json_fields or set()
        for field, value in field_map.items():
            if value is not None:
                if field in json_fields:
                    value = json.dumps(value)
                updates.append(f"{field} = ${len(params) + 1}")
                params.append(value)
        return updates, params

    crew_fields = {
        "name": req.name,
        "role": req.role,
        "specialization": req.specialization,
        "status": req.status,
        "current_task": req.current_task,
        "progress": req.progress,
        "system_instructions": req.system_instructions,
        "knowledge_base_sources": req.knowledge_base_sources,
        "tool_access_whitelist": req.tool_access_whitelist,
        "hiring_logic": req.hiring_logic,
        "persona": req.persona,
        "quality_notes": req.quality_notes,
        "development_notes": req.development_notes,
    }
    crew_updates, crew_params = build_updates(
        crew_fields,
        json_fields={"knowledge_base_sources", "tool_access_whitelist"}
    )

    if not crew_updates:
        raise HTTPException(status_code=400, detail="At least one field must be provided for update")

    crew_updates.append("updated_at = now()")
    crew_params.append(crew_id)
    
    try:
        async with _pool.acquire() as conn:
            # Verify crew member exists first
            crew_check = await conn.fetchrow("SELECT crew_id FROM crew_members WHERE crew_id = $1", crew_id)
            if not crew_check:
                raise HTTPException(status_code=404, detail=f"Crew member {crew_id} not found")

            await conn.execute(
                f"UPDATE crew_members SET {', '.join(crew_updates)} WHERE crew_id = ${len(crew_params)}",
                *crew_params
            )

            ceo_fields = {
                "name": req.name,
                "role": req.role,
                "specialization": req.specialization,
                "status": req.status,
                "system_instructions": req.system_instructions,
                "knowledge_base_sources": req.knowledge_base_sources,
                "tool_access_whitelist": req.tool_access_whitelist,
                "hiring_logic": req.hiring_logic,
                "persona": req.persona,
                "quality_notes": req.quality_notes,
                "development_notes": req.development_notes,
            }
            ceo_updates, ceo_params = build_updates(
                ceo_fields,
                json_fields={"knowledge_base_sources", "tool_access_whitelist"}
            )
            if ceo_updates:
                ceo_updates.append("updated_at = now()")
                ceo_params.append(crew_id)
                await conn.execute(
                    f"UPDATE ceo_hired_agents SET {', '.join(ceo_updates)} WHERE agent_id = ${len(ceo_params)}",
                    *ceo_params
                )

            hired_updates, hired_params = build_updates(
                ceo_fields,
                json_fields={"knowledge_base_sources", "tool_access_whitelist"}
            )
            if hired_updates:
                hired_updates.append("updated_at = now()")
                hired_params.append(crew_id)
                await conn.execute(
                    f"UPDATE hired_agents SET {', '.join(hired_updates)} WHERE agent_id = ${len(hired_params)}",
                    *hired_params
                )
        return {"status": "success", "message": f"Crew member {crew_id} updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update crew member: {str(e)}")


@app.delete("/api/crew/{crew_id}")
async def delete_crew_member(crew_id: str):
    """Deactivate a crew member (soft delete)"""
    from app.db import _pool
    
    if not crew_id or len(crew_id.strip()) == 0:
        raise HTTPException(status_code=400, detail="crew_id cannot be empty")
    
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with _pool.acquire() as conn:
            # Verify crew member exists
            crew_check = await conn.fetchrow("SELECT crew_id FROM crew_members WHERE crew_id = $1", crew_id)
            if not crew_check:
                raise HTTPException(status_code=404, detail=f"Crew member {crew_id} not found")
            
            await conn.execute(
                "UPDATE crew_members SET status = 'deactivated', updated_at = now() WHERE crew_id = $1",
                crew_id
            )
        return {"status": "success", "message": f"Crew member {crew_id} deactivated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate crew member: {str(e)}")


from fastapi import Query

@app.get("/api/explainer/sections")
async def get_explainer_sections(slug: str = Query(None)):
    """Return explainer sections sourced from the database, optionally filtered by slug."""
    from app.db import _pool
    meta = _build_explainer_meta()
    if _pool is None:
        # Filter demo data if slug is provided
        if slug:
            filtered = [s for s in demo_explainer_sections if s["slug"].startswith(slug)]
            return {"sections": filtered, "meta": meta}
        return {"sections": demo_explainer_sections, "meta": meta}
    try:
        async with _pool.acquire() as conn:
            if slug:
                rows = await conn.fetch(
                    "SELECT slug, title, body_markdown, source, updated_at FROM explainer_sections WHERE slug LIKE $1 ORDER BY slug",
                    f"{slug}%"
                )
            else:
                rows = await conn.fetch(
                    "SELECT slug, title, body_markdown, source, updated_at FROM explainer_sections ORDER BY slug"
                )
        sections = [dict(row) for row in rows]
        if not sections:
            sections = demo_explainer_sections
        return {"sections": sections, "meta": meta}
    except Exception:
        return {"sections": demo_explainer_sections, "meta": meta}


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


async def _store_approval_request(approval: dict):
    from app.db import _pool
    if _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ceo_approval_requests (
                    approval_id, request_type, status, details, requested_at, approved_at, rejected_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT (approval_id) DO UPDATE SET
                    request_type = EXCLUDED.request_type,
                    status = EXCLUDED.status,
                    details = EXCLUDED.details,
                    requested_at = EXCLUDED.requested_at,
                    approved_at = EXCLUDED.approved_at,
                    rejected_at = EXCLUDED.rejected_at
                """,
                approval.get("id"),
                approval.get("type"),
                approval.get("status"),
                json.dumps(approval.get("details") or {}),
                approval.get("requested_at"),
                approval.get("approved_at"),
                approval.get("rejected_at"),
            )
    except Exception:
        pass


async def _update_approval_status(approval_id: str, status: str, details: Optional[dict] = None):
    from app.db import _pool
    if _pool is None:
        return
    approved_at = datetime.now().isoformat() if status == "approved" else None
    rejected_at = datetime.now().isoformat() if status == "rejected" else None
    details_json = json.dumps(details) if details is not None else None
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ceo_approval_requests
                SET status = $1,
                    approved_at = COALESCE($2, approved_at),
                    rejected_at = COALESCE($3, rejected_at),
                    details = COALESCE($4, details)
                WHERE approval_id = $5
                """,
                status,
                approved_at,
                rejected_at,
                details_json,
                approval_id,
            )
    except Exception:
        pass


class MakePlanRequest(BaseModel):
    project_idea: str
    context: Optional[dict] = None
    
    @validator('project_idea')
    def validate_project_idea(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("project_idea cannot be empty")
        if len(v) > 1000:
            raise ValueError("project_idea must be 1000 characters or less")
        return v


class HireAgentRequest(BaseModel):
    name: str
    role: str
    specialization: Optional[str] = None
    permissions: Optional[List[str]] = None
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("name cannot be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or less")
        return v
    
    @validator('role')
    def validate_role(cls, v):
        valid_roles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training']
        if v not in valid_roles:
            raise ValueError(f"role must be one of: {', '.join(valid_roles)}")
        return v


class RequestApprovalInput(BaseModel):
    request_type: str
    details: dict
    
    @validator('request_type')
    def validate_request_type(cls, v):
        valid_types = ['training', 'resource', 'promotion', 'critical_action']
        if v not in valid_types:
            raise ValueError(f"request_type must be one of: {', '.join(valid_types)}")
        return v


class ApprovalDecisionInput(BaseModel):
    note: Optional[str] = None


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
    approval_entry = next((a for a in ceo.approvals_pending if a.get("id") == result.get("approval_id")), None)
    if approval_entry:
        await _store_approval_request(approval_entry)
    return result


@app.post("/api/ceo/approval/{approval_id}/decide")
async def ceo_approve_or_reject(
    approval_id: str,
    approved: bool = True,
    decision: ApprovalDecisionInput = Body(default=ApprovalDecisionInput())
):
    """CEO approves or rejects a pending request"""
    ceo = get_ceo_agent()
    approval_entry = next((a for a in ceo.approvals_pending if a.get("id") == approval_id), None)
    if approval_entry and decision.note:
        details = approval_entry.get("details") or {}
        details["decision_note"] = decision.note
        approval_entry["details"] = details
    result = ceo.approve_request(approval_id, approved=approved)

    if approval_entry and approval_entry.get("type") == "training":
        session_id = (approval_entry.get("details") or {}).get("session_id")
        if session_id:
            from app.db import _pool
            if _pool is not None:
                status = "approved" if approved else "rejected"
                try:
                    async with _pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE training_sessions
                            SET approval_status = $1,
                                approved_at = CASE WHEN $1 = 'approved' THEN now() ELSE approved_at END,
                                updated_at = now()
                            WHERE session_id = $2
                            """,
                            status,
                            session_id
                        )
                except Exception:
                    pass

    await _update_approval_status(
        approval_id,
        "approved" if approved else "rejected",
        details=approval_entry.get("details") if approval_entry else None
    )
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
    from app.db import _pool
    if _pool is not None:
        try:
            async with _pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT approval_id, request_type, status, details, requested_at, approved_at, rejected_at "
                    "FROM ceo_approval_requests ORDER BY requested_at DESC"
                )
            return [
                ApprovalRequest(
                    id=row["approval_id"],
                    request_type=row["request_type"],
                    status=row["status"],
                    details=row["details"] or {},
                    requested_at=row["requested_at"],
                    approved_at=row["approved_at"],
                    rejected_at=row["rejected_at"],
                )
                for row in rows
            ]
        except Exception:
            pass

    ceo = get_ceo_agent()
    mapped = []
    for approval in ceo.approvals_pending:
        mapped.append({
            "id": approval.get("id"),
            "request_type": approval.get("type"),
            "status": approval.get("status"),
            "details": approval.get("details"),
            "requested_at": approval.get("requested_at"),
            "approved_at": approval.get("approved_at"),
            "rejected_at": approval.get("rejected_at"),
        })
    return [ApprovalRequest(**approval) for approval in mapped]


# ========================================
# Training Module Endpoints
# ========================================

class RequestTrainingInput(BaseModel):
    crew_id: str
    agent_name: str
    training_url: str
    training_title: Optional[str] = None
    training_summary: Optional[str] = None
    
    @validator('crew_id')
    def validate_crew_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("crew_id cannot be empty")
        return v
    
    @validator('agent_name')
    def validate_agent_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("agent_name cannot be empty")
        return v
    
    @validator('training_url')
    def validate_training_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("training_url must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("training_url is too long (max 2048 characters)")
        return v
    
    @validator('training_title')
    def validate_training_title(cls, v):
        if v is not None and len(v) > 200:
            raise ValueError("training_title must be 200 characters or less")
        return v


class CompleteTrainingInput(BaseModel):
    session_id: str
    knowledge_base: str
    summary: Optional[str] = None
    
    @validator('session_id')
    def validate_session_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("session_id cannot be empty")
        return v
    
    @validator('knowledge_base')
    def validate_knowledge_base(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("knowledge_base cannot be empty")
        if len(v) > 10000:
            raise ValueError("knowledge_base content is too long (max 10000 characters)")
        return v


@app.post("/api/training/request")
async def request_training(req: RequestTrainingInput):
    """Request training for an agent"""
    from app.db import _pool
    
    if _pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please try again later."
        )
    
    session_id = f"train_{uuid.uuid4().hex[:12]}"
    
    try:
        async with _pool.acquire() as conn:
            async with conn.transaction():
                # Verify crew member exists
                crew_check = await conn.fetchrow(
                    "SELECT crew_id FROM crew_members WHERE crew_id = $1 AND status != 'deactivated'",
                    req.crew_id
                )
                if not crew_check:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Crew member {req.crew_id} not found or is deactivated"
                    )

                await conn.execute(
                    "INSERT INTO training_sessions (session_id, crew_id, agent_name, training_url, training_title, training_summary) VALUES ($1, $2, $3, $4, $5, $6)",
                    session_id, req.crew_id, req.agent_name, req.training_url, req.training_title, req.training_summary
                )

                crew_sources_row = await conn.fetchrow(
                    "SELECT knowledge_base_sources FROM crew_members WHERE crew_id = $1",
                    req.crew_id
                )
                existing_sources = crew_sources_row["knowledge_base_sources"] if crew_sources_row else []
                if existing_sources is None:
                    existing_sources = []
                if req.training_url not in existing_sources:
                    existing_sources.append(req.training_url)
                await conn.execute(
                    "UPDATE crew_members SET knowledge_base_sources = $1, updated_at = now() WHERE crew_id = $2",
                    json.dumps(existing_sources), req.crew_id
                )
                await conn.execute(
                    "UPDATE ceo_hired_agents SET knowledge_base_sources = $1, updated_at = now() WHERE agent_id = $2",
                    json.dumps(existing_sources), req.crew_id
                )
                await conn.execute(
                    "UPDATE hired_agents SET knowledge_base_sources = $1, updated_at = now() WHERE agent_id = $2",
                    json.dumps(existing_sources), req.crew_id
                )
        
        ceo = get_ceo_agent()
        approval_result = ceo.request_approval("training", {
            "session_id": session_id,
            "agent": req.agent_name,
            "url": req.training_url,
        })

        approval_entry = next((a for a in ceo.approvals_pending if a.get("id") == approval_result.get("approval_id")), None)
        if approval_entry:
            await _store_approval_request(approval_entry)

        approval_id = approval_result.get("approval_id")
        if approval_id:
            async with _pool.acquire() as conn:
                await conn.execute(
                    "UPDATE training_sessions SET metadata = $1, updated_at = now() WHERE session_id = $2",
                    json.dumps({"approval_id": approval_id}),
                    session_id
                )
        
        return {
            "status": "success",
            "session_id": session_id,
            "approval_id": approval_result.get("approval_id"),
            "message": f"Training requested for {req.agent_name}. Awaiting CEO approval."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to request training: {str(e)}"
        )


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
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please try again later."
        )
    
    try:
        async with _pool.acquire() as conn:
            # Verify training session exists and is approved
            session_check = await conn.fetchrow(
                "SELECT status, approval_status, metadata FROM training_sessions WHERE session_id = $1",
                session_id
            )
            if not session_check:
                raise HTTPException(
                    status_code=404,
                    detail=f"Training session {session_id} not found"
                )
            
            if session_check['approval_status'] != 'approved':
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot complete training that is not approved. Current status: {session_check['approval_status']}"
                )
            
            await conn.execute(
                "UPDATE training_sessions SET status = 'completed', knowledge_base = $1, completed_at = now(), updated_at = now() WHERE session_id = $2",
                req.knowledge_base, session_id
            )

            metadata = session_check.get("metadata") or {}
            approval_id = metadata.get("approval_id") if isinstance(metadata, dict) else None
            if approval_id:
                completion_details = {
                    "training_completed": True,
                    "training_completed_at": datetime.now().isoformat()
                }
                await _update_approval_status(approval_id, "completed", details=completion_details)
        
        return {
            "status": "success",
            "message": f"Training {session_id} marked as completed",
            "session_id": session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete training: {str(e)}"
        )


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
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("agent_id cannot be empty")
        return v
    
    @validator('agent_name')
    def validate_agent_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("agent_name cannot be empty")
        return v
    
    @validator('performance_data')
    def validate_performance_data(cls, v):
        if not v or not isinstance(v, dict):
            raise ValueError("performance_data must be a non-empty dictionary")
        return v


class RegisterImprovementInput(BaseModel):
    agent_id: str
    agent_name: str
    title: str
    summary: Optional[str] = None
    details: Optional[str] = None
    severity: Optional[str] = "medium"
    source: Optional[str] = "hr_manager"
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("agent_id cannot be empty")
        return v
    
    @validator('agent_name')
    def validate_agent_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("agent_name cannot be empty")
        return v
    
    @validator('title')
    def validate_title(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("title cannot be empty")
        if len(v) > 200:
            raise ValueError("title must be 200 characters or less")
        return v
    
    @validator('severity')
    def validate_severity(cls, v):
        if v is not None:
            valid_severities = ['low', 'medium', 'high', 'critical']
            if v not in valid_severities:
                raise ValueError(f"severity must be one of: {', '.join(valid_severities)}")
        return v


@app.post("/api/hr/analyze-performance")
async def hr_analyze_performance(req: AnalyzePerformanceInput):
    """HR Agent analyzes agent performance"""
    hr = get_hr_agent()
    result = hr.analyze_agent_performance(req.agent_id, req.agent_name, req.performance_data)
    return result


@app.post("/api/hr/register-improvement")
async def hr_register_improvement(req: RegisterImprovementInput):
    """Register an improvement point for an agent"""
    from app.db import _pool
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database not available. Please try again later.")

    improvement_id = str(uuid.uuid4())
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_improvements (
                    id, agent_id, agent_name, title, summary, details, severity, status, source, created_at, updated_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,now(),now())
                """,
                improvement_id,
                req.agent_id,
                req.agent_name,
                req.title,
                req.summary,
                req.details,
                req.severity,
                "open",
                req.source
            )
        return {
            "status": "success",
            "agent_id": req.agent_id,
            "improvement_id": improvement_id,
            "message": f"Improvement point registered for {req.agent_name}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register improvement: {str(e)}")


@app.get("/api/hr/improvements")
async def hr_get_improvements(agent_id: Optional[str] = None):
    """Get improvement points"""
    from app.db import _pool
    if _pool is None:
        return []

    query = (
        "SELECT id, agent_id, agent_name, title, summary, details, severity, status, source, created_at, updated_at "
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
        return []


@app.get("/api/hr/development-plan/{agent_id}")
async def hr_get_development_plan(agent_id: str, agent_name: str = ""):
    """Generate a development plan for an agent"""
    if not agent_name:
        agent_name = f"Agent {agent_id}"
    hr = get_hr_agent()

    from app.db import _pool
    if _pool is not None:
        try:
            async with _pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, agent_id, agent_name, title, summary, details, severity, status, source, created_at "
                    "FROM agent_improvements WHERE agent_id=$1 ORDER BY created_at DESC",
                    agent_id
                )
            hr.improvements[agent_id] = [dict(row) for row in rows]
        except Exception:
            pass

    result = hr.get_development_plan(agent_id, agent_name)
    return result
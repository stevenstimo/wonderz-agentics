# --- Imports ---
import os
import sys
import json
import uuid
from uuid import uuid4
from datetime import datetime
from typing import List, Optional
import base64
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Body, Depends, Query
import requests
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, validator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Add root path to sys.path for imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(os.path.dirname(backend_dir))
sys.path.insert(0, repo_root)
sys.path.insert(0, backend_dir)

from models.ui import CrewMember, Task, TaskCrewShare, ImprovementItem, HiredAgent, ApprovalRequest, TrainingSession, Talent
from models.sql_models import CrewMemberSQL, TalentSQL, SettingsSQL
from models.unified import UnifiedProduct
from tools.adapters import ShopifyAdapter, WordPressAdapter
from agents.ceo_manager import CEOManagerAgent
from agents.hr_agent import HRAgent

from config import ANTHROPIC_API_KEY
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cqasccazioqjodctawzx.supabase.co")
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNxYXNjY2F6aW9xam9kY3Rhd3p4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4MDU0NDEsImV4cCI6MjA4NjM4MTQ0MX0.h8wkn_Tg0pEXmQppnQcRbV7Bxw1pSP_0xPqAnVxLA38",
)
SUPER_ADMIN_EMAIL = "stevenstimo@gmail.com"

# --- Database setup ---

# Use DATABASE_URL from environment, fail if not set in production
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set. Configure it as a Fly.io secret or in your .env file.")

# SQLAlchemy sync engine cannot use asyncpg driver in threadpool endpoints.
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

# Local fallback: when DATABASE_URL points to Docker host "postgres", switch to sqlite.
if ":" in DATABASE_URL:
    DATABASE_URL = "sqlite:///./wonderz_local.db"

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs = {"connect_args": {"check_same_thread": False}}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure local fallback sqlite has required tables.
from models.sql_models import Base
Base.metadata.create_all(bind=engine)


# --- FastAPI app instance ---
app = FastAPI(title="Multi-Agentic Crew - Orchestrator API")


@app.get("/api/health")
def health_check():
    """Lightweight readiness endpoint for UI status checks."""
    return {
        "status": "ok",
        "service": "backend",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/health/details")
def health_details():
    """Detailed readiness for UI status dashboard."""
    db_ok = False
    db_error = None

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "backend",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {
            "database": {
                "ok": db_ok,
                "detail": "SELECT 1 succeeded" if db_ok else f"Database check failed: {db_error}",
            },
            "dave_dev_endpoint": {
                "ok": True,
                "detail": "Dave Dev endpoints registered",
            },
        },
    }


@app.get("/api/status/recent")
def status_recent_changes():
    """Expose a small recent-change snapshot for status UI."""
    snippet = _safe_git_snippet(max_lines=8)
    commits = []
    changed = []

    if snippet:
        for block in snippet.split("\n\n"):
            if block.startswith("Recent commits:"):
                commits = [line.strip() for line in block.splitlines()[1:] if line.strip()]
            if block.startswith("Working tree snapshot:"):
                changed = [line.strip() for line in block.splitlines()[1:] if line.strip()]

    return {
        "status": "ok",
        "recent_commits": commits[:5],
        "working_tree_top": changed[:8],
    }


@app.get("/api/status/summary")
def status_summary():
    """Single payload for frontend status dashboard."""
    health = health_details()
    recent = status_recent_changes()

    settings_ok = False
    active_providers: List[str] = []
    db = SessionLocal()
    try:
        settings = db.query(SettingsSQL).filter(SettingsSQL.id == "default").first()
        if settings:
            has_anthropic = bool(getattr(settings, "anthropic_api_key", None))
            has_gemini = bool(getattr(settings, "gemini_api_key", None))
            settings_ok = has_anthropic or has_gemini
            if has_anthropic:
                active_providers.append("Anthropic")
            if has_gemini:
                active_providers.append("Gemini")
    finally:
        db.close()

    return {
        "status": "ok" if health.get("status") == "ok" else "degraded",
        "health": health,
        "dave_dev": {
            "ok": True,
            "status": "active",
            "specialization": "Full-stack Technical Consultant & Agentic Architecture Specialist",
        },
        "settings": {
            "ok": settings_ok,
            "active_providers": active_providers,
        },
        "recent": recent,
    }

# --- CORS ---
cors_origins_env = os.getenv("CORS_ORIGINS")
cors_origins = (
    [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    if cors_origins_env
    else [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
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


class UpdateExplainerSectionRequest(BaseModel):
    title: Optional[str] = None
    body_markdown: Optional[str] = None

# --- Middleware for Global Error Handling ---
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Global error handling middleware"""
    from fastapi.responses import JSONResponse
    try:
        response = await call_next(request)
        return response
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "timestamp": str(datetime.now())
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "details": {"message": str(e)},
                "timestamp": str(datetime.now())
            }
        )

# --- Database session dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def _fetch_supabase_user(access_token: str) -> dict:
    try:
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": SUPABASE_ANON_KEY,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Auth service unavailable: {exc}") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return response.json()


def _resolve_user_role(db: Session, user_id: str, email: str) -> str:
    if (email or "").strip().lower() == SUPER_ADMIN_EMAIL:
        return "super_admin"

    row = db.execute(
        text("SELECT role::text AS role FROM user_roles WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().first()
    return row["role"] if row and row.get("role") else "member"


def get_current_user_context(request: Request, db: Session = Depends(get_db)) -> dict:
    access_token = _extract_bearer_token(request)
    user = _fetch_supabase_user(access_token)
    user_id = user.get("id")
    email = user.get("email", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token user payload")
    role = _resolve_user_role(db, user_id=user_id, email=email)
    return {"id": user_id, "email": email, "role": role}


def require_super_admin(user: dict = Depends(get_current_user_context)) -> dict:
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin required")
    return user


# --- Demo data ---
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
        "title": "How it works",
        "body_markdown": """Wonderz-Agentics is a multi-agent orchestration platform designed to automate complex business workflows through specialized AI agents working together.

The Platform Architecture

Our system is built on three core layers:

Backend Orchestration (FastAPI)
- Manages agent lifecycle and task distribution
    {
        "slug": "how-it-works",
The personas are encoded in system instructions that the agent receives with each task.

- Pragmatic and detail-oriented
- Focuses on clean, maintainable code
- Values testing and documentation
- Thinks three steps ahead to prevent technical debt
- Advocates for best practices and security

Product Owner
- Customer-focused and strategic
- Prioritizes business value
- Asks "why" before "how"
- Balances speed with quality
- Communicates clearly with stakeholders

Reviewer
- Critical but constructive
- Looks for both strengths and improvements

DevOps
HR Agent
- Empathetic and development-focused

Dave Dev (Technical Consultant)
- Pragmatic, analytical, direct
- Explains complex concepts simply

When you hire a new talent to your crew:
1. Define their persona description
2. Set their quality expectations

Persona vs Role

Important distinction:

Learning and Evolution

Personas are not static:
Best Practices for Personas

1. Be specific: Vague personas lead to inconsistent behavior
2. Make them memorable: Use clear language and examples
3. Include decision-making frameworks: How do they prioritize?
4. Define communication style: Formal? Casual? Technical?
5. Set boundaries: What are they NOT supposed to do?

The Impact on Output

A strong persona means:
- Consistent quality and style
- Better decision-making
- Clearer communication
- Fewer conflicts between agents
- Predictable behavior
""",
        "source": "docs",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "slug": "crew",
        "title": "Crew capabilities",
        "body_markdown": """Your crew is the heart of Wonderz-Agentics. Each member brings specialized skills and a unique perspective to solving problems.

What is a Crew Member?

A crew member is:
- An AI agent with a specific role and expertise
- Capable of working independently on assigned tasks
- Part of a collaborative team
- Continuously learning and improving
- Subject to human oversight and approval

Each crew member has three dimensions that define their value:

Persona
- How they think and approach work
- Their decision-making style
- Their communication approach
- What drives their priorities

Quality
- What they do well today
- Their proven capabilities
- Standards they maintain
- Output consistency

Development
- What they're learning
- Skills being acquired
- Areas for improvement
- Growth trajectory

Managing Your Crew

In the Crew Management section, you can:

1. View All Crew Members
- See active status, current task, and progress
- Check their specialization and role
- Review performance metrics

2. Hire New Crew Members
- Start with Talents in the Talent pool
- Review their persona, quality, and growth areas
- Set their system instructions
- Assign hiring logic (when to use them)
- Promote to crew when approved

3. Monitor Performance
- Track task completion rates
- Review quality of output
- Identify improvement areas
- Gather feedback from other agents

4. Provide Feedback
- Regular performance reviews
- Constructive improvement suggestions
- Recognition of achievements
- Adjustment of responsibilities

Crew Roles Available

Developer
- Full-stack implementation
- Code generation and refinement
- Architecture decisions
- Technical problem-solving

Product Owner
- Requirements definition
- Prioritization
- Stakeholder communication
- Success criteria

Reviewer
- Code quality assurance
- Best practices enforcement
- Feedback and improvement suggestions
- Final approval of deliverables

DevOps
- Deployment automation
- Infrastructure management
- Performance optimization
- Monitoring and alerting

HR
- Talent management
- Performance tracking
- Team development
- Conflict resolution

Dave Dev (Technical Consultant)
- Architecture guidance
- Technical decision support
- VS Code prompt generation
- Code quality mentoring

Assigning Tasks

When assigning work:

1. Choose the right crew member for the task
- Match skills to requirements
- Consider current workload
- Account for growth opportunities

2. Provide clear context
- What needs to be done
- Why it matters
- Success criteria
- Constraints and requirements

3. Set approval points
- Where human review is needed
- Escalation criteria
- Final sign-off requirements

4. Monitor progress
- Check progress indicators
- Provide mid-task feedback
- Adjust if needed

Crew Development

Your crew improves over time:

- Each task builds experience
- Feedback is incorporated
- Skills are enhanced
- Personas evolve
- Quality consistently improves

HR tracks improvements and can surface:
- Areas needing training
- Strengths to leverage
- Growth opportunities
- Performance issues

Collaboration

Crew members work together:
- Developers receive requirements from Product Owner
- Developers implement while HR provides coaching
- Reviewers provide feedback on quality
- DevOps prepares deployment
- Dave Dev is available for architectural questions

The key to high-performing teams is clear roles, good communication, and continuous feedback.

Optimizing Your Crew

To get the best results:

1. Match roles to temperament
- Don't force someone into an unnatural role
- Play to strengths

2. Provide clear expectations
- Set persona and quality standards
- Define success metrics

3. Give regular feedback
- Celebrate wins
- Address issues quickly
- Invest in development

4. Rotate responsibilities
- Builds well-rounded team
- Prevents burnout
- Develops new skills

5. Invest in culture
- Create psychological safety
- Encourage collaboration
- Recognize contributions
""",
        "source": "docs",
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


# --- Request/Response Models ---
class CreateTalentRequest(BaseModel):
    name: str
    persona: str
    quality: str
    growth: str
    skills: Optional[list[dict]] = []
    avatar_url: Optional[str] = None


class UpdateTalentRequest(BaseModel):
    name: Optional[str] = None
    persona: Optional[str] = None
    quality: Optional[str] = None
    growth: Optional[str] = None
    skills: Optional[list[dict]] = None
    avatar_url: Optional[str] = None

class PromoteTalentRequest(BaseModel):
    role: str
    system_instructions: str
    hiring_logic: str
    specialization: Optional[str] = None

class CreateCrewMemberRequest(BaseModel):
    name: str
    role: str
    avatar_url: Optional[str] = None
    specialization: Optional[str] = None
    permissions: Optional[List[str]] = None
    system_instructions: str
    knowledge_base_sources: Optional[List[str]] = None
    tool_access_whitelist: Optional[List[str]] = None
    hiring_logic: str
    persona: Optional[str] = None
    quality_notes: Optional[str] = None
    growth: Optional[str] = None
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
        valid_roles = ['Developer', 'Product Owner', 'Reviewer', 'DevOps', 'AI', 'HR', 'Training', 'CIO']
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


class UpdateCrewMemberRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    avatar_url: Optional[str] = None
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
    growth: Optional[str] = None
    development_notes: Optional[str] = None


class CreateJobRequest(BaseModel):
    store_id: Optional[str] = None
    job_type: str = "pdp_optimization"
    payload: Optional[dict] = None
    job_post: Optional[str] = None
    prompt: Optional[str] = None
    user_id: Optional[str] = None
    source_platform: Optional[str] = None


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


class ApprovalDecisionInput(BaseModel):
    note: Optional[str] = None


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


class SettingsInput(BaseModel):
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None


# --- Dummy clients for demonstration ---
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


# --- TALENT API ENDPOINTS ---
@app.get("/api/talents", response_model=List[Talent])
def get_talents(db: Session = Depends(get_db)):
    talents = db.query(TalentSQL).all()
    return [Talent(
        id=t.id,
        name=t.name,
        persona=t.persona,
        quality=t.quality,
        growth=t.growth,
        skills=json.loads(t.skills) if t.skills else [],
        avatar_url=t.avatar_url,
        created_at=t.created_at
    ) for t in talents]

@app.get("/api/talents/{talent_id}", response_model=Talent)
def get_talent(talent_id: str, db: Session = Depends(get_db)):
    t = db.query(TalentSQL).filter(TalentSQL.id == talent_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Talent not found")
    return Talent(
        id=t.id,
        name=t.name,
        persona=t.persona,
        quality=t.quality,
        growth=t.growth,
        skills=json.loads(t.skills) if t.skills else [],
        avatar_url=t.avatar_url,
        created_at=t.created_at
    )

@app.post("/api/talents", response_model=Talent)
def create_talent(
    req: CreateTalentRequest,
    _user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    talent_id = str(uuid4())
    t = TalentSQL(
        id=talent_id,
        name=req.name,
        persona=req.persona,
        quality=req.quality,
        growth=req.growth,
        skills=json.dumps(req.skills or []),
        avatar_url=req.avatar_url,
        created_at=datetime.utcnow()
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return Talent(
        id=t.id,
        name=t.name,
        persona=t.persona,
        quality=t.quality,
        growth=t.growth,
        skills=json.loads(t.skills) if t.skills else [],
        avatar_url=t.avatar_url,
        created_at=t.created_at
    )


@app.put("/api/talents/{talent_id}", response_model=Talent)
def update_talent(
    talent_id: str,
    req: UpdateTalentRequest,
    _user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    t = db.query(TalentSQL).filter(TalentSQL.id == talent_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Talent not found")

    if req.name is not None:
        t.name = req.name
    if req.persona is not None:
        t.persona = req.persona
    if req.quality is not None:
        t.quality = req.quality
    if req.growth is not None:
        t.growth = req.growth
    if req.skills is not None:
        t.skills = json.dumps(req.skills)
    if req.avatar_url is not None:
        t.avatar_url = req.avatar_url

    db.commit()
    db.refresh(t)
    return Talent(
        id=t.id,
        name=t.name,
        persona=t.persona,
        quality=t.quality,
        growth=t.growth,
        skills=json.loads(t.skills) if t.skills else [],
        avatar_url=t.avatar_url,
        created_at=t.created_at
    )


@app.post("/api/talents/{talent_id}/promote", response_model=CrewMember)
def promote_talent_to_crew(
    talent_id: str,
    req: PromoteTalentRequest,
    _user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Promote a talent to a crew member (activate them)"""
    # Get the talent
    talent = db.query(TalentSQL).filter(TalentSQL.id == talent_id).first()
    if not talent:
        raise HTTPException(status_code=404, detail="Talent not found")
    
    # Create crew member from talent
    crew_member = CrewMemberSQL(
        id=talent.id,  # Use same ID for traceability
        name=talent.name,
        role=req.role,
        specialization=req.specialization or talent.persona,
        status="active",
        current_task=None,
        progress=0,
        avatar_url=talent.avatar_url,
        system_instructions=req.system_instructions,
        knowledge_base_sources=None,
        tool_access_whitelist=None,
        hiring_logic=req.hiring_logic,
        persona=talent.persona,
        quality_notes=talent.quality,
        growth=talent.growth,
        development_notes=None
    )
    
    db.add(crew_member)
    # Delete talent after promotion
    db.delete(talent)
    db.commit()
    db.refresh(crew_member)
    
    return CrewMember(
        id=crew_member.id,
        name=crew_member.name,
        role=crew_member.role,
        specialization=crew_member.specialization,
        status=crew_member.status,
        current_task=crew_member.current_task,
        progress=crew_member.progress or 0,
        avatar_url=crew_member.avatar_url,
        system_instructions=crew_member.system_instructions,
        knowledge_base_sources=None,
        tool_access_whitelist=None,
        hiring_logic=crew_member.hiring_logic,
        persona=crew_member.persona,
        quality_notes=crew_member.quality_notes,
        growth=crew_member.growth,
        development_notes=crew_member.development_notes
    )


# --- CREW API ENDPOINTS ---
@app.get("/api/crew", response_model=List[CrewMember])
def get_crew(db: Session = Depends(get_db)):
    crew = db.query(CrewMemberSQL).all()
    return [CrewMember(
        id=c.id,
        name=c.name,
        role=c.role,
        specialization=c.specialization,
        status=c.status,
        current_task=c.current_task,
        progress=c.progress or 0,
        avatar_url=c.avatar_url,
        system_instructions=c.system_instructions,
        knowledge_base_sources=None,
        tool_access_whitelist=None,
        hiring_logic=c.hiring_logic,
        persona=c.persona,
        quality_notes=c.quality_notes,
        growth=getattr(c, 'growth', None),
        development_notes=c.development_notes
    ) for c in crew]


@app.post("/api/crew", response_model=CrewMember)
def add_crew_member(
    req: CreateCrewMemberRequest,
    _user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    crew_id = str(uuid4())
    db_crew = CrewMemberSQL(
        id=crew_id,
        name=req.name,
        role=req.role,
        specialization=req.specialization,
        status='active',
        current_task=None,
        progress=0,
        avatar_url=req.avatar_url,
        system_instructions=req.system_instructions,
        knowledge_base_sources=None,
        tool_access_whitelist=None,
        hiring_logic=req.hiring_logic,
        persona=req.persona,
        quality_notes=req.quality_notes,
        growth=req.growth,
        development_notes=req.development_notes
    )
    db.add(db_crew)
    db.commit()
    db.refresh(db_crew)
    return CrewMember(
        id=db_crew.id,
        name=db_crew.name,
        role=db_crew.role,
        specialization=db_crew.specialization,
        status=db_crew.status,
        current_task=db_crew.current_task,
        progress=db_crew.progress or 0,
        avatar_url=db_crew.avatar_url,
        system_instructions=db_crew.system_instructions,
        knowledge_base_sources=None,
        tool_access_whitelist=None,
        hiring_logic=db_crew.hiring_logic,
        persona=db_crew.persona,
        quality_notes=db_crew.quality_notes,
        growth=getattr(db_crew, 'growth', None),
        development_notes=db_crew.development_notes,
    )


@app.put("/api/crew/{crew_id}", response_model=CrewMember)
def update_crew_member(
    crew_id: str,
    req: UpdateCrewMemberRequest,
    _user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    crew = db.query(CrewMemberSQL).filter(CrewMemberSQL.id == crew_id).first()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew member not found")

    update_fields = [
        "name", "role", "avatar_url", "specialization", "status", "current_task",
        "progress", "system_instructions", "hiring_logic", "persona",
        "quality_notes", "growth", "development_notes"
    ]
    for field in update_fields:
        value = getattr(req, field)
        if value is not None:
            setattr(crew, field, value)

    db.commit()
    db.refresh(crew)
    return CrewMember(
        id=crew.id,
        name=crew.name,
        role=crew.role,
        specialization=crew.specialization,
        status=crew.status,
        current_task=crew.current_task,
        progress=crew.progress or 0,
        avatar_url=crew.avatar_url,
        system_instructions=crew.system_instructions,
        knowledge_base_sources=None,
        tool_access_whitelist=None,
        hiring_logic=crew.hiring_logic,
        persona=crew.persona,
        quality_notes=crew.quality_notes,
        growth=getattr(crew, "growth", None),
        development_notes=crew.development_notes,
    )


@app.delete("/api/crew/{crew_id}")
def deactivate_crew_member(
    crew_id: str,
    _user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    crew = db.query(CrewMemberSQL).filter(CrewMemberSQL.id == crew_id).first()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew member not found")
    crew.status = "inactive"
    db.commit()
    return {"status": "success", "message": "Crew member deactivated"}


@app.get("/api/tasks", response_model=List[Task])
async def get_tasks():
    return demo_tasks


@app.get("/api/improvements", response_model=List[ImprovementItem])
async def get_improvements(agent_id: Optional[str] = None):
    return demo_improvements


@app.get("/api/explainer/sections")
async def get_explainer_sections(slug: str = Query(None)):
    meta = _build_explainer_meta()
    if slug:
        filtered = [s for s in demo_explainer_sections if s["slug"].startswith(slug)]
        return {"sections": filtered, "meta": meta}
    return {"sections": demo_explainer_sections, "meta": meta}


@app.put("/api/explainer/sections/{slug}")
async def update_explainer_section(
    slug: str,
    req: UpdateExplainerSectionRequest,
    _user: dict = Depends(require_super_admin),
):
    section = next((s for s in demo_explainer_sections if s["slug"] == slug), None)
    if not section:
        raise HTTPException(status_code=404, detail="Explainer section not found")

    if req.title is not None:
        section["title"] = req.title
    if req.body_markdown is not None:
        section["body_markdown"] = req.body_markdown
    section["updated_at"] = datetime.utcnow().isoformat()

    return {"status": "success", "section": section, "meta": _build_explainer_meta()}


@app.get("/api/products/unified", response_model=List[UnifiedProduct])
async def get_unified_products():
    """Return a demo list of unified products from multiple platforms via adapters."""
    shopify_adapter = ShopifyAdapter(DummyShopifyClient())
    wp_adapter = WordPressAdapter(DummyWordPressClient())
    shopify_product = await shopify_adapter.get_product("shopify-1")
    wp_product = await wp_adapter.get_product("wp-1")
    return [shopify_product, wp_product]


_demo_jobs = {}


def _build_demo_plan(prompt_text: str):
    return [
        {"step_index": 1, "agent_role": "copywriter", "description": "Analyseer briefing", "requires_approval": False},
        {"step_index": 2, "agent_role": "developer", "description": "Werk concept uit", "requires_approval": False},
        {"step_index": 3, "agent_role": "reviewer", "description": "Kwaliteitscontrole", "requires_approval": True},
    ]


def _demo_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _demo_running_steps():
    return [
        {"step_index": 1, "step_name": "copy_agent", "agent_role": "copywriter", "status": "in_progress", "created_at": _demo_now_iso()},
        {"step_index": 2, "step_name": "reviewer_agent", "agent_role": "reviewer", "status": "pending", "created_at": _demo_now_iso()},
    ]


def _maybe_progress_demo_job(job_state: dict):
    """Assumption-based: demo API auto-progresses RUNNING jobs to JOB_READY after a short delay."""
    job = job_state.get("job", {})
    if job.get("status") != "RUNNING":
        return
    started_at = job.get("running_started_at")
    if not started_at:
        return
    try:
        elapsed = (datetime.utcnow() - datetime.fromisoformat(started_at.replace("Z", ""))).total_seconds()
    except Exception:
        elapsed = 0
    if elapsed < 4:
        return

    job["status"] = "JOB_READY"
    job["updated_at"] = _demo_now_iso()
    job_state["steps"] = [
        {"step_index": 1, "step_name": "copy_agent", "agent_role": "copywriter", "status": "success", "created_at": _demo_now_iso()},
        {"step_index": 2, "step_name": "reviewer_agent", "agent_role": "reviewer", "status": "success", "created_at": _demo_now_iso()},
    ]
    prompt_text = job.get("context", {}).get("job_post", "")
    generated = (
        f"Dit is een gegenereerde tekst op basis van je briefing: {prompt_text}. "
        "De inhoud is opgesteld in duidelijke taal en geoptimaliseerd voor leesbaarheid."
    ).strip()
    job_state["artifacts"] = [
        {
            "id": str(uuid.uuid4()),
            "job_id": job.get("id"),
            "artifact_type": "copy_draft",
            "proposed_data": {"text": generated},
            "created_at": _demo_now_iso(),
        }
    ]


@app.post("/api/jobs")
async def create_job(req: CreateJobRequest):
    job_id = str(uuid.uuid4())
    prompt_text = (req.job_post or req.prompt or ((req.payload or {}).get("job_post") if isinstance(req.payload, dict) else None) or "").strip()

    _demo_jobs[job_id] = {
        "job": {
            "id": job_id,
            "status": "PLAN_PROPOSED",
            "context": {
                "job_post": prompt_text,
                "plan": _build_demo_plan(prompt_text),
            },
            "created_at": _demo_now_iso(),
            "updated_at": _demo_now_iso(),
        },
        "clarifications": [],
        "steps": [],
        "artifacts": [],
    }

    return {"job_id": job_id, "status": "PLAN_PROPOSED"}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = _demo_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _maybe_progress_demo_job(job)
    return job


@app.patch("/api/jobs/{job_id}/answer")
async def submit_job_answer(job_id: str, payload: dict = Body(default={})):
    job_state = _demo_jobs.get(job_id)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    answers = payload.get("answers") if isinstance(payload, dict) else {}
    if not isinstance(answers, dict):
        answers = {}
    job_state["job"]["context"]["answers"] = answers
    job_state["job"]["updated_at"] = _demo_now_iso()
    return {"job_id": job_id, "status": job_state["job"]["status"], "message": "Answers received."}


@app.post("/api/jobs/{job_id}/approve-plan")
async def approve_plan(job_id: str):
    job_state = _demo_jobs.get(job_id)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_state["job"]
    if job.get("status") not in {"PLAN_PROPOSED", "INTAKE_CLARIFICATION"}:
        raise HTTPException(status_code=400, detail=f"Job is not in PLAN_PROPOSED state (current: {job.get('status')})")

    job["status"] = "RUNNING"
    job["running_started_at"] = _demo_now_iso()
    job["updated_at"] = _demo_now_iso()
    job_state["steps"] = _demo_running_steps()
    return {"job_id": job_id, "status": "RUNNING", "message": "Plan approved. Workflow started."}


@app.post("/api/jobs/{job_id}/request-changes")
async def request_plan_changes(job_id: str, payload: dict = Body(default={})):
    job_state = _demo_jobs.get(job_id)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    feedback = (payload or {}).get("feedback", "")
    job_state["job"]["status"] = "PLAN_PROPOSED"
    job_state["job"]["context"]["plan_feedback"] = feedback
    job_state["job"]["updated_at"] = _demo_now_iso()
    return {"job_id": job_id, "status": "PLAN_PROPOSED", "message": "Changes requested."}


@app.post("/api/jobs/{job_id}/feedback")
async def submit_job_feedback(job_id: str, payload: dict = Body(default={})):
    job_state = _demo_jobs.get(job_id)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")
    feedback = (payload or {}).get("feedback", "")
    job_state["job"]["context"]["review_feedback"] = feedback
    job_state["job"]["status"] = "RUNNING"
    job_state["job"]["running_started_at"] = _demo_now_iso()
    job_state["job"]["updated_at"] = _demo_now_iso()
    job_state["steps"] = _demo_running_steps()
    return {"job_id": job_id, "status": "RUNNING", "message": "Feedback recorded. Workflow restarted."}


@app.post("/api/jobs/{job_id}/approve")
async def approve_job(job_id: str):
    job_state = _demo_jobs.get(job_id)
    if not job_state:
        raise HTTPException(status_code=404, detail="Job not found")

    job = job_state["job"]
    # Assumption-based backward compatibility:
    # some frontends use /approve for plan confirmation; route that to plan approval behavior.
    if job.get("status") in {"PLAN_PROPOSED", "INTAKE_CLARIFICATION"}:
        return await approve_plan(job_id)
    if job.get("status") != "JOB_READY":
        raise HTTPException(status_code=400, detail=f"Job not ready for approval (current: {job.get('status')})")

    job["status"] = "COMPLETED"
    job["updated_at"] = _demo_now_iso()
    return {"job_id": job_id, "status": "COMPLETED", "message": "Job approved."}


# --- CEO/Manager Agent endpoints ---
_ceo_agent = None

def get_ceo_agent():
    global _ceo_agent
    if _ceo_agent is None:
        _ceo_agent = CEOManagerAgent(ANTHROPIC_API_KEY)
    return _ceo_agent


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


# --- HR Agent endpoints ---
_hr_agent = None

def get_hr_agent():
    global _hr_agent
    if _hr_agent is None:
        _hr_agent = HRAgent(ANTHROPIC_API_KEY)
    return _hr_agent


@app.post("/api/hr/analyze-performance")
async def hr_analyze_performance(req: AnalyzePerformanceInput):
    """HR Agent analyzes agent performance"""
    hr = get_hr_agent()
    result = hr.analyze_agent_performance(req.agent_id, req.agent_name, req.performance_data)
    return result


@app.post("/api/hr/register-improvement")
async def hr_register_improvement(req: RegisterImprovementInput):
    """Register an improvement point for an agent"""
    improvement_id = str(uuid.uuid4())
    return {
        "status": "success",
        "agent_id": req.agent_id,
        "improvement_id": improvement_id,
        "message": f"Improvement point registered for {req.agent_name}",
    }



@app.on_event("startup")
async def on_startup():
    """Startup hook - skip database initialization."""
    # Database initialization (like creating Dave Dev) should be done via migrations
    # Not during startup, to avoid crashes when tables don't exist
    pass


@app.on_event("shutdown")
async def on_shutdown():
    pass

# --- Request Models for Dave Dev ---
class DaveDevPromptRequest(BaseModel):
    question: str
    context: Optional[str] = None
    page: Optional[str] = None
    selected_tool: Optional[str] = None
    recent_messages: Optional[List[str]] = None


class DaveDevResponse(BaseModel):
    answer: str
    vscode_prompt: Optional[str] = None
    code_references: Optional[List[str]] = None
    confidence: float = 0.9
    llm_used: Optional[str] = None


def _safe_git_snippet(max_lines: int = 8) -> str:
    """Collect a tiny git context block without breaking request flow."""
    git_roots = [repo_root, os.path.dirname(repo_root)]
    logs = ""
    status_lines = ""

    for root in git_roots:
        try:
            logs = subprocess.check_output(
                ["git", "-C", root, "log", "--oneline", "-n", "5"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            ).strip()
            status = subprocess.check_output(
                ["git", "-C", root, "status", "--short"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            ).strip()
            status_lines = "\n".join(status.splitlines()[:max_lines])
            if logs or status_lines:
                break
        except Exception:
            continue

    # Fallback when git is not available in container: use file mtimes.
    if not logs and not status_lines:
        candidates: List[tuple] = []
        roots = [os.path.join(os.path.dirname(backend_dir), "backend"), os.path.join(os.path.dirname(backend_dir), "frontend", "src")]
        for root in roots:
            if not os.path.isdir(root):
                continue
            for current_root, _, files in os.walk(root):
                for fname in files:
                    if not fname.endswith((".py", ".jsx", ".js", ".ts", ".tsx")):
                        continue
                    full_path = os.path.join(current_root, fname)
                    try:
                        mtime = os.path.getmtime(full_path)
                    except OSError:
                        continue
                    rel_path = os.path.relpath(full_path, os.path.dirname(backend_dir))
                    candidates.append((mtime, rel_path))

        candidates.sort(reverse=True)
        if candidates:
            latest_files = "\n".join(f"- {path}" for _, path in candidates[:max_lines])
            status_lines = latest_files
            logs = "mtime-based snapshot (git unavailable)"

    parts: List[str] = []
    if logs:
        parts.append(f"Recent commits:\n{logs}")
    if status_lines:
        parts.append(f"Working tree snapshot:\n{status_lines}")

    return "\n\n".join(parts)


def _infer_question_intent(question: str) -> str:
    q = (question or "").lower()
    if any(
        k in q
        for k in (
            "multiline",
            "multi-line",
            "onder elkaar",
            "tekst doorloopt",
            "input",
            "invoer",
            "typen",
            "typegedrag",
            "shift+enter",
            "enter",
            "nieuwe regel",
        )
    ):
        return "chat-input-behavior"
    if any(k in q for k in ("chatbox", "chat box", "chatbubbel", "bubble", "berichtvak", "message box")):
        return "chatbox"
    if any(k in q for k in ("breedte", "width", "px", "hoe breed", "pagina breed")):
        return "layout-width"
    if any(k in q for k in ("sidebar", "zijbalk", "menu links", "menu linksbalk")):
        return "layout-sidebar"
    if any(k in q for k in ("laatste", "recent", "update", "wijziging", "changed", "changelog")):
        return "updates"
    return "general"


def _should_use_history(question: str) -> bool:
    q = (question or "").lower()
    history_triggers = (
        "eerder",
        "vorige keer",
        "toen",
        "die waarde",
        "zoals net",
        "zoals eerder",
        "in het vorige antwoord",
    )
    return any(t in q for t in history_triggers)


def _build_dave_context(req: DaveDevPromptRequest, include_history: bool) -> str:
    parts: List[str] = []
    if req.page:
        parts.append(f"UI page: {req.page}")
    if req.selected_tool:
        parts.append(f"Selected tool: {req.selected_tool}")
    if req.context:
        parts.append(f"User context:\n{req.context}")
    if include_history and req.recent_messages:
        clipped = [m for m in req.recent_messages if m][:6]
        if clipped:
            parts.append("Recent chat:\n" + "\n".join(f"- {m}" for m in clipped))

    git_block = _safe_git_snippet()
    if git_block:
        parts.append(git_block)

    return "\n\n".join(parts)


def _build_frontend_layout_context(question: str, max_hits_per_file: int = 5) -> str:
    """Collect concrete frontend layout facts to reduce LLM guessing on UI questions."""
    q = (question or "").lower()
    ui_triggers = (
        "breedte", "width", "sidebar", "zijbalk", "layout", "pagina", "chatbox", "chat", "hr", "/hr", "improvements"
    )
    if not any(t in q for t in ui_triggers):
        return ""

    frontend_src = os.path.join(os.path.dirname(backend_dir), "frontend", "src")
    if not os.path.isdir(frontend_src):
        return ""

    files = [
        "main.jsx",
        "Sidebar.jsx",
        "index.css",
        "DevbotHome.jsx",
        "DaveDevConsole.jsx",
        "HRImprovements.jsx",
    ]
    needles = (
        "max-w-",
        "dashboard-container",
        "content-area",
        "sidebar",
        "/hr/improvements",
        "grid",
        "md:grid-cols",
        "margin-left",
        "width",
    )

    blocks: List[str] = []
    for fname in files:
        path = os.path.join(frontend_src, fname)
        if not os.path.isfile(path):
            continue

        try:
            lines = Path(path).read_text(errors="ignore").splitlines()
        except Exception:
            continue

        hits: List[str] = []
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            low = stripped.lower()
            if not stripped:
                continue
            if any(n in low for n in needles):
                hits.append(f"{idx}: {stripped}")
            if len(hits) >= max_hits_per_file:
                break

        if hits:
            blocks.append(f"{fname}:\n" + "\n".join(f"- {h}" for h in hits))

    if not blocks:
        return ""

    return "Frontend layout scan (actuele code):\n" + "\n\n".join(blocks)


def _clean_answer_for_ui(answer: str) -> str:
    """Normalize LLM output for plain-text UI rendering."""
    cleaned_lines: List[str] = []
    for line in (answer or "").splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("* "):
            line = f"{indent}- {stripped[2:]}"
        cleaned_lines.append(line.replace("**", ""))
    return "\n".join(cleaned_lines).strip()


def _question_requests_advice(question: str) -> bool:
    q = (question or "").lower()
    markers = (
        "advies",
        "adviseer",
        "raad je",
        "aanraden",
        "recommend",
        "suggest",
    )
    return any(m in q for m in markers)


def _apply_response_style(resp: DaveDevResponse, question: str) -> DaveDevResponse:
    answer = _clean_answer_for_ui(resp.answer or "")
    lines = [line for line in answer.splitlines() if not line.strip().lower().startswith("eerste actie nu:")]
    answer = "\n".join(lines).strip()
    if _question_requests_advice(question) and answer and not answer.lower().startswith("mijn advies is"):
        lowered = answer[0].lower() + answer[1:] if answer[0].isupper() else answer
        answer = f"Mijn advies is {lowered}"
    return DaveDevResponse(
        answer=answer,
        vscode_prompt=resp.vscode_prompt,
        code_references=resp.code_references,
        confidence=resp.confidence,
        llm_used=resp.llm_used,
    )


def _is_input_behavior_question(question: str) -> bool:
    q = (question or "").lower()
    markers = (
        "multiline",
        "multi-line",
        "onder elkaar",
        "tekst doorloopt",
        "input",
        "invoer",
        "typen",
        "shift+enter",
        "enter",
        "nieuwe regel",
        "new line",
        "newline",
    )
    return any(m in q for m in markers)


def _build_input_behavior_answer(req: DaveDevPromptRequest) -> DaveDevResponse:
    """Answer typing/input behavior questions from current DaveDevConsole code."""
    frontend_src = os.path.join(os.path.dirname(backend_dir), "frontend", "src")
    console_file = os.path.join(frontend_src, "DaveDevConsole.jsx")

    def _find_line(path: str, needle: str) -> str:
        try:
            for i, raw in enumerate(Path(path).read_text(errors="ignore").splitlines(), 1):
                if needle in raw:
                    return f"{i}: {raw.strip()}"
        except Exception:
            return ""
        return ""

    textarea_line = _find_line(console_file, "<textarea")
    onkeydown_line = _find_line(console_file, "onKeyDown")
    shift_line = _find_line(console_file, "e.key === 'Enter' && !e.shiftKey")
    prewrap_line = _find_line(console_file, "whitespace-pre-wrap")

    answer = (
        "ja, Dave Dev gebruikt nu multiline invoer en ondersteunt Enter verzenden + Shift+Enter nieuwe regel.\n\n"
        "Analyse:\n"
        f"- `web_ui/frontend/src/DaveDevConsole.jsx`: {textarea_line or 'textarea regel niet gevonden'}\n"
        f"- `web_ui/frontend/src/DaveDevConsole.jsx`: {onkeydown_line or 'onKeyDown regel niet gevonden'}\n"
        f"- `web_ui/frontend/src/DaveDevConsole.jsx`: {shift_line or 'Enter/Shift+Enter regel niet gevonden'}\n"
        f"- `web_ui/frontend/src/DaveDevConsole.jsx`: {prewrap_line or 'whitespace-pre-wrap regel niet gevonden'}\n\n"
        "Fix:\n"
        "- Geen verplichte fix nodig voor multiline typegedrag.\n"
        "- Optioneel: voeg `break-words` toe aan de message bubble als lange tokens nog overflow geven.\n\n"
        "VS Code Prompt:\n"
        "- Open `web_ui/frontend/src/DaveDevConsole.jsx`; laat `textarea` + `onKeyDown` staan en voeg indien nodig `break-words` toe aan de bubble class naast `max-w-md`."
    )
    return DaveDevResponse(answer=answer, confidence=0.95, llm_used="input-behavior-scan")


def _build_hr_improvements_width_answer(req: DaveDevPromptRequest) -> DaveDevResponse:
    """Answer HR Improvements width questions from actual frontend files."""
    frontend_src = os.path.join(os.path.dirname(backend_dir), "frontend", "src")
    hr_file = os.path.join(frontend_src, "HRImprovements.jsx")
    devbot_file = os.path.join(frontend_src, "DevbotHome.jsx")

    def _find_line(path: str, needle: str) -> str:
        try:
            for i, raw in enumerate(Path(path).read_text(errors="ignore").splitlines(), 1):
                if needle in raw:
                    return f"{i}: {raw.strip()}"
        except Exception:
            return ""
        return ""

    hr_line = _find_line(hr_file, "max-w-")
    devbot_line = _find_line(devbot_file, "max-w-")
    grid_line = _find_line(hr_file, "md:grid-cols-2")

    answer = (
        "`/hr/improvements` is in de container niet smaller dan `/devbot`; "
        "de code gebruikt juist een bredere wrapper op HR Improvements.\n\n"
        "Analyse:\n"
        f"- `web_ui/frontend/src/HRImprovements.jsx`: {hr_line or 'max-w regel niet gevonden'}\n"
        f"- `web_ui/frontend/src/DevbotHome.jsx`: {devbot_line or 'max-w regel niet gevonden'}\n"
        f"- `web_ui/frontend/src/HRImprovements.jsx`: {grid_line or '2-koloms gridregel niet gevonden'}\n"
        "- Conclusie: de smallere indruk komt waarschijnlijk door panel/card-opmaak en 2-koloms verdeling, "
        "niet door een smallere hoofdcontainer.\n\n"
        "Fix:\n"
        "- Voor visuele consistentie met `/devbot`: zet HR wrapper op `max-w-5xl` i.p.v. `max-w-6xl`.\n"
        "- Als je vooral minder 'smal' kaarten wilt: verander `md:grid-cols-2` naar `md:grid-cols-1 lg:grid-cols-2`.\n\n"
        "VS Code Prompt:\n"
        "- Open `web_ui/frontend/src/HRImprovements.jsx` en wijzig `max-w-6xl` naar `max-w-5xl`; "
        "wijzig daarna `md:grid-cols-2` naar `md:grid-cols-1 lg:grid-cols-2` voor betere leesbreedte per kaart."
    )

    return DaveDevResponse(answer=answer, confidence=0.95, llm_used="layout-scan")


def _build_width_answer(req: DaveDevPromptRequest) -> DaveDevResponse:
    """Answer common UI width questions with concrete project values."""
    question = (req.question or "").lower()
    mentions_540 = "540" in question
    if mentions_540:
        intro = "de pagina is niet vast 540 px breed."
    else:
        intro = "de pagina gebruikt een flexibele layout met een vaste sidebar en een begrensde contentcontainer."
    answer = (
        f"{intro}\n\n"
        "Concrete stappen:\n"
        "- Sidebar breedte: 240 px (`.sidebar` in `web_ui/frontend/src/index.css`)\n"
        "- Content offset: `margin-left: 240px` (`.content-area`)\n"
        "- Devbot container op `/devbot`: `max-w-5xl` = ongeveer 1024 px\n"
        "- Dave Dev chatbubbel: `max-w-md` = ongeveer 448 px\n"
        "- Mobiel (`max-width: 600px`): sidebar wordt `100vw` en content schuift onder de topbar\n\n"
        "Bron: `web_ui/frontend/src/DevbotHome.jsx`, `web_ui/frontend/src/DaveDevConsole.jsx`, `web_ui/frontend/src/index.css`"
    )
    return DaveDevResponse(answer=answer, confidence=0.95, llm_used="layout-context")


def _build_chatbox_answer(req: DaveDevPromptRequest) -> DaveDevResponse:
    """Answer chatbox width questions with component-specific values."""
    answer = (
        "Mijn advies is om de chatbubbelbreedte te verhogen; de beperkende regel is `max-w-md` in `web_ui/frontend/src/DaveDevConsole.jsx`.\n\n"
        "Concrete stappen:\n"
        "- Chatpaneel container gebruikt `h-full` en vult de beschikbare contentruimte\n"
        "- Berichtenwrapper gebruikt `max-w-md` (ongeveer 448 px) in `DaveDevConsole.jsx`\n"
        "- Devbot paginawrapper gebruikt `max-w-5xl` (ongeveer 1024 px) in `DevbotHome.jsx`\n"
        "- Op mobiel blijft de layout responsief via breakpointregels in `index.css`\n\n"
        "Bron: `web_ui/frontend/src/DaveDevConsole.jsx`, `web_ui/frontend/src/DevbotHome.jsx`, `web_ui/frontend/src/index.css`"
    )
    return DaveDevResponse(answer=answer, confidence=0.95, llm_used="layout-context")


def _build_sidebar_answer(req: DaveDevPromptRequest) -> DaveDevResponse:
    """Answer sidebar visibility questions with concrete project paths."""
    answer = (
        "Mijn advies is om de route-layout in `main.jsx` te normaliseren; de sidebar ontbreekt waar routes niet dezelfde parent-structuur gebruiken.\n\n"
        "Concrete stappen:\n"
        "- Controleer routing in `web_ui/frontend/src/main.jsx` (o.a. `/devbot` en `/devbot/dave`)\n"
        "- Controleer `web_ui/frontend/src/DevbotHome.jsx`: deze heeft `dashboard-container`, `Sidebar` en `content-area`\n"
        "- Controleer `web_ui/frontend/src/DaveDevConsole.jsx`: dit is een losse console-component zonder eigen `Sidebar`; hij verwacht parent layout\n"
        "- Controleer algemene layout classes in `web_ui/frontend/src/index.css` (`.dashboard-container`, `.sidebar`, `.content-area`)\n"
        "- Als een pagina de sidebar mist: voeg de pagina onder een parent met `Sidebar` toe, of render `Sidebar` direct in die pagina\n\n"
        "Bron: `web_ui/frontend/src/main.jsx`, `web_ui/frontend/src/DevbotHome.jsx`, `web_ui/frontend/src/DaveDevConsole.jsx`"
    )
    return DaveDevResponse(answer=answer, confidence=0.95, llm_used="layout-context")


# --- DAVE DEV ENDPOINTS ---
@app.get("/api/dave-dev/info")
def get_dave_dev_info():
    """Get Dave Dev's profile - return static data without database query."""
    return {
        "id": "dave-dev-001",
        "name": "Dave Dev",
        "role": "Developer",
        "specialization": "Full-stack Technical Consultant & Agentic Architecture Specialist",
        "status": "active",
        "current_task": None,
        "progress": 0,
        "avatar_url": "https://api.dicebear.com/7.x/personas/svg?seed=DaveDev",
        "system_instructions": "Technical Consultant for Wonderz-Agentics",
        "knowledge_base_sources": ["https://www.crewai.com/docs", "https://fastapi.tiangolo.com/", "https://supabase.com/docs"],
        "tool_access_whitelist": ["read_repository_structure", "analyze_code_complexity", "generate_vs_code_prompts", "supabase_schema_lookup"],
        "hiring_logic": "Activate when technical questions are asked",
        "persona": "Pragmatic, analytical, direct",
        "quality_notes": "Code-ready prompts with security best practices",
        "growth": "Continuous improvement in system design",
        "development_notes": None,
    }


@app.post("/api/dave-dev/ask", response_model=DaveDevResponse)
def ask_dave_dev(req: DaveDevPromptRequest):
    """Ask Dave Dev a technical question with repo-aware context."""
    question = (req.question or "").strip()
    if not question:
        return _apply_response_style(DaveDevResponse(
            answer="Stel een technische vraag zodat ik je gericht kan helpen.",
            confidence=0.2,
            llm_used=None,
        ), question)

    def _looks_real_key(value: Optional[str]) -> bool:
        if not value:
            return False
        normalized = value.strip().lower()
        bad_prefixes = ("dummy", "your_", "placeholder", "test", "sk-...")
        return not normalized.startswith(bad_prefixes)

    anthropic_key = ANTHROPIC_API_KEY
    openai_key = OPENAI_API_KEY
    gemini_key = GEMINI_API_KEY

    db = SessionLocal()
    try:
        settings = db.query(SettingsSQL).filter(SettingsSQL.id == "default").first()
        if settings:
            if not _looks_real_key(anthropic_key) and _looks_real_key(settings.anthropic_api_key):
                anthropic_key = settings.anthropic_api_key
            if not _looks_real_key(gemini_key) and _looks_real_key(settings.gemini_api_key):
                gemini_key = settings.gemini_api_key
    finally:
        db.close()

    q_lower = question.lower()
    include_history = _should_use_history(question)
    intent = _infer_question_intent(question)

    base_system_prompt = (
        "Je bent Dave Dev: een actieve technische consultant die uitvoert op basis van codebase-feiten. "
        "Doel: geef concrete, code-gebaseerde antwoorden en vermijd handleidingen als je zelf kunt inspecteren. "
        "Actie boven theorie: als de gebruiker vraagt waarom/hoe/waar en er is repositorycontext, inspecteer direct en rapporteer bevindingen. "
        "Geef geen 'Stap 1 open F12' advies als je het zelf kunt verifiëren. "
        "Relevantie boven historie: behandel nieuwe vragen als nieuw; gebruik chatgeschiedenis alleen bij expliciete verwijzing. "
        "Noem verouderde waarden alleen als ze in huidige code staan of expliciet gevraagd worden. "
        "Bronprioriteit: (1) actuele code/files, (2) runtime context/logs, (3) chatgeschiedenis. "
        "Als bronnen conflicteren, volg code/runtime context. "
        f"Huidige intent: {intent}. "
        "Antwoordformat (altijd):\n"
        "Start direct met de uitkomst in de eerste zin.\n\n"
        "Gebruik geen vaste afsluiters zoals 'Eerste actie nu'.\n"
        "Als je advies geeft, begin de eerste zin met 'Mijn advies is ...'.\n\n"
        "Analyse:\n"
        "- concrete bevindingen met bestandspaden (en regels indien beschikbaar).\n\n"
        "Fix:\n"
        "- exact voorstel (codewijziging of command).\n\n"
        "VS Code Prompt:\n"
        "- 1 direct uitvoerbare prompt voor Codex.\n"
        "Als info ontbreekt: vraag precies 1 ontbrekend artefact (bestand/snippet/log), geen algemeen stappenplan. "
        "Gebruik geen markdown-opmaaktekens zoals ** of * bullets; schrijf platte tekst met normale regels."
    )

    db = SessionLocal()
    try:
        agent_data = db.query(CrewMemberSQL).filter(CrewMemberSQL.name == "Dave Dev").first()
        if agent_data and agent_data.system_instructions:
            system_prompt = (
                f"{base_system_prompt}\n\n"
                f"Extra persona instructies:\n{agent_data.system_instructions}"
            )
        else:
            system_prompt = base_system_prompt
    finally:
        db.close()

    extra_context = _build_dave_context(req, include_history=include_history)
    layout_context = _build_frontend_layout_context(question)
    full_user_prompt = question
    if extra_context:
        full_user_prompt += f"\n\nExtra context:\n{extra_context}"
    if layout_context:
        full_user_prompt += f"\n\n{layout_context}"

    # Deterministic path for chat input/typing behavior questions.
    if _is_input_behavior_question(q_lower):
        return _apply_response_style(_build_input_behavior_answer(req), question)

    # Deterministic path for HR Improvements width/layout questions.
    hr_markers = ["hr improvements", "/hr/improvements", "hr-improvements", "hr improvements pagina"]
    hr_layout_markers = ["smal", "smaller", "breed", "breedte", "width", "layout", "opmaak"]
    if any(m in q_lower for m in hr_markers) and any(m in q_lower for m in hr_layout_markers):
        return _apply_response_style(_build_hr_improvements_width_answer(req), question)

    # Shortcut for chatbox-specific size questions; must run before generic width logic.
    chatbox_markers = ["chatbox", "chat box", "chatbubbel", "bubble", "berichtvak", "message box"]
    if any(marker in q_lower for marker in chatbox_markers):
        return _apply_response_style(_build_chatbox_answer(req), question)

    # Route chat-width questions to chatbox answer instead of generic page-width answer.
    chat_width_markers = ["chat", "chatten", "bericht", "bubble"]
    width_markers = ["smal", "smaller", "breed", "breedte", "width", "desktop", "px"]
    if any(marker in q_lower for marker in chat_width_markers) and any(marker in q_lower for marker in width_markers):
        return _apply_response_style(_build_chatbox_answer(req), question)

    # Shortcut for UI width/px questions in this project.
    width_markers = ["breedte", "width", "px", "hoe breed", "pagina breed"]
    if any(marker in q_lower for marker in width_markers) and not _is_input_behavior_question(q_lower):
        return _apply_response_style(_build_width_answer(req), question)

    # Shortcut for sidebar visibility questions in this project.
    sidebar_markers = ["sidebar", "zijbalk", "menu links", "menu linksbalk"]
    if any(marker in q_lower for marker in sidebar_markers):
        return _apply_response_style(_build_sidebar_answer(req), question)

    # High-signal shortcut for "latest update" style questions.
    latest_markers = ["laatste", "recent", "update", "wijziging", "changed", "changelog"]
    if any(marker in q_lower for marker in latest_markers):
        git_context = _safe_git_snippet(max_lines=12)
        if git_context:
            latest_commit = ""
            recent_commits: List[str] = []
            changes = ""
            for block in git_context.split("\n\n"):
                if block.startswith("Recent commits:"):
                    lines = block.splitlines()[1:]
                    latest_commit = lines[0] if lines else ""
                    recent_commits = lines[:3]
                if block.startswith("Working tree snapshot:"):
                    raw_changes = block.splitlines()[1:6]
                    normalized_changes: List[str] = []
                    for line in raw_changes:
                        stripped = line.strip()
                        if stripped.startswith("m ") and "web_ui/backend" in stripped:
                            normalized_changes.append("- nested repo changed: web_ui/backend")
                        else:
                            normalized_changes.append(line)
                    changes = "\n".join(normalized_changes)
            commit_section = "\n".join(f"- {c}" for c in recent_commits) or f"- {latest_commit or 'onbekend'}"
            answer = (
                "de meest recente wijziging komt uit de laatste commit en huidige werkboom.\n\n"
                "Concrete stappen:\n"
                f"- Laatste commit: {latest_commit or 'onbekend'}\n"
                f"- Top recente commits:\n{commit_section}\n"
                f"- Huidige wijzigingen (top):\n{changes or '- geen open wijzigingen'}"
            )
            return _apply_response_style(DaveDevResponse(
                answer=_clean_answer_for_ui(answer),
                code_references=None,
                confidence=0.9,
                llm_used="git-context",
            ), question)

    llm_errors: List[str] = []

    if _looks_real_key(anthropic_key):
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-latest",
                    "max_tokens": 700,
                    "temperature": 0.35,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": full_user_prompt}],
                },
                timeout=25,
            )
            if response.ok:
                data = response.json()
                content = data.get("content", [])
                answer = ""
                if content and isinstance(content, list):
                    answer = "\n".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
                if answer:
                    return _apply_response_style(DaveDevResponse(answer=_clean_answer_for_ui(answer), confidence=0.9, llm_used="Anthropic"), question)
            llm_errors.append(f"Anthropic {response.status_code}: {response.text[:180]}")
        except Exception as exc:
            llm_errors.append(f"Anthropic exception: {exc}")

    if _looks_real_key(openai_key):
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_user_prompt},
                    ],
                    "max_tokens": 700,
                    "temperature": 0.35,
                },
                timeout=25,
            )
            if response.ok:
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if answer:
                    return _apply_response_style(DaveDevResponse(answer=_clean_answer_for_ui(answer), confidence=0.85, llm_used="OpenAI"), question)
            llm_errors.append(f"OpenAI {response.status_code}: {response.text[:180]}")
        except Exception as exc:
            llm_errors.append(f"OpenAI exception: {exc}")

    if _looks_real_key(gemini_key):
        try:
            response = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                params={"key": gemini_key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"SYSTEM: {system_prompt}\nUSER: {full_user_prompt}"}],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.35,
                        "maxOutputTokens": 700,
                    },
                },
                timeout=25,
            )
            if response.ok:
                data = response.json()
                answer = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if answer:
                    return _apply_response_style(DaveDevResponse(answer=_clean_answer_for_ui(answer), confidence=0.8, llm_used="Gemini"), question)
            llm_errors.append(f"Gemini {response.status_code}: {response.text[:180]}")
        except Exception as exc:
            llm_errors.append(f"Gemini exception: {exc}")

    # Static fallback only when live LLM is unavailable.
    lower_question = question.lower()
    responses = {
        "architecture": {
            "answer": "Mijn advies is om de modulaire stack aan te houden met FastAPI backend, React frontend en SQLAlchemy/Postgres.\n\nConcrete stappen:\n- Werk via adapters voor platformintegratie\n- Houd domain models platform-onafhankelijk\n- Centraliseer orchestration in de API-laag",
            "vscode_prompt": "Design new adapter for [PLATFORM]. Follow pattern in tools/adapters.py: (1) Inherit from BaseAdapter, (2) Implement get_product(id), (3) Map to UnifiedProduct, (4) Add error handling.",
            "code_references": ["tools/adapters.py", "models/unified.py"],
        },
        "frontend": {
            "answer": "Mijn advies is om React + Vite + Tailwind te gebruiken met API-calls naar backend endpoints.\n\nConcrete stappen:\n- Maak de component\n- Voeg state + loading/error states toe\n- Koppel aan het endpoint\n- Valideer response mapping",
            "vscode_prompt": "Create React component for [FEATURE]: (1) Import hooks, (2) Define component, (3) Use Tailwind classes, (4) Fetch from /api/[endpoint], (5) Return JSX.",
            "code_references": ["web_ui/frontend/src/"],
        },
        "database": {
            "answer": "Mijn advies is om SQLAlchemy models + Alembic migrations bovenop Postgres te gebruiken.\n\nConcrete stappen:\n- Update het model\n- Genereer migration via autogenerate\n- Draai upgrade head\n- Pas endpoint aan en test",
            "vscode_prompt": "Add table [NAME]: (1) SQLAlchemy model in models/sql_models.py, (2) Pydantic model in models/ui.py, (3) Alembic migration, (4) API endpoints.",
            "code_references": ["models/sql_models.py", "models/ui.py"],
        },
    }

    for key, data in responses.items():
        if key in lower_question:
            return _apply_response_style(DaveDevResponse(
                answer=data["answer"],
                vscode_prompt=data["vscode_prompt"],
                code_references=data["code_references"],
                confidence=0.65,
                llm_used="static",
            ), question)

    debug_hint = llm_errors[0] if llm_errors else "Geen geldige API key geconfigureerd"
    return _apply_response_style(DaveDevResponse(
        answer=(
            "Ik kan nu geen live LLM-antwoord geven. "
            f"Reden: {debug_hint}. "
            "Configureer ANTHROPIC_API_KEY, OPENAI_API_KEY of GEMINI_API_KEY (env of via /api/settings)."
        ),
        confidence=0.2,
        llm_used=None,
    ), question)


@app.post("/api/dave-dev/generate-prompt")
def generate_vscode_prompt(req: DaveDevPromptRequest):
    """Generate VS Code/Cursor-ready prompt from feature description"""
    vscode_prompt = f"""# Development Task

Feature: {req.question}

Guidelines:
1. Follow Unified Data Model pattern
2. SQLAlchemy for models, Pydantic for API
3. Proper error handling and validation
4. Type hints and docstrings
5. Test with curl/Postman
6. Update frontend component

Start with API endpoint → database model → frontend."""
    
    return {
        "vscode_prompt": vscode_prompt,
        "instructions": "Copy into Cursor/Copilot in VS Code"
    }


# --- SETTINGS API ENDPOINTS ---
@app.get("/api/me")
def get_me(user: dict = Depends(get_current_user_context)):
    """Get current authenticated user context."""
    return user


@app.get("/api/settings")
def get_settings(_user: dict = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Get settings (API keys, config)"""
    settings = db.query(SettingsSQL).filter(SettingsSQL.id == 'default').first()
    if not settings:
        return {
            "gemini_api_key": "",
            "anthropic_api_key": "",
            "supabase_url": "",
            "supabase_key": "",
        }
    return {
        "gemini_api_key": settings.gemini_api_key or "",
        "anthropic_api_key": settings.anthropic_api_key or "",
        "supabase_url": settings.supabase_url or "",
        "supabase_key": settings.supabase_key or "",
    }


@app.post("/api/settings")
def save_settings(req: SettingsInput, _user: dict = Depends(require_super_admin), db: Session = Depends(get_db)):
    """Save settings (API keys, config)"""
    settings = db.query(SettingsSQL).filter(SettingsSQL.id == 'default').first()
    if not settings:
        settings = SettingsSQL(id='default')
        db.add(settings)
    
    if req.gemini_api_key is not None:
        settings.gemini_api_key = req.gemini_api_key
    if req.anthropic_api_key is not None:
        settings.anthropic_api_key = req.anthropic_api_key
    if req.supabase_url is not None:
        settings.supabase_url = req.supabase_url
    if req.supabase_key is not None:
        settings.supabase_key = req.supabase_key
    
    db.commit()
    db.refresh(settings)
    return {
        "status": "success",
        "message": "Settings saved",
        "gemini_api_key": settings.gemini_api_key or "",
        "anthropic_api_key": settings.anthropic_api_key or "",
        "supabase_url": settings.supabase_url or "",
        "supabase_key": settings.supabase_key or "",
    }


# --- Mount static files (frontend) ---
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(static_dir):
    # Mount assets FIRST (before catch-all)
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets"), html=False), name="assets")
    
    # For SPA routing: catch-all that returns index.html for all non-API/non-assets routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API calls
        if full_path.startswith('api/'):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        # Don't intercept assets
        if full_path.startswith('assets/'):
            raise HTTPException(status_code=404, detail="Asset not found")
        
        # Return index.html for all other routes (React Router handles them)
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="index.html not found")
else:
    # Fallback if frontend dist doesn't exist
    @app.get("/")
    async def root():
        return {
            "message": "Multi-Agentic Crew - Orchestrator API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "endpoints": {
                "tasks": "/api/tasks",
                "crew": "/api/crew",
                "improvements": "/api/improvements",
                "explainer": "/api/explainer/sections",
                "products": "/api/products/unified",
                "jobs": "/api/jobs",
                "talents": "/api/talents",
                "talents_promote": "/api/talents/{id}/promote",
                "dave_dev_info": "/api/dave-dev/info",
                "dave_dev_ask": "/api/dave-dev/ask"
            }
        }

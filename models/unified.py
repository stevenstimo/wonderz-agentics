from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


# ============ Job Status Enum ============
class JobStatus(str, Enum):
    """Lifecycle states for a job from intake to completion."""
    INTAKE_CLARIFICATION = "INTAKE_CLARIFICATION"  # CEO asking clarification questions
    PLAN_PROPOSED = "PLAN_PROPOSED"                 # CEO has proposed a plan, awaiting user approval
    RUNNING = "RUNNING"                             # Job is executing
    JOB_READY = "JOB_READY"                         # CEO has finished, awaiting final user approval
    COMPLETED = "COMPLETED"                         # Job approved and deployed
    CANCELLED = "CANCELLED"                         # Job cancelled
    FAILED = "FAILED"                               # Job failed
    AWAITING_APPROVAL = "AWAITING_APPROVAL"         # Manual approval required during execution


# ============ Intake Models ============
class ClarificationQuestion(BaseModel):
    """A single clarification question from the CEO."""
    id: Any
    question: str
    created_at: datetime


class StrategicBrief(BaseModel):
    """Output of the IntakeEngine: validated job post with completeness status."""
    job_post: str
    is_complete: bool
    clarifications: List[ClarificationQuestion] = []
    context: Dict[str, Any] = Field(default_factory=dict)  # objective, language, tone, focus, etc.
    message: Optional[str] = None  # CEO conversational reply for chat UI


# ============ Strategy/Planning Models ============
class JobStep(BaseModel):
    """A single step in the ExecutionPlan."""
    step_index: int
    agent_role: str  # e.g., "copywriter", "developer", "reviewer"
    unified_tool: str  # e.g., "read_product", "write_description"
    requires_approval: bool = False
    description: str = ""


class ExecutionPlan(BaseModel):
    """Output of StrategyRoom: detailed execution plan."""
    brief: StrategicBrief
    steps: List[JobStep]
    hired_agents: List[str] = []  # e.g., ["copywriter_1", "developer_2"]
    estimated_duration_seconds: int = 0


class JobArtifact(BaseModel):
    """Stores original vs proposed data and feedback."""
    artifact_type: str  # "product", "ad", "content", etc.
    original_data: Dict[str, Any] = Field(default_factory=dict)
    proposed_data: Dict[str, Any] = Field(default_factory=dict)
    review_feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============ Unified Data Models ============
class UnifiedProduct(BaseModel):
    """Universele representatie van een product voor alle platformen."""
    external_id: Any
    source_platform: str = Field(..., description="shopify, wordpress, or custom")
    title: str
    description_html: str
    price: float
    currency: str = "EUR"
    inventory_quantity: int
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    tags: List[str] = []
    attributes: Dict[str, str] = Field(default_factory=dict, description="Custom velden")

class UnifiedAd(BaseModel):
    """Universele representatie van een advertentie (Meta, Google, etc.)."""
    ad_id: Any
    platform: str # meta, google
    status: str # active, paused
    headline: str
    body_text: str
    spend: float
    conversions: int
    roas: float

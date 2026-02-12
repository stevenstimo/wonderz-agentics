from pydantic import BaseModel, Field
from typing import List, Optional

class CrewMember(BaseModel):
    id: str
    name: str
    role: str
    specialization: Optional[str] = None
    status: str  # e.g. 'active', 'busy', 'idle'
    current_task: Optional[str] = None
    progress: int = 0  # percentage
    avatar_url: Optional[str] = None
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[List[str]] = None
    tool_access_whitelist: Optional[List[str]] = None
    hiring_logic: Optional[str] = None
    persona: Optional[str] = None
    quality_notes: Optional[str] = None
    development_notes: Optional[str] = None

class TaskCrewShare(BaseModel):
    crew_id: str
    share: int  # percentage

class Task(BaseModel):
    id: str
    title: str
    status: str  # e.g. 'pending', 'in_progress', 'completed'
    crew: List[TaskCrewShare]
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class ImprovementItem(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    title: str
    summary: Optional[str] = None
    details: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HiredAgent(BaseModel):
    id: str
    name: str
    role: str
    specialization: Optional[str] = None
    status: str = "active"
    permissions: List[str] = []
    system_instructions: Optional[str] = None
    knowledge_base_sources: Optional[List[str]] = None
    tool_access_whitelist: Optional[List[str]] = None
    hiring_logic: Optional[str] = None
    hired_at: Optional[str] = None
    performance_score: float = 0.0
    completed_tasks: int = 0


class ApprovalRequest(BaseModel):
    id: str
    request_type: str
    status: str
    details: dict
    requested_at: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_at: Optional[str] = None


class TrainingSession(BaseModel):
    id: Optional[str] = None
    session_id: Optional[str] = None
    crew_id: str
    agent_name: str
    training_url: str
    training_title: Optional[str] = None
    training_summary: Optional[str] = None
    knowledge_base: Optional[str] = None
    status: str = "pending"
    approval_status: str = "pending"
    requested_at: Optional[str] = None
    approved_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Optional[dict] = None
